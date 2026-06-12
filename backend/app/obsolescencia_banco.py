"""Report de obsolescencia acotado a un banco (equipo): estado de ciclo de vida
de sus componentes (lectura del estado almacenado) + refresco síncrono acotado."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app import models, obsolescencia, obsolescencia_service


def _url_fabricante(db: Session, producto: models.Producto) -> str | None:
    if producto.fabricante_id is None:
        return None
    f = db.get(models.Fabricante, producto.fabricante_id)
    return f.url_obsolescencia if f else None


def informe_banco(db: Session, equipo_id: int, hoy: date) -> dict:
    equipo = db.get(models.Equipo, equipo_id)
    if equipo is None:
        raise ValueError(f"equipo {equipo_id} no existe")

    cliente = db.get(models.Cliente, equipo.cliente_id) if equipo.cliente_id else None
    contrato_nivel = None
    if equipo.contrato_id is not None:
        c = db.get(models.ContratoMantenimiento, equipo.contrato_id)
        contrato_nivel = c.nivel if c else None

    filas = []
    conteos = {e: 0 for e in obsolescencia.ESTADOS}
    sin_verificar = 0
    en_riesgo = 0
    verificados = []
    for comp in equipo.componentes:
        p = comp.producto
        estado = p.estado_ciclo_vida
        sev = obsolescencia.severidad(estado)
        if estado in conteos:
            conteos[estado] += 1
        if estado is None:
            sin_verificar += 1
        if sev > 0:
            en_riesgo += 1
        if p.ciclo_vida_verificado_en is not None:
            verificados.append(p.ciclo_vida_verificado_en)
        filas.append({
            "componente_id": comp.id,
            "posicion": comp.posicion,
            "part_number": p.part_number,
            "fabricante": p.fabricante,
            "pn_fabricante": p.pn_fabricante,
            "descripcion": p.descripcion,
            "numero_serie": comp.numero_serie,
            "categoria_componente": comp.categoria_componente,
            "estado_ciclo_vida": estado,
            "severidad": sev,
            "ciclo_vida_fecha": p.ciclo_vida_fecha,
            "ciclo_vida_url": p.ciclo_vida_url,
            "ciclo_vida_resumen": p.ciclo_vida_resumen,
            "ciclo_vida_verificado_en": p.ciclo_vida_verificado_en,
        })

    filas.sort(key=lambda f: (-f["severidad"], f["posicion"] or "", f["part_number"]))

    return {
        "banco": {
            "equipo_id": equipo.id,
            "numero_serie": equipo.numero_serie,
            "producto": equipo.producto.part_number if equipo.producto else "",
            "descripcion": equipo.producto.descripcion if equipo.producto else None,
            "cliente": cliente.nombre if cliente else None,
            "estado": equipo.estado,
            "contrato_nivel": contrato_nivel,
        },
        "componentes": filas,
        "resumen": {
            "conteos": conteos,
            "en_riesgo": en_riesgo,
            "sin_verificar": sin_verificar,
            "total": len(filas),
            "verificado_mas_antiguo": min(verificados) if verificados else None,
        },
    }
