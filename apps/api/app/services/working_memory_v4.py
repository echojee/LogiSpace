from __future__ import annotations

from uuid import uuid4

from app.services import research_repository_v4 as repository
from logispace_domain.models_v4_runtime import ExecutionCheckpointV1, ResearchRuntimeV4


def record(
    job: ResearchRuntimeV4,
    *,
    stage: str,
    status: str,
    unit_id: str | None = None,
    attempt: int = 1,
    error: str | None = None,
) -> ExecutionCheckpointV1:
    """Append an auditable stage transition without duplicating runtime state."""
    operation_key = f"{job.job_id}:{unit_id or 'job'}:{stage}:{attempt}"
    checkpoint = ExecutionCheckpointV1(
        checkpoint_id=f"cp_{uuid4().hex[:12]}",
        job_id=job.job_id,
        stage=stage,
        unit_id=unit_id,
        status=status,
        attempt=attempt,
        state_version=job.state_version,
        operation_key=operation_key,
        error=error,
    )
    repository.append_checkpoint(checkpoint)
    return checkpoint


def checkpoints(job_id: str) -> list[ExecutionCheckpointV1]:
    """Return the append-only execution history for a research job."""
    return repository.list_checkpoints(job_id)
