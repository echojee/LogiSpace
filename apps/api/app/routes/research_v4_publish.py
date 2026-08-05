from fastapi import APIRouter

from app.services import publication_v4
from logispace_domain.models_v4_publish import ProposalReviewV4

router = APIRouter()


@router.post("/{job_id}/review")
def review(job_id: str, request: ProposalReviewV4):
    return publication_v4.review(job_id, request)


@router.post("/{job_id}/publish")
def publish(job_id: str):
    job, delta = publication_v4.publish(job_id)
    return {"job": job, "research_delta": delta}
