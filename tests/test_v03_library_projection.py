from pathlib import Path
from app.main import app
from fastapi.testclient import TestClient
from logispace_domain.models_v3 import KnowledgePackageV3,ResearchReportV3,ReportSectionV3,TrickEntryV3,MurderMethodEntryV3
client=TestClient(app)

def test_library_projects_published_knowledge_package(tmp_path,monkeypatch):
    from app.services import published_knowledge
    package=KnowledgePackageV3(package_id="p",work_id="murder-of-roger-ackroyd",version="0.2.0",tricks=[TrickEntryV3(trick_id="t-new",name="Narrative omission",mechanism="A decisive action is omitted.")],murder_methods=[MurderMethodEntryV3(method_id="m-new",name="Recorded time disguise",execution="A recording shifts the apparent time.")])
    report=ResearchReportV3(report_id="r",work_id="murder-of-roger-ackroyd",version="0.2.0",title="Research Report",summary="Summary",sections=[ReportSectionV3(section_id="identity",title="Overview",body="Body")])
    (tmp_path/"knowledge-package.json").write_text(package.model_dump_json(),encoding="utf-8");(tmp_path/"report.json").write_text(report.model_dump_json(),encoding="utf-8")
    monkeypatch.setattr(published_knowledge,"_version_dir",lambda work_id:tmp_path)
    tricks=client.get("/library/tricks").json();methods=client.get("/library/methods").json();published_report=client.get("/library/works/murder-of-roger-ackroyd/report")
    assert any(x["entity_id"]=="t-new" for x in tricks);assert any(x["entity_id"]=="m-new" for x in methods);assert published_report.status_code==200
