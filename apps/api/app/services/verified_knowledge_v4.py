from __future__ import annotations

from uuid import uuid4

from logispace_domain.models_v4 import ResearchUnitV4
from logispace_domain.models_v4_agent import EvidenceCandidateV4
from logispace_domain.models_v4_knowledge import CuratedBatchV4, VerificationResultV4
from logispace_domain.models_v4_verified import (
    ClaimRelationV4,
    GapStateV4,
    VerifiedClaimV4,
    VerifiedDomainObjectV4,
    VerifiedKnowledgeSnapshotV4,
)

ACCEPTED = {"supported", "partially_supported", "inferred", "interpretive", "conflicted"}


def freeze_verified_knowledge(
    *, work_id: str, media_version: str, units: list[ResearchUnitV4],
    curated_batches: list[CuratedBatchV4], verification_results: list[VerificationResultV4],
    evidence: list[EvidenceCandidateV4], counterevidence_ids: set[str] | None = None,
) -> VerifiedKnowledgeSnapshotV4:
    decisions = {item.claim_id: item for item in verification_results}
    evidence_by_id = {item.candidate_id: item for item in evidence}
    counterevidence_ids = counterevidence_ids or set()
    accepted_claims: dict[str, VerifiedClaimV4] = {}
    conflicts, unknowns, graph = [], [], []
    for batch in curated_batches:
        conflicts.extend(batch.conflicts)
        unknowns.extend(batch.unknowns)
        for claim in batch.claims:
            result = decisions.get(claim.claim_id)
            if not result or result.status not in ACCEPTED:
                continue
            accepted_claims[claim.claim_id] = VerifiedClaimV4(
                claim_id=claim.claim_id, text=claim.text, claim_type=claim.claim_type,
                domain=claim.domain, media_version=claim.media_version,
                support_status=result.status, evidence_ids=result.valid_evidence_ids,
            )
            for evidence_id in result.valid_evidence_ids:
                relation = "opposes" if evidence_id in counterevidence_ids else "supports"
                graph.append(ClaimRelationV4(source_id=evidence_id, relation=relation, target_id=claim.claim_id))
            if result.status == "conflicted":
                conflicts.append(claim.text)
    objects = []
    for batch in curated_batches:
        for item in batch.domain_objects:
            claim_ids = [claim_id for claim_id in item.claim_ids if claim_id in accepted_claims]
            if not claim_ids:
                continue
            objects.append(VerifiedDomainObjectV4(
                object_id=item.object_id, object_type=item.object_type,
                payload=item.payload, claim_ids=claim_ids,
            ))
            graph.extend(ClaimRelationV4(source_id=claim_id, relation="about", target_id=item.object_id) for claim_id in claim_ids)
    gaps = []
    for unit in units:
        unit_claims = [claim for claim in accepted_claims.values() if any(
            candidate.claim_id == claim.claim_id and candidate.research_unit_id == unit.unit_id
            for batch in curated_batches for candidate in batch.claims
        )]
        unit_results = [decisions[claim.claim_id] for claim in unit_claims if claim.claim_id in decisions]
        if any(result.status == "conflicted" for result in unit_results):
            status, reasons = "conflicted", ["The unit contains unresolved verified conflict."]
        elif unit_claims:
            status, reasons = "resolved", []
        else:
            status, reasons = "needs_research", ["No verified claim satisfies this Research Unit."]
        gaps.append(GapStateV4(
            research_unit_id=unit.unit_id, status=status, reasons=reasons,
            suggested_followups=[followup for result in unit_results for followup in result.suggested_followups],
        ))
    used_evidence = sorted({eid for claim in accepted_claims.values() for eid in claim.evidence_ids if eid in evidence_by_id})
    return VerifiedKnowledgeSnapshotV4(
        snapshot_id=f"vk_{uuid4().hex[:12]}", work_id=work_id, media_version=media_version,
        claims=list(accepted_claims.values()), domain_objects=objects, claim_graph=graph,
        conflicts=list(dict.fromkeys(conflicts)), unknowns=list(dict.fromkeys(unknowns)),
        gaps=gaps, evidence_ids=used_evidence,
    )


def completion_check(snapshot: VerifiedKnowledgeSnapshotV4, units: list[ResearchUnitV4]) -> tuple[bool, list[str]]:
    reasons = []
    gap_by_unit = {gap.research_unit_id: gap for gap in snapshot.gaps}
    mandatory = [unit for unit in units if unit.track == "mandatory"]
    if len(mandatory) != 4:
        reasons.append("All four mandatory Research Units must exist.")
    unresolved_high = [unit.unit_id for unit in units if unit.priority >= 4 and gap_by_unit.get(unit.unit_id, None) and gap_by_unit[unit.unit_id].status == "needs_research"]
    if unresolved_high:
        reasons.append(f"High-priority units remain unresolved: {', '.join(unresolved_high)}")
    if any(gap.status == "conflicted" for gap in snapshot.gaps):
        reasons.append("High-risk conflicts must be resolved or explicitly accepted by review.")
    if not snapshot.claims:
        reasons.append("No verified claims are available.")
    return not reasons, reasons
