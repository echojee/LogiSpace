from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from logispace_domain.models import SpoilerLevel


StormStageV4 = Literal[
    "perspective", "research_dialogue", "outline",
    "search_and_draft", "polish", "deposit",
]


class ResearchPerspectiveV4(BaseModel):
    perspective_id: str
    title: str
    description: str
    starting_question: str
    focus_questions: list[str] = Field(default_factory=list)
    source_inspiration: list[str] = Field(default_factory=list)
    is_basic: bool = False
    model: str = ""
    prompt_version: str = ""


class ResearchTurnV4(BaseModel):
    turn_id: str
    perspective_id: str
    question: str
    research_intent: str
    suggested_queries: list[str] = Field(default_factory=list)
    provisional_answer: str
    unresolved_questions: list[str] = Field(default_factory=list)
    reconnaissance_source_urls: list[str] = Field(default_factory=list)
    status: Literal["continue", "complete", "stopped"]
    model: str
    prompt_version: str

    @model_validator(mode="after")
    def label_hypothesis(self):
        if not self.provisional_answer.startswith("待验证假设："):
            raise ValueError("provisional_answer must be explicitly labelled as an unverified hypothesis")
        return self


class OutlineNodeV4(BaseModel):
    section_id: str
    title: str
    purpose: str
    research_questions: list[str] = Field(default_factory=list)
    search_directions: list[str] = Field(default_factory=list)
    required_source_types: list[str] = Field(default_factory=list)
    expected_claims: list[str] = Field(default_factory=list)
    subsections: list["OutlineNodeV4"] = Field(default_factory=list)
    cross_section_dependencies: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    spoiler_level: SpoilerLevel = SpoilerLevel.FULL


class ResearchOutlineV4(BaseModel):
    outline_id: str
    kind: Literal["direct", "research"]
    title: str
    nodes: list[OutlineNodeV4] = Field(min_length=1)
    markdown: str
    prompt_version: str


class StormPlanningStateV4(BaseModel):
    perspectives: list[ResearchPerspectiveV4] = Field(min_length=2, max_length=2)
    research_turns: list[ResearchTurnV4] = Field(default_factory=list)
    direct_outline: ResearchOutlineV4
    research_outline: ResearchOutlineV4


class StageArtifactV4(BaseModel):
    artifact_id: str
    stage: StormStageV4
    schema_version: str = "v4-storm-1"
    status: Literal["valid", "stale", "failed"] = "valid"
    input_artifact_ids: list[str] = Field(default_factory=list)
    input_hash: str
    output_hash: str
    model: str
    model_parameters: dict[str, Any] = Field(default_factory=dict)
    prompt_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost: float | None = None
    error: str | None = None
    files: dict[str, str] = Field(default_factory=dict)


class StageRerunRequestV4(BaseModel):
    from_stage: StormStageV4
    target_stage: StormStageV4
    model_overrides: dict[str, str] = Field(default_factory=dict)
    force: bool = False


class StageStatusV4(BaseModel):
    stage: StormStageV4
    status: Literal["pending", "valid", "stale", "running", "failed", "awaiting_approval"]
    current_artifact_id: str | None = None

