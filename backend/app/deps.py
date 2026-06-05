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
