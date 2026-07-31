from __future__ import annotations

import re
import unicodedata
from uuid import uuid4

from fastapi import HTTPException

from app.services.runtime_store import JsonStore
from logispace_domain import dossiers as dossier_repository
from logispace_domain.models import MediaType, Work, WorkConfirmRequest, WorkResolveRequest, WorkResolveResponse

_store = JsonStore("work_resolutions")


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"[\s《》〈〉『』「」·:：_\-]+", "", value)


def _new_work_id(title: str, media_type: MediaType) -> str:
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()).strip("-")
    return f"{ascii_slug or 'work'}-{media_type.value}-{uuid4().hex[:8]}"


def resolve(request: WorkResolveRequest) -> WorkResolveResponse:
    title = request.query.strip()
    media_type = request.media_type or MediaType.UNKNOWN
    matches: list[Work] = []
    needle = _normalized(title)
    for dossier in dossier_repository.all_dossiers():
        work = dossier.work
        names = [work.canonical_title, *work.aliases]
        if needle in {_normalized(name) for name in names} and media_type in {MediaType.UNKNOWN, work.media_type}:
            matches.append(work)

    # External providers can append candidates here. Until configured, an unknown
    # title remains one provisional identity so author/year are never mandatory.
    if not matches:
        matches = [Work(work_id=_new_work_id(title, media_type), canonical_title=title, aliases=[title], media_type=media_type)]

    resolution_id = f"resolution_{uuid4().hex[:12]}"
    needs_confirmation = len(matches) > 1
    response = WorkResolveResponse(
        resolution_id=resolution_id,
        query=title,
        candidates=matches,
        needs_confirmation=needs_confirmation,
        resolved_work=None if needs_confirmation else matches[0],
    )
    _store.save(resolution_id, response)
    return response


def confirm(resolution_id: str, request: WorkConfirmRequest) -> WorkResolveResponse:
    resolution = _store.load(resolution_id, WorkResolveResponse)
    if resolution is None:
        raise HTTPException(status_code=404, detail="Work resolution not found")
    selected = next((candidate for candidate in resolution.candidates if candidate.work_id == request.work_id), None)
    if selected is None:
        raise HTTPException(status_code=422, detail="Candidate does not belong to this resolution")
    resolution.needs_confirmation = False
    resolution.resolved_work = selected
    _store.save(resolution_id, resolution)
    return resolution
