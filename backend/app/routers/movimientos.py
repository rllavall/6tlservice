from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, trazabilidad
from app.db import get_db
from app.schemas import MovimientoCreate, MovimientoOut

router = APIRouter(prefix="/api/equipos", tags=["movimientos"])


@router.post("/{equipo_id}/movimientos", response_model=MovimientoOut, status_code=201)
def crear_movimiento(equipo_id: int, payload: MovimientoCreate, db: Session = Depends(get_db)) -> models.Movimiento:
    if db.get(models.Equipo, equipo_id) is None:
        raise HTTPException(404, "Equipo no encontrado")
    if db.get(models.Ubicacion, payload.ubicacion_destino_id) is None:
        raise HTTPException(404, "Ubicación destino no encontrada")
    mov = trazabilidad.registrar_movimiento(
        db, equipo_id, payload.ubicacion_destino_id, payload.fecha, payload.motivo, payload.usuario, payload.notas
    )
    db.commit()
    db.refresh(mov)
    return mov
