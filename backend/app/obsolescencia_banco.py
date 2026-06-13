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
            "ciclo_vida_cita": p.ciclo_vida_cita,
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


def productos_de_equipo(db: Session, equipo_id: int) -> list[models.Producto]:
    """Productos distintos de los componentes del banco con fabricante+pn_fabricante
    (verificables). No verificados primero, luego por verificado_en ascendente."""
    equipo = db.get(models.Equipo, equipo_id)
    if equipo is None:
        return []
    vistos: dict[int, models.Producto] = {}
    for comp in equipo.componentes:
        p = comp.producto
        if p.fabricante and p.pn_fabricante and p.id not in vistos:
            vistos[p.id] = p
    prods = list(vistos.values())
    prods.sort(key=lambda p: (p.ciclo_vida_verificado_en is not None,
                              p.ciclo_vida_verificado_en or date.min))
    return prods


def _reemitir_paso(on_progreso, producto, indice, total):
    """Devuelve un on_paso que reemite cada paso como evento 'paso' del on_progreso."""
    if on_progreso is None:
        return None

    def on_paso(ev):
        on_progreso({"tipo": "paso", "indice": indice, "total": total,
                     "producto": producto, "descripcion": ev.get("descripcion")})
    return on_paso


def refrescar_banco(db: Session, equipo_id: int, hoy: date, *,
                    limite: int = 10, consultar, on_progreso=None) -> dict:
    """Re-verifica hasta `limite` productos del banco vía `consultar` (inyectable),
    registra los hallazgos y devuelve el report actualizado. Best-effort: un
    `consultar` que devuelve None/dict-sin-estado o falla no rompe el refresco.
    `consultar` se invoca SIEMPRE como `consultar(p, url, on_paso=...)`.

    Si se pasa `on_progreso`, se invoca con un dict por evento:
    `{"tipo":"actual","indice","total","producto"}` antes de consultar cada
    producto; `{"tipo":"paso","indice","total","producto","descripcion"}` por
    cada paso reemitido por el agente; y `{"tipo":"resultado","indice","total",
    "producto","estado_anterior","estado_nuevo","cambio","tokens",
    "estado_consulta"}` después de registrar."""
    prods = productos_de_equipo(db, equipo_id)[:limite]
    total = len(prods)
    for i, p in enumerate(prods, start=1):
        if on_progreso is not None:
            on_progreso({"tipo": "actual", "indice": i, "total": total, "producto": p})
        anterior = p.estado_ciclo_vida
        try:
            v = consultar(p, _url_fabricante(db, p),
                          on_paso=_reemitir_paso(on_progreso, p, i, total))
        except Exception:
            v = None
        tokens = (v or {}).get("tokens_total", 0)
        estado_consulta = (v or {}).get("estado_consulta", "error")
        cita = (v or {}).get("cita")
        cambio = False
        if v and v.get("estado"):
            res = obsolescencia_service.registrar_hallazgo(
                db, p.id, v["estado"], hoy=hoy, fecha_evento=v.get("fecha_evento"),
                url=v.get("url_fuente"), resumen=v.get("resumen"), cita=cita)
            cambio = bool(res.get("cambio"))
            estado_consulta = "ok"
        elif estado_consulta == "no_encontrado":
            obsolescencia_service.marcar_revisado(db, p.id, hoy)
        if on_progreso is not None:
            on_progreso({"tipo": "resultado", "indice": i, "total": total, "producto": p,
                         "estado_anterior": anterior, "estado_nuevo": p.estado_ciclo_vida,
                         "cambio": cambio, "tokens": tokens, "cita": cita,
                         "estado_consulta": estado_consulta})
    return informe_banco(db, equipo_id, hoy)
