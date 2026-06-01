from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import models


def test_incidencia_table_and_fields(db_session):
    inc = models.Incidencia(
        codigo="RMA-0001",
        equipo_id=None,
        componente_id=None,
        titulo="No arranca",
        descripcion_problema="El equipo no enciende",
        prioridad="media",
        estado="abierta",
        fecha_apertura=date(2026, 6, 1),
    )
    db_session.add(inc)
    db_session.flush()
    assert inc.id is not None
    assert inc.estado == "abierta"
    assert inc.asignado_a is None
    assert inc.en_garantia is None
    assert inc.fecha_cierre is None


def test_enlace_incidencia_id_en_eventos(db_session):
    cc = models.CambioConfiguracion(
        componente_id=1, equipo_id=1, accion="montaje",
        fecha=date(2026, 6, 1), motivo="reparacion", incidencia_id=None,
    )
    mv = models.Movimiento(
        equipo_id=1, ubicacion_destino_id=1, fecha=date(2026, 6, 1),
        motivo="reparacion", incidencia_id=None,
    )
    db_session.add_all([cc, mv])
    db_session.flush()
    assert cc.incidencia_id is None
    assert mv.incidencia_id is None


def test_constantes_incidencia():
    assert models.ESTADOS_INCIDENCIA == [
        "abierta", "diagnostico", "en_reparacion", "resuelta", "cerrada",
    ]
    assert models.PRIORIDADES_INCIDENCIA == ["baja", "media", "alta"]


def test_fk_linkage_movimiento_y_cambio(db_session):
    inc = models.Incidencia(
        codigo="RMA-FK-001",
        titulo="FK test",
        descripcion_problema="Verifica FK real",
        estado="abierta",
        fecha_apertura=date(2026, 6, 1),
    )
    db_session.add(inc)
    db_session.flush()

    mv = models.Movimiento(
        equipo_id=1, ubicacion_destino_id=1, fecha=date(2026, 6, 1),
        motivo="reparacion", incidencia_id=inc.id,
    )
    cc = models.CambioConfiguracion(
        componente_id=1, equipo_id=1, accion="montaje",
        fecha=date(2026, 6, 1), motivo="reparacion", incidencia_id=inc.id,
    )
    db_session.add_all([mv, cc])
    db_session.flush()

    assert mv.incidencia_id == inc.id
    assert cc.incidencia_id == inc.id


def test_codigo_incidencia_unique(db_session):
    db_session.add(models.Incidencia(
        codigo="DUP-001",
        titulo="Primera",
        descripcion_problema="desc",
        estado="abierta",
        fecha_apertura=date(2026, 6, 1),
    ))
    db_session.flush()
    db_session.add(models.Incidencia(
        codigo="DUP-001",
        titulo="Segunda",
        descripcion_problema="desc2",
        estado="abierta",
        fecha_apertura=date(2026, 6, 1),
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()
