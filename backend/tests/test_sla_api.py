def _equipo_contrato(client, nivel="gold"):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-SLAA", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": nivel, "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SLA1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    return eq["id"]


def _incidencia(client, equipo_id, apertura="2020-01-01"):
    return client.post("/api/incidencias", json={
        "tipo": "soporte_tecnico", "equipo_id": equipo_id, "titulo": "x",
        "descripcion_problema": "y", "prioridad": "media", "fecha_apertura": apertura}).json()


def test_sla_endpoint_incumplida(client):
    eid = _equipo_contrato(client)
    inc = _incidencia(client, eid, apertura="2020-01-01")
    out = client.get("/api/sla").json()
    ids = [i["incidencia"]["id"] for i in out["incumplidas"]]
    assert inc["id"] in ids
    item = next(i for i in out["incumplidas"] if i["incidencia"]["id"] == inc["id"])
    assert item["sla"]["estado_global"] == "incumplido"
    assert item["sla"]["nivel"] == "gold"
    assert set(out["resumen"].keys()) == {"en_riesgo", "incumplidas"}
    assert out["cumplimiento"]["total"] >= 1


def test_ficha_incidencia_incluye_sla(client):
    eid = _equipo_contrato(client)
    inc = _incidencia(client, eid, apertura="2020-01-01")
    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert ficha["sla"] is not None
    assert ficha["sla"]["nivel"] == "gold"


def test_ficha_incidencia_sin_contrato_sla_null(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-NOSLA", "tipo": "equipo", "descripcion": "B"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "NS1", "producto_id": prod["id"]}).json()
    inc = _incidencia(client, eq["id"])
    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert ficha["sla"] is None


def test_sla_protegido_401(client_sin_auth):
    assert client_sin_auth.get("/api/sla").status_code == 401
