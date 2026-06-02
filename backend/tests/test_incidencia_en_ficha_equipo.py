def test_ficha_equipo_lista_incidencias(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": p["id"]}).json()
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "a", "descripcion_problema": "y", "fecha_apertura": "2026-06-01"})
    ficha = client.get(f"/api/equipos/{eq['id']}").json()
    assert "incidencias" in ficha
    assert len(ficha["incidencias"]) == 1
    assert ficha["incidencias"][0]["codigo"] == "RMA-0001"


def test_ficha_equipo_sin_incidencias_vacia(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ2", "tipo": "equipo", "descripcion": "Eq"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S2", "producto_id": p["id"]}).json()
    ficha = client.get(f"/api/equipos/{eq['id']}").json()
    assert ficha["incidencias"] == []
