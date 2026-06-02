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


def test_equipo_filter_numero_serie_parcial_insensible(client, prod_equipo):
    client.post("/api/equipos", json={"numero_serie": "FA3000-0007", "producto_id": prod_equipo})
    client.post("/api/equipos", json={"numero_serie": "YAV12-0021", "producto_id": prod_equipo})
    # parcial
    r = client.get("/api/equipos?numero_serie=FA30")
    assert r.status_code == 200
    assert [e["numero_serie"] for e in r.json()] == ["FA3000-0007"]
    # insensible a mayúsculas/minúsculas
    assert len(client.get("/api/equipos?numero_serie=fa30").json()) == 1
    # sin coincidencias
    assert client.get("/api/equipos?numero_serie=ZZZ").json() == []


def test_equipo_filter_numero_serie_por_componente(client, prod_equipo, prod_componente):
    eq = client.post("/api/equipos", json={"numero_serie": "EQ-AAA", "producto_id": prod_equipo}).json()
    # equipo distractor SIN ese componente: no debe coincidir
    client.post("/api/equipos", json={"numero_serie": "EQ-BBB", "producto_id": prod_equipo})
    comp = client.post("/api/componentes", json={"numero_serie": "SN-DIG-1001", "producto_id": prod_componente}).json()
    client.post(f"/api/componentes/{comp['id']}/montar", json={
        "equipo_id": eq["id"], "fecha": "2026-06-01", "motivo": "entrega_inicial",
    })
    # buscar por la serie del COMPONENTE montado devuelve SOLO su equipo
    r = client.get("/api/equipos?numero_serie=DIG-1001")
    assert r.status_code == 200
    assert [e["id"] for e in r.json()] == [eq["id"]]
    # un equipo no se duplica aunque coincidan equipo y/o varios componentes (distinct)
    assert len(client.get("/api/equipos?numero_serie=EQ-AAA").json()) == 1
