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
from app.services.supervisor_v4 import generate_plan
from app.services.verified_knowledge_v4 import completion_check, freeze_verified_knowledge
from app.services.verifier_v4 import verify_batch
from logispace_domain import dossiers
from logispace_domain.models import WorkDossier
from logispace_domain.models_v4 import PlanApprovalV4, ResearchBriefV4, ResearchJobCreateV4, ResearchPlanRevisionV4, ResearchStrategyV4
from logispace_domain.models_v4_agent import SourceCandidateV4
from logispace_domain.models_v4_memo import PlanMemoUpdateV4, PlanMemoV4
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


def _coverage(dossier, domain):
    types = {
        "multiple_timelines": {"Event", "Reveal", "NarrativeUnit"},
        "tricks": {"Trick"}, "murder_methods": {"MurderMethod"},
    }
    if domain == "relationships":
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
    brief = request.brief or ResearchBriefV4(work_id=dossier.work.work_id)
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
    return job


def plan_job(job_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.status not in {"created", "planning_failed", "reconnaissance_running", "supervisor_planning"}:
        raise HTTPException(409, "Research job is not eligible for planning")
    dossier = _planning_dossier(job)
    coverage = [_coverage(dossier, domain) for domain in MANDATORY]
    job.planning_attempt += 1
    job.planning_failure = None
    job.status = "reconnaissance_running"
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    try:
        reconnaissance = run_reconnaissance(brief=job.brief, dossier=dossier)
    except ReconnaissanceFormatError as error:
        return _planning_failed(job, stage="reconnaissance", code="invalid_structured_output", error=error)
    except RuntimeError as error:
        return _planning_failed(job, stage="reconnaissance", code="reconnaissance_failed", error=error)

    job.reconnaissance = reconnaissance
    job.status = "supervisor_planning"
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    try:
        run = generate_plan(
            brief=job.brief, dossier=dossier, coverage=coverage,
            budget=job.planning_budget, reconnaissance=reconnaissance,
            strategy=job.strategy,
        )
    except RuntimeError as error:
        return _planning_failed(job, stage="supervisor", code="supervisor_failed", error=error)

    plan = ResearchPlanRevisionV4(
        coverage=coverage, units=run.output.units, budget=job.planning_budget,
        rationale=f"{run.output.rationale} [model={run.model}; prompt={run.prompt_version}]",
        strategy=job.strategy,
    )
    job.plan = plan
    job.units = {
        unit.unit_id: UnitCheckpointV4(research_unit_id=unit.unit_id, status="planned")
        for unit in plan.units
    }
    job.plan_memo = PlanMemoV4(
        title=f"《{dossier.work.canonical_title}》特色研究备忘录",
        objective=job.brief.user_goal,
        scope=f"{job.brief.media_version} · {job.brief.allowed_source_scope}",
        reconnaissance_summary=reconnaissance.summary,
        signature_units=[unit for unit in plan.units if unit.track == "signature"],
        risks=reconnaissance.contamination_risks,
        strategy=job.strategy,
    )
    job.status = "awaiting_plan_approval"
    job.errors = [item for item in job.errors if not item.startswith(("reconnaissance:", "supervisor:"))]
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
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
    plan.approved = True
    for unit in plan.units:
        unit.status = "approved"
    job.plan = plan
    job.units = {unit.unit_id: UnitCheckpointV4(research_unit_id=unit.unit_id, status="approved") for unit in plan.units}
    job.status = "searching"
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
    except Exception as error:
        checkpoint.status = "failed"
        checkpoint.error = str(error)
        job.status = "partially_completed"
        job.errors.append(f"{unit_id}: {error}")
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    return job

def run_search_session(job_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.plan is None or not job.plan.approved:
        raise HTTPException(409, "Research plan is not approved")
    pending = []
    for unit in job.plan.units:
        checkpoint = job.units[unit.unit_id]
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
    checkpoint.curated = curate(unit=unit, findings=checkpoint.finding_bundle)
    checkpoint.status = "curated"
    job.status = "verifying"
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    return job


def verify_unit(job_id: str, unit_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    checkpoint = job.units.get(unit_id)
    if not checkpoint or checkpoint.status != "curated" or not checkpoint.curated or not checkpoint.finding_bundle:
        raise HTTPException(409, "Research Unit has no curated candidates")
    all_evidence = [*checkpoint.finding_bundle.evidence_candidates, *checkpoint.finding_bundle.counterevidence_candidates]
    checkpoint.verification_results = verify_batch(
        claims=checkpoint.curated.claims, evidence=all_evidence, snapshots=checkpoint.snapshots,
        counterevidence_ids={item.candidate_id for item in checkpoint.finding_bundle.counterevidence_candidates},
    )
    checkpoint.status = "verified"
    job.status = "reflecting" if all(item.status == "verified" for item in job.units.values()) else "searching"
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    return job


def freeze(job_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if not all(item.status == "verified" for item in job.units.values()):
        raise HTTPException(409, "All Research Units must be verified before knowledge freeze")
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
    return job


def project(job_id: str) -> ResearchRuntimeV4:
    job = get(job_id)
    if job.status != "knowledge_frozen" or not job.verified_knowledge:
        raise HTTPException(409, "Verified Knowledge must pass completion checks before projection")
    job.status = "writing"
    job.case_file = write_case_file(work=job.work, knowledge=job.verified_knowledge)
    job.status = "mapping"
    job.proposals = map_knowledge_proposals(job.verified_knowledge)
    job.status = "auditing"
    job.projection_audit = cross_projection_audit(job.case_file, job.proposals, job.verified_knowledge)
    job.status = "needs_review" if job.projection_audit.passed else "auditing"
    job.updated_at = datetime.now(timezone.utc)
    repository.save(job)
    return job
