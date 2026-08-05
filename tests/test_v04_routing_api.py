from fastapi.testclient import TestClient

from app.main_v4_phase2 import app

client = TestClient(app)


def test_source_registry_and_pack_versions_are_exposed():
    registry = client.get("/research/v4/source-registry")
    packs = client.get("/research/v4/source-packs")
    assert registry.status_code == 200
    assert registry.json()["version"] == "source-registry-v0.4.0"
    assert len(registry.json()["entries"]) >= 10
    assert packs.status_code == 200
    assert packs.json()["version"] == "mystery-source-packs-v0.4.0"
    assert len(packs.json()["packs"]) == 10
