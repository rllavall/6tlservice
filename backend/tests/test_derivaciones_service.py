# tests/test_derivaciones_service.py
from datetime import date

import pytest

from app import derivaciones_service as svc
from app import models


def _incidencia(db):
    inc = models.Incidencia(codigo="INC-0001", titulo="DMM no arranca",
                            descripcion_problema="...", fecha_apertura=date(2026, 6, 1))
    db.add(inc)
    db.flush()
    return inc


def test_generar_referencia_incrementa(db_session):
    assert svc.generar_referencia(db_session) == "RMA-0001"
    db_session.add(models.Derivacion(incidencia_id=1, tipo="interna_departamento",
                                     tu_referencia="RMA-0001", estado="pendiente",
                                     fecha_creacion=date(2026, 6, 1)))
    db_session.flush()
    assert svc.generar_referencia(db_session) == "RMA-0002"


def test_crear_externa_asigna_referencia_y_pendiente(db_session):
    inc = _incidencia(db_session)
    d = svc.crear(db_session, inc, tipo="externa_fabricante", fabricante_id=5,
                  hoy=date(2026, 6, 2))
    assert d.tu_referencia == "RMA-0001"
    assert d.estado == "pendiente"
    assert d.tipo == "externa_fabricante"
    assert d.fabricante_id == 5
    assert d.fecha_creacion == date(2026, 6, 2)


def test_crear_interna_exige_departamento(db_session):
    inc = _incidencia(db_session)
    with pytest.raises(svc.DerivacionError):
        svc.crear(db_session, inc, tipo="interna_departamento", hoy=date(2026, 6, 2))


def test_avanzar_un_paso_y_registrar_referencia_externa(db_session):
    inc = _incidencia(db_session)
    d = svc.crear(db_session, inc, tipo="externa_fabricante", fabricante_id=5,
                  hoy=date(2026, 6, 2))
    svc.avanzar(db_session, d, "enviada", hoy=date(2026, 6, 3))
    assert d.estado == "enviada"
    assert d.fecha_envio == date(2026, 6, 3)
    svc.avanzar(db_session, d, "en_proveedor", referencia_externa="NI-RMA-77")
    assert d.referencia_externa == "NI-RMA-77"


def test_avanzar_salto_invalido_lanza(db_session):
    inc = _incidencia(db_session)
    d = svc.crear(db_session, inc, tipo="externa_fabricante", fabricante_id=5,
                  hoy=date(2026, 6, 2))
    with pytest.raises(svc.DerivacionError):
        svc.avanzar(db_session, d, "cerrada")


def test_cerrar_resuelve_la_incidencia(db_session):
    inc = _incidencia(db_session)
    d = svc.crear(db_session, inc, tipo="externa_fabricante", fabricante_id=5,
                  hoy=date(2026, 6, 2))
    for estado in ("enviada", "en_proveedor", "recibida", "cerrada"):
        svc.avanzar(db_session, d, estado, hoy=date(2026, 6, 10))
    assert d.estado == "cerrada"
    assert d.fecha_cierre == date(2026, 6, 10)
    assert inc.estado == "resuelta"
    assert inc.fecha_resolucion == date(2026, 6, 10)
