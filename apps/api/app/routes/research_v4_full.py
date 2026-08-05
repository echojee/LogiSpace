from fastapi import APIRouter, BackgroundTasks, status

from app.services import orchestrator_v4, plan_memo_v4, research_repository_v4
from logispace_domain.models_v4 import PlanApprovalV4, ResearchJobCreateV4
from logispace_domain.models_v4_runtime import ResearchRuntimeV4

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
    return orchestrator_v4.get(job_id)


@router.post("/{job_id}/plan/approve", response_model=ResearchRuntimeV4)
def approve(job_id: str, request: PlanApprovalV4):
    return orchestrator_v4.approve(job_id, request)
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
