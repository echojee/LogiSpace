from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class MetricResultV4(BaseModel):
    name: str
    value: float
    target: float | None = None
    passed: bool | None = None
    detail: str = ""


class EvaluationRunV4(BaseModel):
    evaluation_id: str
    job_id: str
    metrics: list[MetricResultV4]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
