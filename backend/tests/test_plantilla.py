"""CRUD de la plantilla de configuración esperada (producto-equipo)."""
import pytest


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={
        "part_number": "ATE-9000", "tipo": "equipo", "descripcion": "Banco"}).json()["id"]


@pytest.fixture
def prod_inst(client):
    return client.post("/api/productos", json={
        "part_number": "DMM-1", "tipo": "componente", "descripcion": "Multímetro",
        "categoria_componente": "instrumento"}).json()["id"]


@pytest.fixture
def prod_cable(client):
    return client.post("/api/productos", json={
        "part_number": "CBL-1", "tipo": "componente", "descripcion": "Cable",
        "categoria_componente": "wiring", "bajo_coste": True}).json()["id"]


def test_crear_y_listar_plantilla_con_nivel_derivado(client, prod_equipo, prod_inst, prod_cable):
    r = client.post(f"/api/productos/{prod_equipo}/plantilla",
                    json={"producto_componente_id": prod_inst, "posicion": "A1"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["part_number"] == "DMM-1"
    assert body["nivel_trazabilidad"] == "serie"
    assert body["cantidad"] == 1

    client.post(f"/api/productos/{prod_equipo}/plantilla",
                json={"producto_componente_id": prod_cable, "posicion": "W1", "cantidad": 3})

    filas = client.get(f"/api/productos/{prod_equipo}/plantilla").json()
    assert len(filas) == 2
    cable = next(f for f in filas if f["part_number"] == "CBL-1")
    assert cable["nivel_trazabilidad"] == "no_trazado"
    assert cable["cantidad"] == 3


def test_rechaza_producto_equipo_inexistente(client, prod_inst):
    r = client.post("/api/productos/99999/plantilla",
                    json={"producto_componente_id": prod_inst})
    assert r.status_code == 404


def test_rechaza_componente_que_es_equipo(client, prod_equipo):
    r = client.post(f"/api/productos/{prod_equipo}/plantilla",
                    json={"producto_componente_id": prod_equipo})
    assert r.status_code == 409


def test_linea_duplicada_409(client, prod_equipo, prod_inst):
    client.post(f"/api/productos/{prod_equipo}/plantilla",
                json={"producto_componente_id": prod_inst, "posicion": "A1"})
    r = client.post(f"/api/productos/{prod_equipo}/plantilla",
                    json={"producto_componente_id": prod_inst, "posicion": "A1"})
    assert r.status_code == 409


def test_patch_y_delete(client, prod_equipo, prod_inst):
    lid = client.post(f"/api/productos/{prod_equipo}/plantilla",
                      json={"producto_componente_id": prod_inst, "posicion": "A1"}).json()["id"]
    r = client.patch(f"/api/plantilla/{lid}", json={"cantidad": 2, "posicion": "A2"})
    assert r.status_code == 200
    assert r.json()["cantidad"] == 2
    assert r.json()["posicion"] == "A2"

    r = client.patch(f"/api/plantilla/{lid}", json={"cantidad": 0})
    assert r.status_code == 422

    assert client.delete(f"/api/plantilla/{lid}").status_code == 204
    assert client.get(f"/api/productos/{prod_equipo}/plantilla").json() == []
    assert client.delete(f"/api/plantilla/{lid}").status_code == 404
