from fastapi import APIRouter

from app.services.pipeline import run_mock_pipeline
from logispace_domain.models import ResearchJobCreate, ResearchJobSnapshot

router = APIRouter()


@router.post("", response_model=ResearchJobSnapshot)
def create_research_job(request: ResearchJobCreate) -> ResearchJobSnapshot:
    return run_mock_pipeline(request)


@router.get("/{job_id}", response_model=ResearchJobSnapshot)
def get_research_job(job_id: str) -> ResearchJobSnapshot:
    return run_mock_pipeline(ResearchJobCreate(work_id="work_mock_001", requested_by="local-user"))
