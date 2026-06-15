"""Orquesta la auto-clasificacion sobre BD: reglas + LLM para ambiguos.

Escribe afecta_a_medida/bajo_coste con clasificacion_origen='agente' y motivo.
NUNCA toca productos con clasificacion_origen='manual'. La auditoria se registra
sola via los listeners ORM (usuario tomado de db.info).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app import models
from app.clasificacion_trazabilidad import clasificar_por_reglas
from app.clasificacion_llm import consultar_clasificacion


@dataclass
class ResultadoAplicado:
    estado: str          # clasificado | omitido_manual | sin_cambios
    via: str | None      # reglas | llm | None
    afecta_a_medida: bool | None = None
    bajo_coste: bool | None = None
    motivo: str | None = None


@dataclass
class ResumenLote:
    procesados: int = 0
    por_reglas: int = 0
    por_llm: int = 0
    omitidos_manual: int = 0
    sin_cambios: int = 0
    cambios: list = field(default_factory=list)


def clasificar_producto(db: Session, producto, *, usar_llm: bool = False,
                        consultar=consultar_clasificacion,
                        dry_run: bool = False) -> ResultadoAplicado:
    if producto.clasificacion_origen == "manual":
        return ResultadoAplicado("omitido_manual", None)

    r = clasificar_por_reglas(producto.categoria_componente, producto.fabricante,
                              producto.descripcion, producto.part_number)
    via, afecta, bajo, motivo = "reglas", r.afecta_a_medida, r.bajo_coste, r.motivo

    if r.ambiguo and usar_llm:
        llm = consultar(producto.part_number, producto.descripcion,
                        producto.fabricante, producto.categoria_componente)
        if llm is not None:
            via = "llm"
            afecta, bajo = llm["afecta_a_medida"], llm["bajo_coste"]
            motivo = f"LLM: {llm['razon']}"

    sin_cambios = (producto.afecta_a_medida == afecta and producto.bajo_coste == bajo
                   and producto.clasificacion_origen == "agente")
    if not dry_run:
        producto.afecta_a_medida = afecta
        producto.bajo_coste = bajo
        producto.clasificacion_origen = "agente"
        producto.clasificacion_motivo = motivo
        db.commit()
    estado = "sin_cambios" if sin_cambios else "clasificado"
    return ResultadoAplicado(estado, via, afecta, bajo, motivo)


def clasificar_lote(db: Session, *, usar_llm: bool = True,
                    consultar=consultar_clasificacion, limite: int | None = None,
                    dry_run: bool = False) -> ResumenLote:
    q = (db.query(models.Producto)
         .filter(models.Producto.tipo == "componente")
         .order_by(models.Producto.part_number))
    resumen = ResumenLote()
    for p in q.all():
        if p.clasificacion_origen == "manual":
            resumen.omitidos_manual += 1
            continue
        if limite is not None and resumen.procesados >= limite:
            break
        res = clasificar_producto(db, p, usar_llm=usar_llm, consultar=consultar,
                                  dry_run=dry_run)
        resumen.procesados += 1
        if res.via == "llm":
            resumen.por_llm += 1
        elif res.via == "reglas":
            resumen.por_reglas += 1
        if res.estado == "sin_cambios":
            resumen.sin_cambios += 1
        else:
            resumen.cambios.append({
                "producto_id": p.id, "part_number": p.part_number,
                "afecta_a_medida": res.afecta_a_medida, "bajo_coste": res.bajo_coste,
                "origen": "agente", "motivo": res.motivo})
    return resumen
