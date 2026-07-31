from fastapi import APIRouter

from app.services.research_v2 import create_job, get_job, list_jobs, publish_job, review_job
from logispace_domain.models import ProposalReview, ResearchJobV2, ResearchJobV2Create

router = APIRouter()


@router.post("", response_model=ResearchJobV2)
def create(request: ResearchJobV2Create) -> ResearchJobV2:
    return create_job(request)


@router.get("", response_model=list[ResearchJobV2])
def list_items() -> list[ResearchJobV2]:
    return list_jobs()


@router.get("/{job_id}", response_model=ResearchJobV2)
def get_item(job_id: str) -> ResearchJobV2:
    return get_job(job_id)


@router.post("/{job_id}/review", response_model=ResearchJobV2)
def review(job_id: str, request: ProposalReview) -> ResearchJobV2:
    return review_job(job_id, request)


@router.post("/{job_id}/publish", response_model=ResearchJobV2)
def publish(job_id: str) -> ResearchJobV2:
    return publish_job(job_id)
