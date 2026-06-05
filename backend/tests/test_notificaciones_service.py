from datetime import date
from types import SimpleNamespace

from app import models, notificaciones_service


def _equipo_contrato_vencido_preventivo(db):
    p = models.Producto(part_number="6TL-N", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    con = models.ContratoMantenimiento(codigo="CTR-N", nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1))
    db.add(con); db.flush()
    eq = models.Equipo(numero_serie="N1", producto_id=p.id, contrato_id=con.id)
    db.add(eq); db.flush()
    inc = models.Incidencia(codigo="RMA-9", tipo="rma", estado="abierta", equipo_id=eq.id,
        titulo="t", descripcion_problema="d", prioridad="media", fecha_apertura=date(2020, 1, 1))
    db.add(inc); db.flush()
    return eq, inc


def test_construir_digest_cuenta(db_session):
    _equipo_contrato_vencido_preventivo(db_session)
    d = notificaciones_service.construir_digest(db_session, date(2026, 6, 6))
    assert d["resumen"]["preventivos_vencidos"] >= 1
    assert d["resumen"]["sla_incumplidas"] >= 1
    assert d["total"] >= 2
    assert "Resumen" in d["asunto"] or "resumen" in d["asunto"].lower()
    assert isinstance(d["cuerpo"], str) and len(d["cuerpo"]) > 0


def test_notificar_incidencia_compone_mensaje():
    inc = SimpleNamespace(codigo="RMA-1", tipo="rma", titulo="No arranca", estado="en_reparacion", prioridad="alta")
    capt = {}
    def fake(asunto, cuerpo):
        capt["asunto"] = asunto; capt["cuerpo"] = cuerpo
        return {"email": None, "telegram": None}
    notificaciones_service.notificar_incidencia(inc, "en_reparacion", notificar_fn=fake)
    assert "RMA-1" in capt["asunto"]
    assert "en_reparacion" in capt["cuerpo"]


def test_enviar_digest_invoca_notificar(db_session):
    capt = {}
    def fake(asunto, cuerpo):
        capt["llamado"] = True
        return {"email": True, "telegram": None}
    r = notificaciones_service.enviar_digest(db_session, date(2026, 6, 6), notificar_fn=fake)
    assert capt.get("llamado") is True
    assert r["canales"] == {"email": True, "telegram": None}
