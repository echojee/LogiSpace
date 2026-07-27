from fastapi import APIRouter

from logispace_domain.models import MediaType, Work, WorkResolveRequest, WorkResolveResponse

router = APIRouter()


@router.post("/resolve", response_model=WorkResolveResponse)
def resolve_work(request: WorkResolveRequest) -> WorkResolveResponse:
    candidate = Work(
        work_id="work_mock_001",
        canonical_title=request.query.strip(),
        aliases=[request.query.strip()],
        media_type=request.media_type or MediaType.UNKNOWN,
        release_year=None,
        creators=[],
    )
    return WorkResolveResponse(query=request.query, candidates=[candidate], needs_confirmation=True)
