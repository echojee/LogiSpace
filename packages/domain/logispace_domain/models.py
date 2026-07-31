from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class MediaType(str, Enum):
    NOVEL = "novel"
    FILM = "film"
    SERIES = "series"
    GAME = "game"
    MANGA = "manga"
    UNKNOWN = "unknown"


class SpoilerLevel(str, Enum):
    NONE = "none"
    LIGHT = "light"
    FULL = "full"


class SupportStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    INFERRED = "inferred"


class ResearchJobStatus(str, Enum):
    IDENTIFY = "identify"
    PLAN = "plan"
    COLLECT = "collect"
    CLEAN = "clean"
    EXTRACT = "extract"
    NORMALIZE = "normalize"
    MAP = "map"
    WRITE = "write"
    VERIFY = "verify"
    PUBLISHED = "published"
    FAILED = "failed"


class Work(BaseModel):
    work_id: str
    canonical_title: str
    aliases: list[str] = Field(default_factory=list)
    media_type: MediaType = MediaType.UNKNOWN
    release_year: int | None = None
    creators: list[str] = Field(default_factory=list)


class WorkResolveRequest(BaseModel):
    query: str = Field(min_length=1)
    media_type: MediaType | None = None


class WorkResolveResponse(BaseModel):
    resolution_id: str
    query: str
    candidates: list[Work]
    needs_confirmation: bool
    resolved_work: Work | None = None


class WorkConfirmRequest(BaseModel):
    work_id: str


class SourceDocument(BaseModel):
    source_id: str
    url: HttpUrl | str
    title: str
    author: str | None = None
    published_at: datetime | None = None
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    source_type: str
    credibility: float = Field(ge=0, le=1)
    captured_text: str


class EvidenceItem(BaseModel):
    evidence_id: str
    source_id: str
    locator: str
    quote: str
    ontology_type: str
    entities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class Claim(BaseModel):
    claim_id: str
    section: str
    text: str
    importance: int = Field(ge=1, le=5)
    spoiler_level: SpoilerLevel
    evidence_ids: list[str] = Field(default_factory=list)
    support_status: SupportStatus


class ReportSection(BaseModel):
    title: str
    spoiler_level: SpoilerLevel
    claims: list[Claim] = Field(default_factory=list)
    body: str | None = None


class ReportVersion(BaseModel):
    report_id: str
    work_id: str
    schema_version: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    sections: list[ReportSection]
    quality_score: float | None = Field(default=None, ge=0, le=1)
    revision_notes: list[str] = Field(default_factory=list)


class ResearchStep(BaseModel):
    name: ResearchJobStatus
    status: str
    detail: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class ResearchJobCreate(BaseModel):
    work_id: str
    requested_by: str
    spoiler_level: SpoilerLevel = SpoilerLevel.NONE
    report_schema_version: str = "0.1"
    budget: dict[str, Any] = Field(default_factory=dict)


class ResearchJobSnapshot(BaseModel):
    job_id: str
    work_id: str
    status: ResearchJobStatus
    steps: list[ResearchStep] = Field(default_factory=list)
    sources: list[SourceDocument] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class UserWorkState(BaseModel):
    user_id: str
    work_id: str
    state: str = Field(pattern="^(watched|want|dropped|unknown)$")
    rating: int | None = Field(default=None, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    spoiler_level_allowed: SpoilerLevel = SpoilerLevel.NONE


class DossierEntity(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    summary: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class DossierRelation(BaseModel):
    source_id: str
    relation: str
    target_id: str
    note: str | None = None


class GoldenQuestion(BaseModel):
    question_id: str
    question: str
    expected_answer: str
    answer_entity_ids: list[str] = Field(default_factory=list)
    required_relation: str | None = None
    difficulty: str = "medium"
    tags: list[str] = Field(default_factory=list)


class WorkDossier(BaseModel):
    work: Work
    schema_version: str = "0.2"
    dossier_version: str = "0.1.0"
    ontology_version: str = "0.2.0"
    dataset_role: str = "primary"
    entities: list[DossierEntity]
    relations: list[DossierRelation]
    golden_questions: list[GoldenQuestion]
    revision_findings: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    citation_id: str
    label: str
    url: str | None = None
    source_type: str = "work_dossier"
    work_id: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    excerpt: str | None = None


class ConversationMemory(BaseModel):
    active_work_ids: list[str] = Field(default_factory=list)
    active_entities: list[str] = Field(default_factory=list)
    current_topic: str | None = None
    summary: str = ""
    spoiler_level: SpoilerLevel = SpoilerLevel.NONE


class ConversationMessage(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(BaseModel):
    conversation_id: str
    title: str = "New conversation"
    memory: ConversationMemory = Field(default_factory=ConversationMemory)
    messages: list[ConversationMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationCreate(BaseModel):
    spoiler_level: SpoilerLevel = SpoilerLevel.NONE
    active_work_ids: list[str] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    content: str = Field(min_length=1)
    allow_web_search: bool = True
    spoiler_level: SpoilerLevel | None = None


class ConversationAnswer(BaseModel):
    conversation_id: str
    message: ConversationMessage
    answer_status: Literal["supported", "partial", "inferred", "conflicted", "insufficient"]
    used_work_ids: list[str] = Field(default_factory=list)
    used_web_search: bool = False
    suggest_deep_research: bool = False
    memory: ConversationMemory


class ResearchBudget(BaseModel):
    max_search_rounds: int = Field(default=8, ge=1, le=30)
    max_sources: int = Field(default=30, ge=1, le=100)
    max_model_tokens: int = Field(default=200_000, ge=1_000)


class ResearchCoverage(BaseModel):
    section: str
    status: Literal["not_started", "in_progress", "sufficient", "partial", "not_applicable", "conflicted"]
    knowledge_gaps: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)


class ResearchJobV2Create(BaseModel):
    work_id: str
    media_scope: str = "novel"
    research_scope: Literal["incremental_full", "fill_gaps", "resolve_conflicts", "full_rebuild"] = "incremental_full"
    spoiler_level: SpoilerLevel = SpoilerLevel.FULL
    budget: ResearchBudget = Field(default_factory=ResearchBudget)


class KnowledgeProposal(BaseModel):
    proposal_id: str
    operation: Literal["retain", "strengthen", "add_entity", "add_relation", "add_claim", "flag_conflict"]
    target_section: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    review_status: Literal["pending", "approved", "rejected"] = "pending"


class ResearchUsage(BaseModel):
    search_rounds: int = 0
    sources: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class ResearchJobV2(BaseModel):
    job_id: str
    work_id: str
    media_scope: str
    research_scope: str
    base_version: str
    target_version: str
    status: Literal["created", "inventorying", "planning", "collecting", "extracting", "verifying", "drafting", "quality_check", "needs_review", "published", "failed"] = "created"
    budget: ResearchBudget
    usage: ResearchUsage = Field(default_factory=ResearchUsage)
    coverage: list[ResearchCoverage] = Field(default_factory=list)
    sources: list[SourceDocument] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    proposals: list[KnowledgeProposal] = Field(default_factory=list)
    draft: WorkDossier | None = None
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProposalReview(BaseModel):
    approved_proposal_ids: list[str] = Field(default_factory=list)
    rejected_proposal_ids: list[str] = Field(default_factory=list)



class ProductView(BaseModel):
    view_type: str
    work_id: str
    title: str
    payload: dict[str, Any]


class QARequest(BaseModel):
    question_id: str
    source_work_ids: list[str] = Field(min_length=1)


class QAResponse(BaseModel):
    question_id: str
    source_work_ids: list[str]
    answer: str
    evidence_entity_ids: list[str]
    passed: bool
