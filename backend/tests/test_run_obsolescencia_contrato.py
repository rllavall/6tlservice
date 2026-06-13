"""ejecutar() no debe llamar a registrar_hallazgo cuando consultar devuelve estado=None
(el nuevo contrato de consultar_fabricante devuelve siempre dict, con estado=None en
'sin respuesta'). El guard `if not v.get("estado")` lo evita aguas arriba."""
from datetime import date

import run_obsolescencia as ro
from app import models, obsolescencia_service


def _seed(db):
    p = models.Producto(part_number="P1", tipo="componente", descripcion="x",
                        fabricante="Beta", pn_fabricante="B1", estado_ciclo_vida="activo")
    db.add(p); db.commit()
    return p.id


def test_ejecutar_no_registra_cuando_consultar_no_da_estado(db_session, monkeypatch):
    _seed(db_session)

    def fake(p, url, **kw):
        return {"estado": None, "tokens_total": 500, "estado_consulta": "no_encontrado"}

    llamadas = []
    revisados = []
    monkeypatch.setattr(obsolescencia_service, "registrar_hallazgo",
                        lambda *a, **k: llamadas.append(a) or {"cambio": False})
    monkeypatch.setattr(obsolescencia_service, "marcar_revisado",
                        lambda *a, **k: revisados.append(a) or True)
    monkeypatch.setattr(obsolescencia_service, "productos_a_revisar",
                        lambda db, hoy, limite=20: db.query(models.Producto).all())
    monkeypatch.setattr(obsolescencia_service, "enviar_informe",
                        lambda *a, **k: {"enviado": False, "total": 0, "canales": []})

    ro.ejecutar(db_session, date(2026, 6, 13), consultar=fake,
                notificar_fn=lambda *a, **k: {"enviado": False, "canales": []})

    assert llamadas == []        # con estado=None el guard evita registrar_hallazgo
    assert len(revisados) == 1   # pero sí se sella verificado_en (no_encontrado)


def test_ejecutar_si_registra_cuando_hay_estado(db_session, monkeypatch):
    _seed(db_session)

    def fake(p, url, **kw):
        return {"estado": "obsoleto", "fecha_evento": None, "url_fuente": None,
                "resumen": "x", "tokens_total": 10, "estado_consulta": "ok"}

    llamadas = []
    monkeypatch.setattr(obsolescencia_service, "registrar_hallazgo",
                        lambda *a, **k: llamadas.append(a) or {"cambio": True})
    monkeypatch.setattr(obsolescencia_service, "productos_a_revisar",
                        lambda db, hoy, limite=20: db.query(models.Producto).all())
    monkeypatch.setattr(obsolescencia_service, "enviar_informe",
                        lambda *a, **k: {"enviado": False, "total": 0, "canales": []})

    ro.ejecutar(db_session, date(2026, 6, 13), consultar=fake,
                notificar_fn=lambda *a, **k: {"enviado": False, "canales": []})

    assert len(llamadas) == 1  # con estado válido SÍ se registra
