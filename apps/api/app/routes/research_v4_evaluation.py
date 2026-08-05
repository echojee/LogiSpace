from fastapi import APIRouter

from app.services.orchestrator_v4 import get
from logispace_evaluation.run_eval_v4 import evaluate

router = APIRouter()


@router.get("/{job_id}/evaluation")
def evaluation(job_id: str):
    return evaluate(get(job_id))
