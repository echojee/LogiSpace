from fastapi import APIRouter

from app.services.orchestrator_v4 import get

router = APIRouter()


@router.get("/{job_id}/evaluation")
def evaluation(job_id: str):
    # Evaluation is an optional developer package. Import it only when this
    # endpoint is used so the main API and persisted knowledge can always boot.
    from logispace_evaluation.run_eval_v4 import evaluate

    return evaluate(get(job_id))
