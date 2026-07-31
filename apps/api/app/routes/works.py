from fastapi import APIRouter

from app.services.work_resolution import confirm, resolve
from logispace_domain.models import WorkConfirmRequest, WorkResolveRequest, WorkResolveResponse

router = APIRouter()


@router.post("/resolve", response_model=WorkResolveResponse)
def resolve_work(request: WorkResolveRequest) -> WorkResolveResponse:
    return resolve(request)


@router.post("/resolve/{resolution_id}/confirm", response_model=WorkResolveResponse)
def confirm_work(resolution_id: str, request: WorkConfirmRequest) -> WorkResolveResponse:
    return confirm(resolution_id, request)
