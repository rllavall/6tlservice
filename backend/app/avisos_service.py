from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app import avisos, contratos, models


def construir_avisos(db: Session, hoy: date) -> dict:
    preventivos: list[dict] = []
    equipos = db.query(models.Equipo).filter(models.Equipo.contrato_id.isnot(None)).all()
    for eq in equipos:
        con = eq.contrato
        if con is None or not contratos.esta_vigente(con, hoy):
            continue
        ultima = (db.query(models.AccionPreventiva)
                  .filter(models.AccionPreventiva.equipo_id == eq.id)
                  .order_by(models.AccionPreventiva.fecha.desc(), models.AccionPreventiva.id.desc())
                  .first())
        proxima = avisos.proxima_fecha_equipo(eq, con, ultima, hoy)
        bucket = avisos.clasificar(proxima, hoy)
        if bucket == "al_dia":
            continue
        preventivos.append({
            "equipo": eq,
            "contrato": con,
            "proxima_fecha": proxima,
            "dias_restantes": avisos.dias_restantes(proxima, hoy),
            "bucket": bucket,
            "ultima_fecha": ultima.fecha if ultima is not None else None,
        })
    preventivos.sort(key=lambda a: a["dias_restantes"])

    contratos_cad: list[dict] = []
    for con in db.query(models.ContratoMantenimiento).all():
        if avisos.contrato_por_caducar(con, hoy):
            cliente = db.get(models.Cliente, con.cliente_id) if con.cliente_id else None
            contratos_cad.append({
                "contrato": con,
                "cliente": cliente,
                "fecha_fin": con.fecha_fin,
                "dias_restantes": avisos.dias_restantes(con.fecha_fin, hoy),
            })
    contratos_cad.sort(key=lambda c: c["dias_restantes"])

    resumen = {
        "preventivos_vencidos": sum(1 for a in preventivos if a["bucket"] == "vencido"),
        "preventivos_proximos": sum(1 for a in preventivos if a["bucket"] == "proximo"),
        "contratos_por_caducar": len(contratos_cad),
    }
    return {"preventivos": preventivos, "contratos_por_caducar": contratos_cad, "resumen": resumen}
