from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import garantia
from app import incidencias_service as svc
from app import notificaciones_service
from app import sla_service
from app import models
from app.db import get_db
from app.schemas import (
    AvanceOut,
    CambioConfiguracionOut,
    ClienteOut,
    ComponenteOut,
    EquipoOut,
    IncidenciaCreate,
    IncidenciaFicha,
    IncidenciaOut,
    IncidenciaUpdate,
    MovimientoOut,
    TransicionPayload,
)

router = APIRouter(prefix="/api/incidencias", tags=["incidencias"])


@router.get("", response_model=list[IncidenciaOut])
def listar(
    estado: Optional[str] = None,
    prioridad: Optional[str] = None,
    equipo_id: Optional[int] = None,
    componente_id: Optional[int] = None,
    asignado_a: Optional[str] = None,
    abiertas: Optional[bool] = None,
    tipo: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[models.Incidencia]:
    q = db.query(models.Incidencia)
    if estado is not None:
        q = q.filter(models.Incidencia.estado == estado)
    if prioridad is not None:
        q = q.filter(models.Incidencia.prioridad == prioridad)
    if equipo_id is not None:
        q = q.filter(models.Incidencia.equipo_id == equipo_id)
    if componente_id is not None:
        q = q.filter(models.Incidencia.componente_id == componente_id)
    if asignado_a is not None:
        q = q.filter(models.Incidencia.asignado_a == asignado_a)
    if abiertas:
        q = q.filter(models.Incidencia.estado != "cerrada")
    if tipo is not None:
        q = q.filter(models.Incidencia.tipo == tipo)
    return q.order_by(models.Incidencia.id.desc()).all()


@router.post("", response_model=IncidenciaOut, status_code=201)
def crear(payload: IncidenciaCreate, db: Session = Depends(get_db)) -> models.Incidencia:
    eq = None
    if payload.equipo_id is not None:
        eq = db.get(models.Equipo, payload.equipo_id)
        if eq is None:
            raise HTTPException(404, "Equipo no encontrado")
    if payload.componente_id is not None and db.get(models.Componente, payload.componente_id) is None:
        raise HTTPException(404, "Componente no encontrado")
    data = payload.model_dump()
    if data["tipo"] == "rma" and data.get("en_garantia") is None and eq is not None:
        data["en_garantia"] = garantia.equipo_en_garantia(eq, data["fecha_apertura"])
    inc = models.Incidencia(
        codigo=svc.generar_codigo(db, data["tipo"]),
        estado="abierta",
        **data,
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


@router.get("/{incidencia_id}", response_model=IncidenciaFicha)
def ficha(incidencia_id: int, db: Session = Depends(get_db)) -> IncidenciaFicha:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")

    eq = db.get(models.Equipo, inc.equipo_id) if inc.equipo_id is not None else None
    comp = db.get(models.Componente, inc.componente_id) if inc.componente_id is not None else None
    cli = None
    eq_para_cliente = eq
    if eq_para_cliente is None and comp is not None and comp.equipo_id is not None:
        eq_para_cliente = db.get(models.Equipo, comp.equipo_id)
    if eq_para_cliente is not None and eq_para_cliente.cliente_id is not None:
        cli = db.get(models.Cliente, eq_para_cliente.cliente_id)

    cambios = (
        db.query(models.CambioConfiguracion)
        .filter(models.CambioConfiguracion.incidencia_id == incidencia_id)
        .order_by(models.CambioConfiguracion.fecha.desc(), models.CambioConfiguracion.id.desc())
        .all()
    )
    movimientos = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.incidencia_id == incidencia_id)
        .order_by(models.Movimiento.fecha.desc(), models.Movimiento.id.desc())
        .all()
    )
    avances = (
        db.query(models.AvanceIncidencia)
        .filter(models.AvanceIncidencia.incidencia_id == incidencia_id)
        .order_by(models.AvanceIncidencia.fecha.desc(), models.AvanceIncidencia.id.desc())
        .all()
    )

    return IncidenciaFicha(
        incidencia=IncidenciaOut.model_validate(inc),
        equipo=EquipoOut.model_validate(eq) if eq is not None else None,
        componente=ComponenteOut.model_validate(comp) if comp is not None else None,
        cliente=ClienteOut.model_validate(cli) if cli is not None else None,
        cambios_configuracion=[CambioConfiguracionOut.model_validate(c) for c in cambios],
        movimientos=[MovimientoOut.model_validate(m) for m in movimientos],
        avances=[AvanceOut.model_validate(a) for a in avances],
        sla=sla_service.sla_de_incidencia(db, inc, date.today()),
    )


@router.patch("/{incidencia_id}", response_model=IncidenciaOut)
def actualizar(incidencia_id: int, payload: IncidenciaUpdate, db: Session = Depends(get_db)) -> models.Incidencia:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(inc, k, v)
    db.commit()
    db.refresh(inc)
    return inc


@router.post("/{incidencia_id}/transicion", response_model=IncidenciaOut)
def transicion(incidencia_id: int, payload: TransicionPayload, db: Session = Depends(get_db)) -> models.Incidencia:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    try:
        svc.transicionar(db, inc, payload.nuevo_estado, payload.fecha)
    except svc.IncidenciaError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(inc)
    try:
        notificaciones_service.notificar_incidencia(inc, payload.nuevo_estado)
    except Exception:
        pass
    return inc


@router.delete("/{incidencia_id}", status_code=204)
def borrar(incidencia_id: int, db: Session = Depends(get_db)) -> None:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    if inc.estado != "abierta":
        raise HTTPException(409, "Solo se pueden borrar incidencias en estado 'abierta'")
    enlazados = (
        db.query(models.CambioConfiguracion).filter(models.CambioConfiguracion.incidencia_id == incidencia_id).count()
        + db.query(models.Movimiento).filter(models.Movimiento.incidencia_id == incidencia_id).count()
    )
    if enlazados:
        raise HTTPException(409, "La incidencia tiene eventos de trazabilidad enlazados")
    db.delete(inc)
    db.commit()
