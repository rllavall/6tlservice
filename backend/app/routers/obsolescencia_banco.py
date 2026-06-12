from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models, obsolescencia_banco, obsolescencia_export
from app.db import get_db
from app.deps import get_consultar_fabricante
from app.schemas import ObsolescenciaBancoOut

router = APIRouter(prefix="/api/equipos", tags=["obsolescencia"])

_MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _equipo_o_404(db: Session, equipo_id: int) -> models.Equipo:
    eq = db.get(models.Equipo, equipo_id)
    if eq is None:
        raise HTTPException(status_code=404, detail="equipo no encontrado")
    return eq


@router.get("/{equipo_id}/obsolescencia", response_model=ObsolescenciaBancoOut)
def report(equipo_id: int, db: Session = Depends(get_db)):
    _equipo_o_404(db, equipo_id)
    return obsolescencia_banco.informe_banco(db, equipo_id, date.today())


@router.get("/{equipo_id}/obsolescencia/export")
def exportar(equipo_id: int, formato: str = "xlsx", db: Session = Depends(get_db)):
    _equipo_o_404(db, equipo_id)
    if formato not in _MEDIA:
        raise HTTPException(status_code=422, detail="formato debe ser 'xlsx' o 'pdf'")
    informe = obsolescencia_banco.informe_banco(db, equipo_id, date.today())
    datos = (obsolescencia_export.a_xlsx(informe) if formato == "xlsx"
             else obsolescencia_export.a_pdf(informe))
    nombre = f"obsolescencia_{informe['banco']['numero_serie']}_{date.today().isoformat()}.{formato}"
    return Response(content=datos, media_type=_MEDIA[formato],
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/{equipo_id}/obsolescencia/refrescar", response_model=ObsolescenciaBancoOut)
def refrescar(equipo_id: int, limite: int = 10, db: Session = Depends(get_db),
              consultar=Depends(get_consultar_fabricante)):
    _equipo_o_404(db, equipo_id)
    return obsolescencia_banco.refrescar_banco(
        db, equipo_id, date.today(), limite=limite, consultar=consultar)
