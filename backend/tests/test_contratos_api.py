def _crear_contrato(client, cliente_id=None):
    return client.post("/api/contratos", json={
        "cliente_id": cliente_id, "nivel": "silver",
        "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01",
    })


def test_crud_contrato(client):
    r = _crear_contrato(client)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["codigo"].startswith("CTR-")
    assert r.json()["estado"] == "vigente"

    r = client.get(f"/api/contratos/{cid}")
    assert r.status_code == 200
    assert r.json()["contrato"]["nivel"] == "silver"
    assert r.json()["equipos"] == []

    r = client.put(f"/api/contratos/{cid}", json={"cancelado": True})
    assert r.status_code == 200
    assert r.json()["estado"] == "cancelado"

    r = client.get("/api/contratos?estado=cancelado")
    assert any(c["id"] == cid for c in r.json())


def test_asignar_y_desasignar_equipo(client):
    cli = client.post("/api/clientes", json={"nombre": "ACME"}).json()
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQ", "tipo": "equipo", "descripcion": "Banco"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN1", "producto_id": prod["id"], "cliente_id": cli["id"]}).json()
    con = _crear_contrato(client, cliente_id=cli["id"]).json()

    r = client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    assert r.status_code == 200, r.text
    detalle = client.get(f"/api/contratos/{con['id']}").json()
    assert [e["id"] for e in detalle["equipos"]] == [eq["id"]]

    eq_out = client.get(f"/api/equipos/{eq['id']}").json()["equipo"]
    assert eq_out["bajo_contrato"] is True

    r = client.delete(f"/api/contratos/{con['id']}/equipos/{eq['id']}")
    assert r.status_code == 200
    detalle = client.get(f"/api/contratos/{con['id']}").json()
    assert detalle["equipos"] == []


def test_asignar_equipo_cliente_distinto_409(client):
    cli_a = client.post("/api/clientes", json={"nombre": "A"}).json()
    cli_b = client.post("/api/clientes", json={"nombre": "B"}).json()
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQ2", "tipo": "equipo", "descripcion": "Banco"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN9", "producto_id": prod["id"], "cliente_id": cli_b["id"]}).json()
    con = _crear_contrato(client, cliente_id=cli_a["id"]).json()
    r = client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    assert r.status_code == 409


def test_delete_contrato_con_equipos_409(client):
    cli = client.post("/api/clientes", json={"nombre": "ACME"}).json()
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQ3", "tipo": "equipo", "descripcion": "Banco"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN5", "producto_id": prod["id"], "cliente_id": cli["id"]}).json()
    con = _crear_contrato(client, cliente_id=cli["id"]).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    r = client.delete(f"/api/contratos/{con['id']}")
    assert r.status_code == 409


def test_contratos_protegido_401(client_sin_auth):
    assert client_sin_auth.get("/api/contratos").status_code == 401


def test_delete_contrato_vacio_ok(client):
    con = _crear_contrato(client).json()
    r = client.delete(f"/api/contratos/{con['id']}")
    assert r.status_code in (200, 204)
