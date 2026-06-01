from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, trazabilidad
from app.db import get_db
from app.schemas import EquipoCreate, EquipoFicha, EquipoOut, EquipoUpdate, ProductoOut, SustituirPayload, SustitucionOut

router = APIRouter(prefix="/api/equipos", tags=["equipos"])


@router.get("", response_model=list[EquipoOut])
def listar(
    producto_id: Optional[int] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[models.Equipo]:
    q = db.query(models.Equipo)
    if producto_id is not None:
        q = q.filter(models.Equipo.producto_id == producto_id)
    if estado is not None:
        q = q.filter(models.Equipo.estado == estado)
    return q.order_by(models.Equipo.numero_serie).all()


@router.post("", response_model=EquipoOut, status_code=201)
def crear(payload: EquipoCreate, db: Session = Depends(get_db)) -> models.Equipo:
    prod = db.get(models.Producto, payload.producto_id)
    if prod is None:
        raise HTTPException(404, "Producto no encontrado")
    if prod.tipo != "equipo":
        raise HTTPException(409, "El producto referenciado no es de tipo 'equipo'")
    eq = models.Equipo(**payload.model_dump())
    db.add(eq)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un equipo con ese (producto, numero_serie)")
    db.refresh(eq)
    return eq


@router.put("/{equipo_id}", response_model=EquipoOut)
def actualizar(equipo_id: int, payload: EquipoUpdate, db: Session = Depends(get_db)) -> models.Equipo:
    eq = db.get(models.Equipo, equipo_id)
    if eq is None:
        raise HTTPException(404, "Equipo no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(eq, k, v)
    db.commit()
    db.refresh(eq)
    return eq


@router.get("/{equipo_id}", response_model=EquipoFicha)
def ficha(equipo_id: int, db: Session = Depends(get_db)) -> EquipoFicha:
    eq = db.get(models.Equipo, equipo_id)
    if eq is None:
        raise HTTPException(404, "Equipo no encontrado")
    prod = db.get(models.Producto, eq.producto_id)
    # Minimal ficha — enriched in Task 10.
    return EquipoFicha(
        equipo=EquipoOut.model_validate(eq),
        producto=ProductoOut.model_validate(prod),
        ubicacion_actual=None,
        componentes=[],
        historial_movimientos=[],
        historial_configuracion=[],
    )


@router.post("/{equipo_id}/sustituir-componente", response_model=SustitucionOut)
def sustituir_componente(equipo_id: int, payload: SustituirPayload, db: Session = Depends(get_db)) -> SustitucionOut:
    try:
        res = trazabilidad.sustituir_componente(
            db, equipo_id, payload.componente_saliente_id, payload.componente_entrante_id,
            payload.posicion, payload.fecha, payload.motivo, payload.usuario, payload.notas,
        )
    except LookupError as e:
        db.rollback()
        raise HTTPException(404, str(e))
    except trazabilidad.ConfiguracionError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    return SustitucionOut(
        desmontaje=res["desmontaje"],
        montaje=res["montaje"],
    )
