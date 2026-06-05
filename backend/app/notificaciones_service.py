from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app import avisos_service, notificaciones, sla_service


def construir_digest(db: Session, hoy: date) -> dict:
    av = avisos_service.construir_avisos(db, hoy)
    sl = sla_service.construir_sla(db, hoy)
    resumen = {
        "preventivos_vencidos": av["resumen"]["preventivos_vencidos"],
        "preventivos_proximos": av["resumen"]["preventivos_proximos"],
        "contratos_por_caducar": av["resumen"]["contratos_por_caducar"],
        "sla_en_riesgo": sl["resumen"]["en_riesgo"],
        "sla_incumplidas": sl["resumen"]["incumplidas"],
    }
    total = sum(resumen.values())
    asunto = f"[6TL Postventa] Resumen de avisos ({total})"
    lineas = [f"Resumen de avisos al {hoy.isoformat()}:", ""]
    lineas.append(f"- Preventivos vencidos: {resumen['preventivos_vencidos']}")
    lineas.append(f"- Preventivos próximos: {resumen['preventivos_proximos']}")
    lineas.append(f"- Contratos por caducar: {resumen['contratos_por_caducar']}")
    lineas.append(f"- SLA en riesgo: {resumen['sla_en_riesgo']}")
    lineas.append(f"- SLA incumplidas: {resumen['sla_incumplidas']}")
    incumplidas = [i["incidencia"].codigo for i in sl["incumplidas"][:10]]
    if incumplidas:
        lineas += ["", "Incidencias SLA incumplidas: " + ", ".join(incumplidas)]
    vencidos = [a["equipo"].numero_serie for a in av["preventivos"] if a["bucket"] == "vencido"][:10]
    if vencidos:
        lineas += ["", "Equipos con preventivo vencido: " + ", ".join(vencidos)]
    return {"asunto": asunto, "cuerpo": "\n".join(lineas), "resumen": resumen, "total": total}


def enviar_digest(db: Session, hoy: date, *, notificar_fn=notificaciones.notificar) -> dict:
    d = construir_digest(db, hoy)
    canales = notificar_fn(d["asunto"], d["cuerpo"])
    return {**d, "canales": canales}


def mensaje_incidencia(inc, evento: str) -> tuple[str, str]:
    asunto = f"[6TL Postventa] Incidencia {inc.codigo}: {evento}"
    cuerpo = (
        f"Incidencia {inc.codigo} ({inc.tipo})\n"
        f"Evento: {evento}\n"
        f"Titulo: {inc.titulo}\n"
        f"Estado: {inc.estado}\n"
        f"Prioridad: {inc.prioridad}\n"
    )
    return asunto, cuerpo


def notificar_incidencia(inc, evento: str, *, notificar_fn=notificaciones.notificar) -> dict:
    asunto, cuerpo = mensaje_incidencia(inc, evento)
    return notificar_fn(asunto, cuerpo)
