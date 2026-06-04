from datetime import date


def test_modelo_avance_defaults(db_session):
    from app import models
    inc = models.Incidencia(
        codigo="RMA-7001", titulo="t", descripcion_problema="d",
        estado="abierta", fecha_apertura=date(2026, 6, 1),
    )
    db_session.add(inc); db_session.flush()
    av = models.AvanceIncidencia(incidencia_id=inc.id, fecha=date(2026, 6, 2), texto="Primer avance")
    db_session.add(av); db_session.flush()
    assert av.tipo == "avance"        # default
    assert av.autor is None
    assert av.texto == "Primer avance"


def _seed_incidencia(client):
    p = client.post("/api/productos", json={"part_number": "PN-AV", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-AV", "producto_id": p["id"]}).json()
    return client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "t", "descripcion_problema": "x", "fecha_apertura": "2026-06-01",
    }).json()


def test_crear_avance(client):
    inc = _seed_incidencia(client)
    r = client.post(f"/api/incidencias/{inc['id']}/avances", json={
        "tipo": "report", "autor": "ana", "texto": "Llamada al cliente", "fecha": "2026-06-03",
    })
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["tipo"] == "report" and b["autor"] == "ana" and b["texto"] == "Llamada al cliente"
    assert b["incidencia_id"] == inc["id"]


def test_crear_avance_fecha_por_defecto_hoy(client):
    from datetime import date
    inc = _seed_incidencia(client)
    r = client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "sin fecha"})
    assert r.status_code == 201, r.text
    assert r.json()["fecha"] == date.today().isoformat()
    assert r.json()["tipo"] == "avance"  # default


def test_crear_avance_texto_vacio_422(client):
    inc = _seed_incidencia(client)
    r = client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": ""})
    assert r.status_code == 422


def test_crear_avance_incidencia_inexistente_404(client):
    r = client.post("/api/incidencias/9999/avances", json={"texto": "x"})
    assert r.status_code == 404


def test_listar_avances_orden_desc(client):
    inc = _seed_incidencia(client)
    client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "viejo", "fecha": "2026-06-01"})
    client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "nuevo", "fecha": "2026-06-05"})
    r = client.get(f"/api/incidencias/{inc['id']}/avances")
    assert r.status_code == 200
    assert [a["texto"] for a in r.json()] == ["nuevo", "viejo"]


def test_editar_avance(client):
    inc = _seed_incidencia(client)
    av = client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "borrador"}).json()
    r = client.patch(f"/api/incidencias/{inc['id']}/avances/{av['id']}", json={"texto": "corregido", "tipo": "visita"})
    assert r.status_code == 200, r.text
    assert r.json()["texto"] == "corregido" and r.json()["tipo"] == "visita"


def test_editar_avance_de_otra_incidencia_404(client):
    inc1 = _seed_incidencia(client)
    eqid = client.get(f"/api/incidencias/{inc1['id']}").json()["incidencia"]["equipo_id"]
    inc2 = client.post("/api/incidencias", json={
        "equipo_id": eqid, "titulo": "t2", "descripcion_problema": "x", "fecha_apertura": "2026-06-01",
    }).json()
    av = client.post(f"/api/incidencias/{inc1['id']}/avances", json={"texto": "de inc1"}).json()
    r = client.patch(f"/api/incidencias/{inc2['id']}/avances/{av['id']}", json={"texto": "hack"})
    assert r.status_code == 404


def test_borrar_avance(client):
    inc = _seed_incidencia(client)
    av = client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "a borrar"}).json()
    r = client.delete(f"/api/incidencias/{inc['id']}/avances/{av['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/incidencias/{inc['id']}/avances").json() == []
    assert client.delete(f"/api/incidencias/{inc['id']}/avances/{av['id']}").status_code == 404
