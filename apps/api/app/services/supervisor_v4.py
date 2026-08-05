from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.llm import LLMGateway, gateway
from app.services.planning_protocols_v4 import MANDATORY_DOMAINS, compile_mandatory_units
from app.services.signature_planning_v4 import SignatureCandidateV4, compile_signature_units
from logispace_domain.models import WorkDossier
from logispace_domain.models_v4 import (
    CoverageDecisionV4,
    ResearchBriefV4,
    ResearchBudgetV4,
    ResearchStrategyV4,
    ResearchUnitV4,
)
from logispace_domain.models_v4_memo import ReconnaissanceBriefV4

PROMPT_VERSION = "supervisor-plan-v0.5.0"


class SignatureProposalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rationale: str = Field(min_length=1, max_length=500)
    candidates: list[SignatureCandidateV4] = Field(min_length=1, max_length=5)


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


def _dossier_context(dossier: WorkDossier) -> dict:
    return {
        "work": dossier.work.model_dump(mode="json"),
        "dossier_version": dossier.dossier_version,
        "entity_type_counts": {
            kind: sum(item.entity_type == kind for item in dossier.entities)
            for kind in sorted({item.entity_type for item in dossier.entities})
        },
        "relation_count": len(dossier.relations),
        "revision_findings": dossier.revision_findings[:8],
    }


def _validate_compiled_plan(output: SupervisorPlanOutput, budget: ResearchBudgetV4) -> None:
    mandatory = [unit for unit in output.units if unit.track == "mandatory"]
    if len(mandatory) != 4 or {unit.domain for unit in mandatory} != set(MANDATORY_DOMAINS):
        raise ValueError("Compiled plan must contain the four mandatory protocols")
    signatures = [unit for unit in output.units if unit.track == "signature"]
    if not 1 <= len(signatures) <= 3:
        raise ValueError("Compiled plan must contain between one and three signature units")
    if len({unit.unit_id for unit in output.units}) != len(output.units):
        raise ValueError("Compiled plan contains duplicate unit ids")
    if any(unit.budget.max_queries > budget.signature_flexible_queries for unit in signatures):
        raise ValueError("Signature unit exceeds the flexible query budget")


def generate_plan(
    *,
    brief: ResearchBriefV4,
    dossier: WorkDossier,
    coverage: list[CoverageDecisionV4],
    budget: ResearchBudgetV4,
    reconnaissance: ReconnaissanceBriefV4 | None = None,
    strategy: ResearchStrategyV4 = "build_and_verify",
    llm: LLMGateway = gateway,
) -> SupervisorRun:
    if not llm.available:
        raise RuntimeError("OPENAI_API_KEY is required for Supervisor Agent planning")
    mandatory_units = compile_mandatory_units(coverage=coverage, budget=budget, strategy=strategy)
    instructions = f"""You are the LogiSpace signature-research planner. Propose candidate questions only.
The four mandatory protocols (relationships, timelines, tricks, murder methods) are already compiled by code.
Find one to five distinctive research candidates for this selected work. Do not repeat a mandatory protocol.
A candidate should explain something important and distinctive about how this work creates its effect.
Write question and why_it_matters for a general reader, in concrete Chinese, as one main question.
The question must be understandable in ten seconds, end with a question mark, and contain at most two concepts
being compared. Never mention Event, Entity, schema, ontology, JSON, database ids, fields, object granularity,
or internal knowledge-base operations. Avoid lists of mechanisms joined into one question.
research_focus contains one to three small execution steps hidden from the user. expected_answer describes the
kind of answer sought without asserting facts. Score every candidate from 1 to 5. mandatory_overlap and
execution_complexity are penalties, so higher means worse. Prefer evidence-feasible questions and do not force
three directions when only one is strong. Use only the selected medium; never compare adaptations unless asked.
Return JSON matching the supplied schema and no factual conclusions. Prompt version: {PROMPT_VERSION}."""
    payload = {
        "brief": brief.model_dump(mode="json"),
        "strategy": strategy,
        "current_dossier_summary": _dossier_context(dossier),
        "mandatory_questions_already_covered": [unit.question for unit in mandatory_units],
        "reconnaissance": ({
            "summary": reconnaissance.summary,
            "structure_signals": reconnaissance.structure_signals,
            "candidate_features": reconnaissance.candidate_features,
            "open_questions": reconnaissance.open_questions,
        } if reconnaissance else None),
    }
    try:
        raw, result = llm.respond_json(
            instructions=instructions,
            input_text=json.dumps(payload, ensure_ascii=False),
            research=True,
            max_output_tokens=2200,
            reasoning_effort="low",
            verbosity="low",
            response_schema=SignatureProposalOutput.model_json_schema(),
        )
        proposal = SignatureProposalOutput.model_validate(raw)
        signature_units = compile_signature_units(proposal.candidates, budget)
        output = SupervisorPlanOutput(
            rationale=proposal.rationale,
            units=[*mandatory_units, *signature_units],
        )
        _validate_compiled_plan(output, budget)
    except (ValidationError, ValueError) as error:
        raise RuntimeError(f"Supervisor Agent returned invalid signature candidates: {error}") from error
    return SupervisorRun(
        output=output,
        model=llm.research_model,
        prompt_version=PROMPT_VERSION,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )