from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import ClienteCreate, ClienteOut

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


@router.get("", response_model=list[ClienteOut])
def listar(db: Session = Depends(get_db)) -> list[models.Cliente]:
    return db.query(models.Cliente).order_by(models.Cliente.nombre).all()


@router.get("/{cliente_id}", response_model=ClienteOut)
def obtener(cliente_id: int, db: Session = Depends(get_db)) -> models.Cliente:
    c = db.get(models.Cliente, cliente_id)
    if c is None:
        raise HTTPException(404, "Cliente no encontrado")
    return c


@router.post("", response_model=ClienteOut, status_code=201)
def crear(payload: ClienteCreate, db: Session = Depends(get_db)) -> models.Cliente:
    c = models.Cliente(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{cliente_id}", response_model=ClienteOut)
def actualizar(cliente_id: int, payload: ClienteCreate, db: Session = Depends(get_db)) -> models.Cliente:
    c = db.get(models.Cliente, cliente_id)
    if c is None:
        raise HTTPException(404, "Cliente no encontrado")
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{cliente_id}", status_code=204)
def borrar(cliente_id: int, db: Session = Depends(get_db)) -> Response:
    c = db.get(models.Cliente, cliente_id)
    if c is None:
        raise HTTPException(404, "Cliente no encontrado")
    en_uso_ubic = db.query(models.Ubicacion).filter_by(cliente_id=cliente_id).first()
    en_uso_eq = db.query(models.Equipo).filter_by(cliente_id=cliente_id).first()
    if en_uso_ubic is not None or en_uso_eq is not None:
        raise HTTPException(409, "Cliente en uso; no se puede borrar")
    db.delete(c)
    db.commit()
    return Response(status_code=204)
