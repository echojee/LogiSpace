from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.services import research_repository_v4 as repository
from app.services.storm_artifacts_v4 import invalidate_downstream, materialize_planning_artifacts
from app.services.supervisor_v4 import compile_outline_from_units
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
    if job.storm_planning is not None:
        job.storm_planning.research_outline = compile_outline_from_units(
            kind="research", title=f"《{job.work.canonical_title}》研究增强大纲",
            units=job.plan.units,
        )
    planning_fields = {} if job.plan_memo is None else {
        "perspectives": job.plan_memo.perspectives,
        "research_turns": job.plan_memo.research_turns,
        "direct_outline": job.plan_memo.direct_outline,
        "research_outline": job.storm_planning.research_outline if job.storm_planning else job.plan_memo.research_outline,
    }
    job.plan_memo = PlanMemoV4(
        **request.model_dump(), mandatory_units=mandatory,
        **planning_fields, strategy=job.strategy, revision=revision,
    )
    job.units = {
        unit.unit_id: UnitCheckpointV4(research_unit_id=unit.unit_id, status="planned")
        for unit in job.plan.units
    }
    job.updated_at = datetime.now(timezone.utc)
    if job.storm_planning is not None:
        invalidate_downstream(job, "outline")
        materialize_planning_artifacts(job, repository.ROOT, changed_stages={"outline"})
    repository.save(job)
    return job
