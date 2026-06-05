from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import contratos
from app import incidencias_service as inc_svc
from app import models


class PreventivoError(Exception):
    """Error de negocio en preventivo (→ HTTP 409)."""


def crear(db: Session, equipo: models.Equipo, *, fecha: date, tipo: str, veredicto: str,
          tecnico: Optional[str], informe: Optional[str],
          proxima_fecha: Optional[date]) -> models.AccionPreventiva:
    contrato = equipo.contrato if (equipo.contrato is not None and equipo.contrato.vigente) else None
    if proxima_fecha is None and contrato is not None:
        proxima_fecha = contratos.sugerir_proxima_fecha(fecha, contrato.nivel)
    accion = models.AccionPreventiva(
        equipo_id=equipo.id,
        contrato_id=contrato.id if contrato is not None else None,
        fecha=fecha, tecnico=tecnico, tipo=tipo, veredicto=veredicto,
        informe=informe, proxima_fecha=proxima_fecha,
    )
    db.add(accion)
    db.flush()
    return accion


def generar_incidencia(db: Session, accion: models.AccionPreventiva, *, tipo: str,
                       prioridad: str, asignado_a: Optional[str]) -> models.Incidencia:
    if accion.incidencia_id is not None:
        raise PreventivoError("Esta acción de preventivo ya tiene una incidencia")
    inc = models.Incidencia(
        codigo=inc_svc.generar_codigo(db, tipo),
        tipo=tipo,
        estado="abierta",
        equipo_id=accion.equipo_id,
        titulo=f"Correctivo desde preventivo del {accion.fecha.isoformat()}",
        descripcion_problema=accion.informe or "Generada desde acción de preventivo",
        prioridad=prioridad,
        asignado_a=asignado_a,
        fecha_apertura=date.today(),
    )
    db.add(inc)
    db.flush()
    accion.incidencia_id = inc.id
    db.flush()
    return inc
