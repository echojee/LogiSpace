from types import SimpleNamespace

from app.services.reader_v4 import FrozenPage
from app.services.search_agent_v4 import run_search_agent
from app.services.search_providers import SearchHit
from app.services.source_routing_v4 import build_funnel
from logispace_domain import dossiers
from logispace_domain.models_v4 import EvidenceRequirementV4, ResearchUnitV4, UnitBudgetV4


class ScriptedLLM:
    available = True

    def __init__(self, actions):
        self.actions = iter(actions)

    def respond_json(self, **kwargs):
        return next(self.actions), SimpleNamespace(input_tokens=10, output_tokens=5)


class RecordedTools:
    def search_domains(self, query, domains, work, limit=5):
        return [SearchHit("https://gutenberg.org/ebook/4735", "Primary text", "lead only", "recorded", .9)], []

    def fetch_page(self, url):
        text = "The narration records the interval while omitting the decisive action from its account."
        return FrozenPage("snap_recorded", url, "hash", text)


def research_unit(max_steps=6):
    return ResearchUnitV4(
        unit_id="ru_search_narrative", track="signature", domain="timeline_narrative",
        question="Where is the decisive action omitted?", why_it_matters="Tests narrative omission.",
        required_outputs=["claim", "timeline_alignment"],
        evidence_requirements=EvidenceRequirementV4(requires_primary_source=True, requires_counterevidence_search=True),
        budget=UnitBudgetV4(max_steps=max_steps, max_queries=3, max_pages=3),
        done_when=["An exact primary-text quote is frozen"], priority=5,
    )


def test_search_agent_uses_whitelist_and_only_submits_frozen_exact_quote():
    work = dossiers.get_dossier("murder-of-roger-ackroyd").work
    unit = research_unit()
    quote = "omitting the decisive action"
    llm = ScriptedLLM([
        {"action": "search_domains", "parameters": {"query": "Roger Ackroyd narration", "domains": ["gutenberg.org"]}, "decision_summary": "Start with primary text."},
        {"action": "fetch_page", "parameters": {"url": "https://gutenberg.org/ebook/4735"}, "decision_summary": "Freeze the readable body."},
        {"action": "submit_findings", "parameters": {"snapshot_id": "snap_recorded", "quote": quote, "relevance": "narrative omission", "media_version": "original_novel"}, "decision_summary": "Submit an exact quote only."},
        {"action": "stop", "parameters": {"reason": "evidence_requirement_met", "summary": "Primary evidence found."}, "decision_summary": "The unit completion condition is met."},
    ])
    result = run_search_agent(work=work, unit=unit, funnel=build_funnel(work, unit), llm=llm, toolbox=RecordedTools())
    assert result.stop_reason == "evidence_requirement_met"
    assert result.evidence_candidates[0].quote == quote
    assert result.evidence_candidates[0].locator["char_start"] >= 0
    assert [action.action for action in result.actions] == ["search_domains", "fetch_page", "submit_findings", "stop"]
    assert result.usage.queries == 1 and result.usage.pages == 1


def test_search_agent_rejects_snippet_or_unfrozen_quote_as_evidence():
    work = dossiers.get_dossier("murder-of-roger-ackroyd").work
    unit = research_unit(max_steps=2)
    llm = ScriptedLLM([
        {"action": "submit_findings", "parameters": {"snapshot_id": "missing", "quote": "snippet text"}, "decision_summary": "Attempt unsupported submission."},
        {"action": "stop", "parameters": {"reason": "inaccessible"}, "decision_summary": "No frozen source exists."},
    ])
    result = run_search_agent(work=work, unit=unit, funnel=build_funnel(work, unit), llm=llm, toolbox=RecordedTools())
    assert not result.evidence_candidates
    assert any("exact quote" in item["reason"] for item in result.urls_rejected)


def test_search_agent_stops_duplicate_action_loop():
    work = dossiers.get_dossier("murder-of-roger-ackroyd").work
    unit = research_unit(max_steps=4)
    repeated = {"action": "search_domains", "parameters": {"query": "same", "domains": ["gutenberg.org"]}, "decision_summary": "Repeated action."}
    result = run_search_agent(
        work=work, unit=unit, funnel=build_funnel(work, unit),
        llm=ScriptedLLM([repeated, repeated]), toolbox=RecordedTools(),
    )
    assert result.stop_reason == "duplicate_loop"
    assert result.usage.queries == 1
