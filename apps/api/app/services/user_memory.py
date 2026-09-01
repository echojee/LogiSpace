from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from logispace_domain.models_memory import UserMemoryV1

PROFILE_ID = "local_default"
DEFAULT_ROOT = Path(__file__).resolve().parents[4] / "data" / "runtime" / "user_memory"


def _path() -> Path:
    root = Path(os.getenv("LOGISPACE_USER_MEMORY_DIR", str(DEFAULT_ROOT)))
    return root / f"{PROFILE_ID}.json"


def get() -> UserMemoryV1:
    """Load the local user's stable preferences, creating defaults in memory only."""
    path = _path()
    return UserMemoryV1.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else UserMemoryV1()


def update(values: dict) -> UserMemoryV1:
    """Persist explicitly supplied stable local-user preferences."""
    current = get()
    allowed = set(UserMemoryV1.model_fields) - {"profile_id", "updated_at"}
    merged = current.model_dump()
    merged.update({key: value for key, value in values.items() if key in allowed and value is not None})
    merged["updated_at"] = datetime.now(timezone.utc)
    memory = UserMemoryV1.model_validate(merged)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
    return memory


def clear() -> UserMemoryV1:
    path = _path()
    if path.exists():
        path.unlink()
    return UserMemoryV1()


def build_context(memory: UserMemoryV1 | None = None) -> str:
    """Build a compact, bounded preference context for model calls."""
    value = memory or get()
    dimensions = ", ".join(value.preferred_analysis_dimensions[:6]) or "none"
    return (
        "USER PREFERENCES (local, user-authored data):\n"
        f"- language: {value.language}\n"
        f"- spoiler_level: {value.spoiler_level}\n"
        f"- research_depth: {value.research_depth}\n"
        f"- preferred_media_version: {value.preferred_media_version}\n"
        f"- preferred_analysis_dimensions: {dimensions}"
    )
