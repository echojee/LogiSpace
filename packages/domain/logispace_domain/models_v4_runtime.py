from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from logispace_domain.models import Work
from logispace_domain.models_v4 import ResearchBriefV4, ResearchBudgetV4, ResearchPlanRevisionV4, ResearchStrategyV4
from logispace_domain.models_v4_agent import FindingBundleV4
from logispace_domain.models_v4_history import ResearchAttemptArchiveV4
from logispace_domain.models_v4_memo import PerspectiveSetV4, PlanMemoV4, ReconnaissanceBriefV4, SearchSessionV4
from logispace_domain.models_v4_knowledge import CuratedBatchV4, VerificationResultV4
from logispace_domain.models_v4_projection import CaseFileV4, KnowledgeProposalV4, ProjectionAuditV4
from logispace_domain.models_v4_verified import VerifiedKnowledgeSnapshotV4
from logispace_domain.models_v4_storm import StageArtifactV4, StormPlanningStateV4

RuntimeStatusV4 = Literal[
    "created", "researching", "completed", "reconnaissance_running", "perspective_generating", "supervisor_planning", "planning_failed",
    "awaiting_plan_approval", "searching", "curating", "verifying", "reflecting",
    "replanning", "knowledge_frozen", "writing", "auditing", "mapping", "needs_review",
    "depositing", "ready_to_publish", "published", "partially_completed",
    "budget_exhausted", "cancelled", "failed",
]


class ResearchReportCitationV4(BaseModel):
    title: str = ""
    url: str
    start_index: int | None = None
    end_index: int | None = None


class ResearchReportV4(BaseModel):
    title: str
    markdown: str
    citations: list[ResearchReportCitationV4] = Field(default_factory=list)
    prompt: str
    model: str
    provider_response_id: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    incomplete_reason: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanningFailureV4(BaseModel):
    stage: Literal["reconnaissance", "perspectives", "supervisor"]
    code: str
    message: str
    retryable: bool = True
    attempt: int = Field(default=1, ge=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UnitCheckpointV4(BaseModel):
    research_unit_id: str
    status: Literal["planned", "approved", "searching", "searched", "curated", "verified", "failed"]
    attempt: int = 0
    finding_bundle: FindingBundleV4 | None = None
    snapshots: dict[str, str] = Field(default_factory=dict)
    curated: CuratedBatchV4 | None = None
    verification_results: list[VerificationResultV4] = Field(default_factory=list)
    error: str | None = None


class ExecutionCheckpointV1(BaseModel):
    """Append-only record of one recoverable research stage attempt."""

    checkpoint_id: str
    job_id: str
    stage: Literal["planning", "reconnaissance", "perspectives", "plan_synthesis", "search", "search_and_draft", "curate", "verify", "freeze", "projection", "deposit"]
    unit_id: str | None = None
    status: Literal["started", "completed", "failed"]
    attempt: int = Field(default=1, ge=1)
    state_version: int = Field(default=0, ge=0)
    operation_key: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None


class ResearchRuntimeV4(BaseModel):
    job_id: str
    work: Work
    brief: ResearchBriefV4
    status: RuntimeStatusV4
    plan: ResearchPlanRevisionV4 | None = None
    units: dict[str, UnitCheckpointV4] = Field(default_factory=dict)
    strategy: ResearchStrategyV4 = "build_and_verify"
    planning_budget: ResearchBudgetV4 = Field(default_factory=ResearchBudgetV4)
    planning_attempt: int = 0
    planning_failure: PlanningFailureV4 | None = None
    verified_knowledge: VerifiedKnowledgeSnapshotV4 | None = None
    case_file: CaseFileV4 | None = None
    research_report: ResearchReportV4 | None = None
    provider_response_id: str | None = None
    report_memory_status: Literal["not_ready", "pending_approval", "deposited", "rejected"] = "not_ready"
    reconnaissance: ReconnaissanceBriefV4 | None = None
    perspective_set: PerspectiveSetV4 | None = None
    plan_memo: PlanMemoV4 | None = None
    storm_planning: StormPlanningStateV4 | None = None
    stage_artifacts: list[StageArtifactV4] = Field(default_factory=list)
    search_session: SearchSessionV4 = Field(default_factory=SearchSessionV4)
    attempt_history: list[ResearchAttemptArchiveV4] = Field(default_factory=list)
    proposals: list[KnowledgeProposalV4] = Field(default_factory=list)
    projection_audit: ProjectionAuditV4 | None = None
    errors: list[str] = Field(default_factory=list)
    published_version: str | None = None
    state_version: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def migrate_visible_mandatory_memo_units(cls, value):
        """Keep previously persisted v4 jobs readable after memo schema expansion."""
        if not isinstance(value, dict):
            return value
        memo = value.get("plan_memo")
        plan = value.get("plan")
        if value.get("research_report") is not None and "report_memory_status" not in value:
            value["report_memory_status"] = "pending_approval"
        if isinstance(memo, dict) and "mandatory_units" not in memo and isinstance(plan, dict):
            memo["mandatory_units"] = [
                unit for unit in plan.get("units", [])
                if isinstance(unit, dict) and unit.get("track") == "mandatory"
            ]
        return value
