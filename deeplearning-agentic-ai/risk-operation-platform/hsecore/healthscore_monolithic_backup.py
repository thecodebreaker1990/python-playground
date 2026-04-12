# amatia_model.py
from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from datetime import datetime, timedelta


# ---------------------------
# Config / Types
# ---------------------------

@dataclass(frozen=True)
class FeatureSpec:
    """
    Extensible feature definition. Add new optional CSV columns by adding a spec.
    kind:
      - count: raw count (bad or good)
      - rate_per_1000h: count normalized by hours (expects row has hours + column value)
      - flag: 0/1
      - delay_days: higher is worse (or better if direction="good")
      - ratio: expects value 0..1 (or 0..100, you decide; normalize in extractor)
    direction:
      - "bad": higher means worse -> increases risk or decreases trust
      - "good": higher means better -> decreases risk or increases trust
    when_missing:
      - "neutral": ignore
      - "zero": treat as 0
      - "penalize": apply a penalty (used mainly for trust)
    """
    name: str
    kind: str
    weight: float = 1.0
    cap: float = 9999.0
    direction: str = "bad"
    when_missing: str = "neutral"


@dataclass
class Row:
    contractor: str
    month: str  # YYYY-MM
    hours: float
    operated: int
    monthly_close_submitted: int
    # all other columns stored here
    extra: Dict[str, Any]


@dataclass
class RemediationTask:
    """Tarea de remediación con plazo y prioridad"""
    task_id: str
    description: str
    priority: str  # URGENTE, ALTA, MEDIA, BAJA
    deadline_days: int
    category: str  # DOCUMENTAL, OPERACIONAL, FORMACION, VERIFICACION
    weight_improvement: float  # Puntos de mejora si se cumple


@dataclass
class RemediationPlan:
    """Plan de remediación completo para un contratista"""
    target_risk_reduction: float
    target_trust_increase: float
    max_days_to_improve: int
    tasks: List[RemediationTask]
    checkpoint_days: List[int]  # Días para evaluar mejora
    expected_improvement_pct: float  # % mejora esperada por checkpoint


@dataclass
class TimePenaltyInfo:
    """Información de penalización temporal"""
    days_without_report: int
    days_in_critical: int
    cumulative_penalty: float
    penalty_reason: str
    decay_rate: float  # Cuánto se reduce la penalización por mes de buen comportamiento


@dataclass
class ImprovementSignal:
    """Señales de mejora progresiva"""
    trend_direction: str  # IMPROVING, STABLE, WORSENING
    improvement_score: float  # -100 a +100
    consecutive_good_months: int
    milestones_achieved: List[str]
    next_milestone: str
    days_to_milestone: int


@dataclass
class ScoreOutput:
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
    # Nuevos campos HSE Scoring
    remediation_plan: Optional[RemediationPlan] = None
    time_penalty: Optional[TimePenaltyInfo] = None
    improvement_signal: Optional[ImprovementSignal] = None
    severity_adjusted_score: float = 0.0  # Score ajustado por tiempo/penalizaciones
    recommended_review_days: int = 30
    probability_incident_30d: float = 0.0


# ---------------------------
# Utilities
# ---------------------------

def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default

def _to_int(x: Any, default: int = 0) -> int:
    try:
        if x is None or x == "":
            return default
        return int(float(x))
    except Exception:
        return default

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------
# Core scoring
# ---------------------------

def compute_gate_status(row: Row) -> str:
    # Minimal MVP gates: docs_blocked/docs_at_risk if present.
    blocked = _to_int(row.extra.get("docs_blocked", 0), 0)
    at_risk = _to_int(row.extra.get("docs_at_risk", 0), 0)

    if blocked >= 1:
        return "BLOCKED"
    if at_risk >= 1:
        return "AT_RISK"
    return "OK"


def _extract_feature_value(row: Row, spec: FeatureSpec) -> Optional[float]:
    """
    Convert row.extra[spec.name] into a normalized numeric signal, or None.
    """
    raw = row.extra.get(spec.name, None)

    if raw is None or raw == "":
        if spec.when_missing == "zero":
            raw_val = 0.0
        elif spec.when_missing == "penalize":
            # return a penalty marker; the scorer will handle it
            return float("nan")
        else:
            return None
    else:
        raw_val = _to_float(raw, default=0.0)

    hours = max(row.hours, 1.0)

    if spec.kind == "count":
        val = raw_val
    elif spec.kind == "rate_per_1000h":
        val = (raw_val / hours) * 1000.0
    elif spec.kind == "flag":
        val = 1.0 if raw_val >= 1 else 0.0
    elif spec.kind == "delay_days":
        val = raw_val
    elif spec.kind == "ratio":
        # Accept either 0..1 or 0..100; normalize to 0..1
        val = raw_val / 100.0 if raw_val > 1.5 else raw_val
    else:
        # Unknown kinds are ignored safely
        return None

    return clamp(val, 0.0, spec.cap)


def compute_risk_score(rows_last3: List[Row], risk_features: List[FeatureSpec]) -> Tuple[float, List[Tuple[str, float]]]:
    """
    Risk score 0–100 (higher = more risk).
    Uses last 3 months for stability and trend.
    Returns (risk_score, contributions).
    """
    if not rows_last3:
        return 0.0, []

    last = rows_last3[-1]
    contribs: List[Tuple[str, float]] = []

    # Base: events weighted if present (keep simple & explainable)
    # You can also define these via FeatureSpec; keeping explicit is fine for MVP.
    recordables = _to_float(last.extra.get("recordables", 0), 0.0)
    lti = _to_float(last.extra.get("lti", 0), 0.0)
    hipo = _to_float(last.extra.get("hipo", 0), 0.0)

    hours3 = max(sum(r.hours for r in rows_last3), 1.0)
    events_eff = recordables + 3.0 * lti + 2.0 * hipo
    event_rate = (events_eff / hours3) * 1000.0  # per 1000h

    risk = min(60.0, event_rate * 18.0)
    contribs.append(("event_rate_per_1000h", risk))

    # Backlog penalties (critical overdue)
    crit_overdue = _to_float(last.extra.get("critical_overdue", 0), 0.0)
    overdue = _to_float(last.extra.get("actions_overdue", 0), 0.0)

    c1 = min(25.0, crit_overdue * 3.5)
    c2 = min(10.0, overdue * 0.8)
    risk += c1 + c2
    contribs.append(("critical_overdue", c1))
    contribs.append(("actions_overdue", c2))

    # Trend: last vs previous events_eff
    if len(rows_last3) >= 2:
        prev = rows_last3[-2]
        prev_eff = _to_float(prev.extra.get("recordables", 0), 0.0) + 3.0*_to_float(prev.extra.get("lti",0),0.0) + 2.0*_to_float(prev.extra.get("hipo",0),0.0)
        if events_eff > prev_eff:
            risk += 5.0
            contribs.append(("trend_worsening", 5.0))

    # Optional extra risk features
    for spec in risk_features:
        val = _extract_feature_value(last, spec)
        if val is None:
            continue
        # direction: bad increases risk, good decreases risk
        sign = 1.0 if spec.direction == "bad" else -1.0
        add = sign * (spec.weight * val)
        # Keep optional features from dominating
        add = clamp(add, -10.0, 10.0)
        risk += add
        contribs.append((spec.name, add))

    return clamp(risk, 0.0, 100.0), contribs


def compute_trust_score(rows_last3: List[Row], trust_features: List[FeatureSpec]) -> Tuple[float, List[Tuple[str, float]]]:
    """
    Trust score 0–100 (higher = more trust).
    Returns (trust_score, contributions).
    """
    if not rows_last3:
        return 0.0, []

    last = rows_last3[-1]
    t = 70.0
    contribs: List[Tuple[str, float]] = [("base", 70.0)]

    close = last.monthly_close_submitted
    if close == 0:
        t -= 25.0
        contribs.append(("missing_monthly_close", -25.0))

    # Rejections
    rejected = _to_float(last.extra.get("rejected_reports", 0), 0.0)
    rej_pen = -min(15.0, rejected * 7.5)
    t += rej_pen
    if rejected:
        contribs.append(("rejected_reports", rej_pen))

    # Underreporting heuristic (simple)
    exec_crit = _to_float(last.extra.get("exec_crit_findings", 0), 0.0)
    lti = _to_float(last.extra.get("lti", 0), 0.0)
    hipo = _to_float(last.extra.get("hipo", 0), 0.0)
    recordables = _to_float(last.extra.get("recordables", 0), 0.0)

    if exec_crit >= 2 and (recordables + lti + hipo) == 0:
        t -= 10.0
        contribs.append(("discrepancy_exec_vs_self", -10.0))

    # Bonus: consistent closes last 3
    if sum(r.monthly_close_submitted for r in rows_last3) == len(rows_last3):
        t += 5.0
        contribs.append(("consistent_closes_bonus", +5.0))

    # Optional extra trust features (telemetry, delays, etc.)
    for spec in trust_features:
        val = _extract_feature_value(last, spec)
        if val is None:
            continue
        if math.isnan(val):
            # penalize missing
            t -= abs(spec.weight) * 5.0
            contribs.append((f"{spec.name}_missing_penalty", -abs(spec.weight) * 5.0))
            continue

        # For trust: direction="bad" reduces trust, "good" increases trust
        sign = -1.0 if spec.direction == "bad" else 1.0
        add = sign * (spec.weight * val)
        add = clamp(add, -12.0, 12.0)
        t += add
        contribs.append((spec.name, add))

    return clamp(t, 0.0, 100.0), contribs


def compute_stability_index(rows_last3: List[Row], risk_score: float, trust_score: float) -> float:
    """
    0–100 where higher means less stable / more concerning.
    MVP: blend inverse trust + risk + worsening signals.
    """
    inv_trust = (100.0 - trust_score) / 100.0
    r = risk_score / 100.0
    s = 100.0 * (0.55 * r + 0.45 * inv_trust)
    # Optional: add a small bump if last month worsened
    if len(rows_last3) >= 2:
        last = rows_last3[-1]
        prev = rows_last3[-2]
        last_eff = _to_float(last.extra.get("recordables", 0), 0.0) + 3.0*_to_float(last.extra.get("lti",0),0.0) + 2.0*_to_float(last.extra.get("hipo",0),0.0)
        prev_eff = _to_float(prev.extra.get("recordables", 0), 0.0) + 3.0*_to_float(prev.extra.get("lti",0),0.0) + 2.0*_to_float(prev.extra.get("hipo",0),0.0)
        if last_eff > prev_eff:
            s += 5.0
    return clamp(s, 0.0, 100.0)


def risk_bucket(r: float) -> str:
    if r < 35: return "LOW"
    if r < 60: return "MOD"
    if r < 80: return "HIGH"
    return "CRIT"

def trust_bucket(t: float) -> str:
    if t < 50: return "LOW"
    if t < 75: return "MED"
    return "HIGH"

def cell_5x5(trust: float, risk: float) -> str:
    # bins: 0-20,20-40,40-60,60-80,80-100
    def b(x: float) -> int:
        if x < 20: return 1
        if x < 40: return 2
        if x < 60: return 3
        if x < 80: return 4
        return 5
    return f"R{b(risk)}-T{b(trust)}"


# ---------------------------
# Bayesian event-rate (Poisson-Gamma) - Moved here for dependencies
# ---------------------------

@dataclass(frozen=True)
class BayesianPrior:
    """
    Gamma(alpha, beta) prior for event rate per HOUR.
    E[lambda] = alpha / beta.
    beta has units of hours.
    """
    alpha: float = 0.7
    beta: float = 7000.0  # ~ prior strength in hours


def effective_events(row: Row) -> float:
    """
    Convert different event types into a single 'effective event count'.
    Tune weights to your domain (HSE committee can validate these).
    """
    recordables = _to_float(row.extra.get("recordables", 0), 0.0)
    lti = _to_float(row.extra.get("lti", 0), 0.0)
    hipo = _to_float(row.extra.get("hipo", 0), 0.0)
    # Example weights: LTI > HiPo > recordable
    return recordables + 3.0 * lti + 2.0 * hipo


def bayes_event_rate_per_hour(rows: List[Row], prior: BayesianPrior) -> Tuple[float, float, float]:
    """
    Posterior for lambda (events per hour), using Poisson likelihood and Gamma prior.

    Returns:
      lambda_hat: posterior mean alpha/beta
      alpha_post
      beta_post
    """
    alpha = prior.alpha
    beta = prior.beta

    for r in rows:
        alpha += effective_events(r)
        beta += max(r.hours, 0.0)

    lam = alpha / max(beta, 1e-9)
    return lam, alpha, beta


def prob_at_least_one_event_next_hours(lambda_per_hour: float, next_hours: float) -> float:
    """
    Poisson probability of >=1 event given rate and exposure.
    P(N>=1) = 1 - exp(-lambda * hours)
    """
    next_hours = max(next_hours, 0.0)
    return 1.0 - math.exp(-lambda_per_hour * next_hours)


def escalation(row_gate: str, risk: float, trust: float, hours_month: float) -> Tuple[int, str]:
    # 1..4
    if row_gate == "BLOCKED":
        return 4, "Escalar al Administrador del Contrato + bloquear operación; generar solicitud obligatoria."
    if risk >= 80:
        return 4, "Escalar al Administrador del Contrato; intervención inmediata (riesgo crítico)."
    if trust < 40 and hours_month >= 500:
        return 3, "Agentic: plan de señal de vida + verificación ligera; generar solicitud; seguimiento semanal."
    if risk >= 60:
        return 3, "Agentic: plan semanal (3 tareas) + crear acciones críticas; seguimiento semanal."
    if row_gate == "AT_RISK":
        return 2, "Guided: checklist de vencimientos + borrador de solicitud."
    if trust < 60:
        return 2, "Guided: mejorar consistencia (cierre mensual + verificación mínima); recordatorios."
    return 1, "Nudge: mantener. Metas ligeras y resumen semanal."


# ---------------------------
# HSE SCORING MODEL - MATRIZ DE REMEDIACIÓN
# ---------------------------

# Matriz 5x5: Define acciones según combinación Risk (filas) vs Trust (columnas)
# Risk: 1=Muy Bajo (0-20), 2=Bajo (20-40), 3=Moderado (40-60), 4=Alto (60-80), 5=Crítico (80-100)
# Trust: 1=Muy Bajo (0-20), 2=Bajo (20-40), 3=Medio (40-60), 4=Alto (60-80), 5=Muy Alto (80-100)

ESCALATION_MATRIX_5X5: Dict[str, Dict[str, Any]] = {
    # RIESGO CRÍTICO (80-100)
    "R5-T1": {"level": 5, "urgency": "CRITICO", "review_days": 1, 
              "action": "SUSPENSIÓN INMEDIATA: Paralizar operaciones. Notificar dirección. Auditoría exhaustiva 48h.",
              "remediation_days": 90, "improvement_target": 40.0},
    "R5-T2": {"level": 5, "urgency": "CRITICO", "review_days": 3,
              "action": "SUSPENSIÓN CONDICIONAL: Reducir alcance al 25%. Plan correctivo 72h. Supervisión diaria.",
              "remediation_days": 60, "improvement_target": 35.0},
    "R5-T3": {"level": 4, "urgency": "MUY_ALTO", "review_days": 7,
              "action": "INTERVENCIÓN DIRECTA: Asignar supervisor HSE dedicado. Plan semanal obligatorio.",
              "remediation_days": 45, "improvement_target": 30.0},
    "R5-T4": {"level": 4, "urgency": "MUY_ALTO", "review_days": 7,
              "action": "MONITOREO INTENSIVO: Reportes diarios. Verificaciones no anunciadas 2x/semana.",
              "remediation_days": 30, "improvement_target": 25.0},
    "R5-T5": {"level": 3, "urgency": "ALTO", "review_days": 14,
              "action": "PLAN DE CONTENCIÓN: Análisis de causa raíz en 5 días. Acciones correctivas verificables.",
              "remediation_days": 21, "improvement_target": 20.0},
    
    # RIESGO ALTO (60-80)
    "R4-T1": {"level": 4, "urgency": "MUY_ALTO", "review_days": 5,
              "action": "RESTRICCIÓN SEVERA: Operaciones limitadas. Auditoría documental completa. Plan 10 días.",
              "remediation_days": 60, "improvement_target": 30.0},
    "R4-T2": {"level": 4, "urgency": "ALTO", "review_days": 7,
              "action": "ESCALAMIENTO CONTRACTUAL: Reunión con gerencia. Metas semanales estrictas.",
              "remediation_days": 45, "improvement_target": 25.0},
    "R4-T3": {"level": 3, "urgency": "ALTO", "review_days": 14,
              "action": "PLAN CORRECTIVO FORMAL: 5 acciones primarias + seguimiento bisemanal.",
              "remediation_days": 30, "improvement_target": 20.0},
    "R4-T4": {"level": 3, "urgency": "MEDIO_ALTO", "review_days": 14,
              "action": "MEJORA GUIADA: Checklist semanal + 3 acciones críticas. Mentor HSE asignado.",
              "remediation_days": 21, "improvement_target": 15.0},
    "R4-T5": {"level": 2, "urgency": "MEDIO", "review_days": 21,
              "action": "REFUERZO PREVENTIVO: Capacitación específica + verificación de controles.",
              "remediation_days": 14, "improvement_target": 10.0},
    
    # RIESGO MODERADO (40-60)
    "R3-T1": {"level": 4, "urgency": "ALTO", "review_days": 7,
              "action": "INTERVENCIÓN DOCUMENTAN: Regularizar documentación en 10 días. Sin nuevas certificaciones.",
              "remediation_days": 45, "improvement_target": 20.0},
    "R3-T2": {"level": 3, "urgency": "MEDIO_ALTO", "review_days": 14,
              "action": "PLAN DE NORMALIZACIÓN: 3 acciones semanales + cierre de brechas documentales.",
              "remediation_days": 30, "improvement_target": 15.0},
    "R3-T3": {"level": 2, "urgency": "MEDIO", "review_days": 21,
              "action": "SEGUIMIENTO ESTRUCTURADO: Reunión quincenal + dashboard compartido.",
              "remediation_days": 21, "improvement_target": 10.0},
    "R3-T4": {"level": 2, "urgency": "BAJO_MEDIO", "review_days": 30,
              "action": "MEJORA CONTINUA: Metas mensuales + reconocimiento por logros.",
              "remediation_days": 14, "improvement_target": 8.0},
    "R3-T5": {"level": 1, "urgency": "BAJO", "review_days": 30,
              "action": "MANTENIMIENTO: Continuar buenas prácticas. Revisión mensual estándar.",
              "remediation_days": 7, "improvement_target": 5.0},
    
    # RIESGO BAJO (20-40)
    "R2-T1": {"level": 3, "urgency": "MEDIO_ALTO", "review_days": 14,
              "action": "CONSTRUCCIÓN DE CONFIANZA: Programa de regularización documental + capacitación.",
              "remediation_days": 30, "improvement_target": 15.0},
    "R2-T2": {"level": 2, "urgency": "MEDIO", "review_days": 21,
              "action": "FORTALECIMIENTO: Mejorar consistencia en reportes + verificación mensual.",
              "remediation_days": 21, "improvement_target": 10.0},
    "R2-T3": {"level": 2, "urgency": "BAJO_MEDIO", "review_days": 30,
              "action": "OPTIMIZACIÓN: Identificar 2 áreas de mejora + implementar en 30 días.",
              "remediation_days": 14, "improvement_target": 7.0},
    "R2-T4": {"level": 1, "urgency": "BAJO", "review_days": 30,
              "action": "ESTÁNDAR POSITIVO: Mantener nivel. Candidato a certificación interna.",
              "remediation_days": 7, "improvement_target": 5.0},
    "R2-T5": {"level": 1, "urgency": "MUY_BAJO", "review_days": 45,
              "action": "EJEMPLAR: Compartir buenas prácticas. Considerar para mentorías.",
              "remediation_days": 0, "improvement_target": 0.0},
    
    # RIESGO MUY BAJO (0-20)
    "R1-T1": {"level": 3, "urgency": "MEDIO", "review_days": 21,
              "action": "ANOMALÍA DOCUMENTAL: Bajo riesgo pero baja confianza. Regularizar documentación.",
              "remediation_days": 30, "improvement_target": 20.0},
    "R1-T2": {"level": 2, "urgency": "BAJO_MEDIO", "review_days": 30,
              "action": "POTENCIAL OCULTO: Mejorar visibilidad y reportes para validar bajo riesgo.",
              "remediation_days": 21, "improvement_target": 10.0},
    "R1-T3": {"level": 1, "urgency": "BAJO", "review_days": 45,
              "action": "BUEN CAMINO: Pequeños ajustes de proceso. Revisión trimestral.",
              "remediation_days": 7, "improvement_target": 5.0},
    "R1-T4": {"level": 1, "urgency": "MUY_BAJO", "review_days": 60,
              "action": "SÓLIDO: Mantener estándares. Revisión bimestral.",
              "remediation_days": 0, "improvement_target": 0.0},
    "R1-T5": {"level": 1, "urgency": "MINIMO", "review_days": 90,
              "action": "EXCELENCIA: Modelo a seguir. Candidato a proveedor estratégico.",
              "remediation_days": 0, "improvement_target": 0.0},
}


# ---------------------------
# CATÁLOGO DE TAREAS DE REMEDIACIÓN
# ---------------------------

REMEDIATION_TASKS_CATALOG: Dict[str, List[RemediationTask]] = {
    "CRITICO": [
        RemediationTask("CRIT_001", "Suspender todas las operaciones de alto riesgo inmediatamente", "URGENTE", 1, "OPERACIONAL", 15.0),
        RemediationTask("CRIT_002", "Realizar auditoría de seguridad completa por tercero independiente", "URGENTE", 7, "VERIFICACION", 20.0),
        RemediationTask("CRIT_003", "Implementar supervisor HSE dedicado tiempo completo", "URGENTE", 3, "OPERACIONAL", 10.0),
        RemediationTask("CRIT_004", "Capacitación de emergencia para todo el personal (8h mínimo)", "ALTA", 5, "FORMACION", 8.0),
        RemediationTask("CRIT_005", "Actualizar matriz de riesgos y controles críticos", "ALTA", 7, "DOCUMENTAL", 7.0),
        RemediationTask("CRIT_006", "Implementar sistema de reporte diario de incidentes", "ALTA", 3, "DOCUMENTAL", 5.0),
    ],
    "MUY_ALTO": [
        RemediationTask("ALTO_001", "Revisar y actualizar todos los procedimientos de trabajo seguro", "ALTA", 14, "DOCUMENTAL", 12.0),
        RemediationTask("ALTO_002", "Realizar inspecciones no programadas 2x por semana", "ALTA", 7, "VERIFICACION", 8.0),
        RemediationTask("ALTO_003", "Cerrar todas las acciones correctivas vencidas", "URGENTE", 5, "OPERACIONAL", 10.0),
        RemediationTask("ALTO_004", "Capacitación reforzada en áreas de mayor incidencia", "ALTA", 10, "FORMACION", 6.0),
        RemediationTask("ALTO_005", "Reunión semanal de seguimiento con gerencia", "MEDIA", 7, "OPERACIONAL", 4.0),
    ],
    "ALTO": [
        RemediationTask("MED_001", "Completar documentación faltante de procedimientos", "ALTA", 14, "DOCUMENTAL", 8.0),
        RemediationTask("MED_002", "Implementar programa de observaciones de seguridad", "MEDIA", 21, "OPERACIONAL", 6.0),
        RemediationTask("MED_003", "Realizar simulacro de emergencia", "MEDIA", 14, "FORMACION", 5.0),
        RemediationTask("MED_004", "Verificar certificaciones vigentes del personal", "ALTA", 7, "DOCUMENTAL", 7.0),
    ],
    "MEDIO_ALTO": [
        RemediationTask("MEDALT_001", "Actualizar plan de capacitación anual", "MEDIA", 21, "FORMACION", 5.0),
        RemediationTask("MEDALT_002", "Revisar indicadores proactivos mensualmente", "MEDIA", 30, "DOCUMENTAL", 4.0),
        RemediationTask("MEDALT_003", "Implementar reconocimiento por comportamiento seguro", "BAJA", 30, "OPERACIONAL", 3.0),
    ],
    "MEDIO": [
        RemediationTask("MED_NORM_001", "Mantener cierres mensuales al día", "MEDIA", 30, "DOCUMENTAL", 4.0),
        RemediationTask("MED_NORM_002", "Participar en comité HSE mensual", "BAJA", 30, "OPERACIONAL", 3.0),
    ],
    "BAJO_MEDIO": [
        RemediationTask("BAJO_001", "Continuar con mejora continua según plan anual", "BAJA", 45, "OPERACIONAL", 2.0),
    ],
    "BAJO": [
        RemediationTask("MIN_001", "Revisión trimestral de indicadores", "BAJA", 90, "DOCUMENTAL", 1.0),
    ],
    "MUY_BAJO": [],
    "MINIMO": [],
}


def compute_time_penalty(
    rows_history: List[Row],
    current_month: str,
    days_since_last_report: int = 0
) -> TimePenaltyInfo:
    """
    Calcula penalización temporal basada en:
    1. Días sin reportar (gaps en datos)
    2. Tiempo en estado crítico/alto sin mejora
    3. Acciones vencidas acumuladas
    
    Similar a mora bancaria: entre más tiempo sin actuar, mayor penalización.
    """
    penalty = 0.0
    reason_parts = []
    days_in_critical = 0
    
    # 1. Penalización por días sin reporte
    if days_since_last_report > 7:
        # Escala logarítmica: crece rápido al inicio, se estabiliza
        report_penalty = min(25.0, 5.0 * math.log(days_since_last_report / 7.0 + 1))
        penalty += report_penalty
        reason_parts.append(f"Sin reporte por {days_since_last_report} días (+{report_penalty:.1f})")
    
    # 2. Penalización por tiempo en estado crítico
    if len(rows_history) >= 2:
        consecutive_high_risk = 0
        for row in reversed(rows_history[-6:]):  # Últimos 6 meses
            events_eff = effective_events(row)
            hours = max(row.hours, 1.0)
            risk_proxy = (events_eff / hours) * 1000.0
            
            if risk_proxy > 15.0:  # Umbral de riesgo alto
                consecutive_high_risk += 1
                days_in_critical += 30  # Aproximación mensual
            else:
                break
        
        if consecutive_high_risk >= 2:
            persistence_penalty = consecutive_high_risk * 4.0
            penalty += persistence_penalty
            reason_parts.append(f"{consecutive_high_risk} meses consecutivos en riesgo alto (+{persistence_penalty:.1f})")
    
    # 3. Penalización por acciones vencidas no cerradas (acumulativo)
    if rows_history:
        last = rows_history[-1]
        critical_overdue = _to_float(last.extra.get("critical_overdue", 0), 0.0)
        actions_overdue = _to_float(last.extra.get("actions_overdue", 0), 0.0)
        
        if critical_overdue > 0:
            crit_penalty = critical_overdue * 3.0
            penalty += crit_penalty
            reason_parts.append(f"{int(critical_overdue)} acciones críticas vencidas (+{crit_penalty:.1f})")
        
        if actions_overdue > 5:
            backlog_penalty = (actions_overdue - 5) * 0.5
            penalty += backlog_penalty
            reason_parts.append(f"Backlog de {int(actions_overdue)} acciones (+{backlog_penalty:.1f})")
    
    # Decay rate: 15% de reducción por cada mes de buen comportamiento
    decay_rate = 0.15
    
    return TimePenaltyInfo(
        days_without_report=days_since_last_report,
        days_in_critical=days_in_critical,
        cumulative_penalty=clamp(penalty, 0.0, 50.0),
        penalty_reason=" | ".join(reason_parts) if reason_parts else "Sin penalización",
        decay_rate=decay_rate
    )


def compute_improvement_signal(
    rows_history: List[Row],
    risk_features: List[FeatureSpec],
    trust_features: List[FeatureSpec]
) -> ImprovementSignal:
    """
    Detecta señales de mejora progresiva:
    - Tendencia de riesgo (mejorando/estable/empeorando)
    - Meses consecutivos con buen comportamiento
    - Hitos alcanzados
    """
    if len(rows_history) < 2:
        return ImprovementSignal(
            trend_direction="STABLE",
            improvement_score=0.0,
            consecutive_good_months=0,
            milestones_achieved=[],
            next_milestone="Completar primer mes de datos",
            days_to_milestone=30
        )
    
    # Calcular tendencia de riesgo
    risk_scores = []
    for i in range(max(0, len(rows_history) - 3), len(rows_history)):
        window = rows_history[max(0, i-2):i+1]
        r_score, _ = compute_risk_score(window, risk_features)
        risk_scores.append(r_score)
    
    # Calcular pendiente de mejora
    if len(risk_scores) >= 2:
        slope = (risk_scores[-1] - risk_scores[0]) / len(risk_scores)
        
        if slope < -3.0:
            trend = "IMPROVING"
            improvement = min(100.0, abs(slope) * 10)
        elif slope > 3.0:
            trend = "WORSENING"
            improvement = max(-100.0, -slope * 10)
        else:
            trend = "STABLE"
            improvement = 0.0
    else:
        trend = "STABLE"
        improvement = 0.0
    
    # Contar meses consecutivos buenos
    consecutive_good = 0
    for row in reversed(rows_history):
        events_eff = effective_events(row)
        monthly_close = row.monthly_close_submitted
        critical_overdue = _to_float(row.extra.get("critical_overdue", 0), 0.0)
        
        if events_eff == 0 and monthly_close == 1 and critical_overdue == 0:
            consecutive_good += 1
        else:
            break
    
    # Determinar hitos alcanzados y siguiente
    milestones = []
    next_milestone = ""
    days_to_milestone = 30
    
    if consecutive_good >= 1:
        milestones.append("1 mes sin incidentes")
    if consecutive_good >= 3:
        milestones.append("3 meses consecutivos OK")
        days_to_milestone = 60
    if consecutive_good >= 6:
        milestones.append("Semestre sin incidentes")
        days_to_milestone = 90
    if consecutive_good >= 12:
        milestones.append("Año completo ejemplar")
        days_to_milestone = 0
    
    # Siguiente hito
    if consecutive_good < 1:
        next_milestone = "Completar 1 mes sin incidentes"
        days_to_milestone = 30
    elif consecutive_good < 3:
        next_milestone = "Alcanzar 3 meses consecutivos OK"
        days_to_milestone = (3 - consecutive_good) * 30
    elif consecutive_good < 6:
        next_milestone = "Completar semestre sin incidentes"
        days_to_milestone = (6 - consecutive_good) * 30
    elif consecutive_good < 12:
        next_milestone = "Alcanzar año completo ejemplar"
        days_to_milestone = (12 - consecutive_good) * 30
    else:
        next_milestone = "Mantener excelencia - Candidato proveedor estratégico"
        days_to_milestone = 0
    
    return ImprovementSignal(
        trend_direction=trend,
        improvement_score=improvement,
        consecutive_good_months=consecutive_good,
        milestones_achieved=milestones,
        next_milestone=next_milestone,
        days_to_milestone=days_to_milestone
    )


def generate_remediation_plan(
    cell: str,
    risk_score: float,
    trust_score: float,
    drivers: List[str]
) -> Optional[RemediationPlan]:
    """
    Genera un plan de remediación personalizado basado en:
    - Posición en la matriz 5x5
    - Score actual de riesgo y confianza
    - Drivers principales del score
    
    El plan NO es de remediación inmediata - incluye checkpoints
    para validar mejora progresiva.
    """
    matrix_info = ESCALATION_MATRIX_5X5.get(cell)
    if not matrix_info:
        return None
    
    urgency = matrix_info["urgency"]
    remediation_days = matrix_info["remediation_days"]
    improvement_target = matrix_info["improvement_target"]
    
    if remediation_days == 0:
        return None  # No requiere remediación
    
    # Obtener tareas del catálogo según urgencia
    base_tasks = REMEDIATION_TASKS_CATALOG.get(urgency, [])
    
    # Filtrar tareas relevantes según drivers
    selected_tasks = []
    for task in base_tasks:
        # Incluir todas las tareas urgentes
        if task.priority in ["URGENTE", "ALTA"]:
            selected_tasks.append(task)
        # Incluir tareas relacionadas con drivers
        elif any(driver_match(d, task) for d in drivers):
            selected_tasks.append(task)
    
    # Limitar a máximo 6 tareas para ser manejable
    selected_tasks = selected_tasks[:6]
    
    # Calcular checkpoints (puntos de evaluación)
    # No evaluamos inmediatamente - damos tiempo para implementar
    checkpoints = []
    if remediation_days >= 90:
        checkpoints = [30, 60, 90]
    elif remediation_days >= 45:
        checkpoints = [15, 30, 45]
    elif remediation_days >= 21:
        checkpoints = [7, 14, 21]
    elif remediation_days >= 14:
        checkpoints = [7, 14]
    else:
        checkpoints = [remediation_days]
    
    # Mejora esperada por checkpoint (progresiva, no inmediata)
    expected_per_checkpoint = improvement_target / len(checkpoints)
    
    return RemediationPlan(
        target_risk_reduction=improvement_target if risk_score > 40 else 0.0,
        target_trust_increase=improvement_target if trust_score < 60 else 0.0,
        max_days_to_improve=remediation_days,
        tasks=selected_tasks,
        checkpoint_days=checkpoints,
        expected_improvement_pct=expected_per_checkpoint
    )


def driver_match(driver: str, task: RemediationTask) -> bool:
    """Verifica si un driver está relacionado con una tarea"""
    driver_lower = driver.lower()
    task_desc_lower = task.description.lower()
    
    keywords_map = {
        "event_rate": ["incidente", "seguridad", "emergencia"],
        "critical_overdue": ["vencida", "correctiva", "acción"],
        "actions_overdue": ["vencida", "pendiente", "acción"],
        "missing_monthly_close": ["reporte", "mensual", "cierre", "documental"],
        "rejected_reports": ["reporte", "documental", "calidad"],
        "trend_worsening": ["tendencia", "inspección", "verificación"],
    }
    
    for key, keywords in keywords_map.items():
        if key in driver_lower:
            return any(kw in task_desc_lower for kw in keywords)
    
    return False


def compute_severity_adjusted_score(
    risk_score: float,
    trust_score: float,
    time_penalty: TimePenaltyInfo
) -> float:
    """
    Score ajustado que combina riesgo, confianza y penalización temporal.
    Similar a un score de crédito: entre más alto, PEOR situación.
    
    Escala 0-100:
    - 0-25: Excelente (verde)
    - 25-50: Bueno (amarillo claro)
    - 50-70: Precaución (amarillo)
    - 70-85: Alto riesgo (naranja)
    - 85-100: Crítico (rojo)
    """
    # Base: combinación ponderada de riesgo e inverso de confianza
    base = 0.6 * risk_score + 0.4 * (100 - trust_score)
    
    # Aplicar penalización temporal
    adjusted = base + time_penalty.cumulative_penalty
    
    return clamp(adjusted, 0.0, 100.0)


def top_drivers(contribs: List[Tuple[str, float]], k: int = 3) -> List[str]:
    # Pick largest absolute impacts
    ranked = sorted(contribs, key=lambda x: abs(x[1]), reverse=True)
    out = []
    for name, val in ranked[:k]:
        if val == 0:
            continue
        direction = "↑" if val > 0 else "↓"
        out.append(f"{name} {direction}")
    return out or ["stable"]


# ---------------------------
# Pipeline
# ---------------------------

def parse_csv(path: str) -> List[Row]:
    rows: List[Row] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            contractor = (r.get("contractor") or "").strip()
            month = (r.get("month") or "").strip()
            hours = _to_float(r.get("hours"), 0.0)
            operated = _to_int(r.get("operated"), 0)
            monthly_close_submitted = _to_int(r.get("monthly_close_submitted"), 0)

            extra = dict(r)
            for k in ["contractor", "month", "hours", "operated", "monthly_close_submitted"]:
                extra.pop(k, None)

            rows.append(Row(contractor, month, hours, operated, monthly_close_submitted, extra))
    return rows


def score_latest_per_contractor(
    rows: List[Row],
    risk_features: List[FeatureSpec],
    trust_features: List[FeatureSpec],
    explain: bool = True
) -> List[ScoreOutput]:
    # group by contractor
    by_c: Dict[str, List[Row]] = {}
    for r in rows:
        by_c.setdefault(r.contractor, []).append(r)

    outputs: List[ScoreOutput] = []
    for contractor, grp in by_c.items():
        grp.sort(key=lambda x: x.month)
        last3 = grp[-3:]
        last = last3[-1]

        gate = compute_gate_status(last)
        r_score, r_contribs = compute_risk_score(last3, risk_features)
        t_score, t_contribs = compute_trust_score(last3, trust_features)
        stab = compute_stability_index(last3, r_score, t_score)

        esc_level, esc_action = escalation(gate, r_score, t_score, last.hours)

        drivers = []
        if explain:
            # merge contributions for a quick top-3 explanation
            drivers = top_drivers(r_contribs + t_contribs, 3)

        # Calcular celda 5x5 y obtener información de matriz
        cell = cell_5x5(t_score, r_score)
        matrix_info = ESCALATION_MATRIX_5X5.get(cell, {})
        
        # Calcular penalización temporal
        time_penalty = compute_time_penalty(grp, last.month)
        
        # Calcular señales de mejora
        improvement_signal = compute_improvement_signal(grp, risk_features, trust_features)
        
        # Generar plan de remediación
        remediation_plan = generate_remediation_plan(cell, r_score, t_score, drivers)
        
        # Score ajustado por severidad y tiempo
        severity_adjusted = compute_severity_adjusted_score(r_score, t_score, time_penalty)
        
        # Días recomendados para próxima revisión
        review_days = matrix_info.get("review_days", 30)
        
        # Probabilidad de incidente en próximos 30 días (Bayesiano)
        lam, _, _ = bayes_event_rate_per_hour(grp, BayesianPrior())
        prob_30d = prob_at_least_one_event_next_hours(lam, last.hours * 1.0)  # Asume horas similares
        
        # Usar escalation de matriz 5x5 si está disponible
        if matrix_info:
            esc_level = matrix_info.get("level", esc_level)
            esc_action = matrix_info.get("action", esc_action)

        outputs.append(ScoreOutput(
            contractor=contractor,
            month=last.month,
            gate_status=gate,
            risk_score=round(r_score, 1),
            trust_score=round(t_score, 1),
            stability_index=round(stab, 1),
            risk_bucket=risk_bucket(r_score),
            trust_bucket=trust_bucket(t_score),
            cell_5x5=cell,
            escalation_level=esc_level,
            escalation_action=esc_action,
            drivers_top3=drivers,
            remediation_plan=remediation_plan,
            time_penalty=time_penalty,
            improvement_signal=improvement_signal,
            severity_adjusted_score=round(severity_adjusted, 1),
            recommended_review_days=review_days,
            probability_incident_30d=round(prob_30d * 100, 1)
        ))
    return outputs


def to_csv(outputs: List[ScoreOutput], path: str) -> None:
    # Campos simplificados para CSV
    simple_fields = [
        "contractor", "month", "gate_status", "risk_score", "trust_score",
        "stability_index", "risk_bucket", "trust_bucket", "cell_5x5",
        "escalation_level", "escalation_action", "drivers_top3",
        "severity_adjusted_score", "recommended_review_days", "probability_incident_30d",
        "time_penalty_days", "time_penalty_score", "improvement_trend",
        "consecutive_good_months", "next_milestone", "remediation_days", "remediation_tasks_count"
    ]
    
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=simple_fields)
        w.writeheader()
        for o in outputs:
            row = {
                "contractor": o.contractor,
                "month": o.month,
                "gate_status": o.gate_status,
                "risk_score": o.risk_score,
                "trust_score": o.trust_score,
                "stability_index": o.stability_index,
                "risk_bucket": o.risk_bucket,
                "trust_bucket": o.trust_bucket,
                "cell_5x5": o.cell_5x5,
                "escalation_level": o.escalation_level,
                "escalation_action": o.escalation_action,
                "drivers_top3": "|".join(o.drivers_top3),
                "severity_adjusted_score": o.severity_adjusted_score,
                "recommended_review_days": o.recommended_review_days,
                "probability_incident_30d": o.probability_incident_30d,
                "time_penalty_days": o.time_penalty.days_in_critical if o.time_penalty else 0,
                "time_penalty_score": o.time_penalty.cumulative_penalty if o.time_penalty else 0,
                "improvement_trend": o.improvement_signal.trend_direction if o.improvement_signal else "N/A",
                "consecutive_good_months": o.improvement_signal.consecutive_good_months if o.improvement_signal else 0,
                "next_milestone": o.improvement_signal.next_milestone if o.improvement_signal else "N/A",
                "remediation_days": o.remediation_plan.max_days_to_improve if o.remediation_plan else 0,
                "remediation_tasks_count": len(o.remediation_plan.tasks) if o.remediation_plan else 0,
            }
            w.writerow(row)


def to_json_detailed(outputs: List[ScoreOutput], path: str) -> None:
    """Export completo en JSON con todos los detalles de remediación"""
    def serialize(obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)
    
    results = []
    for o in outputs:
        d = {
            "contractor": o.contractor,
            "month": o.month,
            "scores": {
                "risk": o.risk_score,
                "trust": o.trust_score,
                "stability": o.stability_index,
                "severity_adjusted": o.severity_adjusted_score,
            },
            "buckets": {
                "risk": o.risk_bucket,
                "trust": o.trust_bucket,
                "cell_5x5": o.cell_5x5,
            },
            "gate_status": o.gate_status,
            "escalation": {
                "level": o.escalation_level,
                "action": o.escalation_action,
            },
            "drivers": o.drivers_top3,
            "predictions": {
                "probability_incident_30d_pct": o.probability_incident_30d,
                "recommended_review_days": o.recommended_review_days,
            },
            "time_penalty": serialize(o.time_penalty) if o.time_penalty else None,
            "improvement_signal": serialize(o.improvement_signal) if o.improvement_signal else None,
            "remediation_plan": {
                "target_risk_reduction": o.remediation_plan.target_risk_reduction,
                "target_trust_increase": o.remediation_plan.target_trust_increase,
                "max_days": o.remediation_plan.max_days_to_improve,
                "checkpoints": o.remediation_plan.checkpoint_days,
                "expected_improvement_per_checkpoint_pct": o.remediation_plan.expected_improvement_pct,
                "tasks": [serialize(t) for t in o.remediation_plan.tasks]
            } if o.remediation_plan else None,
        }
        results.append(d)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"count": len(results), "results": results}, f, indent=2, ensure_ascii=False)


# ---------------------------
# AWS Lambda handler
# ---------------------------

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Expected event shapes (choose one):
    A) {"rows": [ {csv-like dict}, ... ], "feature_config": {...}}
    B) {"csv_s3_uri": "..."}  (optional future)
    For MVP: use A).
    """
    explain = bool(event.get("explain", True))

    feature_cfg = event.get("feature_config", {})
    risk_specs = [FeatureSpec(**x) for x in feature_cfg.get("risk_features", [])]
    trust_specs = [FeatureSpec(**x) for x in feature_cfg.get("trust_features", [])]

    input_rows = event.get("rows", [])
    rows: List[Row] = []
    for r in input_rows:
        rows.append(Row(
            contractor=str(r.get("contractor","")).strip(),
            month=str(r.get("month","")).strip(),
            hours=_to_float(r.get("hours"), 0.0),
            operated=_to_int(r.get("operated"), 0),
            monthly_close_submitted=_to_int(r.get("monthly_close_submitted"), 0),
            extra={k:v for k,v in r.items() if k not in ["contractor","month","hours","operated","monthly_close_submitted"]}
        ))

    outs = score_latest_per_contractor(rows, risk_specs, trust_specs, explain=explain)

    return {
        "count": len(outs),
        "results": [o.__dict__ for o in outs],
    }


# ---------------------------
# Local run
# ---------------------------

if __name__ == "__main__":
    # Example local run:
    # python amatia_model.py input.csv output.csv
    import sys
    if len(sys.argv) < 3:
        print("Usage: python amatia_model.py <input.csv> <output.csv>")
        raise SystemExit(2)

    input_csv = sys.argv[1]
    out_csv = sys.argv[2]

    # Example: add new optional variables by editing these specs (no code change)
    risk_features = [
        # FeatureSpec(name="incident_report_delay_days", kind="delay_days", weight=0.2, cap=30, direction="bad", when_missing="neutral"),
    ]
    trust_features = [
        # Telemetry examples you can add later:
        # FeatureSpec(name="last_login_days", kind="delay_days", weight=0.3, cap=60, direction="bad", when_missing="penalize"),
        # FeatureSpec(name="active_weeks", kind="count", weight=1.0, cap=4, direction="good", when_missing="neutral"),
    ]

    rows = parse_csv(input_csv)
    outs = score_latest_per_contractor(rows, risk_features, trust_features, explain=True)
    to_csv(outs, out_csv)
    
    # Export JSON detallado
    json_out = out_csv.replace(".csv", "_detailed.json")
    to_json_detailed(outs, json_out)
    
    print(f"\n{'='*60}")
    print("HSE CONTRACTOR SCORING - REPORTE DE REMEDIACIÓN")
    print(f"{'='*60}\n")
    print(f"Procesados: {len(outs)} contratistas")
    print(f"CSV: {out_csv}")
    print(f"JSON detallado: {json_out}\n")
    
    # Resumen por niveles de escalamiento
    print("DISTRIBUCIÓN POR NIVEL DE ESCALAMIENTO:")
    print("-" * 40)
    levels = {}
    for o in outs:
        levels[o.escalation_level] = levels.get(o.escalation_level, 0) + 1
    for lvl in sorted(levels.keys(), reverse=True):
        status = {5: "🔴 CRÍTICO", 4: "🟠 MUY ALTO", 3: "🟡 ALTO", 2: "🟢 MEDIO", 1: "✅ BAJO"}
        print(f"  Nivel {lvl} ({status.get(lvl, 'N/A')}): {levels[lvl]} contratistas")
    
    print("\n" + "="*60)
    print("DETALLE POR CONTRATISTA:")
    print("="*60)
    
    for o in sorted(outs, key=lambda x: x.severity_adjusted_score, reverse=True):
        print(f"\n📋 {o.contractor}")
        print(f"   Celda: {o.cell_5x5} | Riesgo: {o.risk_score} ({o.risk_bucket}) | Confianza: {o.trust_score} ({o.trust_bucket})")
        print(f"   Score Ajustado: {o.severity_adjusted_score} | Prob. Incidente 30d: {o.probability_incident_30d}%")
        
        if o.time_penalty and o.time_penalty.cumulative_penalty > 0:
            print(f"   ⚠️  Penalización temporal: +{o.time_penalty.cumulative_penalty:.1f} pts")
            print(f"      Razón: {o.time_penalty.penalty_reason}")
        
        if o.improvement_signal:
            trend_icon = {"IMPROVING": "📈", "STABLE": "➡️", "WORSENING": "📉"}.get(o.improvement_signal.trend_direction, "")
            print(f"   {trend_icon} Tendencia: {o.improvement_signal.trend_direction} | Meses buenos: {o.improvement_signal.consecutive_good_months}")
            if o.improvement_signal.milestones_achieved:
                print(f"      ✅ Hitos: {', '.join(o.improvement_signal.milestones_achieved)}")
            print(f"      ➡️  Siguiente: {o.improvement_signal.next_milestone} ({o.improvement_signal.days_to_milestone} días)")
        
        print(f"   🎯 Acción: {o.escalation_action}")
        
        if o.remediation_plan:
            print(f"   📅 Plan de Remediación ({o.remediation_plan.max_days_to_improve} días):")
            print(f"      Checkpoints: {o.remediation_plan.checkpoint_days}")
            print(f"      Mejora esperada por checkpoint: {o.remediation_plan.expected_improvement_pct:.1f}%")
            for task in o.remediation_plan.tasks[:3]:  # Solo primeras 3 tareas
                print(f"      • [{task.priority}] {task.description} (Plazo: {task.deadline_days}d)")
    
    print("\n" + "="*60)