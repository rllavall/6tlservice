from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app import models


def ubicacion_actual(db: Session, equipo_id: int) -> Optional[models.Ubicacion]:
    """Ubicación del último movimiento (mayor fecha; desempate por id). None si no hay."""
    mov = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.equipo_id == equipo_id)
        .order_by(desc(models.Movimiento.fecha), desc(models.Movimiento.id))
        .first()
    )
    if mov is None:
        return None
    return db.get(models.Ubicacion, mov.ubicacion_destino_id)


def registrar_movimiento(
    db: Session,
    equipo_id: int,
    ubicacion_destino_id: int,
    fecha: date,
    motivo: str,
    usuario: Optional[str] = None,
    notas: Optional[str] = None,
) -> models.Movimiento:
    mov = models.Movimiento(
        equipo_id=equipo_id,
        ubicacion_destino_id=ubicacion_destino_id,
        fecha=fecha,
        motivo=motivo,
        usuario=usuario,
        notas=notas,
    )
    db.add(mov)
    db.flush()
    return mov
