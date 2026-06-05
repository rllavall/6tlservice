from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import email_notify, models
from app import solicitudes_service as svc
from app.db import get_db
from app.schemas import SolicitudCreate, SolicitudOut

router = APIRouter(prefix="/api/solicitudes", tags=["solicitudes"])


@router.post("", response_model=SolicitudOut, status_code=201)
def crear(payload: SolicitudCreate, db: Session = Depends(get_db)) -> models.SolicitudSoporte:
    if payload.website:  # honeypot relleno -> bot
        raise HTTPException(400, "Solicitud rechazada")
    data = payload.model_dump(exclude={"website"})
    sol = models.SolicitudSoporte(
        codigo=svc.generar_codigo(db),
        estado="pendiente",
        fecha_solicitud=date.today(),
        **data,
    )
    db.add(sol)
    db.commit()
    db.refresh(sol)
    try:
        email_notify.enviar_aviso_solicitud(sol)
    except Exception:  # best-effort: el aviso nunca rompe el alta
        pass
    return sol


@router.get("", response_model=list[SolicitudOut])
def listar(estado: Optional[str] = None, db: Session = Depends(get_db)) -> list[models.SolicitudSoporte]:
    q = db.query(models.SolicitudSoporte)
    if estado is not None:
        q = q.filter(models.SolicitudSoporte.estado == estado)
    return q.order_by(models.SolicitudSoporte.id.desc()).all()


@router.get("/{solicitud_id}", response_model=SolicitudOut)
def obtener(solicitud_id: int, db: Session = Depends(get_db)) -> models.SolicitudSoporte:
    sol = db.get(models.SolicitudSoporte, solicitud_id)
    if sol is None:
        raise HTTPException(404, "Solicitud no encontrada")
    return sol
