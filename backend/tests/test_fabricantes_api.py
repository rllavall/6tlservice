# tests/test_fabricantes_api.py
def test_crud_fabricante(client):
    r = client.post("/api/fabricantes", json={"nombre": "National", "email_service": "svc@ni.com"})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]

    r = client.get("/api/fabricantes")
    assert r.status_code == 200
    assert any(f["id"] == fid for f in r.json())

    r = client.put(f"/api/fabricantes/{fid}", json={"requiere_activacion_web": True})
    assert r.status_code == 200
    assert r.json()["requiere_activacion_web"] is True

    r = client.delete(f"/api/fabricantes/{fid}")
    assert r.status_code == 204
    assert client.get(f"/api/fabricantes/{fid}").status_code == 404


def test_nombre_duplicado_da_409(client):
    client.post("/api/fabricantes", json={"nombre": "Keysight"})
    r = client.post("/api/fabricantes", json={"nombre": "Keysight"})
    assert r.status_code == 409
