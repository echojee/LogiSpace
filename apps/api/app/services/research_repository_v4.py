from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from logispace_domain.models_v4_runtime import ResearchRuntimeV4

ROOT = Path(os.getenv("LOGISPACE_RUNTIME_DIR", Path(__file__).resolve().parents[4] / "data" / "runtime")) / "research_v4"
LOCK = RLock()


def save(job: ResearchRuntimeV4) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / f"{job.job_id}.json"
    temporary = ROOT / f".{job.job_id}.tmp"
    with LOCK:
        temporary.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)


def load(job_id: str) -> ResearchRuntimeV4 | None:
    target = ROOT / f"{job_id}.json"
    if not target.exists():
        return None
    with LOCK:
        return ResearchRuntimeV4.model_validate_json(target.read_text(encoding="utf-8"))


def list_jobs() -> list[ResearchRuntimeV4]:
    if not ROOT.exists():
        return []
    with LOCK:
        return [ResearchRuntimeV4.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(ROOT.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)]
