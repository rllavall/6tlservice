from datetime import date

from app import models


def _prod(db, pn="P-MAN", fab="Keysight", pnf="KS-9"):
    p = models.Producto(part_number=pn, tipo="componente", descripcion=pn,
                        fabricante=fab, pn_fabricante=pnf)
    db.add(p); db.commit(); db.refresh(p)
    return p


def test_patch_ciclo_vida_manual_fija_estado(client, db_session):
    p = _prod(db_session)
    r = client.patch(f"/api/productos/{p.id}/ciclo-vida",
                     json={"estado": "obsoleto", "nota": "EOL confirmado por distribuidor"})
    assert r.status_code == 200
    body = r.json()
    assert body["estado_ciclo_vida"] == "obsoleto"
    assert body["ciclo_vida_origen"] == "manual"
    assert body["ciclo_vida_cita"] == "EOL confirmado por distribuidor"


def test_patch_ciclo_vida_manual_producto_inexistente_404(client):
    r = client.patch("/api/productos/999999/ciclo-vida", json={"estado": "activo"})
    assert r.status_code == 404


def test_patch_ciclo_vida_manual_estado_invalido_422(client, db_session):
    p = _prod(db_session, pn="P-MAN2", pnf="KS-10")
    r = client.patch(f"/api/productos/{p.id}/ciclo-vida", json={"estado": "kaput"})
    assert r.status_code == 422
