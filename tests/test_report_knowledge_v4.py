from logispace_domain.models import Work
from logispace_domain.models_v4 import ResearchBriefV4
from logispace_domain.models_v4_runtime import ResearchReportCitationV4, ResearchReportV4, ResearchRuntimeV4

from app.services import knowledge_memory_v4, report_knowledge_v4


class FakeLLM:
    available = True

    def __init__(self):
        self.calls = 0

    def respond_json(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return ({
                "characters": [
                    {"character_id": "a", "name": "甲", "aliases": [], "summary": "知情者", "evidence_urls": ["https://example.com/source"]},
                    {"character_id": "b", "name": "乙", "aliases": [], "summary": "被协助者", "evidence_urls": ["https://example.com/source"]},
                ],
                "relationships": [{"inventory_id": "rel-a-b", "source_character_id": "a", "target_character_id": "b", "relation": "协助", "summary": "甲帮助乙隐瞒事实", "evidence_urls": ["https://example.com/source"]}],
                "timeline_events": [
                    {"inventory_id": "event-truth-1", "track": "truth", "title": "事实发生", "summary": "甲先帮助乙", "order": 1, "time_label": "顺序1", "evidence_urls": ["https://example.com/source"]},
                    {"inventory_id": "event-reader-1", "track": "reader", "title": "读者得知", "summary": "读者后来得知真相", "order": 1, "time_label": "披露1", "evidence_urls": ["https://example.com/source"]},
                ],
                "tricks": [{"inventory_id": "trick-1", "title": "隐瞒", "summary": "利用协助隐瞒事实", "evidence_urls": ["https://example.com/source"]}],
                "murder_methods": [{"inventory_id": "method-1", "title": "测试手法", "summary": "报告记载的手法", "evidence_urls": ["https://example.com/source"]}],
                "timeline_decision": {"selected_tracks": ["truth", "reader"], "scale": "ordinal", "rationale": "披露顺序与真实顺序不同"},
                "conflicts": [], "unknowns": [],
            }, type("Result", (), {})())
        return ({
            "research_mainline": "人物关系与事件顺序共同构成谜面。",
            "reliability_note": "所有条目均来自报告中允许的引用，保守标记为部分支持。",
            "claims": [
                {"text": "甲帮助乙隐瞒事实。", "domain": "relationships", "claim_type": "fact", "evidence_urls": ["https://example.com/source"], "conflicted": False},
                {"text": "第一事件发生在第二事件之前。", "domain": "multiple_timelines", "claim_type": "fact", "evidence_urls": ["https://example.com/source"], "conflicted": False},
                {"text": "隐瞒构成核心诡计。", "domain": "tricks", "claim_type": "fact", "evidence_urls": ["https://example.com/source"], "conflicted": False},
                {"text": "报告记载了测试手法。", "domain": "murder_methods", "claim_type": "fact", "evidence_urls": ["https://example.com/source"], "conflicted": False},
            ],
            "domain_objects": [
                {"object_type": "character", "inventory_id": "a", "claim_indexes": [0], "source_id": "a", "source_name": "甲", "summary": "知情者"},
                {"object_type": "character", "inventory_id": "b", "claim_indexes": [0], "source_id": "b", "source_name": "乙", "summary": "被协助者"},
                {"object_type": "relationship", "inventory_id": "rel-a-b", "claim_indexes": [0], "source_id": "a", "source_name": "甲", "target_id": "b", "target_name": "乙", "relation": "协助", "summary": "甲帮助乙隐瞒事实"},
                {"object_type": "timeline_alignment", "inventory_id": "event-truth-1", "claim_indexes": [1], "title": "事实发生", "summary": "甲先帮助乙", "order": 1, "track": "truth", "time_label": "顺序1"},
                {"object_type": "timeline_alignment", "inventory_id": "event-reader-1", "claim_indexes": [1], "title": "读者得知", "summary": "读者后来得知真相", "order": 1, "track": "reader", "time_label": "披露1"},
                {"object_type": "trick", "inventory_id": "trick-1", "claim_indexes": [2], "title": "隐瞒", "summary": "利用协助隐瞒事实"},
                {"object_type": "murder_method", "inventory_id": "method-1", "claim_indexes": [3], "title": "测试手法", "summary": "报告记载的手法"},
            ],
            "conflicts": [], "unknowns": [],
            "timeline_tracks": ["truth", "reader"], "timeline_scale": "ordinal",
        }, type("Result", (), {})())


def _job():
    work = Work(work_id="work-report-memory", canonical_title="测试作品", media_type="novel", creators=[])
    return ResearchRuntimeV4(
        job_id="job-report-memory", work=work,
        brief=ResearchBriefV4(work_id=work.work_id, media_version="original_novel"),
        status="completed",
        research_report=ResearchReportV4(
            title="测试研究报告", markdown="# 报告\n\n甲帮助乙隐瞒事实。",
            model="test-model", prompt="test",
            citations=[ResearchReportCitationV4(title="Source", url="https://example.com/source")],
        ),
    )


def test_report_projection_keeps_only_citation_bound_partial_knowledge():
    llm = FakeLLM()
    knowledge, case_file = report_knowledge_v4.build(_job(), llm=llm)
    assert llm.calls == 2
    assert len(knowledge.claims) == 4
    assert {item.support_status for item in knowledge.claims} == {"partially_supported"}
    assert {item.object_type for item in knowledge.domain_objects} == {"character", "relationship", "timeline_alignment", "trick", "murder_method"}
    assert knowledge.visualization_profile["knowledge_curator"]["status"] == "passed"
    assert knowledge.visualization_profile["timeline_tracks"] == ["truth", "reader"]
    assert {item.layer for item in case_file.blocks} == {"one_minute", "core", "appendix"}


def test_report_knowledge_publishes_a_reusable_knowledge_only_version(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge_memory_v4, "DATA", tmp_path)
    job = _job()
    knowledge, case_file = report_knowledge_v4.build(job, llm=FakeLLM())
    knowledge_memory_v4.deposit_report(job)
    version = knowledge_memory_v4.publish_report_knowledge(job, knowledge, case_file)

    current = knowledge_memory_v4.get_current(job.work.work_id)
    assert version == "0.1.0"
    assert current is not None
    assert current.source_job_id == job.job_id
    assert knowledge_memory_v4.list_works()[0]["title"] == "测试作品"
    assert knowledge_memory_v4.list_all_reports()[0]["work_id"] == job.work.work_id


def test_report_projection_rejects_an_incomplete_second_pass():
    class IncompleteLLM(FakeLLM):
        def respond_json(self, **kwargs):
            raw, result = super().respond_json(**kwargs)
            if self.calls == 2:
                raw["domain_objects"] = [
                    item for item in raw["domain_objects"]
                    if item.get("inventory_id") != "event-reader-1"
                ]
            return raw, result

    import pytest

    with pytest.raises(report_knowledge_v4.KnowledgeCompletenessError, match="event-reader-1"):
        report_knowledge_v4.build(_job(), llm=IncompleteLLM())


def test_knowledge_curator_retries_one_timeout_with_a_long_read_window():
    class TimeoutOnceLLM:
        def __init__(self):
            self.timeouts = []

        def respond_json(self, **kwargs):
            self.timeouts.append(kwargs["timeout_seconds"])
            if len(self.timeouts) == 1:
                raise TimeoutError("read timed out")
            return {"ok": True}, object()

    llm = TimeoutOnceLLM()
    result, _ = report_knowledge_v4.KnowledgeCuratorAgent(llm)._respond_json(input_text="test")

    assert result == {"ok": True}
    assert llm.timeouts == [300, 300]


def test_report_url_allowlist_accepts_tracking_and_space_encoding_variants():
    allowed = {"https://www.subtitlecat.com/subs/546/1982%20-%20Witness%20for%20the%20Prosecution.html"}
    model_urls = ["https://www.subtitlecat.com/subs/546/1982 - Witness for the Prosecution.html?utm_source=openai"]

    assert report_knowledge_v4._resolve_allowed_urls(model_urls, allowed) == sorted(allowed)


def test_report_url_allowlist_still_rejects_a_different_page():
    allowed = {"https://example.com/report/source"}

    assert report_knowledge_v4._resolve_allowed_urls(["https://example.com/report/other?utm_source=openai"], allowed) == []
