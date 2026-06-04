from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, trazabilidad
from app.db import get_db
from app.schemas import MapaUbicacionOut

router = APIRouter(prefix="/api/mapa", tags=["mapa"])


@router.get("/ubicaciones", response_model=list[MapaUbicacionOut])
def ubicaciones_en_mapa(
    incluir_baja: bool = False,
    cliente_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Ubicaciones con coordenadas y ≥1 equipo, para el mapa de base instalada."""
    out: list[dict] = []
    for u, equipos in trazabilidad.equipos_por_ubicacion(db, incluir_baja=incluir_baja):
        if u.latitud is None or u.longitud is None:
            continue
        if cliente_id is not None and u.cliente_id != cliente_id:
            continue
        cliente = db.get(models.Cliente, u.cliente_id) if u.cliente_id else None
        out.append(
            {
                "ubicacion_id": u.id,
                "nombre": u.nombre,
                "tipo": u.tipo,
                "ciudad": u.ciudad,
                "provincia": u.provincia,
                "pais": u.pais,
                "latitud": u.latitud,
                "longitud": u.longitud,
                "cliente": {"id": cliente.id, "nombre": cliente.nombre} if cliente else None,
                "num_equipos": len(equipos),
                "equipos": [
                    {
                        "id": e.id,
                        "numero_serie": e.numero_serie,
                        "producto": f"{e.producto.part_number} — {e.producto.descripcion}",
                        "estado": e.estado,
                    }
                    for e in equipos
                ],
            }
        )
    out.sort(key=lambda i: i["ubicacion_id"])
    return out
