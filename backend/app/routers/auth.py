from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import auth_service, models
from app.db import get_db
from app.deps import get_current_user
from app.schemas import LoginOut, LoginPayload, UsuarioOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    try:
        usuario = auth_service.autenticar(db, payload.username, payload.password)
    except auth_service.CredencialesInvalidas:
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    sesion = auth_service.crear_sesion(db, usuario)
    return {"token": sesion.token, "usuario": usuario}


@router.post("/logout", status_code=204)
def logout(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
) -> None:
    token = authorization.split(" ", 1)[1].strip()
    auth_service.cerrar_sesion(db, token)


@router.get("/me", response_model=UsuarioOut)
def me(usuario: models.Usuario = Depends(get_current_user)) -> models.Usuario:
    return usuario
