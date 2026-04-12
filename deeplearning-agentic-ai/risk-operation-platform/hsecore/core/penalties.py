"""
HSE Penalties Module - Penalización temporal y señales de mejora
================================================================

Contiene:
- Penalización temporal (similar a mora bancaria)
- Señales de mejora progresiva
- Score ajustado por severidad

La penalización funciona como interés moratorio:
- Crece con el tiempo sin acción
- Decae con buen comportamiento
"""
from __future__ import annotations

import math
from typing import List, Tuple

from .models import (
    Row, 
    FeatureSpec, 
    TimePenaltyInfo, 
    ImprovementSignal,
    BayesianPrior,
)
from .scoring import _to_float, clamp, compute_risk_score


# ---------------------------
# Utilidad local
# ---------------------------

def _effective_events(row: Row) -> float:
    """Eventos efectivos ponderados de un row."""
    recordables = _to_float(row.extra.get("recordables", 0), 0.0)
    lti = _to_float(row.extra.get("lti", 0), 0.0)
    hipo = _to_float(row.extra.get("hipo", 0), 0.0)
    return recordables + 3.0 * lti + 2.0 * hipo


# ---------------------------
# Penalización Temporal
# ---------------------------

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
    La penalización es acumulativa pero tiene un tope.
    
    Args:
        rows_history: Historial completo del contratista
        current_month: Mes actual (YYYY-MM)
        days_since_last_report: Días desde último reporte (si se conoce)
        
    Returns:
        TimePenaltyInfo con detalles de la penalización
    """
    penalty = 0.0
    reason_parts = []
    days_in_critical = 0
    
    # 1. Penalización por días sin reporte
    # Escala logarítmica: crece rápido al inicio, se estabiliza
    if days_since_last_report > 7:
        report_penalty = min(25.0, 5.0 * math.log(days_since_last_report / 7.0 + 1))
        penalty += report_penalty
        reason_parts.append(f"Sin reporte por {days_since_last_report} días (+{report_penalty:.1f})")
    
    # 2. Penalización por tiempo en estado crítico
    # Revisa últimos 6 meses buscando meses consecutivos en riesgo alto
    if len(rows_history) >= 2:
        consecutive_high_risk = 0
        for row in reversed(rows_history[-6:]):
            events_eff = _effective_events(row)
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
            reason_parts.append(
                f"{consecutive_high_risk} meses consecutivos en riesgo alto (+{persistence_penalty:.1f})"
            )
    
    # 3. Penalización por acciones vencidas no cerradas (acumulativo)
    if rows_history:
        last = rows_history[-1]
        critical_overdue = _to_float(last.extra.get("critical_overdue", 0), 0.0)
        actions_overdue = _to_float(last.extra.get("actions_overdue", 0), 0.0)
        
        if critical_overdue > 0:
            crit_penalty = critical_overdue * 3.0
            penalty += crit_penalty
            reason_parts.append(
                f"{int(critical_overdue)} acciones críticas vencidas (+{crit_penalty:.1f})"
            )
        
        if actions_overdue > 5:
            backlog_penalty = (actions_overdue - 5) * 0.5
            penalty += backlog_penalty
            reason_parts.append(
                f"Backlog de {int(actions_overdue)} acciones (+{backlog_penalty:.1f})"
            )
    
    # Decay rate: 15% de reducción por cada mes de buen comportamiento
    decay_rate = 0.15
    
    return TimePenaltyInfo(
        days_without_report=days_since_last_report,
        days_in_critical=days_in_critical,
        cumulative_penalty=clamp(penalty, 0.0, 50.0),  # Tope máximo de 50
        penalty_reason=" | ".join(reason_parts) if reason_parts else "Sin penalización",
        decay_rate=decay_rate
    )


# ---------------------------
# Señales de Mejora
# ---------------------------

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
    
    Similar a la tendencia de pago en scoring crediticio.
    
    Args:
        rows_history: Historial del contratista
        risk_features: Features de riesgo configurables
        trust_features: Features de confianza configurables
        
    Returns:
        ImprovementSignal con tendencia y milestones
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
        window = rows_history[max(0, i - 2):i + 1]
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
        events_eff = _effective_events(row)
        monthly_close = row.monthly_close_submitted
        critical_overdue = _to_float(row.extra.get("critical_overdue", 0), 0.0)
        
        # Mes "bueno" = sin incidentes + cierre al día + sin críticos vencidos
        if events_eff == 0 and monthly_close == 1 and critical_overdue == 0:
            consecutive_good += 1
        else:
            break
    
    # Determinar hitos alcanzados
    milestones = []
    if consecutive_good >= 1:
        milestones.append("1 mes sin incidentes")
    if consecutive_good >= 3:
        milestones.append("3 meses consecutivos OK")
    if consecutive_good >= 6:
        milestones.append("Semestre sin incidentes")
    if consecutive_good >= 12:
        milestones.append("Año completo ejemplar")
    
    # Determinar siguiente hito
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


# ---------------------------
# Score Ajustado
# ---------------------------

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
    
    Args:
        risk_score: Score de riesgo (0-100)
        trust_score: Score de confianza (0-100)
        time_penalty: Info de penalización temporal
        
    Returns:
        Score ajustado 0-100 (mayor = peor)
    """
    # Base: combinación ponderada de riesgo e inverso de confianza
    base = 0.6 * risk_score + 0.4 * (100 - trust_score)
    
    # Aplicar penalización temporal
    adjusted = base + time_penalty.cumulative_penalty
    
    return clamp(adjusted, 0.0, 100.0)
