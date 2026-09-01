from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from logispace_domain.models_v4_projection import CaseFileV4
from logispace_domain.models_v4_verified import VerifiedKnowledgeSnapshotV4


class KnowledgeMemoryV1(BaseModel):
    """An immutable, reusable knowledge version created by deep research."""

    work_id: str
    media_version: str
    knowledge_version: str
    source_job_id: str | None = None
    verified_knowledge: VerifiedKnowledgeSnapshotV4
    case_file: CaseFileV4
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserMemoryV1(BaseModel):
    """Stable preferences for the local single-user MVP."""

    profile_id: Literal["local_default"] = "local_default"
    language: str = "zh-CN"
    spoiler_level: Literal["none", "light", "full"] = "full"
    research_depth: Literal["compact", "standard", "extended"] = "standard"
    preferred_media_version: str = "original_novel"
    preferred_analysis_dimensions: list[str] = Field(default_factory=list)
    visualization_preference: Literal["mermaid"] = "mermaid"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RelationshipEdgeViewV1(BaseModel):
    source_id: str
    source_label: str
    relation: str
    target_id: str
    target_label: str
    source_entity_id: str
    source_claim_ids: list[str]


class RelationshipNodeViewV1(BaseModel):
    character_id: str
    label: str
    summary: str = ""
    source_entity_id: str
    source_claim_ids: list[str] = Field(default_factory=list)


class TimelineEventViewV1(BaseModel):
    event_id: str
    title: str
    summary: str = ""
    order: int
    track: str = "objective"
    time_label: str = ""
    source_entity_id: str
    source_claim_ids: list[str]


class VisualizationResultV1(BaseModel):
    visualization_id: str
    visualization_type: Literal["character_relationship", "timeline"]
    format: Literal["mermaid"] = "mermaid"
    title: str
    work_id: str
    media_version: str
    knowledge_version: str
    mermaid: str
    relationship_nodes: list[RelationshipNodeViewV1] = Field(default_factory=list)
    relationship_edges: list[RelationshipEdgeViewV1] = Field(default_factory=list)
    timeline_events: list[TimelineEventViewV1] = Field(default_factory=list)
    timeline_scale: Literal["ordinal", "year", "date", "time", "custom"] = "ordinal"
    timeline_tracks: dict[str, str] = Field(default_factory=dict)
    source_entity_ids: list[str] = Field(default_factory=list)
    source_claim_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
