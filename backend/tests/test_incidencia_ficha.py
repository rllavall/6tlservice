from __future__ import annotations


def _seed(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    cli = client.post("/api/clientes", json={"nombre": "ACME"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": p["id"], "cliente_id": cli["id"]}).json()
    return p, cli, eq


def test_ficha_compone_snapshot(client):
    _p, cli, eq = _seed(client)
    inc = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01",
    }).json()
    r = client.get(f"/api/incidencias/{inc['id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["incidencia"]["codigo"] == "RMA-0001"
    assert body["equipo"]["id"] == eq["id"]
    assert body["cliente"]["nombre"] == "ACME"
    assert body["componente"] is None
    assert body["cambios_configuracion"] == []
    assert body["movimientos"] == []


def test_ficha_404(client):
    assert client.get("/api/incidencias/999").status_code == 404
