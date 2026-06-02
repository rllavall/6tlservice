def test_producto_crud_and_filter(client):
    r = client.post("/api/productos", json={"part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    client.post("/api/productos", json={"part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digitizer"})

    r = client.get("/api/productos?tipo=equipo")
    assert r.status_code == 200
    tipos = {p["tipo"] for p in r.json()}
    assert tipos == {"equipo"}

    r = client.put(f"/api/productos/{pid}", json={"part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema v2"})
    assert r.json()["descripcion"] == "Sistema v2"


def test_producto_duplicate_part_number_409(client):
    client.post("/api/productos", json={"part_number": "DUP", "tipo": "equipo", "descripcion": "a"})
    r = client.post("/api/productos", json={"part_number": "DUP", "tipo": "componente", "descripcion": "b"})
    assert r.status_code == 409


def test_producto_delete_in_use_409(client):
    pid = client.post("/api/productos", json={"part_number": "P", "tipo": "equipo", "descripcion": "a"}).json()["id"]
    client.post("/api/equipos", json={"numero_serie": "S", "producto_id": pid})
    r = client.delete(f"/api/productos/{pid}")
    assert r.status_code == 409
