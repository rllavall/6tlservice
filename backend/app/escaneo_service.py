"""Resuelve un escaneo DataMatrix contra los componentes de un banco (equipo).

Empareja el PN parseado con el `pn_fabricante` de los componentes y, si es
inequivoco y el componente esta en placeholder, rellena su `numero_serie`.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import datamatrix, models


def _norm(s: str | None) -> str | None:
    return s.strip().upper() if s else None


def _candidato(comp: models.Componente, prod: models.Producto) -> dict:
    return {
        "componente_id": comp.id,
        "posicion": comp.posicion,
        "part_number": prod.part_number,
        "pn_fabricante": prod.pn_fabricante,
        "numero_serie": comp.numero_serie,
    }


def resolver_escaneo(db: Session, equipo_id: int, raw: str) -> dict:
    equipo = db.get(models.Equipo, equipo_id)
    if equipo is None:
        return {"estado": "equipo_no_existe", "formato": None, "pn": None, "sn": None,
                "componente_id": None, "posicion": None, "part_number": None, "candidatos": []}

    comps = db.query(models.Componente).filter(models.Componente.equipo_id == equipo_id).all()
    pares = []  # (componente, producto)
    reglas: list[str] = []
    fab_ids = set()
    for c in comps:
        prod = db.get(models.Producto, c.producto_id)
        if prod is None:
            continue
        pares.append((c, prod))
        if prod.fabricante_id and prod.fabricante_id not in fab_ids:
            fab_ids.add(prod.fabricante_id)
            fab = db.get(models.Fabricante, prod.fabricante_id)
            if fab and fab.regla_datamatrix:
                reglas.append(fab.regla_datamatrix)

    cand = datamatrix.parsear(raw, reglas)
    pn, sn, formato = cand["pn"], cand["sn"], cand["formato"]

    base = {"estado": None, "formato": formato, "pn": pn, "sn": sn,
            "componente_id": None, "posicion": None, "part_number": None, "candidatos": []}

    pn_norm = _norm(pn)
    casan = [(c, p) for (c, p) in pares if pn_norm and _norm(p.pn_fabricante) == pn_norm]

    if not casan:
        base["estado"] = "sin_match"
        base["candidatos"] = [_candidato(c, p) for (c, p) in pares
                              if datamatrix.es_serie_placeholder(c.numero_serie)]
        return base

    # Narrow to placeholders only; if multiple placeholders → ambiguo
    placeholders = [(c, p) for (c, p) in casan if datamatrix.es_serie_placeholder(c.numero_serie)]
    if len(placeholders) > 1:
        base["estado"] = "ambiguo"
        base["candidatos"] = [_candidato(c, p) for (c, p) in placeholders]
        return base

    # If no placeholders but multiple occupied → ambiguo (all occupied)
    if len(casan) > 1 and not placeholders:
        base["estado"] = "ambiguo"
        base["candidatos"] = [_candidato(c, p) for (c, p) in casan]
        return base

    # Exactly one match (placeholder or not)
    if placeholders:
        casan = placeholders

    comp, prod = casan[0]
    base["componente_id"] = comp.id
    base["posicion"] = comp.posicion
    base["part_number"] = prod.part_number

    if not sn:
        base["estado"] = "sin_sn"
        base["candidatos"] = [_candidato(comp, prod)]
        return base

    if not datamatrix.es_serie_placeholder(comp.numero_serie):
        base["estado"] = "ocupado"
        base["candidatos"] = [_candidato(comp, prod)]
        return base

    comp.numero_serie = sn
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        base["estado"] = "duplicado"
        base["candidatos"] = [_candidato(comp, prod)]
        return base
    db.refresh(comp)
    base["estado"] = "asignado"
    base["numero_serie"] = comp.numero_serie
    return base
