from __future__ import annotations

import re
from hashlib import sha1

from pydantic import BaseModel, ConfigDict, Field

from logispace_domain.models_v4 import EvidenceRequirementV4, ResearchBudgetV4, ResearchUnitV4, UnitBudgetV4

FORBIDDEN_PLAN_TERMS = re.compile(
    r"\b(?:event|entity|schema|ontology|json|id)\b|(?:字段|建模|对象粒度|本体|数据库|标注在)", re.IGNORECASE,
)


class SignatureCandidateV4(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=8, max_length=100)
    why_it_matters: str = Field(min_length=4, max_length=180)
    research_focus: list[str] = Field(min_length=1, max_length=3)
    expected_answer: str = Field(min_length=4, max_length=160)
    work_specificity: int = Field(ge=1, le=5)
    core_explanatory_value: int = Field(ge=1, le=5)
    evidence_feasibility: int = Field(ge=1, le=5)
    user_value: int = Field(ge=1, le=5)
    mandatory_overlap: int = Field(ge=1, le=5)
    execution_complexity: int = Field(ge=1, le=5)


def is_plain_language_question(question: str) -> bool:
    text = question.strip()
    if not text.endswith(("？", "?")) or FORBIDDEN_PLAN_TERMS.search(text):
        return False
    if text.count("、") > 1 or len(re.findall(r"以及|还是|分别|又.*又", text)) > 1:
        return False
    return len(text) <= 80


def _score(candidate: SignatureCandidateV4) -> int:
    return (
        candidate.work_specificity * 2
        + candidate.core_explanatory_value * 2
        + candidate.evidence_feasibility
        + candidate.user_value
        - candidate.mandatory_overlap * 2
        - candidate.execution_complexity
    )


def _bigrams(value: str) -> set[str]:
    value = re.sub(r"\W+", "", value.casefold())
    return {value[index:index + 2] for index in range(max(0, len(value) - 1))}


def _similar(left: str, right: str) -> bool:
    a, b = _bigrams(left), _bigrams(right)
    return bool(a and b) and len(a & b) / len(a | b) >= 0.55


def select_signature_candidates(candidates: list[SignatureCandidateV4]) -> list[SignatureCandidateV4]:
    eligible = [item for item in candidates if is_plain_language_question(item.question)]
    if not eligible:
        raise ValueError("No signature candidate passed the plain-language quality gate")
    selected: list[SignatureCandidateV4] = []
    for candidate in sorted(eligible, key=_score, reverse=True):
        if _score(candidate) < 8 and selected:
            continue
        if any(_similar(candidate.question, existing.question) for existing in selected):
            continue
        selected.append(candidate)
        if len(selected) == 3:
            break
    return selected


def compile_signature_units(
    candidates: list[SignatureCandidateV4], budget: ResearchBudgetV4,
) -> list[ResearchUnitV4]:
    selected = select_signature_candidates(candidates)
    per_unit_queries = max(1, min(5, budget.signature_flexible_queries // len(selected)))
    units = []
    for index, candidate in enumerate(selected, start=1):
        slug = sha1(candidate.question.encode("utf-8")).hexdigest()[:8]
        units.append(ResearchUnitV4(
            unit_id=f"signature-{index:02d}-{slug}",
            track="signature",
            domain="work_signature",
            question=candidate.question,
            why_it_matters=candidate.why_it_matters,
            required_outputs=[*candidate.research_focus, f"回答目标：{candidate.expected_answer}"],
            evidence_requirements=EvidenceRequirementV4(
                requires_primary_source=True,
                minimum_independent_sources=1,
                requires_counterevidence_search=True,
            ),
            budget=UnitBudgetV4(
                max_steps=min(20, per_unit_queries + 3),
                max_queries=per_unit_queries,
                max_pages=min(20, max(3, per_unit_queries * 2)),
            ),
            done_when=["问题得到清晰回答", "关键判断有可靠证据", "反例或替代解释已检查"],
            priority=4 if _score(candidate) >= 12 else 3,
        ))
    return units
