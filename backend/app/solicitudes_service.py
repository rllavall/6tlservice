from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app import garantia
from app import incidencias_service as inc_svc
from app import models


class SolicitudError(Exception):
    """Error de negocio en solicitudes (→ 409)."""


def generar_codigo(db: Session) -> str:
    """Siguiente código `SOL-NNNN`."""
    nums = []
    for (codigo,) in db.query(models.SolicitudSoporte.codigo).all():
        if codigo and codigo.startswith("SOL-"):
            try:
                nums.append(int(codigo.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"SOL-{n:04d}"


def aprobar(db: Session, sol: models.SolicitudSoporte, payload) -> models.Incidencia:
    if sol.estado != "pendiente":
        raise SolicitudError("La solicitud ya no está pendiente")
    eq = None
    if payload.equipo_id is not None:
        eq = db.get(models.Equipo, payload.equipo_id)
        if eq is None:
            raise LookupError("Equipo no encontrado")
    if payload.componente_id is not None and db.get(models.Componente, payload.componente_id) is None:
        raise LookupError("Componente no encontrado")
    if payload.equipo_id is None and payload.componente_id is None:
        raise SolicitudError("Indica equipo_id o componente_id (al menos uno)")

    en_gar = payload.en_garantia
    if payload.tipo == "rma" and en_gar is None and eq is not None:
        en_gar = garantia.equipo_en_garantia(eq, date.today())

    inc = models.Incidencia(
        codigo=inc_svc.generar_codigo(db, payload.tipo),
        tipo=payload.tipo,
        estado="abierta",
        equipo_id=payload.equipo_id,
        componente_id=payload.componente_id,
        titulo=sol.titulo,
        descripcion_problema=sol.descripcion_problema,
        prioridad=payload.prioridad,
        asignado_a=payload.asignado_a,
        en_garantia=en_gar,
        fecha_apertura=date.today(),
    )
    db.add(inc)
    db.flush()
    sol.estado = "aprobada"
    sol.incidencia_id = inc.id
    sol.fecha_resolucion = date.today()
    db.commit()
    db.refresh(inc)
    return inc


def rechazar(db: Session, sol: models.SolicitudSoporte, motivo: str) -> None:
    if sol.estado != "pendiente":
        raise SolicitudError("La solicitud ya no está pendiente")
    sol.estado = "rechazada"
    sol.motivo_rechazo = motivo
    sol.fecha_resolucion = date.today()
    db.commit()
