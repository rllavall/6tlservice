"""Lógica pura de SLA por nivel de contrato. No importa models: duck-typing + `hoy` inyectable.
Granularidad en días (las fechas de incidencia son Date)."""
from __future__ import annotations

from datetime import date, timedelta
from math import ceil
from typing import Optional

SLA_NIVELES: dict[str, dict[str, int]] = {
    "gold": {"respuesta_dias": 1, "resolucion_dias": 5},
    "silver": {"respuesta_dias": 2, "resolucion_dias": 10},
    "bronze": {"respuesta_dias": 3, "resolucion_dias": 15},
}

_ORDEN = {"sin_sla": 0, "en_plazo": 1, "en_riesgo": 2, "incumplido": 3}


def _primera(*fechas: Optional[date]) -> Optional[date]:
    for f in fechas:
        if f is not None:
            return f
    return None


def estado_metrica(apertura: date, fecha_real: Optional[date], objetivo_dias: int, hoy: date) -> dict:
    objetivo = apertura + timedelta(days=objetivo_dias)
    if fecha_real is not None:
        estado = "en_plazo" if fecha_real <= objetivo else "incumplido"
    elif hoy > objetivo:
        estado = "incumplido"
    elif (objetivo - hoy).days <= max(1, ceil(objetivo_dias * 0.25)):
        estado = "en_riesgo"
    else:
        estado = "en_plazo"
    return {
        "objetivo_fecha": objetivo,
        "fecha_real": fecha_real,
        # Solo tiene sentido mientras la métrica está pendiente; si ya se cumplió, None.
        "dias_restantes": None if fecha_real is not None else (objetivo - hoy).days,
        "estado": estado,
    }


def peor(*estados: str) -> str:
    return max(estados, key=lambda e: _ORDEN.get(e, 0)) if estados else "sin_sla"


def evaluar(incidencia, nivel: str, hoy: date) -> dict:
    objetivos = SLA_NIVELES[nivel]
    apertura = incidencia.fecha_apertura
    resp_real = _primera(
        getattr(incidencia, "fecha_diagnostico", None),
        getattr(incidencia, "fecha_inicio_reparacion", None),
        getattr(incidencia, "fecha_resolucion", None),
    )
    reso_real = _primera(
        getattr(incidencia, "fecha_resolucion", None),
        getattr(incidencia, "fecha_cierre", None),
    )
    respuesta = estado_metrica(apertura, resp_real, objetivos["respuesta_dias"], hoy)
    resolucion = estado_metrica(apertura, reso_real, objetivos["resolucion_dias"], hoy)
    return {
        "nivel": nivel,
        "respuesta": respuesta,
        "resolucion": resolucion,
        "estado_global": peor(respuesta["estado"], resolucion["estado"]),
    }
