from __future__ import annotations


def _equipo_con_contrato(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQA", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": "gold", "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "P1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    return eq["id"]


def test_crear_y_listar_preventivo(client):
    eid = _equipo_con_contrato(client)
    r = client.post(f"/api/equipos/{eid}/preventivos", json={
        "fecha": "2026-06-05", "tipo": "on_site", "veredicto": "ok", "tecnico": "Cim"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["proxima_fecha"] == "2026-12-05"   # gold = semestral
    lista = client.get(f"/api/equipos/{eid}/preventivos").json()
    assert len(lista) == 1 and lista[0]["veredicto"] == "ok"


def test_generar_incidencia_desde_preventivo(client):
    eid = _equipo_con_contrato(client)
    a = client.post(f"/api/equipos/{eid}/preventivos", json={
        "fecha": "2026-06-05", "tipo": "on_site", "veredicto": "requiere_accion",
        "informe": "fuga"}).json()
    r = client.post(f"/api/preventivos/{a['id']}/generar-incidencia", json={
        "tipo": "soporte_tecnico", "prioridad": "alta"})
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "abierta"
    r2 = client.post(f"/api/preventivos/{a['id']}/generar-incidencia", json={
        "tipo": "soporte_tecnico", "prioridad": "alta"})
    assert r2.status_code == 409


def test_preventivo_protegido_401(client_sin_auth):
    assert client_sin_auth.get("/api/equipos/1/preventivos").status_code == 401
