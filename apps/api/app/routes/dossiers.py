from fastapi import APIRouter
from app.services.closure import answer_golden_question, build_product_views, ontology_revision_summary, require_dossier
from logispace_domain.dossiers import all_dossiers
from logispace_domain.models import ProductView, QARequest, QAResponse, WorkDossier

router = APIRouter()


@router.get("", response_model=list[WorkDossier])
def list_dossiers() -> list[WorkDossier]:
    return all_dossiers()


@router.get("/ontology/revision")
def get_ontology_revision() -> dict:
    return ontology_revision_summary()


@router.post("/qa", response_model=QAResponse)
def run_golden_qa(request: QARequest) -> QAResponse:
    return answer_golden_question(request.question_id, request.source_work_ids)


@router.get("/{work_id}", response_model=WorkDossier)
def read_dossier(work_id: str) -> WorkDossier:
    return require_dossier(work_id)


@router.get("/{work_id}/views", response_model=list[ProductView])
def read_product_views(work_id: str) -> list[ProductView]:
    return build_product_views(work_id)
