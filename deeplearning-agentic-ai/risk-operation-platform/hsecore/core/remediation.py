"""
HSE Remediation Module - Matriz de escalamiento y planes de acción
==================================================================

Contiene:
- Funciones para acceder a la matriz de escalamiento 5x5 (Risk vs Trust)
- Catálogo de tareas de remediación
- Generador de planes de remediación

La configuración se carga desde config/matrix_5x5.json, lo que permite:
- Editar la matriz sin modificar código
- Soporte multilenguaje (i18n)
- Tooltips de ayuda para UI
- Versionado independiente de la configuración

Similar a una matriz de cobranza en scoring bancario:
- Define acciones según severidad
- Plazos prudentes (no inmediatos)
- Checkpoints de mejora progresiva
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import RemediationTask, RemediationPlan


# ---------------------------
# ACCESO A CONFIGURACIÓN EXTERNA
# ---------------------------
# 
# La matriz y catálogo se cargan desde config/matrix_5x5.json
# Esto permite editar sin tocar código y soporte i18n.
#
# Para cambiar idioma: from config import set_language; set_language("en")

def get_escalation_matrix() -> Dict[str, Dict[str, Any]]:
    """
    Obtiene la matriz de escalamiento 5x5 desde configuración externa.
    
    La matriz mapea celdas (R1-T1 a R5-T5) con acciones y parámetros.
    
    Returns:
        Dict con estructura {cell: {level, urgency, review_days, action, ...}}
    """
    from config import get_escalation_matrix as _get_matrix
    return _get_matrix()


def get_remediation_tasks() -> Dict[str, List[RemediationTask]]:
    """
    Obtiene el catálogo de tareas de remediación desde configuración externa.
    
    Returns:
        Dict con estructura {urgency: [RemediationTask, ...]}
    """
    from config import get_remediation_tasks as _get_tasks
    return _get_tasks()


# Aliases para compatibilidad con código existente (lazy loading)
# Estos se resuelven en runtime para permitir cambio de idioma dinámico

class _LazyMatrix:
    """Proxy que carga la matriz solo cuando se accede."""
    def __getitem__(self, key):
        return get_escalation_matrix()[key]
    
    def get(self, key, default=None):
        return get_escalation_matrix().get(key, default)
    
    def __contains__(self, key):
        return key in get_escalation_matrix()
    
    def items(self):
        return get_escalation_matrix().items()
    
    def keys(self):
        return get_escalation_matrix().keys()
    
    def values(self):
        return get_escalation_matrix().values()


class _LazyTasks:
    """Proxy que carga las tareas solo cuando se accede."""
    def __getitem__(self, key):
        return get_remediation_tasks()[key]
    
    def get(self, key, default=None):
        return get_remediation_tasks().get(key, default)
    
    def __contains__(self, key):
        return key in get_remediation_tasks()
    
    def items(self):
        return get_remediation_tasks().items()


# Aliases para código existente (mantiene compatibilidad)
ESCALATION_MATRIX_5X5 = _LazyMatrix()
REMEDIATION_TASKS_CATALOG = _LazyTasks()


# ---------------------------
# FUNCIONES AUXILIARES
# ---------------------------

def _driver_match(driver: str, task: RemediationTask) -> bool:
    """Verifica si un driver está relacionado con una tarea."""
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
    para validar mejora progresiva (como un plan de pago).
    
    Args:
        cell: Celda 5x5 (ej: "R3-T4")
        risk_score: Score de riesgo actual
        trust_score: Score de confianza actual
        drivers: Factores principales que afectan el score
        
    Returns:
        RemediationPlan o None si no requiere remediación
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
        # Incluir todas las tareas urgentes/altas
        if task.priority in ["URGENTE", "ALTA"]:
            selected_tasks.append(task)
        # Incluir tareas relacionadas con drivers
        elif any(_driver_match(d, task) for d in drivers):
            selected_tasks.append(task)
    
    # Limitar a máximo 6 tareas para ser manejable
    selected_tasks = selected_tasks[:6]
    
    # Calcular checkpoints (puntos de evaluación)
    # No evaluamos inmediatamente - damos tiempo para implementar
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
    expected_per_checkpoint = improvement_target / len(checkpoints) if checkpoints else 0
    
    return RemediationPlan(
        target_risk_reduction=improvement_target if risk_score > 40 else 0.0,
        target_trust_increase=improvement_target if trust_score < 60 else 0.0,
        max_days_to_improve=remediation_days,
        tasks=selected_tasks,
        checkpoint_days=checkpoints,
        expected_improvement_pct=expected_per_checkpoint
    )
