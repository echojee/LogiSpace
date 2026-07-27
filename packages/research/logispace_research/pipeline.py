from datetime import datetime
from uuid import uuid4

from logispace_domain.models import ResearchJobCreate, ResearchJobStatus, ResearchStep


class ResearchPipelineResult:
    def __init__(self, job_id: str, steps: list[ResearchStep]) -> None:
        self.job_id = job_id
        self.steps = steps


class ResearchPipeline:
    """Deterministic scaffold pipeline; replace stages one by one with real adapters."""

    stage_order = [
        ResearchJobStatus.IDENTIFY,
        ResearchJobStatus.PLAN,
        ResearchJobStatus.COLLECT,
        ResearchJobStatus.CLEAN,
        ResearchJobStatus.EXTRACT,
        ResearchJobStatus.NORMALIZE,
        ResearchJobStatus.MAP,
        ResearchJobStatus.WRITE,
        ResearchJobStatus.VERIFY,
        ResearchJobStatus.PUBLISHED,
    ]

    def run(self, request: ResearchJobCreate) -> ResearchPipelineResult:
        job_id = f"job_{uuid4().hex[:12]}"
        steps = [
            ResearchStep(
                name=stage,
                status="completed",
                detail=f"Mock {stage.value} completed for {request.work_id}.",
                finished_at=datetime.utcnow(),
            )
            for stage in self.stage_order
        ]
        return ResearchPipelineResult(job_id=job_id, steps=steps)
