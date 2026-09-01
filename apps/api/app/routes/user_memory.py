from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import user_memory
from logispace_domain.models_memory import UserMemoryV1

router = APIRouter()


class UserMemoryUpdate(BaseModel):
    language: str | None = None
    spoiler_level: Literal["none", "light", "full"] | None = None
    research_depth: Literal["compact", "standard", "extended"] | None = None
    preferred_media_version: str | None = None
    preferred_analysis_dimensions: list[str] | None = None
    visualization_preference: Literal["mermaid"] | None = None


@router.get("", response_model=UserMemoryV1)
def get_memory():
    return user_memory.get()


@router.patch("", response_model=UserMemoryV1)
def update_memory(request: UserMemoryUpdate):
    return user_memory.update(request.model_dump(exclude_none=True))


@router.delete("", response_model=UserMemoryV1)
def clear_memory():
    return user_memory.clear()
