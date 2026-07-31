from __future__ import annotations

import os
from pathlib import Path
from threading import RLock
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
_LOCK = RLock()
_DEFAULT_ROOT = Path(__file__).resolve().parents[4] / "data" / "runtime"


class JsonStore:
    def __init__(self, namespace: str) -> None:
        root = Path(os.getenv("LOGISPACE_RUNTIME_DIR", str(_DEFAULT_ROOT)))
        self.root = root / namespace

    def save(self, key: str, value: BaseModel) -> None:
        with _LOCK:
            self.root.mkdir(parents=True, exist_ok=True)
            target = self.root / f"{key}.json"
            temporary = target.with_suffix(".tmp")
            temporary.write_text(value.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(target)

    def load(self, key: str, model: type[T]) -> T | None:
        target = self.root / f"{key}.json"
        if not target.exists():
            return None
        with _LOCK:
            return model.model_validate_json(target.read_text(encoding="utf-8"))

    def list(self, model: type[T]) -> list[T]:
        if not self.root.exists():
            return []
        with _LOCK:
            return [model.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(self.root.glob("*.json"))]
