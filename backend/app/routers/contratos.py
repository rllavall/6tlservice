from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import contratos_service as svc
from app import models
from app.db import get_db
from app.schemas import (
    AsignarEquipoPayload, ContratoCreate, ContratoDetalle, ContratoOut, ContratoUpdate,
)

router = APIRouter(prefix="/api/contratos", tags=["contratos"])


@router.post("", response_model=ContratoOut, status_code=201)
def crear(payload: ContratoCreate, db: Session = Depends(get_db)) -> models.ContratoMantenimiento:
    con = models.ContratoMantenimiento(codigo=svc.generar_codigo(db), **payload.model_dump())
    db.add(con)
    db.commit()
    db.refresh(con)
    return con


@router.get("", response_model=list[ContratoOut])
def listar(estado: Optional[str] = None, cliente_id: Optional[int] = None,
           db: Session = Depends(get_db)) -> list[models.ContratoMantenimiento]:
    q = db.query(models.ContratoMantenimiento)
    if cliente_id is not None:
        q = q.filter(models.ContratoMantenimiento.cliente_id == cliente_id)
    items = q.order_by(models.ContratoMantenimiento.id.desc()).all()
    if estado is not None:
        items = [c for c in items if c.estado == estado]
    return items


@router.get("/{contrato_id}", response_model=ContratoDetalle)
def detalle(contrato_id: int, db: Session = Depends(get_db)) -> ContratoDetalle:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    cliente = db.get(models.Cliente, con.cliente_id) if con.cliente_id else None
    return ContratoDetalle(contrato=con, cliente=cliente, equipos=con.equipos)


@router.put("/{contrato_id}", response_model=ContratoOut)
def editar(contrato_id: int, payload: ContratoUpdate,
           db: Session = Depends(get_db)) -> models.ContratoMantenimiento:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(con, k, v)
    db.commit()
    db.refresh(con)
    return con


@router.delete("/{contrato_id}", status_code=204)
def borrar(contrato_id: int, db: Session = Depends(get_db)) -> None:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    _AP = getattr(models, "AccionPreventiva", None)
    tiene_acciones = False
    if _AP is not None:
        tiene_acciones = db.query(_AP).filter(_AP.contrato_id == contrato_id).first() is not None
    if con.equipos or tiene_acciones:
        raise HTTPException(409, "El contrato tiene equipos o acciones; cancélalo en su lugar (cancelado=true)")
    db.delete(con)
    db.commit()


@router.post("/{contrato_id}/equipos", response_model=ContratoOut)
def asignar_equipo(contrato_id: int, payload: AsignarEquipoPayload,
                   db: Session = Depends(get_db)) -> models.ContratoMantenimiento:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    eq = db.get(models.Equipo, payload.equipo_id)
    if eq is None:
        raise HTTPException(404, "Equipo no encontrado")
    try:
        svc.vincular_equipo(db, con, eq)
    except svc.ContratoError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(con)
    return con


@router.delete("/{contrato_id}/equipos/{equipo_id}", response_model=ContratoOut)
def desasignar_equipo(contrato_id: int, equipo_id: int,
                      db: Session = Depends(get_db)) -> models.ContratoMantenimiento:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    eq = db.get(models.Equipo, equipo_id)
    if eq is None or eq.contrato_id != contrato_id:
        raise HTTPException(404, "Equipo no vinculado a este contrato")
    svc.desvincular_equipo(db, eq)
    db.commit()
    db.refresh(con)
    return con
