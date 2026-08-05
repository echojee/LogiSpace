from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ClaimCandidateV4(BaseModel):
    claim_id: str
    research_unit_id: str
    text: str = Field(min_length=1)
    claim_type: Literal["fact", "inference", "interpretation", "conflict", "unknown"]
    evidence_candidate_ids: list[str] = Field(default_factory=list)
    domain: str
    media_version: str
    high_risk: bool = False


class DomainObjectCandidateV4(BaseModel):
    object_id: str
    object_type: Literal["relationship", "timeline_alignment", "trick", "murder_method"]
    payload: dict[str, Any]
    claim_ids: list[str] = Field(min_length=1)


class CuratedBatchV4(BaseModel):
    research_unit_id: str
    claims: list[ClaimCandidateV4]
    domain_objects: list[DomainObjectCandidateV4] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class VerificationIssueV4(BaseModel):
    code: Literal[
        "missing_snapshot", "quote_mismatch", "invalid_locator", "version_mismatch",
        "missing_evidence", "insufficient_independence", "semantic_overreach",
        "counterevidence", "invalid_entity_reference", "schema_error"
    ]
    detail: str


class VerificationResultV4(BaseModel):
    claim_id: str
    status: Literal["supported", "partially_supported", "inferred", "interpretive", "conflicted", "unsupported"]
    valid_evidence_ids: list[str] = Field(default_factory=list)
    rejected_evidence_ids: list[str] = Field(default_factory=list)
    issues: list[VerificationIssueV4] = Field(default_factory=list)
    reason: str
    suggested_followups: list[str] = Field(default_factory=list)
