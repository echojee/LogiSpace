import json

import pytest
from fastapi import HTTPException

from app.services import publication_v4, research_repository_v4, research_v4
from logispace_domain import dossiers
from logispace_domain.models_v4 import ResearchBriefV4, ResearchBudgetV4, ResearchPlanRevisionV4
from logispace_domain.models_v4_projection import CaseFileV4, DossierBlockV4, KnowledgeProposalV4, ProjectionAuditV4
from logispace_domain.models_v4_publish import ProposalReviewV4
from logispace_domain.models_v4_runtime import ResearchRuntimeV4, UnitCheckpointV4
from logispace_domain.models_v4_verified import VerifiedClaimV4, VerifiedKnowledgeSnapshotV4


@pytest.fixture
def publish_job(tmp_path, monkeypatch):
    base = dossiers.get_dossier("murder-of-roger-ackroyd")
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "runtime")
    monkeypatch.setattr(publication_v4, "DATA", tmp_path / "data")
    monkeypatch.setattr(publication_v4.dossiers, "get_dossier", lambda work_id: base)
    work_root = publication_v4.DATA / "works" / base.work.work_id
    work_root.mkdir(parents=True)
    (work_root / "manifest.json").write_text(json.dumps({
        "work_id": base.work.work_id,
        "current_dossier_version": base.dossier_version,
        "dossier_versions": [base.dossier_version],
    }), encoding="utf-8")
    budget = ResearchBudgetV4()
    units = [research_v4._mandatory_unit(domain, budget) for domain in ("relationships", "multiple_timelines", "tricks", "murder_methods")]
    plan = ResearchPlanRevisionV4(
        coverage=[research_v4._coverage(base, domain) for domain in ("relationships", "multiple_timelines", "tricks", "murder_methods")],
        units=units, budget=budget, rationale="recorded", approved=True,
    )
    verified = VerifiedKnowledgeSnapshotV4(
        snapshot_id="vk_publish", work_id=base.work.work_id, media_version="original_novel",
        claims=[VerifiedClaimV4(
            claim_id="claim_1", text="Verified", claim_type="fact", domain="tricks",
            media_version="original_novel", support_status="supported", evidence_ids=["ev_1"],
        )], domain_objects=[], claim_graph=[], conflicts=[], unknowns=[], gaps=[], evidence_ids=["ev_1"],
    )
    case = CaseFileV4(
        case_file_id="case", work_id=base.work.work_id, media_version="original_novel",
        title="Case", research_mainline="Main", reliability_note="Verified",
        blocks=[DossierBlockV4(
            block_id="block", layer="core", block_type="trick", title="Trick", text="Verified",
            claim_ids=["claim_1"], evidence_ids=["ev_1"],
        )],
    )
    proposal = KnowledgeProposalV4(
        proposal_id="proposal_1", operation="add_trick", target_section="tricks",
        payload={"name": "Verified narrative trick", "summary": "Verified"},
        claim_ids=["claim_1"], evidence_ids=["ev_1"],
    )
    job = ResearchRuntimeV4(
        job_id="job_publish", work=base.work, brief=ResearchBriefV4(work_id=base.work.work_id),
        status="needs_review", plan=plan,
        units={unit.unit_id: UnitCheckpointV4(research_unit_id=unit.unit_id, status="verified") for unit in units},
        verified_knowledge=verified, case_file=case, proposals=[proposal],
        projection_audit=ProjectionAuditV4(passed=True),
    )
    research_repository_v4.save(job)
    return job, base, work_root


def test_publish_requires_explicit_review_for_every_proposal(publish_job):
    job, _, _ = publish_job
    with pytest.raises(HTTPException) as error:
        publication_v4.publish(job.job_id)
    assert error.value.status_code == 409
    assert "explicit human decision" in error.value.detail


def test_review_and_transactional_publish_write_versioned_outputs(publish_job):
    job, base, work_root = publish_job
    publication_v4.review(job.job_id, ProposalReviewV4(approved_proposal_ids=["proposal_1"]))
    published, delta = publication_v4.publish(job.job_id)
    assert published.status == "published"
    assert delta.base_version == base.dossier_version
    version = work_root / "versions" / delta.target_version
    assert (version / "dossier.json").exists()
    assert (version / "case-file.json").exists()
    assert (version / "verified-knowledge.json").exists()
    assert (version / "research-delta.json").exists()
    assert delta.added_entities
