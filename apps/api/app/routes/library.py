from fastapi import APIRouter, HTTPException

from app.services.search import relationship_view, timeline_view
from app.services.published_knowledge import knowledge_package, report
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
    package=knowledge_package(work_id);dossier=get_dossier(work_id)
    if package and dossier:
        nodes=[{"entity_id":x.entity_id,"entity_type":"Character","name":x.name,"summary":x.summary,"attributes":{"aliases":x.aliases}} for x in package.characters];names={x.entity_id:x.name for x in package.characters};edges=[x.model_dump()|{"relation":x.relation_type,"note":x.summary,"source_name":names.get(x.source_id,x.source_id),"target_name":names.get(x.target_id,x.target_id)} for x in package.relationships];return {"work":dossier.work.model_dump(),"nodes":nodes,"edges":edges}
    result = relationship_view(work_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown work")
    return result


@router.get("/works/{work_id}/timeline")
def get_timeline(work_id: str) -> dict:
    package=knowledge_package(work_id);dossier=get_dossier(work_id)
    if package and dossier:
        items=[{"entity_id":x.event_id,"entity_type":"Event","name":x.title,"summary":x.summary,"attributes":{"track":x.track,"order":x.order,"participants":x.participant_ids,"claim_ids":x.claim_ids}} for x in package.timeline];return {"work":dossier.work.model_dump(),"items":items}
    result = timeline_view(work_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown work")
    return result


@router.get("/tricks")
def list_tricks() -> list[dict]:
    result=[]
    for dossier in all_dossiers():
        package=knowledge_package(dossier.work.work_id)
        if package:result.extend({"work_id":dossier.work.work_id,"work_title":dossier.work.canonical_title,"entity_id":item.trick_id,"name":item.name,"summary":item.mechanism,"attributes":{"trick_type":item.trick_type},"claim_ids":item.claim_ids,"evidence_ids":item.evidence_ids} for item in package.tricks)
        else:result.extend({"work_id":dossier.work.work_id,"work_title":dossier.work.canonical_title,**entity.model_dump()} for entity in dossier.entities if entity.entity_type=="Trick")
    return result


@router.get("/methods")
def list_methods() -> list[dict]:
    result=[]
    for dossier in all_dossiers():
        package=knowledge_package(dossier.work.work_id)
        if package:result.extend({"work_id":dossier.work.work_id,"work_title":dossier.work.canonical_title,"entity_id":item.method_id,"name":item.name,"summary":item.execution,"attributes":{"method_type":item.method_type},"claim_ids":item.claim_ids,"evidence_ids":item.evidence_ids} for item in package.murder_methods)
        else:result.extend({"work_id":dossier.work.work_id,"work_title":dossier.work.canonical_title,**entity.model_dump()} for entity in dossier.entities if entity.entity_type=="MurderMethod")
    return result

@router.get("/works/{work_id}/report")
def get_report(work_id:str):
    value=report(work_id)
    if value is None:raise HTTPException(status_code=404,detail="Published report not found")
    return value