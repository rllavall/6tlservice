"""Lógica pura de SLA por nivel de contrato. Granularidad en HORAS.
El DÍA sale de la fecha autoritativa (fecha_*); la HORA, de la marca de evento si existe. `ahora` inyectable."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from math import ceil
from typing import Optional

SLA_NIVELES: dict[str, dict[str, int]] = {
    "gold": {"respuesta_horas": 2, "resolucion_horas": 24},
    "silver": {"respuesta_horas": 4, "resolucion_horas": 48},
    "bronze": {"respuesta_horas": 8, "resolucion_horas": 168},
}

_ORDEN = {"sin_sla": 0, "en_plazo": 1, "en_riesgo": 2, "incumplido": 3}


def _primera(*fechas: Optional[date]) -> Optional[date]:
    for f in fechas:
        if f is not None:
            return f
    return None


def _combinar(dia: Optional[date], preciso: Optional[datetime]) -> Optional[datetime]:
    if dia is None:
        return None
    return datetime.combine(dia, preciso.time() if preciso is not None else time.min)


def estado_metrica(inicio: datetime, real: Optional[datetime], objetivo_horas: int, ahora: datetime) -> dict:
    objetivo = inicio + timedelta(hours=objetivo_horas)
    if real is not None:
        estado = "en_plazo" if real <= objetivo else "incumplido"
        horas_restantes = None
    else:
        horas_restantes = int((objetivo - ahora).total_seconds() // 3600)
        if ahora > objetivo:
            estado = "incumplido"
        elif horas_restantes <= max(1, ceil(objetivo_horas * 0.25)):
            estado = "en_riesgo"
        else:
            estado = "en_plazo"
    return {"objetivo": objetivo, "real": real, "horas_restantes": horas_restantes, "estado": estado}


def peor(*estados: str) -> str:
    return max(estados, key=lambda e: _ORDEN.get(e, 0)) if estados else "sin_sla"


def evaluar(incidencia, nivel: str, ahora: datetime) -> dict:
    obj = SLA_NIVELES[nivel]
    inicio = _combinar(getattr(incidencia, "fecha_apertura", None), getattr(incidencia, "creada_en", None))
    resp_dia = _primera(
        getattr(incidencia, "fecha_diagnostico", None),
        getattr(incidencia, "fecha_inicio_reparacion", None),
        getattr(incidencia, "fecha_resolucion", None),
    )
    reso_dia = _primera(
        getattr(incidencia, "fecha_resolucion", None),
        getattr(incidencia, "fecha_cierre", None),
    )
    resp_real = _combinar(resp_dia, getattr(incidencia, "respondida_en", None))
    reso_real = _combinar(reso_dia, getattr(incidencia, "resuelta_en", None))
    respuesta = estado_metrica(inicio, resp_real, obj["respuesta_horas"], ahora)
    resolucion = estado_metrica(inicio, reso_real, obj["resolucion_horas"], ahora)
    return {
        "nivel": nivel,
        "respuesta": respuesta,
        "resolucion": resolucion,
        "estado_global": peor(respuesta["estado"], resolucion["estado"]),
    }
