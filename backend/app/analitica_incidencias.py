"""Agregación de incidencias para la pantalla de analítica.

Funciones puras sobre la sesión de BD; `hoy` se inyecta para tests deterministas.
Task 5 implementa total + distribuciones + KPIs de tiempo. Task 6 añade tendencia,
fiabilidad y resumen de garantía.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import garantia, models
from app.schemas import (
    AnaliticaIncidenciasOut,
    ConteoItem,
    KpiTiempo,
    KpiTiempoItem,
    PuntoTendencia,
    RankingItem,
    ResumenGarantia,
    ResumenServicioOut,
)

_ETIQUETA_TIPO = {
    "rma": "RMA",
    "soporte_venta": "Soporte Venta",
    "soporte_tecnico": "Soporte Técnico",
    "calibracion": "Calibración",
}

_ETQ_GARANTIA = {
    "vigente": "Vigente",
    "por_vencer": "Por vencer",
    "vencida": "Vencida",
    "sin_datos": "Sin datos",
}


def _producto_de(db: Session, inc: models.Incidencia) -> Optional[models.Producto]:
    if inc.equipo_id is not None:
        eq = db.get(models.Equipo, inc.equipo_id)
        return db.get(models.Producto, eq.producto_id) if eq is not None else None
    if inc.componente_id is not None:
        comp = db.get(models.Componente, inc.componente_id)
        return db.get(models.Producto, comp.producto_id) if comp is not None else None
    return None


def _cliente_id_de(db: Session, inc: models.Incidencia) -> Optional[int]:
    eq = db.get(models.Equipo, inc.equipo_id) if inc.equipo_id is not None else None
    if eq is None and inc.componente_id is not None:
        comp = db.get(models.Componente, inc.componente_id)
        if comp is not None and comp.equipo_id is not None:
            eq = db.get(models.Equipo, comp.equipo_id)
    return eq.cliente_id if eq is not None else None


def _incidencias_filtradas(db, desde, hasta, tipo, cliente_id) -> list[models.Incidencia]:
    q = db.query(models.Incidencia)
    if tipo is not None:
        q = q.filter(models.Incidencia.tipo == tipo)
    if desde is not None:
        q = q.filter(models.Incidencia.fecha_apertura >= desde)
    if hasta is not None:
        q = q.filter(models.Incidencia.fecha_apertura <= hasta)
    incs = q.all()
    if cliente_id is not None:
        incs = [i for i in incs if _cliente_id_de(db, i) == cliente_id]
    return incs


def _media(valores: list[int]) -> Optional[float]:
    return round(sum(valores) / len(valores), 1) if valores else None


def _conteos(claves_etiquetas: list[tuple[str, str]]) -> list[ConteoItem]:
    c = Counter(k for k, _ in claves_etiquetas)
    etiqueta = dict(claves_etiquetas)
    return [ConteoItem(clave=k, etiqueta=etiqueta[k], valor=v)
            for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]


def calcular(db: Session, hoy: date, desde: Optional[date] = None,
             hasta: Optional[date] = None, tipo: Optional[str] = None,
             cliente_id: Optional[int] = None) -> AnaliticaIncidenciasOut:
    incs = _incidencias_filtradas(db, desde, hasta, tipo, cliente_id)
    prod_por_inc = {i.id: _producto_de(db, i) for i in incs}

    def _prod_label(i):
        p = prod_por_inc.get(i.id)
        return (str(p.id), f"{p.part_number} — {p.descripcion}") if p else ("sin_producto", "Sin producto")

    # Distribuciones
    por_tipo = _conteos([(i.tipo, _ETIQUETA_TIPO.get(i.tipo, i.tipo)) for i in incs])
    por_prioridad = _conteos([(i.prioridad, i.prioridad) for i in incs])
    por_estado = _conteos([(i.estado, i.estado) for i in incs])
    por_tecnico = _conteos([(i.asignado_a or "sin_asignar", i.asignado_a or "Sin asignar") for i in incs])
    por_producto = _conteos([_prod_label(i) for i in incs])
    cli_pairs = []
    for i in incs:
        cid = _cliente_id_de(db, i)
        if cid is None:
            cli_pairs.append(("sin_cliente", "Sin cliente"))
        else:
            cli = db.get(models.Cliente, cid)
            cli_pairs.append((str(cid), cli.nombre if cli else f"Cliente {cid}"))
    por_cliente = _conteos(cli_pairs)

    # KPIs de tiempo
    def _resol_dias(i):
        if i.fecha_resolucion is not None:
            return (i.fecha_resolucion - i.fecha_apertura).days
        return None

    def _diag_dias(i):
        if i.fecha_diagnostico is not None:
            return (i.fecha_diagnostico - i.fecha_apertura).days
        return None

    mttr = _media([d for i in incs if (d := _resol_dias(i)) is not None])
    diag = _media([d for i in incs if (d := _diag_dias(i)) is not None])
    # "abiertas" = no cerradas (coherente con el filtro `abiertas` del listado, que excluye solo cerrada)
    edad = _media([(hoy - i.fecha_apertura).days for i in incs if i.estado != "cerrada"])

    def _kpi_por(grupo_fn, etiqueta_fn) -> list[KpiTiempoItem]:
        grupos = defaultdict(list)
        for i in incs:
            d = _resol_dias(i)
            if d is not None:
                grupos[grupo_fn(i)].append(d)
        items = []
        for clave, valores in grupos.items():
            items.append(KpiTiempoItem(clave=clave, etiqueta=etiqueta_fn(clave), dias=_media(valores), n=len(valores)))
        return sorted(items, key=lambda it: it.clave)

    # Mapas clave->etiqueta legible para los desgloses de MTTR (mismo criterio que las distribuciones).
    prod_etiqueta = dict(_prod_label(i) for i in incs)
    tecnico_etiqueta = {(i.asignado_a or "sin_asignar"): (i.asignado_a or "Sin asignar") for i in incs}

    kpis = KpiTiempo(
        mttr_dias=mttr,
        diagnostico_dias=diag,
        edad_abiertas_dias=edad,
        por_tipo=_kpi_por(lambda i: i.tipo, lambda k: _ETIQUETA_TIPO.get(k, k)),
        por_producto=_kpi_por(lambda i: _prod_label(i)[0], lambda k: prod_etiqueta.get(k, k)),
        por_tecnico=_kpi_por(lambda i: i.asignado_a or "sin_asignar", lambda k: tecnico_etiqueta.get(k, k)),
    )

    # Tendencia mensual
    aperturas = Counter(i.fecha_apertura.strftime("%Y-%m") for i in incs)
    cierres = Counter(i.fecha_cierre.strftime("%Y-%m") for i in incs if i.fecha_cierre is not None)
    meses = sorted(set(aperturas) | set(cierres))
    # Backlog arrastrado: incidencias abiertas ANTES del rango visible que seguian abiertas
    # al inicio del mismo (si no, el backlog arrancaria en 0 al filtrar por `desde`).
    backlog = 0
    if desde is not None:
        previas = _incidencias_filtradas(db, None, desde - timedelta(days=1), tipo, cliente_id)
        backlog = sum(1 for i in previas if i.fecha_cierre is None or i.fecha_cierre >= desde)
    tendencia = []
    for mes in meses:
        ab = aperturas.get(mes, 0)
        ce = cierres.get(mes, 0)
        backlog += ab - ce
        tendencia.append(PuntoTendencia(mes=mes, abiertas=ab, cerradas=ce, backlog=backlog))

    # Fiabilidad (rankings)
    fiab_prod = Counter()
    etiqueta_prod = {}
    fiab_eq = Counter()
    etiqueta_eq = {}
    for i in incs:
        clave, etq = _prod_label(i)
        fiab_prod[clave] += 1
        etiqueta_prod[clave] = etq
        if i.equipo_id is not None:
            fiab_eq[i.equipo_id] += 1
    for eid in list(fiab_eq):
        eq = db.get(models.Equipo, eid)
        etiqueta_eq[eid] = eq.numero_serie if eq is not None else f"Equipo {eid}"
    fiabilidad_productos = [
        RankingItem(id=None, etiqueta=etiqueta_prod[k], valor=v)
        for k, v in sorted(fiab_prod.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    ]
    fiabilidad_equipos = [
        RankingItem(id=k, etiqueta=etiqueta_eq[k], valor=v)
        for k, v in sorted(fiab_eq.items(), key=lambda kv: (-kv[1], str(kv[0])))[:10]
    ]

    # Resumen de garantía sobre la base instalada (parque). Filtra por cliente si se indica;
    # tipo/fechas son dimensiones de incidencia y NO aplican al estado de garantía del parque.
    eq_query = db.query(models.Equipo)
    if cliente_id is not None:
        eq_query = eq_query.filter(models.Equipo.cliente_id == cliente_id)
    equipos = eq_query.all()
    estados = Counter(garantia.estado_garantia(eq, hoy) for eq in equipos)
    equipos_por_estado = [
        ConteoItem(clave=k, etiqueta=_ETQ_GARANTIA.get(k, k), valor=v)
        for k, v in sorted(estados.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    rma = [i for i in incs if i.tipo == "rma"]
    rma_en = sum(1 for i in rma if i.en_garantia is True)
    rma_fuera = sum(1 for i in rma if i.en_garantia is False)
    rma_desc = sum(1 for i in rma if i.en_garantia is None)
    resumen_garantia = ResumenGarantia(
        equipos_por_estado=equipos_por_estado,
        rma_en_garantia=rma_en,
        rma_fuera_garantia=rma_fuera,
        rma_garantia_desconocida=rma_desc,
    )

    return AnaliticaIncidenciasOut(
        total=len(incs),
        por_tipo=por_tipo,
        por_producto=por_producto,
        por_tecnico=por_tecnico,
        por_prioridad=por_prioridad,
        por_estado=por_estado,
        por_cliente=por_cliente,
        kpis_tiempo=kpis,
        tendencia_mensual=tendencia,
        fiabilidad_productos=fiabilidad_productos,
        fiabilidad_equipos=fiabilidad_equipos,
        garantia=resumen_garantia,
    )


def resumen_servicio(db: Session, hoy: date) -> ResumenServicioOut:
    incs = db.query(models.Incidencia).all()
    abiertas = [i for i in incs if i.estado != "cerrada"]
    inicio_30d = hoy - timedelta(days=30)
    cerradas_30d = [
        i for i in incs
        if i.fecha_cierre is not None and i.fecha_cierre >= inicio_30d
    ]
    tiempos = [(i.fecha_cierre - i.fecha_apertura).days for i in cerradas_30d]
    return ResumenServicioOut(
        incidencias_abiertas=len(abiertas),
        incidencias_abiertas_alta=sum(1 for i in abiertas if i.prioridad == "alta"),
        rma_abierto=sum(1 for i in abiertas if i.tipo == "rma"),
        en_reparacion=sum(1 for i in incs if i.estado == "en_reparacion"),
        cerradas_30d=len(cerradas_30d),
        tiempo_medio_cierre_dias=_media(tiempos),
    )
