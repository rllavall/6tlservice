from datetime import date

import pytest

from app import contratos_service as svc
from app import models


def _cliente(db, nombre="ACME"):
    c = models.Cliente(nombre=nombre)
    db.add(c); db.flush()
    return c


def _producto(db):
    p = models.Producto(part_number="6TL-EQ", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    return p


def _contrato(db, cliente_id):
    c = models.ContratoMantenimiento(
        codigo=svc.generar_codigo(db), cliente_id=cliente_id, nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db.add(c); db.flush()
    return c


def test_generar_codigo_secuencial(db_session):
    assert svc.generar_codigo(db_session) == "CTR-0001"
    db_session.add(models.ContratoMantenimiento(
        codigo="CTR-0001", nivel="bronze", fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    ))
    db_session.flush()
    assert svc.generar_codigo(db_session) == "CTR-0002"


def test_vincular_equipo_ok(db_session):
    cli = _cliente(db_session)
    con = _contrato(db_session, cli.id)
    p = _producto(db_session)
    eq = models.Equipo(numero_serie="SN1", producto_id=p.id, cliente_id=cli.id)
    db_session.add(eq); db_session.flush()
    svc.vincular_equipo(db_session, con, eq)
    assert eq.contrato_id == con.id


def test_vincular_equipo_cliente_distinto_falla(db_session):
    cli_a = _cliente(db_session, "A")
    cli_b = _cliente(db_session, "B")
    con = _contrato(db_session, cli_a.id)
    p = _producto(db_session)
    eq = models.Equipo(numero_serie="SN2", producto_id=p.id, cliente_id=cli_b.id)
    db_session.add(eq); db_session.flush()
    with pytest.raises(svc.ContratoError):
        svc.vincular_equipo(db_session, con, eq)


def test_vincular_equipo_sin_cliente_permitido(db_session):
    cli = _cliente(db_session)
    con = _contrato(db_session, cli.id)
    p = _producto(db_session)
    eq = models.Equipo(numero_serie="SN3", producto_id=p.id, cliente_id=None)
    db_session.add(eq); db_session.flush()
    svc.vincular_equipo(db_session, con, eq)
    assert eq.contrato_id == con.id
