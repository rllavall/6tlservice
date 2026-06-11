# app/routers/derivaciones.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import derivaciones_service as svc
from app import fabricantes as fab
from app import fabricantes_email, models
from app.db import get_db
from app.schemas import DerivacionCreate, DerivacionOut, DerivacionUpdate

router = APIRouter(prefix="/api", tags=["derivaciones"])


def _incidencia_o_404(db: Session, incidencia_id: int) -> models.Incidencia:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    return inc


@router.get("/incidencias/{incidencia_id}/derivaciones", response_model=list[DerivacionOut])
def listar(incidencia_id: int, db: Session = Depends(get_db)) -> list[models.Derivacion]:
    _incidencia_o_404(db, incidencia_id)
    return (
        db.query(models.Derivacion)
        .filter(models.Derivacion.incidencia_id == incidencia_id)
        .order_by(models.Derivacion.id.desc())
        .all()
    )


@router.post("/incidencias/{incidencia_id}/derivaciones",
             response_model=DerivacionOut, status_code=201)
def crear(incidencia_id: int, payload: DerivacionCreate,
          db: Session = Depends(get_db)) -> models.Derivacion:
    inc = _incidencia_o_404(db, incidencia_id)
    # `tu_referencia` (RMA-NNNN) se calcula con max+1 y la constraint UNIQUE es el
    # árbitro: si dos altas concurrentes colisionan, el commit perdedor lanza
    # IntegrityError. Reintentamos un par de veces con una referencia fresca antes
    # de rendirnos con un 409 (en vez de propagar un 500).
    d = None
    for _ in range(3):
        try:
            d = svc.crear(db, inc, tipo=payload.tipo, fabricante_id=payload.fabricante_id,
                          departamento=payload.departamento)
            if payload.notas is not None:
                d.notas = payload.notas
            db.commit()
            break
        except svc.DerivacionError as e:
            db.rollback()
            raise HTTPException(409, str(e))
        except IntegrityError:
            # Colisión de tu_referencia (flush o commit): reintenta con otra.
            db.rollback()
            d = None
    if d is None:
        raise HTTPException(409, "No se pudo asignar una referencia RMA única; reinténtalo")
    db.refresh(d)
    # Email best-effort tras persistir (evita doble envío si hubo reintento).
    if d.tipo == "externa_fabricante" and d.fabricante_id is not None:
        fabricante = db.get(models.Fabricante, d.fabricante_id)
        if fabricante is not None and fab.destino_rma(fabricante):
            fabricantes_email.enviar_rma(d, fabricante)
    return d


@router.patch("/derivaciones/{derivacion_id}", response_model=DerivacionOut)
def actualizar(derivacion_id: int, payload: DerivacionUpdate,
               db: Session = Depends(get_db)) -> models.Derivacion:
    d = db.get(models.Derivacion, derivacion_id)
    if d is None:
        raise HTTPException(404, "Derivación no encontrada")
    if payload.notas is not None:
        d.notas = payload.notas
    if payload.estado is not None:
        try:
            svc.avanzar(db, d, payload.estado, referencia_externa=payload.referencia_externa)
        except svc.DerivacionError as e:
            db.rollback()
            raise HTTPException(409, str(e))
    elif payload.referencia_externa is not None:
        d.referencia_externa = payload.referencia_externa
    db.commit()
    db.refresh(d)
    return d
