from fastapi import APIRouter, status

from app.services import research_v4_agent as service
from logispace_domain.models_v4 import (
    PlanApprovalV4,
    ResearchJobCreateV4,
    ResearchJobV4,
    ResearchPlanRevisionV4,
)

router = APIRouter()


@router.post("", response_model=ResearchJobV4, status_code=status.HTTP_202_ACCEPTED)
def create(request: ResearchJobCreateV4):
    return service.create(request)


@router.get("/{job_id}", response_model=ResearchJobV4)
def get(job_id: str):
    return service.get(job_id)


@router.get("/{job_id}/plan", response_model=ResearchPlanRevisionV4)
def plan(job_id: str):
    return service.get(job_id).plan


@router.post("/{job_id}/plan/approve", response_model=ResearchJobV4)
def approve(job_id: str, request: PlanApprovalV4):
    return service.approve(job_id, request)
