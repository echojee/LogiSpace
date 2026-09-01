from types import SimpleNamespace
import json

import pytest

from app.services import supervisor_v4
from app.services.llm import JSONResponseError, LLMResult
from logispace_domain import dossiers
from logispace_domain.models_v4 import CoverageDecisionV4, ResearchBriefV4, ResearchBudgetV4

MANDATORY = ("relationships", "multiple_timelines", "tricks", "murder_methods")


class RecordedSupervisorLLM:
    available = True
    research_model = "recorded-supervisor-model"

    def __init__(self):
        self.calls = []
        self.invalid_question = False

    def respond_json(self, *, instructions, input_text, research, **kwargs):
        payload = json.loads(input_text)
        kwargs["research"] = research
        self.calls.append((payload, kwargs))
        usage = SimpleNamespace(input_tokens=100, output_tokens=50)
        if "round" not in payload and "perspectives" not in payload:
            question = "夜间声响应该建成哪些 Event 和 Entity？" if self.invalid_question else "小说如何逐步隐藏叙述者实施的关键行动？"
            return {"perspectives": [{
                "title": "叙述空白",
                "starting_question": question,
                "dossier_leads": ["叙述视角发生切换"],
                "why_potentially_distinctive": "作品通过可见信息的边界隐藏行动。",
                "information_gain": 5,
                "evidence_feasibility": 5,
                "generic_modules_sufficient": False,
            }]}, usage
        if "round" in payload:
            perspective = payload["active_perspectives"][0]
            title = perspective["title"]
            round_number = payload["round"]
            is_signature = title == "叙述空白"
            return {"notes": [{
                "perspective_title": title, "round": round_number,
                "question": "哪些段落省略了关键行动？",
                "answer_note": "需要对照叙述段落和真实行动顺序。",
                "research_intent": "定位叙事省略与真实行动之间的对应关系。",
                "suggested_queries": ["罗杰疑案 叙述省略 章节"],
                "source_urls": ["https://example.com/recon-source"],
                "leads": ["检查章节切换"], "unresolved": ["精确句界"],
                "continue_research": is_signature and round_number == 1,
                "expected_information_gain": 4 if is_signature else 2,
            }]}, usage
        return {"units": [{
            "title": "叙述空白与行动隐藏",
            "scope": "对照叙述视角、章节切换和关键行动。",
            "why_generic_modules_are_insufficient": "需要综合考察读者能够看到的信息边界。",
            "research_questions": ["小说如何逐步隐藏叙述者实施的关键行动？"],
            "known_leads": ["章节切换可能遮蔽行动"],
            "unresolved_points": ["需要原文确认精确句界"],
        }]}, usage


def _inputs():
    dossier = dossiers.get_dossier("murder-of-roger-ackroyd")
    coverage = [CoverageDecisionV4(domain=domain, status="needs_update", reason="existing") for domain in MANDATORY]
    return dossier, coverage


def test_supervisor_compiles_mandatory_protocols_and_researched_signatures():
    dossier, coverage = _inputs()
    llm = RecordedSupervisorLLM()
    run = supervisor_v4.generate_plan(
        brief=ResearchBriefV4(work_id=dossier.work.work_id, user_goal="研究不可靠叙述"),
        dossier=dossier, coverage=coverage, budget=ResearchBudgetV4(), llm=llm,
    )
    first_payload, first_kwargs = llm.calls[0]
    assert first_payload["brief"]["user_goal"] == "研究不可靠叙述"
    assert len(first_payload["generic_modules"]) == 4
    assert first_kwargs["response_schema"]["additionalProperties"] is False
    mandatory = [unit for unit in run.output.units if unit.track == "mandatory"]
    signature = [unit for unit in run.output.units if unit.track == "signature"]
    assert {unit.domain for unit in mandatory} == set(MANDATORY)
    assert len(signature) == 1
    assert signature[0].question == "小说如何逐步隐藏叙述者实施的关键行动？"
    assert len(llm.calls) == 5
    round_calls = [(payload, kwargs) for payload, kwargs in llm.calls if "round" in payload]
    assert all(kwargs["web_search"] is True and kwargs["max_tool_calls"] == 1 for _, kwargs in round_calls)
    boundary_calls = [payload for payload, _ in round_calls if payload["active_perspectives"][0]["title"] == "基础事实与版本边界"]
    dynamic_calls = [payload for payload, _ in round_calls if payload["active_perspectives"][0]["title"] != "基础事实与版本边界"]
    assert len(boundary_calls) == 1
    assert len(dynamic_calls) == 2
    assert all(kwargs["research"] is False and kwargs["model"] == "recorded-supervisor-model" for _, kwargs in llm.calls)
    assert run.model == "recorded-supervisor-model"
    assert len(run.storm_planning.perspectives) == 2
    assert len(run.storm_planning.research_turns) == 3
    assert run.storm_planning.direct_outline.kind == "direct"
    assert run.storm_planning.research_outline.kind == "research"
    assert run.storm_planning.research_turns[0].provisional_answer.startswith("待验证假设：")


def test_supervisor_falls_back_when_dynamic_perspective_fails_quality_gate():
    dossier, coverage = _inputs()
    llm = RecordedSupervisorLLM()
    llm.invalid_question = True
    run = supervisor_v4.generate_plan(
        brief=ResearchBriefV4(work_id=dossier.work.work_id), dossier=dossier,
        coverage=coverage, budget=ResearchBudgetV4(), llm=llm,
    )
    assert len([unit for unit in run.output.units if unit.track == "mandatory"]) == 4
    assert len([unit for unit in run.output.units if unit.track == "signature"]) >= 1
    assert "备用视角" in run.output.rationale


def test_supervisor_requires_configured_model():
    dossier, coverage = _inputs()
    llm = RecordedSupervisorLLM()
    llm.available = False
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        supervisor_v4.generate_plan(
            brief=ResearchBriefV4(work_id=dossier.work.work_id), dossier=dossier,
            coverage=coverage, budget=ResearchBudgetV4(), llm=llm,
        )


def test_structured_planning_retries_once_with_more_output_room():
    class TruncatedOnceLLM:
        research_model = "test-model"

        def __init__(self):
            self.output_limits = []

        def respond_json(self, **kwargs):
            self.output_limits.append(kwargs["max_output_tokens"])
            if len(self.output_limits) == 1:
                result = LLMResult(text='{"perspectives":[{"title":"未闭合')
                raise JSONResponseError("unterminated", result.text, result)
            return {"perspectives": [{
                "title": "叙述空白",
                "starting_question": "作品如何隐藏关键行动？",
                "dossier_leads": ["章节切换"],
                "why_potentially_distinctive": "叙述边界遮蔽行动。",
                "information_gain": 5,
                "evidence_feasibility": 5,
                "generic_modules_sufficient": False,
            }]}, LLMResult(text="{}")

    llm = TruncatedOnceLLM()
    output, _ = supervisor_v4._call_json(
        llm, instructions="test", payload={},
        schema=supervisor_v4.PerspectiveDiscoveryOutput,
        max_output_tokens=800,
    )

    assert output.perspectives[0].title == "叙述空白"
    assert llm.output_limits == [800, 1600]
