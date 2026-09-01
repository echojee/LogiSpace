from __future__ import annotations

import hashlib
import json
import socket
from collections import Counter
from typing import Literal
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from pydantic import BaseModel, Field

from app.services.llm import LLMGateway, gateway
from logispace_domain.models_v4_projection import CaseFileV4, DossierBlockV4
from logispace_domain.models_v4_runtime import ResearchRuntimeV4
from logispace_domain.models_v4_verified import (
    GapStateV4,
    VerifiedClaimV4,
    VerifiedDomainObjectV4,
    VerifiedKnowledgeSnapshotV4,
)

DOMAINS = ("relationships", "multiple_timelines", "tricks", "murder_methods")
TimelineTrack = Literal["truth", "investigation", "reader"]


class InventoryCharacterV1(BaseModel):
    character_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    summary: str
    evidence_urls: list[str] = Field(default_factory=list)


class InventoryRelationshipV1(BaseModel):
    inventory_id: str
    source_character_id: str
    target_character_id: str
    relation: str
    summary: str
    evidence_urls: list[str] = Field(default_factory=list)


class InventoryTimelineEventV1(BaseModel):
    inventory_id: str
    track: TimelineTrack
    title: str
    summary: str
    order: int
    time_label: str = ""
    evidence_urls: list[str] = Field(default_factory=list)


class InventoryCardV1(BaseModel):
    inventory_id: str
    title: str
    summary: str
    evidence_urls: list[str] = Field(default_factory=list)


class TimelineDecisionV1(BaseModel):
    selected_tracks: list[TimelineTrack] = Field(default_factory=list)
    scale: Literal["ordinal", "year", "date", "time", "custom"] = "ordinal"
    rationale: str


class ReportKnowledgeInventoryV1(BaseModel):
    characters: list[InventoryCharacterV1] = Field(default_factory=list)
    relationships: list[InventoryRelationshipV1] = Field(default_factory=list)
    timeline_events: list[InventoryTimelineEventV1] = Field(default_factory=list)
    tricks: list[InventoryCardV1] = Field(default_factory=list)
    murder_methods: list[InventoryCardV1] = Field(default_factory=list)
    timeline_decision: TimelineDecisionV1
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ReportClaimDraftV1(BaseModel):
    text: str
    domain: Literal["relationships", "multiple_timelines", "tricks", "murder_methods"]
    claim_type: str
    evidence_urls: list[str] = Field(default_factory=list)
    conflicted: bool = False


class ReportObjectDraftV1(BaseModel):
    object_type: Literal["character", "relationship", "timeline_alignment", "trick", "murder_method"]
    claim_indexes: list[int] = Field(default_factory=list)
    source_id: str | None = None
    source_name: str | None = None
    target_id: str | None = None
    target_name: str | None = None
    relation: str | None = None
    title: str | None = None
    summary: str | None = None
    order: int | None = None
    track: str | None = None
    time_label: str | None = None
    inventory_id: str | None = None


class ReportKnowledgeDraftV1(BaseModel):
    research_mainline: str
    reliability_note: str
    claims: list[ReportClaimDraftV1] = Field(default_factory=list)
    domain_objects: list[ReportObjectDraftV1] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    timeline_tracks: list[TimelineTrack] = Field(default_factory=list)
    timeline_scale: Literal["ordinal", "year", "date", "time", "custom"] = "ordinal"


def _evidence_id(url: str) -> str:
    return f"report_ev_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}"


def _url_key(url: str) -> str:
    """Normalize harmless URL presentation/tracking differences for allowlist matching."""
    value = url.strip()
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return value
    query = [
        (key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"gclid", "fbclid"}
    ]
    path = quote(unquote(parts.path), safe="/:@!$&'()*+,;=-._~")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), ""))


def _resolve_allowed_urls(urls: list[str], allowed_urls: set[str]) -> list[str]:
    """Return the report's original URLs for model-provided equivalent URLs."""
    allowed_by_key = {_url_key(url): url for url in allowed_urls}
    return sorted({allowed_by_key[key] for url in urls if (key := _url_key(url)) in allowed_by_key})


def _payload(item: ReportObjectDraftV1) -> dict:
    if item.object_type == "character":
        if not item.source_id or not item.source_name:
            return {}
        payload = {
            "character_id": item.source_id,
            "name": item.source_name,
            "summary": item.summary or "",
        }
        if item.inventory_id:
            payload["inventory_id"] = item.inventory_id
        return payload
    if item.object_type == "relationship":
        if not item.source_id or not item.target_id or not item.relation:
            return {}
        payload = {
            "source_character_id": item.source_id,
            "source_name": item.source_name or item.source_id,
            "target_character_id": item.target_id,
            "target_name": item.target_name or item.target_id,
            "relation_type": item.relation,
            "summary": item.summary or "",
        }
        if item.inventory_id:
            payload["inventory_id"] = item.inventory_id
        return payload
    if not item.title:
        return {}
    payload = {"title": item.title, "summary": item.summary or ""}
    if item.inventory_id:
        payload["inventory_id"] = item.inventory_id
    if item.object_type == "timeline_alignment":
        payload.update({
            "order": item.order or 1, "track": item.track or "truth",
            "time_label": item.time_label or "",
        })
    return payload


def _case_file(job: ResearchRuntimeV4, knowledge: VerifiedKnowledgeSnapshotV4, draft: ReportKnowledgeDraftV1) -> CaseFileV4:
    blocks: list[DossierBlockV4] = []
    lead_claims = knowledge.claims[:6]
    blocks.append(DossierBlockV4(
        block_id=f"block_{uuid4().hex[:12]}", layer="one_minute", block_type="summary",
        title="研究摘要", text=draft.research_mainline,
        claim_ids=[item.claim_id for item in lead_claims],
        evidence_ids=sorted({value for item in lead_claims for value in item.evidence_ids}),
    ))
    block_types = {
        "relationships": "relationships", "multiple_timelines": "timeline",
        "tricks": "trick", "murder_methods": "murder_method",
    }
    titles = {
        "relationships": "人物关系", "multiple_timelines": "时间线",
        "tricks": "诡计结构", "murder_methods": "作案手法",
    }
    for domain in DOMAINS:
        claims = [item for item in knowledge.claims if item.domain == domain]
        if not claims:
            continue
        blocks.append(DossierBlockV4(
            block_id=f"block_{uuid4().hex[:12]}", layer="core",
            block_type=block_types[domain], title=titles[domain],
            text="\n".join(f"- {item.text}" for item in claims),
            claim_ids=[item.claim_id for item in claims],
            evidence_ids=sorted({value for item in claims for value in item.evidence_ids}),
        ))
    blocks.append(DossierBlockV4(
        block_id=f"block_{uuid4().hex[:12]}", layer="appendix", block_type="sources",
        title="来源与可靠性说明", text=draft.reliability_note,
    ))
    return CaseFileV4(
        case_file_id=f"case_{uuid4().hex[:12]}", work_id=job.work.work_id,
        media_version=job.brief.media_version, title=job.research_report.title,
        research_mainline=draft.research_mainline,
        reliability_note=draft.reliability_note, blocks=blocks,
    )


class KnowledgeCompletenessError(ValueError):
    pass


class KnowledgeCuratorAgent:
    """Two-pass, report-grounded curator with a deterministic publication gate."""

    def __init__(self, llm: LLMGateway):
        self.llm = llm

    def _respond_json(self, **kwargs):
        """Give long report projections enough time and retry one transient timeout."""
        try:
            return self.llm.respond_json(**kwargs, timeout_seconds=300)
        except (TimeoutError, socket.timeout):
            return self.llm.respond_json(**kwargs, timeout_seconds=300)
        except RuntimeError as error:
            if "timed out" not in str(error).lower() and "timeout" not in str(error).lower():
                raise
            return self.llm.respond_json(**kwargs, timeout_seconds=300)

    def _inventory(self, extraction_input: dict, allowed_urls: set[str]) -> ReportKnowledgeInventoryV1:
        instructions = """You are the inventory pass of a knowledge-curation agent. Read the reviewed report without summarizing away items.
Build a complete ledger for four visualization panels: every named plot-relevant character with a short introduction; every explicit plot-relevant relationship; every significant event for the selected timeline tracks; every distinct trick; and every distinct murder method.
Use stable lowercase ASCII IDs. Every ledger item needs at least one exact URL from allowed_citation_urls. Do not invent facts or URLs.
Timeline selection rules: truth is required when events exist; add investigation only for a sustained inquiry whose discovery order materially differs from truth; add reader only when disclosure order or deliberate misdirection materially differs from truth; select all three only when both differences are independently meaningful. Prefer ordinal scale when precise dates/times are absent. Event order starts at 1 within each track.
Do not substitute a group label for named people. Put genuinely unsupported or ambiguous items in unknowns/conflicts instead of fabricating them."""
        raw, _ = self._respond_json(
            instructions=instructions,
            input_text=json.dumps(extraction_input, ensure_ascii=False),
            research=False, reasoning_effort="medium", verbosity="low",
            max_output_tokens=24000,
            response_schema=ReportKnowledgeInventoryV1.model_json_schema(),
        )
        inventory = ReportKnowledgeInventoryV1.model_validate(raw)
        issues: list[str] = []
        collections = (
            inventory.characters, inventory.relationships, inventory.timeline_events,
            inventory.tricks, inventory.murder_methods,
        )
        for collection in collections:
            for item in collection:
                urls = _resolve_allowed_urls(item.evidence_urls, allowed_urls)
                if not item.evidence_urls or len(urls) != len({_url_key(url) for url in item.evidence_urls}):
                    issues.append(f"inventory evidence is missing or outside the report allowlist: {item!r}")
        character_ids = {item.character_id for item in inventory.characters}
        for item in inventory.relationships:
            if item.source_character_id not in character_ids or item.target_character_id not in character_ids:
                issues.append(f"relationship {item.inventory_id} has an endpoint absent from the character inventory")
        selected = set(inventory.timeline_decision.selected_tracks)
        event_tracks = {item.track for item in inventory.timeline_events}
        if event_tracks != selected:
            issues.append(f"selected timeline tracks {sorted(selected)} do not match inventoried tracks {sorted(event_tracks)}")
        if issues:
            raise KnowledgeCompletenessError("Inventory audit failed: " + "; ".join(issues))
        return inventory

    def _materialize(self, extraction_input: dict, inventory: ReportKnowledgeInventoryV1) -> ReportKnowledgeDraftV1:
        instructions = """You are the materialization pass of a knowledge-curation agent. Convert the reviewed report and its audited inventory into the existing reusable-knowledge contract.
Materialize every inventory item exactly once; do not omit, merge, cap, or replace items. Copy inventory_id to every output object. For character objects also copy character_id to source_id, name to source_name, and provide its introduction in summary. Relationship endpoints must use inventoried character IDs.
Create concise atomic citation-bound claims in all supported domains. Every object needs at least one valid zero-based claim_indexes entry, and claims may support multiple objects. Use only exact URLs from allowed_citation_urls.
Timeline tracks and scale must exactly match inventory.timeline_decision. Preserve each event's track, order, time_label, title, and substantive summary. Never invent a calendar date.
Always represent all four domains. Unsupported domains stay empty and are explained in unknowns. Preserve conflicts and uncertainty. The caller will reject any incomplete or dangling result."""
        materialization_input = dict(extraction_input)
        materialization_input["audited_inventory"] = inventory.model_dump(mode="json")
        raw, _ = self._respond_json(
            instructions=instructions,
            input_text=json.dumps(materialization_input, ensure_ascii=False),
            research=False, reasoning_effort="medium", verbosity="low",
            max_output_tokens=30000,
            response_schema=ReportKnowledgeDraftV1.model_json_schema(),
        )
        return ReportKnowledgeDraftV1.model_validate(raw)

    @staticmethod
    def _audit_materialization(
        inventory: ReportKnowledgeInventoryV1,
        draft: ReportKnowledgeDraftV1,
        valid_claim_indexes: set[int],
    ) -> dict:
        issues: list[str] = []
        expected = {
            "character": {item.character_id for item in inventory.characters},
            "relationship": {item.inventory_id for item in inventory.relationships},
            "timeline_alignment": {item.inventory_id for item in inventory.timeline_events},
            "trick": {item.inventory_id for item in inventory.tricks},
            "murder_method": {item.inventory_id for item in inventory.murder_methods},
        }
        actual = {key: set() for key in expected}
        identity_counts: Counter[tuple[str, str]] = Counter()
        for item in draft.domain_objects:
            identity = item.source_id if item.object_type == "character" else item.inventory_id
            if identity:
                actual[item.object_type].add(identity)
                identity_counts[(item.object_type, identity)] += 1
            if not set(item.claim_indexes) & valid_claim_indexes:
                issues.append(f"{item.object_type}:{identity or 'missing-id'} has no citation-bound claim")
            if not (item.summary or "").strip():
                issues.append(f"{item.object_type}:{identity or 'missing-id'} has no summary")
        duplicates = [f"{kind}:{identity}" for (kind, identity), count in identity_counts.items() if count != 1]
        if duplicates:
            issues.append(f"inventory IDs must materialize exactly once: {sorted(duplicates)}")
        for object_type, expected_ids in expected.items():
            missing = expected_ids - actual[object_type]
            extra = actual[object_type] - expected_ids
            if missing:
                issues.append(f"{object_type} missing inventory IDs: {sorted(missing)}")
            if extra:
                issues.append(f"{object_type} contains uninventoried IDs: {sorted(extra)}")
        if draft.timeline_tracks != inventory.timeline_decision.selected_tracks:
            issues.append("materialized timeline tracks differ from the audited decision")
        if draft.timeline_scale != inventory.timeline_decision.scale:
            issues.append("materialized timeline scale differs from the audited decision")
        objects_by_key = {
            (item.object_type, item.source_id if item.object_type == "character" else item.inventory_id): item
            for item in draft.domain_objects
        }
        for expected_item in inventory.characters:
            item = objects_by_key.get(("character", expected_item.character_id))
            if item and (item.source_name != expected_item.name or item.summary != expected_item.summary):
                issues.append(f"character {expected_item.character_id} differs from its audited inventory entry")
        for expected_item in inventory.relationships:
            item = objects_by_key.get(("relationship", expected_item.inventory_id))
            if item and (
                item.source_id != expected_item.source_character_id
                or item.target_id != expected_item.target_character_id
                or item.relation != expected_item.relation
                or item.summary != expected_item.summary
            ):
                issues.append(f"relationship {expected_item.inventory_id} differs from its audited inventory entry")
        for expected_item in inventory.timeline_events:
            item = objects_by_key.get(("timeline_alignment", expected_item.inventory_id))
            if item and (
                item.track != expected_item.track
                or item.order != expected_item.order
                or (item.time_label or "") != expected_item.time_label
                or item.title != expected_item.title
                or item.summary != expected_item.summary
            ):
                issues.append(f"timeline event {expected_item.inventory_id} differs from its audited inventory entry")
        for object_type, cards in (("trick", inventory.tricks), ("murder_method", inventory.murder_methods)):
            for expected_item in cards:
                item = objects_by_key.get((object_type, expected_item.inventory_id))
                if item and (item.title != expected_item.title or item.summary != expected_item.summary):
                    issues.append(f"{object_type} {expected_item.inventory_id} differs from its audited inventory entry")
        if issues:
            raise KnowledgeCompletenessError("Materialization audit failed: " + "; ".join(issues))
        return {
            "status": "passed",
            "counts": {key: len(value) for key, value in expected.items()},
            "timeline_rationale": inventory.timeline_decision.rationale,
        }

    def run(self, job: ResearchRuntimeV4) -> tuple[VerifiedKnowledgeSnapshotV4, CaseFileV4]:
        """Project a reviewed report using exactly two model calls."""
        if job.research_report is None:
            raise ValueError("research_report is required")
        allowed_urls = {item.url for item in job.research_report.citations if item.url}
        if not allowed_urls:
            raise ValueError("The report has no citable sources for reusable knowledge")
        extraction_input = {
            "work": job.work.model_dump(mode="json"),
            "media_version": job.brief.media_version,
            "allowed_citation_urls": sorted(allowed_urls),
            "report_markdown": job.research_report.markdown,
        }
        inventory = self._inventory(extraction_input, allowed_urls)
        draft = self._materialize(extraction_input, inventory)
        claims: list[VerifiedClaimV4] = []
        draft_to_claim: dict[int, str] = {}
        for index, item in enumerate(draft.claims):
            urls = _resolve_allowed_urls(item.evidence_urls, allowed_urls)
            if not item.text.strip() or not urls:
                continue
            claim_id = f"report_claim_{uuid4().hex[:12]}"
            draft_to_claim[index] = claim_id
            claims.append(VerifiedClaimV4(
            claim_id=claim_id, text=item.text.strip(), claim_type=item.claim_type,
            domain=item.domain, media_version=job.brief.media_version,
            support_status="conflicted" if item.conflicted else "partially_supported",
            evidence_ids=[_evidence_id(url) for url in urls],
            ))
        if not claims:
            raise ValueError("No citation-bound claims could be extracted from the report")
        audit = self._audit_materialization(inventory, draft, set(draft_to_claim))
        objects: list[VerifiedDomainObjectV4] = []
        for item in draft.domain_objects:
            claim_ids = [draft_to_claim[index] for index in item.claim_indexes if index in draft_to_claim]
            payload = _payload(item)
            if not claim_ids or not payload:
                continue
            objects.append(VerifiedDomainObjectV4(
            object_id=f"report_object_{uuid4().hex[:12]}", object_type=item.object_type,
            payload=payload, claim_ids=claim_ids,
            ))
        present_domains = {item.domain for item in claims}
        knowledge = VerifiedKnowledgeSnapshotV4(
        snapshot_id=f"vk_report_{uuid4().hex[:12]}", work_id=job.work.work_id,
        media_version=job.brief.media_version, claims=claims, domain_objects=objects,
        claim_graph=[], conflicts=draft.conflicts, unknowns=draft.unknowns,
        gaps=[GapStateV4(
            research_unit_id=f"report-{domain}",
            status="resolved" if domain in present_domains else "needs_research",
            reasons=[] if domain in present_domains else ["Reviewed report did not contain citation-bound claims in this domain"],
        ) for domain in DOMAINS],
        evidence_ids=sorted({value for item in claims for value in item.evidence_ids}),
            visualization_profile={
                "timeline_tracks": draft.timeline_tracks,
                "timeline_scale": draft.timeline_scale,
                "knowledge_curator": {"version": "2-pass-v1", **audit},
            },
        )
        return knowledge, _case_file(job, knowledge, draft)


def build(job: ResearchRuntimeV4, llm: LLMGateway = gateway) -> tuple[VerifiedKnowledgeSnapshotV4, CaseFileV4]:
    return KnowledgeCuratorAgent(llm).run(job)
