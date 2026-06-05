from datetime import date, datetime, timedelta

import pytest

from app import auth_service as svc
from app import models, seguridad


def _crear_usuario(db, username="ramon", password="secreto", activo=True):
    u = models.Usuario(
        username=username, nombre="Ramón",
        password_hash=seguridad.hash_password(password),
        activo=activo, rol="admin", fecha_alta=date(2026, 6, 5),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_autenticar_ok(db_session):
    u = _crear_usuario(db_session)
    assert svc.autenticar(db_session, "ramon", "secreto").id == u.id


def test_autenticar_password_mala(db_session):
    _crear_usuario(db_session)
    with pytest.raises(svc.CredencialesInvalidas):
        svc.autenticar(db_session, "ramon", "mala")


def test_autenticar_usuario_inactivo(db_session):
    _crear_usuario(db_session, activo=False)
    with pytest.raises(svc.CredencialesInvalidas):
        svc.autenticar(db_session, "ramon", "secreto")


def test_autenticar_usuario_inexistente(db_session):
    with pytest.raises(svc.CredencialesInvalidas):
        svc.autenticar(db_session, "nadie", "x")


def test_crear_y_validar_token(db_session):
    u = _crear_usuario(db_session)
    s = svc.crear_sesion(db_session, u)
    assert s.token and s.usuario_id == u.id
    assert svc.validar_token(db_session, s.token).id == u.id


def test_validar_token_expirado(db_session):
    u = _crear_usuario(db_session)
    ayer = datetime(2026, 1, 1)
    s = svc.crear_sesion(db_session, u, ahora=ayer)
    with pytest.raises(svc.SesionInvalida):
        svc.validar_token(db_session, s.token, ahora=datetime(2026, 6, 5))


def test_validar_token_inexistente(db_session):
    with pytest.raises(svc.SesionInvalida):
        svc.validar_token(db_session, "no-existe")


def test_cerrar_sesion(db_session):
    u = _crear_usuario(db_session)
    s = svc.crear_sesion(db_session, u)
    svc.cerrar_sesion(db_session, s.token)
    with pytest.raises(svc.SesionInvalida):
        svc.validar_token(db_session, s.token)
