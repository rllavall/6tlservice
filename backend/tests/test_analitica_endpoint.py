def test_endpoint_vacio(client):
    r = client.get("/api/analitica/incidencias")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 0
    assert body["kpis_tiempo"]["mttr_dias"] is None
    assert body["garantia"]["rma_en_garantia"] == 0


def test_endpoint_con_datos_y_filtro(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-E", "tipo": "equipo", "descripcion": "Eq E", "meses_garantia_default": 24,
    }).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN-E", "producto_id": p["id"], "fecha_entrega": "2025-06-01",
    }).json()
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "a",
        "descripcion_problema": "x", "tipo": "rma", "fecha_apertura": "2026-06-01"})
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "b",
        "descripcion_problema": "x", "tipo": "calibracion", "fecha_apertura": "2026-06-01"})
    r = client.get("/api/analitica/incidencias")
    assert r.json()["total"] == 2
    r2 = client.get("/api/analitica/incidencias?tipo=rma")
    assert r2.json()["total"] == 1
    assert {c["clave"]: c["valor"] for c in r2.json()["por_tipo"]} == {"rma": 1}
