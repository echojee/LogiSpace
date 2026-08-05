from __future__ import annotations

from uuid import uuid4

from logispace_domain.models_v4_runtime import ResearchRuntimeV4
from logispace_evaluation.models_v4 import EvaluationRunV4, MetricResultV4


def evaluate(job: ResearchRuntimeV4) -> EvaluationRunV4:
    units = list(job.units.values())
    mandatory_domains = {item.domain for item in job.plan.units if item.track == "mandatory"}
    coverage = len(mandatory_domains & {"relationships", "multiple_timelines", "tricks", "murder_methods"}) / 4
    actions = [action for unit in units if unit.finding_bundle for action in unit.finding_bundle.actions]
    duplicate_count = len(actions) - len({action.fingerprint for action in actions})
    invalid_actions = sum(action.result_summary.startswith("rejected:") for action in actions)
    invalid_rate = (invalid_actions + duplicate_count) / max(1, len(actions))
    queries = [query for unit in units if unit.finding_bundle for query in unit.finding_bundle.queries_executed]
    duplicate_query_rate = (len(queries) - len(set(queries))) / max(1, len(queries))
    evidence = [candidate for unit in units if unit.finding_bundle for candidate in [*unit.finding_bundle.evidence_candidates, *unit.finding_bundle.counterevidence_candidates]]
    snapshot_text = {snapshot_id: text for unit in units for snapshot_id, text in unit.snapshots.items()}
    exact_valid = sum(
        candidate.snapshot_id in snapshot_text and candidate.quote in snapshot_text[candidate.snapshot_id]
        for candidate in evidence
    ) / max(1, len(evidence))
    version_contamination = sum(candidate.media_version != job.brief.media_version for candidate in evidence) / max(1, len(evidence))
    open_web_actions = sum(
        action.action == "search_domains" and "open_web" in action.parameters.get("domains", [])
        for action in actions
    )
    open_web_ratio = open_web_actions / max(1, sum(action.action == "search_domains" for action in actions))
    high_priority = [unit for unit in job.plan.units if unit.priority >= 4]
    completed_high = sum(job.units[unit.unit_id].status == "verified" for unit in high_priority) / max(1, len(high_priority))
    projection_consistency = 1.0 if job.projection_audit and job.projection_audit.passed else 0.0
    metrics = [
        MetricResultV4(name="mandatory_coverage", value=coverage, target=1.0, passed=coverage == 1.0),
        MetricResultV4(name="exact_quote_validity", value=exact_valid, target=1.0, passed=exact_valid == 1.0),
        MetricResultV4(name="media_version_contamination", value=version_contamination, target=0.0, passed=version_contamination == 0.0),
        MetricResultV4(name="high_priority_unit_completion", value=completed_high, target=.8, passed=completed_high >= .8),
        MetricResultV4(name="invalid_or_duplicate_action_rate", value=invalid_rate, target=.15, passed=invalid_rate < .15),
        MetricResultV4(name="duplicate_query_rate", value=duplicate_query_rate, target=0.0, passed=duplicate_query_rate == 0.0),
        MetricResultV4(name="open_web_query_ratio", value=open_web_ratio, target=.1, passed=open_web_ratio <= .1),
        MetricResultV4(name="cross_projection_consistency", value=projection_consistency, target=1.0, passed=projection_consistency == 1.0),
    ]
    return EvaluationRunV4(evaluation_id=f"eval_{uuid4().hex[:12]}", job_id=job.job_id, metrics=metrics)
