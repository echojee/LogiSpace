from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from urllib.parse import quote

from app.services import deep_research_mvp, orchestrator_v4, plan_memo_v4, research_repository_v4, stage_control_v4
from logispace_domain.models_v4 import PlanApprovalV4, ResearchJobCreateV4
from logispace_domain.models_v4_runtime import ResearchRuntimeV4
from logispace_domain.models_v4_storm import StageArtifactV4, StageRerunRequestV4, StageStatusV4

from logispace_domain.models_v4_memo import PlanMemoUpdateV4
router = APIRouter()


@router.post("", response_model=ResearchRuntimeV4, status_code=status.HTTP_202_ACCEPTED)
def create(request: ResearchJobCreateV4, background_tasks: BackgroundTasks):
    job = orchestrator_v4.start(request)
    response = job.model_copy(deep=True)
    background_tasks.add_task(orchestrator_v4.plan_job, job.job_id)
    return response


@router.get("", response_model=list[ResearchRuntimeV4])
def list_jobs():
    return research_repository_v4.list_jobs()


@router.get("/{job_id}", response_model=ResearchRuntimeV4)
def get(job_id: str):
    return deep_research_mvp.get(job_id)


@router.get("/{job_id}/checkpoints")
def checkpoints(job_id: str):
    orchestrator_v4.get(job_id)
    return research_repository_v4.list_checkpoints(job_id)


@router.get("/{job_id}/report.md")
def download_current_report(job_id: str):
    job = deep_research_mvp.get(job_id)
    if job.research_report is None:
        raise HTTPException(404, "Research report not found")
    safe_title = "".join(character for character in job.work.canonical_title if character not in '\\/:*?"<>|').strip()
    filename = f"{safe_title or job.job_id}-{job.job_id}.md"
    return Response(
        content=job.research_report.markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/{job_id}/artifacts", response_model=list[StageArtifactV4])
def artifacts(job_id: str):
    return orchestrator_v4.get(job_id).stage_artifacts


@router.get("/{job_id}/stages", response_model=list[StageStatusV4])
def stages(job_id: str):
    return stage_control_v4.statuses(orchestrator_v4.get(job_id))


@router.post("/{job_id}/rerun", response_model=ResearchRuntimeV4)
def rerun(job_id: str, request: StageRerunRequestV4):
    return stage_control_v4.rerun_outline(job_id, request)


@router.post("/{job_id}/resume", response_model=ResearchRuntimeV4)
def resume(job_id: str, background_tasks: BackgroundTasks):
    job = orchestrator_v4.get(job_id)
    if job.plan is None or not job.plan.approved:
        raise HTTPException(409, "Only an approved research dossier can be resumed")
    deep_research_mvp.schedule_run(background_tasks, job.job_id)
    return job


@router.post("/{job_id}/plan/approve", response_model=ResearchRuntimeV4)
def approve(job_id: str, request: PlanApprovalV4, background_tasks: BackgroundTasks):
    job = orchestrator_v4.approve(job_id, request)
    response = job.model_copy(deep=True)
    deep_research_mvp.schedule_run(background_tasks, job.job_id)
    return response


@router.post("/{job_id}/report/memory/{decision}", response_model=ResearchRuntimeV4)
def review_report_memory(job_id: str, decision: str):
    return deep_research_mvp.review_report_memory(job_id, decision)


@router.post("/{job_id}/report/knowledge/rebuild", response_model=ResearchRuntimeV4)
def rebuild_report_memory(job_id: str):
    return deep_research_mvp.rebuild_report_memory(job_id)
@router.post("/{job_id}/plan/retry", response_model=ResearchRuntimeV4, status_code=status.HTTP_202_ACCEPTED)
def retry_plan(job_id: str, background_tasks: BackgroundTasks):
    job = orchestrator_v4.prepare_planning_retry(job_id)
    response = job.model_copy(deep=True)
    background_tasks.add_task(orchestrator_v4.plan_job, job.job_id)
    return response

@router.patch("/{job_id}/plan/memo", response_model=ResearchRuntimeV4)
def update_memo(job_id: str, request: PlanMemoUpdateV4):
    return plan_memo_v4.update(job_id, request)




@router.post("/{job_id}/search/run", response_model=ResearchRuntimeV4)
def run_search_session(job_id: str):
    return orchestrator_v4.run_search_session(job_id)


@router.post("/{job_id}/units/{unit_id}/search", response_model=ResearchRuntimeV4)
def search_unit(job_id: str, unit_id: str):
    return orchestrator_v4.run_unit(job_id, unit_id)


@router.post("/{job_id}/units/{unit_id}/curate", response_model=ResearchRuntimeV4)
def curate_unit(job_id: str, unit_id: str):
    return orchestrator_v4.curate_unit(job_id, unit_id)


@router.post("/{job_id}/units/{unit_id}/verify", response_model=ResearchRuntimeV4)
def verify_unit(job_id: str, unit_id: str):
    return orchestrator_v4.verify_unit(job_id, unit_id)


@router.post("/{job_id}/freeze", response_model=ResearchRuntimeV4)
def freeze(job_id: str):
    return orchestrator_v4.freeze(job_id)


@router.post("/{job_id}/project", response_model=ResearchRuntimeV4)
def project(job_id: str):
    return orchestrator_v4.project(job_id)
