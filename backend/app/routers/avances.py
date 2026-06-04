from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import AvanceCreate, AvanceOut, AvanceUpdate

router = APIRouter(prefix="/api/incidencias", tags=["avances"])


def _incidencia_o_404(db: Session, incidencia_id: int) -> models.Incidencia:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    return inc


def _avance_o_404(db: Session, incidencia_id: int, avance_id: int) -> models.AvanceIncidencia:
    av = db.get(models.AvanceIncidencia, avance_id)
    if av is None or av.incidencia_id != incidencia_id:
        raise HTTPException(404, "Avance no encontrado")
    return av


@router.get("/{incidencia_id}/avances", response_model=list[AvanceOut])
def listar(incidencia_id: int, db: Session = Depends(get_db)) -> list[models.AvanceIncidencia]:
    _incidencia_o_404(db, incidencia_id)
    return (
        db.query(models.AvanceIncidencia)
        .filter(models.AvanceIncidencia.incidencia_id == incidencia_id)
        .order_by(models.AvanceIncidencia.fecha.desc(), models.AvanceIncidencia.id.desc())
        .all()
    )


@router.post("/{incidencia_id}/avances", response_model=AvanceOut, status_code=201)
def crear(incidencia_id: int, payload: AvanceCreate, db: Session = Depends(get_db)) -> models.AvanceIncidencia:
    _incidencia_o_404(db, incidencia_id)
    data = payload.model_dump()
    if data.get("fecha") is None:
        data["fecha"] = date.today()
    av = models.AvanceIncidencia(incidencia_id=incidencia_id, **data)
    db.add(av)
    db.commit()
    db.refresh(av)
    return av


@router.patch("/{incidencia_id}/avances/{avance_id}", response_model=AvanceOut)
def actualizar(incidencia_id: int, avance_id: int, payload: AvanceUpdate, db: Session = Depends(get_db)) -> models.AvanceIncidencia:
    av = _avance_o_404(db, incidencia_id, avance_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(av, k, v)
    db.commit()
    db.refresh(av)
    return av


@router.delete("/{incidencia_id}/avances/{avance_id}", status_code=204)
def borrar(incidencia_id: int, avance_id: int, db: Session = Depends(get_db)) -> Response:
    av = _avance_o_404(db, incidencia_id, avance_id)
    db.delete(av)
    db.commit()
    return Response(status_code=204)
