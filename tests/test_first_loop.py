from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_three_works_are_equal_primary_databases():
    response = client.get("/dossiers")
    assert response.status_code == 200
    dossiers = response.json()
    assert len(dossiers) == 3
    assert {item["dataset_role"] for item in dossiers} == {"primary"}


def test_each_database_generates_four_product_views():
    for work_id in ["devotion-of-suspect-x", "murder-of-roger-ackroyd", "murder-on-orient-express"]:
        response = client.get(f"/dossiers/{work_id}/views")
        assert response.status_code == 200
        assert {item["view_type"] for item in response.json()} == {"knowledge_graph", "multi_track_timeline", "mystery_mechanism", "solution_adjudication"}


def test_golden_qa_is_grounded_in_selected_source_database():
    response = client.post("/dossiers/qa", json={"question_id": "oe-q-collective", "source_work_ids": ["murder-on-orient-express"]})
    assert response.status_code == 200
    assert response.json()["passed"] is True
    assert response.json()["evidence_entity_ids"] == ["oe-jury", "oe-sequence"]


def test_ontology_revision_closes_the_loop():
    response = client.get("/dossiers/ontology/revision")
    assert response.status_code == 200
    assert response.json()["source_database_count"] == 3
    assert response.json()["schema_version"] == "0.2"
    assert response.json()["status"] == "closed"


def test_each_work_is_loaded_from_its_own_versioned_asset():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "data" / "works"
    work_ids = {item["work"]["work_id"] for item in client.get("/dossiers").json()}
    for work_id in work_ids:
        manifest = root / work_id / "manifest.json"
        dossier = root / work_id / "versions" / "0.1.0" / "dossier.json"
        assert manifest.exists()
        assert dossier.exists()
        assert work_id in dossier.read_text(encoding="utf-8")

def test_chat_retrieves_relationships_with_traceable_links():
    response = client.post("/chat/query", json={"question": "《嫌疑人X的献身》中石神和靖子是什么关系？", "source_work_ids": ["devotion-of-suspect-x"]})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "character_relationship"
    assert "石神哲哉" in body["answer"]
    assert body["source_work_ids"] == ["devotion-of-suspect-x"]
    assert body["links"][0]["href"].endswith("/relationships")


def test_library_exposes_works_timelines_tricks_and_methods():
    assert len(client.get("/library/works").json()) == 3
    assert client.get("/library/works/devotion-of-suspect-x/relationships").json()["edges"]
    assert client.get("/library/works/murder-of-roger-ackroyd/timeline").json()["items"]
    assert len(client.get("/library/tricks").json()) == 2
    assert len(client.get("/library/methods").json()) == 3