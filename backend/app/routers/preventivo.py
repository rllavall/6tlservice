from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app import preventivo_service as svc
from app.db import get_db
from app.schemas import AccionPreventivaCreate, AccionPreventivaOut, GenerarIncidenciaPrevPayload, IncidenciaOut

router = APIRouter(prefix="/api", tags=["preventivo"])


@router.get("/equipos/{equipo_id}/preventivos", response_model=list[AccionPreventivaOut])
def listar(equipo_id: int, db: Session = Depends(get_db)) -> list[models.AccionPreventiva]:
    if db.get(models.Equipo, equipo_id) is None:
        raise HTTPException(404, "Equipo no encontrado")
    return (db.query(models.AccionPreventiva)
            .filter(models.AccionPreventiva.equipo_id == equipo_id)
            .order_by(models.AccionPreventiva.fecha.desc(), models.AccionPreventiva.id.desc())
            .all())


@router.post("/equipos/{equipo_id}/preventivos", response_model=AccionPreventivaOut, status_code=201)
def crear(equipo_id: int, payload: AccionPreventivaCreate,
          db: Session = Depends(get_db)) -> models.AccionPreventiva:
    eq = db.get(models.Equipo, equipo_id)
    if eq is None:
        raise HTTPException(404, "Equipo no encontrado")
    accion = svc.crear(
        db, eq, fecha=payload.fecha, tipo=payload.tipo, veredicto=payload.veredicto,
        tecnico=payload.tecnico, informe=payload.informe, proxima_fecha=payload.proxima_fecha,
    )
    db.commit()
    db.refresh(accion)
    return accion


@router.post("/preventivos/{accion_id}/generar-incidencia", response_model=IncidenciaOut, status_code=201)
def generar_incidencia(accion_id: int, payload: GenerarIncidenciaPrevPayload,
                       db: Session = Depends(get_db)) -> models.Incidencia:
    accion = db.get(models.AccionPreventiva, accion_id)
    if accion is None:
        raise HTTPException(404, "Acción de preventivo no encontrada")
    try:
        inc = svc.generar_incidencia(db, accion, tipo=payload.tipo, prioridad=payload.prioridad,
                                     asignado_a=payload.asignado_a)
    except svc.PreventivoError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(inc)
    return inc
