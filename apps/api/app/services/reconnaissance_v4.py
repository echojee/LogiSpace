from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.llm import JSONResponseError, LLMGateway, gateway
from logispace_domain.models import WorkDossier
from logispace_domain.models_v4 import ResearchBriefV4
from logispace_domain.models_v4_memo import ReconnaissanceBriefV4

PROMPT_VERSION = "reconnaissance-v0.5.0"
CACHE_ROOT = Path(os.getenv("LOGISPACE_RUNTIME_DIR", Path(__file__).resolve().parents[4] / "data" / "runtime")) / "reconnaissance_v4"

INSTRUCTIONS = f"""You are the LogiSpace mystery-work scout. Produce a small planning brief, not a report.
The work identity and medium in the input have already been selected. Accept them as the research boundary.
Focus on how the selected work operates: puzzle shape, narrative and information structure, clue and
misdirection mechanisms, character-group dynamics, spatial or temporal constraints, and distinctive themes.
Do not spend searches reconfirming an unambiguous identity. If the supplied title, creator, year, and medium
conflict, report that single conflict in open_questions instead of researching version history.
Record only the selected medium and one stable locator strategy. Do not research ISBNs, printings,
publishers, translation history, bibliographic variants, or adaptation genealogy unless the user requested it.
Never search film or television adaptations when the selected medium is a novel. Use at most two targeted web
searches. Return at most 4 short structure signals, 4 work-specific feature hypotheses,
5 useful sources, 2 contamination warnings, and 3 open questions. Every source must be a real URL encountered
in this run. Do not establish final plot conclusions. Return only data matching the supplied JSON schema.
Prompt version: {PROMPT_VERSION}."""


class ReconAgentSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    url: str
    role: str


class ReconAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=1200)
    edition_scope: str = Field(max_length=300)
    structure_signals: list[str] = Field(max_length=4)
    candidate_features: list[str] = Field(min_length=1, max_length=4)
    primary_text_options: list[str] = Field(max_length=2)
    location_strategy: str = Field(max_length=300)
    contamination_risks: list[str] = Field(max_length=2)
    open_questions: list[str] = Field(max_length=3)
    sources: list[ReconAgentSource] = Field(max_length=5)


class ReconnaissanceFormatError(RuntimeError):
    pass


def _normalized_identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"[\s《》〈〉『』「」·:：_\-]+", "", normalized)


def _pipeline_fingerprint(brief: ResearchBriefV4, dossier: WorkDossier, llm: LLMGateway) -> str:
    prompt_hash = hashlib.sha256(INSTRUCTIONS.encode("utf-8")).hexdigest()
    schema_hash = hashlib.sha256(json.dumps(ReconAgentOutput.model_json_schema(), sort_keys=True).encode("utf-8")).hexdigest()
    identity = {
        "title": _normalized_identity(dossier.work.canonical_title),
        "media_type": dossier.work.media_type.value,
        "creators": sorted(_normalized_identity(item) for item in dossier.work.creators),
        "release_year": dossier.work.release_year,
    }
    payload = {
        "identity": identity,
        "media_version": brief.media_version,
        "goal": brief.user_goal,
        "prompt_hash": prompt_hash,
        "schema_hash": schema_hash,
        "model": llm.research_model,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _cache_path(brief: ResearchBriefV4, dossier: WorkDossier, llm: LLMGateway = gateway) -> Path:
    return CACHE_ROOT / f"{_pipeline_fingerprint(brief, dossier, llm)[:20]}.json"


def _load_cache(path: Path) -> ReconnaissanceBriefV4 | None:
    if not path.exists():
        return None
    try:
        value = ReconnaissanceBriefV4.model_validate_json(path.read_text(encoding="utf-8"))
        return value if value.prompt_version == PROMPT_VERSION else None
    except (OSError, ValidationError, ValueError):
        return None


def _payload(brief: ResearchBriefV4, dossier: WorkDossier) -> dict:
    return {
        "brief": brief.model_dump(mode="json"),
        "work": dossier.work.model_dump(mode="json"),
        "current_dossier": {
            "version": dossier.dossier_version,
            "entity_types": sorted({item.entity_type for item in dossier.entities}),
            "revision_findings": dossier.revision_findings,
        },
    }


def _request_output(*, brief: ResearchBriefV4, dossier: WorkDossier, llm: LLMGateway) -> ReconAgentOutput:
    schema = ReconAgentOutput.model_json_schema()
    try:
        raw, _ = llm.respond_json(
            instructions=INSTRUCTIONS,
            input_text=json.dumps(_payload(brief, dossier), ensure_ascii=False),
            research=True,
            web_search=True,
            max_tool_calls=2,
            max_output_tokens=2500,
            reasoning_effort="low",
            verbosity="low",
            response_schema=schema,
        )
    except JSONResponseError as first_error:
        try:
            raw, _ = llm.respond_json(
                instructions=(
                    "Repair the supplied malformed reconnaissance response into the requested JSON schema. "
                    "Preserve only information already present. Do not browse, add facts, URLs, or explanations."
                ),
                input_text=json.dumps({"malformed_response": first_error.raw_text}, ensure_ascii=False),
                research=True,
                max_output_tokens=2500,
                reasoning_effort="low",
                verbosity="low",
                response_schema=schema,
            )
        except (JSONResponseError, RuntimeError, ValidationError) as repair_error:
            raise ReconnaissanceFormatError(
                f"Reconnaissance Agent returned malformed structured output after one repair attempt: {repair_error}"
            ) from repair_error
    try:
        return ReconAgentOutput.model_validate(raw)
    except ValidationError as error:
        raise ReconnaissanceFormatError(f"Reconnaissance Agent returned invalid structured output: {error}") from error


def run_reconnaissance(
    *, brief: ResearchBriefV4, dossier: WorkDossier, llm: LLMGateway = gateway,
) -> ReconnaissanceBriefV4:
    if not llm.available:
        raise RuntimeError("OPENAI_API_KEY is required for preliminary reconnaissance")
    cache_path = _cache_path(brief, dossier, llm)
    cached = _load_cache(cache_path)
    if cached is not None:
        return cached
    output = _request_output(brief=brief, dossier=dossier, llm=llm)
    result = ReconnaissanceBriefV4(
        **output.model_dump(), model=llm.research_model, prompt_version=PROMPT_VERSION,
    )
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(cache_path)
    return result