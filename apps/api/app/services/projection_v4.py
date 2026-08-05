from __future__ import annotations

import json
from uuid import uuid4

from app.services.llm import LLMGateway, gateway
from logispace_domain.models import Work
from logispace_domain.models_v4_projection import (
    CaseFileV4, DossierBlockV4, KnowledgeProposalV4, ProjectionAuditV4,
)
from logispace_domain.models_v4_verified import VerifiedKnowledgeSnapshotV4

PROMPT_VERSION = "case-file-writer-v0.4.0"
OBJECT_OPERATIONS = {
    "relationship": ("add_relation", "relationships"),
    "timeline_alignment": ("add_timeline_alignment", "multiple_timelines"),
    "trick": ("add_trick", "tricks"),
    "murder_method": ("add_murder_method", "murder_methods"),
}


def write_case_file(*, work: Work, knowledge: VerifiedKnowledgeSnapshotV4, llm: LLMGateway = gateway) -> CaseFileV4:
    if not llm.available:
        raise RuntimeError("OPENAI_API_KEY is required for the Case File Writer")
    payload = {
        "work": work.model_dump(mode="json"),
        "verified_knowledge": knowledge.model_dump(mode="json"),
        "rules": {"layers": ["one_minute", "core", "appendix"], "facts_must_reference_claim_ids": True},
    }
    instructions = f"""You are the LogiSpace Case File Writer. Use only Verified Knowledge supplied here.
Return JSON with research_mainline, reliability_note, blocks. Each block needs layer, block_type, title, text, claim_ids, evidence_ids.
Use all three reading layers: one_minute, core, appendix. Never introduce a fact not represented by a verified claim ID.
Preserve qualifications for partial, inferred, interpretive, and conflicted claims. Include unknowns and limitations.
Do not read or infer from rejected claims or raw web pages. Prompt version: {PROMPT_VERSION}."""
    raw, _ = llm.respond_json(instructions=instructions, input_text=json.dumps(payload, ensure_ascii=False), research=True)
    blocks = []
    for item in raw.get("blocks", []) if isinstance(raw, dict) else []:
        blocks.append(DossierBlockV4(
            block_id=f"block_{uuid4().hex[:12]}", layer=item.get("layer", "core"),
            block_type=item.get("block_type", "analysis"), title=str(item.get("title", "")),
            text=str(item.get("text", "")), claim_ids=[str(value) for value in item.get("claim_ids", [])],
            evidence_ids=[str(value) for value in item.get("evidence_ids", [])],
        ))
    return CaseFileV4(
        case_file_id=f"case_{uuid4().hex[:12]}", work_id=work.work_id,
        media_version=knowledge.media_version, title=f"{work.canonical_title}：深度档案",
        research_mainline=str(raw.get("research_mainline", "")),
        reliability_note=str(raw.get("reliability_note", "")), blocks=blocks,
    )


def audit_case_file(case_file: CaseFileV4, knowledge: VerifiedKnowledgeSnapshotV4) -> ProjectionAuditV4:
    claims = {item.claim_id: item for item in knowledge.claims}
    issues = []
    layers = {block.layer for block in case_file.blocks}
    if layers != {"one_minute", "core", "appendix"}:
        issues.append("Case File must contain all three reading layers.")
    for block in case_file.blocks:
        unknown_claims = [claim_id for claim_id in block.claim_ids if claim_id not in claims]
        if unknown_claims:
            issues.append(f"{block.block_id} references unknown claims: {unknown_claims}")
        if block.block_type in {"summary", "analysis", "timeline", "relationships", "trick", "murder_method"} and block.text.strip() and not block.claim_ids:
            issues.append(f"{block.block_id} contains factual presentation without claim IDs")
        allowed_evidence = {eid for claim_id in block.claim_ids if claim_id in claims for eid in claims[claim_id].evidence_ids}
        extra_evidence = set(block.evidence_ids) - allowed_evidence
        if extra_evidence:
            issues.append(f"{block.block_id} references evidence outside its claims: {sorted(extra_evidence)}")
        if any(claims[claim_id].support_status != "supported" for claim_id in block.claim_ids if claim_id in claims):
            absolute_markers = {"确定", "证明了", "毫无疑问", "definitively", "proves"}
            if any(marker in block.text.lower() for marker in absolute_markers):
                issues.append(f"{block.block_id} overstates a qualified claim")
    return ProjectionAuditV4(passed=not issues, issues=issues)


def map_knowledge_proposals(knowledge: VerifiedKnowledgeSnapshotV4) -> list[KnowledgeProposalV4]:
    claims = {item.claim_id: item for item in knowledge.claims}
    proposals = []
    for item in knowledge.domain_objects:
        operation, section = OBJECT_OPERATIONS[item.object_type]
        evidence_ids = sorted({eid for claim_id in item.claim_ids for eid in claims[claim_id].evidence_ids})
        proposals.append(KnowledgeProposalV4(
            proposal_id=f"proposal_{uuid4().hex[:12]}", operation=operation,
            target_section=section, payload=item.payload, claim_ids=item.claim_ids,
            evidence_ids=evidence_ids,
        ))
    for conflict in knowledge.conflicts:
        linked = [claim.claim_id for claim in knowledge.claims if claim.support_status == "conflicted" and claim.text == conflict]
        evidence_ids = sorted({eid for claim_id in linked for eid in claims[claim_id].evidence_ids})
        proposals.append(KnowledgeProposalV4(
            proposal_id=f"proposal_{uuid4().hex[:12]}", operation="flag_conflict",
            target_section="conflicts", payload={"summary": conflict},
            claim_ids=linked, evidence_ids=evidence_ids,
        ))
    return proposals


def cross_projection_audit(case_file: CaseFileV4, proposals: list[KnowledgeProposalV4], knowledge: VerifiedKnowledgeSnapshotV4) -> ProjectionAuditV4:
    issues = audit_case_file(case_file, knowledge).issues
    known_claims = {item.claim_id for item in knowledge.claims}
    for proposal in proposals:
        if not set(proposal.claim_ids) <= known_claims:
            issues.append(f"{proposal.proposal_id} references claims outside Verified Knowledge")
        if proposal.operation != "flag_conflict" and not proposal.claim_ids:
            issues.append(f"{proposal.proposal_id} has no verified claim support")
    return ProjectionAuditV4(passed=not issues, issues=issues)
