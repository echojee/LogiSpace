from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.services import knowledge_memory_v4
from logispace_domain.models_memory import (
    KnowledgeMemoryV1,
    RelationshipEdgeViewV1,
    RelationshipNodeViewV1,
    TimelineEventViewV1,
)

TRACK_LABELS = {
    "truth": "真实时间线",
    "objective": "真实时间线",
    "investigation": "调查时间线",
    "reader": "读者时间线",
    "narrative": "读者时间线",
    "reveal": "读者时间线",
}


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _plain(value: str) -> str:
    value = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", value)
    value = re.sub(r"\(\[[^]]+]\([^)]+\)\)", "", value)
    value = value.replace("**", "").replace("`", "").strip()
    return re.sub(r"\s+", " ", value)


def _section(lines: list[str], heading_pattern: str) -> list[str]:
    start = None
    level = 0
    pattern = re.compile(heading_pattern)
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if match and pattern.search(_plain(match.group(2))):
            start, level = index + 1, len(match.group(1))
            break
    if start is None:
        return []
    end = len(lines)
    for index in range(start, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[index].strip())
        if match and len(match.group(1)) <= level:
            end = index
            break
    return lines[start:end]


def _report(memory: KnowledgeMemoryV1) -> str:
    if not memory.source_job_id:
        return ""
    value = knowledge_memory_v4.get_report(memory.work_id, memory.source_job_id)
    return value.get("markdown", "") if value else ""


def _domain_claims(memory: KnowledgeMemoryV1, domain: str) -> list[str]:
    return [
        claim.claim_id for claim in memory.verified_knowledge.claims
        if claim.domain == domain and claim.support_status in {"supported", "partially_supported"}
    ]


def relationship_projection(
    memory: KnowledgeMemoryV1,
) -> tuple[list[RelationshipNodeViewV1], list[RelationshipEdgeViewV1]]:
    """Recover the report's complete character index and named key relationships.

    The verified domain objects remain authoritative for edges. The Markdown report is
    used as a deterministic, work-scoped retrieval source for nodes and relationship
    sections that the bounded publication extraction may have omitted.
    """
    markdown = _report(memory)
    if not markdown:
        return [], []
    lines = markdown.splitlines()
    relation_claims = _domain_claims(memory, "relationships")
    section = _section(lines, r"人物与人物关系|人物关系")
    nodes: list[RelationshipNodeViewV1] = []
    in_character_table = False
    for line in section:
        if re.match(r"^#{2,6}\s+.*人物索引", line.strip()):
            in_character_table = True
            continue
        if in_character_table and re.match(r"^#{1,6}\s+", line.strip()):
            break
        if not in_character_table or not line.strip().startswith("|"):
            continue
        cells = [_plain(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"人物", "---"} or set(cells[0]) <= {"-", ":"}:
            continue
        label = cells[0]
        if not label or label == "人物":
            continue
        summary = "；".join(cell for cell in (cells[1], cells[-1]) if cell and not set(cell) <= {"-", ":"})
        nodes.append(RelationshipNodeViewV1(
            character_id=_stable_id("character", label), label=label, summary=summary,
            source_entity_id="report:character-index", source_claim_ids=relation_claims,
        ))

    by_label = {node.label: node for node in nodes}
    def resolve_name(value: str) -> str | None:
        if value in by_label:
            return value
        matches = [label for label in by_label if value in label or label in value]
        return matches[0] if len(matches) == 1 else None

    edges: list[RelationshipEdgeViewV1] = []
    key_section = _section(section, r"最重要的关系结构|决定情节走向的关系")
    for index, line in enumerate(key_section):
        match = re.match(r"^#{3,6}\s+(.+)$", line.strip())
        if not match:
            continue
        heading = _plain(match.group(1))
        names_part = re.split(r"[:：]", heading, maxsplit=1)[0]
        names = [resolved for value in re.split(r"[—–－]", names_part) if (resolved := resolve_name(value.strip()))]
        if len(names) < 2:
            continue
        summary = ""
        for candidate in key_section[index + 1:]:
            if re.match(r"^#{1,6}\s+", candidate.strip()):
                break
            if candidate.strip() and not candidate.lstrip().startswith(("-", "|")):
                summary = _plain(candidate)
                break
        relation = _plain(re.split(r"[:：]", heading, maxsplit=1)[1]) if re.search(r"[:：]", heading) else "关键关系"
        for left, right in zip(names, names[1:]):
            edges.append(RelationshipEdgeViewV1(
                source_id=by_label[left].character_id, source_label=left,
                relation=relation, target_id=by_label[right].character_id,
                target_label=right, source_entity_id=_stable_id("report_relation", heading),
                source_claim_ids=relation_claims,
            ))
            if summary and not by_label[left].summary:
                by_label[left].summary = summary
    return nodes, edges


@dataclass
class TimelineProfile:
    tracks: list[str]
    scale: str


def _timeline_profile(memory: KnowledgeMemoryV1) -> TimelineProfile:
    manifest = knowledge_memory_v4._manifest(memory.work_id) or {}
    metadata = manifest.get("knowledge_versions", {}).get(memory.knowledge_version, {})
    profile = memory.verified_knowledge.visualization_profile
    tracks = profile.get("timeline_tracks") or metadata.get("timeline_tracks") or ["truth", "investigation", "reader"]
    scale = profile.get("timeline_scale") or metadata.get("timeline_scale", "ordinal")
    return TimelineProfile(tracks=list(tracks), scale=str(scale))


def _timeline_section(lines: list[str], track: str) -> list[str]:
    patterns = {
        "truth": r"故事真实发生顺序|真实发生顺序",
        "investigation": r"调查发现顺序|调查时间线",
        "reader": r"作品向读者揭示的顺序|作品向观众披露的顺序|披露顺序",
    }
    return _section(lines, patterns.get(track, re.escape(track)))


def _table_events(section: list[str]) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    for line in section:
        if not line.strip().startswith("|"):
            continue
        cells = [_plain(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= {"-", ":"} or cells[0] in {"时间", "阶段"}:
            continue
        title = cells[1]
        result.append((cells[0], title[:54], title))
    return result


def _list_events(section: list[str]) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    context = ""
    for line in section:
        heading = re.match(r"^#{3,6}\s+(.+)$", line.strip())
        if heading:
            context = _plain(heading.group(1))
            continue
        item = re.match(r"^\s*(\d+)[.、]\s+(.+)$", line)
        if not item:
            continue
        summary = _plain(item.group(2))
        title = re.split(r"[；。]", summary, maxsplit=1)[0][:54]
        result.append((context or f"顺序 {item.group(1)}", title, summary))
    return result


def timeline_projection(memory: KnowledgeMemoryV1) -> tuple[list[TimelineEventViewV1], str, dict[str, str]]:
    markdown = _report(memory)
    profile = _timeline_profile(memory)
    track_labels = {track: TRACK_LABELS.get(track, track) for track in profile.tracks}
    if not markdown:
        return [], profile.scale, track_labels
    lines = markdown.splitlines()
    claim_ids = _domain_claims(memory, "multiple_timelines")
    events: list[TimelineEventViewV1] = []
    for track in profile.tracks:
        section = _timeline_section(lines, track)
        extracted = _table_events(section) or _list_events(section)
        for order, (time_label, title, summary) in enumerate(extracted, 1):
            event_key = f"{memory.work_id}:{track}:{order}:{title}"
            events.append(TimelineEventViewV1(
                event_id=_stable_id("report_event", event_key), title=title,
                summary=summary, order=order, track=track, time_label=time_label,
                source_entity_id=f"report:timeline:{track}", source_claim_ids=claim_ids,
            ))
    return events, profile.scale, track_labels
