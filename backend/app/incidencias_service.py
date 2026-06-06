from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models

ORDEN = {e: i for i, e in enumerate(models.ESTADOS_INCIDENCIA)}
FECHA_DE_ESTADO = {
    "diagnostico": "fecha_diagnostico",
    "en_reparacion": "fecha_inicio_reparacion",
    "resuelta": "fecha_resolucion",
    "cerrada": "fecha_cierre",
}


class IncidenciaError(Exception):
    """Transición inválida o guarda de contenido no cumplida (→ 409)."""


_PREFIJO_TIPO = {
    "rma": "RMA",
    "soporte_venta": "SV",
    "soporte_tecnico": "ST",
    "calibracion": "CAL",
}


def generar_codigo(db: Session, tipo: str = "rma") -> str:
    """Siguiente código `PREFIJO-NNNN` (secuencia propia por prefijo de tipo)."""
    prefijo = _PREFIJO_TIPO.get(tipo, "RMA")
    nums = []
    for (codigo,) in db.query(models.Incidencia.codigo).all():
        if codigo and codigo.startswith(prefijo + "-"):
            try:
                nums.append(int(codigo.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"{prefijo}-{n:04d}"


def transicionar(
    db: Session, inc: models.Incidencia, nuevo_estado: str, fecha: Optional[date]
) -> models.Incidencia:
    actual = inc.estado
    es_reabrir = actual in ("resuelta", "cerrada") and nuevo_estado == "en_reparacion"
    es_avance = ORDEN.get(nuevo_estado, -1) == ORDEN.get(actual, -99) + 1

    if not (es_avance or es_reabrir):
        raise IncidenciaError(
            f"Transición no permitida: {actual} → {nuevo_estado}"
        )
    if nuevo_estado == "resuelta" and not (inc.resolucion and inc.resolucion.strip()):
        raise IncidenciaError("Para resolver la incidencia hace falta una resolución")

    fecha = fecha or date.today()
    ahora = datetime.now()

    if es_reabrir:
        inc.fecha_resolucion = None
        inc.fecha_cierre = None
        inc.resuelta_en = None
        inc.estado = "en_reparacion"
        db.flush()
        return inc

    inc.estado = nuevo_estado
    campo = FECHA_DE_ESTADO.get(nuevo_estado)
    if campo is not None:
        setattr(inc, campo, fecha)
    if nuevo_estado in ("diagnostico", "en_reparacion") and inc.respondida_en is None:
        inc.respondida_en = ahora
    if nuevo_estado == "resuelta":
        inc.resuelta_en = ahora
    db.flush()
    return inc
