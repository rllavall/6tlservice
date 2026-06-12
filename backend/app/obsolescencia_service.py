"""Servicio de obsolescencia: lista de trabajo, registro de hallazgos y resumen.
Escribe directo a BD (lo usa el orquestador semanal sin auth y el router con auth)."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, obsolescencia, notificaciones


def productos_a_revisar(db: Session, hoy: date, *, dias: int = 7, limite: int | None = None):
    """Productos con fabricante+pn_fabricante no verificados en los últimos `dias`.
    No verificados primero; `limite` reparte el catálogo entre ejecuciones."""
    umbral = hoy - timedelta(days=dias)
    q = (
        db.query(models.Producto)
        .filter(models.Producto.fabricante.isnot(None))
        .filter(models.Producto.pn_fabricante.isnot(None))
        .filter(or_(models.Producto.ciclo_vida_verificado_en.is_(None),
                    models.Producto.ciclo_vida_verificado_en <= umbral))
        .order_by(models.Producto.ciclo_vida_verificado_en.is_(None).desc(),
                  models.Producto.ciclo_vida_verificado_en.asc())
    )
    if limite is not None:
        q = q.limit(limite)
    return q.all()


def registrar_hallazgo(db: Session, producto_id: int, estado: str, *, hoy: date,
                       fecha_evento: date | None = None, url: str | None = None,
                       resumen: str | None = None) -> dict:
    p = db.get(models.Producto, producto_id)
    if p is None:
        return {"registrado": False, "motivo": "no_existe", "cambio": False}
    if not obsolescencia.estado_valido(estado):
        return {"registrado": False, "motivo": "estado_invalido", "cambio": False}
    if obsolescencia.requiere_url(estado) and not url:
        return {"registrado": False, "motivo": "sin_url", "cambio": False}

    anterior = p.estado_ciclo_vida
    notable = obsolescencia.es_cambio_notable(anterior, estado)

    p.estado_ciclo_vida = estado
    p.ciclo_vida_fecha = fecha_evento
    p.ciclo_vida_url = url
    p.ciclo_vida_resumen = resumen
    p.ciclo_vida_verificado_en = hoy

    if notable:
        db.add(models.NoticiaObsolescencia(
            producto_id=p.id, fecha_deteccion=hoy, estado_anterior=anterior,
            estado_nuevo=estado, fecha_evento=fecha_evento, url_fuente=url,
            resumen=resumen, notificado=False))
    db.commit()
    return {"registrado": True, "cambio": notable, "motivo": None}


def construir_informe(db: Session, hoy: date) -> dict:
    noticias = (
        db.query(models.NoticiaObsolescencia)
        .filter(models.NoticiaObsolescencia.notificado.is_(False))
        .order_by(models.NoticiaObsolescencia.fecha_deteccion.asc(),
                  models.NoticiaObsolescencia.id.asc())
        .all()
    )
    total = len(noticias)
    asunto = f"[6TL Postventa] Cambios de obsolescencia ({total})"
    lineas = [f"Cambios de ciclo de vida detectados al {hoy.isoformat()}:", ""]
    for n in noticias:
        p = db.get(models.Producto, n.producto_id)
        ref = p.part_number if p else f"producto#{n.producto_id}"
        linea = f"- {ref}: {n.estado_anterior or 'sin verificar'} -> {n.estado_nuevo}"
        if n.url_fuente:
            linea += f"  ({n.url_fuente})"
        lineas.append(linea)
    return {"asunto": asunto, "cuerpo": "\n".join(lineas), "total": total, "noticias": noticias}


def enviar_informe(db: Session, hoy: date, *, notificar_fn=notificaciones.notificar) -> dict:
    info = construir_informe(db, hoy)
    if info["total"] == 0:
        return {"asunto": info["asunto"], "cuerpo": info["cuerpo"], "total": 0,
                "canales": {"email": None, "telegram": None}, "enviado": False}
    canales = notificar_fn(info["asunto"], info["cuerpo"])
    for n in info["noticias"]:
        n.notificado = True
    db.commit()
    return {"asunto": info["asunto"], "cuerpo": info["cuerpo"], "total": info["total"],
            "canales": canales, "enviado": True}


def resumen_obsolescencia(db: Session, *, limite_noticias: int = 20) -> dict:
    conteos = {e: 0 for e in obsolescencia.ESTADOS}
    sin_verificar = 0
    for (estado,) in db.query(models.Producto.estado_ciclo_vida).all():
        if estado in conteos:
            conteos[estado] += 1
        else:
            sin_verificar += 1
    noticias = (
        db.query(models.NoticiaObsolescencia)
        .order_by(models.NoticiaObsolescencia.fecha_deteccion.desc(),
                  models.NoticiaObsolescencia.id.desc())
        .limit(limite_noticias).all()
    )
    return {"conteos": conteos, "sin_verificar": sin_verificar, "noticias": noticias}
