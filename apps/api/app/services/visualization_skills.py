from __future__ import annotations

import re
from typing import Protocol
from uuid import uuid4

from fastapi import HTTPException

from app.services import knowledge_memory_v4
from app.services.report_visualization_projection import relationship_projection, timeline_projection
from logispace_domain.models_memory import (
    KnowledgeMemoryV1,
    RelationshipEdgeViewV1,
    RelationshipNodeViewV1,
    TimelineEventViewV1,
    VisualizationResultV1,
)


def _node_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    return f"n_{cleaned}" if cleaned and cleaned[0].isdigit() else cleaned or f"n_{uuid4().hex[:8]}"


def _label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', "'").replace("\n", " ")[:160]


def _supported_claims(memory: KnowledgeMemoryV1) -> set[str]:
    return {
        claim.claim_id for claim in memory.verified_knowledge.claims
        if claim.support_status in {"supported", "partially_supported"}
    }


class VisualizationSkill(Protocol):
    name: str
    description: str

    def execute(self, memory: KnowledgeMemoryV1) -> VisualizationResultV1: ...


class CharacterRelationshipSkill:
    name = "character_relationship"
    description = "Project verified character relationships into a Mermaid graph."

    def execute(self, memory: KnowledgeMemoryV1) -> VisualizationResultV1:
        supported = _supported_claims(memory)
        edges: list[RelationshipEdgeViewV1] = []
        character_nodes: list[RelationshipNodeViewV1] = []
        warnings: list[str] = []
        for item in memory.verified_knowledge.domain_objects:
            if item.object_type == "character":
                claim_ids = [value for value in item.claim_ids if value in supported]
                character_id = item.payload.get("character_id") or item.payload.get("id")
                name = item.payload.get("name") or item.payload.get("label")
                if claim_ids and character_id and name:
                    character_nodes.append(RelationshipNodeViewV1(
                        character_id=str(character_id), label=str(name),
                        summary=str(item.payload.get("summary") or ""),
                        source_entity_id=item.object_id, source_claim_ids=claim_ids,
                    ))
                continue
            if item.object_type != "relationship":
                continue
            claim_ids = [value for value in item.claim_ids if value in supported]
            payload = item.payload
            source = payload.get("source_character_id") or payload.get("source_id")
            target = payload.get("target_character_id") or payload.get("target_id")
            relation = payload.get("relation_type") or payload.get("relation")
            if not claim_ids or not source or not target or not relation:
                warnings.append(f"Skipped unsupported or incomplete relationship {item.object_id}")
                continue
            edges.append(RelationshipEdgeViewV1(
                source_id=str(source), source_label=str(payload.get("source_name") or source),
                relation=str(relation), target_id=str(target),
                target_label=str(payload.get("target_name") or target),
                source_entity_id=item.object_id, source_claim_ids=claim_ids,
            ))
        report_nodes, report_edges = relationship_projection(memory)
        nodes: dict[str, RelationshipNodeViewV1] = {node.character_id: node for node in character_nodes}
        for edge in edges:
            nodes[edge.source_id] = RelationshipNodeViewV1(
                character_id=edge.source_id, label=edge.source_label,
                source_entity_id=edge.source_entity_id, source_claim_ids=edge.source_claim_ids,
            )
            nodes[edge.target_id] = RelationshipNodeViewV1(
                character_id=edge.target_id, label=edge.target_label,
                source_entity_id=edge.source_entity_id, source_claim_ids=edge.source_claim_ids,
            )
        ids_by_label = {node.label: node.character_id for node in nodes.values()}
        for node in report_nodes:
            existing_id = ids_by_label.get(node.label)
            if existing_id:
                existing = nodes[existing_id]
                if node.summary and not existing.summary:
                    existing.summary = node.summary
                existing.source_claim_ids = sorted(set(existing.source_claim_ids + node.source_claim_ids))
            else:
                nodes[node.character_id] = node
                ids_by_label[node.label] = node.character_id
        edge_keys = {(edge.source_label, edge.relation, edge.target_label) for edge in edges}
        for edge in report_edges:
            key = (edge.source_label, edge.relation, edge.target_label)
            if key in edge_keys:
                continue
            edge.source_id = ids_by_label.get(edge.source_label, edge.source_id)
            edge.target_id = ids_by_label.get(edge.target_label, edge.target_id)
            edges.append(edge)
            edge_keys.add(key)
        lines = ["graph LR"]
        lines.extend(f'    {_node_id(node.character_id)}["{_label(node.label)}"]' for node in nodes.values())
        lines.extend(
            f'    {_node_id(edge.source_id)} -->|"{_label(edge.relation)}"| {_node_id(edge.target_id)}'
            for edge in edges
        )
        return VisualizationResultV1(
            visualization_id=f"viz_{uuid4().hex[:12]}", visualization_type=self.name,
            title="人物关系图", work_id=memory.work_id, media_version=memory.media_version,
            knowledge_version=memory.knowledge_version, mermaid="\n".join(lines),
            relationship_nodes=list(nodes.values()),
            relationship_edges=edges,
            source_entity_ids=sorted({
                *[edge.source_entity_id for edge in edges],
                *[node.source_entity_id for node in nodes.values()],
            }),
            source_claim_ids=sorted({
                claim for item in [*edges, *nodes.values()] for claim in item.source_claim_ids
            }),
            warnings=warnings,
        )


class TimelineSkill:
    name = "timeline"
    description = "Project verified timeline objects into a stable Mermaid flowchart."

    def execute(self, memory: KnowledgeMemoryV1) -> VisualizationResultV1:
        supported = _supported_claims(memory)
        events: list[TimelineEventViewV1] = []
        warnings: list[str] = []
        for index, item in enumerate(memory.verified_knowledge.domain_objects):
            if item.object_type != "timeline_alignment":
                continue
            claim_ids = [value for value in item.claim_ids if value in supported]
            payload = item.payload
            title = payload.get("title") or payload.get("name") or payload.get("event")
            if not claim_ids or not title:
                warnings.append(f"Skipped unsupported or incomplete timeline object {item.object_id}")
                continue
            raw_order = payload.get("order", index + 1)
            try:
                order = int(raw_order)
            except (TypeError, ValueError):
                order = index + 1
            events.append(TimelineEventViewV1(
                event_id=str(payload.get("event_id") or item.object_id), title=str(title),
                summary=str(payload.get("summary") or ""), order=order,
                track=str(payload.get("track") or payload.get("timeline_type") or "objective"),
                time_label=str(payload.get("time_label") or payload.get("date_label") or ""),
                source_entity_id=item.object_id, source_claim_ids=claim_ids,
            ))
        report_events, timeline_scale, timeline_tracks = timeline_projection(memory)
        if report_events:
            events = report_events
        track_order = {track: index for index, track in enumerate(timeline_tracks)}
        events.sort(key=lambda item: (track_order.get(item.track, len(track_order)), item.order, item.event_id))
        lines = ["flowchart LR"]
        tracks: dict[str, list[TimelineEventViewV1]] = {}
        for event in events:
            tracks.setdefault(event.track, []).append(event)
        for track, track_events in tracks.items():
            lines.append(f'    subgraph {_node_id(track)}["{_label(timeline_tracks.get(track, track))}"]')
            for event in track_events:
                lines.append(f'        {_node_id(event.event_id)}["{_label(event.title)}"]')
            for left, right in zip(track_events, track_events[1:]):
                lines.append(f"        {_node_id(left.event_id)} --> {_node_id(right.event_id)}")
            lines.append("    end")
        return VisualizationResultV1(
            visualization_id=f"viz_{uuid4().hex[:12]}", visualization_type=self.name,
            title="作品时间线", work_id=memory.work_id, media_version=memory.media_version,
            knowledge_version=memory.knowledge_version, mermaid="\n".join(lines),
            timeline_events=events,
            timeline_scale=timeline_scale, timeline_tracks=timeline_tracks,
            source_entity_ids=[event.source_entity_id for event in events],
            source_claim_ids=sorted({claim for event in events for claim in event.source_claim_ids}),
            warnings=warnings,
        )


SKILLS: dict[str, VisualizationSkill] = {
    "character_relationship": CharacterRelationshipSkill(),
    "timeline": TimelineSkill(),
}


def generate(work_id: str, visualization_type: str, media_version: str | None = None, knowledge_version: str | None = None) -> VisualizationResultV1:
    skill = SKILLS.get(visualization_type)
    if skill is None:
        raise HTTPException(422, "Unknown visualization skill")
    memory = knowledge_memory_v4.get_version(work_id, knowledge_version) if knowledge_version and knowledge_version != "current" else knowledge_memory_v4.get_current(work_id, media_version)
    if memory is None or (media_version and memory.media_version != media_version):
        raise HTTPException(404, "Compatible knowledge memory not found")
    return skill.execute(memory)
