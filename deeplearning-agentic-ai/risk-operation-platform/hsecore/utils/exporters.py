"""
HSE Exporters Module - Exportación de resultados
================================================

Funciones para exportar los resultados del scoring a diferentes formatos:
- CSV (resumen)
- JSON (detallado)
- Consola (reporte formateado)
"""
from __future__ import annotations

import csv
import json
from typing import List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import ScoreOutput


def to_csv(outputs: List[ScoreOutput], path: str) -> None:
    """
    Exporta resultados a CSV con campos simplificados.
    
    Ideal para importar en Excel o herramientas de BI.
    Los campos complejos (listas, objetos) se aplanan.
    
    Args:
        outputs: Lista de ScoreOutput
        path: Ruta del archivo de salida
    """
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
    """
    Exporta resultados completos en JSON con todos los detalles.
    
    Incluye:
    - Todos los scores
    - Plan de remediación completo con tareas
    - Señales de mejora
    - Penalizaciones temporales
    
    Args:
        outputs: Lista de ScoreOutput
        path: Ruta del archivo de salida
    """
    def serialize(obj):
        """Serializa objetos con __dict__ a diccionarios."""
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


def print_report(outputs: List[ScoreOutput]) -> None:
    """
    Imprime un reporte formateado en consola.
    
    Útil para revisión rápida de resultados.
    
    Args:
        outputs: Lista de ScoreOutput
    """
    print(f"\n{'='*60}")
    print("HSE CONTRACTOR SCORING - REPORTE DE REMEDIACIÓN")
    print(f"{'='*60}\n")
    print(f"Procesados: {len(outputs)} contratistas\n")
    
    # Distribución por nivel de escalamiento
    print("DISTRIBUCIÓN POR NIVEL DE ESCALAMIENTO:")
    print("-" * 40)
    levels = {}
    for o in outputs:
        levels[o.escalation_level] = levels.get(o.escalation_level, 0) + 1
    
    status_icons = {
        5: "🔴 CRÍTICO", 
        4: "🟠 MUY ALTO", 
        3: "🟡 ALTO", 
        2: "🟢 MEDIO", 
        1: "✅ BAJO"
    }
    
    for lvl in sorted(levels.keys(), reverse=True):
        print(f"  Nivel {lvl} ({status_icons.get(lvl, 'N/A')}): {levels[lvl]} contratistas")
    
    # Detalle por contratista
    print("\n" + "="*60)
    print("DETALLE POR CONTRATISTA:")
    print("="*60)
    
    for o in sorted(outputs, key=lambda x: x.severity_adjusted_score, reverse=True):
        print(f"\n📋 {o.contractor}")
        print(f"   Celda: {o.cell_5x5} | Riesgo: {o.risk_score} ({o.risk_bucket}) | Confianza: {o.trust_score} ({o.trust_bucket})")
        print(f"   Score Ajustado: {o.severity_adjusted_score} | Prob. Incidente 30d: {o.probability_incident_30d}%")
        
        if o.time_penalty and o.time_penalty.cumulative_penalty > 0:
            print(f"   ⚠️  Penalización temporal: +{o.time_penalty.cumulative_penalty:.1f} pts")
            print(f"      Razón: {o.time_penalty.penalty_reason}")
        
        if o.improvement_signal:
            trend_icons = {"IMPROVING": "📈", "STABLE": "➡️", "WORSENING": "📉"}
            trend_icon = trend_icons.get(o.improvement_signal.trend_direction, "")
            print(f"   {trend_icon} Tendencia: {o.improvement_signal.trend_direction} | Meses buenos: {o.improvement_signal.consecutive_good_months}")
            
            if o.improvement_signal.milestones_achieved:
                print(f"      ✅ Hitos: {', '.join(o.improvement_signal.milestones_achieved)}")
            print(f"      ➡️  Siguiente: {o.improvement_signal.next_milestone} ({o.improvement_signal.days_to_milestone} días)")
        
        print(f"   🎯 Acción: {o.escalation_action}")
        
        if o.remediation_plan:
            print(f"   📅 Plan de Remediación ({o.remediation_plan.max_days_to_improve} días):")
            print(f"      Checkpoints: {o.remediation_plan.checkpoint_days}")
            print(f"      Mejora esperada por checkpoint: {o.remediation_plan.expected_improvement_pct:.1f}%")
            
            for task in o.remediation_plan.tasks[:3]:
                print(f"      • [{task.priority}] {task.description} (Plazo: {task.deadline_days}d)")
    
    print("\n" + "="*60)
