import json
from datetime import date

from app import models, seguridad


def _con_usuario(db):
    db.info["usuario_id"] = None
    db.info["usuario_username"] = "ramon"


def test_alta_genera_log(db_session):
    _con_usuario(db_session)
    db_session.add(models.Cliente(nombre="ACME"))
    db_session.commit()
    logs = db_session.query(models.AuditoriaLog).filter_by(entidad="clientes").all()
    assert len(logs) == 1
    log = logs[0]
    assert log.accion == "alta" and log.usuario_username == "ramon" and log.entidad_id is not None
    cambios = json.loads(log.cambios)
    assert cambios["nombre"][1] == "ACME"


def test_edicion_genera_log_con_diff(db_session):
    _con_usuario(db_session)
    c = models.Cliente(nombre="ACME")
    db_session.add(c)
    db_session.commit()
    c.nombre = "ACME 2"
    db_session.commit()
    log = db_session.query(models.AuditoriaLog).filter_by(entidad="clientes", accion="edicion").one()
    cambios = json.loads(log.cambios)
    assert cambios["nombre"] == ["ACME", "ACME 2"]


def test_edicion_sin_cambios_reales_no_genera_log(db_session):
    _con_usuario(db_session)
    c = models.Cliente(nombre="ACME")
    db_session.add(c)
    db_session.commit()
    c.nombre = "ACME"  # mismo valor
    db_session.commit()
    assert db_session.query(models.AuditoriaLog).filter_by(accion="edicion").count() == 0


def test_borrado_genera_log(db_session):
    _con_usuario(db_session)
    c = models.Cliente(nombre="ACME")
    db_session.add(c)
    db_session.commit()
    cid = c.id
    db_session.delete(c)
    db_session.commit()
    log = db_session.query(models.AuditoriaLog).filter_by(entidad="clientes", accion="borrado").one()
    assert log.entidad_id == cid


def test_sin_usuario_registra_sistema(db_session):
    # sin sellar db.info
    db_session.add(models.Cliente(nombre="X"))
    db_session.commit()
    log = db_session.query(models.AuditoriaLog).filter_by(entidad="clientes").one()
    assert log.usuario_username == "sistema"


def test_password_hash_redactado(db_session):
    _con_usuario(db_session)
    db_session.add(models.Usuario(
        username="u", nombre="U", password_hash=seguridad.hash_password("s"),
        activo=True, rol="admin", fecha_alta=date(2026, 6, 5),
    ))
    db_session.commit()
    log = db_session.query(models.AuditoriaLog).filter_by(entidad="usuarios").one()
    cambios = json.loads(log.cambios)
    assert cambios["password_hash"][1] == "***"


def test_sesion_y_auditoria_excluidas(db_session):
    _con_usuario(db_session)
    u = models.Usuario(
        username="u", nombre="U", password_hash=seguridad.hash_password("s"),
        activo=True, rol="admin", fecha_alta=date(2026, 6, 5),
    )
    db_session.add(u)
    db_session.commit()
    from app import auth_service
    auth_service.crear_sesion(db_session, u)  # crea una Sesion
    assert db_session.query(models.AuditoriaLog).filter(
        models.AuditoriaLog.entidad.in_(["sesiones", "auditoria"])
    ).count() == 0
