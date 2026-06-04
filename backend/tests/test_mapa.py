from __future__ import annotations

from datetime import date


def _crear_producto(client, part_number="PN-1", tipo="equipo"):
    r = client.post("/api/productos", json={"part_number": part_number, "tipo": tipo, "descripcion": "Equipo X"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _crear_ubicacion(client, nombre="Sitio", **extra):
    payload = {"nombre": nombre, "tipo": "fabrica_cliente"}
    payload.update(extra)
    r = client.post("/api/ubicaciones", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _crear_equipo(client, producto_id, numero_serie, **extra):
    payload = {"numero_serie": numero_serie, "producto_id": producto_id}
    payload.update(extra)
    r = client.post("/api/equipos", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _mover(client, equipo_id, ubicacion_id, fecha="2026-01-01", motivo="entrega"):
    r = client.post(
        f"/api/equipos/{equipo_id}/movimientos",
        json={"ubicacion_destino_id": ubicacion_id, "fecha": fecha, "motivo": motivo},
    )
    assert r.status_code == 201, r.text


# --- lat/lon en ubicacion (override manual) ---


def test_ubicacion_acepta_lat_lon_manual(client):
    u = _crear_ubicacion(client, latitud=40.4168, longitud=-3.7038)
    assert u["latitud"] == 40.4168
    assert u["longitud"] == -3.7038


def test_lat_lon_opcionales_por_defecto_null(client):
    u = _crear_ubicacion(client)
    assert u["latitud"] is None
    assert u["longitud"] is None


# --- geocodificación al guardar ---


def test_post_geocodifica_cuando_faltan_coords(client, monkeypatch):
    from app import geocoding

    monkeypatch.setattr(geocoding, "geocode_ubicacion", lambda *a, **k: (40.0, -3.0))
    u = _crear_ubicacion(client, ciudad="Madrid", pais="España")
    assert u["latitud"] == 40.0
    assert u["longitud"] == -3.0


def test_post_no_geocodifica_si_coords_manuales(client, monkeypatch):
    from app import geocoding

    def boom(*a, **k):
        raise AssertionError("no debería geocodificar con coords manuales")

    monkeypatch.setattr(geocoding, "geocode_ubicacion", boom)
    u = _crear_ubicacion(client, ciudad="Madrid", pais="España", latitud=1.0, longitud=2.0)
    assert (u["latitud"], u["longitud"]) == (1.0, 2.0)


def test_post_geocode_falla_no_rompe_guardado(client, monkeypatch):
    from app import geocoding

    monkeypatch.setattr(geocoding, "geocode_ubicacion", lambda *a, **k: None)
    u = _crear_ubicacion(client, ciudad="CiudadInventada", pais="Nowhere")
    assert u["latitud"] is None and u["longitud"] is None


def test_put_geocodifica_si_cambia_direccion_sin_coords(client, monkeypatch):
    from app import geocoding

    monkeypatch.setattr(geocoding, "geocode_ubicacion", lambda *a, **k: None)
    u = _crear_ubicacion(client, nombre="S1")
    monkeypatch.setattr(geocoding, "geocode_ubicacion", lambda *a, **k: (10.0, 20.0))
    r = client.put(f"/api/ubicaciones/{u['id']}", json={"nombre": "S1", "tipo": "fabrica_cliente", "ciudad": "Lisboa", "pais": "Portugal"})
    assert r.status_code == 200, r.text
    assert (r.json()["latitud"], r.json()["longitud"]) == (10.0, 20.0)


# --- endpoint GET /api/mapa/ubicaciones ---


def _crear_cliente(client, nombre="ACME"):
    r = client.post("/api/clientes", json={"nombre": nombre})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_mapa_lista_ubicacion_con_equipo_y_coords(client):
    pid = _crear_producto(client)
    cli = _crear_cliente(client, "Indra")
    u = _crear_ubicacion(client, nombre="Madrid", ciudad="Madrid", pais="España", latitud=40.4, longitud=-3.7, cliente_id=cli)
    e = _crear_equipo(client, pid, "SN-1")
    _mover(client, e, u["id"])

    r = client.get("/api/mapa/ubicaciones")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    item = data[0]
    assert item["ubicacion_id"] == u["id"]
    assert item["ciudad"] == "Madrid"
    assert item["latitud"] == 40.4 and item["longitud"] == -3.7
    assert item["num_equipos"] == 1
    assert item["cliente"] == {"id": cli, "nombre": "Indra"}
    assert item["equipos"][0]["numero_serie"] == "SN-1"
    assert "PN-1" in item["equipos"][0]["producto"]


def test_mapa_excluye_ubicacion_sin_coords(client):
    # sin campos de dirección → geocode_ubicacion devuelve None (sin red) → coords null
    pid = _crear_producto(client)
    u = _crear_ubicacion(client, nombre="SinCoords")
    e = _crear_equipo(client, pid, "SN-2")
    _mover(client, e, u["id"])
    r = client.get("/api/mapa/ubicaciones")
    ids = [i["ubicacion_id"] for i in r.json()]
    assert u["id"] not in ids


def test_mapa_excluye_ubicacion_sin_equipos(client):
    _crear_ubicacion(client, nombre="Vacia", latitud=1.0, longitud=2.0)
    r = client.get("/api/mapa/ubicaciones")
    assert r.json() == []


def test_mapa_ultimo_movimiento_gana(client):
    pid = _crear_producto(client)
    a = _crear_ubicacion(client, nombre="A", latitud=1.0, longitud=1.0)
    b = _crear_ubicacion(client, nombre="B", latitud=2.0, longitud=2.0)
    e = _crear_equipo(client, pid, "SN-3")
    _mover(client, e, a["id"], fecha="2026-01-01")
    _mover(client, e, b["id"], fecha="2026-02-01", motivo="traslado")

    data = {i["ubicacion_id"]: i for i in client.get("/api/mapa/ubicaciones").json()}
    assert a["id"] not in data
    assert data[b["id"]]["num_equipos"] == 1


def test_mapa_excluye_baja_por_defecto_e_incluye_con_flag(client):
    pid = _crear_producto(client)
    u = _crear_ubicacion(client, nombre="U", latitud=1.0, longitud=2.0)
    e = _crear_equipo(client, pid, "SN-4", estado="baja")
    _mover(client, e, u["id"])

    assert client.get("/api/mapa/ubicaciones").json() == []
    con_baja = client.get("/api/mapa/ubicaciones?incluir_baja=true").json()
    assert con_baja[0]["num_equipos"] == 1


def test_mapa_filtra_por_cliente(client):
    pid = _crear_producto(client)
    c1 = _crear_cliente(client, "C1")
    c2 = _crear_cliente(client, "C2")
    u1 = _crear_ubicacion(client, nombre="U1", latitud=1.0, longitud=1.0, cliente_id=c1)
    u2 = _crear_ubicacion(client, nombre="U2", latitud=2.0, longitud=2.0, cliente_id=c2)
    e1 = _crear_equipo(client, pid, "SN-5")
    e2 = _crear_equipo(client, pid, "SN-6")
    _mover(client, e1, u1["id"])
    _mover(client, e2, u2["id"])

    data = client.get(f"/api/mapa/ubicaciones?cliente_id={c1}").json()
    assert [i["ubicacion_id"] for i in data] == [u1["id"]]
