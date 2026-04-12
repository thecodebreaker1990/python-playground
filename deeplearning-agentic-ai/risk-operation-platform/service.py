from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from hsecore.core.bayesian import (
    bayes_event_rate_per_hour,
    prob_at_least_one_event_next_hours,
)
from hsecore.core.models import (
    BayesianPrior,
    FeatureSpec,
    Row,
    ScoreOutput,
)
from hsecore.core.penalties import (
    compute_improvement_signal,
    compute_severity_adjusted_score,
    compute_time_penalty,
)
from hsecore.core.remediation import (
    ESCALATION_MATRIX_5X5,
    generate_remediation_plan,
)
from hsecore.core.scoring import (
    cell_5x5,
    compute_gate_status,
    compute_risk_score,
    compute_stability_index,
    compute_trust_score,
    escalation,
    risk_bucket,
    top_drivers,
    trust_bucket,
)


@dataclass(frozen=True)
class ContractorContext:
    contractor: str
    history: List[Row]
    last3: List[Row]
    latest: Row


@dataclass(frozen=True)
class BaseScoreResult:
    gate_status: str
    risk_score: float
    trust_score: float
    stability_index: float
    risk_contribs: List[tuple[str, float]]
    trust_contribs: List[tuple[str, float]]
    drivers_top3: List[str]


@dataclass(frozen=True)
class ClassificationResult:
    risk_bucket: str
    trust_bucket: str
    cell_5x5: str
    escalation_level: int
    escalation_action: str
    recommended_review_days: int


@dataclass(frozen=True)
class EnrichmentResult:
    remediation_plan: object
    time_penalty: object
    improvement_signal: object
    severity_adjusted_score: float
    probability_incident_30d: float


def group_rows_by_contractor(rows: List[Row]) -> Dict[str, List[Row]]:
    """Group all monthly rows by contractor name."""
    grouped: Dict[str, List[Row]] = {}
    for row in rows:
        grouped.setdefault(row.contractor, []).append(row)
    return grouped


def build_contractor_context(contractor: str, rows: List[Row]) -> ContractorContext:
    """Prepare a normalized scoring context for one contractor."""
    history = sorted(rows, key=lambda row: row.month)
    last3 = history[-3:]
    latest = last3[-1]
    return ContractorContext(
        contractor=contractor,
        history=history,
        last3=last3,
        latest=latest,
    )


def compute_contractor_scores(
    context: ContractorContext,
    risk_features: List[FeatureSpec],
    trust_features: List[FeatureSpec],
    explain: bool = True,
) -> BaseScoreResult:
    """Compute the base gate, risk, trust, stability, and optional drivers."""
    gate_status = compute_gate_status(context.latest)
    risk_score, risk_contribs = compute_risk_score(context.last3, risk_features)
    trust_score, trust_contribs = compute_trust_score(context.last3, trust_features)
    stability_index = compute_stability_index(context.last3, risk_score, trust_score)
    drivers = top_drivers(risk_contribs + trust_contribs, 3) if explain else []
    return BaseScoreResult(
        gate_status=gate_status,
        risk_score=risk_score,
        trust_score=trust_score,
        stability_index=stability_index,
        risk_contribs=risk_contribs,
        trust_contribs=trust_contribs,
        drivers_top3=drivers,
    )


def classify_contractor_score(
    context: ContractorContext,
    scores: BaseScoreResult,
) -> ClassificationResult:
    """Assign buckets, matrix cell, escalation, and review cadence."""
    escalation_level, escalation_action = escalation(
        scores.gate_status,
        scores.risk_score,
        scores.trust_score,
        context.latest.hours,
    )

    matrix_cell = cell_5x5(scores.trust_score, scores.risk_score)
    matrix_info = ESCALATION_MATRIX_5X5.get(matrix_cell, {})

    if matrix_info:
        escalation_level = matrix_info.get("level", escalation_level)
        escalation_action = matrix_info.get("action", escalation_action)

    return ClassificationResult(
        risk_bucket=risk_bucket(scores.risk_score),
        trust_bucket=trust_bucket(scores.trust_score),
        cell_5x5=matrix_cell,
        escalation_level=escalation_level,
        escalation_action=escalation_action,
        recommended_review_days=matrix_info.get("review_days", 30),
    )


def enrich_contractor_score(
    context: ContractorContext,
    scores: BaseScoreResult,
    classification: ClassificationResult,
    risk_features: List[FeatureSpec],
    trust_features: List[FeatureSpec],
    prior: BayesianPrior | None = None,
) -> EnrichmentResult:
    """Compute remediation, time effects, trend, and Bayesian probability."""
    time_penalty = compute_time_penalty(context.history, context.latest.month)
    improvement_signal = compute_improvement_signal(
        context.history,
        risk_features,
        trust_features,
    )
    remediation_plan = generate_remediation_plan(
        classification.cell_5x5,
        scores.risk_score,
        scores.trust_score,
        scores.drivers_top3,
    )
    severity_adjusted_score = compute_severity_adjusted_score(
        scores.risk_score,
        scores.trust_score,
        time_penalty,
    )

    lam, _, _ = bayes_event_rate_per_hour(context.history, prior or BayesianPrior())
    probability_incident_30d = prob_at_least_one_event_next_hours(
        lam,
        context.latest.hours * 1.0,
    )

    return EnrichmentResult(
        remediation_plan=remediation_plan,
        time_penalty=time_penalty,
        improvement_signal=improvement_signal,
        severity_adjusted_score=severity_adjusted_score,
        probability_incident_30d=probability_incident_30d,
    )


def build_score_output(
    context: ContractorContext,
    scores: BaseScoreResult,
    classification: ClassificationResult,
    enrichment: EnrichmentResult,
) -> ScoreOutput:
    """Assemble the final ScoreOutput DTO."""
    return ScoreOutput(
        contractor=context.contractor,
        month=context.latest.month,
        gate_status=scores.gate_status,
        risk_score=round(scores.risk_score, 1),
        trust_score=round(scores.trust_score, 1),
        stability_index=round(scores.stability_index, 1),
        risk_bucket=classification.risk_bucket,
        trust_bucket=classification.trust_bucket,
        cell_5x5=classification.cell_5x5,
        escalation_level=classification.escalation_level,
        escalation_action=classification.escalation_action,
        drivers_top3=scores.drivers_top3,
        remediation_plan=enrichment.remediation_plan,
        time_penalty=enrichment.time_penalty,
        improvement_signal=enrichment.improvement_signal,
        severity_adjusted_score=round(enrichment.severity_adjusted_score, 1),
        recommended_review_days=classification.recommended_review_days,
        probability_incident_30d=round(enrichment.probability_incident_30d * 100, 1),
    )


def score_contractor(
    contractor: str,
    rows: List[Row],
    risk_features: List[FeatureSpec],
    trust_features: List[FeatureSpec],
    explain: bool = True,
    prior: BayesianPrior | None = None,
) -> ScoreOutput:
    """Run the full scoring pipeline for a single contractor."""
    context = build_contractor_context(contractor, rows)
    scores = compute_contractor_scores(
        context,
        risk_features,
        trust_features,
        explain=explain,
    )
    classification = classify_contractor_score(context, scores)
    enrichment = enrich_contractor_score(
        context,
        scores,
        classification,
        risk_features,
        trust_features,
        prior=prior,
    )
    return build_score_output(context, scores, classification, enrichment)


def score_latest_per_contractor(
    rows: List[Row],
    risk_features: List[FeatureSpec],
    trust_features: List[FeatureSpec],
    explain: bool = True,
    prior: BayesianPrior | None = None,
) -> List[ScoreOutput]:
    """
    Score each contractor using its latest available month.

    This service keeps orchestration thin by composing small scoring steps.
    """
    outputs: List[ScoreOutput] = []
    for contractor, contractor_rows in group_rows_by_contractor(rows).items():
        outputs.append(
            score_contractor(
                contractor,
                contractor_rows,
                risk_features,
                trust_features,
                explain=explain,
                prior=prior,
            )
        )
    return outputs
