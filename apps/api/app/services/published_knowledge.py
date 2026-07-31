from __future__ import annotations
import json
from pathlib import Path
from logispace_domain import dossiers
from logispace_domain.models_v3 import KnowledgePackageV3,ResearchReportV3

def _version_dir(work_id:str)->Path|None:
    record=next((item for item in dossiers._catalog()["works"] if item["work_id"]==work_id),None)
    if not record:return None
    manifest_path=dossiers.DATA_ROOT/record["manifest"]
    if not manifest_path.exists():return None
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"));return manifest_path.parent/"versions"/manifest["current_dossier_version"]
def knowledge_package(work_id:str)->KnowledgePackageV3|None:
    root=_version_dir(work_id);path=root/"knowledge-package.json" if root else None
    return KnowledgePackageV3.model_validate_json(path.read_text(encoding="utf-8")) if path and path.exists() else None
def report(work_id:str)->ResearchReportV3|None:
    root=_version_dir(work_id);path=root/"report.json" if root else None
    return ResearchReportV3.model_validate_json(path.read_text(encoding="utf-8")) if path and path.exists() else None
