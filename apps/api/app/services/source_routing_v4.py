from __future__ import annotations

from logispace_domain.models import Work
from logispace_domain.models_v4 import ResearchUnitV4
from logispace_domain.models_v4_search import (
    RoutedSourceV4,
    SearchFunnelV4,
    SourcePackV4,
    SourceRegistryEntryV4,
)

REGISTRY_VERSION = "source-registry-v0.4.0"
PACK_VERSION = "mystery-source-packs-v0.4.0"


def _entry(domain, family, market, preferred, research, authority, group, *, sole=(), risk="medium", locator="paragraph_text_anchor", access="html"):
    return SourceRegistryEntryV4(
        domain=domain, source_family=family, market=market, preferred_for=list(preferred),
        prohibited_as_sole_support_for=list(sole), access_mode=access,
        research_value=research, evidence_authority=authority, version_risk=risk,
        independence_group=group, locator_strategy=locator,
    )


REGISTRY = {
    item.domain: item for item in [
        _entry("local_work_dossier", "local", "bilingual", ["all"], 1.0, 0.65, "local", risk="low", locator="entity_or_claim_id", access="local"),
        _entry("gutenberg.org", "primary_text", "en", ["primary_text", "timeline", "trick", "murder_method"], 0.85, 0.95, "primary_text", risk="low"),
        _entry("archive.org", "primary_archive", "en", ["primary_text", "edition"], 0.75, 0.9, "primary_archive", risk="medium", locator="page_and_text_anchor"),
        _entry("bl.uk", "institution", "en", ["identity", "creation_background"], 0.7, 0.92, "british_library", risk="low"),
        _entry("openalex.org", "academic_index", "en", ["academic_analysis"], 0.72, 0.7, "academic_index", sole=["plot_fact"], risk="low", access="api"),
        _entry("crossref.org", "academic_index", "en", ["academic_analysis"], 0.65, 0.68, "academic_index", sole=["plot_fact"], risk="low", access="api"),
        _entry("book.douban.com", "reader_community", "zh", ["edition", "reception", "controversy"], 0.88, 0.42, "douban", sole=["high_risk_claim", "author_intent"], risk="high"),
        _entry("zhihu.com", "explanation_community", "zh", ["trick_discovery", "controversy", "fair_play"], 0.82, 0.38, "zhihu", sole=["high_risk_claim", "author_intent"], risk="high"),
        _entry("bilibili.com", "video_community", "zh", ["timeline_discovery", "adaptation"], 0.72, 0.32, "bilibili", sole=["high_risk_claim"], risk="high", locator="video_timestamp_and_transcript", access="transcript"),
        _entry("goodreads.com", "reader_community", "en", ["edition", "reception", "controversy"], 0.78, 0.35, "goodreads", sole=["high_risk_claim"], risk="high"),
        _entry("reddit.com", "discussion_community", "en", ["counterargument", "omitted_lead", "controversy"], 0.8, 0.28, "reddit_thread", sole=["high_risk_claim"], risk="high", locator="thread_comment_author_time"),
        _entry("crimereads.com", "professional_criticism", "en", ["reception", "creation_background", "genre_analysis"], 0.75, 0.64, "crimereads", sole=["primary_plot_fact"], risk="medium"),
        _entry("youtube.com", "video_community", "en", ["timeline_discovery", "adaptation"], 0.68, 0.3, "youtube", sole=["high_risk_claim"], risk="high", locator="video_timestamp_and_transcript", access="transcript"),
        _entry("open_web", "fallback", "bilingual", ["lead_discovery"], 0.3, 0.2, "unknown", sole=["all_publishable_claims"], risk="high"),
    ]
}


def _pack(pack_id, domains, high, secondary=()):
    return SourcePackV4(
        pack_id=pack_id, domains=list(domains), high_priority=list(high), secondary=list(secondary),
        query_templates_zh=["{title} {question}", "{title} {alias} {domain}"],
        query_templates_en=["{english_title} {question}", '"{english_title}" {domain} analysis'],
    )


PACKS = {
    pack.pack_id: pack for pack in [
        _pack("identity_and_edition", ["identity", "edition"], ["bl.uk", "book.douban.com", "goodreads.com"]),
        _pack("primary_text_and_script", ["primary_text", "timeline_narrative"], ["gutenberg.org", "archive.org"]),
        _pack("relationships", ["relationships"], ["gutenberg.org", "archive.org"], ["zhihu.com", "reddit.com"]),
        _pack("multiple_timelines", ["multiple_timelines", "timeline_narrative"], ["gutenberg.org", "archive.org"], ["bilibili.com", "youtube.com"]),
        _pack("trick_and_misdirection", ["tricks", "trick_misdirection"], ["gutenberg.org", "archive.org"], ["zhihu.com", "reddit.com"]),
        _pack("murder_method", ["murder_methods", "murder_method"], ["gutenberg.org", "archive.org"], ["zhihu.com", "reddit.com"]),
        _pack("creation_background", ["creation_background"], ["bl.uk", "crimereads.com"], ["openalex.org"]),
        _pack("adaptation", ["adaptation"], ["bl.uk", "crimereads.com"], ["bilibili.com", "youtube.com"]),
        _pack("reception_and_controversy", ["controversy", "fair_play"], ["book.douban.com", "goodreads.com", "crimereads.com"], ["zhihu.com", "reddit.com"]),
        _pack("academic_analysis", ["academic_analysis"], ["openalex.org", "crossref.org"], ["bl.uk"]),
    ]
}


DOMAIN_PACK = {
    "relationships": "relationships",
    "multiple_timelines": "multiple_timelines",
    "timeline_narrative": "multiple_timelines",
    "tricks": "trick_and_misdirection",
    "trick_misdirection": "trick_and_misdirection",
    "murder_methods": "murder_method",
    "murder_method": "murder_method",
    "creation_background": "creation_background",
    "adaptation": "adaptation",
    "controversy": "reception_and_controversy",
    "academic_analysis": "academic_analysis",
}


def _queries(work: Work, unit: ResearchUnitV4, pack: SourcePackV4) -> list[str]:
    english_title = next((alias for alias in work.aliases if alias.isascii()), work.canonical_title)
    alias = next(iter(work.aliases), work.canonical_title)
    values = {"title": work.canonical_title, "english_title": english_title, "alias": alias, "domain": unit.domain, "question": unit.question}
    rendered = [template.format(**values) for template in [*pack.query_templates_zh, *pack.query_templates_en]]
    return list(dict.fromkeys(rendered))[:unit.budget.max_queries]


def build_funnel(work: Work, unit: ResearchUnitV4) -> SearchFunnelV4:
    pack_id = DOMAIN_PACK.get(unit.domain, "academic_analysis")
    primary_pack = PACKS[pack_id]
    pack_ids = [pack_id]
    if unit.evidence_requirements.requires_primary_source and pack_id != "primary_text_and_script":
        pack_ids.append("primary_text_and_script")
    routes = [RoutedSourceV4(domain="local_work_dossier", level="local", research_value=1, evidence_authority=.65, source_role="existing_knowledge")]
    for domain in primary_pack.high_priority:
        entry = REGISTRY[domain]
        routes.append(RoutedSourceV4(domain=domain, level="core_pack", research_value=entry.research_value, evidence_authority=entry.evidence_authority, source_role="core_discovery"))
    authority_domains = PACKS["primary_text_and_script"].high_priority if unit.evidence_requirements.requires_primary_source else [d for d in primary_pack.high_priority if REGISTRY[d].evidence_authority >= .6]
    for domain in authority_domains:
        entry = REGISTRY[domain]
        routes.append(RoutedSourceV4(domain=domain, level="authority_verification", research_value=entry.research_value, evidence_authority=entry.evidence_authority, source_role="claim_verification"))
    for domain in primary_pack.secondary:
        entry = REGISTRY[domain]
        routes.append(RoutedSourceV4(domain=domain, level="adjacent", research_value=entry.research_value, evidence_authority=entry.evidence_authority, source_role="lead_or_counterargument"))
    routes.append(RoutedSourceV4(domain="open_web", level="open_web", research_value=.3, evidence_authority=.2, source_role="last_resort_lead"))
    total = unit.budget.max_queries
    open_limit = 1 if total >= 2 else 0
    return SearchFunnelV4(
        research_unit_id=unit.unit_id,
        source_pack_ids=pack_ids,
        queries=_queries(work, unit, primary_pack),
        routes=routes,
        query_budget_by_level={
            "local": 0,
            "core_pack": max(1, int(total * .6)),
            "authority_verification": max(1, int(total * .25)),
            "adjacent": max(0, int(total * .1)),
            "open_web": open_limit,
        },
        open_web_query_limit=open_limit,
    )
