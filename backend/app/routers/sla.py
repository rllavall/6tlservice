from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import sla_service
from app.db import get_db
from app.schemas import SlaOut

router = APIRouter(prefix="/api/sla", tags=["sla"])


@router.get("", response_model=SlaOut)
def cumplimiento(db: Session = Depends(get_db)) -> dict:
    return sla_service.construir_sla(db, date.today())
