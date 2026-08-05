from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DossierBlockV4(BaseModel):
    block_id: str
    layer: Literal["one_minute", "core", "appendix"]
    block_type: Literal["summary", "analysis", "timeline", "relationships", "trick", "murder_method", "conflicts", "unknowns", "sources"]
    title: str
    text: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class CaseFileV4(BaseModel):
    case_file_id: str
    work_id: str
    media_version: str
    title: str
    research_mainline: str
    reliability_note: str
    blocks: list[DossierBlockV4]


class ProjectionAuditV4(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)


class KnowledgeProposalV4(BaseModel):
    proposal_id: str
    operation: Literal[
        "add_entity", "add_relation", "add_timeline_event", "add_timeline_alignment",
        "add_trick", "add_murder_method", "flag_conflict"
    ]
    target_section: str
    payload: dict[str, Any]
    claim_ids: list[str]
    evidence_ids: list[str]
    review_status: Literal["pending", "approved", "rejected"] = "pending"
