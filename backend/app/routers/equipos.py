from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, trazabilidad
from app.db import get_db
from app.schemas import CambioConfiguracionOut, ClienteOut, ComponenteOut, EquipoCreate, EquipoFicha, EquipoOut, EquipoUpdate, MovimientoOut, ProductoOut, SustituirPayload, SustitucionOut, UbicacionOut

router = APIRouter(prefix="/api/equipos", tags=["equipos"])


@router.get("", response_model=list[EquipoOut])
def listar(
    producto_id: Optional[int] = None,
    estado: Optional[str] = None,
    part_number: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[models.Equipo]:
    q = db.query(models.Equipo)
    if producto_id is not None:
        q = q.filter(models.Equipo.producto_id == producto_id)
    if estado is not None:
        q = q.filter(models.Equipo.estado == estado)
    if part_number is not None:
        q = (
            q.join(models.Componente, models.Componente.equipo_id == models.Equipo.id)
            .join(models.Producto, models.Producto.id == models.Componente.producto_id)
            .filter(models.Producto.part_number == part_number)
            .distinct()
        )
    return q.order_by(models.Equipo.numero_serie).all()


@router.post("", response_model=EquipoOut, status_code=201)
def crear(payload: EquipoCreate, db: Session = Depends(get_db)) -> models.Equipo:
    prod = db.get(models.Producto, payload.producto_id)
    if prod is None:
        raise HTTPException(404, "Producto no encontrado")
    if prod.tipo != "equipo":
        raise HTTPException(409, "El producto referenciado no es de tipo 'equipo'")
    if payload.cliente_id is not None:
        if db.get(models.Cliente, payload.cliente_id) is None:
            raise HTTPException(404, "Cliente no encontrado")
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
    if payload.cliente_id is not None:
        if db.get(models.Cliente, payload.cliente_id) is None:
            raise HTTPException(404, "Cliente no encontrado")
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

    ubic = trazabilidad.ubicacion_actual(db, equipo_id)

    componentes = (
        db.query(models.Componente)
        .filter(models.Componente.equipo_id == equipo_id)
        .order_by(models.Componente.posicion)
        .all()
    )
    movimientos = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.equipo_id == equipo_id)
        .order_by(models.Movimiento.fecha.desc(), models.Movimiento.id.desc())
        .all()
    )
    cambios = (
        db.query(models.CambioConfiguracion)
        .filter(models.CambioConfiguracion.equipo_id == equipo_id)
        .order_by(models.CambioConfiguracion.fecha.desc(), models.CambioConfiguracion.id.desc())
        .all()
    )

    cli = db.get(models.Cliente, eq.cliente_id) if eq.cliente_id is not None else None

    return EquipoFicha(
        equipo=EquipoOut.model_validate(eq),
        producto=ProductoOut.model_validate(prod),
        cliente=ClienteOut.model_validate(cli) if cli is not None else None,
        ubicacion_actual=UbicacionOut.model_validate(ubic) if ubic is not None else None,
        componentes=[ComponenteOut.model_validate(c) for c in componentes],
        historial_movimientos=[MovimientoOut.model_validate(m) for m in movimientos],
        historial_configuracion=[CambioConfiguracionOut.model_validate(c) for c in cambios],
    )


@router.post("/{equipo_id}/sustituir-componente", response_model=SustitucionOut)
def sustituir_componente(equipo_id: int, payload: SustituirPayload, db: Session = Depends(get_db)) -> SustitucionOut:
    try:
        res = trazabilidad.sustituir_componente(
            db, equipo_id, payload.componente_saliente_id, payload.componente_entrante_id,
            payload.posicion, payload.fecha, payload.motivo, payload.usuario, payload.notas,
            payload.incidencia_id,
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
