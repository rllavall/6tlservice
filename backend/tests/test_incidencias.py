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


def test_filtro_abiertas_excluye_solo_cerrada(client):
    """abiertas=true must include non-cerrada states (e.g. diagnostico) and exclude cerrada."""
    p = client.post("/api/productos", json={"part_number": "PN-ABC", "tipo": "equipo", "descripcion": "Eq2"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S99", "producto_id": p["id"]}).json()

    # Incidencia 1: advance to 'diagnostico' (non-cerrada → must appear in abiertas=true)
    r1 = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "diag", "descripcion_problema": "x", "fecha_apertura": "2026-06-01",
    })
    assert r1.status_code == 201
    id1 = r1.json()["id"]
    t = client.post(f"/api/incidencias/{id1}/transicion", json={"nuevo_estado": "diagnostico"})
    assert t.status_code == 200
    assert t.json()["estado"] == "diagnostico"

    # Incidencia 2: advance all the way to 'cerrada' (must NOT appear in abiertas=true)
    r2 = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "cerrada", "descripcion_problema": "x", "fecha_apertura": "2026-06-01",
    })
    assert r2.status_code == 201
    id2 = r2.json()["id"]
    client.post(f"/api/incidencias/{id2}/transicion", json={"nuevo_estado": "diagnostico"})
    client.post(f"/api/incidencias/{id2}/transicion", json={"nuevo_estado": "en_reparacion"})
    # resolucion must be non-empty before transitioning to resuelta
    client.patch(f"/api/incidencias/{id2}", json={"resolucion": "Reparado OK"})
    client.post(f"/api/incidencias/{id2}/transicion", json={"nuevo_estado": "resuelta"})
    t2 = client.post(f"/api/incidencias/{id2}/transicion", json={"nuevo_estado": "cerrada"})
    assert t2.status_code == 200
    assert t2.json()["estado"] == "cerrada"

    # abiertas=true must return exactly the diagnostico incidencia, not the cerrada one
    items = client.get("/api/incidencias?abiertas=true").json()
    ids = [i["id"] for i in items]
    assert id1 in ids, "diagnostico incidencia must appear with abiertas=true"
    assert id2 not in ids, "cerrada incidencia must NOT appear with abiertas=true"
    assert any(i["estado"] == "diagnostico" for i in items if i["id"] == id1)


def test_incidencia_create_acepta_tipo_y_lo_devuelve(client):
    p = client.post("/api/productos", json={"part_number": "PN-I", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-I", "producto_id": p["id"]}).json()
    r = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "Cal anual", "descripcion_problema": "x",
        "tipo": "calibracion", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 201, r.text
    assert r.json()["tipo"] == "calibracion"


def test_rma_autodetecta_en_garantia(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-W", "tipo": "equipo", "descripcion": "d", "meses_garantia_default": 24,
    }).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN-W", "producto_id": p["id"], "fecha_entrega": "2025-06-01",
    }).json()
    r = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "Fallo", "descripcion_problema": "x",
        "tipo": "rma", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 201, r.text
    assert r.json()["en_garantia"] is True
    assert r.json()["codigo"].startswith("RMA-")


def test_rma_en_garantia_override_manual(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-W2", "tipo": "equipo", "descripcion": "d", "meses_garantia_default": 24,
    }).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN-W2", "producto_id": p["id"], "fecha_entrega": "2025-06-01",
    }).json()
    r = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "Fallo", "descripcion_problema": "x",
        "tipo": "rma", "en_garantia": False, "fecha_apertura": "2026-06-01",
    })
    assert r.json()["en_garantia"] is False  # respeta el override


def test_rma_solo_componente_deja_en_garantia_none(client):
    # RMA contra solo un componente (sin equipo): no hay equipo del que deducir
    # la garantia, asi que en_garantia queda None (comportamiento deliberado).
    pc = client.post("/api/productos", json={"part_number": "PN-C", "tipo": "componente", "descripcion": "d"}).json()
    comp = client.post("/api/componentes", json={"numero_serie": "CMP-1", "producto_id": pc["id"]}).json()
    r = client.post("/api/incidencias", json={
        "componente_id": comp["id"], "titulo": "Fallo comp", "descripcion_problema": "x",
        "tipo": "rma", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 201, r.text
    assert r.json()["en_garantia"] is None


def test_filtro_por_tipo(client):
    p = client.post("/api/productos", json={"part_number": "PN-F", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-F", "producto_id": p["id"]}).json()
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "a", "descripcion_problema": "x", "tipo": "rma", "fecha_apertura": "2026-06-01"})
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "b", "descripcion_problema": "x", "tipo": "calibracion", "fecha_apertura": "2026-06-01"})
    r = client.get("/api/incidencias?tipo=calibracion")
    assert r.status_code == 200
    assert [i["tipo"] for i in r.json()] == ["calibracion"]
