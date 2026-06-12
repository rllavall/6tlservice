from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import auth_service, models
from app.db import get_db


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> models.Usuario:
    """Valida el token Bearer y sella el usuario en la sesión de BD (para auditoría)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "No autenticado")
    token = authorization.split(" ", 1)[1].strip()
    try:
        usuario = auth_service.validar_token(db, token)
    except auth_service.SesionInvalida:
        raise HTTPException(401, "Sesión inválida o expirada")
    db.info["usuario_id"] = usuario.id
    db.info["usuario_username"] = usuario.username
    return usuario


def get_consultar_fabricante():
    """Dependencia: función que consulta el estado de ciclo de vida de un producto
    (Claude Code headless). Inyectable — en tests se sobreescribe por un doble, así
    el import real de run_obsolescencia (con sus efectos de arranque) nunca ocurre."""
    from run_obsolescencia import consultar_fabricante
    return consultar_fabricante
