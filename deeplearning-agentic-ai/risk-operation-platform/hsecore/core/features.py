"""
HSE Dynamic Features - Sistema extensible de características para scoring
========================================================================

Permite definir nuevas columnas/variables de forma dinámica:
- Cargar desde JSON (sin tocar código)
- Validación automática de tipos
- Normalización configurable
- Registro centralizado

Ejemplo de uso:
    from core.features import FeatureRegistry, ScoringFeature

    # Agregar nueva columna
    registry.add(ScoringFeature(
        name="near_miss_count",
        column="near_misses",
        type="count",
        category="RISK",
        weight=0.15,
        direction="negative",  # más = peor
    ))
    
    # Calcular score con features dinámicos
    score = registry.compute_risk_score(row_data)
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from pathlib import Path


# ---------------------------
# Enums para tipado fuerte
# ---------------------------

class FeatureType(str, Enum):
    """Tipos de datos soportados para features."""
    COUNT = "count"              # Conteo simple: 0, 1, 2, ...
    RATE = "rate"                # Tasa: eventos / 1000 HH
    FLAG = "flag"                # Binario: 0 o 1
    RATIO = "ratio"              # Proporción: 0.0 a 1.0
    PERCENTAGE = "percentage"    # Porcentaje: 0 a 100
    DAYS = "days"                # Días de plazo/retraso
    SCORE = "score"              # Ya es un score 0-100
    CURRENCY = "currency"        # Valor monetario
    CUSTOM = "custom"            # Normalizador personalizado


class FeatureCategory(str, Enum):
    """Categoría del score que afecta."""
    RISK = "RISK"        # Afecta Risk Score
    TRUST = "TRUST"      # Afecta Trust Score
    BOTH = "BOTH"        # Afecta ambos (ponderado)
    PENALTY = "PENALTY"  # Es una penalización directa


class FeatureDirection(str, Enum):
    """Dirección del impacto en el score."""
    POSITIVE = "positive"  # Más valor = mejor score (menos riesgo / más confianza)
    NEGATIVE = "negative"  # Más valor = peor score (más riesgo / menos confianza)


class NormalizationType(str, Enum):
    """Métodos de normalización a escala 0-100."""
    LINEAR = "linear"          # Lineal: (val - min) / (max - min) * 100
    LOGARITHMIC = "log"        # Logarítmica: suaviza valores altos
    SIGMOID = "sigmoid"        # S-curve: suaviza extremos
    STEP = "step"              # Por umbrales discretos
    INVERSE = "inverse"        # Inverso: 100 - linear
    NONE = "none"              # Sin normalización (ya está en escala)


class MissingStrategy(str, Enum):
    """Cómo manejar valores faltantes."""
    ZERO = "zero"          # Tratar como 0
    NEUTRAL = "neutral"    # No afecta el score
    PENALIZE = "penalize"  # Aplicar penalización
    DEFAULT = "default"    # Usar valor por defecto configurado
    EXCLUDE = "exclude"    # Excluir del cálculo


# ---------------------------
# Feature Definition
# ---------------------------

@dataclass
class ScoringFeature:
    """
    Definición completa de una característica/columna para scoring.
    
    Diseñada para ser extensible y configurable sin modificar código.
    Similar a la definición de variables en un modelo de credit scoring.
    
    Attributes:
        name: Identificador único del feature
        column: Nombre de la columna en el CSV/DB (puede diferir del name)
        type: Tipo de dato (count, rate, flag, etc.)
        category: RISK, TRUST, o BOTH
        weight: Ponderación en el score (0.0 a 1.0)
        direction: positive o negative
        normalization: Método de normalización
        min_value: Valor mínimo para normalización
        max_value: Valor máximo para normalización
        cap: Límite superior para prevenir outliers
        floor: Límite inferior
        missing_strategy: Cómo manejar valores faltantes
        default_value: Valor por defecto si falta
        thresholds: Lista de umbrales para clasificar
        labels: Etiquetas para cada umbral
        description: Descripción legible
        enabled: Si está activo en el cálculo
        group: Grupo lógico (ej: "incidents", "documents")
    """
    # Identificación
    name: str
    column: str = ""  # Si vacío, usa 'name'
    description: str = ""
    group: str = "general"
    enabled: bool = True
    
    # Tipo y categoría
    type: Union[FeatureType, str] = FeatureType.COUNT
    category: Union[FeatureCategory, str] = FeatureCategory.RISK
    direction: Union[FeatureDirection, str] = FeatureDirection.NEGATIVE
    
    # Ponderación
    weight: float = 1.0  # Peso relativo en el score
    
    # Normalización
    normalization: Union[NormalizationType, str] = NormalizationType.LINEAR
    min_value: float = 0.0
    max_value: float = 100.0
    cap: float = float('inf')  # Sin cap por defecto
    floor: float = 0.0
    
    # Valores faltantes
    missing_strategy: Union[MissingStrategy, str] = MissingStrategy.ZERO
    default_value: float = 0.0
    
    # Clasificación por umbrales
    thresholds: List[float] = field(default_factory=lambda: [20, 40, 60, 80])
    labels: List[str] = field(default_factory=lambda: ["Very Low", "Low", "Medium", "High", "Critical"])
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Normaliza los tipos de enum strings."""
        if self.column == "":
            self.column = self.name
            
        if isinstance(self.type, str):
            self.type = FeatureType(self.type)
        if isinstance(self.category, str):
            self.category = FeatureCategory(self.category)
        if isinstance(self.direction, str):
            self.direction = FeatureDirection(self.direction)
        if isinstance(self.normalization, str):
            self.normalization = NormalizationType(self.normalization)
        if isinstance(self.missing_strategy, str):
            self.missing_strategy = MissingStrategy(self.missing_strategy)
    
    def get_column_name(self) -> str:
        """Retorna el nombre de columna a usar."""
        return self.column if self.column else self.name
    
    def is_risk_feature(self) -> bool:
        """¿Afecta al Risk Score?"""
        return self.category in (FeatureCategory.RISK, FeatureCategory.BOTH)
    
    def is_trust_feature(self) -> bool:
        """¿Afecta al Trust Score?"""
        return self.category in (FeatureCategory.TRUST, FeatureCategory.BOTH)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario (para JSON)."""
        d = asdict(self)
        # Convertir enums a strings
        for key in ['type', 'category', 'direction', 'normalization', 'missing_strategy']:
            if hasattr(d.get(key), 'value'):
                d[key] = d[key].value
        # Manejar infinitos que no son válidos en JSON
        if d.get('cap') == float('inf'):
            d['cap'] = None
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScoringFeature':
        """Crea desde diccionario (desde JSON)."""
        # Manejar cap=null como infinito
        if data.get('cap') is None:
            data['cap'] = float('inf')
        return cls(**data)


# ---------------------------
# Normalization Functions
# ---------------------------

def _normalize_linear(value: float, min_val: float, max_val: float) -> float:
    """Normalización lineal a 0-100."""
    if max_val == min_val:
        return 0.0
    return ((value - min_val) / (max_val - min_val)) * 100.0


def _normalize_log(value: float, min_val: float, max_val: float) -> float:
    """Normalización logarítmica (suaviza valores altos)."""
    if value <= 0:
        return 0.0
    log_val = math.log1p(value)
    log_max = math.log1p(max_val) if max_val > 0 else 1.0
    log_min = math.log1p(min_val) if min_val > 0 else 0.0
    if log_max == log_min:
        return 0.0
    return ((log_val - log_min) / (log_max - log_min)) * 100.0


def _normalize_sigmoid(value: float, min_val: float, max_val: float) -> float:
    """Normalización sigmoide (suaviza extremos)."""
    midpoint = (max_val + min_val) / 2.0
    scale = (max_val - min_val) / 6.0 if max_val != min_val else 1.0
    x = (value - midpoint) / scale
    return 100.0 / (1.0 + math.exp(-x))


def _normalize_step(value: float, thresholds: List[float]) -> float:
    """Normalización por escalones discretos."""
    for i, threshold in enumerate(thresholds):
        if value < threshold:
            return (i / len(thresholds)) * 100.0
    return 100.0


# ---------------------------
# Feature Registry
# ---------------------------

class FeatureRegistry:
    """
    Registro centralizado de features para scoring.
    
    Permite:
    - Agregar/eliminar features dinámicamente
    - Cargar configuración desde JSON
    - Calcular scores basados en features registrados
    - Validar datos de entrada
    
    Ejemplo:
        registry = FeatureRegistry()
        registry.load_from_json("config/features.json")
        
        risk_score = registry.compute_risk_score(row_data)
        trust_score = registry.compute_trust_score(row_data)
    """
    
    def __init__(self):
        self._features: Dict[str, ScoringFeature] = {}
        self._groups: Dict[str, List[str]] = {}
        
    def add(self, feature: ScoringFeature) -> None:
        """Agrega un feature al registro."""
        self._features[feature.name] = feature
        
        # Agregar al grupo
        if feature.group not in self._groups:
            self._groups[feature.group] = []
        if feature.name not in self._groups[feature.group]:
            self._groups[feature.group].append(feature.name)
    
    def remove(self, name: str) -> bool:
        """Elimina un feature del registro."""
        if name in self._features:
            feature = self._features[name]
            del self._features[name]
            if feature.group in self._groups:
                self._groups[feature.group].remove(name)
            return True
        return False
    
    def get(self, name: str) -> Optional[ScoringFeature]:
        """Obtiene un feature por nombre."""
        return self._features.get(name)
    
    def get_all(self) -> List[ScoringFeature]:
        """Retorna todos los features."""
        return list(self._features.values())
    
    def get_by_category(self, category: FeatureCategory) -> List[ScoringFeature]:
        """Retorna features de una categoría."""
        return [f for f in self._features.values() 
                if f.category == category or f.category == FeatureCategory.BOTH]
    
    def get_risk_features(self) -> List[ScoringFeature]:
        """Retorna features que afectan Risk Score."""
        return [f for f in self._features.values() if f.is_risk_feature() and f.enabled]
    
    def get_trust_features(self) -> List[ScoringFeature]:
        """Retorna features que afectan Trust Score."""
        return [f for f in self._features.values() if f.is_trust_feature() and f.enabled]
    
    def get_by_group(self, group: str) -> List[ScoringFeature]:
        """Retorna features de un grupo."""
        names = self._groups.get(group, [])
        return [self._features[n] for n in names if n in self._features]
    
    def list_groups(self) -> List[str]:
        """Lista todos los grupos."""
        return list(self._groups.keys())
    
    # ---------------------------
    # Extracting & Normalizing
    # ---------------------------
    
    def extract_value(
        self, 
        feature: ScoringFeature, 
        data: Dict[str, Any],
        hours: float = 1.0
    ) -> Tuple[Optional[float], str]:
        """
        Extrae y normaliza el valor de un feature desde los datos.
        
        Args:
            feature: Definición del feature
            data: Diccionario con los datos (row.extra o similar)
            hours: Horas trabajadas (para tasas)
            
        Returns:
            Tupla (valor_normalizado, status) donde status es:
            - "ok": valor extraído correctamente
            - "missing": dato faltante (manejado según missing_strategy)
            - "error": error en extracción
        """
        column = feature.get_column_name()
        raw = data.get(column)
        
        # Manejar valores faltantes
        if raw is None or raw == "" or raw == "N/A":
            if feature.missing_strategy == MissingStrategy.ZERO:
                raw_value = 0.0
            elif feature.missing_strategy == MissingStrategy.DEFAULT:
                raw_value = feature.default_value
            elif feature.missing_strategy == MissingStrategy.PENALIZE:
                return (100.0, "penalized") if feature.direction == FeatureDirection.NEGATIVE else (0.0, "penalized")
            elif feature.missing_strategy == MissingStrategy.NEUTRAL:
                return (None, "neutral")
            elif feature.missing_strategy == MissingStrategy.EXCLUDE:
                return (None, "excluded")
            else:
                return (None, "missing")
        else:
            try:
                raw_value = float(raw)
            except (ValueError, TypeError):
                return (None, "error")
        
        # Aplicar floor y cap
        raw_value = max(feature.floor, min(feature.cap, raw_value))
        
        # Transformar según tipo
        if feature.type == FeatureType.RATE:
            hours = max(hours, 1.0)
            raw_value = (raw_value / hours) * 1000.0
        elif feature.type == FeatureType.FLAG:
            raw_value = 1.0 if raw_value >= 1 else 0.0
        elif feature.type == FeatureType.PERCENTAGE:
            raw_value = raw_value  # Ya en escala 0-100
        elif feature.type == FeatureType.RATIO:
            raw_value = raw_value * 100.0 if raw_value <= 1.0 else raw_value
        
        # Normalizar a 0-100
        if feature.normalization == NormalizationType.NONE:
            normalized = raw_value
        elif feature.normalization == NormalizationType.LINEAR:
            normalized = _normalize_linear(raw_value, feature.min_value, feature.max_value)
        elif feature.normalization == NormalizationType.LOGARITHMIC:
            normalized = _normalize_log(raw_value, feature.min_value, feature.max_value)
        elif feature.normalization == NormalizationType.SIGMOID:
            normalized = _normalize_sigmoid(raw_value, feature.min_value, feature.max_value)
        elif feature.normalization == NormalizationType.STEP:
            normalized = _normalize_step(raw_value, feature.thresholds)
        elif feature.normalization == NormalizationType.INVERSE:
            normalized = 100.0 - _normalize_linear(raw_value, feature.min_value, feature.max_value)
        else:
            normalized = raw_value
        
        # Clamp final
        normalized = max(0.0, min(100.0, normalized))
        
        return (normalized, "ok")
    
    # ---------------------------
    # Score Calculation
    # ---------------------------
    
    def compute_weighted_score(
        self,
        features: List[ScoringFeature],
        data: Dict[str, Any],
        hours: float = 1.0
    ) -> Tuple[float, List[Tuple[str, float, float]]]:
        """
        Calcula score ponderado para un conjunto de features.
        
        Args:
            features: Lista de features a usar
            data: Datos del contratista
            hours: Horas trabajadas
            
        Returns:
            Tupla (score_total, contributions) donde contributions
            es lista de (nombre, contribución, peso)
        """
        contributions: List[Tuple[str, float, float]] = []
        total_weight = 0.0
        weighted_sum = 0.0
        
        for feature in features:
            if not feature.enabled:
                continue
                
            value, status = self.extract_value(feature, data, hours)
            
            if value is None:
                continue
            
            # Invertir si es dirección positiva (más = mejor = menos riesgo)
            if feature.direction == FeatureDirection.POSITIVE:
                value = 100.0 - value
            
            contribution = value * feature.weight
            weighted_sum += contribution
            total_weight += feature.weight
            
            contributions.append((feature.name, contribution, feature.weight))
        
        if total_weight == 0:
            return (0.0, contributions)
        
        # Normalizar por peso total
        final_score = weighted_sum / total_weight
        
        return (max(0.0, min(100.0, final_score)), contributions)
    
    def compute_risk_score(
        self,
        data: Dict[str, Any],
        hours: float = 1.0
    ) -> Tuple[float, List[Tuple[str, float, float]]]:
        """Calcula Risk Score usando features de tipo RISK."""
        features = self.get_risk_features()
        return self.compute_weighted_score(features, data, hours)
    
    def compute_trust_score(
        self,
        data: Dict[str, Any],
        hours: float = 1.0
    ) -> Tuple[float, List[Tuple[str, float, float]]]:
        """Calcula Trust Score usando features de tipo TRUST."""
        features = self.get_trust_features()
        return self.compute_weighted_score(features, data, hours)
    
    # ---------------------------
    # JSON Persistence
    # ---------------------------
    
    def to_dict(self) -> Dict[str, Any]:
        """Exporta el registro completo a diccionario."""
        return {
            "version": "1.0",
            "features": [f.to_dict() for f in self._features.values()]
        }
    
    def to_json(self, path: str = None) -> str:
        """Exporta a JSON string o archivo."""
        data = self.to_dict()
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(json_str)
        
        return json_str
    
    def load_from_dict(self, data: Dict[str, Any]) -> int:
        """Carga features desde diccionario. Retorna cantidad cargada."""
        features = data.get("features", [])
        count = 0
        
        for f_data in features:
            try:
                feature = ScoringFeature.from_dict(f_data)
                self.add(feature)
                count += 1
            except Exception as e:
                print(f"Error cargando feature: {e}")
        
        return count
    
    def load_from_json(self, path: str) -> int:
        """Carga features desde archivo JSON."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return self.load_from_dict(data)
    
    # ---------------------------
    # Validation
    # ---------------------------
    
    def validate_data(self, data: Dict[str, Any]) -> List[str]:
        """
        Valida que los datos tengan las columnas requeridas.
        
        Returns:
            Lista de mensajes de error (vacía si todo OK)
        """
        errors = []
        
        for feature in self._features.values():
            if not feature.enabled:
                continue
                
            column = feature.get_column_name()
            if column not in data:
                if feature.missing_strategy not in (MissingStrategy.NEUTRAL, MissingStrategy.EXCLUDE):
                    errors.append(f"Columna faltante: {column} (requerida por {feature.name})")
        
        return errors
    
    def get_required_columns(self) -> List[str]:
        """Retorna lista de columnas requeridas."""
        columns = set()
        for feature in self._features.values():
            if feature.enabled:
                columns.add(feature.get_column_name())
        return sorted(columns)


# ---------------------------
# Default Features Factory
# ---------------------------

def create_default_risk_features() -> List[ScoringFeature]:
    """Crea features por defecto para Risk Score."""
    return [
        ScoringFeature(
            name="recordables",
            column="recordables",
            description="Incidentes registrables OSHA",
            type=FeatureType.COUNT,
            category=FeatureCategory.RISK,
            weight=0.25,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.LOGARITHMIC,
            max_value=10,
            group="incidents"
        ),
        ScoringFeature(
            name="lti",
            column="lti",
            description="Lesiones con tiempo perdido (Lost Time Injuries)",
            type=FeatureType.COUNT,
            category=FeatureCategory.RISK,
            weight=0.30,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.LOGARITHMIC,
            max_value=5,
            group="incidents"
        ),
        ScoringFeature(
            name="hipo",
            column="hipo",
            description="Incidentes de alto potencial (HiPo)",
            type=FeatureType.COUNT,
            category=FeatureCategory.RISK,
            weight=0.20,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.LOGARITHMIC,
            max_value=3,
            group="incidents"
        ),
        ScoringFeature(
            name="critical_overdue",
            column="critical_actions_overdue",
            description="Acciones críticas vencidas",
            type=FeatureType.COUNT,
            category=FeatureCategory.RISK,
            weight=0.15,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.LINEAR,
            max_value=10,
            group="actions"
        ),
        ScoringFeature(
            name="missing_monthly_close",
            column="monthly_close_missing",
            description="Cierres mensuales faltantes",
            type=FeatureType.COUNT,
            category=FeatureCategory.RISK,
            weight=0.10,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.LINEAR,
            max_value=3,
            group="compliance"
        ),
        # ---------------------------
        # RIESGO FINANCIERO
        # ---------------------------
        ScoringFeature(
            name="financial_risk",
            column="financial_risk_score",
            description="Score de riesgo financiero del contratista (deudas, impagos, liquidez)",
            type=FeatureType.SCORE,
            category=FeatureCategory.RISK,
            weight=0.12,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.NONE,  # Ya viene como score 0-100
            max_value=100,
            group="financial",
            thresholds=[20, 40, 60, 80],
            labels=["Sólido", "Estable", "Moderado", "Alto", "Crítico"],
            metadata={"source": "bureau_financiero", "update_frequency": "monthly"}
        ),
        ScoringFeature(
            name="payment_delays",
            column="avg_payment_delay_days",
            description="Promedio de días de retraso en pagos a proveedores",
            type=FeatureType.DAYS,
            category=FeatureCategory.RISK,
            weight=0.08,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.LOGARITHMIC,
            max_value=90,  # Más de 90 días es crítico
            group="financial",
            thresholds=[15, 30, 45, 60],
            labels=["A tiempo", "Leve", "Moderado", "Severo", "Crítico"]
        ),
        # ---------------------------
        # RIESGO REPUTACIONAL / PÚBLICO
        # ---------------------------
        ScoringFeature(
            name="reputational_risk",
            column="reputation_score",
            description="Score de riesgo reputacional (prensa negativa, redes sociales, demandas públicas)",
            type=FeatureType.SCORE,
            category=FeatureCategory.RISK,
            weight=0.10,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.NONE,
            max_value=100,
            group="reputational",
            thresholds=[20, 40, 60, 80],
            labels=["Excelente", "Buena", "Neutral", "Negativa", "Crisis"],
            metadata={"source": "media_monitoring", "includes": ["news", "social_media", "legal"]}
        ),
        ScoringFeature(
            name="negative_media_mentions",
            column="negative_news_count",
            description="Cantidad de menciones negativas en medios en últimos 12 meses",
            type=FeatureType.COUNT,
            category=FeatureCategory.RISK,
            weight=0.06,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.LOGARITHMIC,
            max_value=50,
            group="reputational",
            thresholds=[2, 5, 10, 20],
            labels=["Ninguna", "Aisladas", "Moderadas", "Frecuentes", "Crisis"]
        ),
        ScoringFeature(
            name="active_lawsuits",
            column="pending_lawsuits",
            description="Demandas laborales o ambientales activas",
            type=FeatureType.COUNT,
            category=FeatureCategory.RISK,
            weight=0.08,
            direction=FeatureDirection.NEGATIVE,
            normalization=NormalizationType.LINEAR,
            max_value=10,
            group="reputational",
            thresholds=[1, 2, 4, 6],
            labels=["Ninguna", "Baja", "Moderada", "Alta", "Muy Alta"]
        ),
    ]


def create_default_trust_features() -> List[ScoringFeature]:
    """Crea features por defecto para Trust Score."""
    return [
        ScoringFeature(
            name="data_completeness",
            column="data_quality_score",
            description="Completitud de datos reportados",
            type=FeatureType.PERCENTAGE,
            category=FeatureCategory.TRUST,
            weight=0.30,
            direction=FeatureDirection.POSITIVE,
            normalization=NormalizationType.NONE,
            group="quality"
        ),
        ScoringFeature(
            name="ontime_reports",
            column="reports_on_time_pct",
            description="Porcentaje de reportes a tiempo",
            type=FeatureType.PERCENTAGE,
            category=FeatureCategory.TRUST,
            weight=0.25,
            direction=FeatureDirection.POSITIVE,
            normalization=NormalizationType.NONE,
            group="quality"
        ),
        ScoringFeature(
            name="action_closure_rate",
            column="actions_closed_pct",
            description="Tasa de cierre de acciones",
            type=FeatureType.PERCENTAGE,
            category=FeatureCategory.TRUST,
            weight=0.25,
            direction=FeatureDirection.POSITIVE,
            normalization=NormalizationType.NONE,
            group="actions"
        ),
        ScoringFeature(
            name="months_without_incident",
            column="months_no_incident",
            description="Meses consecutivos sin incidentes",
            type=FeatureType.COUNT,
            category=FeatureCategory.TRUST,
            weight=0.20,
            direction=FeatureDirection.POSITIVE,
            normalization=NormalizationType.LINEAR,
            max_value=12,
            group="safety"
        ),
    ]


def create_default_registry() -> FeatureRegistry:
    """Crea un registro con features por defecto."""
    registry = FeatureRegistry()
    
    for f in create_default_risk_features():
        registry.add(f)
    
    for f in create_default_trust_features():
        registry.add(f)
    
    return registry


# ---------------------------
# Quick Example
# ---------------------------

if __name__ == "__main__":
    # Demo de uso
    registry = create_default_registry()
    
    # Simular datos de un contratista
    contractor_data = {
        "recordables": 2,
        "lti": 0,
        "hipo": 1,
        "critical_actions_overdue": 3,
        "monthly_close_missing": 1,
        "data_quality_score": 85,
        "reports_on_time_pct": 90,
        "actions_closed_pct": 75,
        "months_no_incident": 2,
    }
    
    # Calcular scores
    risk_score, risk_contrib = registry.compute_risk_score(contractor_data, hours=5000)
    trust_score, trust_contrib = registry.compute_trust_score(contractor_data)
    
    print("=" * 60)
    print("DEMO: Feature Registry")
    print("=" * 60)
    
    print(f"\nRisk Score: {risk_score:.1f}/100")
    print("Contribuciones:")
    for name, contrib, weight in risk_contrib:
        print(f"  - {name}: {contrib:.1f} (peso: {weight:.2f})")
    
    print(f"\nTrust Score: {trust_score:.1f}/100")
    print("Contribuciones:")
    for name, contrib, weight in trust_contrib:
        print(f"  - {name}: {contrib:.1f} (peso: {weight:.2f})")
    
    print("\nColumnas requeridas:")
    print(f"  {registry.get_required_columns()}")
    
    # Exportar a JSON
    print("\nExportando a features_config.json...")
    registry.to_json("features_config.json")
    print("✅ Listo!")
