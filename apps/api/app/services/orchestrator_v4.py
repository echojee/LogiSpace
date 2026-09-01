from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.services import research_repository_v4 as repository
from app.services.curator_v4 import curate
from app.services.projection_v4 import cross_projection_audit, map_knowledge_proposals, write_case_file
from app.services.reconnaissance_v4 import ReconnaissanceFormatError, run_reconnaissance
from app.services.reader_v4 import FrozenPage
from app.services.search_agent_v4 import SearchToolboxV4, SearchWorkspace, run_search_agent
from app.services.source_routing_v4 import build_funnel
from app.services.supervisor_v4 import compile_planning_state_from_units, generate_plan
from app.services.storm_artifacts_v4 import materialize_planning_artifacts
from app.services.verified_knowledge_v4 import completion_check, freeze_verified_knowledge
from app.services.verifier_v4 import verify_batch
from app.services.working_memory_v4 import record as record_checkpoint
from app.services import knowledge_memory_v4
from app.services import user_memory
from logispace_domain import dossiers
from logispace_domain.models import WorkDossier
from logispace_domain.models_v4 import PlanApprovalV4, ResearchBriefV4, ResearchJobCreateV4, ResearchPlanRevisionV4, ResearchStrategyV4
from logispace_domain.models_v4_agent import SourceCandidateV4
from logispace_domain.models_v4_memo import PerspectiveSetV4, PlanMemoUpdateV4, PlanMemoV4
from logispace_domain.models_v4_runtime import PlanningFailureV4, ResearchRuntimeV4, UnitCheckpointV4

MANDATORY = ("relationships", "multiple_timelines", "tricks", "murder_methods")


class CapturingToolbox(SearchToolboxV4):
    def __init__(self, cached: dict[str, FrozenPage] | None = None):
        self.snapshots: dict[str, str] = {}
        self.cached = cached or {}

    def fetch_page(self, url: str) -> FrozenPage:
        cached = next((item for item in self.cached.values() if item.url == url), None)
        if cached is not None:
            self.snapshots[cached.snapshot_id] = cached.text
            return cached
        page = super().fetch_page(url)
        self.snapshots[page.snapshot_id] = page.text
        return page


def _coverage(dossier, domain, knowledge=None):
    types = {
        "multiple_timelines": {"Event", "Reveal", "NarrativeUnit"},
        "tricks": {"Trick"}, "murder_methods": {"MurderMethod"},
    }
    if knowledge is not None:
        object_type = "relationship" if domain == "relationships" else "timeline_alignment" if domain == "multiple_timelines" else domain[:-1] if domain.endswith("s") else domain
        ids = [item.object_id for item in knowledge.verified_knowledge.domain_objects if item.object_type == object_type]
        ids.extend(item.claim_id for item in knowledge.verified_knowledge.claims if item.domain == domain)
    elif domain == "relationships":
        ids = [f"{item.source_id}:{item.relation}:{item.target_id}" for item in dossier.relations]
    else:
        ids = [item.entity_id for item in dossier.entities if item.entity_type in types[domain]]
    from logispace_domain.models_v4 import CoverageDecisionV4
    return CoverageDecisionV4(
        domain=domain, status="needs_update" if ids else "missing",
        reason="Existing structure requires 0.4 evidence review." if ids else "No existing structured objects.",
        existing_object_ids=ids,
    )


def get(job_id: str) -> ResearchRuntimeV4:
    job = repository.load(job_id)
    if job is None:
        raise HTTPException(404, "Research job not found")
    return job


def _baseline_dossier(work) -> WorkDossier:
    return WorkDossier(
        work=work, dossier_version="0.0.0", entities=[], relations=[],
        golden_questions=[], revision_findings=["New 0.4 research baseline."],
    )


def _resolve_request(request: ResearchJobCreateV4) -> tuple[WorkDossier, ResearchStrategyV4]:
    if bool(request.work_id) == bool(request.work):
        raise HTTPException(422, "Provide exactly one of work_id or work")
    if request.work_id:
        dossier = dossiers.get_dossier(request.work_id)
        if dossier is None:
            raise HTTPException(404, "Work not found")
        return dossier, "review_strengthen_and_correct"
    if request.work is None:
        raise HTTPException(422, "Resolved work identity is required")
    return _baseline_dossier(request.work), "build_and_verify"


def _planning_dossier(job: ResearchRuntimeV4) -> WorkDossier:
    if job.strategy == "review_strengthen_and_correct":
        dossier = dossiers.get_dossier(job.work.work_id)
        if dossier is None:
            raise RuntimeError("Existing WorkDossier is no longer available")
        return dossier
    return _baseline_dossier(job.work)


def start(request: ResearchJobCreateV4) -> ResearchRuntimeV4:
    dossier, strategy = _resolve_request(request)
    preferences = user_memory.get()
    brief = request.brief or ResearchBriefV4(
        work_id=dossier.work.work_id,
        media_version=preferences.preferred_media_version,
        spoiler_level=preferences.spoiler_level,
        budget_profile=preferences.research_depth,
    )
    if brief.work_id != dossier.work.work_id:
        raise HTTPException(422, "brief.work_id must match the resolved work")
    job = ResearchRuntimeV4(
        job_id=f"research_v4_{uuid4().hex[:12]}", work=dossier.work, brief=brief,
        status="created", strategy=strategy, planning_budget=request.budget,
    )
    repository.save(job)
    return job


def _planning_failed(job: ResearchRuntimeV4, *, stage: str, code: str, error: Exception) -> ResearchRuntimeV4:
    job.status = "planning_failed"
    job.planning_failure = PlanningFailureV4(
        stage=stage, code=code, message=str(error), attempt=job.planning_attempt,
    )
    message = f"{stage}: {error}"
    if message not in job.errors:
        job.errors.append(message)
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    record_checkpoint(job, stage="planning", status="failed", attempt=job.planning_attempt, error=str(error))
    return job


def plan_job(job_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.status not in {"created", "planning_failed", "reconnaissance_running", "supervisor_planning"}:
        raise HTTPException(409, "Research job is not eligible for planning")
    dossier = _planning_dossier(job)
    existing_memory = knowledge_memory_v4.get_current(job.work.work_id, job.brief.media_version)
    coverage = [_coverage(dossier, domain, existing_memory) for domain in MANDATORY]
    job.planning_attempt += 1
    job.planning_failure = None
    job.status = "reconnaissance_running"
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    record_checkpoint(job, stage="planning", status="started", attempt=job.planning_attempt)
    reconnaissance = job.reconnaissance
    if reconnaissance is None:
        record_checkpoint(job, stage="reconnaissance", status="started", attempt=job.planning_attempt)
        try:
            reconnaissance = run_reconnaissance(brief=job.brief, dossier=dossier)
        except ReconnaissanceFormatError as error:
            record_checkpoint(job, stage="reconnaissance", status="failed", attempt=job.planning_attempt, error=str(error))
            return _planning_failed(job, stage="reconnaissance", code="invalid_structured_output", error=error)
        except RuntimeError as error:
            record_checkpoint(job, stage="reconnaissance", status="failed", attempt=job.planning_attempt, error=str(error))
            return _planning_failed(job, stage="reconnaissance", code="reconnaissance_failed", error=error)
        job.reconnaissance = reconnaissance
        repository.save(job)
        record_checkpoint(job, stage="reconnaissance", status="completed", attempt=job.planning_attempt)
    job.status = "supervisor_planning"
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    record_checkpoint(job, stage="perspectives", status="started", attempt=job.planning_attempt)
    record_checkpoint(job, stage="plan_synthesis", status="started", attempt=job.planning_attempt)
    try:
        run = generate_plan(
            brief=job.brief, dossier=dossier, coverage=coverage,
            budget=job.planning_budget, reconnaissance=reconnaissance,
            strategy=job.strategy,
        )
    except RuntimeError as error:
        record_checkpoint(job, stage="perspectives", status="failed", attempt=job.planning_attempt, error=str(error))
        record_checkpoint(job, stage="plan_synthesis", status="failed", attempt=job.planning_attempt, error=str(error))
        return _planning_failed(job, stage="supervisor", code="supervisor_failed", error=error)

    plan = ResearchPlanRevisionV4(
        coverage=coverage, units=run.output.units, budget=job.planning_budget,
        rationale=f"{run.output.rationale} [model={run.model}; prompt={run.prompt_version}]",
        strategy=job.strategy,
    )
    job.plan = plan
    job.storm_planning = getattr(run, "storm_planning", None) or compile_planning_state_from_units(
        title=job.work.canonical_title, units=run.output.units,
        model=run.model, prompt_version=run.prompt_version,
    )
    job.perspective_set = PerspectiveSetV4(perspectives=job.storm_planning.perspectives)
    job.units = {
        unit.unit_id: UnitCheckpointV4(research_unit_id=unit.unit_id, status="planned")
        for unit in plan.units
    }
    job.plan_memo = PlanMemoV4(
        title=f"《{dossier.work.canonical_title}》特色研究备忘录",
        objective=job.brief.user_goal,
        scope=f"{job.brief.media_version} · {job.brief.allowed_source_scope}",
        reconnaissance_summary=reconnaissance.summary,
        mandatory_units=[unit for unit in plan.units if unit.track == "mandatory"],
        signature_units=[unit for unit in plan.units if unit.track == "signature"],
        risks=reconnaissance.contamination_risks,
        perspectives=job.storm_planning.perspectives,
        research_turns=job.storm_planning.research_turns,
        direct_outline=job.storm_planning.direct_outline,
        research_outline=job.storm_planning.research_outline,
        strategy=job.strategy,
    )
    job.status = "awaiting_plan_approval"
    job.errors = [item for item in job.errors if not item.startswith(("reconnaissance:", "supervisor:"))]
    job.updated_at = datetime.now(timezone.utc)
    materialize_planning_artifacts(job, repository.ROOT)
    repository.save(job)
    record_checkpoint(job, stage="perspectives", status="completed", attempt=job.planning_attempt)
    record_checkpoint(job, stage="plan_synthesis", status="completed", attempt=job.planning_attempt)
    record_checkpoint(job, stage="planning", status="completed", attempt=job.planning_attempt)
    return job


def create(request: ResearchJobCreateV4) -> ResearchRuntimeV4:
    """Synchronous service entry point retained for tests and non-HTTP callers."""
    return plan_job(start(request).job_id)


def prepare_planning_retry(job_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.status != "planning_failed":
        raise HTTPException(409, "Only a failed planning job can be retried")
    job.status = "created"
    job.planning_failure = None
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    return job

def approve(job_id: str, request: PlanApprovalV4) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.status != "awaiting_plan_approval" or job.plan is None:
        raise HTTPException(409, "Plan is not awaiting approval")
    units = request.units if request.units is not None else job.plan.units
    try:
        plan = ResearchPlanRevisionV4.model_validate(job.plan.model_copy(update={"units": units}, deep=True).model_dump())
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    available_ids = {unit.unit_id for unit in plan.units}
    selected_ids = request.selected_unit_ids if request.selected_unit_ids is not None else [unit.unit_id for unit in plan.units]
    if not selected_ids:
        raise HTTPException(422, "Select at least one research plan item")
    if len(selected_ids) != len(set(selected_ids)) or not set(selected_ids).issubset(available_ids):
        raise HTTPException(422, "selected_unit_ids must contain unique ids from this plan")
    plan.approved = True
    plan.selected_unit_ids = selected_ids
    for unit in plan.units:
        unit.status = "approved" if unit.unit_id in selected_ids else "planned"
    job.plan = plan
    job.units = {
        unit.unit_id: UnitCheckpointV4(research_unit_id=unit.unit_id, status="approved")
        for unit in plan.units if unit.unit_id in selected_ids
    }
    job.status = "researching"
    job.provider_response_id = None
    job.research_report = None
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    return job


def run_unit(job_id: str, unit_id: str, *, toolbox: SearchToolboxV4 | None = None) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.plan is None:
        raise HTTPException(409, "Research plan is not ready")
    checkpoint = job.units.get(unit_id)
    unit = next((item for item in job.plan.units if item.unit_id == unit_id), None)
    if job.status not in {"searching", "curating", "verifying", "reflecting", "partially_completed"} or not checkpoint or not unit:
        raise HTTPException(409, "Research Unit cannot be searched in the current state")
    retry_empty_search = checkpoint.status == "searched" and checkpoint.finding_bundle is not None and not (
        checkpoint.finding_bundle.evidence_candidates or checkpoint.finding_bundle.counterevidence_candidates
    )
    if checkpoint.status not in {"approved", "failed"} and not retry_empty_search:
        raise HTTPException(409, "Research Unit already has a search checkpoint")
    shared_snapshots = {
        snapshot_id: FrozenPage(snapshot_id, job.search_session.snapshot_urls.get(snapshot_id, ""), snapshot_id, text)
        for snapshot_id, text in job.search_session.snapshots.items()
    }
    workspace = SearchWorkspace(
        hits={url: SourceCandidateV4.model_validate(data) for url, data in job.search_session.sources.items()},
        snapshots=shared_snapshots,
        queries=list(job.search_session.queries),
    )
    capture = toolbox or CapturingToolbox(shared_snapshots)
    checkpoint.status = "searching"
    checkpoint.attempt += 1
    repository.save(job)
    record_checkpoint(job, stage="search", status="started", unit_id=unit_id, attempt=checkpoint.attempt)
    try:
        checkpoint.finding_bundle = run_search_agent(
            work=job.work, unit=unit, funnel=build_funnel(job.work, unit), toolbox=capture, workspace=workspace,
        )
        checkpoint.snapshots = getattr(capture, "snapshots", {})
        job.search_session.queries = list(workspace.queries)
        for query in checkpoint.finding_bundle.queries_executed:
            owners = job.search_session.query_units.setdefault(query, [])
            if unit_id not in owners:
                owners.append(unit_id)
        job.search_session.sources = {
            url: item.model_dump(mode="json") for url, item in workspace.hits.items()
        }
        for snapshot_id, page in workspace.snapshots.items():
            job.search_session.snapshots[snapshot_id] = page.text
            job.search_session.snapshot_urls[snapshot_id] = page.url
        job.search_session.cache_hits += len(set(checkpoint.snapshots) & set(shared_snapshots))
        evidence_count = len(checkpoint.finding_bundle.evidence_candidates) + len(checkpoint.finding_bundle.counterevidence_candidates)
        if evidence_count == 0:
            checkpoint.status = "failed"
            checkpoint.error = "Search completed without citable evidence. Review provider errors and retry."
            job.status = "partially_completed"
            job.errors.append(f"{unit_id}: {checkpoint.error}")
        else:
            checkpoint.status = "searched"
            job.status = "curating"
            record_checkpoint(job, stage="search", status="completed", unit_id=unit_id, attempt=checkpoint.attempt)
    except Exception as error:
        checkpoint.status = "failed"
        checkpoint.error = str(error)
        job.status = "partially_completed"
        job.errors.append(f"{unit_id}: {error}")
        record_checkpoint(job, stage="search", status="failed", unit_id=unit_id, attempt=checkpoint.attempt, error=str(error))
    if checkpoint.status == "failed" and not any(
        item.operation_key == f"{job.job_id}:{unit_id}:search:{checkpoint.attempt}" and item.status == "failed"
        for item in repository.list_checkpoints(job.job_id)
    ):
        record_checkpoint(job, stage="search", status="failed", unit_id=unit_id, attempt=checkpoint.attempt, error=checkpoint.error)
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    return job

def run_search_session(job_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.plan is None or not job.plan.approved:
        raise HTTPException(409, "Research plan is not approved")
    pending = []
    for unit in job.plan.units:
        checkpoint = job.units.get(unit.unit_id)
        if checkpoint is None:
            continue
        empty_search = checkpoint.status == "searched" and checkpoint.finding_bundle is not None and not (
            checkpoint.finding_bundle.evidence_candidates or checkpoint.finding_bundle.counterevidence_candidates
        )
        if checkpoint.status in {"approved", "failed"} or empty_search:
            pending.append(unit.unit_id)
    for unit_id in pending:
        job = run_unit(job_id, unit_id)
        if job.units[unit_id].status == "failed":
            break
    return job


def curate_unit(job_id: str, unit_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.plan is None:
        raise HTTPException(409, "Research plan is not ready")
    checkpoint = job.units.get(unit_id)
    unit = next((item for item in job.plan.units if item.unit_id == unit_id), None)
    if not checkpoint or not unit or checkpoint.status != "searched" or not checkpoint.finding_bundle:
        raise HTTPException(409, "Research Unit has no searchable FindingBundle")
    attempt = max(checkpoint.attempt, 1)
    record_checkpoint(job, stage="curate", status="started", unit_id=unit_id, attempt=attempt)
    try:
        checkpoint.curated = curate(unit=unit, findings=checkpoint.finding_bundle)
        checkpoint.status = "curated"
        job.status = "verifying"
        job.updated_at = datetime.now(timezone.utc)
        repository.save(job)
        record_checkpoint(job, stage="curate", status="completed", unit_id=unit_id, attempt=attempt)
        return job
    except Exception as error:
        checkpoint.status = "failed"
        checkpoint.error = str(error)
        job.status = "partially_completed"
        repository.save(job)
        record_checkpoint(job, stage="curate", status="failed", unit_id=unit_id, attempt=attempt, error=str(error))
        raise


def verify_unit(job_id: str, unit_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    checkpoint = job.units.get(unit_id)
    if not checkpoint or checkpoint.status != "curated" or not checkpoint.curated or not checkpoint.finding_bundle:
        raise HTTPException(409, "Research Unit has no curated candidates")
    attempt = max(checkpoint.attempt, 1)
    record_checkpoint(job, stage="verify", status="started", unit_id=unit_id, attempt=attempt)
    try:
        all_evidence = [*checkpoint.finding_bundle.evidence_candidates, *checkpoint.finding_bundle.counterevidence_candidates]
        checkpoint.verification_results = verify_batch(
            claims=checkpoint.curated.claims, evidence=all_evidence, snapshots=checkpoint.snapshots,
            counterevidence_ids={item.candidate_id for item in checkpoint.finding_bundle.counterevidence_candidates},
        )
        checkpoint.status = "verified"
        job.status = "reflecting" if all(item.status == "verified" for item in job.units.values()) else "searching"
        job.updated_at = datetime.now(timezone.utc)
        repository.save(job)
        record_checkpoint(job, stage="verify", status="completed", unit_id=unit_id, attempt=attempt)
        return job
    except Exception as error:
        checkpoint.status = "failed"
        checkpoint.error = str(error)
        job.status = "partially_completed"
        repository.save(job)
        record_checkpoint(job, stage="verify", status="failed", unit_id=unit_id, attempt=attempt, error=str(error))
        raise


def freeze(job_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if not all(item.status == "verified" for item in job.units.values()):
        raise HTTPException(409, "All Research Units must be verified before knowledge freeze")
    if job.verified_knowledge is not None and job.status in {"knowledge_frozen", "writing", "mapping", "auditing", "needs_review", "depositing", "ready_to_publish", "published"}:
        return job
    record_checkpoint(job, stage="freeze", status="started")
    batches = [item.curated for item in job.units.values() if item.curated]
    results = [result for item in job.units.values() for result in item.verification_results]
    evidence = [candidate for item in job.units.values() if item.finding_bundle for candidate in [*item.finding_bundle.evidence_candidates, *item.finding_bundle.counterevidence_candidates]]
    counter_ids = {candidate.candidate_id for item in job.units.values() if item.finding_bundle for candidate in item.finding_bundle.counterevidence_candidates}
    job.verified_knowledge = freeze_verified_knowledge(
        work_id=job.work.work_id, media_version=job.brief.media_version,
        units=job.plan.units, curated_batches=batches, verification_results=results,
        evidence=evidence, counterevidence_ids=counter_ids,
    )
    complete, reasons = completion_check(job.verified_knowledge, job.plan.units)
    job.status = "knowledge_frozen" if complete else "reflecting"
    job.errors.extend(reason for reason in reasons if reason not in job.errors)
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    record_checkpoint(job, stage="freeze", status="completed")
    return job


def project(job_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.status != "knowledge_frozen" or not job.verified_knowledge:
        raise HTTPException(409, "Verified Knowledge must pass completion checks before projection")
    if job.case_file is not None and job.projection_audit is not None:
        return job
    record_checkpoint(job, stage="projection", status="started")
    try:
        job.status = "writing"
        if job.case_file is None:
            job.case_file = write_case_file(work=job.work, knowledge=job.verified_knowledge)
        job.status = "mapping"
        if not job.proposals:
            job.proposals = map_knowledge_proposals(job.verified_knowledge)
        job.status = "auditing"
        job.projection_audit = cross_projection_audit(job.case_file, job.proposals, job.verified_knowledge)
        job.status = "needs_review" if job.projection_audit.passed else "auditing"
        job.updated_at = datetime.now(timezone.utc)
        repository.save(job)
        record_checkpoint(job, stage="projection", status="completed")
        return job
    except Exception as error:
        job.status = "knowledge_frozen"
        job.errors.append(f"Projection failed: {error}")
        repository.save(job)
        record_checkpoint(job, stage="projection", status="failed", error=str(error))
        raise


def resume_research_job(job_id: str) -> ResearchRuntimeV4:
    """Continue a persisted job from its first incomplete automatic stage."""
    job = get(job_id)
    if job.status in {"awaiting_plan_approval", "needs_review", "published", "cancelled", "budget_exhausted"}:
        return job
    if job.status in {"created", "planning_failed", "reconnaissance_running", "perspective_generating", "supervisor_planning"}:
        return plan_job(job_id)
    if job.plan is None or not job.plan.approved:
        return job

    for unit in job.plan.units:
        checkpoint = get(job_id).units[unit.unit_id]
        if checkpoint.status == "verified":
            continue
        if checkpoint.status in {"approved", "failed", "searching"}:
            # A persisted "searching" state means the previous process stopped mid-stage.
            if checkpoint.status == "searching":
                checkpoint.status = "failed"
                checkpoint.error = "Interrupted search recovered for retry"
                job = get(job_id)
                job.units[unit.unit_id] = checkpoint
                job.status = "partially_completed"
                repository.save(job)
            checkpoint = get(job_id).units[unit.unit_id]
            if checkpoint.status == "failed" and checkpoint.curated is not None and checkpoint.finding_bundle is not None:
                checkpoint.status = "curated"
                job = get(job_id); job.units[unit.unit_id] = checkpoint; repository.save(job)
            elif checkpoint.status == "failed" and checkpoint.finding_bundle is not None and (
                checkpoint.finding_bundle.evidence_candidates or checkpoint.finding_bundle.counterevidence_candidates
            ):
                checkpoint.status = "searched"
                job = get(job_id); job.units[unit.unit_id] = checkpoint; repository.save(job)
            else:
                job = run_unit(job_id, unit.unit_id)
                if job.units[unit.unit_id].status == "failed":
                    return job
        checkpoint = get(job_id).units[unit.unit_id]
        if checkpoint.status == "searched":
            curate_unit(job_id, unit.unit_id)
        checkpoint = get(job_id).units[unit.unit_id]
        if checkpoint.status == "curated":
            verify_unit(job_id, unit.unit_id)

    job = get(job_id)
    if all(item.status == "verified" for item in job.units.values()) and job.verified_knowledge is None:
        job = freeze(job_id)
    if job.status == "knowledge_frozen" and job.case_file is None:
        job = project(job_id)
    return job
