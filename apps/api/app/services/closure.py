from __future__ import annotations

from fastapi import HTTPException
from logispace_domain.dossiers import all_dossiers, get_dossier
from logispace_domain.models import ProductView, QAResponse


def require_dossier(work_id: str):
    dossier = get_dossier(work_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail=f"Unknown source work: {work_id}")
    return dossier


def build_product_views(work_id: str) -> list[ProductView]:
    dossier = require_dossier(work_id)
    by_type: dict[str, list[dict]] = {}
    for item in dossier.entities:
        by_type.setdefault(item.entity_type, []).append(item.model_dump())
    return [
        ProductView(view_type="knowledge_graph", work_id=work_id, title="人物—事件—证据关系图", payload={"nodes": [item.model_dump() for item in dossier.entities], "edges": [item.model_dump() for item in dossier.relations]}),
        ProductView(view_type="multi_track_timeline", work_id=work_id, title="真相—调查—话语时间线", payload={"items": [item.model_dump() for item in dossier.entities if item.entity_type in {"Event", "Reveal", "NarrativeUnit"}]}),
        ProductView(view_type="mystery_mechanism", work_id=work_id, title="诡计与协作机制视图", payload={"tricks": by_type.get("Trick", []), "testimonies": by_type.get("Testimony", []), "collective_actors": by_type.get("CollectiveActor", [])}),
        ProductView(view_type="solution_adjudication", work_id=work_id, title="真相模型与裁决视图", payload={"solution_models": by_type.get("SolutionModel", []), "revision_findings": dossier.revision_findings}),
    ]


def answer_golden_question(question_id: str, source_work_ids: list[str]) -> QAResponse:
    for dossier in [require_dossier(work_id) for work_id in source_work_ids]:
        for question in dossier.golden_questions:
            if question.question_id != question_id:
                continue
            entity_ids = {item.entity_id for item in dossier.entities}
            evidence_ok = set(question.answer_entity_ids).issubset(entity_ids)
            relation_ok = question.required_relation is None or any(item.relation == question.required_relation and item.source_id in question.answer_entity_ids and item.target_id in question.answer_entity_ids for item in dossier.relations)
            return QAResponse(question_id=question_id, source_work_ids=source_work_ids, answer=question.expected_answer, evidence_entity_ids=question.answer_entity_ids, passed=evidence_ok and relation_ok)
    raise HTTPException(status_code=404, detail="Question not found in selected source databases")


def ontology_revision_summary() -> dict:
    dossiers = all_dossiers()
    return {"schema_version": "0.2", "source_database_count": len(dossiers), "source_work_ids": [item.work.work_id for item in dossiers], "new_entity_types": ["CollectiveActor", "Testimony", "Location", "SolutionModel", "NarrativeUnit"], "revision_findings": sorted({finding for item in dossiers for finding in item.revision_findings}), "status": "closed"}
