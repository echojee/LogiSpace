from types import SimpleNamespace

from app.services import orchestrator_v4, research_repository_v4, research_v4, stage_control_v4
from logispace_domain import dossiers
from logispace_domain.models_v4 import ResearchBudgetV4, ResearchJobCreateV4
from logispace_domain.models_v4_storm import StageRerunRequestV4


def _planned_job(tmp_path, monkeypatch, stub_reconnaissance):
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "research_v4")
    dossier = dossiers.get_dossier("murder-of-roger-ackroyd")
    budget = ResearchBudgetV4()
    units = [research_v4._mandatory_unit(domain, budget) for domain in orchestrator_v4.MANDATORY]
    units.extend(research_v4._signature_units(dossier, budget))
    monkeypatch.setattr(orchestrator_v4, "generate_plan", lambda **kwargs: SimpleNamespace(
        output=SimpleNamespace(units=units, rationale="recorded"),
        model="recorded", prompt_version="recorded",
    ))
    return orchestrator_v4.create(ResearchJobCreateV4(work_id=dossier.work.work_id))


def test_planning_artifacts_are_isolated_by_work_and_run(tmp_path, monkeypatch, stub_reconnaissance):
    job = _planned_job(tmp_path, monkeypatch, stub_reconnaissance)
    run_root = tmp_path / "works" / job.work.work_id / "research" / job.job_id
    assert (run_root / "perspectives/perspectives.json").exists()
    assert (run_root / "dialogues/research_turns.json").exists()
    assert (run_root / "outline/direct_outline.json").exists()
    assert (run_root / "outline/research_outline.md").exists()
    assert (run_root / "manifest.json").exists()
    assert {item.stage for item in job.stage_artifacts if item.status == "valid"} == {
        "perspective", "research_dialogue", "outline",
    }


def test_isolated_outline_rerun_preserves_upstream_and_never_searches(tmp_path, monkeypatch, stub_reconnaissance):
    job = _planned_job(tmp_path, monkeypatch, stub_reconnaissance)
    original_perspectives = job.storm_planning.perspectives
    original_turns = job.storm_planning.research_turns
    monkeypatch.setattr(orchestrator_v4, "run_search_session", lambda *_: (_ for _ in ()).throw(AssertionError("search ran")))

    rerun = stage_control_v4.rerun_outline(job.job_id, StageRerunRequestV4(
        from_stage="outline", target_stage="outline", force=True,
    ))

    assert rerun.status == "awaiting_plan_approval"
    assert rerun.storm_planning.perspectives == original_perspectives
    assert rerun.storm_planning.research_turns == original_turns
    assert any(item.stage == "outline" and item.status == "stale" for item in rerun.stage_artifacts)
    assert any(item.stage == "outline" and item.status == "valid" for item in rerun.stage_artifacts)

