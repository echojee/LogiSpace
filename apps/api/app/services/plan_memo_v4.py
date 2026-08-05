from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.services import research_repository_v4 as repository
from logispace_domain.models_v4 import ResearchPlanRevisionV4
from logispace_domain.models_v4_memo import PlanMemoUpdateV4, PlanMemoV4
from logispace_domain.models_v4_runtime import ResearchRuntimeV4, UnitCheckpointV4


def update(job_id: str, request: PlanMemoUpdateV4) -> ResearchRuntimeV4:
    job = repository.load(job_id)
    if job is None:
        raise HTTPException(404, "Research job not found")
    if job.status != "awaiting_plan_approval" or job.plan is None:
        raise HTTPException(409, "Plan memo can only be edited before approval")
    signatures = [
        unit.model_copy(update={"track": "signature", "status": "planned"})
        for unit in request.signature_units
    ]
    mandatory = [unit for unit in job.plan.units if unit.track == "mandatory"]
    try:
        job.plan = ResearchPlanRevisionV4.model_validate(job.plan.model_copy(update={
            "revision": job.plan.revision + 1,
            "units": [*mandatory, *signatures],
            "approved": False,
        }).model_dump())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    revision = job.plan_memo.revision + 1 if job.plan_memo else 1
    job.plan_memo = PlanMemoV4(**request.model_dump(), strategy=job.strategy, revision=revision)
    job.units = {
        unit.unit_id: UnitCheckpointV4(research_unit_id=unit.unit_id, status="planned")
        for unit in job.plan.units
    }
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    return job
