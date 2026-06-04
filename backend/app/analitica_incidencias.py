"""Agregación de incidencias para la pantalla de analítica.

Funciones puras sobre la sesión de BD; `hoy` se inyecta para tests deterministas.
Task 5 implementa total + distribuciones + KPIs de tiempo. Task 6 añade tendencia,
fiabilidad y resumen de garantía.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import garantia, models
from app.schemas import (
    AnaliticaIncidenciasOut,
    ConteoItem,
    KpiTiempo,
    KpiTiempoItem,
)

_ETIQUETA_TIPO = {
    "rma": "RMA",
    "soporte_venta": "Soporte Venta",
    "soporte_tecnico": "Soporte Técnico",
    "calibracion": "Calibración",
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

    kpis = KpiTiempo(
        mttr_dias=mttr,
        diagnostico_dias=diag,
        edad_abiertas_dias=edad,
        por_tipo=_kpi_por(lambda i: i.tipo, lambda k: _ETIQUETA_TIPO.get(k, k)),
        por_producto=_kpi_por(lambda i: _prod_label(i)[0], lambda k: k),
        por_tecnico=_kpi_por(lambda i: i.asignado_a or "sin_asignar", lambda k: k),
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
    )
