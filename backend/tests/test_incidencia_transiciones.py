def _inc(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": p["id"]}).json()
    return client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01",
    }).json()


def test_patch_campos_libres(client):
    inc = _inc(client)
    r = client.patch(f"/api/incidencias/{inc['id']}", json={"asignado_a": "Cim", "prioridad": "alta"})
    assert r.status_code == 200, r.text
    assert r.json()["asignado_a"] == "Cim"
    assert r.json()["prioridad"] == "alta"


def test_transicion_lineal_y_fechas(client):
    inc = _inc(client)
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "diagnostico", "fecha": "2026-06-02"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "diagnostico"
    assert r.json()["fecha_diagnostico"] == "2026-06-02"


def test_transicion_salto_409(client):
    inc = _inc(client)
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "resuelta"})
    assert r.status_code == 409


def test_transicion_resuelta_exige_resolucion(client):
    inc = _inc(client)
    client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "diagnostico"})
    client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "en_reparacion"})
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "resuelta"})
    assert r.status_code == 409
    client.patch(f"/api/incidencias/{inc['id']}", json={"resolucion": "Sustituida fuente"})
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "resuelta", "fecha": "2026-06-04"})
    assert r.status_code == 200
    assert r.json()["fecha_resolucion"] == "2026-06-04"


def test_delete_guarded(client):
    inc = _inc(client)
    assert client.delete(f"/api/incidencias/{inc['id']}").status_code == 204
    assert client.delete(f"/api/incidencias/{inc['id']}").status_code == 404


def test_delete_no_abierta_409(client):
    inc = _inc(client)
    client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "diagnostico"})
    assert client.delete(f"/api/incidencias/{inc['id']}").status_code == 409
