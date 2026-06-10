# tests/test_garantia_fabricante_api.py
def _crea_componente(client):
    fab = client.post("/api/fabricantes", json={"nombre": "National", "email_service": "svc@ni.com"}).json()
    prod = client.post("/api/productos", json={
        "part_number": "PN-DMM", "tipo": "componente", "descripcion": "DMM",
        "fabricante_id": fab["id"], "meses_garantia_default": 24,
    }).json()
    comp = client.post("/api/componentes", json={
        "numero_serie": "SN-1", "producto_id": prod["id"],
    }).json()
    return comp["id"], fab["id"]


def test_activar_confirmar_y_pendientes(client):
    comp_id, _ = _crea_componente(client)

    r = client.post(f"/api/componentes/{comp_id}/garantia/activar",
                    json={"responsable": "Galarzo"})
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "pendiente_activacion"

    r = client.get("/api/garantias/pendientes")
    assert r.status_code == 200
    assert any(g["componente_id"] == comp_id for g in r.json())

    r = client.post(f"/api/componentes/{comp_id}/garantia/confirmar",
                    json={"fecha_activacion": "2026-06-05", "referencia": "NI-9"})
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "activada"
    assert body["fecha_fin"] == "2028-06-05"

    # tras confirmar ya no aparece en pendientes
    r = client.get("/api/garantias/pendientes")
    assert not any(g["componente_id"] == comp_id for g in r.json())


def test_confirmar_sin_activar_da_404(client):
    comp_id, _ = _crea_componente(client)
    r = client.post(f"/api/componentes/{comp_id}/garantia/confirmar",
                    json={"fecha_activacion": "2026-06-05"})
    assert r.status_code == 404
