from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha1, sha256
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.llm import JSONResponseError, LLMGateway, gateway
from app.services.planning_protocols_v4 import MANDATORY_DOMAINS, compile_mandatory_units
from app.services.signature_planning_v4 import (
    PerspectiveNoteV4, SignatureResearchUnitV4, TemporaryPerspectiveV4,
    compile_signature_units, select_perspectives,
)
from logispace_domain.models import WorkDossier
from logispace_domain.models_v4 import CoverageDecisionV4, ResearchBriefV4, ResearchBudgetV4, ResearchStrategyV4, ResearchUnitV4
from logispace_domain.models_v4_memo import ReconnaissanceBriefV4
from logispace_domain.models_v4_storm import (
    OutlineNodeV4, ResearchOutlineV4, ResearchPerspectiveV4,
    ResearchTurnV4, StormPlanningStateV4,
)

PROMPT_VERSION = "signature-storm-plan-v0.7.0"
MAX_PERSPECTIVES = 1
FOLLOW_UP_ROUNDS = 3


class PerspectiveDiscoveryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    perspectives: list[TemporaryPerspectiveV4] = Field(min_length=1, max_length=MAX_PERSPECTIVES)


class FollowUpOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notes: list[PerspectiveNoteV4] = Field(min_length=1, max_length=5)


class SignatureSynthesisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    units: list[SignatureResearchUnitV4] = Field(min_length=1, max_length=3)


class SupervisorPlanOutput(BaseModel):
    rationale: str = Field(min_length=1)
    units: list[ResearchUnitV4] = Field(min_length=5, max_length=7)


@dataclass(frozen=True)
class SupervisorRun:
    output: SupervisorPlanOutput
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    storm_planning: StormPlanningStateV4


DOMAIN_TITLES = {
    "relationships": "人物关系、动机与心理",
    "multiple_timelines": "真实事件与叙事披露时间线",
    "tricks": "线索、误导、公平推理与诡计机制",
    "murder_methods": "杀人手法、执行条件与证据",
    "work_signature": "作品专属研究方向",
}


def _basic_perspective() -> TemporaryPerspectiveV4:
    return TemporaryPerspectiveV4(
        title="基础事实与版本边界",
        starting_question="这部作品的基础事实、版本边界与核心研究对象分别是什么？",
        dossier_leads=["作品身份与指定媒介版本"],
        why_potentially_distinctive="为所有后续视角建立一致的作品身份、人物与情节边界。",
        information_gain=5, evidence_feasibility=5, generic_modules_sufficient=False,
    )


def _fallback_perspective() -> TemporaryPerspectiveV4:
    return TemporaryPerspectiveV4(
        title="叙事结构与信息控制",
        starting_question="作品如何安排视角、伏笔与信息披露来控制读者判断？",
        dossier_leads=["叙述顺序与读者已知信息"],
        why_potentially_distinctive="补充单一事实模块无法表达的叙事组织方式。",
        information_gain=4, evidence_feasibility=4, generic_modules_sufficient=False,
    )


def _perspective_models(items: list[TemporaryPerspectiveV4], model: str) -> list[ResearchPerspectiveV4]:
    unique: list[TemporaryPerspectiveV4] = []
    for item in [_basic_perspective(), *items]:
        if item.title not in {prior.title for prior in unique}:
            unique.append(item)
    if len(unique) < 2:
        unique.append(_fallback_perspective())
    return [ResearchPerspectiveV4(
        perspective_id=f"perspective-{index:02d}-{sha1(item.title.encode('utf-8')).hexdigest()[:8]}",
        title=item.title, description=item.why_potentially_distinctive,
        starting_question=item.starting_question, focus_questions=[item.starting_question],
        source_inspiration=item.dossier_leads, is_basic=index == 1,
        model=model, prompt_version=PROMPT_VERSION,
    ) for index, item in enumerate(unique[:2], start=1)]


def _outline_markdown(title: str, nodes: list[OutlineNodeV4]) -> str:
    lines = [f"# {title}"]
    for index, node in enumerate(nodes, start=1):
        lines.extend([f"\n## {index}. {node.title}", f"- 目的：{node.purpose}"])
        lines.extend(f"- [ ] {question}" for question in node.research_questions)
        lines.extend(f"  - 搜索方向：{direction}" for direction in node.search_directions)
        if node.open_questions:
            lines.extend(f"  - 未决：{question}" for question in node.open_questions)
    return "\n".join(lines)


def _compile_outline(*, kind: str, title: str, units: list[ResearchUnitV4],
                     notes: list[PerspectiveNoteV4] | None = None) -> ResearchOutlineV4:
    notes = notes or []
    nodes: list[OutlineNodeV4] = []
    for index, unit in enumerate(units, start=1):
        relevant = [note for note in notes if unit.question == note.question or unit.domain == "work_signature"]
        directions = list(dict.fromkeys([
            *unit.required_outputs,
            *(query for note in relevant for query in note.suggested_queries),
        ]))
        open_questions = list(dict.fromkeys(question for note in relevant for question in note.unresolved))
        nodes.append(OutlineNodeV4(
            section_id=unit.unit_id, title=DOMAIN_TITLES.get(unit.domain, unit.question),
            purpose=unit.why_it_matters, research_questions=[unit.question],
            search_directions=directions, required_source_types=[
                "primary_text" if unit.evidence_requirements.requires_primary_source else "reliable_secondary",
                "independent_cross_check",
            ], expected_claims=unit.required_outputs,
            cross_section_dependencies=[item.unit_id for item in units if item.unit_id != unit.unit_id and item.track == "mandatory"][:2],
            open_questions=open_questions, spoiler_level="full",
        ))
    markdown = _outline_markdown(title, nodes)
    digest = sha256(markdown.encode("utf-8")).hexdigest()[:12]
    return ResearchOutlineV4(
        outline_id=f"{kind}-outline-{digest}", kind=kind, title=title,
        nodes=nodes, markdown=markdown, prompt_version=PROMPT_VERSION,
    )


def compile_outline_from_units(*, kind: str, title: str, units: list[ResearchUnitV4]) -> ResearchOutlineV4:
    return _compile_outline(kind=kind, title=title, units=units)


def compile_planning_state_from_units(*, title: str, units: list[ResearchUnitV4],
                                      model: str, prompt_version: str) -> StormPlanningStateV4:
    """Compatibility adapter for recorded/legacy supervisors used by old v4 jobs."""
    temporary = [_basic_perspective(), _fallback_perspective()]
    perspectives = [ResearchPerspectiveV4(
        perspective_id=f"perspective-{index:02d}-{sha1(item.title.encode('utf-8')).hexdigest()[:8]}",
        title=item.title, description=item.why_potentially_distinctive,
        starting_question=item.starting_question, focus_questions=[item.starting_question],
        source_inspiration=item.dossier_leads, is_basic=index == 1,
        model=model, prompt_version=prompt_version,
    ) for index, item in enumerate(temporary, start=1)]
    direct = _compile_outline(kind="direct", title=f"《{title}》初始研究大纲", units=units[:4])
    research = _compile_outline(kind="research", title=f"《{title}》研究增强大纲", units=units)
    return StormPlanningStateV4(
        perspectives=perspectives, research_turns=[], direct_outline=direct, research_outline=research,
    )


def _dossier_context(dossier: WorkDossier) -> dict:
    return {
        "work": dossier.work.model_dump(mode="json"),
        "dossier_version": dossier.dossier_version,
        "entities": [{"name": x.name, "summary": x.summary, "attributes": x.attributes} for x in dossier.entities[:30]],
        "relations": [x.model_dump(mode="json") for x in dossier.relations[:30]],
        "revision_findings": dossier.revision_findings[:8],
    }


def _validate_compiled_plan(output: SupervisorPlanOutput, budget: ResearchBudgetV4) -> None:
    mandatory = [unit for unit in output.units if unit.track == "mandatory"]
    signatures = [unit for unit in output.units if unit.track == "signature"]
    if len(mandatory) != 4 or {unit.domain for unit in mandatory} != set(MANDATORY_DOMAINS):
        raise ValueError("Compiled plan must contain the four mandatory protocols")
    if not 1 <= len(signatures) <= 3:
        raise ValueError("Compiled plan must contain between one and three signature units")
    if len({unit.unit_id for unit in output.units}) != len(output.units):
        raise ValueError("Compiled plan contains duplicate unit ids")
    if sum(unit.budget.max_queries for unit in signatures) > budget.signature_flexible_queries:
        raise ValueError("Signature units exceed the shared flexible query budget")


def _call_json(llm: LLMGateway, *, instructions: str, payload: dict, schema: type[BaseModel],
               web_search: bool = False, max_output_tokens: int = 2400,
               max_tool_calls: int = 3):
    plan_model = getattr(llm, "plan_model", llm.research_model)
    request = {
        "instructions": f"{instructions}\nPrompt version: {PROMPT_VERSION}.",
        "input_text": json.dumps(payload, ensure_ascii=False),
        "research": False,
        "model": plan_model,
        "web_search": web_search,
        "max_tool_calls": max_tool_calls if web_search else None,
        "reasoning_effort": "low",
        "verbosity": "low",
        "response_schema": schema.model_json_schema(),
    }
    try:
        raw, result = llm.respond_json(**request, max_output_tokens=max_output_tokens)
    except JSONResponseError:
        # Structured output can still be cut off when the response budget also
        # has to accommodate reasoning tokens. Retry once with bounded headroom.
        raw, result = llm.respond_json(**request, max_output_tokens=max_output_tokens * 2)
    return schema.model_validate(raw), result


def generate_plan(*, brief: ResearchBriefV4, dossier: WorkDossier, coverage: list[CoverageDecisionV4],
                  budget: ResearchBudgetV4, reconnaissance: ReconnaissanceBriefV4 | None = None,
                  strategy: ResearchStrategyV4 = "build_and_verify", llm: LLMGateway = gateway) -> SupervisorRun:
    if not llm.available:
        raise RuntimeError("OPENAI_API_KEY is required for Supervisor Agent planning")
    mandatory_units = compile_mandatory_units(coverage=coverage, budget=budget, strategy=strategy)
    direct_outline = _compile_outline(
        kind="direct", title=f"《{dossier.work.canonical_title}》初始研究大纲",
        units=mandatory_units,
    )
    base = {
        "brief": brief.model_dump(mode="json"), "dossier": _dossier_context(dossier),
        "generic_modules": {unit.domain: unit.question for unit in mandatory_units},
        "reconnaissance": reconnaissance.model_dump(mode="json") if reconnaissance else None,
    }
    input_tokens = output_tokens = 0
    try:
        discovery, result = _call_json(
            llm, schema=PerspectiveDiscoveryOutput, payload=base, max_output_tokens=1600,
            instructions="""Discover exactly one temporary, work-specific research perspective. Together with the built-in
basic-facts/version-boundary perspective, this forms exactly two perspectives. The dynamic perspective is a disposable
question, not Feature Schema or a fixed feature type. Make it concrete from the dossier and existing reconnaissance.
It may cross relationships, timelines, tricks, or murder methods. Mark
generic_modules_sufficient=true only when those four modules can already answer the whole direction; overlap itself is
never a penalty. Prefer important work-specific connections and avoid generic themes or adaptation comparisons.""",
        )
        input_tokens += result.input_tokens; output_tokens += result.output_tokens
        try:
            selected = select_perspectives(discovery.perspectives)
            perspective_fallback_used = False
        except ValueError as error:
            if "No perspective exposes a material gap" not in str(error):
                raise
            # A work does not need to invent a fifth taxonomy merely to pass
            # planning. Keep the four mandatory modules and continue with a
            # conservative narrative/information-control angle that the user
            # can review or deselect before the single research request.
            selected = [_fallback_perspective()]
            perspective_fallback_used = True
        basic = _basic_perspective()
        active = selected[:1]
        all_perspectives = [basic, *active]
        plan_model = getattr(llm, "plan_model", llm.research_model)
        perspective_models = _perspective_models(selected, plan_model)
        notes: list[PerspectiveNoteV4] = []

        # Version and media boundaries are a fixed prerequisite, not a research
        # branch. Resolve them once with one bounded search and never carry the
        # basic perspective into the progressive follow-up loop.
        boundary, result = _call_json(
            llm, schema=FollowUpOutput, web_search=True, max_tool_calls=1,
            max_output_tokens=1200,
            payload={
                **base, "round": 1,
                "active_perspectives": [basic.model_dump()],
                "prior_notes": [],
            },
            instructions="""Confirm only the work identity, requested media/version boundary, creators, and the
scope that later research must not mix with adaptations or abridgements. Use at most one Web Search call. Return one
compact planning note. Do not branch into themes, plot analysis, character analysis, or additional questions.""",
        )
        input_tokens += result.input_tokens; output_tokens += result.output_tokens
        notes.extend(note for note in boundary.notes if note.perspective_title == basic.title)

        for round_number in range(1, FOLLOW_UP_ROUNDS + 1):
            if not active:
                break
            def follow_perspective(perspective):
                return _call_json(
                    llm, schema=FollowUpOutput, web_search=True, max_tool_calls=1,
                    max_output_tokens=1800,
                    payload={
                        **base, "round": round_number,
                        "active_perspectives": [perspective.model_dump()],
                        "prior_notes": [n.model_dump() for n in notes if n.perspective_title == perspective.title],
                    },
                    instructions="""Act as the Topic Expert for exactly one research perspective. Use its prior dialogue
to ask and answer the next progressive question. Convert the question into 1-3 suggested queries and use the available
Web Search only as bounded reconnaissance for outline planning. Stop when information gain is low or the branch repeats.
Return exactly one note with research intent, suggested future queries, URLs actually encountered, an explicitly
planning-only answer_note, leads, uncertainty, and the continue decision. Do not manufacture conclusions.""",
                )

            with ThreadPoolExecutor(max_workers=len(active)) as executor:
                results = list(executor.map(follow_perspective, active))
            for _, usage in results:
                input_tokens += usage.input_tokens; output_tokens += usage.output_tokens
            current = {p.title: p for p in active}
            batch = [
                note for followup, _ in results for note in followup.notes
                if note.perspective_title in current and note.round == round_number
            ]
            allowed_urls = {
                str((annotation.get("url_citation") or annotation).get("url"))
                for _, usage in results
                for annotation in getattr(usage, "annotations", [])
                if isinstance(annotation, dict) and (annotation.get("url_citation") or annotation).get("url")
            }
            if allowed_urls:
                batch = [note.model_copy(update={
                    "source_urls": [url for url in note.source_urls if url in allowed_urls],
                }) for note in batch]
            else:
                batch = [note.model_copy(update={"source_urls": []}) for note in batch]
            notes.extend(batch)
            active = [current[n.perspective_title] for n in batch if n.continue_research and n.expected_information_gain >= 3]

        synthesis, result = _call_json(
            llm, schema=SignatureSynthesisOutput, max_output_tokens=2400,
            payload={**base, "perspectives": [p.model_dump() for p in all_perspectives],
                     "research_notes": [n.model_dump() for n in notes]},
            instructions="""After research, merge duplicate notes and generate the outline as 1-3 signature research units.
Do not impose a feature taxonomy or entity/relation categories. Keep a direction when it adds a key connection or whole-
work understanding that the four generic modules cannot fully express, even if it crosses them. Reject only substantive
duplicates or directions the generic modules fully answer. Output exactly these fields per unit: title, scope,
why_generic_modules_are_insufficient, research_questions, known_leads, unresolved_points. Do not add fields.""",
        )
        input_tokens += result.input_tokens; output_tokens += result.output_tokens
        output = SupervisorPlanOutput(
            rationale=(
                "动态特色视角未显示出足够独立的信息增益，因此采用可取消的叙事结构备用视角；"
                if perspective_fallback_used else
                "先由 dossier 动态发现视角，经有限连续追问与检索后，从研究笔记事后归并特色大纲。"
            ),
            units=[*mandatory_units, *compile_signature_units(synthesis.units, budget)],
        )
        _validate_compiled_plan(output, budget)
        perspective_ids = {item.title: item.perspective_id for item in perspective_models}
        turns = [ResearchTurnV4(
            turn_id=f"turn-{index:03d}-{sha1((note.perspective_title + str(note.round)).encode('utf-8')).hexdigest()[:8]}",
            perspective_id=perspective_ids[note.perspective_title], question=note.question,
            research_intent=note.research_intent, suggested_queries=note.suggested_queries,
            provisional_answer=f"待验证假设：{note.answer_note}",
            unresolved_questions=note.unresolved, reconnaissance_source_urls=note.source_urls,
            status="continue" if note.continue_research else "complete",
            model=plan_model, prompt_version=PROMPT_VERSION,
        ) for index, note in enumerate(notes, start=1) if note.perspective_title in perspective_ids]
        research_outline = _compile_outline(
            kind="research", title=f"《{dossier.work.canonical_title}》研究增强大纲",
            units=output.units, notes=notes,
        )
        storm_planning = StormPlanningStateV4(
            perspectives=perspective_models, research_turns=turns,
            direct_outline=direct_outline, research_outline=research_outline,
        )
    except (ValidationError, ValueError) as error:
        raise RuntimeError(f"Supervisor Agent returned invalid signature research: {error}") from error
    return SupervisorRun(output=output, model=getattr(llm, "plan_model", llm.research_model), prompt_version=PROMPT_VERSION,
                         input_tokens=input_tokens, output_tokens=output_tokens,
                         storm_planning=storm_planning)
