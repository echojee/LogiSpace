from types import SimpleNamespace

from app.services.curator_v4 import curate
from app.services.verifier_v4 import verify_batch
from logispace_domain.models_v4 import EvidenceRequirementV4, ResearchUnitV4, UnitBudgetV4
from logispace_domain.models_v4_agent import EvidenceCandidateV4, FindingBundleV4, SearchUsageV4
from logispace_domain.models_v4_knowledge import ClaimCandidateV4


class CuratorLLM:
    available = True

    def respond_json(self, **kwargs):
        return {
            "claims": [{
                "text": "The narrative omits the decisive action.", "claim_type": "fact",
                "evidence_candidate_ids": ["evc_1", "invented"], "domain": "timeline_narrative",
                "media_version": "original_novel", "high_risk": True,
            }],
            "domain_objects": [{
                "object_type": "timeline_alignment", "payload": {"alignment_type": "omission"},
                "claim_indexes": [0],
            }],
            "conflicts": [], "unknowns": ["Authorial intent is not established."],
        }, SimpleNamespace(input_tokens=1, output_tokens=1)


class VerifierLLM:
    available = True

    def __init__(self, status="supported"):
        self.status = status

    def respond_json(self, **kwargs):
        import json
        values = json.loads(kwargs["input_text"])
        return [{"claim_id": item["claim"]["claim_id"], "status": self.status, "reason": "The quote directly supports the atomic wording.", "suggested_followups": []} for item in values], SimpleNamespace(input_tokens=1, output_tokens=1)


def unit():
    return ResearchUnitV4(
        unit_id="ru_curate", track="signature", domain="timeline_narrative",
        question="Where is action omitted?", why_it_matters="Narrative trick",
        required_outputs=["claim", "timeline_alignment"],
        evidence_requirements=EvidenceRequirementV4(requires_primary_source=True),
        budget=UnitBudgetV4(), done_when=["quote located"],
    )


def evidence(url="https://gutenberg.org/ebook/4735", quote="omits the decisive action"):
    return EvidenceCandidateV4(
        candidate_id="evc_1", snapshot_id="snap_1", source_url=url, quote=quote,
        locator={"char_start": 14, "char_end": 39}, proposed_relevance="omission",
        media_version="original_novel",
    )


def test_curator_uses_only_supplied_evidence_and_builds_typed_object():
    findings = FindingBundleV4(
        research_unit_id="ru_curate", summary="found", evidence_candidates=[evidence()],
        stop_reason="evidence_requirement_met", usage=SearchUsageV4(), actions=[],
    )
    result = curate(unit=unit(), findings=findings, llm=CuratorLLM())
    assert result.claims[0].evidence_candidate_ids == ["evc_1"]
    assert result.domain_objects[0].object_type == "timeline_alignment"
    assert result.domain_objects[0].claim_ids == [result.claims[0].claim_id]
    assert result.unknowns


def test_verifier_checks_quote_locator_version_before_semantics():
    ev = evidence()
    claim = ClaimCandidateV4(
        claim_id="claim_1", research_unit_id="ru", text="The narrative omits the decisive action.",
        claim_type="fact", evidence_candidate_ids=[ev.candidate_id], domain="timeline_narrative",
        media_version="original_novel", high_risk=True,
    )
    result = verify_batch(
        claims=[claim], evidence=[ev], snapshots={"snap_1": "The narrative omits the decisive action from the account."},
        llm=VerifierLLM(),
    )[0]
    assert result.status == "supported"
    assert result.valid_evidence_ids == ["evc_1"]


def test_verifier_rejects_quote_mismatch_without_semantic_model():
    ev = evidence(quote="fabricated exact quote")
    claim = ClaimCandidateV4(
        claim_id="claim_bad", research_unit_id="ru", text="Unsupported", claim_type="fact",
        evidence_candidate_ids=[ev.candidate_id], domain="tricks", media_version="original_novel", high_risk=True,
    )
    result = verify_batch(
        claims=[claim], evidence=[ev], snapshots={"snap_1": "Different frozen content entirely."},
        llm=SimpleNamespace(available=False),
    )[0]
    assert result.status == "unsupported"
    assert any(issue.code in {"invalid_locator", "quote_mismatch"} for issue in result.issues)


def test_high_risk_community_claim_cannot_be_fully_supported_by_one_group():
    text = "Community analysis proposes a decisive action."
    ev = EvidenceCandidateV4(
        candidate_id="evc_community", snapshot_id="snap_c", source_url="https://reddit.com/r/mystery/1",
        quote=text, locator={"char_start": 0, "char_end": len(text)}, proposed_relevance="lead",
        media_version="original_novel",
    )
    claim = ClaimCandidateV4(
        claim_id="claim_community", research_unit_id="ru", text=text, claim_type="fact",
        evidence_candidate_ids=[ev.candidate_id], domain="tricks", media_version="original_novel", high_risk=True,
    )
    result = verify_batch(claims=[claim], evidence=[ev], snapshots={"snap_c": text}, llm=VerifierLLM())[0]
    assert result.status == "partially_supported"
    assert any(issue.code == "insufficient_independence" for issue in result.issues)
