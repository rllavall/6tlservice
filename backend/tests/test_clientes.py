import pytest


@pytest.fixture
def cliente_payload():
    return {
        "nombre": "Indra Sistemas",
        "cif": "A28297059",
        "persona_contacto": "Juan García",
        "email_contacto": "jgarcia@indra.es",
        "telefono_contacto": "+34 91 396 60 00",
        "notas": "Cliente prioritario",
    }


@pytest.fixture
def prod_equipo(client):
    return client.post(
        "/api/productos",
        json={"part_number": "ATE-2000", "tipo": "equipo", "descripcion": "Sistema ATE"},
    ).json()["id"]


# --- CRUD happy path ---

def test_cliente_create(client, cliente_payload):
    r = client.post("/api/clientes", json=cliente_payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["nombre"] == "Indra Sistemas"
    assert data["cif"] == "A28297059"
    assert "id" in data


def test_cliente_list(client, cliente_payload):
    client.post("/api/clientes", json=cliente_payload)
    r = client.get("/api/clientes")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["nombre"] == "Indra Sistemas"


def test_cliente_get(client, cliente_payload):
    cid = client.post("/api/clientes", json=cliente_payload).json()["id"]
    r = client.get(f"/api/clientes/{cid}")
    assert r.status_code == 200
    assert r.json()["id"] == cid


def test_cliente_get_404(client):
    r = client.get("/api/clientes/9999")
    assert r.status_code == 404


def test_cliente_update(client, cliente_payload):
    cid = client.post("/api/clientes", json=cliente_payload).json()["id"]
    updated = dict(cliente_payload, nombre="Indra Actualizado")
    r = client.put(f"/api/clientes/{cid}", json=updated)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Indra Actualizado"


def test_cliente_delete(client, cliente_payload):
    cid = client.post("/api/clientes", json=cliente_payload).json()["id"]
    r = client.delete(f"/api/clientes/{cid}")
    assert r.status_code == 204
    r = client.get(f"/api/clientes/{cid}")
    assert r.status_code == 404


# --- Delete guard ---

def test_cliente_delete_409_when_equipo_references_it(client, cliente_payload, prod_equipo):
    cid = client.post("/api/clientes", json=cliente_payload).json()["id"]
    client.post("/api/equipos", json={"numero_serie": "EQ-CL1", "producto_id": prod_equipo, "cliente_id": cid})
    r = client.delete(f"/api/clientes/{cid}")
    assert r.status_code == 409
    assert "uso" in r.json()["detail"].lower()


def test_cliente_delete_409_when_ubicacion_references_it(client, cliente_payload):
    cid = client.post("/api/clientes", json=cliente_payload).json()["id"]
    client.post(
        "/api/ubicaciones",
        json={"nombre": "Planta Indra", "tipo": "fabrica_cliente", "cliente_id": cid},
    )
    r = client.delete(f"/api/clientes/{cid}")
    assert r.status_code == 409
    assert "uso" in r.json()["detail"].lower()


# --- Ubicacion with cliente_id ---

def test_ubicacion_with_valid_cliente_id(client, cliente_payload):
    cid = client.post("/api/clientes", json=cliente_payload).json()["id"]
    r = client.post(
        "/api/ubicaciones",
        json={"nombre": "Planta Madrid", "tipo": "fabrica_cliente", "cliente_id": cid, "ciudad": "Madrid"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["cliente_id"] == cid


def test_ubicacion_with_nonexistent_cliente_id_404(client):
    r = client.post(
        "/api/ubicaciones",
        json={"nombre": "Planta X", "tipo": "fabrica_cliente", "cliente_id": 9999},
    )
    assert r.status_code == 404


# --- Equipo with cliente_id ---

def test_equipo_with_valid_cliente_id(client, cliente_payload, prod_equipo):
    cid = client.post("/api/clientes", json=cliente_payload).json()["id"]
    r = client.post(
        "/api/equipos",
        json={"numero_serie": "EQ-V1", "producto_id": prod_equipo, "cliente_id": cid},
    )
    assert r.status_code == 201, r.text
    assert r.json()["cliente_id"] == cid


def test_equipo_with_nonexistent_cliente_id_404(client, prod_equipo):
    r = client.post(
        "/api/equipos",
        json={"numero_serie": "EQ-X1", "producto_id": prod_equipo, "cliente_id": 9999},
    )
    assert r.status_code == 404


# --- Ficha includes cliente ---

def test_ficha_includes_cliente(client, cliente_payload, prod_equipo):
    cid = client.post("/api/clientes", json=cliente_payload).json()["id"]
    eid = client.post(
        "/api/equipos",
        json={"numero_serie": "EQ-F1", "producto_id": prod_equipo, "cliente_id": cid},
    ).json()["id"]
    r = client.get(f"/api/equipos/{eid}")
    assert r.status_code == 200
    ficha = r.json()
    assert ficha["equipo"]["numero_serie"] == "EQ-F1"
    assert ficha["cliente"] is not None
    assert ficha["cliente"]["id"] == cid
    assert ficha["cliente"]["nombre"] == "Indra Sistemas"


def test_ficha_cliente_none_when_no_cliente(client, prod_equipo):
    eid = client.post(
        "/api/equipos",
        json={"numero_serie": "EQ-NC1", "producto_id": prod_equipo},
    ).json()["id"]
    r = client.get(f"/api/equipos/{eid}")
    assert r.status_code == 200
    assert r.json()["cliente"] is None
