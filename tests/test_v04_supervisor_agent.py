from types import SimpleNamespace

import pytest

from app.services import supervisor_v4
from logispace_domain import dossiers
from logispace_domain.models_v4 import CoverageDecisionV4, ResearchBriefV4, ResearchBudgetV4

MANDATORY = ("relationships", "multiple_timelines", "tricks", "murder_methods")


class RecordedSupervisorLLM:
    available = True
    research_model = "recorded-supervisor-model"

    def __init__(self):
        self.payload = None
        self.kwargs = None

    def respond_json(self, *, instructions, input_text, research, **kwargs):
        import json

        self.payload = json.loads(input_text)
        self.kwargs = kwargs
        candidate = {
            "question": "小说如何让读者逐步发现叙述者隐瞒的关键行动？",
            "why_it_matters": "这能解释作品最独特的信息控制方式。",
            "research_focus": ["定位叙述空白", "对照行动与叙述"],
            "expected_answer": "说明信息隐瞒如何成立并影响读者判断。",
            "work_specificity": 5,
            "core_explanatory_value": 5,
            "evidence_feasibility": 5,
            "user_value": 5,
            "mandatory_overlap": 1,
            "execution_complexity": 2,
        }
        return {"rationale": "聚焦作品独特的叙述方式。", "candidates": [candidate]}, SimpleNamespace(
            input_tokens=100, output_tokens=50,
        )


def _inputs():
    dossier = dossiers.get_dossier("murder-of-roger-ackroyd")
    coverage = [
        CoverageDecisionV4(domain=domain, status="needs_update", reason="existing")
        for domain in MANDATORY
    ]
    return dossier, coverage


def test_supervisor_compiles_mandatory_protocols_and_only_asks_agent_for_signatures():
    dossier, coverage = _inputs()
    llm = RecordedSupervisorLLM()
    run = supervisor_v4.generate_plan(
        brief=ResearchBriefV4(work_id=dossier.work.work_id, user_goal="研究不可靠叙述"),
        dossier=dossier,
        coverage=coverage,
        budget=ResearchBudgetV4(),
        llm=llm,
    )
    assert llm.payload["brief"]["user_goal"] == "研究不可靠叙述"
    assert llm.payload["strategy"] == "build_and_verify"
    assert llm.payload["current_dossier_summary"]["entity_type_counts"]
    assert len(llm.payload["mandatory_questions_already_covered"]) == 4
    assert "research_unit_schema" not in llm.payload
    assert llm.kwargs["response_schema"]["additionalProperties"] is False
    mandatory = [unit for unit in run.output.units if unit.track == "mandatory"]
    signature = [unit for unit in run.output.units if unit.track == "signature"]
    assert {unit.domain for unit in mandatory} == set(MANDATORY)
    assert len(signature) == 1
    assert signature[0].question == "小说如何让读者逐步发现叙述者隐瞒的关键行动？"
    assert run.model == "recorded-supervisor-model"


def test_supervisor_rejects_candidate_that_uses_internal_schema_language():
    dossier, coverage = _inputs()
    llm = RecordedSupervisorLLM()
    original = llm.respond_json

    def invalid(**kwargs):
        data, usage = original(**kwargs)
        data["candidates"][0]["question"] = "夜间声响应该建成哪些 Event 和 Entity？"
        return data, usage

    llm.respond_json = invalid
    with pytest.raises(RuntimeError, match="plain-language"):
        supervisor_v4.generate_plan(
            brief=ResearchBriefV4(work_id=dossier.work.work_id),
            dossier=dossier,
            coverage=coverage,
            budget=ResearchBudgetV4(),
            llm=llm,
        )


def test_supervisor_requires_configured_model():
    dossier, coverage = _inputs()
    llm = RecordedSupervisorLLM()
    llm.available = False
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        supervisor_v4.generate_plan(
            brief=ResearchBriefV4(work_id=dossier.work.work_id),
            dossier=dossier,
            coverage=coverage,
            budget=ResearchBudgetV4(),
            llm=llm,
        )