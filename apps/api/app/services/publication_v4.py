from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.services import research_repository_v4 as repository
from app.services.orchestrator_v4 import get
from app.services.working_memory_v4 import record as record_checkpoint
from logispace_domain import dossiers
from logispace_domain.models import DossierEntity, DossierRelation, WorkDossier
from logispace_domain.models_v4_publish import ProposalReviewV4, ResearchDeltaV4
from logispace_domain.models_v4_verified import VerifiedKnowledgeSnapshotV4

DATA = Path(__file__).resolve().parents[4] / "data"


def review(job_id: str, request: ProposalReviewV4):
    job = get(job_id)
    if job.status != "needs_review":
        raise HTTPException(409, "Job is not awaiting human review")
    known = {item.proposal_id for item in job.proposals}
    selected = set(request.approved_proposal_ids) | set(request.rejected_proposal_ids)
    if not selected <= known:
        raise HTTPException(422, "Review references unknown proposals")
    if set(request.approved_proposal_ids) & set(request.rejected_proposal_ids):
        raise HTTPException(422, "A proposal cannot be both approved and rejected")
    for proposal in job.proposals:
        if proposal.proposal_id in request.approved_proposal_ids:
            proposal.review_status = "approved"
        elif proposal.proposal_id in request.rejected_proposal_ids:
            proposal.review_status = "rejected"
    repository.save(job)
    return job


def _next_version(version: str) -> str:
    major, minor, _ = (int(value) for value in version.split("."))
    return f"{major}.{minor + 1}.0"


def _apply(draft, proposal, delta: ResearchDeltaV4):
    payload = proposal.payload
    if proposal.operation == "add_relation":
        required = {"source_character_id", "target_character_id", "relation_type"}
        if not required <= set(payload):
            raise HTTPException(409, f"Relation proposal {proposal.proposal_id} lacks typed fields")
        relation = DossierRelation(
            source_id=payload["source_character_id"], relation=payload["relation_type"],
            target_id=payload["target_character_id"], note=payload.get("summary"),
        )
        draft.relations.append(relation)
        delta.added_relations.append(f"{relation.source_id}:{relation.relation}:{relation.target_id}")
        return
    type_map = {
        "add_timeline_event": "Event", "add_timeline_alignment": "TimelineAlignment",
        "add_trick": "Trick", "add_murder_method": "MurderMethod",
        "add_entity": str(payload.get("entity_type", "Entity")),
    }
    if proposal.operation in type_map:
        entity_id = str(payload.get("entity_id", f"{type_map[proposal.operation].lower()}_{proposal.proposal_id}"))
        entity = DossierEntity(
            entity_id=entity_id, entity_type=type_map[proposal.operation],
            name=str(payload.get("name", payload.get("title", proposal.operation))),
            summary=str(payload.get("summary", "Verified knowledge proposal")),
            attributes={**payload, "claim_ids": proposal.claim_ids, "evidence_ids": proposal.evidence_ids},
        )
        draft.entities.append(entity)
        delta.added_entities.append(entity_id)
        return
    if proposal.operation == "flag_conflict":
        delta.flagged_conflicts.append(str(payload.get("summary", "conflict")))


def publish(job_id: str) -> tuple[object, ResearchDeltaV4]:
    job = get(job_id)
    if job.status == "published" and job.published_version:
        delta_path = DATA / "works" / job.work.work_id / "versions" / job.published_version / "research-delta.json"
        if delta_path.exists():
            return job, ResearchDeltaV4.model_validate_json(delta_path.read_text(encoding="utf-8"))
    if job.status == "depositing":
        manifest_path = DATA / "works" / job.work.work_id / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            recovered_version = next((version for version, item in manifest.get("knowledge_versions", {}).items() if item.get("source_job_id") == job.job_id), None)
            if recovered_version:
                delta_path = DATA / "works" / job.work.work_id / "versions" / recovered_version / "research-delta.json"
                if delta_path.exists():
                    job.status = "published"
                    job.published_version = recovered_version
                    repository.save(job)
                    return job, ResearchDeltaV4.model_validate_json(delta_path.read_text(encoding="utf-8"))
    if job.status not in {"needs_review", "depositing"} or not job.verified_knowledge or not job.case_file:
        raise HTTPException(409, "Job is not publishable")
    approved = [item for item in job.proposals if item.review_status == "approved"]
    pending = [item for item in job.proposals if item.review_status == "pending"]
    if pending:
        raise HTTPException(409, "All proposals require an explicit human decision")
    if not approved:
        raise HTTPException(409, "Approve at least one proposal before publishing")
    known_claims = {item.claim_id for item in job.verified_knowledge.claims}
    known_evidence = set(job.verified_knowledge.evidence_ids)
    for proposal in approved:
        if not set(proposal.claim_ids) <= known_claims or not set(proposal.evidence_ids) <= known_evidence:
            raise HTTPException(409, "Approved proposal is outside frozen Verified Knowledge")
    base = dossiers.get_dossier(job.work.work_id)
    is_new_work = base is None
    if base is None:
        base = WorkDossier(
            work=job.work, dossier_version="0.0.0", entities=[], relations=[],
            golden_questions=[], revision_findings=["Created by LogiSpace 0.4 research."],
        )
    target_version = _next_version(base.dossier_version)
    draft = base.model_copy(deep=True)
    draft.dossier_version = target_version
    delta = ResearchDeltaV4(
        work_id=job.work.work_id, base_version=base.dossier_version,
        target_version=target_version,
        source_verified_knowledge_snapshot_id=job.verified_knowledge.snapshot_id,
    )
    for proposal in approved:
        _apply(draft, proposal, delta)
    work_root = DATA / "works" / job.work.work_id
    target = work_root / "versions" / target_version
    if target.exists():
        delta_path = target / "research-delta.json"
        verified_path = target / "verified-knowledge.json"
        if delta_path.exists() and verified_path.exists() and VerifiedKnowledgeSnapshotV4.model_validate_json(verified_path.read_text(encoding="utf-8")).snapshot_id == job.verified_knowledge.snapshot_id:
            job.status = "published"
            job.published_version = target_version
            repository.save(job)
            return job, ResearchDeltaV4.model_validate_json(delta_path.read_text(encoding="utf-8"))
        raise HTTPException(409, "Target dossier version already exists")
    temporary = work_root / "versions" / f".deposit-{uuid4().hex}"
    job.status = "depositing"
    repository.save(job)
    record_checkpoint(job, stage="deposit", status="started")
    try:
        temporary.mkdir(parents=True)
        (temporary / "dossier.json").write_text(draft.model_dump_json(indent=2), encoding="utf-8")
        (temporary / "case-file.json").write_text(job.case_file.model_dump_json(indent=2), encoding="utf-8")
        (temporary / "verified-knowledge.json").write_text(job.verified_knowledge.model_dump_json(indent=2), encoding="utf-8")
        (temporary / "research-delta.json").write_text(delta.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)
        manifest_path = work_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
            "work_id": job.work.work_id,
            "current_dossier_version": target_version,
            "ontology_version": draft.ontology_version,
            "dossier_versions": [],
        }
        manifest["current_dossier_version"] = target_version
        manifest["current_knowledge_version"] = target_version
        manifest.setdefault("knowledge_versions", {})[target_version] = {
            "media_version": job.verified_knowledge.media_version,
            "source_job_id": job.job_id,
            "snapshot_id": job.verified_knowledge.snapshot_id,
        }
        versions = manifest.setdefault("dossier_versions", [])
        if target_version not in versions:
            versions.append(target_version)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        if is_new_work:
            catalog_path = DATA / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            if not any(item["work_id"] == job.work.work_id for item in catalog["works"]):
                catalog["works"].append({
                    "work_id": job.work.work_id, "manifest": f"works/{job.work.work_id}/manifest.json",
                })
                catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as error:
        job.status = "needs_review"
        job.errors.append(f"Deposit failed: {error}")
        repository.save(job)
        record_checkpoint(job, stage="deposit", status="failed", error=str(error))
        raise
    dossiers._catalog.cache_clear()
    cache_clear = getattr(dossiers.get_dossier, "cache_clear", None)
    if cache_clear:
        cache_clear()
    job.status = "published"
    job.published_version = target_version
    repository.save(job)
    record_checkpoint(job, stage="deposit", status="completed")
    return job, delta
