from types import SimpleNamespace

import pytest

from app.services import orchestrator_v4, research_repository_v4, research_v4
from logispace_domain.models import Work
from logispace_domain.models_v4 import ResearchBudgetV4, ResearchJobCreateV4


def test_new_resolved_work_gets_zero_baseline_and_agent_plan(tmp_path, monkeypatch, stub_reconnaissance):
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "runtime")
    budget = ResearchBudgetV4()
    placeholder = Work(work_id="and-then-there-were-none-novel-new", canonical_title="无人生还", aliases=["And Then There Were None"], media_type="novel")
    units = [research_v4._mandatory_unit(domain, budget) for domain in ("relationships", "multiple_timelines", "tricks", "murder_methods")]
    units.append(research_v4._signature_units(
        research_v4.baseline(placeholder) if hasattr(research_v4, "baseline") else SimpleNamespace(work=placeholder, entities=[]),
        budget,
    )[0])
    captured = {}

    def fake_generate_plan(**kwargs):
        captured["dossier"] = kwargs["dossier"]
        return SimpleNamespace(
            output=SimpleNamespace(units=units, rationale="Agent planned a new work"),
            model="recorded", prompt_version="recorded",
        )

    monkeypatch.setattr(orchestrator_v4, "generate_plan", fake_generate_plan)
    job = orchestrator_v4.create(ResearchJobCreateV4(work=placeholder))
    assert captured["dossier"].dossier_version == "0.0.0"
    assert captured["dossier"].entities == []
    assert job.work.work_id == placeholder.work_id
    assert job.status == "awaiting_plan_approval"
    assert len(job.plan.units) == 5


def test_v04_create_requires_exactly_one_identity():
    with pytest.raises(Exception) as error:
        orchestrator_v4.create(ResearchJobCreateV4())
    assert getattr(error.value, "status_code", None) == 422
