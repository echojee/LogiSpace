from app.services.research_synthesis import build_package,build_report
from logispace_domain import dossiers
from logispace_domain.models import SpoilerLevel
from logispace_domain.models_v3 import ClaimV3

def test_report_and_knowledge_package_are_two_views_of_verified_claims():
    baseline=dossiers.get_dossier("murder-of-roger-ackroyd")
    claims=[ClaimV3(claim_id="c-trick",section="trick_misdirection",text="The narration omits a decisive action.",evidence_ids=["ev-1"],support_status="supported"),ClaimV3(claim_id="c-time",section="timeline_narrative",text="The decisive interval is compressed.",evidence_ids=["ev-2"],support_status="supported")]
    report=build_report(baseline.work,"0.2.0",claims);package=build_package(baseline.work,"0.2.0",baseline,claims)
    assert {s.section_id for s in report.sections}=={"trick_misdirection","timeline_narrative"}
    assert package.characters and package.relationships
    assert any(x.claim_ids==["c-trick"] for x in package.tricks)
    assert any(x.track=="narrative" and x.claim_ids==["c-time"] for x in package.timeline)
