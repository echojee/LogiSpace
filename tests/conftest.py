import pytest

from app.services import orchestrator_v4
from logispace_domain.models_v4_memo import ReconnaissanceBriefV4


@pytest.fixture
def stub_reconnaissance(monkeypatch):
    def fake(**kwargs):
        work = kwargs["dossier"].work
        return ReconnaissanceBriefV4(
            summary=f"Reconnaissance for {work.canonical_title}",
            edition_scope="original work",
            candidate_features=["recorded feature"],
        )

    monkeypatch.setattr(orchestrator_v4, "run_reconnaissance", fake)
    return fake
