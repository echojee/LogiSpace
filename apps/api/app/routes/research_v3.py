from fastapi import APIRouter,HTTPException,status
from fastapi.responses import StreamingResponse
import json
from app.services import research_repository as repo
from app.services import research_v3 as service
from logispace_domain.models_v3 import JobV3,PlanApprovalV3,ResearchJobCreateV3,ResearchPlanV3,ReviewV3
router=APIRouter()
@router.post("",response_model=JobV3,status_code=status.HTTP_202_ACCEPTED)
def create(request:ResearchJobCreateV3):return service.create(request)
@router.get("")
def list_items():return repo.list_jobs()
@router.get("/{job_id}",response_model=JobV3)
def get(job_id:str):return service.get(job_id)
@router.get("/{job_id}/events")
def events(job_id:str):
 service.get(job_id)
 def stream():
  for event in repo.events(job_id):yield f"event: progress\ndata: {json.dumps(event)}\n\n"
 return StreamingResponse(stream(),media_type="text/event-stream")
@router.get("/{job_id}/plan",response_model=ResearchPlanV3)
def plan(job_id:str):
 p=service.get(job_id).plan
 if not p:raise HTTPException(404,"Plan not generated")
 return p
@router.post("/{job_id}/plan/approve",response_model=JobV3)
def approve(job_id:str,request:PlanApprovalV3):return service.approve(job_id,request)
@router.get("/{job_id}/coverage")
def coverage(job_id:str):return service.get(job_id).coverage
@router.get("/{job_id}/sources")
def sources(job_id:str):return service.get(job_id).sources
@router.get("/{job_id}/evidence")
def evidence(job_id:str):return service.get(job_id).evidence
@router.get("/{job_id}/claims")
def claims(job_id:str):return service.get(job_id).claims
@router.get("/{job_id}/proposals")
def proposals(job_id:str):return service.get(job_id).proposals
@router.get("/{job_id}/report")
def report(job_id:str):
 j=service.get(job_id)
 if not j.report:raise HTTPException(404,"Report not generated")
 return j.report
@router.get("/{job_id}/knowledge-package")
def knowledge_package(job_id:str):
 j=service.get(job_id)
 if not j.knowledge_package:raise HTTPException(404,"Knowledge package not generated")
 return j.knowledge_package
@router.get("/{job_id}/draft")
def draft(job_id:str):
 j=service.get(job_id);return {"dossier":j.draft,"diff":j.diff}
@router.post("/{job_id}/review",response_model=JobV3)
def review(job_id:str,request:ReviewV3):return service.review(job_id,request)
@router.post("/{job_id}/publish",response_model=JobV3)
def publish(job_id:str):return service.publish(job_id)
@router.post("/{job_id}/pause",response_model=JobV3)
def pause(job_id:str):
 j=service.get(job_id)
 if j.status in {"published","failed","cancelled"}:raise HTTPException(409,"Terminal job cannot be paused")
 j.status="paused";repo.save(j,"Paused by user");return j
@router.post("/{job_id}/resume",response_model=JobV3)
def resume(job_id:str):
 j=service.get(job_id)
 if j.status!="paused":raise HTTPException(409,"Job is not paused")
 j.status="searching";repo.save(j,"Resumed from checkpoint");service._dispatch(job_id);return j
@router.post("/{job_id}/cancel",response_model=JobV3)
def cancel(job_id:str):
 j=service.get(job_id);j.status="cancelled";repo.save(j,"Cancelled by user");return j
@router.post("/{job_id}/retry",response_model=JobV3)
def retry(job_id:str):
 j=service.get(job_id)
 if j.status not in {"failed","partially_completed","budget_exhausted"}:raise HTTPException(409,"Job cannot be retried")
 j.status="retrying";repo.save(j,"Retrying from checkpoint");service._dispatch(job_id);return j
