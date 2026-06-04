from __future__ import annotations

from sqlalchemy.orm import Session

from app import models


class SolicitudError(Exception):
    """Error de negocio en solicitudes (→ 409)."""


def generar_codigo(db: Session) -> str:
    """Siguiente código `SOL-NNNN`."""
    nums = []
    for (codigo,) in db.query(models.SolicitudSoporte.codigo).all():
        if codigo and codigo.startswith("SOL-"):
            try:
                nums.append(int(codigo.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"SOL-{n:04d}"
