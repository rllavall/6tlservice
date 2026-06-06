from datetime import date, datetime

from app import incidencias_service as svc
from app import models


def _inc(db, estado="abierta"):
    p = models.Producto(part_number="6TL-TS", tipo="equipo", descripcion="B")
    db.add(p); db.flush()
    eq = models.Equipo(numero_serie="TS1", producto_id=p.id)
    db.add(eq); db.flush()
    inc = models.Incidencia(codigo="RMA-1", tipo="rma", estado=estado, equipo_id=eq.id,
        titulo="t", descripcion_problema="d", prioridad="media", fecha_apertura=date(2026, 6, 1))
    db.add(inc); db.flush()
    return inc


def test_creada_en_se_rellena_sola(db_session):
    inc = _inc(db_session)
    assert isinstance(inc.creada_en, datetime)
    assert inc.respondida_en is None and inc.resuelta_en is None


def test_respondida_en_al_diagnosticar(db_session):
    inc = _inc(db_session)
    svc.transicionar(db_session, inc, "diagnostico", None)
    assert isinstance(inc.respondida_en, datetime)


def test_respondida_en_no_se_pisa(db_session):
    inc = _inc(db_session)
    svc.transicionar(db_session, inc, "diagnostico", None)
    primera = inc.respondida_en
    svc.transicionar(db_session, inc, "en_reparacion", None)
    assert inc.respondida_en == primera


def test_resuelta_en_y_reabrir_la_borra(db_session):
    inc = _inc(db_session, estado="en_reparacion")
    inc.resolucion = "arreglado"
    svc.transicionar(db_session, inc, "resuelta", None)
    assert isinstance(inc.resuelta_en, datetime)
    svc.transicionar(db_session, inc, "en_reparacion", None)
    assert inc.resuelta_en is None
