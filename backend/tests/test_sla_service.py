from datetime import date, datetime

from app import models, sla_service


def _equipo_con_contrato(db, nivel="gold", vigente=True):
    p = models.Producto(part_number="6TL-SLA", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    fin = date(2100, 1, 1) if vigente else date(2021, 1, 1)
    con = models.ContratoMantenimiento(codigo="CTR-S1", nivel=nivel,
        fecha_inicio=date(2020, 1, 1), fecha_fin=fin)
    db.add(con); db.flush()
    eq = models.Equipo(numero_serie="S1", producto_id=p.id, contrato_id=con.id)
    db.add(eq); db.flush()
    return eq


def _inc(db, equipo_id, apertura, estado="abierta", **fechas):
    kwargs = dict(codigo="RMA-1", tipo="rma", estado=estado, equipo_id=equipo_id,
        titulo="t", descripcion_problema="d", prioridad="media", fecha_apertura=apertura)
    kwargs.update(fechas)
    inc = models.Incidencia(**kwargs)
    db.add(inc); db.flush()
    return inc


def test_incidencia_sin_contrato_sin_sla(db_session):
    p = models.Producto(part_number="6TL-X", tipo="equipo", descripcion="B")
    db_session.add(p); db_session.flush()
    eq = models.Equipo(numero_serie="X", producto_id=p.id)
    db_session.add(eq); db_session.flush()
    inc = _inc(db_session, eq.id, date(2026, 6, 1))
    assert sla_service.sla_de_incidencia(db_session, inc, datetime(2026, 6, 10)) is None


def test_incidencia_abierta_incumplida_aparece(db_session):
    eq = _equipo_con_contrato(db_session, nivel="gold")
    inc = _inc(db_session, eq.id, date(2020, 1, 1))
    out = sla_service.construir_sla(db_session, datetime(2026, 6, 20))
    ids = [i["incidencia"].id for i in out["incumplidas"]]
    assert inc.id in ids
    assert out["resumen"]["incumplidas"] >= 1


def test_cumplimiento_no_none(db_session):
    eq = _equipo_con_contrato(db_session, nivel="gold")
    _inc(db_session, eq.id, date(2020, 1, 1))
    out = sla_service.construir_sla(db_session, datetime(2026, 6, 30))
    assert out["cumplimiento"]["total"] >= 1
    assert out["cumplimiento"]["resolucion_pct"] is not None
