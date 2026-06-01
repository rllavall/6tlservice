import pytest


@pytest.fixture
def escenario(client):
    pe = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "Sistema"}).json()["id"]
    pc = client.post("/api/productos", json={"part_number": "PXI", "tipo": "componente", "descripcion": "Digi"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "EQ-SER", "producto_id": pe}).json()["id"]
    comp = client.post("/api/componentes", json={"numero_serie": "COMP-SER", "producto_id": pc}).json()["id"]
    uid = client.post("/api/ubicaciones", json={"nombre": "Indra", "tipo": "fabrica_cliente"}).json()["id"]
    client.post(f"/api/componentes/{comp}/montar", json={"equipo_id": eq, "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    client.post(f"/api/equipos/{eq}/movimientos", json={"ubicacion_destino_id": uid, "fecha": "2026-02-01", "motivo": "entrega"})
    return {"equipo": eq, "componente": comp, "ubicacion": uid, "prod_componente": pc}


def test_buscar_por_serie_equipo(client, escenario):
    r = client.get("/api/buscar?serie=EQ-SER")
    assert r.status_code == 200
    assert r.json()["tipo"] == "equipo"
    assert r.json()["equipo"]["id"] == escenario["equipo"]


def test_buscar_por_serie_componente_devuelve_su_equipo(client, escenario):
    r = client.get("/api/buscar?serie=COMP-SER")
    body = r.json()
    assert body["tipo"] == "componente"
    assert body["componente"]["id"] == escenario["componente"]
    assert body["equipo_del_componente"]["id"] == escenario["equipo"]


def test_buscar_no_encontrado(client):
    r = client.get("/api/buscar?serie=NOPE")
    assert r.status_code == 200
    assert r.json()["tipo"] == "ninguno"


def test_equipos_por_part_number(client, escenario):
    r = client.get("/api/equipos?part_number=PXI")
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert escenario["equipo"] in ids


def test_equipos_en_ubicacion(client, escenario):
    r = client.get(f"/api/ubicaciones/{escenario['ubicacion']}/equipos")
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert escenario["equipo"] in ids
