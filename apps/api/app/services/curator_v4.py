from __future__ import annotations

import json
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from app.services.llm import LLMGateway, gateway
from logispace_domain.models_v4 import ResearchUnitV4
from logispace_domain.models_v4_agent import FindingBundleV4
from logispace_domain.models_v4_knowledge import ClaimCandidateV4, CuratedBatchV4, DomainObjectCandidateV4

PROMPT_VERSION = "knowledge-curator-v0.4.0"


class _CuratorOutput(BaseModel):
    claims: list[dict] = Field(default_factory=list)
    domain_objects: list[dict] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


def curate(*, unit: ResearchUnitV4, findings: FindingBundleV4, llm: LLMGateway = gateway) -> CuratedBatchV4:
    if not llm.available:
        raise RuntimeError("OPENAI_API_KEY is required for Knowledge Curator")
    if not findings.evidence_candidates and not findings.counterevidence_candidates:
        return CuratedBatchV4(
            research_unit_id=unit.unit_id,
            claims=[], domain_objects=[], conflicts=[],
            unknowns=["Search produced no citable evidence; the unit must be searched again."],
        )

    evidence_by_id = {item.candidate_id: item for item in [*findings.evidence_candidates, *findings.counterevidence_candidates]}
    payload = {
        "research_unit": unit.model_dump(mode="json"),
        "evidence_candidates": [item.model_dump(mode="json") for item in evidence_by_id.values()],
        "unresolved_questions": findings.unresolved_questions,
    }
    instructions = f"""You are the LogiSpace Knowledge Curator. Use only supplied evidence candidates.
Return JSON with claims, domain_objects, conflicts, unknowns. Split compound statements into atomic claims.
Each claim needs text, claim_type (fact|inference|interpretation|conflict|unknown), evidence_candidate_ids, domain, media_version, high_risk.
Each domain object needs object_type (relationship|timeline_alignment|trick|murder_method), payload, claim_indexes.
Do not decide support status. Do not invent missing fields. Preserve conflict and unknown explicitly.
Do not merge different media versions. Prompt version: {PROMPT_VERSION}."""
    raw, _ = llm.respond_json(
        instructions=instructions, input_text=json.dumps(payload, ensure_ascii=False), research=True,
        max_output_tokens=2000, reasoning_effort="low", verbosity="low",
    )
    try:
        parsed = _CuratorOutput.model_validate(raw)
    except ValidationError as error:
        raise RuntimeError(f"Curator returned invalid structured output: {error}") from error
    claims: list[ClaimCandidateV4] = []
    for item in parsed.claims:
        evidence_ids = [eid for eid in item.get("evidence_candidate_ids", []) if eid in evidence_by_id]
        claim_type = item.get("claim_type", "unknown")
        if claim_type not in {"fact", "inference", "interpretation", "conflict", "unknown"}:
            claim_type = "unknown"
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        claims.append(ClaimCandidateV4(
            claim_id=f"claim_{uuid4().hex[:12]}", research_unit_id=unit.unit_id,
            text=text, claim_type=claim_type, evidence_candidate_ids=evidence_ids,
            domain=str(item.get("domain", unit.domain)),
            media_version=str(item.get("media_version", "selected")),
            high_risk=bool(item.get("high_risk", unit.domain in {"multiple_timelines", "tricks", "murder_methods"})),
        ))
    objects = []
    allowed_types = {"relationship", "timeline_alignment", "trick", "murder_method"}
    for item in parsed.domain_objects:
        indexes = [index for index in item.get("claim_indexes", []) if isinstance(index, int) and 0 <= index < len(claims)]
        object_type = item.get("object_type")
        if object_type not in allowed_types or not indexes:
            continue
        objects.append(DomainObjectCandidateV4(
            object_id=f"candidate_{uuid4().hex[:12]}", object_type=object_type,
            payload=item.get("payload", {}), claim_ids=[claims[index].claim_id for index in indexes],
        ))
    return CuratedBatchV4(
        research_unit_id=unit.unit_id, claims=claims, domain_objects=objects,
        conflicts=parsed.conflicts, unknowns=parsed.unknowns,
    )
