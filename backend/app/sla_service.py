from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import contratos, models, sla

_ABIERTAS = ("abierta", "diagnostico", "en_reparacion")


def _contrato_vigente_de(db: Session, incidencia, hoy: date):
    if incidencia.equipo_id is None:
        return None
    eq = db.get(models.Equipo, incidencia.equipo_id)
    if eq is None or eq.contrato is None or not contratos.esta_vigente(eq.contrato, hoy):
        return None
    return eq.contrato


def sla_de_incidencia(db: Session, incidencia, hoy: date) -> Optional[dict]:
    con = _contrato_vigente_de(db, incidencia, hoy)
    if con is None:
        return None
    return sla.evaluar(incidencia, con.nivel, hoy)


def construir_sla(db: Session, hoy: date) -> dict:
    en_riesgo: list[dict] = []
    incumplidas: list[dict] = []
    total = resp_ok = reso_ok = 0
    for inc in db.query(models.Incidencia).all():
        ev = sla_de_incidencia(db, inc, hoy)
        if ev is None:
            continue
        total += 1
        if ev["respuesta"]["estado"] == "en_plazo":
            resp_ok += 1
        if ev["resolucion"]["estado"] == "en_plazo":
            reso_ok += 1
        if inc.estado in _ABIERTAS:
            if ev["estado_global"] == "incumplido":
                incumplidas.append({"incidencia": inc, "sla": ev})
            elif ev["estado_global"] == "en_riesgo":
                en_riesgo.append({"incidencia": inc, "sla": ev})
    en_riesgo.sort(key=lambda x: x["sla"]["resolucion"]["dias_restantes"])
    incumplidas.sort(key=lambda x: x["sla"]["resolucion"]["dias_restantes"])
    cumplimiento = {
        "total": total,
        "respuesta_pct": round(100 * resp_ok / total, 1) if total else None,
        "resolucion_pct": round(100 * reso_ok / total, 1) if total else None,
    }
    return {
        "cumplimiento": cumplimiento,
        "en_riesgo": en_riesgo,
        "incumplidas": incumplidas,
        "resumen": {"en_riesgo": len(en_riesgo), "incumplidas": len(incumplidas)},
    }
