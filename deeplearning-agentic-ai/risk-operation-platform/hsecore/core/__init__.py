# HSE Core Scoring Module
# Módulos principales del modelo de scoring HSE

from .models import (
    FeatureSpec,
    Row,
    RemediationTask,
    RemediationPlan,
    TimePenaltyInfo,
    ImprovementSignal,
    ScoreOutput,
    BayesianPrior,
)

from .scoring import (
    compute_gate_status,
    compute_risk_score,
    compute_trust_score,
    compute_stability_index,
    risk_bucket,
    trust_bucket,
    cell_5x5,
    escalation,
    top_drivers,
)

from .remediation import (
    ESCALATION_MATRIX_5X5,
    REMEDIATION_TASKS_CATALOG,
    generate_remediation_plan,
)

from .penalties import (
    compute_time_penalty,
    compute_improvement_signal,
    compute_severity_adjusted_score,
)

from .bayesian import (
    effective_events,
    bayes_event_rate_per_hour,
    prob_at_least_one_event_next_hours,
)

__all__ = [
    # Models
    "FeatureSpec", "Row", "RemediationTask", "RemediationPlan",
    "TimePenaltyInfo", "ImprovementSignal", "ScoreOutput", "BayesianPrior",
    # Scoring
    "compute_gate_status", "compute_risk_score", "compute_trust_score",
    "compute_stability_index", "risk_bucket", "trust_bucket", "cell_5x5",
    "escalation", "top_drivers",
    # Remediation
    "ESCALATION_MATRIX_5X5", "REMEDIATION_TASKS_CATALOG", "generate_remediation_plan",
    # Penalties
    "compute_time_penalty", "compute_improvement_signal", "compute_severity_adjusted_score",
    # Bayesian
    "effective_events", "bayes_event_rate_per_hour", "prob_at_least_one_event_next_hours",
]
