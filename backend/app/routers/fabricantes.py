# app/routers/fabricantes.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import FabricanteCreate, FabricanteOut, FabricanteUpdate

router = APIRouter(prefix="/api/fabricantes", tags=["fabricantes"])


def _o_404(db: Session, fabricante_id: int) -> models.Fabricante:
    f = db.get(models.Fabricante, fabricante_id)
    if f is None:
        raise HTTPException(404, "Fabricante no encontrado")
    return f


@router.post("", response_model=FabricanteOut, status_code=201)
def crear(payload: FabricanteCreate, db: Session = Depends(get_db)) -> models.Fabricante:
    f = models.Fabricante(**payload.model_dump())
    db.add(f)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un fabricante con ese nombre")
    db.refresh(f)
    return f


@router.get("", response_model=list[FabricanteOut])
def listar(db: Session = Depends(get_db)) -> list[models.Fabricante]:
    return db.query(models.Fabricante).order_by(models.Fabricante.nombre).all()


@router.get("/{fabricante_id}", response_model=FabricanteOut)
def detalle(fabricante_id: int, db: Session = Depends(get_db)) -> models.Fabricante:
    return _o_404(db, fabricante_id)


@router.put("/{fabricante_id}", response_model=FabricanteOut)
def editar(fabricante_id: int, payload: FabricanteUpdate,
           db: Session = Depends(get_db)) -> models.Fabricante:
    f = _o_404(db, fabricante_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(f, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un fabricante con ese nombre")
    db.refresh(f)
    return f


@router.delete("/{fabricante_id}", status_code=204)
def borrar(fabricante_id: int, db: Session = Depends(get_db)) -> None:
    f = _o_404(db, fabricante_id)
    db.delete(f)
    db.commit()
