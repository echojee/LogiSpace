from __future__ import annotations

from dataclasses import dataclass

from logispace_domain.dossiers import all_dossiers, get_dossier
from logispace_domain.models import WorkDossier


@dataclass
class SearchResult:
    intent: str
    answer: str
    source_work_ids: list[str]
    matched_entity_ids: list[str]
    links: list[dict[str, str]]


def _selected_dossiers(question: str, source_work_ids: list[str]) -> list[WorkDossier]:
    if source_work_ids:
        return [dossier for work_id in source_work_ids if (dossier := get_dossier(work_id)) is not None]
    mentioned = [dossier for dossier in all_dossiers() if dossier.work.canonical_title in question or any(alias in question for alias in dossier.work.aliases)]
    return mentioned or all_dossiers()


def _intent(question: str) -> str:
    if any(word in question for word in ["关系", "联系", "人物网"]):
        return "character_relationship"
    if any(word in question for word in ["时间线", "时间", "先后", "过程", "发生"]):
        return "timeline"
    if any(word in question for word in ["杀人手法", "作案手法", "怎么杀", "如何杀", "凶器"]):
        return "murder_method"
    if any(word in question for word in ["诡计", "误导", "骗局"]):
        return "trick"
    if any(word in question for word in ["人物", "角色", "是谁", "谁"]):
        return "character"
    return "overview"


def _entity_map(dossier: WorkDossier) -> dict[str, object]:
    return {entity.entity_id: entity for entity in dossier.entities}


def query_dossiers(question: str, source_work_ids: list[str] | None = None) -> SearchResult:
    selected = _selected_dossiers(question, source_work_ids or [])
    intent = _intent(question)
    sections: list[str] = []
    matched: list[str] = []
    links: list[dict[str, str]] = []

    for dossier in selected:
        entities = _entity_map(dossier)
        title = dossier.work.canonical_title
        if intent == "character_relationship":
            character_ids = {entity.entity_id for entity in dossier.entities if entity.entity_type in {"Character", "CollectiveActor"}}
            relations = [relation for relation in dossier.relations if relation.source_id in character_ids and relation.target_id in character_ids]
            if relations:
                lines = [f"{entities[item.source_id].name} —{item.relation}→ {entities[item.target_id].name}：{item.note or '结构化关系'}" for item in relations]
                sections.append(f"《{title}》人物关系：\n" + "\n".join(f"- {line}" for line in lines))
                matched.extend([value for item in relations for value in [item.source_id, item.target_id]])
                links.append({"label": f"查看《{title}》人物关系", "href": f"/library/works/{dossier.work.work_id}/relationships"})
        elif intent == "timeline":
            timeline = [entity for entity in dossier.entities if entity.entity_type in {"Event", "Reveal", "NarrativeUnit", "SolutionModel"}]
            timeline.sort(key=lambda item: item.attributes.get("order", 999))
            if timeline:
                lines = [f"{item.attributes.get('track', item.entity_type)}｜{item.name}：{item.summary}" for item in timeline]
                sections.append(f"《{title}》时间线：\n" + "\n".join(f"- {line}" for line in lines))
                matched.extend(item.entity_id for item in timeline)
                links.append({"label": f"查看《{title}》时间线", "href": f"/library/works/{dossier.work.work_id}/timeline"})
        elif intent in {"trick", "murder_method", "character"}:
            target_type = {"trick": "Trick", "murder_method": "MurderMethod", "character": "Character"}[intent]
            items = [entity for entity in dossier.entities if entity.entity_type == target_type]
            if items:
                label = {"trick": "诡计", "murder_method": "杀人手法", "character": "人物"}[intent]
                sections.append(f"《{title}》{label}：\n" + "\n".join(f"- {item.name}：{item.summary}" for item in items))
                matched.extend(item.entity_id for item in items)
                href = f"/library/{'tricks' if intent == 'trick' else 'methods'}" if intent != "character" else f"/library/works/{dossier.work.work_id}/relationships"
                links.append({"label": f"查看《{title}》{label}", "href": href})
        else:
            counts: dict[str, int] = {}
            for entity in dossier.entities:
                counts[entity.entity_type] = counts.get(entity.entity_type, 0) + 1
            summary = "、".join(f"{kind} {count}" for kind, count in sorted(counts.items()))
            sections.append(f"《{title}》当前收录：{summary}。")
            matched.extend(entity.entity_id for entity in dossier.entities)
            links.append({"label": f"进入《{title}》", "href": f"/library/works/{dossier.work.work_id}"})

    if not sections:
        return SearchResult(intent=intent, answer="当前 WorkDossier 中没有足够的结构化数据回答这个问题。", source_work_ids=[item.work.work_id for item in selected], matched_entity_ids=[], links=[])
    return SearchResult(intent=intent, answer="\n\n".join(sections), source_work_ids=[item.work.work_id for item in selected], matched_entity_ids=list(dict.fromkeys(matched)), links=links)


def relationship_view(work_id: str) -> dict | None:
    dossier = get_dossier(work_id)
    if dossier is None:
        return None
    entities = _entity_map(dossier)
    character_ids = {item.entity_id for item in dossier.entities if item.entity_type in {"Character", "CollectiveActor"}}
    nodes = [item.model_dump() for item in dossier.entities if item.entity_id in character_ids]
    edges = [item.model_dump() | {"source_name": entities[item.source_id].name, "target_name": entities[item.target_id].name} for item in dossier.relations if item.source_id in character_ids and item.target_id in character_ids]
    return {"work": dossier.work.model_dump(), "nodes": nodes, "edges": edges}


def timeline_view(work_id: str) -> dict | None:
    dossier = get_dossier(work_id)
    if dossier is None:
        return None
    items = [item.model_dump() for item in dossier.entities if item.entity_type in {"Event", "Reveal", "NarrativeUnit", "SolutionModel"}]
    items.sort(key=lambda item: item["attributes"].get("order", 999))
    return {"work": dossier.work.model_dump(), "items": items}