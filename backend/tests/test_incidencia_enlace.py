"""Task 7: optional incidencia_id wired through montar/desmontar/sustituir/movimiento."""
from __future__ import annotations


def _setup(client):
    pe = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    pc = client.post("/api/productos", json={"part_number": "PN-C", "tipo": "componente", "descripcion": "C"}).json()
    ub = client.post("/api/ubicaciones", json={"nombre": "Taller", "tipo": "en_reparacion"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": pe["id"]}).json()
    comp = client.post("/api/componentes", json={"numero_serie": "C1", "producto_id": pc["id"]}).json()
    inc = client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01"}).json()
    return pe, pc, ub, eq, comp, inc


def test_montar_con_incidencia_aparece_en_expediente(client):
    _pe, _pc, _ub, eq, comp, inc = _setup(client)
    r = client.post(f"/api/componentes/{comp['id']}/montar", json={
        "equipo_id": eq["id"], "fecha": "2026-06-02", "motivo": "reparacion", "incidencia_id": inc["id"],
    })
    assert r.status_code == 201, r.text
    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert len(ficha["cambios_configuracion"]) == 1
    assert ficha["cambios_configuracion"][0]["componente_id"] == comp["id"]


def test_movimiento_con_incidencia_aparece_en_expediente(client):
    _pe, _pc, ub, eq, _comp, inc = _setup(client)
    r = client.post(f"/api/equipos/{eq['id']}/movimientos", json={
        "ubicacion_destino_id": ub["id"], "fecha": "2026-06-02", "motivo": "reparacion", "incidencia_id": inc["id"],
    })
    assert r.status_code == 201, r.text
    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert len(ficha["movimientos"]) == 1


def test_montar_sin_incidencia_sigue_funcionando(client):
    _pe, _pc, _ub, eq, comp, _inc = _setup(client)
    r = client.post(f"/api/componentes/{comp['id']}/montar", json={
        "equipo_id": eq["id"], "fecha": "2026-06-02", "motivo": "reparacion",
    })
    assert r.status_code == 201, r.text


def test_delete_incidencia_con_evento_enlazado_409(client):
    _pe, _pc, ub, eq, _comp, inc = _setup(client)
    client.post(f"/api/equipos/{eq['id']}/movimientos", json={
        "ubicacion_destino_id": ub["id"], "fecha": "2026-06-02", "motivo": "reparacion", "incidencia_id": inc["id"],
    })
    # la incidencia está 'abierta' pero tiene un evento enlazado -> no se puede borrar
    assert client.delete(f"/api/incidencias/{inc['id']}").status_code == 409
