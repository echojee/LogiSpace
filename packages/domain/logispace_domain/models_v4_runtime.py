from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from logispace_domain.models import Work
from logispace_domain.models_v4 import ResearchBriefV4, ResearchBudgetV4, ResearchPlanRevisionV4, ResearchStrategyV4
from logispace_domain.models_v4_agent import FindingBundleV4
from logispace_domain.models_v4_history import ResearchAttemptArchiveV4
from logispace_domain.models_v4_memo import PlanMemoV4, ReconnaissanceBriefV4, SearchSessionV4
from logispace_domain.models_v4_knowledge import CuratedBatchV4, VerificationResultV4
from logispace_domain.models_v4_projection import CaseFileV4, KnowledgeProposalV4, ProjectionAuditV4
from logispace_domain.models_v4_verified import VerifiedKnowledgeSnapshotV4

RuntimeStatusV4 = Literal[
    "created", "reconnaissance_running", "supervisor_planning", "planning_failed",
    "awaiting_plan_approval", "searching", "curating", "verifying", "reflecting",
    "replanning", "knowledge_frozen", "writing", "auditing", "mapping", "needs_review",
    "depositing", "ready_to_publish", "published", "partially_completed",
    "budget_exhausted", "cancelled", "failed",
]


class PlanningFailureV4(BaseModel):
    stage: Literal["reconnaissance", "supervisor"]
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
    reconnaissance: ReconnaissanceBriefV4 | None = None
    plan_memo: PlanMemoV4 | None = None
    search_session: SearchSessionV4 = Field(default_factory=SearchSessionV4)
    attempt_history: list[ResearchAttemptArchiveV4] = Field(default_factory=list)
    proposals: list[KnowledgeProposalV4] = Field(default_factory=list)
    projection_audit: ProjectionAuditV4 | None = None
    errors: list[str] = Field(default_factory=list)
    published_version: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))