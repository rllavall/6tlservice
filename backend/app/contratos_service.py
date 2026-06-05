from __future__ import annotations

from sqlalchemy.orm import Session

from app import models


class ContratoError(Exception):
    """Error de negocio en contratos (→ HTTP 409)."""


def generar_codigo(db: Session) -> str:
    """Siguiente código `CTR-NNNN`."""
    nums = []
    for (codigo,) in db.query(models.ContratoMantenimiento.codigo).all():
        if codigo and codigo.startswith("CTR-"):
            try:
                nums.append(int(codigo.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"CTR-{n:04d}"


def vincular_equipo(db: Session, contrato: models.ContratoMantenimiento, equipo: models.Equipo) -> None:
    if equipo.cliente_id is not None and contrato.cliente_id is not None \
            and equipo.cliente_id != contrato.cliente_id:
        raise ContratoError("El equipo pertenece a otro cliente que el titular del contrato")
    equipo.contrato_id = contrato.id
    db.flush()


def desvincular_equipo(db: Session, equipo: models.Equipo) -> None:
    equipo.contrato_id = None
    db.flush()
