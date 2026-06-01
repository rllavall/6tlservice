from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import ComponenteCreate, ComponenteOut

router = APIRouter(prefix="/api/componentes", tags=["componentes"])


@router.get("", response_model=list[ComponenteOut])
def listar(
    equipo_id: Optional[int] = None,
    producto_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> list[models.Componente]:
    q = db.query(models.Componente)
    if equipo_id is not None:
        q = q.filter(models.Componente.equipo_id == equipo_id)
    if producto_id is not None:
        q = q.filter(models.Componente.producto_id == producto_id)
    return q.order_by(models.Componente.numero_serie).all()


@router.get("/{componente_id}", response_model=ComponenteOut)
def obtener(componente_id: int, db: Session = Depends(get_db)) -> models.Componente:
    c = db.get(models.Componente, componente_id)
    if c is None:
        raise HTTPException(404, "Componente no encontrado")
    return c


@router.post("", response_model=ComponenteOut, status_code=201)
def crear(payload: ComponenteCreate, db: Session = Depends(get_db)) -> models.Componente:
    prod = db.get(models.Producto, payload.producto_id)
    if prod is None:
        raise HTTPException(404, "Producto no encontrado")
    if prod.tipo != "componente":
        raise HTTPException(409, "El producto referenciado no es de tipo 'componente'")
    if payload.equipo_id is not None and db.get(models.Equipo, payload.equipo_id) is None:
        raise HTTPException(404, "Equipo no encontrado")
    c = models.Componente(**payload.model_dump())
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un componente con ese (producto, numero_serie)")
    db.refresh(c)
    return c


@router.put("/{componente_id}", response_model=ComponenteOut)
def actualizar(componente_id: int, payload: ComponenteCreate, db: Session = Depends(get_db)) -> models.Componente:
    c = db.get(models.Componente, componente_id)
    if c is None:
        raise HTTPException(404, "Componente no encontrado")
    # numero_serie/producto editable here; montaje state is managed via Task 8 endpoints.
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un componente con ese (producto, numero_serie)")
    db.refresh(c)
    return c
