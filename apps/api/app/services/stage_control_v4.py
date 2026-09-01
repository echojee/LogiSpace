from __future__ import annotations

from fastapi import HTTPException

from app.services import research_repository_v4 as repository
from app.services.storm_artifacts_v4 import invalidate_downstream, materialize_planning_artifacts
from app.services.supervisor_v4 import compile_outline_from_units
from logispace_domain.models_v4_runtime import ResearchRuntimeV4
from logispace_domain.models_v4_storm import StageRerunRequestV4, StageStatusV4

STAGES = ("perspective", "research_dialogue", "outline", "search_and_draft", "polish", "deposit")


def statuses(job: ResearchRuntimeV4) -> list[StageStatusV4]:
    current = {item.stage: item for item in job.stage_artifacts if item.status == "valid"}
    result = []
    for stage in STAGES:
        artifact = current.get(stage)
        status = "valid" if artifact else "pending"
        if stage == "outline" and job.status == "awaiting_plan_approval":
            status = "awaiting_approval"
        elif stage == "search_and_draft" and job.status == "researching":
            status = "running"
        elif stage == "search_and_draft" and job.research_report is not None:
            status = "valid"
        result.append(StageStatusV4(
            stage=stage, status=status,
            current_artifact_id=artifact.artifact_id if artifact else None,
        ))
    return result


def rerun_outline(job_id: str, request: StageRerunRequestV4) -> ResearchRuntimeV4:
    job = repository.load(job_id)
    if job is None:
        raise HTTPException(404, "Research job not found")
    if request.target_stage != "outline" or request.from_stage != "outline":
        raise HTTPException(422, "This endpoint currently accepts an isolated outline-to-outline rerun")
    if job.status != "awaiting_plan_approval" or job.plan is None or job.storm_planning is None:
        raise HTTPException(409, "Outline can only be regenerated before approval")
    previous = job.storm_planning.research_outline
    regenerated = compile_outline_from_units(
        kind="research", title=f"《{job.work.canonical_title}》研究增强大纲",
        units=job.plan.units,
    )
    if not request.force and regenerated.model_dump() == previous.model_dump():
        return job
    job.storm_planning.research_outline = regenerated
    if job.plan_memo is not None:
        job.plan_memo.research_outline = regenerated
        job.plan_memo.revision += 1
    invalidate_downstream(job, "outline")
    materialize_planning_artifacts(job, repository.ROOT, changed_stages={"outline"})
    repository.save(job)
    return job
