from fastapi import APIRouter, HTTPException

from app.services.search import relationship_view, timeline_view
from logispace_domain.dossiers import all_dossiers, get_dossier

router = APIRouter()


@router.get("/works")
def list_works() -> list[dict]:
    return [{"work": dossier.work.model_dump(), "dossier_version": dossier.dossier_version, "entity_count": len(dossier.entities)} for dossier in all_dossiers()]


@router.get("/works/{work_id}")
def get_work(work_id: str) -> dict:
    dossier = get_dossier(work_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Unknown work")
    return {"work": dossier.work.model_dump(), "dossier_version": dossier.dossier_version, "entity_counts": {kind: len([item for item in dossier.entities if item.entity_type == kind]) for kind in sorted({item.entity_type for item in dossier.entities})}}


@router.get("/works/{work_id}/relationships")
def get_relationships(work_id: str) -> dict:
    result = relationship_view(work_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown work")
    return result


@router.get("/works/{work_id}/timeline")
def get_timeline(work_id: str) -> dict:
    result = timeline_view(work_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown work")
    return result


@router.get("/tricks")
def list_tricks() -> list[dict]:
    return [{"work_id": dossier.work.work_id, "work_title": dossier.work.canonical_title, **entity.model_dump()} for dossier in all_dossiers() for entity in dossier.entities if entity.entity_type == "Trick"]


@router.get("/methods")
def list_methods() -> list[dict]:
    return [{"work_id": dossier.work.work_id, "work_title": dossier.work.canonical_title, **entity.model_dump()} for dossier in all_dossiers() for entity in dossier.entities if entity.entity_type == "MurderMethod"]