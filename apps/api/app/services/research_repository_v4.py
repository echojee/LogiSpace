from __future__ import annotations

import os
import json
from pathlib import Path
from threading import RLock
from typing import Protocol

from logispace_domain.models_v4_runtime import ExecutionCheckpointV1, ResearchRuntimeV4

ROOT = Path(os.getenv("LOGISPACE_RUNTIME_DIR", Path(__file__).resolve().parents[4] / "data" / "runtime")) / "research_v4"
LOCK = RLock()


class ResearchRuntimeRepository(Protocol):
    """Persistence contract used by the v4 research runtime."""

    def save_runtime(self, job: ResearchRuntimeV4) -> None: ...
    def load_runtime(self, job_id: str) -> ResearchRuntimeV4 | None: ...
    def list_runtimes(self) -> list[ResearchRuntimeV4]: ...
    def append_checkpoint(self, checkpoint: ExecutionCheckpointV1) -> None: ...
    def list_checkpoints(self, job_id: str) -> list[ExecutionCheckpointV1]: ...


class JsonResearchRuntimeRepository:
    """Atomic JSON runtime snapshots plus an append-only checkpoint journal."""

    @property
    def root(self) -> Path:
        return ROOT

    def save_runtime(self, job: ResearchRuntimeV4) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{job.job_id}.json"
        temporary = self.root / f".{job.job_id}.tmp"
        with LOCK:
            job.state_version += 1
            temporary.write_text(job.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(target)

    def load_runtime(self, job_id: str) -> ResearchRuntimeV4 | None:
        target = self.root / f"{job_id}.json"
        if not target.exists():
            return None
        with LOCK:
            return ResearchRuntimeV4.model_validate_json(target.read_text(encoding="utf-8"))

    def list_runtimes(self) -> list[ResearchRuntimeV4]:
        if not self.root.exists():
            return []
        with LOCK:
            paths = [path for path in self.root.glob("*.json") if not path.name.endswith(".checkpoints.json")]
            return [ResearchRuntimeV4.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True)]

    def append_checkpoint(self, checkpoint: ExecutionCheckpointV1) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{checkpoint.job_id}.checkpoints.jsonl"
        with LOCK:
            with target.open("a", encoding="utf-8") as stream:
                stream.write(checkpoint.model_dump_json() + "\n")

    def list_checkpoints(self, job_id: str) -> list[ExecutionCheckpointV1]:
        target = self.root / f"{job_id}.checkpoints.jsonl"
        if not target.exists():
            return []
        with LOCK:
            return [ExecutionCheckpointV1.model_validate(json.loads(line)) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]


_repository = JsonResearchRuntimeRepository()


def save(job: ResearchRuntimeV4) -> None:
    _repository.save_runtime(job)


def load(job_id: str) -> ResearchRuntimeV4 | None:
    return _repository.load_runtime(job_id)


def list_jobs() -> list[ResearchRuntimeV4]:
    return _repository.list_runtimes()


def append_checkpoint(checkpoint: ExecutionCheckpointV1) -> None:
    _repository.append_checkpoint(checkpoint)


def list_checkpoints(job_id: str) -> list[ExecutionCheckpointV1]:
    return _repository.list_checkpoints(job_id)
