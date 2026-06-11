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


def test_producto_acepta_y_devuelve_categoria(client):
    r = client.post("/api/productos", json={
        "part_number": "FASTATE-3000", "tipo": "equipo", "descripcion": "Sistema ATE",
        "categoria": "ate",
    })
    assert r.status_code == 201, r.text
    assert r.json()["categoria"] == "ate"


def test_producto_categoria_opcional(client):
    r = client.post("/api/productos", json={"part_number": "PN-NC", "tipo": "equipo", "descripcion": "x"})
    assert r.status_code == 201, r.text
    assert r.json()["categoria"] is None


def test_producto_categoria_invalida_422(client):
    r = client.post("/api/productos", json={
        "part_number": "PN-BAD", "tipo": "equipo", "descripcion": "x", "categoria": "no_existe",
    })
    assert r.status_code == 422


def test_producto_enlaza_fabricante_id(client):
    fab = client.post("/api/fabricantes", json={"nombre": "National"}).json()
    r = client.post("/api/productos", json={
        "part_number": "PN-DMM", "tipo": "componente", "descripcion": "DMM",
        "fabricante_id": fab["id"],
    })
    assert r.status_code == 201, r.text
    assert r.json()["fabricante_id"] == fab["id"]


def test_producto_fabricante_id_opcional(client):
    r = client.post("/api/productos", json={"part_number": "PN-SIN", "tipo": "equipo", "descripcion": "x"})
    assert r.status_code == 201, r.text
    assert r.json()["fabricante_id"] is None


def test_producto_repunta_fabricante_id_en_update(client):
    fab = client.post("/api/fabricantes", json={"nombre": "Keysight"}).json()
    pid = client.post("/api/productos", json={
        "part_number": "PN-UPD", "tipo": "componente", "descripcion": "Osc",
    }).json()["id"]
    r = client.put(f"/api/productos/{pid}", json={
        "part_number": "PN-UPD", "tipo": "componente", "descripcion": "Osc",
        "fabricante_id": fab["id"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["fabricante_id"] == fab["id"]


def test_producto_acepta_y_devuelve_categoria_componente(client):
    r = client.post("/api/productos", json={
        "part_number": "KS-34470A", "tipo": "componente", "descripcion": "DMM",
        "categoria_componente": "instrumento",
    })
    assert r.status_code == 201, r.text
    assert r.json()["categoria_componente"] == "instrumento"


def test_producto_categoria_componente_opcional(client):
    r = client.post("/api/productos", json={
        "part_number": "CC-NC", "tipo": "componente", "descripcion": "x",
    })
    assert r.status_code == 201, r.text
    assert r.json()["categoria_componente"] is None


def test_producto_categoria_componente_invalida_422(client):
    r = client.post("/api/productos", json={
        "part_number": "CC-BAD", "tipo": "componente", "descripcion": "x",
        "categoria_componente": "no_existe",
    })
    assert r.status_code == 422


def test_productos_filtra_por_categoria_componente(client):
    client.post("/api/productos", json={
        "part_number": "INS-1", "tipo": "componente", "descripcion": "DMM",
        "categoria_componente": "instrumento",
    })
    client.post("/api/productos", json={
        "part_number": "WIR-1", "tipo": "componente", "descripcion": "Cable",
        "categoria_componente": "wiring",
    })
    r = client.get("/api/productos?categoria_componente=instrumento")
    assert r.status_code == 200
    pns = {p["part_number"] for p in r.json()}
    assert pns == {"INS-1"}
