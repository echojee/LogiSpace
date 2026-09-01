from __future__ import annotations

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from logispace_domain import dossiers
from logispace_domain.models_memory import KnowledgeMemoryV1
from logispace_domain.models_v4_projection import CaseFileV4
from logispace_domain.models_v4_verified import VerifiedKnowledgeSnapshotV4
from logispace_domain.models_v4_runtime import ResearchRuntimeV4

DATA = Path(__file__).resolve().parents[4] / "data"


def _work_root(work_id: str) -> Path:
    return DATA / "works" / work_id


def deposit_report(job: ResearchRuntimeV4) -> Path:
    """Persist a completed Markdown report as reusable work-scoped knowledge."""
    if job.research_report is None:
        raise ValueError("research_report is required")
    root = _work_root(job.work.work_id) / "knowledge" / "reports" / job.job_id
    root.mkdir(parents=True, exist_ok=True)
    markdown_path = root / "report.md"
    metadata_path = root / "report.json"
    markdown_path.write_text(job.research_report.markdown, encoding="utf-8")
    metadata = {
        "schema_version": "knowledge-report-v1",
        "work_id": job.work.work_id,
        "work_title": job.work.canonical_title,
        "media_version": job.brief.media_version,
        "source_job_id": job.job_id,
        "title": job.research_report.title,
        "model": job.research_report.model,
        "provider_response_id": job.research_report.provider_response_id,
        "citations": [item.model_dump(mode="json") for item in job.research_report.citations],
        "generated_at": job.research_report.generated_at.isoformat(),
        "deposited_at": datetime.now(timezone.utc).isoformat(),
        "markdown_file": "report.md",
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    index_path = _work_root(job.work.work_id) / "knowledge" / "reports" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"reports": []}
    index["reports"] = [item for item in index["reports"] if item.get("source_job_id") != job.job_id]
    index["reports"].append({key: metadata[key] for key in (
        "source_job_id", "media_version", "title", "model", "generated_at", "deposited_at"
    )})
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def list_reports(work_id: str, media_version: str | None = None) -> list[dict]:
    index_path = _work_root(work_id) / "knowledge" / "reports" / "index.json"
    if not index_path.exists():
        return []
    reports = json.loads(index_path.read_text(encoding="utf-8")).get("reports", [])
    if media_version:
        reports = [item for item in reports if item.get("media_version") == media_version]
    return sorted(reports, key=lambda item: item.get("generated_at", ""), reverse=True)


def list_all_reports() -> list[dict]:
    result: list[dict] = []
    works_root = DATA / "works"
    if not works_root.exists():
        return result
    for work_root in works_root.iterdir():
        if not work_root.is_dir():
            continue
        dossier = dossiers.get_dossier(work_root.name)
        manifest = _manifest(work_root.name) or {}
        versions_by_job = {
            metadata.get("source_job_id"): version
            for version, metadata in manifest.get("knowledge_versions", {}).items()
            if metadata.get("source_job_id")
        }
        for item in list_reports(work_root.name):
            result.append({
                **item, "work_id": work_root.name,
                "work_title": dossier.work.canonical_title if dossier else item.get("work_title", item.get("title", work_root.name)),
                "knowledge_version": versions_by_job.get(item.get("source_job_id")),
            })
    return sorted(result, key=lambda item: item.get("generated_at", ""), reverse=True)


def get_report(work_id: str, job_id: str) -> dict | None:
    root = _work_root(work_id) / "knowledge" / "reports" / job_id
    metadata_path, markdown_path = root / "report.json", root / "report.md"
    if not metadata_path.exists() or not markdown_path.exists():
        return None
    return {
        **json.loads(metadata_path.read_text(encoding="utf-8")),
        "markdown": markdown_path.read_text(encoding="utf-8"),
    }


def _manifest(work_id: str) -> dict | None:
    path = _work_root(work_id) / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def version_for_source_job(work_id: str, job_id: str) -> str | None:
    manifest = _manifest(work_id) or {}
    return next((
        version for version, item in manifest.get("knowledge_versions", {}).items()
        if item.get("source_job_id") == job_id
    ), None)


def _next_knowledge_version(manifest: dict) -> str:
    values = set(manifest.get("knowledge_versions", {})) | set(manifest.get("dossier_versions", []))
    numeric = []
    for value in values:
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
        if match:
            numeric.append(tuple(int(part) for part in match.groups()))
    if not numeric:
        return "0.1.0"
    major, minor, _ = max(numeric)
    return f"{major}.{minor + 1}.0"


def publish_report_knowledge(
    job: ResearchRuntimeV4, verified: VerifiedKnowledgeSnapshotV4, case_file: CaseFileV4,
    *, force_new: bool = False,
) -> str:
    """Publish an immutable knowledge-only version derived from a reviewed report."""
    existing = version_for_source_job(job.work.work_id, job.job_id)
    if existing and not force_new:
        return existing
    work_root = _work_root(job.work.work_id)
    manifest_path = work_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
        "work_id": job.work.work_id, "dossier_versions": [], "knowledge_versions": {},
    }
    version = _next_knowledge_version(manifest)
    target = work_root / "versions" / version
    temporary = work_root / "versions" / f".knowledge-{uuid4().hex}"
    temporary.mkdir(parents=True)
    try:
        (temporary / "verified-knowledge.json").write_text(verified.model_dump_json(indent=2), encoding="utf-8")
        (temporary / "case-file.json").write_text(case_file.model_dump_json(indent=2), encoding="utf-8")
        (temporary / "report-source.json").write_text(json.dumps({
            "source_job_id": job.job_id, "report_path": f"knowledge/reports/{job.job_id}/report.md",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
    except Exception:
        if temporary.exists():
            for path in temporary.iterdir():
                path.unlink()
            temporary.rmdir()
        raise
    manifest["current_knowledge_version"] = version
    manifest.setdefault("knowledge_versions", {})[version] = {
        "media_version": verified.media_version, "source_job_id": job.job_id,
        "snapshot_id": verified.snapshot_id, "work_title": job.work.canonical_title,
        "media_type": getattr(job.work.media_type, "value", job.work.media_type),
        "release_year": job.work.release_year, "creators": job.work.creators,
        "created_at": verified.frozen_at.isoformat(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return version


def versions(work_id: str, media_version: str | None = None) -> list[str]:
    """List immutable versions that contain v4 verified knowledge."""
    manifest = _manifest(work_id)
    if not manifest:
        return []
    result: list[str] = []
    metadata = manifest.get("knowledge_versions", {})
    ordered = list(dict.fromkeys([*manifest.get("dossier_versions", []), *metadata.keys()]))
    for version in ordered:
        root = _work_root(work_id) / "versions" / version
        if not (root / "verified-knowledge.json").exists() or not (root / "case-file.json").exists():
            continue
        if media_version and metadata.get(version, {}).get("media_version") not in {None, media_version}:
            continue
        result.append(version)
    return result


def get_version(work_id: str, knowledge_version: str) -> KnowledgeMemoryV1 | None:
    """Load a reusable knowledge version from the published work store."""
    root = _work_root(work_id) / "versions" / knowledge_version
    verified_path, case_path = root / "verified-knowledge.json", root / "case-file.json"
    if not verified_path.exists() or not case_path.exists():
        return None
    manifest = _manifest(work_id) or {}
    metadata = manifest.get("knowledge_versions", {}).get(knowledge_version, {})
    verified = VerifiedKnowledgeSnapshotV4.model_validate_json(verified_path.read_text(encoding="utf-8"))
    case_file = CaseFileV4.model_validate_json(case_path.read_text(encoding="utf-8"))
    return KnowledgeMemoryV1(
        work_id=work_id,
        media_version=verified.media_version,
        knowledge_version=knowledge_version,
        source_job_id=metadata.get("source_job_id"),
        verified_knowledge=verified,
        case_file=case_file,
        created_at=verified.frozen_at,
    )


def get_current(work_id: str, media_version: str | None = None) -> KnowledgeMemoryV1 | None:
    """Load the newest compatible reusable knowledge version."""
    manifest = _manifest(work_id)
    if not manifest:
        return None
    candidates = versions(work_id, media_version)
    current = manifest.get("current_knowledge_version")
    if current in candidates:
        return get_version(work_id, current)
    return get_version(work_id, candidates[-1]) if candidates else None


def list_works() -> list[dict]:
    """List works with at least one reusable v4 knowledge version."""
    result = []
    works_root = DATA / "works"
    if not works_root.exists():
        return result
    for root in sorted(path for path in works_root.iterdir() if path.is_dir()):
        memory = get_current(root.name)
        if memory is None:
            continue
        dossier = dossiers.get_dossier(root.name)
        manifest = _manifest(root.name) or {}
        metadata = manifest.get("knowledge_versions", {}).get(memory.knowledge_version, {})
        result.append({
            "work_id": root.name,
            "title": dossier.work.canonical_title if dossier else metadata.get("work_title", memory.case_file.title),
            "media_type": (
                getattr(dossier.work.media_type, "value", dossier.work.media_type)
                if dossier else metadata.get("media_type", "unknown")
            ),
            "release_year": dossier.work.release_year if dossier else metadata.get("release_year"),
            "creators": dossier.work.creators if dossier else metadata.get("creators", []),
            "cover_url": metadata.get("cover_url"),
            "media_version": memory.media_version,
            "current_knowledge_version": memory.knowledge_version,
            "domains": sorted({claim.domain for claim in memory.verified_knowledge.claims}),
        })
    return result


def get_domain_knowledge(work_id: str, domain: str, media_version: str | None = None) -> dict:
    memory = get_current(work_id, media_version)
    if memory is None:
        raise HTTPException(404, "Knowledge memory not found")
    claims = [item for item in memory.verified_knowledge.claims if item.domain == domain]
    claim_ids = {item.claim_id for item in claims}
    objects = [item for item in memory.verified_knowledge.domain_objects if set(item.claim_ids) & claim_ids]
    return {"claims": claims, "domain_objects": objects, "knowledge_version": memory.knowledge_version}
