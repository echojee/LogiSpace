import pytest

from app.services.source_routing_v4 import PACKS, REGISTRY, build_funnel
from logispace_domain import dossiers
from logispace_domain.models_v4 import EvidenceRequirementV4, ResearchUnitV4, UnitBudgetV4


def unit(domain="timeline_narrative", *, primary=True, queries=8):
    return ResearchUnitV4(
        unit_id=f"ru_{domain}", track="signature", domain=domain,
        question="叙述在哪里省略了关键行动？", why_it_matters="解释叙述性诡计。",
        required_outputs=["claim", "timeline_alignment"],
        evidence_requirements=EvidenceRequirementV4(
            requires_primary_source=primary,
            requires_counterevidence_search=True,
        ),
        budget=UnitBudgetV4(max_steps=10, max_queries=queries, max_pages=10),
        done_when=["关键行动具有原文定位"], priority=5,
    )


def test_registry_separates_research_value_from_evidence_authority():
    assert REGISTRY["zhihu.com"].research_value > REGISTRY["zhihu.com"].evidence_authority
    assert REGISTRY["gutenberg.org"].evidence_authority > REGISTRY["gutenberg.org"].research_value
    assert "high_risk_claim" in REGISTRY["reddit.com"].prohibited_as_sole_support_for


def test_first_release_has_all_ten_bilingual_source_packs():
    assert set(PACKS) == {
        "identity_and_edition", "primary_text_and_script", "relationships",
        "multiple_timelines", "trick_and_misdirection", "murder_method",
        "creation_background", "adaptation", "reception_and_controversy",
        "academic_analysis",
    }
    assert all(pack.query_templates_zh and pack.query_templates_en for pack in PACKS.values())


def test_primary_evidence_unit_routes_through_controlled_funnel():
    work = dossiers.get_dossier("murder-of-roger-ackroyd").work
    funnel = build_funnel(work, unit())
    assert funnel.source_pack_ids == ["multiple_timelines", "primary_text_and_script"]
    assert funnel.routes[0].level == "local"
    assert funnel.routes[-1].level == "open_web"
    assert any(route.level == "authority_verification" for route in funnel.routes)
    assert any("罗杰疑案" in query for query in funnel.queries)
    assert any("The Murder of Roger Ackroyd" in query for query in funnel.queries)
    assert funnel.open_web_query_limit == 1


def test_open_web_is_capped_at_ten_percent_and_only_for_larger_budget():
    work = dossiers.get_dossier("murder-of-roger-ackroyd").work
    funnel = build_funnel(work, unit(queries=10))
    assert funnel.open_web_query_limit == 1
    assert funnel.query_budget_by_level["open_web"] == 1


def test_unknown_signature_domain_gets_bounded_academic_discovery_pack():
    work = dossiers.get_dossier("murder-of-roger-ackroyd").work
    funnel = build_funnel(work, unit("social_history", primary=False, queries=4))
    assert funnel.source_pack_ids == ["academic_analysis"]
    assert len(funnel.queries) <= 4
