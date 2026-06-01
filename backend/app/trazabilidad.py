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
    incidencia_id: Optional[int] = None,
) -> models.Movimiento:
    mov = models.Movimiento(
        equipo_id=equipo_id,
        ubicacion_destino_id=ubicacion_destino_id,
        fecha=fecha,
        motivo=motivo,
        usuario=usuario,
        notas=notas,
        incidencia_id=incidencia_id,
    )
    db.add(mov)
    db.flush()
    return mov


class ConfiguracionError(Exception):
    """Estado de montaje inválido (ya montado / no montado)."""


def montar_componente(
    db: Session,
    componente_id: int,
    equipo_id: int,
    posicion: Optional[str],
    fecha: date,
    motivo: str,
    usuario: Optional[str] = None,
    notas: Optional[str] = None,
    incidencia_id: Optional[int] = None,
) -> models.CambioConfiguracion:
    comp = db.get(models.Componente, componente_id)
    if comp is None:
        raise LookupError("Componente no encontrado")
    if db.get(models.Equipo, equipo_id) is None:
        raise LookupError("Equipo no encontrado")
    if comp.equipo_id is not None:
        raise ConfiguracionError("El componente ya está montado; desmóntalo primero")
    comp.equipo_id = equipo_id
    comp.posicion = posicion
    comp.fecha_montaje = fecha
    evento = models.CambioConfiguracion(
        componente_id=componente_id, equipo_id=equipo_id, accion="montaje",
        posicion=posicion, fecha=fecha, motivo=motivo, usuario=usuario, notas=notas,
        incidencia_id=incidencia_id,
    )
    db.add(evento)
    db.flush()
    return evento


def desmontar_componente(
    db: Session,
    componente_id: int,
    fecha: date,
    motivo: str,
    usuario: Optional[str] = None,
    notas: Optional[str] = None,
    incidencia_id: Optional[int] = None,
) -> models.CambioConfiguracion:
    comp = db.get(models.Componente, componente_id)
    if comp is None:
        raise LookupError("Componente no encontrado")
    if comp.equipo_id is None:
        raise ConfiguracionError("El componente no está montado en ningún equipo")
    equipo_id = comp.equipo_id
    evento = models.CambioConfiguracion(
        componente_id=componente_id, equipo_id=equipo_id, accion="desmontaje",
        posicion=comp.posicion, fecha=fecha, motivo=motivo, usuario=usuario, notas=notas,
        incidencia_id=incidencia_id,
    )
    db.add(evento)
    comp.equipo_id = None
    comp.posicion = None
    db.flush()
    return evento


def sustituir_componente(
    db: Session,
    equipo_id: int,
    componente_saliente_id: int,
    componente_entrante_id: int,
    posicion: Optional[str],
    fecha: date,
    motivo: str,
    usuario: Optional[str] = None,
    notas: Optional[str] = None,
    incidencia_id: Optional[int] = None,
) -> dict:
    """Desmonta el saliente y monta el entrante en el mismo equipo. Atómico:
    si el montaje falla, NO se aplica el desmontaje (la sesión se revierte arriba)."""
    if db.get(models.Equipo, equipo_id) is None:
        raise LookupError("Equipo no encontrado")
    saliente = db.get(models.Componente, componente_saliente_id)
    if saliente is None:
        raise LookupError("Componente saliente no encontrado")
    if saliente.equipo_id != equipo_id:
        raise ConfiguracionError("El componente saliente no está montado en este equipo")
    # Both operations share the session; the router commits once at the end.
    desmontaje = desmontar_componente(db, componente_saliente_id, fecha, motivo, usuario, notas, incidencia_id)
    montaje = montar_componente(db, componente_entrante_id, equipo_id, posicion, fecha, motivo, usuario, notas, incidencia_id)
    return {"desmontaje": desmontaje, "montaje": montaje}
