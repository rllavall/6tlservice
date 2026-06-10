# app/routers/garantia_fabricante.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import fabricantes as fab
from app import fabricantes_email, garantia_fabricante_service as svc, models
from app.db import get_db
from app.schemas import GarantiaActivarPayload, GarantiaConfirmarPayload, GarantiaFabricanteOut

router = APIRouter(prefix="/api", tags=["garantia-fabricante"])


def _componente_o_404(db: Session, componente_id: int) -> models.Componente:
    c = db.get(models.Componente, componente_id)
    if c is None:
        raise HTTPException(404, "Componente no encontrado")
    return c


@router.post("/componentes/{componente_id}/garantia/activar",
             response_model=GarantiaFabricanteOut, status_code=201)
def activar(componente_id: int, payload: GarantiaActivarPayload,
            db: Session = Depends(get_db)) -> models.GarantiaFabricante:
    comp = _componente_o_404(db, componente_id)
    g = svc.activar(db, comp, meses_garantia=payload.meses_garantia,
                    responsable=payload.responsable)
    fabricante = db.get(models.Fabricante, g.fabricante_id) if g.fabricante_id else None
    if fabricante is not None and fab.destino_activacion(fabricante):
        fabricantes_email.enviar_activacion(comp, fabricante)
    db.commit()
    db.refresh(g)
    return g


@router.post("/componentes/{componente_id}/garantia/confirmar",
             response_model=GarantiaFabricanteOut)
def confirmar(componente_id: int, payload: GarantiaConfirmarPayload,
              db: Session = Depends(get_db)) -> models.GarantiaFabricante:
    _componente_o_404(db, componente_id)
    g = svc.obtener(db, componente_id)
    if g is None:
        raise HTTPException(404, "El componente no tiene garantía de fabricante iniciada")
    try:
        svc.confirmar(db, g, fecha_activacion=payload.fecha_activacion, referencia=payload.referencia)
    except svc.GarantiaError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(g)
    return g


@router.get("/componentes/{componente_id}/garantia", response_model=GarantiaFabricanteOut)
def detalle(componente_id: int, db: Session = Depends(get_db)) -> models.GarantiaFabricante:
    _componente_o_404(db, componente_id)
    g = svc.obtener(db, componente_id)
    if g is None:
        raise HTTPException(404, "El componente no tiene garantía de fabricante")
    return g


@router.get("/garantias/pendientes", response_model=list[GarantiaFabricanteOut])
def pendientes(db: Session = Depends(get_db)) -> list[models.GarantiaFabricante]:
    return (
        db.query(models.GarantiaFabricante)
        .filter(models.GarantiaFabricante.estado == "pendiente_activacion")
        .order_by(models.GarantiaFabricante.fecha_solicitud)
        .all()
    )
