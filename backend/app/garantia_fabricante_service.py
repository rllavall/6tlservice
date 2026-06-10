from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import models


class GarantiaError(Exception):
    """Error de negocio en garantía de fabricante (→ HTTP 409)."""


def obtener(db: Session, componente_id: int) -> Optional[models.GarantiaFabricante]:
    return (
        db.query(models.GarantiaFabricante)
        .filter(models.GarantiaFabricante.componente_id == componente_id)
        .first()
    )


def activar(db: Session, componente: models.Componente, meses_garantia: Optional[int] = None,
            responsable: Optional[str] = None, hoy: Optional[date] = None) -> models.GarantiaFabricante:
    """Crea (o reusa, 1:1) la garantía del componente en `pendiente_activacion`."""
    hoy = hoy or date.today()
    fabricante_id = componente.producto.fabricante_id if componente.producto else None
    if meses_garantia is None and componente.producto is not None:
        meses_garantia = componente.producto.meses_garantia_default
    g = obtener(db, componente.id)
    if g is None:
        g = models.GarantiaFabricante(componente_id=componente.id)
        db.add(g)
    g.fabricante_id = fabricante_id
    g.estado = "pendiente_activacion"
    g.fecha_solicitud = hoy
    g.meses_garantia = meses_garantia
    if responsable is not None:
        g.responsable = responsable
    db.flush()
    return g


def confirmar(db: Session, garantia: models.GarantiaFabricante, fecha_activacion: date,
              referencia: Optional[str] = None) -> models.GarantiaFabricante:
    """Registra el feedback del fabricante: pasa a `activada` y arranca el conteo."""
    if garantia.estado != "pendiente_activacion":
        raise GarantiaError(f"La garantía no está pendiente de activación (estado={garantia.estado})")
    garantia.estado = "activada"
    garantia.fecha_activacion = fecha_activacion
    if referencia is not None:
        garantia.referencia_fabricante = referencia
    db.flush()
    return garantia
