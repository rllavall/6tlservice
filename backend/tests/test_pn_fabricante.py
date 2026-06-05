from app import models


def test_producto_pn_fabricante_se_guarda_y_expone(db_session):
    p = models.Producto(
        part_number="6TL-100", tipo="componente", descripcion="Tarjeta RF",
        pn_fabricante="NI-PXIe-5840",
    )
    db_session.add(p); db_session.flush()
    assert p.pn_fabricante == "NI-PXIe-5840"


def test_producto_pn_fabricante_opcional(db_session):
    p = models.Producto(part_number="6TL-101", tipo="componente", descripcion="Cable")
    db_session.add(p); db_session.flush()
    assert p.pn_fabricante is None


def test_alta_producto_con_pn_fabricante_api(client):
    r = client.post("/api/productos", json={
        "part_number": "6TL-200", "tipo": "componente", "descripcion": "Fuente",
        "pn_fabricante": "KEYSIGHT-N6700",
    })
    assert r.status_code == 201, r.text
    assert r.json()["pn_fabricante"] == "KEYSIGHT-N6700"
