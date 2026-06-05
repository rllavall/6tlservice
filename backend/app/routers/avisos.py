from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import avisos_service
from app.db import get_db
from app.schemas import AvisosOut

router = APIRouter(prefix="/api/avisos", tags=["avisos"])


@router.get("", response_model=AvisosOut)
def listar(db: Session = Depends(get_db)) -> dict:
    return avisos_service.construir_avisos(db, date.today())
