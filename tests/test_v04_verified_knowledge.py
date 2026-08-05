from logispace_domain.models_v4 import EvidenceRequirementV4, ResearchUnitV4, UnitBudgetV4
from logispace_domain.models_v4_agent import EvidenceCandidateV4
from logispace_domain.models_v4_knowledge import (
    ClaimCandidateV4, CuratedBatchV4, DomainObjectCandidateV4, VerificationResultV4,
)
from app.services.verified_knowledge_v4 import completion_check, freeze_verified_knowledge


def make_unit(domain, track="mandatory", priority=4):
    return ResearchUnitV4(
        unit_id=f"ru_{domain}", track=track, domain=domain, question=f"Research {domain}",
        why_it_matters="Required", required_outputs=["claim"],
        evidence_requirements=EvidenceRequirementV4(), budget=UnitBudgetV4(),
        done_when=["verified"], priority=priority,
    )


def test_verified_snapshot_is_single_source_for_claims_objects_and_graph():
    units = [make_unit(domain) for domain in ("relationships", "multiple_timelines", "tricks", "murder_methods")]
    claim = ClaimCandidateV4(
        claim_id="claim_1", research_unit_id="ru_tricks", text="Verified trick fact.",
        claim_type="fact", evidence_candidate_ids=["ev_1"], domain="tricks",
        media_version="original_novel", high_risk=True,
    )
    batch = CuratedBatchV4(
        research_unit_id="ru_tricks", claims=[claim],
        domain_objects=[DomainObjectCandidateV4(
            object_id="trick_1", object_type="trick", payload={"trick_type": "narrative"},
            claim_ids=[claim.claim_id],
        )], unknowns=["Intent remains unknown."],
    )
    verification = VerificationResultV4(
        claim_id=claim.claim_id, status="supported", valid_evidence_ids=["ev_1"], reason="Exact support",
    )
    evidence = EvidenceCandidateV4(
        candidate_id="ev_1", snapshot_id="snap", source_url="https://gutenberg.org/x",
        quote="Verified trick fact.", locator={"char_start": 0, "char_end": 20},
        proposed_relevance="trick", media_version="original_novel",
    )
    snapshot = freeze_verified_knowledge(
        work_id="work", media_version="original_novel", units=units,
        curated_batches=[batch], verification_results=[verification], evidence=[evidence],
    )
    assert snapshot.claims[0].claim_id == "claim_1"
    assert snapshot.domain_objects[0].claim_ids == ["claim_1"]
    assert {(edge.source_id, edge.relation, edge.target_id) for edge in snapshot.claim_graph} == {
        ("ev_1", "supports", "claim_1"), ("claim_1", "about", "trick_1")
    }
    assert snapshot.unknowns == ["Intent remains unknown."]
    assert next(gap for gap in snapshot.gaps if gap.research_unit_id == "ru_tricks").status == "resolved"


def test_completion_guard_blocks_unresolved_high_priority_units():
    units = [make_unit(domain) for domain in ("relationships", "multiple_timelines", "tricks", "murder_methods")]
    snapshot = freeze_verified_knowledge(
        work_id="work", media_version="original_novel", units=units,
        curated_batches=[], verification_results=[], evidence=[],
    )
    complete, reasons = completion_check(snapshot, units)
    assert complete is False
    assert any("High-priority" in reason for reason in reasons)
    assert any("No verified claims" in reason for reason in reasons)


def test_unsupported_claim_never_enters_verified_knowledge():
    unit = make_unit("tricks")
    claim = ClaimCandidateV4(
        claim_id="claim_bad", research_unit_id=unit.unit_id, text="Unsupported",
        claim_type="fact", evidence_candidate_ids=[], domain="tricks",
        media_version="original_novel", high_risk=True,
    )
    snapshot = freeze_verified_knowledge(
        work_id="work", media_version="original_novel", units=[unit],
        curated_batches=[CuratedBatchV4(research_unit_id=unit.unit_id, claims=[claim])],
        verification_results=[VerificationResultV4(claim_id="claim_bad", status="unsupported", reason="No evidence")],
        evidence=[],
    )
    assert snapshot.claims == []
