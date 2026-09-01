import json
from types import SimpleNamespace

from app.services import reconnaissance_v4
from app.services.llm import JSONResponseError, LLMResult
from logispace_domain import dossiers
from logispace_domain.models_v4 import ResearchBriefV4


class RecordedReconLLM:
    available = True
    research_model = "recorded-recon"

    def __init__(self):
        self.calls = []

    def respond_json(self, **kwargs):
        self.calls.append(kwargs)
        return ({
            "summary": "A compact mystery-structure scout.",
            "edition_scope": "original novel only",
            "structure_signals": ["Closed suspect group"],
            "candidate_features": ["Information control inside a closed group"],
            "primary_text_options": ["chapter anchors"],
            "location_strategy": "chapter and short text anchor",
            "contamination_risks": ["Do not mix screen adaptations"],
            "open_questions": ["How does knowledge move through the group?"],
            "sources": [{"title": "Official work page", "url": "https://example.com/work", "role": "identity"}],
        }, SimpleNamespace(input_tokens=10, output_tokens=10))


def test_reconnaissance_is_bounded_and_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(reconnaissance_v4, "CACHE_ROOT", tmp_path / "recon")
    dossier = dossiers.get_dossier("murder-of-roger-ackroyd")
    brief = ResearchBriefV4(work_id=dossier.work.work_id)
    llm = RecordedReconLLM()
    first = reconnaissance_v4.run_reconnaissance(brief=brief, dossier=dossier, llm=llm)
    second = reconnaissance_v4.run_reconnaissance(brief=brief, dossier=dossier, llm=llm)
    assert first == second
    assert len(llm.calls) == 1
    assert llm.calls[0]["max_output_tokens"] == 1200
    assert llm.calls[0]["max_tool_calls"] == 1
    assert llm.calls[0]["research"] is False
    assert llm.calls[0]["model"] == "recorded-recon"
    assert llm.calls[0]["reasoning_effort"] == "low"
    assert llm.calls[0]["web_search"] is True
    assert llm.calls[0]["response_schema"]["additionalProperties"] is False


def test_reconnaissance_repairs_malformed_json_once_without_browsing(tmp_path, monkeypatch):
    monkeypatch.setattr(reconnaissance_v4, "CACHE_ROOT", tmp_path / "recon")
    dossier = dossiers.get_dossier("murder-of-roger-ackroyd")
    brief = ResearchBriefV4(work_id=dossier.work.work_id)

    class RepairLLM(RecordedReconLLM):
        def respond_json(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise JSONResponseError("malformed", '{"summary":', LLMResult(text='{"summary":'))
            return super().respond_json(**kwargs)

    llm = RepairLLM()
    result = reconnaissance_v4.run_reconnaissance(brief=brief, dossier=dossier, llm=llm)
    assert result.summary == "A compact mystery-structure scout."
    assert len(llm.calls) == 3  # repair override records, then delegates to recorded response
    assert llm.calls[0]["web_search"] is True
    assert "web_search" not in llm.calls[1]


def test_reconnaissance_cache_identity_does_not_depend_on_random_work_id():
    dossier = dossiers.get_dossier("murder-of-roger-ackroyd")
    changed_work = dossier.work.model_copy(update={"work_id": "another-provisional-id"})
    changed_dossier = dossier.model_copy(update={"work": changed_work})
    llm = RecordedReconLLM()
    first = reconnaissance_v4._cache_path(ResearchBriefV4(work_id=dossier.work.work_id), dossier, llm)
    second = reconnaissance_v4._cache_path(ResearchBriefV4(work_id=changed_work.work_id), changed_dossier, llm)
    assert first == second
