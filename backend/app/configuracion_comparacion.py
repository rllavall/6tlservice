"""Compara la configuración REAL de un equipo (componentes montados) con la
configuración ESPERADA (plantilla de su producto-equipo).

Devuelve, por producto esperado, cuántas unidades faltan/sobran, más las tareas
pendientes del operario: series por capturar (nivel serie) y revisiones por
indicar (nivel version). Read-only.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import datamatrix, models, plantilla


def _serie_pendiente(comp: models.Componente) -> bool:
    return not comp.numero_serie or datamatrix.es_serie_placeholder(comp.numero_serie)


def construir_configuracion(db: Session, equipo_id: int) -> dict:
    equipo = db.get(models.Equipo, equipo_id)
    if equipo is None:
        raise LookupError("Equipo no encontrado")

    reales = db.query(models.Componente).filter(models.Componente.equipo_id == equipo_id).all()

    # cantidad esperada por producto componente (agregando líneas de plantilla)
    esperado_por_prod: dict[int, int] = {}
    info_prod: dict[int, models.Producto] = {}
    for pl in plantilla.listar(db, equipo.producto_id):
        esperado_por_prod[pl.producto_componente_id] = (
            esperado_por_prod.get(pl.producto_componente_id, 0) + (pl.cantidad or 1))
        if pl.producto_componente is not None:
            info_prod[pl.producto_componente_id] = pl.producto_componente

    # cantidad presente por producto
    presente_por_prod: dict[int, int] = {}
    for c in reales:
        presente_por_prod[c.producto_id] = presente_por_prod.get(c.producto_id, 0) + 1
        info_prod.setdefault(c.producto_id, c.producto)

    lineas = []
    total_faltan = 0
    for pid, esp in esperado_por_prod.items():
        p = info_prod.get(pid)
        pres = presente_por_prod.get(pid, 0)
        faltan = max(0, esp - pres)
        total_faltan += faltan
        lineas.append({
            "producto_componente_id": pid,
            "part_number": p.part_number if p else None,
            "descripcion": p.descripcion if p else None,
            "nivel_trazabilidad": p.nivel_trazabilidad if p else None,
            "cantidad_esperada": esp,
            "cantidad_presente": pres,
            "faltan": faltan,
        })
    lineas.sort(key=lambda x: (x["part_number"] or ""))

    # sobrantes: unidades reales por encima de lo esperado (o no esperadas)
    sobrantes = []
    series_pendientes = []
    versiones_pendientes = []
    for c in reales:
        p = c.producto
        nivel = p.nivel_trazabilidad if p else None
        esp = esperado_por_prod.get(c.producto_id, 0)
        if esp == 0:
            sobrantes.append({"componente_id": c.id, "producto_id": c.producto_id,
                              "part_number": p.part_number if p else None,
                              "numero_serie": c.numero_serie, "posicion": c.posicion})
        if nivel == "serie" and _serie_pendiente(c):
            series_pendientes.append({"componente_id": c.id, "producto_id": c.producto_id,
                                      "part_number": p.part_number if p else None,
                                      "posicion": c.posicion})
        if nivel == "version" and not c.revision:
            versiones_pendientes.append({"componente_id": c.id, "producto_id": c.producto_id,
                                         "part_number": p.part_number if p else None,
                                         "posicion": c.posicion})

    completo = (total_faltan == 0 and not sobrantes
                and not series_pendientes and not versiones_pendientes)
    return {
        "equipo_id": equipo_id,
        "producto_equipo_id": equipo.producto_id,
        "lineas": lineas,
        "sobrantes": sobrantes,
        "series_pendientes": series_pendientes,
        "versiones_pendientes": versiones_pendientes,
        "resumen": {
            "esperados": sum(esperado_por_prod.values()),
            "presentes": len(reales),
            "faltantes": total_faltan,
            "sobrantes": len(sobrantes),
            "series_pendientes": len(series_pendientes),
            "versiones_pendientes": len(versiones_pendientes),
            "completo": completo,
        },
    }
