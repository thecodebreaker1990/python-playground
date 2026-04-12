"""
HSE Config Loader - Carga y gestión de configuración de matriz 5x5
==================================================================

Funciones principales:
- load_matrix_config(): Carga el JSON de configuración
- get_escalation_matrix(): Retorna la matriz en formato para código
- get_remediation_tasks(): Retorna tareas en formato para código
- get_label/get_tooltip(): Obtiene textos traducidos
- set_language(): Cambia el idioma activo

Soporta múltiples idiomas (i18n) y tooltips de ayuda.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import RemediationTask


# ---------------------------
# Configuración global
# ---------------------------

SUPPORTED_LANGUAGES = ["es", "en", "pt"]
_current_language = "es"  # Idioma por defecto
_config_cache: Optional[Dict[str, Any]] = None
_config_path: Optional[str] = None


def set_language(lang: str) -> None:
    """
    Establece el idioma activo para labels y tooltips.
    
    Args:
        lang: Código de idioma ('es', 'en', 'pt')
        
    Raises:
        ValueError: Si el idioma no está soportado
    """
    global _current_language
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Idioma '{lang}' no soportado. Use: {SUPPORTED_LANGUAGES}")
    _current_language = lang


def get_current_language() -> str:
    """Retorna el idioma activo actual."""
    return _current_language


# ---------------------------
# Carga de configuración
# ---------------------------

def _get_default_config_path() -> str:
    """Obtiene la ruta por defecto del archivo de configuración."""
    return os.path.join(os.path.dirname(__file__), "matrix_5x5.json")


def load_matrix_config(path: str = None, force_reload: bool = False) -> Dict[str, Any]:
    """
    Carga la configuración de la matriz desde JSON.
    
    El resultado se cachea para evitar lecturas repetidas.
    
    Args:
        path: Ruta al archivo JSON (usa default si no se especifica)
        force_reload: Si es True, recarga aunque esté en caché
        
    Returns:
        Diccionario con la configuración completa
    """
    global _config_cache, _config_path
    
    if path is None:
        path = _get_default_config_path()
    
    # Usar caché si está disponible y no se pide recarga
    if _config_cache is not None and _config_path == path and not force_reload:
        return _config_cache
    
    with open(path, "r", encoding="utf-8") as f:
        _config_cache = json.load(f)
        _config_path = path
    
    return _config_cache


def reload_config() -> Dict[str, Any]:
    """Fuerza recarga de la configuración desde disco."""
    return load_matrix_config(force_reload=True)


# ---------------------------
# Acceso a textos traducidos
# ---------------------------

def _get_localized(obj: Any, lang: str = None) -> str:
    """
    Obtiene texto localizado de un objeto.
    
    Si el objeto es un dict con claves de idioma, retorna el valor para el idioma.
    Si es un string, lo retorna directamente.
    """
    if lang is None:
        lang = _current_language
    
    if isinstance(obj, dict):
        # Intentar idioma solicitado, luego español, luego inglés, luego cualquiera
        if lang in obj:
            return obj[lang]
        if "es" in obj:
            return obj["es"]
        if "en" in obj:
            return obj["en"]
        # Retornar primer valor disponible
        for v in obj.values():
            if isinstance(v, str):
                return v
        return str(obj)
    
    return str(obj) if obj else ""


def get_label(category: str, key: str, lang: str = None) -> str:
    """
    Obtiene una etiqueta traducida.
    
    Args:
        category: Categoría de etiqueta (risk_levels, trust_levels, etc.)
        key: Clave específica (R1, T2, CRITICO, etc.)
        lang: Idioma (usa el activo si no se especifica)
        
    Returns:
        Texto traducido
        
    Example:
        get_label("risk_levels", "R3") -> "Moderado"
        get_label("urgency_levels", "ALTO") -> "Alto"
    """
    config = load_matrix_config()
    labels = config.get("labels", {})
    
    if category not in labels:
        return key
    
    category_labels = labels[category]
    if key not in category_labels:
        return key
    
    return _get_localized(category_labels[key], lang)


def get_tooltip(key: str, lang: str = None) -> str:
    """
    Obtiene un tooltip de ayuda traducido.
    
    Args:
        key: Clave del tooltip (risk_score, trust_score, etc.)
        lang: Idioma (usa el activo si no se especifica)
        
    Returns:
        Texto del tooltip
        
    Example:
        get_tooltip("risk_score") -> "Puntuación de riesgo basada en..."
    """
    config = load_matrix_config()
    tooltips = config.get("tooltips", {})
    
    if key not in tooltips:
        return ""
    
    return _get_localized(tooltips[key], lang)


def get_cell_tooltip(cell: str, lang: str = None) -> str:
    """
    Obtiene el tooltip específico de una celda de la matriz.
    
    Args:
        cell: Celda (ej: "R3-T4")
        lang: Idioma
        
    Returns:
        Tooltip de la celda
    """
    config = load_matrix_config()
    matrix = config.get("matrix", {})
    
    if cell not in matrix:
        return ""
    
    cell_data = matrix[cell]
    tooltip = cell_data.get("tooltip", {})
    
    return _get_localized(tooltip, lang)


def get_cell_action(cell: str, lang: str = None) -> str:
    """
    Obtiene la acción traducida para una celda.
    
    Args:
        cell: Celda (ej: "R3-T4")
        lang: Idioma
        
    Returns:
        Acción recomendada
    """
    config = load_matrix_config()
    matrix = config.get("matrix", {})
    
    if cell not in matrix:
        return ""
    
    cell_data = matrix[cell]
    action = cell_data.get("action", {})
    
    return _get_localized(action, lang)


# ---------------------------
# Conversión a formato código
# ---------------------------

def get_escalation_matrix(lang: str = None) -> Dict[str, Dict[str, Any]]:
    """
    Retorna la matriz de escalamiento en formato compatible con el código existente.
    
    Convierte las acciones al idioma seleccionado.
    
    Args:
        lang: Idioma para las acciones
        
    Returns:
        Dict con estructura {cell: {level, urgency, review_days, action, ...}}
    """
    if lang is None:
        lang = _current_language
    
    config = load_matrix_config()
    matrix = config.get("matrix", {})
    
    result = {}
    for cell, data in matrix.items():
        # Ignorar comentarios
        if cell.startswith("_"):
            continue
        
        result[cell] = {
            "level": data.get("level", 1),
            "urgency": data.get("urgency", "BAJO"),
            "review_days": data.get("review_days", 30),
            "remediation_days": data.get("remediation_days", 0),
            "improvement_target": data.get("improvement_target", 0.0),
            "action": _get_localized(data.get("action", {}), lang),
            # Metadata adicional
            "description": data.get("_description", ""),
            "tooltip": _get_localized(data.get("tooltip", {}), lang),
        }
    
    return result


def get_remediation_tasks(lang: str = None) -> Dict[str, List[RemediationTask]]:
    """
    Retorna el catálogo de tareas de remediación como objetos RemediationTask.
    
    Args:
        lang: Idioma para las descripciones
        
    Returns:
        Dict con estructura {urgency: [RemediationTask, ...]}
    """
    if lang is None:
        lang = _current_language
    
    config = load_matrix_config()
    tasks_config = config.get("remediation_tasks", {})
    
    result = {}
    for urgency, tasks in tasks_config.items():
        # Ignorar comentarios
        if urgency.startswith("_"):
            continue
        
        result[urgency] = []
        for task_data in tasks:
            task = RemediationTask(
                task_id=task_data.get("id", ""),
                description=_get_localized(task_data.get("description", {}), lang),
                priority=task_data.get("priority", "MEDIA"),
                deadline_days=task_data.get("deadline_days", 30),
                category=task_data.get("category", "OPERACIONAL"),
                weight_improvement=task_data.get("weight", 0.0),
            )
            result[urgency].append(task)
    
    return result


def get_all_labels_for_ui(lang: str = None) -> Dict[str, Any]:
    """
    Retorna todos los labels para uso en UI.
    
    Útil para cargar todas las traducciones de una vez.
    
    Args:
        lang: Idioma
        
    Returns:
        Dict con todos los labels traducidos
    """
    if lang is None:
        lang = _current_language
    
    config = load_matrix_config()
    labels = config.get("labels", {})
    
    result = {}
    for category, items in labels.items():
        if category.startswith("_"):
            continue
        
        result[category] = {}
        for key, value in items.items():
            if isinstance(value, dict):
                result[category][key] = {
                    "label": _get_localized(value, lang),
                    "color": value.get("color"),
                    "icon": value.get("icon"),
                }
            else:
                result[category][key] = {"label": str(value)}
    
    return result


# ---------------------------
# Utilidades de validación
# ---------------------------

def validate_config(config: Dict[str, Any] = None) -> List[str]:
    """
    Valida la configuración y retorna lista de errores.
    
    Args:
        config: Configuración a validar (carga de disco si no se provee)
        
    Returns:
        Lista de mensajes de error (vacía si todo OK)
    """
    if config is None:
        config = load_matrix_config()
    
    errors = []
    
    # Verificar estructura básica
    required_sections = ["labels", "matrix", "remediation_tasks"]
    for section in required_sections:
        if section not in config:
            errors.append(f"Falta sección requerida: {section}")
    
    # Verificar que todas las celdas de la matriz existen
    expected_cells = [f"R{r}-T{t}" for r in range(1, 6) for t in range(1, 6)]
    matrix = config.get("matrix", {})
    for cell in expected_cells:
        if cell not in matrix:
            errors.append(f"Falta celda de matriz: {cell}")
    
    # Verificar campos requeridos en cada celda
    required_cell_fields = ["level", "urgency", "action"]
    for cell, data in matrix.items():
        if cell.startswith("_"):
            continue
        for field in required_cell_fields:
            if field not in data:
                errors.append(f"Celda {cell} le falta campo: {field}")
    
    return errors


def print_matrix_summary(lang: str = None) -> None:
    """
    Imprime un resumen visual de la matriz en consola.
    
    Útil para verificar la configuración.
    """
    if lang is None:
        lang = _current_language
    
    matrix = get_escalation_matrix(lang)
    
    print("\n" + "="*80)
    print("MATRIZ DE ESCALAMIENTO HSE 5x5")
    print("="*80)
    
    # Header
    print(f"\n{'':15}", end="")
    for t in range(1, 6):
        print(f"T{t:^12}", end="")
    print()
    
    # Filas
    for r in range(5, 0, -1):
        print(f"R{r:>2} ", end="")
        for t in range(1, 6):
            cell = f"R{r}-T{t}"
            data = matrix.get(cell, {})
            level = data.get("level", "?")
            print(f"  [{level}]       ", end="")
        print()
    
    print("\n" + "-"*80)
    print("Niveles: 1=Bajo ✅  2=Medio 🟢  3=Alto 🟡  4=Muy Alto 🟠  5=Crítico 🔴")
    print("="*80 + "\n")
