# app/fabricantes_seed.py
"""Siembra `Fabricante` a partir del texto libre `Producto.fabricante` y enlaza
`Producto.fabricante_id`. Idempotente: empareja por nombre, no duplica."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models


def sembrar_fabricantes_desde_texto(db: Session) -> int:
    """Crea fabricantes que falten y enlaza productos. Devuelve nº de fabricantes creados.

    No hace commit: el llamante decide la transacción.
    """
    existentes = {f.nombre: f for f in db.query(models.Fabricante).all()}
    creados = 0
    productos = (
        db.query(models.Producto)
        .filter(models.Producto.fabricante.isnot(None))
        .all()
    )
    for p in productos:
        nombre = (p.fabricante or "").strip()
        if not nombre:
            continue
        fabricante = existentes.get(nombre)
        if fabricante is None:
            fabricante = models.Fabricante(nombre=nombre)
            db.add(fabricante)
            db.flush()
            existentes[nombre] = fabricante
            creados += 1
        if p.fabricante_id is None:
            p.fabricante_id = fabricante.id
    return creados
