from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import ComponenteOut, EquipoOut, ResultadoBusqueda

router = APIRouter(prefix="/api/buscar", tags=["busqueda"])


@router.get("", response_model=ResultadoBusqueda)
def buscar(serie: str, db: Session = Depends(get_db)) -> ResultadoBusqueda:
    eq = db.query(models.Equipo).filter(models.Equipo.numero_serie == serie).first()
    if eq is not None:
        return ResultadoBusqueda(tipo="equipo", equipo=EquipoOut.model_validate(eq))
    comp = db.query(models.Componente).filter(models.Componente.numero_serie == serie).first()
    if comp is not None:
        equipo = db.get(models.Equipo, comp.equipo_id) if comp.equipo_id is not None else None
        return ResultadoBusqueda(
            tipo="componente",
            componente=ComponenteOut.model_validate(comp),
            equipo_del_componente=EquipoOut.model_validate(equipo) if equipo is not None else None,
        )
    return ResultadoBusqueda(tipo="ninguno")
