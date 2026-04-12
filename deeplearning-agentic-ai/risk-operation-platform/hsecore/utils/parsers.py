"""
HSE Parsers Module - Importación de datos
=========================================

Este módulo maneja la importación de datos desde diferentes fuentes.
Actualmente soporta CSV (para pruebas).

NOTA IMPORTANTE:
Este módulo es temporal para pruebas con CSV.
En producción, reemplazar con:
- rows_from_database() para leer desde PostgreSQL/MySQL
- rows_from_api() para leer desde API REST
- rows_from_s3() para leer desde S3

La estructura Row es la misma independientemente de la fuente.
"""
from __future__ import annotations

import csv
from typing import Any, Dict, List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import Row


def _to_float(x: Any, default: float = 0.0) -> float:
    """Convierte a float de forma segura."""
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def _to_int(x: Any, default: int = 0) -> int:
    """Convierte a int de forma segura."""
    try:
        if x is None or x == "":
            return default
        return int(float(x))
    except Exception:
        return default


def parse_csv(path: str) -> List[Row]:
    """
    Parse un archivo CSV a lista de Row.
    
    SOLO PARA PRUEBAS - En producción usar rows_from_database()
    
    Columnas requeridas:
    - contractor: Nombre del contratista
    - month: Mes en formato YYYY-MM
    - hours: Horas trabajadas
    - operated: 1 si operó, 0 si no
    - monthly_close_submitted: 1 si envió cierre mensual
    
    Columnas opcionales (se guardan en extra):
    - recordables, lti, hipo, actions_open, actions_closed, etc.
    
    Args:
        path: Ruta al archivo CSV
        
    Returns:
        Lista de Row
    """
    rows: List[Row] = []
    
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        for r in reader:
            contractor = (r.get("contractor") or "").strip()
            month = (r.get("month") or "").strip()
            hours = _to_float(r.get("hours"), 0.0)
            operated = _to_int(r.get("operated"), 0)
            monthly_close_submitted = _to_int(r.get("monthly_close_submitted"), 0)

            # Todo lo demás va a extra
            extra = dict(r)
            for k in ["contractor", "month", "hours", "operated", "monthly_close_submitted"]:
                extra.pop(k, None)

            rows.append(Row(
                contractor=contractor,
                month=month,
                hours=hours,
                operated=operated,
                monthly_close_submitted=monthly_close_submitted,
                extra=extra
            ))
    
    return rows


def rows_from_dicts(data: List[Dict[str, Any]]) -> List[Row]:
    """
    Convierte lista de diccionarios a lista de Row.
    
    Útil para:
    - Lambda handler (recibe JSON)
    - API responses
    - Base de datos (fetchall como dicts)
    
    Args:
        data: Lista de diccionarios con los campos necesarios
        
    Returns:
        Lista de Row
    """
    rows: List[Row] = []
    
    for r in data:
        contractor = str(r.get("contractor", "")).strip()
        month = str(r.get("month", "")).strip()
        hours = _to_float(r.get("hours"), 0.0)
        operated = _to_int(r.get("operated"), 0)
        monthly_close_submitted = _to_int(r.get("monthly_close_submitted"), 0)
        
        extra = {
            k: v for k, v in r.items() 
            if k not in ["contractor", "month", "hours", "operated", "monthly_close_submitted"]
        }
        
        rows.append(Row(
            contractor=contractor,
            month=month,
            hours=hours,
            operated=operated,
            monthly_close_submitted=monthly_close_submitted,
            extra=extra
        ))
    
    return rows


# ---------------------------
# PLANTILLAS PARA PRODUCCIÓN
# ---------------------------

def rows_from_database(connection, query: str = None) -> List[Row]:
    """
    PLANTILLA: Leer datos desde base de datos.
    
    Implementar cuando se conecte a producción.
    
    Args:
        connection: Conexión a la base de datos
        query: Query SQL (opcional, usa default si no se proporciona)
        
    Returns:
        Lista de Row
    """
    # TODO: Implementar cuando se tenga acceso a BD
    # 
    # Ejemplo para PostgreSQL/MySQL:
    # cursor = connection.cursor(dictionary=True)  # MySQL
    # cursor.execute(query or '''
    #     SELECT contractor, month, hours, operated, monthly_close_submitted,
    #            recordables, lti, hipo, actions_open, actions_closed,
    #            actions_overdue, critical_overdue, exec_walks, exec_crit_findings,
    #            rejected_reports, docs_blocked, docs_at_risk
    #     FROM hse_monthly_data
    #     WHERE month >= DATE_FORMAT(NOW() - INTERVAL 6 MONTH, '%Y-%m')
    #     ORDER BY contractor, month
    # ''')
    # data = cursor.fetchall()
    # return rows_from_dicts(data)
    
    raise NotImplementedError("Implementar conexión a base de datos")


def rows_from_s3(bucket: str, key: str) -> List[Row]:
    """
    PLANTILLA: Leer datos desde S3.
    
    Implementar cuando se use S3 como fuente.
    
    Args:
        bucket: Nombre del bucket S3
        key: Key del objeto (archivo)
        
    Returns:
        Lista de Row
    """
    # TODO: Implementar cuando se use S3
    #
    # import boto3
    # import io
    # 
    # s3 = boto3.client('s3')
    # obj = s3.get_object(Bucket=bucket, Key=key)
    # data = obj['Body'].read().decode('utf-8')
    # 
    # reader = csv.DictReader(io.StringIO(data))
    # return rows_from_dicts(list(reader))
    
    raise NotImplementedError("Implementar lectura desde S3")
