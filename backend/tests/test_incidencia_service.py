from datetime import date

import pytest

from app import incidencias_service as svc
from app import models


def _nueva(db, **kw):
    inc = models.Incidencia(
        codigo=svc.generar_codigo(db),
        titulo="t", descripcion_problema="d", prioridad="media",
        estado="abierta", fecha_apertura=date(2026, 6, 1), **kw,
    )
    db.add(inc)
    db.flush()
    return inc


def test_generar_codigo_secuencial(db_session):
    assert svc.generar_codigo(db_session) == "RMA-0001"
    _nueva(db_session, equipo_id=None, componente_id=None)
    assert svc.generar_codigo(db_session) == "RMA-0002"


def test_transicion_lineal_sella_fecha(db_session):
    inc = _nueva(db_session, equipo_id=None, componente_id=None)
    svc.transicionar(db_session, inc, "diagnostico", date(2026, 6, 2))
    assert inc.estado == "diagnostico"
    assert inc.fecha_diagnostico == date(2026, 6, 2)


def test_salto_prohibido(db_session):
    inc = _nueva(db_session, equipo_id=None, componente_id=None)
    with pytest.raises(svc.IncidenciaError):
        svc.transicionar(db_session, inc, "resuelta", date(2026, 6, 2))


def test_resuelta_exige_resolucion(db_session):
    inc = _nueva(db_session, equipo_id=None, componente_id=None)
    svc.transicionar(db_session, inc, "diagnostico", date(2026, 6, 2))
    svc.transicionar(db_session, inc, "en_reparacion", date(2026, 6, 3))
    with pytest.raises(svc.IncidenciaError):
        svc.transicionar(db_session, inc, "resuelta", date(2026, 6, 4))
    inc.resolucion = "Sustituida fuente"
    svc.transicionar(db_session, inc, "resuelta", date(2026, 6, 4))
    assert inc.estado == "resuelta"
    assert inc.fecha_resolucion == date(2026, 6, 4)


def test_reabrir_limpia_fechas_conserva_inicio(db_session):
    inc = _nueva(db_session, equipo_id=None, componente_id=None)
    svc.transicionar(db_session, inc, "diagnostico", date(2026, 6, 2))
    svc.transicionar(db_session, inc, "en_reparacion", date(2026, 6, 3))
    inc.resolucion = "ok"
    svc.transicionar(db_session, inc, "resuelta", date(2026, 6, 4))
    svc.transicionar(db_session, inc, "cerrada", date(2026, 6, 5))
    svc.transicionar(db_session, inc, "en_reparacion", date(2026, 6, 10))
    assert inc.estado == "en_reparacion"
    assert inc.fecha_resolucion is None
    assert inc.fecha_cierre is None
    assert inc.fecha_inicio_reparacion == date(2026, 6, 3)
