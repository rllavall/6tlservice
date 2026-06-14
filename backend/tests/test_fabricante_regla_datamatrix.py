def test_crear_fabricante_con_regla(client):
    resp = client.post("/api/fabricantes", json={"nombre": "ACME-DM", "regla_datamatrix": r"^(?P<sn>\d+)$"})
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["regla_datamatrix"] == r"^(?P<sn>\d+)$"
