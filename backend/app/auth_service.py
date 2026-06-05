from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import models, seguridad


class CredencialesInvalidas(Exception):
    """Login fallido (usuario/contraseña incorrectos o usuario inactivo)."""


class SesionInvalida(Exception):
    """Token inexistente, expirado, o de usuario inactivo."""


def _dias_sesion() -> int:
    try:
        return int(os.environ.get("AUTH_SESION_DIAS", "7"))
    except ValueError:
        return 7


def autenticar(db: Session, username: str, password: str) -> models.Usuario:
    u = db.query(models.Usuario).filter(models.Usuario.username == username).first()
    if u is None or not u.activo or not seguridad.verify_password(password, u.password_hash):
        raise CredencialesInvalidas("Usuario o contraseña incorrectos")
    return u


def crear_sesion(db: Session, usuario: models.Usuario, *, ahora: Optional[datetime] = None) -> models.Sesion:
    ahora = ahora or datetime.now()
    s = models.Sesion(
        token=secrets.token_urlsafe(32),
        usuario_id=usuario.id,
        fecha_creacion=ahora,
        fecha_expiracion=ahora + timedelta(days=_dias_sesion()),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def validar_token(db: Session, token: str, *, ahora: Optional[datetime] = None) -> models.Usuario:
    ahora = ahora or datetime.now()
    s = db.query(models.Sesion).filter(models.Sesion.token == token).first()
    if s is None or s.fecha_expiracion < ahora:
        raise SesionInvalida("Sesión inválida o expirada")
    u = db.get(models.Usuario, s.usuario_id)
    if u is None or not u.activo:
        raise SesionInvalida("Usuario inactivo")
    return u


def cerrar_sesion(db: Session, token: str) -> None:
    s = db.query(models.Sesion).filter(models.Sesion.token == token).first()
    if s is not None:
        db.delete(s)
        db.commit()
