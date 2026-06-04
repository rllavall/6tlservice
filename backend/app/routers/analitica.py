from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import analitica_incidencias as ana
from app.db import get_db
from app.schemas import AnaliticaIncidenciasOut

router = APIRouter(prefix="/api/analitica", tags=["analitica"])


@router.get("/incidencias", response_model=AnaliticaIncidenciasOut)
def incidencias(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    tipo: Optional[str] = None,
    cliente_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> AnaliticaIncidenciasOut:
    return ana.calcular(db, hoy=date.today(), desde=desde, hasta=hasta, tipo=tipo, cliente_id=cliente_id)
