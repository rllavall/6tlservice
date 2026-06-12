# tests/test_obsolescencia_api.py
"""Tests para el router /api/obsolescencia (Task 6)."""


def test_productos_a_revisar_endpoint(client):
    """Producto con fabricante+pn_fabricante expone url_obsolescencia del fabricante."""
    f = client.post("/api/fabricantes", json={
        "nombre": "Keysight", "url_obsolescencia": "https://k/eol"
    })
    assert f.status_code == 201
    fid = f.json()["id"]

    p = client.post("/api/productos", json={
        "part_number": "OBS-A", "tipo": "componente", "descripcion": "Sensor",
        "fabricante": "Keysight", "pn_fabricante": "ABC", "fabricante_id": fid,
    })
    assert p.status_code == 201

    r = client.get("/api/obsolescencia/productos-a-revisar")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["pn_fabricante"] == "ABC"
    assert data[0]["url_obsolescencia"] == "https://k/eol"


def test_post_hallazgos_y_resumen(client):
    """POST /hallazgos registra un hallazgo; GET / devuelve conteos+noticias."""
    p = client.post("/api/productos", json={
        "part_number": "OBS-B", "tipo": "componente", "descripcion": "Chip",
        "fabricante": "NI", "pn_fabricante": "DEF",
    })
    assert p.status_code == 201
    pid = p.json()["id"]

    r = client.post("/api/obsolescencia/hallazgos", json=[
        {"producto_id": pid, "estado": "obsoleto", "url": "https://x", "resumen": "EOL"}
    ])
    assert r.status_code == 200
    assert r.json()["cambios"] == 1

    r2 = client.get("/api/obsolescencia")
    assert r2.status_code == 200
    body = r2.json()
    assert body["conteos"]["obsoleto"] == 1
    assert len(body["noticias"]) == 1


def test_hallazgo_estado_invalido_422(client):
    """Estado desconocido -> 422 (validación Pydantic, sin tocar el servicio)."""
    r = client.post("/api/obsolescencia/hallazgos", json=[
        {"producto_id": 1, "estado": "zzz"}
    ])
    assert r.status_code == 422


def test_obsolescencia_protegido_401(client_sin_auth):
    """Los tres endpoints requieren autenticación."""
    assert client_sin_auth.get("/api/obsolescencia").status_code == 401
    assert client_sin_auth.get("/api/obsolescencia/productos-a-revisar").status_code == 401
    assert client_sin_auth.post("/api/obsolescencia/hallazgos", json=[]).status_code == 401
