from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import sla_service
from app.db import get_db
from app.schemas import SlaOut

# La autenticación se aplica a nivel de include en main.py (como el resto de routers).
router = APIRouter(prefix="/api/sla", tags=["sla"])


@router.get("", response_model=SlaOut)
def cumplimiento(db: Session = Depends(get_db)) -> dict:
    return sla_service.construir_sla(db, datetime.now())
