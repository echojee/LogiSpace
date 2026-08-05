import pytest

from app.services.planning_protocols_v4 import compile_mandatory_units
from app.services.signature_planning_v4 import (
    SignatureCandidateV4,
    compile_signature_units,
    select_signature_candidates,
)
from logispace_domain.models_v4 import CoverageDecisionV4, ResearchBudgetV4

DOMAINS = ("relationships", "multiple_timelines", "tricks", "murder_methods")


def _candidate(question: str, *, overlap: int = 1, complexity: int = 1, specificity: int = 5):
    return SignatureCandidateV4(
        question=question,
        why_it_matters="这能解释作品独特的阅读体验。",
        research_focus=["寻找关键段落"],
        expected_answer="形成一个有原文依据的清晰解释。",
        work_specificity=specificity,
        core_explanatory_value=5,
        evidence_feasibility=5,
        user_value=5,
        mandatory_overlap=overlap,
        execution_complexity=complexity,
    )


def test_mandatory_protocols_are_deterministic_and_review_aware():
    coverage = [
        CoverageDecisionV4(
            domain=domain,
            status="needs_update",
            reason="existing",
            existing_object_ids=["existing-1"],
        )
        for domain in DOMAINS
    ]
    units = compile_mandatory_units(
        coverage=coverage,
        budget=ResearchBudgetV4(),
        strategy="review_strengthen_and_correct",
    )
    assert [unit.domain for unit in units] == list(DOMAINS)
    assert all(unit.track == "mandatory" for unit in units)
    assert all("核验、纠错和补证" in unit.why_it_matters for unit in units)
    assert all(unit.evidence_requirements.requires_primary_source for unit in units)


def test_signature_selector_deduplicates_and_does_not_force_three():
    first = _candidate("小说如何让读者逐步发现两位核心人物之间的秘密联系？")
    duplicate = _candidate("小说怎样让读者逐步看出两位核心人物之间的秘密联系？")
    weak = _candidate(
        "作品的主题有什么特点？",
        overlap=5,
        complexity=5,
        specificity=1,
    )
    selected = select_signature_candidates([duplicate, weak, first])
    assert len(selected) == 1
    assert "秘密联系" in selected[0].question


def test_signature_compiler_splits_flexible_budget_across_selected_units():
    units = compile_signature_units(
        [
            _candidate("小说如何让读者逐步发现两位核心人物之间的秘密联系？"),
            _candidate("反复出现的太阳意象如何表现人物无法公开的愿望？"),
        ],
        ResearchBudgetV4(signature_flexible_queries=8),
    )
    assert len(units) == 2
    assert sum(unit.budget.max_queries for unit in units) <= 8


@pytest.mark.parametrize("question", [
    "夜间声响应建成哪些 Event？",
    "证词应标注在字段、角色还是网络上？",
    "观察者局限、角色伪装、社会偏见与文本省略如何共同形成不可靠性？",
])
def test_internal_or_compound_questions_fail_quality_gate(question):
    with pytest.raises(ValueError, match="plain-language"):
        select_signature_candidates([_candidate(question)])