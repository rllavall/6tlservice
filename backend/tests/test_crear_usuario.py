import pytest

from app import crear_usuario, models, seguridad


def test_crear_usuario_persiste_hash(db_session):
    u = crear_usuario.crear_usuario(db_session, "ramon", "secreto", nombre="Ramón", rol="admin")
    assert u.id is not None
    assert u.username == "ramon" and u.nombre == "Ramón" and u.rol == "admin" and u.activo is True
    assert u.password_hash != "secreto"
    assert seguridad.verify_password("secreto", u.password_hash) is True


def test_crear_usuario_duplicado_falla(db_session):
    crear_usuario.crear_usuario(db_session, "ramon", "secreto")
    with pytest.raises(crear_usuario.UsuarioYaExiste):
        crear_usuario.crear_usuario(db_session, "ramon", "otra")
