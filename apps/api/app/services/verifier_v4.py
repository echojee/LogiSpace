from __future__ import annotations

import json
from urllib.parse import urlparse

from app.services.llm import LLMGateway, gateway
from app.services.source_routing_v4 import REGISTRY
from logispace_domain.models_v4_agent import EvidenceCandidateV4
from logispace_domain.models_v4_knowledge import ClaimCandidateV4, VerificationIssueV4, VerificationResultV4

PROMPT_VERSION = "verification-agent-v0.4.0"


def _source_entry(url: str):
    host = urlparse(url).netloc.lower()
    return next((entry for domain, entry in REGISTRY.items() if host.endswith(domain)), None)


def deterministic_verify(
    claim: ClaimCandidateV4,
    evidence: dict[str, EvidenceCandidateV4],
    snapshots: dict[str, str],
) -> tuple[list[str], list[str], list[VerificationIssueV4]]:
    valid, rejected, issues = [], [], []
    if not claim.evidence_candidate_ids:
        issues.append(VerificationIssueV4(code="missing_evidence", detail="Claim has no linked evidence candidates"))
    groups, has_primary = set(), False
    for evidence_id in claim.evidence_candidate_ids:
        item = evidence.get(evidence_id)
        if item is None:
            rejected.append(evidence_id)
            issues.append(VerificationIssueV4(code="missing_evidence", detail=f"Unknown evidence candidate {evidence_id}"))
            continue
        text = snapshots.get(item.snapshot_id)
        if text is None:
            rejected.append(evidence_id)
            issues.append(VerificationIssueV4(code="missing_snapshot", detail=f"Snapshot {item.snapshot_id} is unavailable"))
            continue
        start, end = item.locator.get("char_start"), item.locator.get("char_end")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(text):
            rejected.append(evidence_id)
            issues.append(VerificationIssueV4(code="invalid_locator", detail=f"Invalid character locator for {evidence_id}"))
            continue
        if text[start:end] != item.quote:
            rejected.append(evidence_id)
            issues.append(VerificationIssueV4(code="quote_mismatch", detail=f"Quote does not match frozen snapshot for {evidence_id}"))
            continue
        if claim.media_version != item.media_version:
            rejected.append(evidence_id)
            issues.append(VerificationIssueV4(code="version_mismatch", detail=f"Claim and evidence media versions differ for {evidence_id}"))
            continue
        entry = _source_entry(item.source_url)
        if entry:
            groups.add(entry.independence_group)
            has_primary = has_primary or entry.source_family in {"primary_text", "primary_archive"}
        valid.append(evidence_id)
    if claim.high_risk and valid and not has_primary and len(groups) < 2:
        issues.append(VerificationIssueV4(code="insufficient_independence", detail="High-risk claim requires primary evidence or two independent source groups"))
    return valid, rejected, issues


def verify_batch(
    *, claims: list[ClaimCandidateV4], evidence: list[EvidenceCandidateV4],
    snapshots: dict[str, str], counterevidence_ids: set[str] | None = None,
    llm: LLMGateway = gateway,
) -> list[VerificationResultV4]:
    evidence_by_id = {item.candidate_id: item for item in evidence}
    counterevidence_ids = counterevidence_ids or set()
    deterministic = {}
    semantic_input = []
    results: list[VerificationResultV4] = []
    fatal_codes = {"missing_snapshot", "quote_mismatch", "invalid_locator", "version_mismatch", "missing_evidence"}
    for claim in claims:
        valid, rejected, issues = deterministic_verify(claim, evidence_by_id, snapshots)
        deterministic[claim.claim_id] = (valid, rejected, issues)
        if any(issue.code in fatal_codes for issue in issues) or not valid:
            results.append(VerificationResultV4(
                claim_id=claim.claim_id, status="unsupported", valid_evidence_ids=valid,
                rejected_evidence_ids=rejected, issues=issues,
                reason="Deterministic evidence validation failed.", suggested_followups=["Acquire valid frozen evidence."],
            ))
            continue
        semantic_input.append({
            "claim": claim.model_dump(mode="json"),
            "evidence": [{"evidence_id": eid, "quote": evidence_by_id[eid].quote, "is_counterevidence": eid in counterevidence_ids} for eid in valid],
            "deterministic_issues": [issue.model_dump() for issue in issues],
        })
    if semantic_input:
        if not llm.available:
            raise RuntimeError("OPENAI_API_KEY is required for semantic Verification Agent")
        instructions = f"""You are the LogiSpace Verification Agent. Evaluate only the supplied atomic claims and exact quotes.
Return a JSON array with claim_id, status, reason, issue_codes, suggested_followups.
Allowed statuses: supported, partially_supported, inferred, interpretive, conflicted, unsupported.
Reject semantic overreach. Keep interpretations qualified. If counterevidence materially opposes a claim, use conflicted.
Do not add claims or evidence. Prompt version: {PROMPT_VERSION}."""
        raw, _ = llm.respond_json(instructions=instructions, input_text=json.dumps(semantic_input, ensure_ascii=False), research=True)
        decisions = {item.get("claim_id"): item for item in raw if isinstance(item, dict)} if isinstance(raw, list) else {}
        allowed = {"supported", "partially_supported", "inferred", "interpretive", "conflicted", "unsupported"}
        for item in semantic_input:
            claim_id = item["claim"]["claim_id"]
            valid, rejected, issues = deterministic[claim_id]
            decision = decisions.get(claim_id, {})
            status = decision.get("status", "unsupported")
            if status not in allowed:
                status = "unsupported"
            if any(issue.code == "insufficient_independence" for issue in issues) and status == "supported":
                status = "partially_supported"
            if any(eid in counterevidence_ids for eid in valid) and status == "supported":
                status = "conflicted"
                issues.append(VerificationIssueV4(code="counterevidence", detail="Linked counterevidence requires conflict treatment"))
            results.append(VerificationResultV4(
                claim_id=claim_id, status=status, valid_evidence_ids=valid,
                rejected_evidence_ids=rejected, issues=issues,
                reason=str(decision.get("reason", "Verifier returned no valid decision.")),
                suggested_followups=[str(value) for value in decision.get("suggested_followups", [])],
            ))
    order = {claim.claim_id: index for index, claim in enumerate(claims)}
    return sorted(results, key=lambda item: order[item.claim_id])
