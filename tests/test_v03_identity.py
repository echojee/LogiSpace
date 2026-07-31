from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_known_work_resolves_without_confirmation():
    response = client.post("/works/resolve", json={"query": "罗杰疑案", "media_type": "novel"})
    assert response.status_code == 200
    body = response.json()
    assert body["needs_confirmation"] is False
    assert body["resolved_work"]["work_id"] == "murder-of-roger-ackroyd"


def test_unknown_work_only_requires_title_and_type():
    response = client.post("/works/resolve", json={"query": "一部数据库外的新作品", "media_type": "film"})
    assert response.status_code == 200
    body = response.json()
    assert body["needs_confirmation"] is False
    assert body["resolved_work"]["canonical_title"] == "一部数据库外的新作品"
    assert body["resolved_work"]["media_type"] == "film"
    assert body["resolved_work"]["creators"] == []
    assert body["resolved_work"]["release_year"] is None


def test_confirmation_rejects_candidate_outside_resolution():
    resolved = client.post("/works/resolve", json={"query": "罗杰疑案", "media_type": "novel"}).json()
    response = client.post(
        f"/works/resolve/{resolved['resolution_id']}/confirm",
        json={"work_id": "not-a-candidate"},
    )
    assert response.status_code == 422


def test_multiple_candidates_require_confirmation(monkeypatch):
    from app.services import work_resolution
    from logispace_domain.models import MediaType, Work, WorkDossier

    def dossier(work_id: str, author: str, year: int) -> WorkDossier:
        return WorkDossier(
            work=Work(work_id=work_id, canonical_title="同名作品", aliases=[], media_type=MediaType.FILM, release_year=year, creators=[author]),
            entities=[], relations=[], golden_questions=[],
        )

    monkeypatch.setattr(work_resolution.dossier_repository, "all_dossiers", lambda: [dossier("same-a", "作者甲", 1999), dossier("same-b", "作者乙", 2024)])
    response = client.post("/works/resolve", json={"query": "同名作品", "media_type": "film"})
    body = response.json()
    assert body["needs_confirmation"] is True
    assert body["resolved_work"] is None
    assert {item["work_id"] for item in body["candidates"]} == {"same-a", "same-b"}

    confirmed = client.post(f"/works/resolve/{body['resolution_id']}/confirm", json={"work_id": "same-b"})
    assert confirmed.status_code == 200
    assert confirmed.json()["resolved_work"]["work_id"] == "same-b"
