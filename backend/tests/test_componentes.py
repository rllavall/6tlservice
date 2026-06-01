import pytest


@pytest.fixture
def prod_componente(client):
    return client.post("/api/productos", json={"part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digi"}).json()["id"]


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={"part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema"}).json()["id"]


def test_componente_create_unassigned(client, prod_componente):
    r = client.post("/api/componentes", json={"numero_serie": "C-1", "producto_id": prod_componente})
    assert r.status_code == 201, r.text
    assert r.json()["equipo_id"] is None


def test_componente_rejects_equipo_producto(client, prod_equipo):
    r = client.post("/api/componentes", json={"numero_serie": "C", "producto_id": prod_equipo})
    assert r.status_code == 409
    assert "componente" in r.json()["detail"].lower()


def test_componente_list_and_update(client, prod_componente):
    cid = client.post("/api/componentes", json={"numero_serie": "C-2", "producto_id": prod_componente}).json()["id"]
    r = client.get("/api/componentes")
    assert any(c["id"] == cid for c in r.json())
    r = client.put(f"/api/componentes/{cid}", json={"numero_serie": "C-2", "producto_id": prod_componente, "notas": "ok"})
    assert r.json()["notas"] == "ok"
