from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from fastapi import HTTPException

from app.services import research_v4 as baseline
from app.services.supervisor_v4 import generate_plan
from logispace_domain import dossiers
from logispace_domain.models_v4 import (
    PlanApprovalV4,
    ResearchBriefV4,
    ResearchJobCreateV4,
    ResearchJobV4,
    ResearchPlanRevisionV4,
)

_JOBS: dict[str, ResearchJobV4] = {}
_LOCK = RLock()
_MANDATORY = ("relationships", "multiple_timelines", "tricks", "murder_methods")


def create(request: ResearchJobCreateV4) -> ResearchJobV4:
    dossier = dossiers.get_dossier(request.work_id)
    if dossier is None:
        raise HTTPException(404, "Work not found")
    brief = request.brief or ResearchBriefV4(work_id=request.work_id)
    if brief.work_id != request.work_id:
        raise HTTPException(422, "brief.work_id must match work_id")
    coverage = [baseline._coverage(dossier, domain) for domain in _MANDATORY]
    job = ResearchJobV4(
        job_id=f"research_v4_{uuid4().hex[:12]}",
        work=dossier.work,
        status="supervisor_planning",
        brief=brief,
    )
    try:
        run = generate_plan(
            brief=brief,
            dossier=dossier,
            coverage=coverage,
            budget=request.budget,
        )
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    job.plan = ResearchPlanRevisionV4(
        coverage=coverage,
        units=run.output.units,
        budget=request.budget,
        rationale=(
            f"{run.output.rationale} "
            f"[model={run.model}; prompt={run.prompt_version}; "
            f"tokens={run.input_tokens + run.output_tokens}]"
        ),
    )
    job.status = "awaiting_plan_approval"
    with _LOCK:
        _JOBS[job.job_id] = job
    return job


def get(job_id: str) -> ResearchJobV4:
    with _LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Research job not found")
    return job


def approve(job_id: str, request: PlanApprovalV4) -> ResearchJobV4:
    job = get(job_id)
    if job.status != "awaiting_plan_approval" or job.plan is None:
        raise HTTPException(409, "Plan is not awaiting approval")
    units = request.units if request.units is not None else job.plan.units
    try:
        revised = ResearchPlanRevisionV4.model_validate(
            job.plan.model_copy(update={"units": units}, deep=True).model_dump()
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    revised.approved = True
    for unit in revised.units:
        unit.status = "approved"
    job.plan = revised
    job.status = "searching"
    job.updated_at = datetime.now(timezone.utc)
    with _LOCK:
        _JOBS[job.job_id] = job
    return job
