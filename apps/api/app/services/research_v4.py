from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from fastapi import HTTPException

from logispace_domain import dossiers
from logispace_domain.models import WorkDossier
from logispace_domain.models_v4 import (
    CoverageDecisionV4, EvidenceRequirementV4, PlanApprovalV4, ResearchBriefV4,
    ResearchBudgetV4, ResearchJobCreateV4, ResearchJobV4, ResearchPlanRevisionV4,
    ResearchUnitV4, UnitBudgetV4,
)

_JOBS: dict[str, ResearchJobV4] = {}
_LOCK = RLock()
_MANDATORY = ("relationships", "multiple_timelines", "tricks", "murder_methods")
_OBJECT_TYPES = {
    "relationships": set(),
    "multiple_timelines": {"Event", "Reveal", "NarrativeUnit"},
    "tricks": {"Trick"},
    "murder_methods": {"MurderMethod"},
}
_QUESTIONS = {
    "relationships": "哪些人物关系会影响案件动机、证言或共谋判断？",
    "multiple_timelines": "真实事件、调查揭示和叙事呈现如何对齐？",
    "tricks": "核心诡计的前提、执行、遮蔽、误导与揭示分别是什么？",
    "murder_methods": "杀人手法的准备、实施、掩盖与识破过程是什么？",
}
_OUTPUTS = {
    "relationships": ["claim", "relationship"],
    "multiple_timelines": ["claim", "timeline_alignment"],
    "tricks": ["claim", "trick_component"],
    "murder_methods": ["claim", "murder_method"],
}


def _coverage(dossier: WorkDossier, domain: str) -> CoverageDecisionV4:
    if domain == "relationships":
        ids = [f"{item.source_id}:{item.relation}:{item.target_id}" for item in dossier.relations]
    else:
        ids = [item.entity_id for item in dossier.entities if item.entity_type in _OBJECT_TYPES[domain]]
    return CoverageDecisionV4(
        domain=domain,
        status="needs_update" if ids else "missing",
        reason="已有结构化内容，但仍需为 0.4 补齐可追溯证据与覆盖判断。" if ids else "当前 WorkDossier 中没有该板块的结构化内容。",
        existing_object_ids=ids,
    )


def _mandatory_unit(domain: str, budget: ResearchBudgetV4) -> ResearchUnitV4:
    high_risk = domain in {"multiple_timelines", "tricks", "murder_methods"}
    queries = budget.mandatory_reserve[domain]
    return ResearchUnitV4(
        unit_id=f"ru_mandatory_{domain}", track="mandatory", domain=domain,
        question=_QUESTIONS[domain], why_it_matters="这是每部作品必须完成覆盖判断的知识板块。",
        required_outputs=_OUTPUTS[domain],
        evidence_requirements=EvidenceRequirementV4(
            requires_primary_source=high_risk,
            minimum_independent_sources=1 if high_risk else 2,
            requires_counterevidence_search=high_risk,
        ),
        budget=UnitBudgetV4(max_steps=min(20, queries + 3), max_queries=queries, max_pages=min(20, queries * 2)),
        done_when=["完成覆盖判断", "关键结论具有稳定定位的证据", "未知与冲突被显式保留"],
        priority=5 if high_risk else 4,
    )


def _signature_units(dossier: WorkDossier, budget: ResearchBudgetV4) -> list[ResearchUnitV4]:
    work = dossier.work
    haystack = " ".join([work.canonical_title, *work.aliases] + [f"{e.name} {e.summary} {e.attributes}" for e in dossier.entities]).lower()
    if "narrative_omission" in haystack or "叙述" in haystack:
        return [ResearchUnitV4(
            unit_id="ru_signature_unreliable_narration", track="signature", domain="timeline_narrative",
            question="叙述在哪些位置压缩或省略了关键行动？",
            why_it_matters="解释不可靠叙述如何在不直接陈述虚假事实的情况下误导读者。",
            required_outputs=["claim", "timeline_alignment", "trick_component"],
            evidence_requirements=EvidenceRequirementV4(
                requires_primary_source=True, minimum_independent_sources=1,
                requires_counterevidence_search=True,
            ),
            budget=UnitBudgetV4(
                max_steps=min(20, budget.signature_flexible_queries + 2),
                max_queries=max(1, min(10, budget.signature_flexible_queries)),
                max_pages=min(20, max(2, budget.signature_flexible_queries)),
            ),
            done_when=["关键行动有原文定位", "真实事件与叙述位置完成对齐", "无法确认的作者意图明确标为解读"],
            priority=5,
        )]
    return [ResearchUnitV4(
        unit_id="ru_signature_structure", track="signature", domain="work_signature",
        question="这部作品区别于同类案件的结构性研究重点是什么？",
        why_it_matters="避免档案仅机械填充四个必修板块。", required_outputs=["claim"],
        evidence_requirements=EvidenceRequirementV4(requires_counterevidence_search=True),
        budget=UnitBudgetV4(max_queries=max(1, min(10, budget.signature_flexible_queries))),
        done_when=["提出可证伪的特色问题", "特色结论与必修板块建立连接"], priority=3,
    )]


def create(request: ResearchJobCreateV4) -> ResearchJobV4:
    dossier = dossiers.get_dossier(request.work_id)
    if dossier is None:
        raise HTTPException(404, "Work not found")
    brief = request.brief or ResearchBriefV4(work_id=request.work_id)
    if brief.work_id != request.work_id:
        raise HTTPException(422, "brief.work_id must match work_id")
    job = ResearchJobV4(
        job_id=f"research_v4_{uuid4().hex[:12]}", work=dossier.work,
        status="supervisor_planning", brief=brief,
    )
    coverage = [_coverage(dossier, domain) for domain in _MANDATORY]
    units = [_mandatory_unit(domain, request.budget) for domain in _MANDATORY]
    units.extend(_signature_units(dossier, request.budget))
    job.plan = ResearchPlanRevisionV4(
        coverage=coverage, units=units, budget=request.budget,
        rationale="保留四个必修板块的最低预算，并根据当前 WorkDossier 生成作品特色轨道。",
    )
    job.status = "awaiting_plan_approval"
    with _LOCK:
        _JOBS[job.job_id] = job
    return job


def get(job_id: str) -> ResearchJobV4:
    with _LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Research job not found")
    return job


def approve(job_id: str, request: PlanApprovalV4) -> ResearchJobV4:
    job = get(job_id)
    if job.status != "awaiting_plan_approval" or job.plan is None:
        raise HTTPException(409, "Plan is not awaiting approval")
    units = request.units if request.units is not None else job.plan.units
    try:
        revised = ResearchPlanRevisionV4.model_validate(
            job.plan.model_copy(update={"units": units}, deep=True).model_dump()
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    revised.approved = True
    for unit in revised.units:
        unit.status = "approved"
    job.plan = revised
    job.status = "searching"
    job.updated_at = datetime.now(timezone.utc)
    with _LOCK:
        _JOBS[job.job_id] = job
    return job
