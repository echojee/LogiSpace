from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ResearchAttemptArchiveV4(BaseModel):
    attempt_id: str
    reason: str
    plan_revision: int
    unit_checkpoints: dict[str, dict]
    search_session: dict
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
