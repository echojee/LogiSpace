from fastapi import APIRouter, HTTPException

from app.services import research_v4_agent
from app.services.source_routing_v4 import (
    PACKS,
    PACK_VERSION,
    REGISTRY,
    REGISTRY_VERSION,
    build_funnel,
)

router = APIRouter()


@router.get("/source-registry")
def source_registry():
    return {
        "version": REGISTRY_VERSION,
        "entries": list(REGISTRY.values()),
    }


@router.get("/source-packs")
def source_packs():
    return {
        "version": PACK_VERSION,
        "packs": list(PACKS.values()),
    }


@router.get("/jobs/{job_id}/search-funnels")
def search_funnels(job_id: str):
    job = research_v4_agent.get(job_id)
    if job.plan is None or not job.plan.approved:
        raise HTTPException(409, "Approve the Supervisor plan before building search funnels")
    return {
        "job_id": job.job_id,
        "registry_version": REGISTRY_VERSION,
        "pack_version": PACK_VERSION,
        "funnels": [build_funnel(job.work, unit) for unit in job.plan.units],
    }
