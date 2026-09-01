import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import knowledge_memory_v4, orchestrator_v4, research_repository_v4, user_memory
from app.services.visualization_skills import generate
from logispace_domain import dossiers
from logispace_domain.models_v4 import ResearchBriefV4, ResearchPlanRevisionV4
from logispace_domain.models_v4_projection import CaseFileV4, DossierBlockV4
from logispace_domain.models_v4_runtime import ResearchRuntimeV4, UnitCheckpointV4
from logispace_domain.models_v4_verified import VerifiedClaimV4, VerifiedDomainObjectV4, VerifiedKnowledgeSnapshotV4


client = TestClient(app)


def test_seeded_knowledge_keeps_the_two_current_researched_works():
    works = {item["work_id"]: item for item in knowledge_memory_v4.list_works()}
    reports = {item["work_id"] for item in knowledge_memory_v4.list_all_reports()}

    assert works["work-novel-962a77c6"]["title"] == "无人生还"
    assert works["work-series-93c9174b"]["title"] == "有罪之身"
    assert {"work-novel-962a77c6", "work-series-93c9174b"}.issubset(reports)


def _knowledge_files(tmp_path):
    work = dossiers.get_dossier("work-novel-962a77c6").work
    root = tmp_path / "works" / work.work_id
    version = root / "versions" / "1.0.0"
    version.mkdir(parents=True)
    verified = VerifiedKnowledgeSnapshotV4(
        snapshot_id="vk_memory", work_id=work.work_id, media_version="original_novel",
        claims=[
            VerifiedClaimV4(claim_id="c_rel", text="A knows B", claim_type="fact", domain="relationships", media_version="original_novel", support_status="supported", evidence_ids=["e1"]),
            VerifiedClaimV4(claim_id="c_time", text="Event one precedes event two", claim_type="fact", domain="multiple_timelines", media_version="original_novel", support_status="supported", evidence_ids=["e2"]),
            VerifiedClaimV4(claim_id="c_bad", text="Unsupported relation", claim_type="fact", domain="relationships", media_version="original_novel", support_status="inferred", evidence_ids=["e3"]),
        ],
        domain_objects=[
            VerifiedDomainObjectV4(object_id="rel_1", object_type="relationship", payload={"source_character_id": "a", "source_name": "甲", "target_character_id": "b", "target_name": "乙", "relation_type": "认识"}, claim_ids=["c_rel"]),
            VerifiedDomainObjectV4(object_id="rel_bad", object_type="relationship", payload={"source_id": "x", "target_id": "y", "relation": "猜测"}, claim_ids=["c_bad"]),
            VerifiedDomainObjectV4(object_id="event_1", object_type="timeline_alignment", payload={"title": "第一事件", "order": 1, "track": "objective"}, claim_ids=["c_time"]),
            VerifiedDomainObjectV4(object_id="event_2", object_type="timeline_alignment", payload={"title": "第二事件", "order": 2, "track": "objective"}, claim_ids=["c_time"]),
        ], claim_graph=[], conflicts=[], unknowns=[], gaps=[], evidence_ids=["e1", "e2", "e3"],
    )
    case = CaseFileV4(case_file_id="case", work_id=work.work_id, media_version="original_novel", title="测试档案", research_mainline="主线", reliability_note="可靠", blocks=[DossierBlockV4(block_id="b", layer="core", block_type="analysis", title="分析", text="内容", claim_ids=["c_rel"], evidence_ids=["e1"])])
    (version / "verified-knowledge.json").write_text(verified.model_dump_json(), encoding="utf-8")
    (version / "case-file.json").write_text(case.model_dump_json(), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({"work_id": work.work_id, "current_dossier_version": "1.0.0", "current_knowledge_version": "1.0.0", "dossier_versions": ["1.0.0"], "knowledge_versions": {"1.0.0": {"media_version": "original_novel", "source_job_id": "job_source"}}}), encoding="utf-8")
    return work, verified


def test_knowledge_memory_survives_restart_and_filters_by_version(tmp_path, monkeypatch):
    work, _ = _knowledge_files(tmp_path)
    monkeypatch.setattr(knowledge_memory_v4, "DATA", tmp_path)
    memory = knowledge_memory_v4.get_current(work.work_id, "original_novel")
    assert memory is not None
    assert memory.knowledge_version == "1.0.0"
    assert memory.source_job_id == "job_source"
    assert knowledge_memory_v4.get_current(work.work_id, "film") is None
    assert knowledge_memory_v4.versions(work.work_id) == ["1.0.0"]


def test_visualizations_use_only_supported_structured_knowledge(tmp_path, monkeypatch):
    work, _ = _knowledge_files(tmp_path)
    monkeypatch.setattr(knowledge_memory_v4, "DATA", tmp_path)
    graph = generate(work.work_id, "character_relationship")
    assert '"认识"' in graph.mermaid
    assert "猜测" not in graph.mermaid
    assert graph.source_claim_ids == ["c_rel"]
    assert len(graph.relationship_edges) == 1
    assert graph.warnings
    timeline = generate(work.work_id, "timeline")
    assert timeline.mermaid.index("第一事件") < timeline.mermaid.index("第二事件")
    assert "event_1 --> event_2" in timeline.mermaid
    assert [item.title for item in timeline.timeline_events] == ["第一事件", "第二事件"]


def test_local_user_memory_persists_and_is_available_to_api(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGISPACE_USER_MEMORY_DIR", str(tmp_path))
    saved = user_memory.update({"language": "zh-CN", "spoiler_level": "none", "preferred_analysis_dimensions": ["relationships"]})
    assert saved.spoiler_level == "none"
    assert user_memory.get().preferred_analysis_dimensions == ["relationships"]
    response = client.get("/memory/user")
    assert response.status_code == 200
    assert response.json()["spoiler_level"] == "none"


def test_resume_skips_verified_units_and_continues_from_searched(tmp_path, monkeypatch):
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "runtime")
    work = dossiers.get_dossier("work-novel-962a77c6").work
    job = ResearchRuntimeV4(job_id="job_resume", work=work, brief=ResearchBriefV4(work_id=work.work_id), status="curating")
    from app.services import research_v4
    budget = job.planning_budget
    units = [research_v4._mandatory_unit(domain, budget) for domain in ("relationships", "multiple_timelines", "tricks", "murder_methods")]
    dossier = dossiers.get_dossier(work.work_id)
    job.plan = ResearchPlanRevisionV4(
        coverage=[research_v4._coverage(dossier, domain) for domain in ("relationships", "multiple_timelines", "tricks", "murder_methods")],
        units=units, budget=budget, rationale="resume test", approved=True,
    )
    job.units = {unit.unit_id: UnitCheckpointV4(research_unit_id=unit.unit_id, status="verified") for unit in job.plan.units}
    target = job.plan.units[-1].unit_id
    job.units[target].status = "searched"
    research_repository_v4.save(job)
    calls = []
    def fake_curate(job_id, unit_id):
        value = orchestrator_v4.get(job_id); value.units[unit_id].status = "curated"; research_repository_v4.save(value); calls.append(("curate", unit_id)); return value
    def fake_verify(job_id, unit_id):
        value = orchestrator_v4.get(job_id); value.units[unit_id].status = "verified"; value.status = "reflecting"; research_repository_v4.save(value); calls.append(("verify", unit_id)); return value
    monkeypatch.setattr(orchestrator_v4, "curate_unit", fake_curate)
    monkeypatch.setattr(orchestrator_v4, "verify_unit", fake_verify)
    monkeypatch.setattr(orchestrator_v4, "freeze", lambda job_id: orchestrator_v4.get(job_id))
    orchestrator_v4.resume_research_job(job.job_id)
    assert calls == [("curate", target), ("verify", target)]
