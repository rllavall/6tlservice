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


def test_kpis_tiempo_desglose_usa_etiquetas_legibles(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    # solo las 2 RMA estan resueltas (CAL sigue abierta) -> el desglose es por RMA
    pt = {it.clave: it for it in out.kpis_tiempo.por_tipo}
    assert pt["rma"].etiqueta == "RMA" and pt["rma"].dias == 7.0 and pt["rma"].n == 2
    # producto: etiqueta legible "PN — descripcion", no el id crudo
    assert out.kpis_tiempo.por_producto[0].etiqueta == "PN-A — Equipo A"
    # tecnico: etiqueta legible (las resueltas son de "ana")
    assert {it.clave: it.etiqueta for it in out.kpis_tiempo.por_tecnico} == {"ana": "ana"}


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


def test_tendencia_mensual(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    t = {p.mes: p for p in out.tendencia_mensual}
    # aperturas: ene, feb, mar 2026 (1 cada uno); cierre: ene 2026 (RMA-0001)
    assert t["2026-01"].abiertas == 1 and t["2026-01"].cerradas == 1
    assert t["2026-02"].abiertas == 1 and t["2026-02"].cerradas == 0
    # backlog acumulado: ene 1-1=0, feb 0+1=1, mar 1+1=2
    assert t["2026-01"].backlog == 0
    assert t["2026-02"].backlog == 1
    assert t["2026-03"].backlog == 2


def test_fiabilidad_y_garantia(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    # fiabilidad: el unico producto acumula 3 incidencias
    assert out.fiabilidad_productos[0].valor == 3
    # equipo eq2 tiene 2 incidencias, eq1 tiene 1 -> eq2 primero
    assert out.fiabilidad_equipos[0].valor == 2
    # garantia equipos: eq1 entrega 2025 fin 2027 -> vigente; eq2 entrega 2020 -> vencida
    estados = {c.clave: c.valor for c in out.garantia.equipos_por_estado}
    assert estados.get("vigente") == 1
    assert estados.get("vencida") == 1
    # RMA en/fuera garantia: RMA-0001 True, RMA-0002 False
    assert out.garantia.rma_en_garantia == 1
    assert out.garantia.rma_fuera_garantia == 1
