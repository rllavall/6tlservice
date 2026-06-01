from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import UbicacionCreate, UbicacionOut

router = APIRouter(prefix="/api/ubicaciones", tags=["ubicaciones"])


@router.get("", response_model=list[UbicacionOut])
def listar(db: Session = Depends(get_db)) -> list[models.Ubicacion]:
    return db.query(models.Ubicacion).order_by(models.Ubicacion.nombre).all()


@router.get("/{ubicacion_id}", response_model=UbicacionOut)
def obtener(ubicacion_id: int, db: Session = Depends(get_db)) -> models.Ubicacion:
    u = db.get(models.Ubicacion, ubicacion_id)
    if u is None:
        raise HTTPException(404, "Ubicación no encontrada")
    return u


@router.post("", response_model=UbicacionOut, status_code=201)
def crear(payload: UbicacionCreate, db: Session = Depends(get_db)) -> models.Ubicacion:
    u = models.Ubicacion(**payload.model_dump())
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.put("/{ubicacion_id}", response_model=UbicacionOut)
def actualizar(ubicacion_id: int, payload: UbicacionCreate, db: Session = Depends(get_db)) -> models.Ubicacion:
    u = db.get(models.Ubicacion, ubicacion_id)
    if u is None:
        raise HTTPException(404, "Ubicación no encontrada")
    for k, v in payload.model_dump().items():
        setattr(u, k, v)
    db.commit()
    db.refresh(u)
    return u


@router.delete("/{ubicacion_id}", status_code=204)
def borrar(ubicacion_id: int, db: Session = Depends(get_db)) -> Response:
    u = db.get(models.Ubicacion, ubicacion_id)
    if u is None:
        raise HTTPException(404, "Ubicación no encontrada")
    en_uso = db.query(models.Movimiento).filter_by(ubicacion_destino_id=ubicacion_id).first()
    if en_uso is not None:
        raise HTTPException(409, "Ubicación en uso por movimientos; no se puede borrar")
    db.delete(u)
    db.commit()
    return Response(status_code=204)
