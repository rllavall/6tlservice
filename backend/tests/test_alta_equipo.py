import pytest


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={
        "part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema",
        "meses_garantia_default": 24,
    }).json()["id"]


@pytest.fixture
def prod_componente(client):
    return client.post("/api/productos", json={
        "part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digi",
    }).json()["id"]


@pytest.fixture
def cliente(client):
    return client.post("/api/clientes", json={"nombre": "Indra"}).json()["id"]


@pytest.fixture
def ubicacion(client, cliente):
    return client.post("/api/ubicaciones", json={
        "nombre": "Planta Aranjuez", "tipo": "fabrica_cliente", "cliente_id": cliente,
    }).json()["id"]


def test_alta_schema_defaults():
    from app.schemas import EquipoAltaCreate
    p = EquipoAltaCreate(numero_serie="EQ-1", producto_id=1)
    assert p.estado == "operativo"
    assert p.componentes == []
    assert p.ubicacion_id is None


def test_alta_solo_equipo_prefill_garantia(client, prod_equipo):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-100", "producto_id": prod_equipo,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["numero_serie"] == "EQ-100"
    assert body["meses_garantia"] == 24
    assert client.get(f"/api/equipos/{body['id']}").status_code == 200


def test_alta_respeta_garantia_explicita(client, prod_equipo):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-101", "producto_id": prod_equipo, "meses_garantia": 12,
    })
    assert r.status_code == 201, r.text
    assert r.json()["meses_garantia"] == 12


def test_alta_con_ubicacion_crea_movimiento(client, prod_equipo, cliente, ubicacion):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-200", "producto_id": prod_equipo,
        "cliente_id": cliente, "ubicacion_id": ubicacion,
    })
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    ficha = client.get(f"/api/equipos/{eid}").json()
    assert ficha["ubicacion_actual"] is not None
    assert ficha["ubicacion_actual"]["id"] == ubicacion


def test_alta_con_componentes_los_monta(client, prod_equipo, prod_componente):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-300", "producto_id": prod_equipo,
        "componentes": [
            {"producto_id": prod_componente, "numero_serie": "C-1", "posicion": "slot1"},
            {"producto_id": prod_componente, "numero_serie": "C-2"},
        ],
    })
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    comps = client.get(f"/api/componentes?equipo_id={eid}").json()
    series = sorted(c["numero_serie"] for c in comps)
    assert series == ["C-1", "C-2"]


def test_alta_rechaza_producto_equipo_no_equipo(client, prod_componente):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "X", "producto_id": prod_componente,
    })
    assert r.status_code == 409
    assert r.json()["detail"]["step"] == "unit"


def test_alta_rechaza_componente_no_componente(client, prod_equipo):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-400", "producto_id": prod_equipo,
        "componentes": [{"producto_id": prod_equipo, "numero_serie": "C-X"}],
    })
    assert r.status_code == 409
    assert r.json()["detail"]["step"] == "component"
    assert r.json()["detail"]["index"] == 0
    assert client.get("/api/equipos?numero_serie=EQ-400").json() == []
