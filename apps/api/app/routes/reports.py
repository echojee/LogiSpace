from fastapi import APIRouter
from logispace_domain.models import Claim, ReportSection, ReportVersion, SpoilerLevel, SupportStatus

router = APIRouter()


@router.get("/{report_id}", response_model=ReportVersion)
def get_report(report_id: str) -> ReportVersion:
    claim = Claim(claim_id="claim_mock_001", section="导读", text="这是一个由 EvidenceItem 支撑的确定性占位结论。", importance=1, spoiler_level=SpoilerLevel.NONE, evidence_ids=["evidence_mock_001"], support_status=SupportStatus.SUPPORTED)
    return ReportVersion(report_id=report_id, work_id="work_mock_001", schema_version="0.2", sections=[ReportSection(title="作品导读", spoiler_level=SpoilerLevel.NONE, claims=[claim])], quality_score=None)
