from __future__ import annotations

import re
from hashlib import sha1

from pydantic import BaseModel, ConfigDict, Field

from logispace_domain.models_v4 import EvidenceRequirementV4, ResearchBudgetV4, ResearchUnitV4, UnitBudgetV4

FORBIDDEN_PLAN_TERMS = re.compile(
    r"\b(?:event|entity|schema|ontology|json|database id)\b|(?:字段|建模|对象粒度|本体|数据库|实体分类)",
    re.IGNORECASE,
)


class TemporaryPerspectiveV4(BaseModel):
    """A disposable research angle, deliberately not a feature taxonomy."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=60)
    starting_question: str = Field(min_length=8, max_length=140)
    dossier_leads: list[str] = Field(max_length=4)
    why_potentially_distinctive: str = Field(min_length=4, max_length=220)
    information_gain: int = Field(ge=1, le=5)
    evidence_feasibility: int = Field(ge=1, le=5)
    generic_modules_sufficient: bool


class PerspectiveNoteV4(BaseModel):
    model_config = ConfigDict(extra="forbid")
    perspective_title: str
    round: int = Field(ge=1, le=3)
    question: str = Field(min_length=4, max_length=180)
    answer_note: str = Field(min_length=1, max_length=500)
    research_intent: str = Field(min_length=4, max_length=240)
    suggested_queries: list[str] = Field(min_length=1, max_length=3)
    source_urls: list[str] = Field(max_length=5)
    leads: list[str] = Field(max_length=4)
    unresolved: list[str] = Field(max_length=4)
    continue_research: bool
    expected_information_gain: int = Field(ge=1, le=5)


class SignatureResearchUnitV4(BaseModel):
    """The only public shape emitted by post-research signature synthesis."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=80)
    scope: str = Field(min_length=4, max_length=300)
    why_generic_modules_are_insufficient: str = Field(min_length=4, max_length=300)
    research_questions: list[str] = Field(min_length=1, max_length=4)
    known_leads: list[str] = Field(max_length=6)
    unresolved_points: list[str] = Field(max_length=6)


# Compatibility alias for callers which used the old candidate name. Its schema no
# longer contains Feature Schema fields or an overlap penalty.
class SignatureCandidateV4(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question: str = Field(min_length=8, max_length=140)
    why_it_matters: str = Field(min_length=4, max_length=220)
    research_focus: list[str] = Field(min_length=1, max_length=3)
    expected_answer: str = Field(min_length=4, max_length=200)
    work_specificity: int = Field(default=3, ge=1, le=5)
    core_explanatory_value: int = Field(default=3, ge=1, le=5)
    evidence_feasibility: int = Field(default=3, ge=1, le=5)
    user_value: int = Field(default=3, ge=1, le=5)
    execution_complexity: int = Field(default=3, ge=1, le=5)


def is_plain_language_question(question: str) -> bool:
    text = question.strip()
    if not text.endswith(("？", "?")) or FORBIDDEN_PLAN_TERMS.search(text):
        return False
    if text.count("、") > 1 or len(re.findall(r"以及|还是|分别|又.*又", text)) > 1:
        return False
    return len(text) <= 100


def _bigrams(value: str) -> set[str]:
    value = re.sub(r"\W+", "", value.casefold())
    return {value[index:index + 2] for index in range(max(0, len(value) - 1))}


def _similar(left: str, right: str) -> bool:
    a, b = _bigrams(left), _bigrams(right)
    return bool(a and b) and len(a & b) / len(a | b) >= 0.55


def select_perspectives(items: list[TemporaryPerspectiveV4]) -> list[TemporaryPerspectiveV4]:
    """Keep only high-yield gaps; crossing a generic module is explicitly allowed."""
    eligible = [
        item for item in items
        if not item.generic_modules_sufficient
        and item.information_gain >= 3
        and is_plain_language_question(item.starting_question)
    ]
    selected: list[TemporaryPerspectiveV4] = []
    for item in sorted(eligible, key=lambda x: (x.information_gain, x.evidence_feasibility), reverse=True):
        if any(_similar(item.starting_question, prior.starting_question) for prior in selected):
            continue
        selected.append(item)
        if len(selected) == 1:
            break
    if not selected:
        raise ValueError("No perspective exposes a material gap beyond the four generic modules")
    return selected


def select_signature_candidates(candidates: list[SignatureCandidateV4]) -> list[SignatureCandidateV4]:
    """Legacy adapter: deduplicate without penalising overlap with generic modules."""
    eligible = [item for item in candidates if is_plain_language_question(item.question)]
    if not eligible:
        raise ValueError("No signature candidate passed the plain-language quality gate")
    score = lambda x: x.work_specificity * 2 + x.core_explanatory_value * 2 + x.evidence_feasibility + x.user_value - x.execution_complexity
    chosen: list[SignatureCandidateV4] = []
    for item in sorted(eligible, key=score, reverse=True):
        if score(item) < 18 and chosen:
            continue
        if not any(_similar(item.question, prior.question) for prior in chosen):
            chosen.append(item)
        if len(chosen) == 3:
            break
    return chosen


def compile_signature_units(units: list[SignatureResearchUnitV4] | list[SignatureCandidateV4], budget: ResearchBudgetV4) -> list[ResearchUnitV4]:
    if not units:
        raise ValueError("Signature synthesis must produce one to three units")
    if budget.signature_flexible_queries < 1:
        raise ValueError("At least one flexible query is required for a signature unit")
    if isinstance(units[0], SignatureCandidateV4):
        units = [SignatureResearchUnitV4(
            title=item.question.rstrip("？?"), scope=item.why_it_matters,
            why_generic_modules_are_insufficient=item.expected_answer,
            research_questions=[item.question], known_leads=item.research_focus,
            unresolved_points=[],
        ) for item in select_signature_candidates(units)]
    units = units[:min(3, budget.signature_flexible_queries)]
    per_unit_queries = max(1, min(3, budget.signature_flexible_queries // len(units)))
    result: list[ResearchUnitV4] = []
    for index, item in enumerate(units, start=1):
        question = item.research_questions[0]
        slug = sha1(item.title.encode("utf-8")).hexdigest()[:8]
        result.append(ResearchUnitV4(
            unit_id=f"signature-{index:02d}-{slug}", track="signature", domain="work_signature",
            question=question, why_it_matters=item.scope,
            required_outputs=[
                f"title: {item.title}", f"scope: {item.scope}",
                f"why_generic_modules_are_insufficient: {item.why_generic_modules_are_insufficient}",
                *[f"research_question: {q}" for q in item.research_questions],
                *[f"known_lead: {lead}" for lead in item.known_leads],
                *[f"unresolved_point: {point}" for point in item.unresolved_points],
            ],
            evidence_requirements=EvidenceRequirementV4(requires_primary_source=True, minimum_independent_sources=1),
            budget=UnitBudgetV4(
                max_steps=min(20, max(8, per_unit_queries * 2 + 4)),
                max_queries=per_unit_queries, max_pages=max(2, per_unit_queries * 2),
            ),
            done_when=["关键联系有检索或 dossier 支撑", "仅保留通用模块不能充分回答的增量", "未决点明确保留"],
            priority=4,
        ))
    return result
