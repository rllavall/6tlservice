from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, plantilla
from app.db import get_db
from app.schemas import (
    PlantillaComponenteCreate,
    PlantillaComponenteOut,
    PlantillaComponenteUpdate,
)

router = APIRouter(prefix="/api", tags=["plantillas"])


@router.get("/productos/{producto_equipo_id}/plantilla",
            response_model=list[PlantillaComponenteOut])
def listar(producto_equipo_id: int, db: Session = Depends(get_db)):
    return plantilla.listar(db, producto_equipo_id)


@router.post("/productos/{producto_equipo_id}/plantilla",
             response_model=PlantillaComponenteOut, status_code=201)
def crear(producto_equipo_id: int, payload: PlantillaComponenteCreate,
          db: Session = Depends(get_db)):
    try:
        linea = plantilla.crear(
            db, producto_equipo_id, payload.producto_componente_id,
            payload.posicion, payload.cantidad)
        db.commit()
    except plantilla.PlantillaError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Esa línea ya existe en la plantilla (producto+posición)")
    db.refresh(linea)
    return linea


@router.patch("/plantilla/{linea_id}", response_model=PlantillaComponenteOut)
def actualizar(linea_id: int, payload: PlantillaComponenteUpdate,
               db: Session = Depends(get_db)):
    campos = payload.model_dump(exclude_unset=True)
    try:
        linea = plantilla.actualizar(
            db, linea_id,
            posicion=campos["posicion"] if "posicion" in campos else ...,
            cantidad=campos["cantidad"] if "cantidad" in campos else ...,
        )
        db.commit()
    except plantilla.PlantillaError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)
    db.refresh(linea)
    return linea


@router.delete("/plantilla/{linea_id}", status_code=204)
def borrar(linea_id: int, db: Session = Depends(get_db)):
    try:
        plantilla.borrar(db, linea_id)
        db.commit()
    except plantilla.PlantillaError as e:
        db.rollback()
        raise HTTPException(e.status_code, e.message)
