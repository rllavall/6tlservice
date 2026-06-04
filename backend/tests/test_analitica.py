from datetime import date

from app import analitica_incidencias as ana
from app import models


def _seed(db):
    """2 equipos del mismo producto, varias incidencias de distintos tipos."""
    p = models.Producto(part_number="PN-A", tipo="equipo", descripcion="Equipo A", meses_garantia_default=24)
    db.add(p); db.flush()
    cli = models.Cliente(nombre="Cli1"); db.add(cli); db.flush()
    eq1 = models.Equipo(numero_serie="S1", producto_id=p.id, cliente_id=cli.id,
                        fecha_entrega=date(2025, 1, 1), meses_garantia=24)
    eq2 = models.Equipo(numero_serie="S2", producto_id=p.id,
                        fecha_entrega=date(2020, 1, 1), meses_garantia=24)
    db.add_all([eq1, eq2]); db.flush()
    incs = [
        models.Incidencia(codigo="RMA-0001", tipo="rma", titulo="t", descripcion_problema="d",
            prioridad="alta", estado="cerrada", asignado_a="ana", en_garantia=True,
            equipo_id=eq1.id, fecha_apertura=date(2026, 1, 1),
            fecha_diagnostico=date(2026, 1, 3), fecha_resolucion=date(2026, 1, 11),
            fecha_cierre=date(2026, 1, 12)),
        models.Incidencia(codigo="CAL-0001", tipo="calibracion", titulo="t", descripcion_problema="d",
            prioridad="media", estado="abierta", asignado_a="luis",
            equipo_id=eq2.id, fecha_apertura=date(2026, 2, 1)),
        models.Incidencia(codigo="RMA-0002", tipo="rma", titulo="t", descripcion_problema="d",
            prioridad="baja", estado="resuelta", asignado_a="ana", en_garantia=False,
            equipo_id=eq2.id, fecha_apertura=date(2026, 3, 1),
            fecha_resolucion=date(2026, 3, 5)),
    ]
    db.add_all(incs); db.flush()
    return p, eq1, eq2


def _mapa(items):
    return {c.clave: c.valor for c in items}


def test_total_y_distribuciones(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    assert out.total == 3
    assert _mapa(out.por_tipo) == {"rma": 2, "calibracion": 1}
    assert _mapa(out.por_prioridad) == {"alta": 1, "media": 1, "baja": 1}
    assert _mapa(out.por_estado) == {"cerrada": 1, "abierta": 1, "resuelta": 1}
    assert _mapa(out.por_tecnico) == {"ana": 2, "luis": 1}
    assert sum(c.valor for c in out.por_producto) == 3


def test_kpis_tiempo(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    # MTTR: RMA-0001=10 dias, RMA-0002=4 dias -> media 7.0
    assert out.kpis_tiempo.mttr_dias == 7.0
    # diagnostico: solo RMA-0001 (3-1)=2 dias
    assert out.kpis_tiempo.diagnostico_dias == 2.0
    # edad abiertas = no cerradas: CAL-0001 (abierta, 2026-02-01 -> 120 dias) y
    # RMA-0002 (resuelta, 2026-03-01 -> 92 dias); media (120+92)/2 = 106.0
    assert out.kpis_tiempo.edad_abiertas_dias == 106.0


def test_filtros_desde_hasta_y_tipo(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1), tipo="rma")
    assert out.total == 2
    out2 = ana.calcular(db_session, hoy=date(2026, 6, 1), desde=date(2026, 2, 15))
    assert out2.total == 1  # solo RMA-0002 (2026-03-01)


def test_vacio_no_rompe(db_session):
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    assert out.total == 0
    assert out.kpis_tiempo.mttr_dias is None
