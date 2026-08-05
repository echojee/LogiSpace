from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class VerifiedClaimV4(BaseModel):
    claim_id: str
    text: str
    claim_type: str
    domain: str
    media_version: str
    support_status: Literal["supported", "partially_supported", "inferred", "interpretive", "conflicted"]
    evidence_ids: list[str]


class ClaimRelationV4(BaseModel):
    source_id: str
    relation: Literal["supports", "opposes", "depends_on", "contradicts", "about"]
    target_id: str


class VerifiedDomainObjectV4(BaseModel):
    object_id: str
    object_type: Literal["relationship", "timeline_alignment", "trick", "murder_method"]
    payload: dict[str, Any]
    claim_ids: list[str]


class GapStateV4(BaseModel):
    research_unit_id: str
    status: Literal["resolved", "needs_research", "conflicted", "unobtainable"]
    reasons: list[str] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)


class VerifiedKnowledgeSnapshotV4(BaseModel):
    snapshot_id: str
    work_id: str
    media_version: str
    claims: list[VerifiedClaimV4]
    domain_objects: list[VerifiedDomainObjectV4]
    claim_graph: list[ClaimRelationV4]
    conflicts: list[str]
    unknowns: list[str]
    gaps: list[GapStateV4]
    evidence_ids: list[str]
    frozen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
