from __future__ import annotations

from logispace_domain.models_v4 import (
    CoverageDecisionV4,
    EvidenceRequirementV4,
    ResearchBudgetV4,
    ResearchStrategyV4,
    ResearchUnitV4,
    UnitBudgetV4,
)

MANDATORY_DOMAINS = ("relationships", "multiple_timelines", "tricks", "murder_methods")

_PROTOCOLS = {
    "relationships": {
        "question": "人物之间有哪些关键关系，这些关系如何影响动机、证词和行动？",
        "why": "人物关系是理解动机、共谋、冲突与信息流动的基础。",
        "outputs": ["character_index", "relationship_records", "relationship_changes", "uncertainties"],
        "done": ["主要人物均已纳入关系梳理", "关键关系有可靠证据", "关系变化和不确定项已明确记录"],
        "priority": 4,
    },
    "multiple_timelines": {
        "question": "案件实际发生、人物陈述、调查发现和作品揭示的先后顺序分别是什么？",
        "why": "分开梳理不同时间线，才能发现矛盾、延迟揭示和误导。",
        "outputs": ["event_timeline", "testimony_timeline", "investigation_timeline", "reveal_timeline", "conflicts"],
        "done": ["关键事件具有时间或顺序定位", "不同时间线已对齐", "冲突与未知项已明确记录"],
        "priority": 5,
    },
    "tricks": {
        "question": "核心诡计依赖哪些条件，它如何实施、误导读者并最终被揭示？",
        "why": "诡计需要同时说明机制、线索、误导和揭示，不能只记录答案。",
        "outputs": ["trick_mechanism", "required_conditions", "clues", "misdirection", "reveal_path"],
        "done": ["核心诡计的执行链条完整", "线索与误导均有证据", "替代解释或争议已检查"],
        "priority": 5,
    },
    "murder_methods": {
        "question": "每起关键案件的实施手法、时间窗口、工具、准备和掩盖方式是什么？",
        "why": "杀人手法需要与时间线和诡计分开核实，避免把推测当作事实。",
        "outputs": ["case_index", "method", "time_window", "tools_and_preparation", "concealment", "uncertainties"],
        "done": ["每起关键案件均有独立记录", "手法与时间窗口有可靠证据", "推定内容和争议已明确标注"],
        "priority": 5,
    },
}


def compile_mandatory_units(
    *,
    coverage: list[CoverageDecisionV4],
    budget: ResearchBudgetV4,
    strategy: ResearchStrategyV4,
) -> list[ResearchUnitV4]:
    decisions = {item.domain: item for item in coverage}
    units: list[ResearchUnitV4] = []
    for domain in MANDATORY_DOMAINS:
        protocol = _PROTOCOLS[domain]
        decision = decisions[domain]
        queries = budget.mandatory_reserve[domain]
        review_note = (
            f"已有 {len(decision.existing_object_ids)} 项结构化内容；本轮重点是核验、纠错和补证。"
            if strategy == "review_strengthen_and_correct" and decision.existing_object_ids
            else "本轮建立可核验的基础档案。"
        )
        high_risk = domain != "relationships"
        units.append(ResearchUnitV4(
            unit_id=f"mandatory-{domain}-01",
            track="mandatory",
            domain=domain,
            question=protocol["question"],
            why_it_matters=f'{protocol["why"]}{review_note}',
            required_outputs=protocol["outputs"],
            evidence_requirements=EvidenceRequirementV4(
                requires_primary_source=True,
                minimum_independent_sources=1 if high_risk else 2,
                requires_counterevidence_search=high_risk,
            ),
            budget=UnitBudgetV4(
                max_steps=min(20, queries + 3),
                max_queries=queries,
                max_pages=min(20, max(3, queries * 2)),
            ),
            done_when=protocol["done"],
            priority=protocol["priority"],
        ))
    return units
