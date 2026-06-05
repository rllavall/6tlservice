from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import notificaciones_service
from app.db import get_db
from app.schemas import DigestOut

router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])


@router.post("/digest", response_model=DigestOut)
def digest(dry_run: bool = False, db: Session = Depends(get_db)) -> dict:
    hoy = date.today()
    if dry_run:
        d = notificaciones_service.construir_digest(db, hoy)
        return {**d, "enviado": False, "canales": None}
    r = notificaciones_service.enviar_digest(db, hoy)
    return {**r, "enviado": True}
