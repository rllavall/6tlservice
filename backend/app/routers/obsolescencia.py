from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, obsolescencia_service
from app.db import get_db
from app.schemas import (HallazgoObsolescencia, ObsolescenciaResumenOut,
                         ProductoARevisarOut)

router = APIRouter(prefix="/api/obsolescencia", tags=["obsolescencia"])


@router.get("", response_model=ObsolescenciaResumenOut)
def resumen(db: Session = Depends(get_db)):
    return obsolescencia_service.resumen_obsolescencia(db)


@router.get("/productos-a-revisar", response_model=list[ProductoARevisarOut])
def productos_a_revisar(dias: int = 7, limite: Optional[int] = None,
                        db: Session = Depends(get_db)):
    prods = obsolescencia_service.productos_a_revisar(db, date.today(), dias=dias, limite=limite)
    salida = []
    for p in prods:
        url = None
        if p.fabricante_id is not None:
            f = db.get(models.Fabricante, p.fabricante_id)
            url = f.url_obsolescencia if f else None
        salida.append(ProductoARevisarOut(
            id=p.id, fabricante=p.fabricante, pn_fabricante=p.pn_fabricante,
            descripcion=p.descripcion, estado_ciclo_vida=p.estado_ciclo_vida,
            url_obsolescencia=url))
    return salida


@router.post("/hallazgos")
def registrar_hallazgos(payload: list[HallazgoObsolescencia],
                        db: Session = Depends(get_db)):
    hoy = date.today()
    detalle = [
        obsolescencia_service.registrar_hallazgo(
            db, h.producto_id, h.estado, hoy=hoy, fecha_evento=h.fecha_evento,
            url=h.url, resumen=h.resumen)
        for h in payload
    ]
    return {"procesados": len(detalle),
            "cambios": sum(1 for d in detalle if d["cambio"]),
            "detalle": detalle}
