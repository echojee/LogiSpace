from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from logispace_domain.models import SpoilerLevel, Work

MandatoryDomain = Literal["relationships", "multiple_timelines", "tricks", "murder_methods"]
CoverageStatusV4 = Literal["sufficient", "needs_update", "missing", "conflicted", "not_applicable"]
ResearchStrategyV4 = Literal["build_and_verify", "review_strengthen_and_correct"]


class ResearchBriefV4(BaseModel):
    work_id: str
    media_version: str = "original_novel"
    user_goal: str = "全面理解作品的诡计结构"
    audience: str = "已读完原著的推理爱好者"
    spoiler_level: SpoilerLevel = SpoilerLevel.FULL
    output_mode: Literal["case_file", "knowledge", "case_file_and_knowledge"] = "case_file_and_knowledge"
    budget_profile: Literal["compact", "standard", "extended"] = "standard"
    allowed_source_scope: str = "bilingual_mystery_default"


class EvidenceRequirementV4(BaseModel):
    requires_primary_source: bool = False
    minimum_independent_sources: int = Field(default=1, ge=1, le=5)
    requires_counterevidence_search: bool = False


class UnitBudgetV4(BaseModel):
    max_steps: int = Field(default=6, ge=1, le=20)
    max_queries: int = Field(default=3, ge=1, le=10)
    max_pages: int = Field(default=5, ge=1, le=20)


class ResearchUnitV4(BaseModel):
    unit_id: str
    track: Literal["mandatory", "signature"]
    domain: str
    question: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    required_outputs: list[str] = Field(min_length=1)
    evidence_requirements: EvidenceRequirementV4
    budget: UnitBudgetV4
    done_when: list[str] = Field(min_length=1)
    priority: int = Field(default=3, ge=1, le=5)
    status: Literal["planned", "approved", "completed", "unobtainable"] = "planned"


class CoverageDecisionV4(BaseModel):
    domain: MandatoryDomain
    status: CoverageStatusV4
    reason: str = Field(min_length=1)
    existing_object_ids: list[str] = Field(default_factory=list)


class ResearchBudgetV4(BaseModel):
    mandatory_reserve: dict[MandatoryDomain, int] = Field(default_factory=lambda: {
        "relationships": 2,
        "multiple_timelines": 3,
        "tricks": 3,
        "murder_methods": 2,
    })
    signature_flexible_queries: int = Field(default=8, ge=0, le=30)
    verification_reserve_ratio: float = Field(default=0.2, ge=0.1, le=0.5)

    @model_validator(mode="after")
    def validate_reserves(self):
        required = {"relationships", "multiple_timelines", "tricks", "murder_methods"}
        if set(self.mandatory_reserve) != required:
            raise ValueError("mandatory_reserve must contain exactly the four mandatory domains")
        if any(value < 1 for value in self.mandatory_reserve.values()):
            raise ValueError("mandatory research budgets cannot be removed")
        return self


class ResearchPlanRevisionV4(BaseModel):
    revision: int = Field(default=1, ge=1)
    coverage: list[CoverageDecisionV4]
    units: list[ResearchUnitV4]
    budget: ResearchBudgetV4 = Field(default_factory=ResearchBudgetV4)
    rationale: str
    approved: bool = False
    selected_unit_ids: list[str] = Field(default_factory=list)
    strategy: ResearchStrategyV4 = "build_and_verify"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_mandatory_track(self):
        required = {"relationships", "multiple_timelines", "tricks", "murder_methods"}
        if {item.domain for item in self.coverage} != required:
            raise ValueError("coverage must decide all four mandatory domains exactly once")
        planned = {item.domain for item in self.units if item.track == "mandatory"}
        if planned != required:
            raise ValueError("plan must include a ResearchUnit for every mandatory domain")
        return self


class ResearchJobCreateV4(BaseModel):
    work_id: str | None = None
    work: Work | None = None
    brief: ResearchBriefV4 | None = None
    budget: ResearchBudgetV4 = Field(default_factory=ResearchBudgetV4)


class PlanApprovalV4(BaseModel):
    units: list[ResearchUnitV4] | None = None
    selected_unit_ids: list[str] | None = None


class ResearchJobV4(BaseModel):
    job_id: str
    work: Work
    status: Literal["supervisor_planning", "awaiting_plan_approval", "searching", "cancelled"]
    brief: ResearchBriefV4
    plan: ResearchPlanRevisionV4 | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
