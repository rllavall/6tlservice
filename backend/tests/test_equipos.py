import pytest


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={"part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema"}).json()["id"]


@pytest.fixture
def prod_componente(client):
    return client.post("/api/productos", json={"part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digi"}).json()["id"]


def test_equipo_create_and_get(client, prod_equipo):
    r = client.post("/api/equipos", json={"numero_serie": "EQ-1", "producto_id": prod_equipo})
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    r = client.get(f"/api/equipos/{eid}")
    assert r.status_code == 200
    assert r.json()["equipo"]["numero_serie"] == "EQ-1"


def test_equipo_rejects_componente_producto(client, prod_componente):
    r = client.post("/api/equipos", json={"numero_serie": "X", "producto_id": prod_componente})
    assert r.status_code == 409
    assert "equipo" in r.json()["detail"].lower()


def test_equipo_duplicate_serie_same_producto_409(client, prod_equipo):
    client.post("/api/equipos", json={"numero_serie": "DUP", "producto_id": prod_equipo})
    r = client.post("/api/equipos", json={"numero_serie": "DUP", "producto_id": prod_equipo})
    assert r.status_code == 409


def test_equipo_list_filter_by_producto(client, prod_equipo):
    client.post("/api/equipos", json={"numero_serie": "A", "producto_id": prod_equipo})
    r = client.get(f"/api/equipos?producto_id={prod_equipo}")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_equipo_update(client, prod_equipo):
    eid = client.post("/api/equipos", json={"numero_serie": "U", "producto_id": prod_equipo}).json()["id"]
    r = client.put(f"/api/equipos/{eid}", json={"estado": "baja"})
    assert r.status_code == 200
    assert r.json()["estado"] == "baja"
