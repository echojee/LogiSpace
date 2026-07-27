from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from logispace_domain.models import WorkDossier

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"
CATALOG_PATH = DATA_ROOT / "catalog.json"


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _catalog() -> dict:
    return _read_json(CATALOG_PATH)


@lru_cache(maxsize=None)
def get_dossier(work_id: str) -> WorkDossier | None:
    record = next((item for item in _catalog()["works"] if item["work_id"] == work_id), None)
    if record is None:
        return None
    manifest_path = DATA_ROOT / record["manifest"]
    manifest = _read_json(manifest_path)
    dossier_path = manifest_path.parent / "versions" / manifest["current_dossier_version"] / "dossier.json"
    dossier = WorkDossier.model_validate(_read_json(dossier_path))
    if dossier.work.work_id != manifest["work_id"]:
        raise ValueError(f"Dossier namespace mismatch for {work_id}")
    if dossier.dossier_version != manifest["current_dossier_version"]:
        raise ValueError(f"Dossier version mismatch for {work_id}")
    return dossier


def all_dossiers() -> list[WorkDossier]:
    dossiers = [get_dossier(item["work_id"]) for item in _catalog()["works"]]
    return [dossier for dossier in dossiers if dossier is not None]