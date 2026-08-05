from __future__ import annotations

from pydantic import BaseModel, Field


class ProposalReviewV4(BaseModel):
    approved_proposal_ids: list[str] = Field(default_factory=list)
    rejected_proposal_ids: list[str] = Field(default_factory=list)


class ResearchDeltaV4(BaseModel):
    work_id: str
    base_version: str
    target_version: str
    added_entities: list[str] = Field(default_factory=list)
    added_relations: list[str] = Field(default_factory=list)
    flagged_conflicts: list[str] = Field(default_factory=list)
    source_verified_knowledge_snapshot_id: str
