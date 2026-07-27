from logispace_domain.models import (
    EvidenceItem,
    ResearchJobCreate,
    ResearchJobSnapshot,
    ResearchJobStatus,
    ResearchStep,
    SourceDocument,
)
from logispace_research.pipeline import ResearchPipeline


def run_mock_pipeline(request: ResearchJobCreate) -> ResearchJobSnapshot:
    pipeline = ResearchPipeline()
    result = pipeline.run(request)
    source = SourceDocument(
        source_id="source_mock_001",
        url="https://example.com/mock-source",
        title="Mock source for scaffold validation",
        source_type="mock",
        credibility=0.5,
        captured_text="Local deterministic source used before real collectors are wired.",
    )
    evidence = EvidenceItem(
        evidence_id="evidence_mock_001",
        source_id=source.source_id,
        locator="paragraph:1",
        quote="Local deterministic source used before real collectors are wired.",
        ontology_type="Work",
        entities=["work_mock_001"],
        confidence=0.5,
    )
    return ResearchJobSnapshot(
        job_id=result.job_id,
        work_id=request.work_id,
        status=ResearchJobStatus.PUBLISHED,
        steps=[ResearchStep(name=step.name, status=step.status, detail=step.detail) for step in result.steps],
        sources=[source],
        evidence=[evidence],
        errors=[],
    )
