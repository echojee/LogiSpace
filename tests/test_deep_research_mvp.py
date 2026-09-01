import json
import asyncio
import pytest
from fastapi import BackgroundTasks

from logispace_domain.models import Work
from logispace_domain.models_v4 import ResearchBriefV4
from logispace_domain.models_v4_runtime import ResearchRuntimeV4

from app.services.deep_research_mvp import (
    SYSTEM_PROMPT,
    _fail,
    _extract_report,
    build_request_payload,
    build_research_prompt,
    _save_response_snapshot,
    get,
    schedule_run,
)


@pytest.fixture(autouse=True)
def isolated_knowledge_memory(monkeypatch, tmp_path):
    from app.services import knowledge_memory_v4
    monkeypatch.setattr(knowledge_memory_v4, "DATA", tmp_path / "knowledge-data")


def _job() -> ResearchRuntimeV4:
    work = Work(
        work_id="and-then-there-were-none",
        canonical_title="无人生还",
        media_type="novel",
        creators=["Agatha Christie"],
    )
    return ResearchRuntimeV4(
        job_id="research_v4_test",
        work=work,
        brief=ResearchBriefV4(
            work_id=work.work_id,
            media_version="original_novel",
            user_goal="重点解释封闭空间与读者误导",
            audience="读完原著的推理爱好者",
        ),
        status="created",
    )


def test_fixed_prompt_contains_intake_and_four_mandatory_sections():
    prompt = build_research_prompt(_job())
    assert "无人生还" in prompt
    assert "novel" in prompt
    assert "封闭空间与读者误导" in prompt
    for section in ("人物关系", "多重时间线", "核心诡计", "死亡与作案手法"):
        assert section in prompt or section in SYSTEM_PROMPT


def test_request_limits_search_but_not_report_length(monkeypatch):
    monkeypatch.delenv("LOGISPACE_DEEP_RESEARCH_MAX_TOOL_CALLS", raising=False)
    payload = build_request_payload(_job())
    assert payload["max_tool_calls"] == 6
    assert "max_output_tokens" not in payload
    assert payload["background"] is True


def test_extract_report_preserves_markdown_and_citations():
    report = _extract_report({
        "id": "resp_test",
        "model": "o3-deep-research",
        "usage": {"input_tokens": 10, "output_tokens": 20},
        "output": [{
            "type": "message",
            "content": [{
                "type": "output_text",
                "text": "# 深度研究报告\n\n正文",
                "annotations": [{
                    "type": "url_citation",
                    "url": "https://example.com/source",
                    "title": "Source",
                    "start_index": 0,
                    "end_index": 4,
                }],
            }],
        }],
    }, "prompt", "无人生还")
    assert report.markdown.startswith("# 深度研究报告")
    assert report.citations[0].url == "https://example.com/source"
    assert report.provider_response_id == "resp_test"


def test_raw_response_is_saved_as_valid_json(monkeypatch, tmp_path):
    from app.services import research_repository_v4
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "research_v4")
    _save_response_snapshot("job-test", {"id": "resp-test", "output": []})
    saved = tmp_path / "research_v4" / "_responses" / "job-test.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["id"] == "resp-test"


def test_http_run_uses_managed_background_task(monkeypatch):
    from app.services import deep_research_mvp
    calls = []
    monkeypatch.setattr(deep_research_mvp, "run", lambda job_id: calls.append(job_id))
    background_tasks = BackgroundTasks()

    assert schedule_run(background_tasks, "job-managed") is True
    assert calls == []

    asyncio.run(background_tasks())

    assert calls == ["job-managed"]
    assert "job-managed" not in deep_research_mvp._ACTIVE_RUNS


def test_incomplete_response_with_text_is_preserved():
    report = _extract_report({
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "output": [{"type": "message", "content": [{
            "type": "output_text", "text": "# 已生成的报告正文", "annotations": [],
        }]}],
    }, "prompt", "无人生还")
    assert report.markdown == "# 已生成的报告正文"
    assert report.incomplete_reason == "max_output_tokens"


def test_completed_snapshot_recovers_job_that_was_raced_back_to_plan(monkeypatch, tmp_path):
    from app.services import research_repository_v4
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "research_v4")
    job = _job().model_copy(update={"status": "awaiting_plan_approval"})
    research_repository_v4.save(job)
    _save_response_snapshot(job.job_id, {
        "id": "resp_completed",
        "status": "completed",
        "model": "o3-deep-research",
        "output": [{"type": "message", "content": [{
            "type": "output_text", "text": "# 完整报告", "annotations": [],
        }]}],
    })

    recovered = get(job.job_id)

    assert recovered.status == "completed"
    assert recovered.provider_response_id == "resp_completed"
    assert recovered.research_report.markdown == "# 完整报告"


def test_late_worker_error_cannot_downgrade_a_completed_report(monkeypatch, tmp_path):
    from app.services import research_repository_v4
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "research_v4")
    completed = _job().model_copy(update={
        "status": "completed",
        "research_report": _extract_report({
            "id": "resp_done", "model": "o3-deep-research",
            "output": [{"type": "message", "content": [{
                "type": "output_text", "text": "# 已保存报告", "annotations": [],
            }]}],
        }, "prompt", "测试作品"),
    })
    research_repository_v4.save(completed)

    result = _fail(_job(), OSError("late snapshot writer failed"))

    assert result.status == "completed"
    assert result.research_report.markdown == "# 已保存报告"
    assert "late snapshot writer failed" not in result.errors


def test_completed_report_requires_approval_before_knowledge_deposit(monkeypatch, tmp_path):
    from app.services import knowledge_memory_v4, report_knowledge_v4, research_repository_v4
    from logispace_domain.models_v4_projection import CaseFileV4, DossierBlockV4
    from logispace_domain.models_v4_verified import VerifiedClaimV4, VerifiedKnowledgeSnapshotV4
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "runtime" / "research_v4")
    monkeypatch.setattr(knowledge_memory_v4, "DATA", tmp_path / "data")
    job = _job()
    research_repository_v4.save(job)

    from app.services.deep_research_mvp import _complete_from_response
    completed = _complete_from_response(job, {
        "id": "resp_knowledge", "status": "completed", "model": "gpt-5.6-sol",
        "output": [{"type": "message", "content": [{
            "type": "output_text", "text": "# 可复用研究报告", "annotations": [],
        }]}],
    })

    assert completed.report_memory_status == "pending_approval"
    assert knowledge_memory_v4.get_report(completed.work.work_id, completed.job_id) is None

    evidence_id = "report_ev_test"
    knowledge = VerifiedKnowledgeSnapshotV4(
        snapshot_id="vk_report_test", work_id=completed.work.work_id,
        media_version=completed.brief.media_version,
        claims=[VerifiedClaimV4(
            claim_id="claim_report_test", text="测试事实", claim_type="fact",
            domain="relationships", media_version=completed.brief.media_version,
            support_status="partially_supported", evidence_ids=[evidence_id],
        )], domain_objects=[], claim_graph=[], conflicts=[], unknowns=[], gaps=[], evidence_ids=[evidence_id],
    )
    case_file = CaseFileV4(
        case_file_id="case_report_test", work_id=completed.work.work_id,
        media_version=completed.brief.media_version, title="测试档案",
        research_mainline="主线", reliability_note="部分支持",
        blocks=[DossierBlockV4(
            block_id="block_report_test", layer="one_minute", block_type="summary",
            title="摘要", text="测试事实", claim_ids=["claim_report_test"], evidence_ids=[evidence_id],
        )],
    )
    monkeypatch.setattr(report_knowledge_v4, "build", lambda job: (knowledge, case_file))

    from app.services.deep_research_mvp import review_report_memory
    approved = review_report_memory(completed.job_id, "approve")
    saved = knowledge_memory_v4.get_report(approved.work.work_id, approved.job_id)
    assert saved is not None
    assert saved["markdown"] == "# 可复用研究报告"
    assert saved["source_job_id"] == approved.job_id
    assert approved.report_memory_status == "deposited"
    assert approved.published_version == "0.1.0"
    assert knowledge_memory_v4.get_current(approved.work.work_id) is not None


def test_archived_markdown_can_resume_knowledge_deposit_without_research(monkeypatch, tmp_path):
    from app.services import knowledge_memory_v4, report_knowledge_v4, research_repository_v4
    from logispace_domain.models_v4_projection import CaseFileV4
    from logispace_domain.models_v4_verified import VerifiedKnowledgeSnapshotV4

    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "runtime" / "research_v4")
    monkeypatch.setattr(knowledge_memory_v4, "DATA", tmp_path / "data")
    job = _job().model_copy(update={
        "research_report": _extract_report({
            "id": "resp_resume", "model": "gpt-5.6-sol",
            "output": [{"type": "message", "content": [{
                "type": "output_text", "text": "# 已保存、待恢复沉淀", "annotations": [],
            }]}],
        }, "prompt", "测试作品"),
        "status": "completed", "report_memory_status": "pending_approval",
    })
    research_repository_v4.save(job)
    knowledge_memory_v4.deposit_report(job)
    knowledge = VerifiedKnowledgeSnapshotV4(
        snapshot_id="vk_resumed", work_id=job.work.work_id,
        media_version=job.brief.media_version, claims=[], domain_objects=[],
        claim_graph=[], conflicts=[], unknowns=[], gaps=[], evidence_ids=[],
    )
    case_file = CaseFileV4(
        case_file_id="case_resumed", work_id=job.work.work_id,
        media_version=job.brief.media_version, title="恢复档案",
        research_mainline="恢复", reliability_note="测试", blocks=[],
    )
    monkeypatch.setattr(report_knowledge_v4, "build", lambda runtime: (knowledge, case_file))

    from app.routes.knowledge_memory import deposit_historical_report
    response = deposit_historical_report(job.work.work_id, job.job_id)

    assert response.source_job_id == job.job_id
    restored = research_repository_v4.load(job.job_id)
    assert restored.report_memory_status == "deposited"
    assert restored.published_version == "0.1.0"


def test_rejected_report_stays_out_of_knowledge_memory(monkeypatch, tmp_path):
    from app.services import knowledge_memory_v4, research_repository_v4
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "runtime" / "research_v4")
    job = _job().model_copy(update={
        "research_report": _extract_report({
            "id": "resp_rejected", "model": "gpt-5.6-sol",
            "output": [{"type": "message", "content": [{
                "type": "output_text", "text": "# 不沉淀", "annotations": [],
            }]}],
        }, "prompt", "测试作品"),
        "status": "completed", "report_memory_status": "pending_approval",
    })
    research_repository_v4.save(job)

    from app.services.deep_research_mvp import review_report_memory
    rejected = review_report_memory(job.job_id, "reject")

    assert rejected.report_memory_status == "rejected"
    assert knowledge_memory_v4.get_report(job.work.work_id, job.job_id) is None
