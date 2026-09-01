from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services import knowledge_memory_v4
from logispace_domain.models_memory import KnowledgeMemoryV1

router = APIRouter()


@router.get("/reports")
def all_reports():
    return {"reports": knowledge_memory_v4.list_all_reports()}


@router.get("/works")
def list_works():
    return knowledge_memory_v4.list_works()


@router.get("/works/{work_id}", response_model=KnowledgeMemoryV1)
def current(work_id: str, media_version: str | None = None):
    memory = knowledge_memory_v4.get_current(work_id, media_version)
    if memory is None:
        raise HTTPException(404, "Knowledge memory not found")
    return memory


@router.get("/works/{work_id}/versions")
def versions(work_id: str, media_version: str | None = None):
    return {"versions": knowledge_memory_v4.versions(work_id, media_version)}


@router.get("/works/{work_id}/reports")
def reports(work_id: str, media_version: str | None = None):
    return {"reports": knowledge_memory_v4.list_reports(work_id, media_version)}


@router.get("/works/{work_id}/reports/{job_id}")
def report(work_id: str, job_id: str):
    value = knowledge_memory_v4.get_report(work_id, job_id)
    if value is None:
        raise HTTPException(404, "Knowledge report not found")
    return value


@router.get("/works/{work_id}/reports/{job_id}/download")
def download_report(work_id: str, job_id: str):
    path = knowledge_memory_v4.DATA / "works" / work_id / "knowledge" / "reports" / job_id / "report.md"
    if not path.exists():
        raise HTTPException(404, "Knowledge report not found")
    return FileResponse(path, media_type="text/markdown; charset=utf-8", filename=f"{job_id}.md")


@router.post("/works/{work_id}/reports/{job_id}/deposit", response_model=KnowledgeMemoryV1)
def deposit_historical_report(work_id: str, job_id: str):
    """Resume knowledge projection from an archived report without rerunning research."""
    from app.services import deep_research_mvp

    report = knowledge_memory_v4.get_report(work_id, job_id)
    if report is None:
        raise HTTPException(404, "Knowledge report not found")
    job = deep_research_mvp.get(job_id)
    if job.work.work_id != work_id:
        raise HTTPException(409, "Archived report does not belong to this work")
    job = deep_research_mvp.review_report_memory(job_id, "approve")
    memory = knowledge_memory_v4.get_current(work_id, job.brief.media_version)
    if memory is None or memory.source_job_id != job_id:
        raise HTTPException(500, "Knowledge publication completed without a matching version")
    return memory


@router.get("/works/{work_id}/versions/{version}", response_model=KnowledgeMemoryV1)
def version(work_id: str, version: str):
    memory = knowledge_memory_v4.get_version(work_id, version)
    if memory is None:
        raise HTTPException(404, "Knowledge memory version not found")
    return memory


@router.get("/works/{work_id}/domains/{domain}")
def domain(work_id: str, domain: str, media_version: str | None = None):
    return knowledge_memory_v4.get_domain_knowledge(work_id, domain, media_version)
