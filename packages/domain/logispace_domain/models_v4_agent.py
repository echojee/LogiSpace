from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentActionDecisionV4(BaseModel):
    action: Literal["search_domains", "fetch_page", "find_in_source", "submit_findings", "stop"]
    parameters: dict[str, Any] = Field(default_factory=dict)
    decision_summary: str = Field(min_length=1, max_length=500)


class AgentActionV4(BaseModel):
    sequence: int = Field(ge=1)
    action: str
    parameters: dict[str, Any]
    result_summary: str
    decision_summary: str
    cost: dict[str, int] = Field(default_factory=dict)
    fingerprint: str


class SourceCandidateV4(BaseModel):
    url: str
    title: str
    domain: str
    provider: str
    research_value: float = Field(ge=0, le=1)
    evidence_authority: float = Field(ge=0, le=1)


class EvidenceCandidateV4(BaseModel):
    candidate_id: str
    snapshot_id: str
    source_url: str
    quote: str = Field(min_length=1)
    locator: dict[str, Any]
    proposed_relevance: str
    media_version: str


class SearchUsageV4(BaseModel):
    steps: int = 0
    queries: int = 0
    pages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class FindingBundleV4(BaseModel):
    research_unit_id: str
    summary: str
    source_candidates: list[SourceCandidateV4] = Field(default_factory=list)
    snapshot_ids: list[str] = Field(default_factory=list)
    evidence_candidates: list[EvidenceCandidateV4] = Field(default_factory=list)
    counterevidence_candidates: list[EvidenceCandidateV4] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    queries_executed: list[str] = Field(default_factory=list)
    urls_rejected: list[dict[str, str]] = Field(default_factory=list)
    stop_reason: Literal[
        "evidence_requirement_met", "no_novelty", "duplicate_loop", "inaccessible",
        "human_version_review", "budget_exhausted", "agent_stopped", "failed"
    ]
    usage: SearchUsageV4
    actions: list[AgentActionV4]
