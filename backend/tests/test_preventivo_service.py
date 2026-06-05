from datetime import date

import pytest

from app import models
from app import preventivo_service as svc


def _equipo(db, contrato_id=None):
    p = models.Producto(part_number="6TL-EQS", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    eq = models.Equipo(numero_serie="SN1", producto_id=p.id, contrato_id=contrato_id)
    db.add(eq); db.flush()
    return eq


def _contrato(db, nivel="bronze"):
    c = models.ContratoMantenimiento(
        codigo="CTR-0001", nivel=nivel,
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db.add(c); db.flush()
    return c


def test_crear_autoasocia_contrato_vigente_y_sugiere_proxima(db_session):
    con = _contrato(db_session, "bronze")  # preventivo anual
    eq = _equipo(db_session, contrato_id=con.id)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="on_site",
                  veredicto="ok", tecnico="Cim", informe=None, proxima_fecha=None)
    assert a.contrato_id == con.id
    assert a.proxima_fecha == date(2027, 6, 5)   # +12 meses (bronze)


def test_crear_sin_contrato_proxima_vacia(db_session):
    eq = _equipo(db_session, contrato_id=None)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="remoto",
                  veredicto="ok", tecnico=None, informe=None, proxima_fecha=None)
    assert a.contrato_id is None
    assert a.proxima_fecha is None


def test_crear_respeta_proxima_explicita(db_session):
    con = _contrato(db_session)
    eq = _equipo(db_session, contrato_id=con.id)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="on_site",
                  veredicto="ok", tecnico=None, informe=None, proxima_fecha=date(2026, 9, 1))
    assert a.proxima_fecha == date(2026, 9, 1)


def test_generar_incidencia_enlaza(db_session):
    eq = _equipo(db_session)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="on_site",
                  veredicto="requiere_accion", tecnico=None, informe="ruido", proxima_fecha=None)
    inc = svc.generar_incidencia(db_session, a, tipo="soporte_tecnico", prioridad="alta", asignado_a="Cim")
    assert inc.equipo_id == eq.id
    assert inc.estado == "abierta"
    assert a.incidencia_id == inc.id


def test_generar_incidencia_doble_falla(db_session):
    eq = _equipo(db_session)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="on_site",
                  veredicto="requiere_accion", tecnico=None, informe=None, proxima_fecha=None)
    svc.generar_incidencia(db_session, a, tipo="soporte_tecnico", prioridad="media", asignado_a=None)
    with pytest.raises(svc.PreventivoError):
        svc.generar_incidencia(db_session, a, tipo="soporte_tecnico", prioridad="media", asignado_a=None)
