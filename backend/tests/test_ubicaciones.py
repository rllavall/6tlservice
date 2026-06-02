def test_ubicacion_crud(client):
    r = client.post("/api/ubicaciones", json={"nombre": "Indra Madrid", "tipo": "fabrica_cliente", "pais": "España"})
    assert r.status_code == 201, r.text
    uid = r.json()["id"]

    r = client.get("/api/ubicaciones")
    assert r.status_code == 200
    assert any(u["id"] == uid for u in r.json())

    r = client.put(f"/api/ubicaciones/{uid}", json={"nombre": "Indra Madrid 2", "tipo": "fabrica_cliente"})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Indra Madrid 2"

    r = client.delete(f"/api/ubicaciones/{uid}")
    assert r.status_code == 204

    r = client.get(f"/api/ubicaciones/{uid}")
    assert r.status_code == 404


def test_ubicacion_invalid_tipo_422(client):
    r = client.post("/api/ubicaciones", json={"nombre": "x", "tipo": "marte"})
    assert r.status_code == 422
