from types import SimpleNamespace

from app.services import orchestrator_v4, plan_memo_v4, research_repository_v4, research_v4
from logispace_domain import dossiers
from logispace_domain.models_v4 import ResearchBudgetV4, ResearchJobCreateV4
from logispace_domain.models_v4_memo import PlanMemoUpdateV4


def test_plan_memo_edits_only_signature_track(tmp_path, monkeypatch, stub_reconnaissance):
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "runtime")
    dossier = dossiers.get_dossier("murder-of-roger-ackroyd")
    budget = ResearchBudgetV4()
    units = [research_v4._mandatory_unit(domain, budget) for domain in orchestrator_v4.MANDATORY]
    units.extend(research_v4._signature_units(dossier, budget))
    monkeypatch.setattr(orchestrator_v4, "generate_plan", lambda **kwargs: SimpleNamespace(
        output=SimpleNamespace(units=units, rationale="recorded"), model="recorded", prompt_version="recorded",
    ))
    job = orchestrator_v4.create(ResearchJobCreateV4(work_id=dossier.work.work_id))
    memo = job.plan_memo
    signature = memo.signature_units[0].model_copy(update={"question": "Edited work-specific question"})
    updated = plan_memo_v4.update(job.job_id, PlanMemoUpdateV4(
        title=memo.title, objective=memo.objective, scope=memo.scope,
        reconnaissance_summary=memo.reconnaissance_summary,
        signature_units=[signature], risks=memo.risks,
    ))
    assert updated.plan_memo.signature_units[0].question == "Edited work-specific question"
    assert {unit.domain for unit in updated.plan.units if unit.track == "mandatory"} == set(orchestrator_v4.MANDATORY)
    assert len([unit for unit in updated.plan.units if unit.track == "signature"]) == 1
