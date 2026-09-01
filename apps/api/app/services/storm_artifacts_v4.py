from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from logispace_domain.models_v4_runtime import ResearchRuntimeV4
from logispace_domain.models_v4_storm import StageArtifactV4

STAGE_ORDER = ["perspective", "research_dialogue", "outline", "search_and_draft", "polish", "deposit"]


def invalidate_downstream(job: ResearchRuntimeV4, from_stage: str) -> None:
    downstream = set(STAGE_ORDER[STAGE_ORDER.index(from_stage) + 1:])
    job.stage_artifacts = [
        item.model_copy(update={"status": "stale"})
        if item.stage in downstream and item.status == "valid" else item
        for item in job.stage_artifacts
    ]


def _hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _data_root(runtime_root: Path) -> Path:
    # Production ROOT is data/runtime/research_v4; tests commonly replace it
    # with tmp/runtime. Both resolve to a sibling works directory.
    if runtime_root.name == "research_v4" and runtime_root.parent.name == "runtime":
        return runtime_root.parents[1]
    return runtime_root.parent


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def materialize_planning_artifacts(job: ResearchRuntimeV4, runtime_root: Path,
                                   changed_stages: set[str] | None = None) -> Path:
    if job.storm_planning is None:
        raise ValueError("STORM planning state is required")
    run_root = _data_root(runtime_root) / "works" / job.work.work_id / "research" / job.job_id
    planning = job.storm_planning
    perspectives = [item.model_dump(mode="json") for item in planning.perspectives]
    turns = [item.model_dump(mode="json") for item in planning.research_turns]
    direct = planning.direct_outline.model_dump(mode="json")
    research = planning.research_outline.model_dump(mode="json")
    now = datetime.now(timezone.utc)
    model = planning.perspectives[0].model
    prompt_version = planning.research_outline.prompt_version
    perspective_artifact = StageArtifactV4(
        artifact_id=f"artifact-perspective-{_hash(perspectives)[:12]}", stage="perspective",
        input_hash=_hash({"work": job.work.model_dump(mode="json"), "brief": job.brief.model_dump(mode="json")}),
        output_hash=_hash(perspectives), model=model, prompt_version=prompt_version,
        completed_at=now, files={"perspectives": "perspectives/perspectives.json"},
    )
    dialogue_artifact = StageArtifactV4(
        artifact_id=f"artifact-dialogue-{_hash(turns)[:12]}", stage="research_dialogue",
        input_artifact_ids=[perspective_artifact.artifact_id], input_hash=perspective_artifact.output_hash,
        output_hash=_hash(turns), model=model, prompt_version=prompt_version,
        completed_at=now, files={"turns": "dialogues/research_turns.json"},
    )
    outline_artifact = StageArtifactV4(
        artifact_id=f"artifact-outline-{_hash(research)[:12]}", stage="outline",
        input_artifact_ids=[perspective_artifact.artifact_id, dialogue_artifact.artifact_id],
        input_hash=_hash({"direct": direct, "turns": turns}), output_hash=_hash(research),
        model=model, prompt_version=prompt_version, completed_at=now,
        files={
            "direct_json": "outline/direct_outline.json", "direct_markdown": "outline/direct_outline.md",
            "research_json": "outline/research_outline.json", "research_markdown": "outline/research_outline.md",
        },
    )
    planning_stages = changed_stages or {"perspective", "research_dialogue", "outline"}
    prior = [
        item.model_copy(update={"status": "stale"}) if item.stage in planning_stages and item.status == "valid" else item
        for item in job.stage_artifacts
    ]
    generated = [perspective_artifact, dialogue_artifact, outline_artifact]
    job.stage_artifacts = [*prior, *(item for item in generated if item.stage in planning_stages)]
    _write(run_root / "perspectives/perspectives.json", json.dumps(perspectives, ensure_ascii=False, indent=2))
    _write(run_root / "dialogues/research_turns.json", json.dumps(turns, ensure_ascii=False, indent=2))
    _write(run_root / "outline/direct_outline.json", json.dumps(direct, ensure_ascii=False, indent=2))
    _write(run_root / "outline/direct_outline.md", planning.direct_outline.markdown)
    _write(run_root / "outline/research_outline.json", json.dumps(research, ensure_ascii=False, indent=2))
    _write(run_root / "outline/research_outline.md", planning.research_outline.markdown)
    # Immutable copies preserve prior versions even when the stable current
    # paths are updated by an explicit rerun or human memo edit.
    _write(run_root / f"_artifacts/{perspective_artifact.artifact_id}/perspectives.json", json.dumps(perspectives, ensure_ascii=False, indent=2))
    _write(run_root / f"_artifacts/{dialogue_artifact.artifact_id}/research_turns.json", json.dumps(turns, ensure_ascii=False, indent=2))
    _write(run_root / f"_artifacts/{outline_artifact.artifact_id}/direct_outline.json", json.dumps(direct, ensure_ascii=False, indent=2))
    _write(run_root / f"_artifacts/{outline_artifact.artifact_id}/direct_outline.md", planning.direct_outline.markdown)
    _write(run_root / f"_artifacts/{outline_artifact.artifact_id}/research_outline.json", json.dumps(research, ensure_ascii=False, indent=2))
    _write(run_root / f"_artifacts/{outline_artifact.artifact_id}/research_outline.md", planning.research_outline.markdown)
    manifest = {
        "run_id": job.job_id, "work_id": job.work.work_id,
        "stage_order": STAGE_ORDER,
        "current_artifacts": {item.stage: item.artifact_id for item in job.stage_artifacts if item.status == "valid"},
        "artifacts": [item.model_dump(mode="json") for item in job.stage_artifacts],
    }
    _write(run_root / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    _write(run_root / "runtime.json", job.model_dump_json(indent=2))
    return run_root

