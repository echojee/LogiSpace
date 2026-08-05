from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import orchestrator_v4, research_repository_v4, research_v4
from logispace_domain import dossiers
from logispace_domain.models_v4 import PlanApprovalV4, ResearchBudgetV4, ResearchJobCreateV4
from logispace_domain.models_v4_memo import ReconnaissanceBriefV4
from logispace_domain.models_v4_agent import FindingBundleV4, SearchUsageV4
from app.services.reconnaissance_v4 import ReconnaissanceFormatError


@pytest.fixture
def runtime_root(tmp_path, monkeypatch):
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "research_v4")
    dossier = dossiers.get_dossier("murder-of-roger-ackroyd")
    budget = ResearchBudgetV4()
    units = [research_v4._mandatory_unit(domain, budget) for domain in ("relationships", "multiple_timelines", "tricks", "murder_methods")]
    units.extend(research_v4._signature_units(dossier, budget))
    run = SimpleNamespace(
        output=SimpleNamespace(units=units, rationale="Recorded agent plan"),
        model="recorded-supervisor", prompt_version="recorded-prompt",
    )
    monkeypatch.setattr(orchestrator_v4, "generate_plan", lambda **kwargs: run)
    return tmp_path


def test_orchestrator_persists_agent_plan_and_unit_checkpoints(runtime_root, stub_reconnaissance):
    job = orchestrator_v4.create(ResearchJobCreateV4(work_id="murder-of-roger-ackroyd"))
    assert job.status == "awaiting_plan_approval"
    assert len(job.units) == 5
    restored = research_repository_v4.load(job.job_id)
    assert restored.plan.rationale.startswith("Recorded agent plan")
    approved = orchestrator_v4.approve(job.job_id, PlanApprovalV4())
    assert approved.status == "searching"
    assert all(item.status == "approved" for item in approved.units.values())
    assert research_repository_v4.load(job.job_id).status == "searching"


def test_orchestrator_prevents_freeze_before_all_units_are_verified(runtime_root, stub_reconnaissance):
    job = orchestrator_v4.create(ResearchJobCreateV4(work_id="murder-of-roger-ackroyd"))
    orchestrator_v4.approve(job.job_id, PlanApprovalV4())
    with pytest.raises(HTTPException) as error:
        orchestrator_v4.freeze(job.job_id)
    assert error.value.status_code == 409


def test_existing_and_new_works_share_pipeline_with_distinct_strategy(runtime_root, stub_reconnaissance):
    existing = orchestrator_v4.create(ResearchJobCreateV4(work_id="murder-of-roger-ackroyd"))
    assert existing.strategy == "review_strengthen_and_correct"
    assert existing.plan.strategy == "review_strengthen_and_correct"
    assert existing.plan_memo.strategy == "review_strengthen_and_correct"


def test_planning_failure_is_persisted_and_retryable(runtime_root, monkeypatch):
    monkeypatch.setattr(
        orchestrator_v4, "run_reconnaissance",
        lambda **kwargs: (_ for _ in ()).throw(ReconnaissanceFormatError("broken JSON")),
    )
    failed = orchestrator_v4.create(ResearchJobCreateV4(work_id="murder-of-roger-ackroyd"))
    assert failed.status == "planning_failed"
    assert failed.plan is None
    assert failed.planning_failure.code == "invalid_structured_output"
    assert research_repository_v4.load(failed.job_id).planning_failure.message == "broken JSON"

    monkeypatch.setattr(orchestrator_v4, "run_reconnaissance", lambda **kwargs: ReconnaissanceBriefV4(
        summary="recovered", edition_scope="original work", candidate_features=["feature"],
    ))
    queued = orchestrator_v4.prepare_planning_retry(failed.job_id)
    assert queued.status == "created"
    recovered = orchestrator_v4.plan_job(failed.job_id)
    assert recovered.status == "awaiting_plan_approval"
    assert recovered.plan is not None
    assert recovered.planning_attempt == 2

def test_partially_completed_job_can_retry_failed_unit(runtime_root, stub_reconnaissance, monkeypatch):
    job = orchestrator_v4.create(ResearchJobCreateV4(work_id="murder-of-roger-ackroyd"))
    job = orchestrator_v4.approve(job.job_id, PlanApprovalV4())
    unit_id = next(iter(job.units))
    job.status = "partially_completed"
    job.units[unit_id].status = "failed"
    research_repository_v4.save(job)
    monkeypatch.setattr(orchestrator_v4, "run_search_agent", lambda **kwargs: FindingBundleV4(
        research_unit_id=unit_id, summary="no evidence", stop_reason="no_novelty",
        usage=SearchUsageV4(), actions=[],
    ))
    retried = orchestrator_v4.run_unit(job.job_id, unit_id)
    assert retried.units[unit_id].attempt == 1
    assert retried.units[unit_id].status == "failed"