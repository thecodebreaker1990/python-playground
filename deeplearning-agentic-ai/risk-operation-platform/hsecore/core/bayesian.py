"""
HSE Bayesian Module - Modelo Poisson-Gamma para predicción de incidentes
========================================================================

Usa inferencia Bayesiana para estimar la tasa de eventos y
calcular probabilidad de incidentes futuros.

El modelo:
- Prior: Gamma(alpha, beta) para la tasa de eventos por hora
- Likelihood: Poisson para el conteo de eventos
- Posterior: Gamma actualizado con datos observados
"""
from __future__ import annotations

import math
from typing import List, Tuple

from .models import Row, BayesianPrior
from .scoring import _to_float


def effective_events(row: Row) -> float:
    """
    Convierte diferentes tipos de eventos en un conteo único de 'eventos efectivos'.
    
    Pesos sugeridos (validar con comité HSE):
    - LTI (Lost Time Injury): 3x - más severo
    - HiPo (High Potential): 2x - casi fue grave
    - Recordable: 1x - evento base
    
    Args:
        row: Registro mensual del contratista
        
    Returns:
        Eventos efectivos ponderados
    """
    recordables = _to_float(row.extra.get("recordables", 0), 0.0)
    lti = _to_float(row.extra.get("lti", 0), 0.0)
    hipo = _to_float(row.extra.get("hipo", 0), 0.0)
    
    return recordables + 3.0 * lti + 2.0 * hipo


def bayes_event_rate_per_hour(
    rows: List[Row], 
    prior: BayesianPrior
) -> Tuple[float, float, float]:
    """
    Calcula el posterior para lambda (tasa de eventos por hora).
    
    Usa conjugación Gamma-Poisson:
    - Prior: Gamma(alpha, beta)
    - Posterior: Gamma(alpha + sum(events), beta + sum(hours))
    
    Args:
        rows: Lista de registros mensuales
        prior: Prior Gamma(alpha, beta)
        
    Returns:
        Tupla (lambda_hat, alpha_post, beta_post):
        - lambda_hat: Media posterior (alpha/beta)
        - alpha_post: Alpha del posterior
        - beta_post: Beta del posterior
    """
    alpha = prior.alpha
    beta = prior.beta

    for r in rows:
        alpha += effective_events(r)
        beta += max(r.hours, 0.0)

    lam = alpha / max(beta, 1e-9)
    return lam, alpha, beta


def prob_at_least_one_event_next_hours(
    lambda_per_hour: float, 
    next_hours: float
) -> float:
    """
    Calcula la probabilidad de al menos un evento en las próximas horas.
    
    Usa distribución Poisson:
    P(N >= 1) = 1 - P(N = 0) = 1 - exp(-lambda * hours)
    
    Args:
        lambda_per_hour: Tasa de eventos por hora (posterior mean)
        next_hours: Horas de exposición proyectadas
        
    Returns:
        Probabilidad de al menos un evento (0-1)
    """
    next_hours = max(next_hours, 0.0)
    return 1.0 - math.exp(-lambda_per_hour * next_hours)


def estimate_incident_probability_30d(
    rows: List[Row],
    prior: BayesianPrior = BayesianPrior(),
    hours_next_month: float = None
) -> float:
    """
    Estima la probabilidad de incidente en los próximos 30 días.
    
    Función de conveniencia que combina el cálculo Bayesiano
    con una estimación de horas si no se proporciona.
    
    Args:
        rows: Historial del contratista
        prior: Prior Gamma (usa default si no se especifica)
        hours_next_month: Horas proyectadas (si None, usa promedio)
        
    Returns:
        Probabilidad de incidente en 30 días (0-100 en porcentaje)
    """
    if not rows:
        return 0.0
    
    # Estimar horas del próximo mes si no se proporciona
    if hours_next_month is None:
        # Usar promedio de últimos 3 meses
        recent_hours = [r.hours for r in rows[-3:] if r.hours > 0]
        hours_next_month = sum(recent_hours) / len(recent_hours) if recent_hours else 0
    
    lambda_hat, _, _ = bayes_event_rate_per_hour(rows, prior)
    prob = prob_at_least_one_event_next_hours(lambda_hat, hours_next_month)
    
    return prob * 100.0  # Convertir a porcentaje


def credible_interval_rate(
    rows: List[Row],
    prior: BayesianPrior = BayesianPrior(),
    confidence: float = 0.95
) -> Tuple[float, float, float]:
    """
    Calcula intervalo de credibilidad para la tasa de eventos.
    
    Usa la distribución Gamma posterior para obtener cuantiles.
    
    Args:
        rows: Historial del contratista
        prior: Prior Gamma
        confidence: Nivel de confianza (default 0.95)
        
    Returns:
        Tupla (lower, mean, upper) para la tasa por 1000 horas
    """
    import scipy.stats as stats  # Import local para no requerir scipy siempre
    
    _, alpha_post, beta_post = bayes_event_rate_per_hour(rows, prior)
    
    # Gamma(alpha, 1/beta) en scipy usa scale = 1/beta
    dist = stats.gamma(alpha_post, scale=1.0/beta_post)
    
    alpha_tail = (1 - confidence) / 2
    lower = dist.ppf(alpha_tail) * 1000  # por 1000 horas
    upper = dist.ppf(1 - alpha_tail) * 1000
    mean = (alpha_post / beta_post) * 1000
    
    return lower, mean, upper
