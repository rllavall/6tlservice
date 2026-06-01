from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import incidencias_service as svc
from app import models
from app.db import get_db
from app.schemas import IncidenciaCreate, IncidenciaOut

router = APIRouter(prefix="/api/incidencias", tags=["incidencias"])


@router.get("", response_model=list[IncidenciaOut])
def listar(
    estado: Optional[str] = None,
    prioridad: Optional[str] = None,
    equipo_id: Optional[int] = None,
    componente_id: Optional[int] = None,
    asignado_a: Optional[str] = None,
    abiertas: Optional[bool] = None,
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
    return q.order_by(models.Incidencia.id.desc()).all()


@router.post("", response_model=IncidenciaOut, status_code=201)
def crear(payload: IncidenciaCreate, db: Session = Depends(get_db)) -> models.Incidencia:
    if payload.equipo_id is not None and db.get(models.Equipo, payload.equipo_id) is None:
        raise HTTPException(404, "Equipo no encontrado")
    if payload.componente_id is not None and db.get(models.Componente, payload.componente_id) is None:
        raise HTTPException(404, "Componente no encontrado")
    inc = models.Incidencia(
        codigo=svc.generar_codigo(db),
        estado="abierta",
        **payload.model_dump(),
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc
