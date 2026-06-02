from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, trazabilidad
from app.db import get_db
from app.schemas import CambioConfiguracionOut, DesmontarPayload, MontarPayload

router = APIRouter(prefix="/api/componentes", tags=["configuracion"])


@router.post("/{componente_id}/montar", response_model=CambioConfiguracionOut, status_code=201)
def montar(componente_id: int, payload: MontarPayload, db: Session = Depends(get_db)) -> models.CambioConfiguracion:
    try:
        evento = trazabilidad.montar_componente(
            db, componente_id, payload.equipo_id, payload.posicion, payload.fecha, payload.motivo, payload.usuario, payload.notas,
            payload.incidencia_id,
        )
    except LookupError as e:
        db.rollback()
        raise HTTPException(404, str(e))
    except trazabilidad.ConfiguracionError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(evento)
    return evento


@router.post("/{componente_id}/desmontar", response_model=CambioConfiguracionOut, status_code=201)
def desmontar(componente_id: int, payload: DesmontarPayload, db: Session = Depends(get_db)) -> models.CambioConfiguracion:
    try:
        evento = trazabilidad.desmontar_componente(
            db, componente_id, payload.fecha, payload.motivo, payload.usuario, payload.notas,
            payload.incidencia_id,
        )
    except LookupError as e:
        db.rollback()
        raise HTTPException(404, str(e))
    except trazabilidad.ConfiguracionError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(evento)
    return evento
