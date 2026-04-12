"""
HSE Scoring Models - Estructuras de datos del sistema
=====================================================

Contiene todas las dataclasses y tipos utilizados en el modelo de scoring HSE.
Similar a entidades/DTOs en un modelo bancario de scoring crediticio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FeatureSpec:
    """
    Definición extensible de características para scoring.
    Permite agregar nuevas variables CSV sin modificar código.
    
    kind:
      - count: conteo raw (bueno o malo)
      - rate_per_1000h: conteo normalizado por horas
      - flag: 0/1 binario
      - delay_days: días de retraso (mayor es peor o mejor según direction)
      - ratio: valor 0..1 o 0..100
      
    direction:
      - "bad": mayor valor = más riesgo
      - "good": mayor valor = menos riesgo
      
    when_missing:
      - "neutral": ignorar
      - "zero": tratar como 0
      - "penalize": aplicar penalización
    """
    name: str
    kind: str
    weight: float = 1.0
    cap: float = 9999.0
    direction: str = "bad"
    when_missing: str = "neutral"


@dataclass
class Row:
    """
    Registro mensual de un contratista.
    Estructura base que puede venir de CSV, DB, o API.
    """
    contractor: str
    month: str  # YYYY-MM
    hours: float
    operated: int
    monthly_close_submitted: int
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BayesianPrior:
    """
    Prior Gamma(alpha, beta) para tasa de eventos por HORA.
    E[lambda] = alpha / beta.
    beta tiene unidades de horas.
    
    Valores por defecto calibrados para industria típica HSE.
    """
    alpha: float = 0.7
    beta: float = 7000.0  # ~ fuerza del prior en horas


@dataclass
class RemediationTask:
    """
    Tarea de remediación individual con plazo y prioridad.
    Similar a una acción correctiva en un plan de mejora.
    """
    task_id: str
    description: str
    priority: str  # URGENTE, ALTA, MEDIA, BAJA
    deadline_days: int
    category: str  # DOCUMENTAL, OPERACIONAL, FORMACION, VERIFICACION
    weight_improvement: float  # Puntos de mejora si se cumple


@dataclass
class RemediationPlan:
    """
    Plan de remediación completo para un contratista.
    Similar a un plan de pago en scoring crediticio.
    
    - NO es remediación inmediata
    - Incluye checkpoints para validar mejora progresiva
    - Tiene objetivos medibles
    """
    target_risk_reduction: float
    target_trust_increase: float
    max_days_to_improve: int
    tasks: List[RemediationTask]
    checkpoint_days: List[int]  # Días para evaluar mejora
    expected_improvement_pct: float  # % mejora esperada por checkpoint


@dataclass
class TimePenaltyInfo:
    """
    Información de penalización temporal.
    Funciona como "mora" en scoring bancario:
    - Entre más tiempo sin actuar, mayor penalización
    - La penalización decae con buen comportamiento
    """
    days_without_report: int
    days_in_critical: int
    cumulative_penalty: float
    penalty_reason: str
    decay_rate: float  # Reducción por mes de buen comportamiento (ej: 0.15 = 15%)


@dataclass
class ImprovementSignal:
    """
    Señales de mejora progresiva.
    Detecta si el contratista está mejorando, estable o empeorando.
    Similar a la tendencia de pago en crédito.
    """
    trend_direction: str  # IMPROVING, STABLE, WORSENING
    improvement_score: float  # -100 a +100
    consecutive_good_months: int
    milestones_achieved: List[str]
    next_milestone: str
    days_to_milestone: int


@dataclass
class ScoreOutput:
    """
    Resultado completo del scoring para un contratista.
    Contiene todos los scores, buckets, y recomendaciones.
    
    Es el "buró de crédito HSE" del contratista.
    """
    contractor: str
    month: str
    gate_status: str
    risk_score: float
    trust_score: float
    stability_index: float
    risk_bucket: str
    trust_bucket: str
    cell_5x5: str
    escalation_level: int
    escalation_action: str
    drivers_top3: List[str]
    # Campos HSE Scoring extendido
    remediation_plan: Optional[RemediationPlan] = None
    time_penalty: Optional[TimePenaltyInfo] = None
    improvement_signal: Optional[ImprovementSignal] = None
    severity_adjusted_score: float = 0.0
    recommended_review_days: int = 30
    probability_incident_30d: float = 0.0
