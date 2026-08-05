from logispace_domain import dossiers
from logispace_domain.models_v4 import ResearchBriefV4, ResearchBudgetV4, ResearchPlanRevisionV4
from logispace_domain.models_v4_projection import ProjectionAuditV4
from logispace_domain.models_v4_runtime import ResearchRuntimeV4, UnitCheckpointV4
from logispace_evaluation.run_eval_v4 import evaluate
from app.services import research_v4


def test_v04_evaluation_reports_deterministic_release_metrics():
    dossier = dossiers.get_dossier("murder-of-roger-ackroyd")
    budget = ResearchBudgetV4()
    domains = ("relationships", "multiple_timelines", "tricks", "murder_methods")
    units = [research_v4._mandatory_unit(domain, budget) for domain in domains]
    plan = ResearchPlanRevisionV4(
        coverage=[research_v4._coverage(dossier, domain) for domain in domains],
        units=units, budget=budget, rationale="recorded", approved=True,
    )
    job = ResearchRuntimeV4(
        job_id="job_eval", work=dossier.work, brief=ResearchBriefV4(work_id=dossier.work.work_id),
        status="needs_review", plan=plan,
        units={unit.unit_id: UnitCheckpointV4(research_unit_id=unit.unit_id, status="verified") for unit in units},
        projection_audit=ProjectionAuditV4(passed=True),
    )
    metrics = {metric.name: metric for metric in evaluate(job).metrics}
    assert metrics["mandatory_coverage"].value == 1
    assert metrics["high_priority_unit_completion"].value == 1
    assert metrics["media_version_contamination"].value == 0
    assert metrics["open_web_query_ratio"].value == 0
    assert metrics["cross_projection_consistency"].passed is True
