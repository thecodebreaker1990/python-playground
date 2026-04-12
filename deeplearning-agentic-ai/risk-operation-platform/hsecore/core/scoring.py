"""
HSE Scoring Functions - Cálculo de scores de riesgo y confianza
===============================================================

Funciones principales para calcular:
- Risk Score (0-100): Mayor = más riesgo
- Trust Score (0-100): Mayor = más confianza
- Stability Index: Combinación ponderada
- Buckets y clasificaciones
"""
from __future__ import annotations

import math
from typing import Any, List, Optional, Tuple

from .models import FeatureSpec, Row


# ---------------------------
# Utilidades
# ---------------------------

def _to_float(x: Any, default: float = 0.0) -> float:
    """Convierte cualquier valor a float de forma segura."""
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def _to_int(x: Any, default: int = 0) -> int:
    """Convierte cualquier valor a int de forma segura."""
    try:
        if x is None or x == "":
            return default
        return int(float(x))
    except Exception:
        return default


def clamp(x: float, lo: float, hi: float) -> float:
    """Limita un valor entre un mínimo y máximo."""
    return max(lo, min(hi, x))


def sigmoid(x: float) -> float:
    """Función sigmoide para normalización."""
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------
# Gate Status
# ---------------------------

def compute_gate_status(row: Row) -> str:
    """
    Determina el estado de compuerta del contratista.
    Similar a un semáforo de acceso.
    
    Returns:
        BLOCKED: No puede operar
        AT_RISK: Puede operar con restricciones
        OK: Operación normal
    """
    blocked = _to_int(row.extra.get("docs_blocked", 0), 0)
    at_risk = _to_int(row.extra.get("docs_at_risk", 0), 0)

    if blocked >= 1:
        return "BLOCKED"
    if at_risk >= 1:
        return "AT_RISK"
    return "OK"


# ---------------------------
# Feature Extraction
# ---------------------------

def _extract_feature_value(row: Row, spec: FeatureSpec) -> Optional[float]:
    """
    Extrae y normaliza el valor de una característica del row.
    Maneja diferentes tipos de features según su 'kind'.
    """
    raw = row.extra.get(spec.name, None)

    if raw is None or raw == "":
        if spec.when_missing == "zero":
            raw_val = 0.0
        elif spec.when_missing == "penalize":
            return float("nan")  # Marcador para penalización
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
        # Acepta 0..1 o 0..100; normaliza a 0..1
        val = raw_val / 100.0 if raw_val > 1.5 else raw_val
    else:
        return None

    return clamp(val, 0.0, spec.cap)


# ---------------------------
# Risk Score
# ---------------------------

def compute_risk_score(
    rows_last3: List[Row], 
    risk_features: List[FeatureSpec]
) -> Tuple[float, List[Tuple[str, float]]]:
    """
    Calcula Risk Score 0-100 (mayor = más riesgo).
    
    Usa los últimos 3 meses para estabilidad y tendencia.
    Similar a un score de riesgo crediticio pero para HSE.
    
    Args:
        rows_last3: Últimos 3 meses de datos del contratista
        risk_features: Features adicionales configurables
        
    Returns:
        Tupla (risk_score, contributions) donde contributions
        es lista de (nombre_factor, puntos_contribuidos)
    """
    if not rows_last3:
        return 0.0, []

    last = rows_last3[-1]
    contribs: List[Tuple[str, float]] = []

    # Base: eventos ponderados
    recordables = _to_float(last.extra.get("recordables", 0), 0.0)
    lti = _to_float(last.extra.get("lti", 0), 0.0)
    hipo = _to_float(last.extra.get("hipo", 0), 0.0)

    hours3 = max(sum(r.hours for r in rows_last3), 1.0)
    events_eff = recordables + 3.0 * lti + 2.0 * hipo
    event_rate = (events_eff / hours3) * 1000.0  # por 1000h

    risk = min(60.0, event_rate * 18.0)
    contribs.append(("event_rate_per_1000h", risk))

    # Penalizaciones por backlog
    crit_overdue = _to_float(last.extra.get("critical_overdue", 0), 0.0)
    overdue = _to_float(last.extra.get("actions_overdue", 0), 0.0)

    c1 = min(25.0, crit_overdue * 3.5)
    c2 = min(10.0, overdue * 0.8)
    risk += c1 + c2
    contribs.append(("critical_overdue", c1))
    contribs.append(("actions_overdue", c2))

    # Tendencia: último vs previo
    if len(rows_last3) >= 2:
        prev = rows_last3[-2]
        prev_eff = (
            _to_float(prev.extra.get("recordables", 0), 0.0) +
            3.0 * _to_float(prev.extra.get("lti", 0), 0.0) +
            2.0 * _to_float(prev.extra.get("hipo", 0), 0.0)
        )
        if events_eff > prev_eff:
            risk += 5.0
            contribs.append(("trend_worsening", 5.0))

    # Features adicionales configurables
    for spec in risk_features:
        val = _extract_feature_value(last, spec)
        if val is None:
            continue
        sign = 1.0 if spec.direction == "bad" else -1.0
        add = sign * (spec.weight * val)
        add = clamp(add, -10.0, 10.0)
        risk += add
        contribs.append((spec.name, add))

    return clamp(risk, 0.0, 100.0), contribs


# ---------------------------
# Trust Score
# ---------------------------

def compute_trust_score(
    rows_last3: List[Row], 
    trust_features: List[FeatureSpec]
) -> Tuple[float, List[Tuple[str, float]]]:
    """
    Calcula Trust Score 0-100 (mayor = más confianza).
    
    Mide qué tan confiable es la información reportada por el contratista.
    Similar a un score de comportamiento de pago.
    
    Args:
        rows_last3: Últimos 3 meses de datos
        trust_features: Features adicionales configurables
        
    Returns:
        Tupla (trust_score, contributions)
    """
    if not rows_last3:
        return 0.0, []

    last = rows_last3[-1]
    t = 70.0  # Base de confianza
    contribs: List[Tuple[str, float]] = [("base", 70.0)]

    # Penalización por cierre mensual faltante
    close = last.monthly_close_submitted
    if close == 0:
        t -= 25.0
        contribs.append(("missing_monthly_close", -25.0))

    # Penalización por reportes rechazados
    rejected = _to_float(last.extra.get("rejected_reports", 0), 0.0)
    rej_pen = -min(15.0, rejected * 7.5)
    t += rej_pen
    if rejected:
        contribs.append(("rejected_reports", rej_pen))

    # Heurística de sub-reporte
    exec_crit = _to_float(last.extra.get("exec_crit_findings", 0), 0.0)
    lti = _to_float(last.extra.get("lti", 0), 0.0)
    hipo = _to_float(last.extra.get("hipo", 0), 0.0)
    recordables = _to_float(last.extra.get("recordables", 0), 0.0)

    if exec_crit >= 2 and (recordables + lti + hipo) == 0:
        t -= 10.0
        contribs.append(("discrepancy_exec_vs_self", -10.0))

    # Bonus: cierres consistentes últimos 3 meses
    if sum(r.monthly_close_submitted for r in rows_last3) == len(rows_last3):
        t += 5.0
        contribs.append(("consistent_closes_bonus", +5.0))

    # Features adicionales
    for spec in trust_features:
        val = _extract_feature_value(last, spec)
        if val is None:
            continue
        if math.isnan(val):
            t -= abs(spec.weight) * 5.0
            contribs.append((f"{spec.name}_missing_penalty", -abs(spec.weight) * 5.0))
            continue

        sign = -1.0 if spec.direction == "bad" else 1.0
        add = sign * (spec.weight * val)
        add = clamp(add, -12.0, 12.0)
        t += add
        contribs.append((spec.name, add))

    return clamp(t, 0.0, 100.0), contribs


# ---------------------------
# Stability Index
# ---------------------------

def compute_stability_index(
    rows_last3: List[Row], 
    risk_score: float, 
    trust_score: float
) -> float:
    """
    Calcula índice de estabilidad 0-100 (mayor = menos estable/más preocupante).
    
    Combina riesgo e inverso de confianza con señales de empeoramiento.
    """
    inv_trust = (100.0 - trust_score) / 100.0
    r = risk_score / 100.0
    s = 100.0 * (0.55 * r + 0.45 * inv_trust)
    
    # Bump adicional si el último mes empeoró
    if len(rows_last3) >= 2:
        last = rows_last3[-1]
        prev = rows_last3[-2]
        last_eff = (
            _to_float(last.extra.get("recordables", 0), 0.0) +
            3.0 * _to_float(last.extra.get("lti", 0), 0.0) +
            2.0 * _to_float(last.extra.get("hipo", 0), 0.0)
        )
        prev_eff = (
            _to_float(prev.extra.get("recordables", 0), 0.0) +
            3.0 * _to_float(prev.extra.get("lti", 0), 0.0) +
            2.0 * _to_float(prev.extra.get("hipo", 0), 0.0)
        )
        if last_eff > prev_eff:
            s += 5.0
    
    return clamp(s, 0.0, 100.0)


# ---------------------------
# Buckets y Clasificaciones
# ---------------------------

def risk_bucket(r: float) -> str:
    """Clasifica el risk score en buckets."""
    if r < 35:
        return "LOW"
    if r < 60:
        return "MOD"
    if r < 80:
        return "HIGH"
    return "CRIT"


def trust_bucket(t: float) -> str:
    """Clasifica el trust score en buckets."""
    if t < 50:
        return "LOW"
    if t < 75:
        return "MED"
    return "HIGH"


def cell_5x5(trust: float, risk: float) -> str:
    """
    Determina la celda en la matriz 5x5 de Risk vs Trust.
    
    Risk: R1 (0-20) a R5 (80-100)
    Trust: T1 (0-20) a T5 (80-100)
    
    Returns:
        String como "R3-T4" indicando la posición en la matriz
    """
    def b(x: float) -> int:
        if x < 20:
            return 1
        if x < 40:
            return 2
        if x < 60:
            return 3
        if x < 80:
            return 4
        return 5
    return f"R{b(risk)}-T{b(trust)}"


# ---------------------------
# Escalation (básico)
# ---------------------------

def escalation(
    row_gate: str, 
    risk: float, 
    trust: float, 
    hours_month: float
) -> Tuple[int, str]:
    """
    Determina nivel de escalamiento básico (1-4).
    Se usa como fallback si no hay info en la matriz 5x5.
    """
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
# Drivers
# ---------------------------

def top_drivers(contribs: List[Tuple[str, float]], k: int = 3) -> List[str]:
    """
    Extrae los top K factores que más contribuyen al score.
    Útil para explicabilidad (¿por qué este score?).
    """
    ranked = sorted(contribs, key=lambda x: abs(x[1]), reverse=True)
    out = []
    for name, val in ranked[:k]:
        if val == 0:
            continue
        direction = "↑" if val > 0 else "↓"
        out.append(f"{name} {direction}")
    return out or ["stable"]
