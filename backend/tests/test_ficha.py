import pytest


@pytest.fixture
def escenario(client):
    pe = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "Sistema"}).json()["id"]
    pc = client.post("/api/productos", json={"part_number": "PXI", "tipo": "componente", "descripcion": "Digi"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "EQ", "producto_id": pe}).json()["id"]
    comp = client.post("/api/componentes", json={"numero_serie": "C", "producto_id": pc}).json()["id"]
    uid = client.post("/api/ubicaciones", json={"nombre": "Indra", "tipo": "fabrica_cliente"}).json()["id"]
    client.post(f"/api/componentes/{comp}/montar", json={"equipo_id": eq, "posicion": "r3", "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    client.post(f"/api/equipos/{eq}/movimientos", json={"ubicacion_destino_id": uid, "fecha": "2026-02-01", "motivo": "entrega"})
    return {"equipo": eq, "ubicacion": uid}


def test_ficha_composes_everything(client, escenario):
    r = client.get(f"/api/equipos/{escenario['equipo']}")
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["equipo"]["numero_serie"] == "EQ"
    assert f["producto"]["part_number"] == "ATE"
    assert f["ubicacion_actual"]["id"] == escenario["ubicacion"]
    assert len(f["componentes"]) == 1 and f["componentes"][0]["posicion"] == "r3"
    assert len(f["historial_movimientos"]) == 1
    assert len(f["historial_configuracion"]) == 1


def test_ficha_no_movimientos_ubicacion_null(client):
    pe = client.post("/api/productos", json={"part_number": "P", "tipo": "equipo", "descripcion": "x"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "S", "producto_id": pe}).json()["id"]
    f = client.get(f"/api/equipos/{eq}").json()
    assert f["ubicacion_actual"] is None
