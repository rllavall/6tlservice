# app/derivaciones_service.py
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import derivaciones, models


class DerivacionError(Exception):
    """Error de negocio en derivaciones (→ HTTP 409)."""


def generar_referencia(db: Session) -> str:
    """Siguiente `RMA-NNNN` mirando `Derivacion.tu_referencia`."""
    nums = []
    for (ref,) in db.query(models.Derivacion.tu_referencia).all():
        if ref and ref.startswith("RMA-"):
            try:
                nums.append(int(ref.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"RMA-{n:04d}"


def crear(db: Session, incidencia: models.Incidencia, tipo: str,
          fabricante_id: Optional[int] = None, departamento: Optional[str] = None,
          hoy: Optional[date] = None) -> models.Derivacion:
    hoy = hoy or date.today()
    if tipo not in models.TIPOS_DERIVACION:
        raise DerivacionError(f"Tipo de derivación inválido: {tipo}")
    if tipo == "externa_fabricante" and fabricante_id is None:
        raise DerivacionError("Una derivación externa requiere fabricante_id")
    if tipo == "interna_departamento" and not departamento:
        raise DerivacionError("Una derivación interna requiere departamento")
    d = models.Derivacion(
        incidencia_id=incidencia.id,
        tipo=tipo,
        fabricante_id=fabricante_id,
        departamento=departamento,
        tu_referencia=generar_referencia(db),
        estado="pendiente",
        fecha_creacion=hoy,
    )
    db.add(d)
    db.flush()
    return d


def avanzar(db: Session, derivacion: models.Derivacion, nuevo_estado: str,
            referencia_externa: Optional[str] = None, hoy: Optional[date] = None) -> models.Derivacion:
    hoy = hoy or date.today()
    if not derivaciones.transicion_valida(derivacion.estado, nuevo_estado):
        raise DerivacionError(
            f"Transición inválida {derivacion.estado} -> {nuevo_estado}")
    derivacion.estado = nuevo_estado
    if referencia_externa is not None:
        derivacion.referencia_externa = referencia_externa
    if nuevo_estado == "enviada" and derivacion.fecha_envio is None:
        derivacion.fecha_envio = hoy
    if nuevo_estado == "cerrada":
        derivacion.fecha_cierre = hoy
        _resolver_incidencia(db, derivacion.incidencia_id, hoy)
    db.flush()
    return derivacion


def _resolver_incidencia(db: Session, incidencia_id: int, hoy: date) -> None:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None or inc.estado in ("resuelta", "cerrada"):
        return
    inc.estado = "resuelta"
    inc.fecha_resolucion = hoy
