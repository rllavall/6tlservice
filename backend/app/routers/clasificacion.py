from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.clasificacion_service import clasificar_lote

router = APIRouter(prefix="/api/clasificacion-trazabilidad", tags=["clasificacion"])


@router.post("/lote")
def lote(dry_run: bool = False, usar_llm: bool = True, limite: int | None = None,
         db: Session = Depends(get_db)) -> dict:
    r = clasificar_lote(db, usar_llm=usar_llm, limite=limite, dry_run=dry_run)
    return {
        "procesados": r.procesados, "por_reglas": r.por_reglas, "por_llm": r.por_llm,
        "omitidos_manual": r.omitidos_manual, "sin_cambios": r.sin_cambios,
        "cambios": r.cambios,
    }
