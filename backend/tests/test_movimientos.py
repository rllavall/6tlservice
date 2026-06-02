from datetime import date

import pytest

from app import models
from app.trazabilidad import ubicacion_actual


@pytest.fixture
def equipo_id(client):
    pid = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "x"}).json()["id"]
    return client.post("/api/equipos", json={"numero_serie": "S", "producto_id": pid}).json()["id"]


def test_ubicacion_actual_none_when_no_movimientos(db_session):
    p = models.Producto(part_number="ATE", tipo="equipo", descripcion="x")
    db_session.add(p)
    db_session.flush()
    eq = models.Equipo(numero_serie="S", producto_id=p.id)
    db_session.add(eq)
    db_session.flush()
    assert ubicacion_actual(db_session, eq.id) is None


def test_ubicacion_actual_is_latest_by_fecha(db_session):
    p = models.Producto(part_number="ATE", tipo="equipo", descripcion="x")
    u1 = models.Ubicacion(nombre="A", tipo="sede_6tl")
    u2 = models.Ubicacion(nombre="B", tipo="fabrica_cliente")
    db_session.add_all([p, u1, u2])
    db_session.flush()
    eq = models.Equipo(numero_serie="S", producto_id=p.id)
    db_session.add(eq)
    db_session.flush()
    db_session.add(models.Movimiento(equipo_id=eq.id, ubicacion_destino_id=u1.id, fecha=date(2026, 1, 1), motivo="entrega"))
    db_session.add(models.Movimiento(equipo_id=eq.id, ubicacion_destino_id=u2.id, fecha=date(2026, 6, 1), motivo="traslado"))
    db_session.flush()
    assert ubicacion_actual(db_session, eq.id).id == u2.id


def test_registrar_movimiento_endpoint(client, equipo_id):
    uid = client.post("/api/ubicaciones", json={"nombre": "Indra", "tipo": "fabrica_cliente"}).json()["id"]
    r = client.post(f"/api/equipos/{equipo_id}/movimientos", json={"ubicacion_destino_id": uid, "fecha": "2026-03-01", "motivo": "entrega"})
    assert r.status_code == 201, r.text
    assert r.json()["ubicacion_destino_id"] == uid
