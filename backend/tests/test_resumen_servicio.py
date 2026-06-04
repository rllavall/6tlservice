from datetime import date

from app import analitica_incidencias as ana
from app import models


def _inc(db, codigo, tipo="rma", prioridad="media", estado="abierta",
         apertura=date(2026, 6, 1), cierre=None):
    i = models.Incidencia(
        codigo=codigo, tipo=tipo, prioridad=prioridad, estado=estado,
        titulo="t", descripcion_problema="d", fecha_apertura=apertura, fecha_cierre=cierre,
    )
    db.add(i); db.flush()
    return i


def _seed(db):
    _inc(db, "RMA-0001", tipo="rma", prioridad="alta", estado="abierta")
    _inc(db, "RMA-0002", tipo="rma", prioridad="media", estado="en_reparacion")
    _inc(db, "CAL-0001", tipo="calibracion", prioridad="media", estado="diagnostico")
    # cerrada dentro de los 30 dias (hoy=2026-06-05 -> inicio 2026-05-06): 10 dias
    _inc(db, "RMA-0003", tipo="rma", estado="cerrada", apertura=date(2026, 5, 20), cierre=date(2026, 5, 30))
    # cerrada dentro de los 30 dias: 20 dias
    _inc(db, "ST-0001", tipo="soporte_tecnico", estado="cerrada", apertura=date(2026, 5, 15), cierre=date(2026, 6, 4))
    # cerrada FUERA de los 30 dias (cierre 2026-04-20 < 2026-05-06) -> excluida
    _inc(db, "RMA-0004", tipo="rma", estado="cerrada", apertura=date(2026, 4, 1), cierre=date(2026, 4, 20))


def test_resumen_cuenta_abiertas_rma_reparacion(db_session):
    _seed(db_session)
    r = ana.resumen_servicio(db_session, hoy=date(2026, 6, 5))
    assert r.incidencias_abiertas == 3        # RMA-0001, RMA-0002, CAL-0001
    assert r.incidencias_abiertas_alta == 1   # RMA-0001
    assert r.rma_abierto == 2                  # RMA-0001, RMA-0002 (las rma cerradas no cuentan)
    assert r.en_reparacion == 1                # RMA-0002


def test_resumen_tiempo_medio_cierre_30d(db_session):
    _seed(db_session)
    r = ana.resumen_servicio(db_session, hoy=date(2026, 6, 5))
    assert r.cerradas_30d == 2                  # RMA-0003 (10d) + ST-0001 (20d); RMA-0004 excluida
    assert r.tiempo_medio_cierre_dias == 15.0   # (10 + 20) / 2


def test_resumen_vacio(db_session):
    r = ana.resumen_servicio(db_session, hoy=date(2026, 6, 5))
    assert r.incidencias_abiertas == 0
    assert r.rma_abierto == 0
    assert r.en_reparacion == 0
    assert r.cerradas_30d == 0
    assert r.tiempo_medio_cierre_dias is None
