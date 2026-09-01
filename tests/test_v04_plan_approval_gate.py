from fastapi import BackgroundTasks, HTTPException

from app.routes import research_v4_full
from app.services import orchestrator_v4, research_repository_v4
from logispace_domain.models import Work
from logispace_domain.models_v4 import ResearchBriefV4, ResearchJobCreateV4


def _request():
    work = Work(
        work_id="approval-gate-work",
        canonical_title="审批闸门测试作品",
        media_type="novel",
        creators=["Test Author"],
    )
    return ResearchJobCreateV4(
        work=work,
        brief=ResearchBriefV4(work_id=work.work_id),
    )


def test_create_schedules_planning_and_never_search(tmp_path, monkeypatch):
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "runtime")
    scheduled = []
    background = BackgroundTasks()
    monkeypatch.setattr(background, "add_task", lambda func, *args, **kwargs: scheduled.append((func, args, kwargs)))

    job = research_v4_full.create(_request(), background)

    assert job.status == "created"
    assert len(scheduled) == 1
    assert scheduled[0][0] is orchestrator_v4.plan_job
    try:
        orchestrator_v4.run_search_session(job.job_id)
    except HTTPException as error:
        assert error.status_code == 409
    else:
        raise AssertionError("search must stay locked until the outline is approved")

