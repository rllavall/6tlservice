from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import AuditoriaLogOut

router = APIRouter(prefix="/api/auditoria", tags=["auditoria"])


@router.get("", response_model=list[AuditoriaLogOut])
def listar(
    entidad: Optional[str] = None,
    entidad_id: Optional[int] = None,
    usuario_id: Optional[int] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[models.AuditoriaLog]:
    q = db.query(models.AuditoriaLog)
    if entidad is not None:
        q = q.filter(models.AuditoriaLog.entidad == entidad)
    if entidad_id is not None:
        q = q.filter(models.AuditoriaLog.entidad_id == entidad_id)
    if usuario_id is not None:
        q = q.filter(models.AuditoriaLog.usuario_id == usuario_id)
    if desde is not None:
        q = q.filter(models.AuditoriaLog.fecha_hora >= datetime.combine(desde, time.min))
    if hasta is not None:
        q = q.filter(models.AuditoriaLog.fecha_hora <= datetime.combine(hasta, time.max))
    return q.order_by(models.AuditoriaLog.id.desc()).limit(limit).all()
