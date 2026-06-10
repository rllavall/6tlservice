# tests/test_derivaciones_api.py
from datetime import date

from app import models


def _incidencia(db_session):
    inc = models.Incidencia(codigo="INC-9", titulo="t", descripcion_problema="d",
                            fecha_apertura=date(2026, 6, 1))
    db_session.add(inc)
    db_session.commit()
    return inc.id


def test_crear_listar_y_avanzar_derivacion(client, db_session):
    inc_id = _incidencia(db_session)
    fab = client.post("/api/fabricantes", json={"nombre": "National", "email_service": "svc@ni.com"}).json()

    r = client.post(f"/api/incidencias/{inc_id}/derivaciones",
                    json={"tipo": "externa_fabricante", "fabricante_id": fab["id"]})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["tu_referencia"] == "RMA-0001"
    assert d["estado"] == "pendiente"

    r = client.get(f"/api/incidencias/{inc_id}/derivaciones")
    assert r.status_code == 200 and len(r.json()) == 1

    r = client.patch(f"/api/derivaciones/{d['id']}",
                     json={"estado": "enviada", "referencia_externa": "NI-77"})
    assert r.status_code == 200
    assert r.json()["estado"] == "enviada"
    assert r.json()["referencia_externa"] == "NI-77"


def test_interna_sin_departamento_da_409(client, db_session):
    inc_id = _incidencia(db_session)
    r = client.post(f"/api/incidencias/{inc_id}/derivaciones",
                    json={"tipo": "interna_departamento"})
    assert r.status_code == 409


def test_transicion_invalida_da_409(client, db_session):
    inc_id = _incidencia(db_session)
    fab = client.post("/api/fabricantes", json={"nombre": "NI"}).json()
    d = client.post(f"/api/incidencias/{inc_id}/derivaciones",
                    json={"tipo": "externa_fabricante", "fabricante_id": fab["id"]}).json()
    r = client.patch(f"/api/derivaciones/{d['id']}", json={"estado": "cerrada"})
    assert r.status_code == 409
