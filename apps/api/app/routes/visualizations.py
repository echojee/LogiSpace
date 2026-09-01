from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.visualization_skills import generate
from logispace_domain.models_memory import VisualizationResultV1

router = APIRouter()


class VisualizationRequest(BaseModel):
    visualization_type: Literal["character_relationship", "timeline"]
    media_version: str | None = None
    knowledge_version: str = "current"


@router.post("/works/{work_id}/visualizations", response_model=VisualizationResultV1)
def create_visualization(work_id: str, request: VisualizationRequest):
    return generate(work_id, request.visualization_type, request.media_version, request.knowledge_version)
