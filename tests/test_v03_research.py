import time
from pathlib import Path
from uuid import uuid4
import pytest
from app.main import app
from fastapi.testclient import TestClient
from logispace_domain.models_v3 import ClaimV3,EvidenceV3
client=TestClient(app)

def wait_job(job_id):
    for _ in range(150):
        body=client.get(f"/research/jobs/{job_id}").json()
        if body["status"] not in {"searching","reading","extracting","verifying","proposing","reflecting","drafting","retrying"}:return body
        time.sleep(.02)
    raise AssertionError("job did not settle")

@pytest.fixture
def recorded_extractor(monkeypatch):
    from app.services import research_v3
    monkeypatch.setattr(research_v3.gateway,"api_key","recorded-test-key")
    def fake(title,media,items,ranked):
        evidence=[];claims=[]
        for item in items:
            candidates=ranked.get(item.section,[])
            if not candidates:continue
            chunk=candidates[0].chunk;quote=chunk.content[:min(100,len(chunk.content))]
            ev=EvidenceV3(evidence_id=f"ev_{uuid4().hex[:10]}",snapshot_id=chunk.snapshot_id,source_id=chunk.source_id,section=item.section,locator=chunk.locator|{"chunk_id":chunk.chunk_id},quote=quote,relevance_score=.9)
            evidence.append(ev);claims.append(ClaimV3(claim_id=f"claim_{uuid4().hex[:10]}",section=item.section,text="A source-grounded recorded claim.",evidence_ids=[ev.evidence_id],support_status="supported",media_version=media))
        return evidence,claims,{"input_tokens":120,"output_tokens":40,"model_calls":1}
    monkeypatch.setattr(research_v3,"extract_batch",fake)
    monkeypatch.setattr(research_v3,"verify_batch",lambda claims,evidence:(claims,{"input_tokens":60,"output_tokens":20,"model_calls":1},[]))

def make_page(path:Path):
    path.write_text("<html><body><main><p>The Murder of Roger Ackroyd was written by Agatha Christie. This sufficiently long recorded paragraph verifies that LogiSpace reads source body text, stores an immutable snapshot, retrieves a relevant chunk, and preserves exact evidence quotations.</p></main></body></html>",encoding="utf-8")

def test_v03_plan_gate_recorded_body_and_evidence_chain(tmp_path,recorded_extractor):
    page=tmp_path/"source.html";make_page(page)
    created=client.post("/research/jobs",json={"work_id":"murder-of-roger-ackroyd","source_urls":[page.as_uri()],"budget":{"max_sources":2,"max_queries":2}})
    assert created.status_code==202;body=created.json();assert body["status"]=="awaiting_plan_approval"
    approved=client.post(f"/research/jobs/{body['job_id']}/plan/approve",json={"items":body["plan"]["items"][:1]});assert approved.status_code==200
    done=wait_job(body["job_id"]);assert done["status"]=="needs_review";assert done["usage"]["model_calls"]==2
    ev=done["evidence"][0];snap=done["snapshots"][0];assert ev["quote"] in snap["content"];assert "chunk_id" in ev["locator"]
    assert done["claims"][0]["support_status"]=="supported";assert done["proposals"][0]["payload"]
    report=client.get(f"/research/jobs/{body['job_id']}/report");package=client.get(f"/research/jobs/{body['job_id']}/knowledge-package");assert report.status_code==200;assert report.json()["sections"];assert package.status_code==200;assert package.json()["characters"]

def test_v03_no_model_preserves_sources_without_fake_claims(tmp_path,monkeypatch):
    from app.services import research_v3
    monkeypatch.setattr(research_v3.gateway,"api_key","")
    page=tmp_path/"source.html";make_page(page)
    created=client.post("/research/jobs",json={"work_id":"murder-on-orient-express","source_urls":[page.as_uri()]}).json()
    client.post(f"/research/jobs/{created['job_id']}/plan/approve",json={"items":created["plan"]["items"][:1]})
    done=wait_job(created["job_id"]);assert done["status"]=="partially_completed";assert done["snapshots"];assert done["claims"]==[];assert any("OPENAI_API_KEY" in e for e in done["errors"])
    assert client.post(f"/research/jobs/{created['job_id']}/publish").status_code==409

def test_v03_no_readable_body_cannot_publish():
    created=client.post("/research/jobs",json={"work_id":"murder-on-orient-express","source_urls":["file:///definitely/missing.html"]}).json();client.post(f"/research/jobs/{created['job_id']}/plan/approve",json={})
    done=wait_job(created["job_id"]);assert done["status"]=="partially_completed";assert client.post(f"/research/jobs/{created['job_id']}/publish").status_code==409

def test_v03_new_work_starts_at_zero_baseline():
    response=client.post("/research/jobs",json={"work":{"work_id":"new-film-test","canonical_title":"New Film","media_type":"film"}});assert response.status_code==202;body=response.json();assert body["base_version"]=="0.0.0";assert body["target_version"]=="0.1.0"

def test_v03_review_applies_payload_and_publishes_real_diff(tmp_path,monkeypatch,recorded_extractor):
    from app.services import research_v3
    page=tmp_path/"publish.html";make_page(page)
    created=client.post("/research/jobs",json={"work_id":"murder-of-roger-ackroyd","source_urls":[page.as_uri()]}).json();client.post(f"/research/jobs/{created['job_id']}/plan/approve",json={"items":created["plan"]["items"][:1]})
    done=wait_job(created["job_id"]);proposal=done["proposals"][0];client.post(f"/research/jobs/{created['job_id']}/review",json={"approved_proposal_ids":[proposal["proposal_id"]]})
    root=tmp_path/"data";root.mkdir();(root/"catalog.json").write_text('{"catalog_version":"0.1.0","works":[]}',encoding="utf-8");monkeypatch.setattr(research_v3,"DATA",root)
    published=client.post(f"/research/jobs/{created['job_id']}/publish");assert published.status_code==200;assert published.json()["diff"]["added_entities"]==1
    version=root/"works"/"murder-of-roger-ackroyd"/"versions"/"0.2.0";assert (version/"report.json").exists();assert (version/"knowledge-package.json").exists()
