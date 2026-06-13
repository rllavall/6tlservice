from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, obsolescencia_service
from app.db import get_db
from app.schemas import CicloVidaManualIn, ProductoCreate, ProductoOut

router = APIRouter(prefix="/api/productos", tags=["productos"])


@router.get("", response_model=list[ProductoOut])
def listar(
    tipo: Optional[str] = None,
    categoria_componente: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[models.Producto]:
    q = db.query(models.Producto)
    if tipo is not None:
        q = q.filter(models.Producto.tipo == tipo)
    if categoria_componente is not None:
        q = q.filter(models.Producto.categoria_componente == categoria_componente)
    return q.order_by(models.Producto.part_number).all()


@router.get("/{producto_id}", response_model=ProductoOut)
def obtener(producto_id: int, db: Session = Depends(get_db)) -> models.Producto:
    p = db.get(models.Producto, producto_id)
    if p is None:
        raise HTTPException(404, "Producto no encontrado")
    return p


@router.patch("/{producto_id}/ciclo-vida", response_model=ProductoOut)
def fijar_ciclo_vida_manual(producto_id: int, payload: CicloVidaManualIn,
                            db: Session = Depends(get_db)) -> models.Producto:
    p = db.get(models.Producto, producto_id)
    if p is None:
        raise HTTPException(404, "Producto no encontrado")
    obsolescencia_service.registrar_manual(
        db, producto_id, payload.estado, hoy=date.today(),
        fecha_evento=payload.fecha_evento, url=payload.url, nota=payload.nota)
    db.refresh(p)
    return p


@router.post("", response_model=ProductoOut, status_code=201)
def crear(payload: ProductoCreate, db: Session = Depends(get_db)) -> models.Producto:
    p = models.Producto(**payload.model_dump())
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "part_number ya existe")
    db.refresh(p)
    return p


@router.put("/{producto_id}", response_model=ProductoOut)
def actualizar(producto_id: int, payload: ProductoCreate, db: Session = Depends(get_db)) -> models.Producto:
    p = db.get(models.Producto, producto_id)
    if p is None:
        raise HTTPException(404, "Producto no encontrado")
    for k, v in payload.model_dump().items():
        setattr(p, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "part_number ya existe")
    db.refresh(p)
    return p


@router.delete("/{producto_id}", status_code=204)
def borrar(producto_id: int, db: Session = Depends(get_db)) -> Response:
    p = db.get(models.Producto, producto_id)
    if p is None:
        raise HTTPException(404, "Producto no encontrado")
    usado_eq = db.query(models.Equipo).filter_by(producto_id=producto_id).first()
    usado_comp = db.query(models.Componente).filter_by(producto_id=producto_id).first()
    if usado_eq is not None or usado_comp is not None:
        raise HTTPException(409, "Producto en uso; no se puede borrar")
    db.delete(p)
    db.commit()
    return Response(status_code=204)
