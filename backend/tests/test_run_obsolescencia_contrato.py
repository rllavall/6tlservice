"""ejecutar() no debe registrar hallazgo cuando consultar devuelve estado=None."""
from datetime import date

import run_obsolescencia as ro
from app import models, obsolescencia_service


def _seed(db):
    p = models.Producto(part_number="P1", tipo="componente", descripcion="x",
                        fabricante="Beta", pn_fabricante="B1", estado_ciclo_vida="activo")
    db.add(p); db.commit()
    return p.id


def test_ejecutar_ignora_dict_sin_estado(db_session, monkeypatch):
    pid = _seed(db_session)
    def fake(p, url, **kw):
        return {"estado": None, "tokens_total": 500, "estado_consulta": "sin_respuesta"}
    monkeypatch.setattr(obsolescencia_service, "productos_a_revisar",
                        lambda db, hoy, limite=20: db.query(models.Producto).all())
    ro.ejecutar(db_session, date(2026, 6, 13), consultar=fake,
                notificar_fn=lambda *a, **k: {"enviado": False, "canales": []})
    p = db_session.get(models.Producto, pid)
    assert p.estado_ciclo_vida == "activo"
