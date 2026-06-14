from app import models


def _banco(db):
    p_eq = models.Producto(part_number="BANCO-1", tipo="equipo", descripcion="Banco")
    db.add(p_eq); db.flush()
    eq = models.Equipo(numero_serie="EQ-1", producto_id=p_eq.id)
    db.add(eq); db.flush()
    p_comp = models.Producto(part_number="COMP-1", tipo="componente", descripcion="Comp",
                             pn_fabricante="PN-A")
    db.add(p_comp); db.flush()
    comp = models.Componente(numero_serie="S/N pendiente (1.1)", producto_id=p_comp.id,
                             equipo_id=eq.id, posicion="1.1")
    db.add(comp); db.commit()
    return eq.id, comp.id


def test_escaneo_asignado_200(client, db_session):
    eq_id, comp_id = _banco(db_session)
    resp = client.post(f"/api/equipos/{eq_id}/escaneo", json={"raw": "240PN-A\x1d21SER-99"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["estado"] == "asignado"
    assert body["componente_id"] == comp_id
    assert body["sn"] == "SER-99"


def test_escaneo_equipo_inexistente_404(client):
    resp = client.post("/api/equipos/99999/escaneo", json={"raw": "240PN-A\x1d21SER-99"})
    assert resp.status_code == 404


def test_escaneo_raw_vacio_422(client, db_session):
    eq_id, _ = _banco(db_session)
    resp = client.post(f"/api/equipos/{eq_id}/escaneo", json={"raw": "   "})
    assert resp.status_code == 422
