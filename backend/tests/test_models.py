from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import models


def test_create_full_graph(db_session):
    sede = models.Ubicacion(nombre="6TL Barcelona", tipo="sede_6tl")
    prod_eq = models.Producto(part_number="ATE-1000", tipo="equipo", descripcion="Sistema test")
    prod_comp = models.Producto(part_number="PXI-5122", tipo="componente", descripcion="Digitizer")
    db_session.add_all([sede, prod_eq, prod_comp])
    db_session.flush()

    eq = models.Equipo(numero_serie="EQ-001", producto_id=prod_eq.id, estado="operativo")
    db_session.add(eq)
    db_session.flush()

    comp = models.Componente(numero_serie="C-001", producto_id=prod_comp.id, equipo_id=eq.id, posicion="ranura 3")
    db_session.add(comp)
    db_session.flush()

    db_session.add(models.Movimiento(equipo_id=eq.id, ubicacion_destino_id=sede.id, fecha=date(2026, 1, 1), motivo="entrega"))
    db_session.add(models.CambioConfiguracion(componente_id=comp.id, equipo_id=eq.id, accion="montaje", fecha=date(2026, 1, 1), motivo="entrega_inicial"))
    db_session.flush()

    assert eq.id is not None and comp.equipo_id == eq.id


def test_serie_unique_per_producto(db_session):
    p = models.Producto(part_number="ATE-1000", tipo="equipo", descripcion="x")
    db_session.add(p)
    db_session.flush()
    db_session.add(models.Equipo(numero_serie="DUP", producto_id=p.id))
    db_session.flush()
    db_session.add(models.Equipo(numero_serie="DUP", producto_id=p.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_serie_different_producto_ok(db_session):
    p1 = models.Producto(part_number="A", tipo="equipo", descripcion="x")
    p2 = models.Producto(part_number="B", tipo="equipo", descripcion="y")
    db_session.add_all([p1, p2])
    db_session.flush()
    db_session.add(models.Equipo(numero_serie="S1", producto_id=p1.id))
    db_session.add(models.Equipo(numero_serie="S1", producto_id=p2.id))
    db_session.flush()  # no raise


def test_part_number_unique(db_session):
    db_session.add(models.Producto(part_number="X", tipo="equipo", descripcion="a"))
    db_session.flush()
    db_session.add(models.Producto(part_number="X", tipo="componente", descripcion="b"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_equipo_props_garantia(db_session):
    from app import models
    p = models.Producto(part_number="PN1", tipo="equipo", descripcion="d", meses_garantia_default=24)
    db_session.add(p); db_session.flush()
    eq = models.Equipo(
        numero_serie="SN1", producto_id=p.id, version="Rev C",
        fecha_entrega=date(2024, 1, 1), meses_garantia=24,
    )
    db_session.add(eq); db_session.flush()
    assert eq.version == "Rev C"
    assert eq.fecha_fin_garantia == date(2026, 1, 1)
    assert eq.estado_garantia in {"vigente", "por_vencer", "vencida"}


def test_incidencia_tipo_default(db_session):
    from app import models
    inc = models.Incidencia(
        codigo="RMA-9001", titulo="t", descripcion_problema="d",
        estado="abierta", fecha_apertura=date(2026, 6, 1),
    )
    db_session.add(inc); db_session.flush()
    assert inc.tipo == "rma"
