def _seed_equipo(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    return client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": p["id"]}).json()


def test_crear_incidencia_genera_codigo(client):
    eq = _seed_equipo(client)
    r = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "No arranca",
        "descripcion_problema": "nada", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["codigo"] == "RMA-0001"
    assert body["estado"] == "abierta"


def test_crear_sin_sujeto_422(client):
    r = client.post("/api/incidencias", json={
        "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 422


def test_crear_equipo_inexistente_404(client):
    r = client.post("/api/incidencias", json={
        "equipo_id": 999, "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 404


def test_listar_y_filtros(client):
    eq = _seed_equipo(client)
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "a", "descripcion_problema": "y", "fecha_apertura": "2026-06-01", "prioridad": "alta"})
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "b", "descripcion_problema": "y", "fecha_apertura": "2026-06-02", "prioridad": "baja"})
    assert len(client.get("/api/incidencias").json()) == 2
    assert len(client.get("/api/incidencias?prioridad=alta").json()) == 1
    assert len(client.get(f"/api/incidencias?equipo_id={eq['id']}").json()) == 2
    assert len(client.get("/api/incidencias?estado=abierta").json()) == 2
    assert len(client.get("/api/incidencias?abiertas=true").json()) == 2
