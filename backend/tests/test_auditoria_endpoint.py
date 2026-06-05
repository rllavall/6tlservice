def test_auditoria_filtra_por_entidad(client):
    # el fixture `client` sella usuario de prueba; crear un cliente genera un log
    client.post("/api/clientes", json={"nombre": "ACME"})
    r = client.get("/api/auditoria", params={"entidad": "clientes"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 1
    assert all(item["entidad"] == "clientes" for item in data)
    assert data[0]["accion"] == "alta"


def test_auditoria_filtra_por_entidad_id(client):
    c = client.post("/api/clientes", json={"nombre": "ACME"}).json()
    otro = client.post("/api/clientes", json={"nombre": "OTRA"}).json()
    r = client.get("/api/auditoria", params={"entidad": "clientes", "entidad_id": c["id"]})
    ids = {item["entidad_id"] for item in r.json()}
    assert ids == {c["id"]}


def test_auditoria_orden_desc_y_limite(client):
    for n in range(3):
        client.post("/api/clientes", json={"nombre": f"C{n}"})
    r = client.get("/api/auditoria", params={"limit": 2})
    data = r.json()
    assert len(data) == 2
    assert data[0]["id"] > data[1]["id"]   # más reciente primero
