"""
HSE Health Score - Entry Point Principal
========================================

Sistema de Scoring HSE para contratistas.
Funciona como un modelo de scoring bancario aplicado a seguridad.

Uso local:
    python healthscore.py input/data.csv output/results.csv

Lambda:
    Handler: healthscore.lambda_handler

Estructura modular:
    core/          - Lógica de scoring y remediación
    utils/         - Parsers y exportadores
    input/         - Datos de entrada (CSV para pruebas)
    output/        - Resultados generados
"""
from __future__ import annotations

import sys
import os
from typing import Any, Dict, List

# Asegurar que los módulos locales estén en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar desde módulos core
from core.models import (
    FeatureSpec,
    Row,
    ScoreOutput,
    BayesianPrior,
)
from core.scoring import (
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
from core.remediation import (
    ESCALATION_MATRIX_5X5,
    generate_remediation_plan,
)
from core.penalties import (
    compute_time_penalty,
    compute_improvement_signal,
    compute_severity_adjusted_score,
)
from core.bayesian import (
    bayes_event_rate_per_hour,
    prob_at_least_one_event_next_hours,
)

# Importar desde utils
from utils.parsers import parse_csv, rows_from_dicts
from utils.exporters import to_csv, to_json_detailed, print_report


# ---------------------------
# Pipeline Principal
# ---------------------------

def score_latest_per_contractor(
    rows: List[Row],
    risk_features: List[FeatureSpec],
    trust_features: List[FeatureSpec],
    explain: bool = True
) -> List[ScoreOutput]:
    """
    Calcula scores HSE para cada contratista usando su mes más reciente.
    
    Este es el motor principal del scoring:
    1. Agrupa datos por contratista
    2. Calcula risk y trust scores
    3. Determina posición en matriz 5x5
    4. Genera plan de remediación
    5. Calcula señales de mejora
    6. Aplica penalizaciones temporales
    
    Args:
        rows: Todos los registros mensuales
        risk_features: Features adicionales de riesgo
        trust_features: Features adicionales de confianza
        explain: Si incluir drivers en output
        
    Returns:
        Lista de ScoreOutput, uno por contratista
    """
    # Agrupar por contratista
    by_c: Dict[str, List[Row]] = {}
    for r in rows:
        by_c.setdefault(r.contractor, []).append(r)

    outputs: List[ScoreOutput] = []
    
    for contractor, grp in by_c.items():
        grp.sort(key=lambda x: x.month)
        last3 = grp[-3:]  # Últimos 3 meses
        last = last3[-1]   # Mes más reciente

        # Scores base
        gate = compute_gate_status(last)
        r_score, r_contribs = compute_risk_score(last3, risk_features)
        t_score, t_contribs = compute_trust_score(last3, trust_features)
        stab = compute_stability_index(last3, r_score, t_score)

        # Escalamiento base
        esc_level, esc_action = escalation(gate, r_score, t_score, last.hours)

        # Drivers explicativos
        drivers = top_drivers(r_contribs + t_contribs, 3) if explain else []

        # Celda 5x5 e info de matriz
        cell = cell_5x5(t_score, r_score)
        matrix_info = ESCALATION_MATRIX_5X5.get(cell, {})
        
        # Penalización temporal
        time_penalty = compute_time_penalty(grp, last.month)
        
        # Señales de mejora
        improvement_signal = compute_improvement_signal(grp, risk_features, trust_features)
        
        # Plan de remediación
        remediation_plan = generate_remediation_plan(cell, r_score, t_score, drivers)
        
        # Score ajustado por severidad y tiempo
        severity_adjusted = compute_severity_adjusted_score(r_score, t_score, time_penalty)
        
        # Días recomendados para próxima revisión
        review_days = matrix_info.get("review_days", 30)
        
        # Probabilidad de incidente (Bayesiano)
        lam, _, _ = bayes_event_rate_per_hour(grp, BayesianPrior())
        prob_30d = prob_at_least_one_event_next_hours(lam, last.hours * 1.0)
        
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


# ---------------------------
# AWS Lambda Handler
# ---------------------------

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler para AWS Lambda.
    
    Evento esperado:
    {
        "rows": [
            {"contractor": "...", "month": "YYYY-MM", "hours": 1000, ...},
            ...
        ],
        "feature_config": {
            "risk_features": [...],
            "trust_features": [...]
        },
        "explain": true
    }
    
    Retorna:
    {
        "count": N,
        "results": [...]
    }
    """
    explain = bool(event.get("explain", True))

    # Configuración de features (opcional)
    feature_cfg = event.get("feature_config", {})
    risk_specs = [FeatureSpec(**x) for x in feature_cfg.get("risk_features", [])]
    trust_specs = [FeatureSpec(**x) for x in feature_cfg.get("trust_features", [])]

    # Convertir datos de entrada a Row
    input_rows = event.get("rows", [])
    rows = rows_from_dicts(input_rows)

    # Ejecutar scoring
    outs = score_latest_per_contractor(rows, risk_specs, trust_specs, explain=explain)

    # Serializar resultados
    def serialize(obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)

    return {
        "count": len(outs),
        "results": [serialize(o) for o in outs],
    }


# ---------------------------
# Local CLI
# ---------------------------

def main():
    """
    Punto de entrada para uso local por línea de comandos.
    
    Uso:
        python healthscore.py <input.csv> <output.csv>
    """
    if len(sys.argv) < 3:
        print("Uso: python healthscore.py <input.csv> <output.csv>")
        print("\nEjemplo:")
        print("  python healthscore.py input/data.csv output/results.csv")
        sys.exit(2)

    input_csv = sys.argv[1]
    out_csv = sys.argv[2]

    # Features adicionales configurables (vacíos por defecto)
    # Descomentar y modificar según necesidad
    risk_features = [
        # FeatureSpec(name="incident_report_delay_days", kind="delay_days", 
        #             weight=0.2, cap=30, direction="bad", when_missing="neutral"),
    ]
    trust_features = [
        # FeatureSpec(name="last_login_days", kind="delay_days", 
        #             weight=0.3, cap=60, direction="bad", when_missing="penalize"),
        # FeatureSpec(name="active_weeks", kind="count", 
        #             weight=1.0, cap=4, direction="good", when_missing="neutral"),
    ]

    # Parsear CSV (solo para pruebas)
    # En producción: rows = rows_from_database(connection)
    rows = parse_csv(input_csv)
    
    # Ejecutar scoring
    outs = score_latest_per_contractor(rows, risk_features, trust_features, explain=True)
    
    # Exportar resultados
    to_csv(outs, out_csv)
    
    # JSON detallado
    json_out = out_csv.replace(".csv", "_detailed.json")
    to_json_detailed(outs, json_out)
    
    # Imprimir reporte en consola
    print(f"\nArchivos generados:")
    print(f"  CSV: {out_csv}")
    print(f"  JSON: {json_out}")
    
    print_report(outs)


if __name__ == "__main__":
    main()
