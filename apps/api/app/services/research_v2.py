from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.services.llm import gateway
from app.services.runtime_store import JsonStore
from logispace_domain import dossiers as dossier_repository
from logispace_domain.models import EvidenceItem, KnowledgeProposal, ProposalReview, ResearchCoverage, ResearchJobV2, ResearchJobV2Create, SourceDocument, WorkDossier

_store = JsonStore("research_jobs")
_DATA_ROOT = Path(__file__).resolve().parents[4] / "data"
_REQUIRED_SECTIONS = {
    "identity": {"Work"},
    "characters": {"Character", "CollectiveActor"},
    "relationships": set(),
    "timeline_truth": {"Event"},
    "timeline_investigation": {"Reveal"},
    "timeline_narrative": {"NarrativeUnit"},
    "clues_testimony": {"Clue", "Testimony"},
    "murder_method": {"MurderMethod"},
    "trick": {"Trick"},
    "solution": {"SolutionModel"},
}


def _target_version(current: str) -> str:
    major, minor, _patch = (int(part) for part in current.split("."))
    return f"{major}.{minor + 1}.0"


def _coverage(dossier: WorkDossier) -> list[ResearchCoverage]:
    types = {item.entity_type for item in dossier.entities}
    result = []
    for section, expected in _REQUIRED_SECTIONS.items():
        if section == "identity":
            result.append(ResearchCoverage(section=section, status="sufficient", entity_ids=[dossier.work.work_id]))
            continue
        if section == "relationships":
            ok = bool(dossier.relations)
            entity_ids = list(dict.fromkeys(value for relation in dossier.relations for value in (relation.source_id, relation.target_id)))
        else:
            entity_ids = [item.entity_id for item in dossier.entities if item.entity_type in expected]
            ok = bool(entity_ids)
        result.append(ResearchCoverage(section=section, status="sufficient" if ok else "partial", knowledge_gaps=[] if ok else [f"{section} has no structured content"], entity_ids=entity_ids))
    return result


def list_jobs() -> list[ResearchJobV2]:
    return sorted(_store.list(ResearchJobV2), key=lambda item: item.updated_at, reverse=True)


def get_job(job_id: str) -> ResearchJobV2:
    job = _store.load(job_id, ResearchJobV2)
    if job is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    return job


def create_job(request: ResearchJobV2Create) -> ResearchJobV2:
    dossier = dossier_repository.get_dossier(request.work_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Work must be resolved before deep research")
    duplicate = next((item for item in list_jobs() if item.work_id == request.work_id and item.base_version == dossier.dossier_version and item.status not in {"published", "failed"}), None)
    if duplicate is not None:
        return duplicate
    job = ResearchJobV2(
        job_id=f"research_{uuid4().hex[:12]}",
        work_id=request.work_id,
        media_scope=request.media_scope,
        research_scope=request.research_scope,
        base_version=dossier.dossier_version,
        target_version=_target_version(dossier.dossier_version),
        budget=request.budget,
        status="inventorying",
    )
    _store.save(job.job_id, job)
    return _run(job, dossier)


def _run(job: ResearchJobV2, dossier: WorkDossier) -> ResearchJobV2:
    try:
        job.coverage = _coverage(dossier)
        job.status = "planning"
        _store.save(job.job_id, job)
        gaps = [item.section for item in job.coverage if item.status != "sufficient"]
        research_text = ""
        if gateway.available:
            job.status = "collecting"
            _store.save(job.job_id, job)
            result = gateway.respond(
                instructions=(
                    "You are the LogiSpace deep-research agent. Research the selected work and fill the listed knowledge gaps."
                    " Separate originals from adaptations, cite facts, and answer in the user's language."
                ),
                input_text=(
                    f"Work: {dossier.work.canonical_title}\nMedia: {job.media_scope}\n"
                    f"Existing entity types: {sorted({item.entity_type for item in dossier.entities})}\n"
                    f"Knowledge gaps: {gaps or ['strengthen evidence']}\n"
                    "Perform web research and return an evidence-oriented incremental research summary."
                ),
                research=True,
                web_search=True,
            )
            research_text = result.text
            job.usage.search_rounds = 1
            job.usage.input_tokens = result.input_tokens
            job.usage.output_tokens = result.output_tokens
            urls = [item for item in result.annotations if item.get("url")]
            for index, annotation in enumerate(urls[: job.budget.max_sources]):
                job.sources.append(SourceDocument(source_id=f"source_{job.job_id}_{index}", url=annotation["url"], title=annotation.get("title") or annotation["url"], source_type="web", credibility=0.65, captured_text=research_text[:4000]))
        else:
            research_text = "OPENAI_API_KEY is not configured. The existing WorkDossier was inventoried; configure a key to continue web research."
        if not job.sources:
            job.sources.append(SourceDocument(source_id=f"source_{job.job_id}_baseline", url=f"logispace://dossiers/{job.work_id}/{job.base_version}", title=f"WorkDossier {job.base_version}", source_type="work_dossier", credibility=0.8, captured_text=research_text))
        job.usage.sources = len(job.sources)
        job.status = "extracting"
        evidence = EvidenceItem(evidence_id=f"evidence_{job.job_id}_summary", source_id=job.sources[0].source_id, locator="research-summary", quote=research_text[:1200], ontology_type="Work", entities=[job.work_id], confidence=0.7 if gateway.available else 0.5)
        job.evidence.append(evidence)
        job.status = "verifying"
        proposals = []
        for item in job.coverage:
            operation = "retain" if item.status == "sufficient" else "strengthen"
            proposals.append(KnowledgeProposal(proposal_id=f"proposal_{uuid4().hex[:10]}", operation=operation, target_section=item.section, summary=("Retain verified structure" if operation == "retain" else f"Strengthen {item.section}: {research_text[:240]}"), evidence_ids=[evidence.evidence_id], confidence=0.85 if operation == "retain" else 0.65))
        job.proposals = proposals
        job.status = "drafting"
        draft_data = dossier.model_dump()
        draft_data["dossier_version"] = job.target_version
        draft_data["revision_findings"] = list(dict.fromkeys(dossier.revision_findings + [f"0.2 research job {job.job_id}: {len(proposals)} proposals generated"]))
        job.draft = WorkDossier.model_validate(draft_data)
        job.status = "quality_check"
        WorkDossier.model_validate(job.draft.model_dump())
        job.status = "needs_review"
    except Exception as error:
        job.status = "failed"
        job.errors.append(str(error))
    job.updated_at = datetime.utcnow()
    _store.save(job.job_id, job)
    return job


def review_job(job_id: str, request: ProposalReview) -> ResearchJobV2:
    job = get_job(job_id)
    approved = set(request.approved_proposal_ids)
    rejected = set(request.rejected_proposal_ids)
    for proposal in job.proposals:
        if proposal.proposal_id in approved:
            proposal.review_status = "approved"
        elif proposal.proposal_id in rejected:
            proposal.review_status = "rejected"
    job.updated_at = datetime.utcnow()
    _store.save(job.job_id, job)
    return job


def publish_job(job_id: str) -> ResearchJobV2:
    job = get_job(job_id)
    if job.status != "needs_review" or job.draft is None:
        raise HTTPException(status_code=409, detail="Only reviewed draft jobs can be published")
    if not any(item.review_status == "approved" for item in job.proposals):
        raise HTTPException(status_code=409, detail="Approve at least one proposal before publishing")
    if job.usage.search_rounds == 0:
        raise HTTPException(status_code=409, detail="Configure OPENAI_API_KEY and complete real research before publishing")
    record = next((item for item in json.loads((_DATA_ROOT / "catalog.json").read_text(encoding="utf-8"))["works"] if item["work_id"] == job.work_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Work catalog entry not found")
    manifest_path = _DATA_ROOT / record["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version_dir = manifest_path.parent / "versions" / job.target_version
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "dossier.json").write_text(job.draft.model_dump_json(indent=2), encoding="utf-8")
    manifest["current_dossier_version"] = job.target_version
    versions = manifest.setdefault("dossier_versions", [])
    if job.target_version not in versions:
        versions.append(job.target_version)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    dossier_repository.get_dossier.cache_clear()
    job.status = "published"
    job.updated_at = datetime.utcnow()
    _store.save(job.job_id, job)
    return job
