from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main_v4 import app
from app.services import orchestrator_v4, research_repository_v4, research_v4
from logispace_domain.models_v4_memo import ReconnaissanceBriefV4

client = TestClient(app)
MANDATORY = {"relationships", "multiple_timelines", "tricks", "murder_methods"}


@pytest.fixture(autouse=True)
def planning_agents(monkeypatch, tmp_path):
    monkeypatch.setattr(research_repository_v4, "ROOT", tmp_path / "research_v4")
    monkeypatch.setattr(orchestrator_v4, "run_reconnaissance", lambda **kwargs: ReconnaissanceBriefV4(
        summary="Recorded reconnaissance",
        edition_scope="original work",
        candidate_features=["unreliable narration"],
    ))

    def generate(**kwargs):
        budget = kwargs["budget"]
        dossier = kwargs["dossier"]
        units = [research_v4._mandatory_unit(domain, budget) for domain in orchestrator_v4.MANDATORY]
        units.extend(research_v4._signature_units(dossier, budget))
        return SimpleNamespace(
            output=SimpleNamespace(units=units, rationale="Recorded agent plan"),
            model="recorded-supervisor", prompt_version="recorded-prompt",
        )

    monkeypatch.setattr(orchestrator_v4, "generate_plan", generate)


def create_planned(payload: dict) -> tuple[dict, dict]:
    response = client.post("/research/v4/jobs", json=payload)
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "created"
    assert accepted["plan"] is None
    planned = client.get(f"/research/v4/jobs/{accepted['job_id']}").json()
    assert planned["status"] == "awaiting_plan_approval"
    return accepted, planned


def test_v04_roger_ackroyd_generates_dual_track_plan():
    _, body = create_planned({
        "work_id": "murder-of-roger-ackroyd",
        "brief": {
            "work_id": "murder-of-roger-ackroyd",
            "user_goal": "全面理解作品的诡计结构",
        },
    })
    assert body["strategy"] == "review_strengthen_and_correct"
    assert {item["domain"] for item in body["plan"]["coverage"]} == MANDATORY
    mandatory = [item for item in body["plan"]["units"] if item["track"] == "mandatory"]
    signature = [item for item in body["plan"]["units"] if item["track"] == "signature"]
    assert {item["domain"] for item in mandatory} == MANDATORY
    assert signature[0]["unit_id"] == "ru_signature_unreliable_narration"
    assert signature[0]["evidence_requirements"]["requires_primary_source"] is True
    assert body["plan"]["budget"]["verification_reserve_ratio"] == 0.2


def test_v04_plan_approval_is_a_hard_gate():
    accepted, _ = create_planned({"work_id": "murder-of-roger-ackroyd"})
    approved = client.post(
        f"/research/v4/jobs/{accepted['job_id']}/plan/approve", json={}
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "searching"
    assert body["plan"]["approved"] is True
    assert all(item["status"] == "approved" for item in body["plan"]["units"])
    assert client.post(
        f"/research/v4/jobs/{accepted['job_id']}/plan/approve", json={}
    ).status_code == 409


def test_v04_rejects_plan_that_drops_a_mandatory_unit():
    accepted, planned = create_planned({"work_id": "murder-of-roger-ackroyd"})
    units = [
        item for item in planned["plan"]["units"]
        if item["domain"] != "murder_methods"
    ]
    response = client.post(
        f"/research/v4/jobs/{accepted['job_id']}/plan/approve",
        json={"units": units},
    )
    assert response.status_code == 422
    assert client.get(
        f"/research/v4/jobs/{accepted['job_id']}"
    ).json()["status"] == "awaiting_plan_approval"


def test_v04_rejects_brief_for_another_work():
    response = client.post(
        "/research/v4/jobs",
        json={
            "work_id": "murder-of-roger-ackroyd",
            "brief": {"work_id": "murder-on-orient-express"},
        },
    )
    assert response.status_code == 422