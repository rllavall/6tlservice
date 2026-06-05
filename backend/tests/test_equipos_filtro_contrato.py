"""Tests for ?bajo_contrato= filter on GET /api/equipos."""


def _setup(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQF", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": "bronze", "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    e_con = client.post("/api/equipos", json={
        "numero_serie": "C1", "producto_id": prod["id"]}).json()
    e_sin = client.post("/api/equipos", json={
        "numero_serie": "S1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": e_con["id"]})
    return e_con["id"], e_sin["id"]


def test_filtro_bajo_contrato_true(client):
    con_id, sin_id = _setup(client)
    ids = [e["id"] for e in client.get("/api/equipos?bajo_contrato=true").json()]
    assert con_id in ids and sin_id not in ids


def test_filtro_bajo_contrato_false(client):
    con_id, sin_id = _setup(client)
    ids = [e["id"] for e in client.get("/api/equipos?bajo_contrato=false").json()]
    assert sin_id in ids and con_id not in ids
