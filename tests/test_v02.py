from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_conversation_keeps_work_memory_and_refuses_unscoped_unknowns():
    created = client.post("/conversations", json={"spoiler_level": "full"}).json()
    conversation_id = created["conversation_id"]
    first = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"content": "\u300a\u5acc\u7591\u4ebaX\u7684\u732e\u8eab\u300b\u4e2d\u77f3\u795e\u662f\u8c01\uff1f", "allow_web_search": False},
    )
    assert first.status_code == 200
    assert first.json()["used_work_ids"] == ["devotion-of-suspect-x"]
    saved = client.get(f"/conversations/{conversation_id}").json()
    assert saved["memory"]["active_work_ids"] == ["devotion-of-suspect-x"]
    assert len(saved["messages"]) == 2

    unknown = client.post("/conversations", json={}).json()
    response = client.post(
        f"/conversations/{unknown['conversation_id']}/messages",
        json={"content": "\u798f\u5c14\u6469\u65af\u548c\u534e\u751f\u662f\u4ec0\u4e48\u5173\u7cfb\uff1f", "allow_web_search": False},
    )
    assert response.json()["answer_status"] == "insufficient"
    assert response.json()["used_work_ids"] == []


def test_deep_research_creates_incremental_draft_and_proposals():
    response = client.post(
        "/research",
        json={
            "work_id": "murder-of-roger-ackroyd",
            "research_scope": "incremental_full",
            "budget": {"max_search_rounds": 2, "max_sources": 5, "max_model_tokens": 10000},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_review"
    assert body["base_version"] == "0.1.0"
    assert body["target_version"] == "0.2.0"
    assert body["draft"]["work"]["work_id"] == "murder-of-roger-ackroyd"
    assert body["coverage"]
    assert body["proposals"]
    assert body["sources"]
