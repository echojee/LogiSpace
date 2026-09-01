from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, model_validator

from logispace_domain.models_v4 import ResearchStrategyV4, ResearchUnitV4
from logispace_domain.models_v4_storm import ResearchOutlineV4, ResearchPerspectiveV4, ResearchTurnV4


class ReconSourceV4(BaseModel):
    title: str
    url: str
    role: str = "discovery"


class ReconnaissanceBriefV4(BaseModel):
    summary: str = Field(max_length=1200)
    edition_scope: str = Field(max_length=300)
    structure_signals: list[str] = Field(default_factory=list, max_length=4)
    candidate_features: list[str] = Field(default_factory=list, min_length=1, max_length=4)
    primary_text_options: list[str] = Field(default_factory=list, max_length=2)
    location_strategy: str = Field(default="chapter_or_stable_text_anchor", max_length=300)
    contamination_risks: list[str] = Field(default_factory=list, max_length=2)
    open_questions: list[str] = Field(default_factory=list, max_length=3)
    sources: list[ReconSourceV4] = Field(default_factory=list, max_length=5)
    model: str = ""
    prompt_version: str = "reconnaissance-v0.5.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PerspectiveSetV4(BaseModel):
    """Compatibility view of the STORM perspective stage."""

    perspectives: list[ResearchPerspectiveV4] = Field(min_length=2, max_length=2)
    status: Literal["generated"] = "generated"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanMemoV4(BaseModel):
    title: str
    objective: str
    scope: str
    reconnaissance_summary: str
    mandatory_units: list[ResearchUnitV4] = Field(min_length=4, max_length=4)
    signature_units: list[ResearchUnitV4] = Field(min_length=1, max_length=3)
    perspectives: list[ResearchPerspectiveV4] = Field(default_factory=list)
    research_turns: list[ResearchTurnV4] = Field(default_factory=list)
    direct_outline: ResearchOutlineV4 | None = None
    research_outline: ResearchOutlineV4 | None = None
    risks: list[str] = Field(default_factory=list)
    strategy: ResearchStrategyV4 = "build_and_verify"
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_mandatory_outline(self):
        required = {"relationships", "multiple_timelines", "tricks", "murder_methods"}
        domains = {unit.domain for unit in self.mandatory_units if unit.track == "mandatory"}
        if domains != required:
            raise ValueError("plan memo must visibly include all four mandatory research domains")
        return self


class PlanMemoUpdateV4(BaseModel):
    title: str
    objective: str
    scope: str
    reconnaissance_summary: str
    signature_units: list[ResearchUnitV4] = Field(min_length=1, max_length=3)
    risks: list[str] = Field(default_factory=list)


class SearchSessionV4(BaseModel):
    queries: list[str] = Field(default_factory=list)
    query_units: dict[str, list[str]] = Field(default_factory=dict)
    sources: dict[str, dict] = Field(default_factory=dict)
    snapshots: dict[str, str] = Field(default_factory=dict)
    snapshot_urls: dict[str, str] = Field(default_factory=dict)
    cache_hits: int = 0
    duplicate_queries_avoided: int = 0
