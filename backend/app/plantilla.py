"""Configuración esperada (plantilla BOM) por producto-equipo.

Define qué componentes lleva un modelo de ATE. Lo consume el pre-relleno del alta
y la comparación real vs esperada. Escribe con flush; el router hace commit.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app import models


class PlantillaError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def listar(db: Session, producto_equipo_id: int) -> list[models.PlantillaComponente]:
    return (
        db.query(models.PlantillaComponente)
        .filter(models.PlantillaComponente.producto_equipo_id == producto_equipo_id)
        .order_by(models.PlantillaComponente.posicion, models.PlantillaComponente.id)
        .all()
    )


def crear(db: Session, producto_equipo_id: int, producto_componente_id: int,
          posicion: Optional[str], cantidad: int) -> models.PlantillaComponente:
    eq = db.get(models.Producto, producto_equipo_id)
    if eq is None:
        raise PlantillaError(404, "Producto-equipo no encontrado")
    if eq.tipo != "equipo":
        raise PlantillaError(409, "El producto de la plantilla no es de tipo 'equipo'")
    comp = db.get(models.Producto, producto_componente_id)
    if comp is None:
        raise PlantillaError(404, "Producto-componente no encontrado")
    if comp.tipo != "componente":
        raise PlantillaError(409, "El producto referenciado no es de tipo 'componente'")
    if cantidad < 1:
        raise PlantillaError(422, "La cantidad debe ser >= 1")
    linea = models.PlantillaComponente(
        producto_equipo_id=producto_equipo_id,
        producto_componente_id=producto_componente_id,
        posicion=posicion, cantidad=cantidad,
    )
    db.add(linea)
    db.flush()
    return linea


def actualizar(db: Session, linea_id: int, *, posicion=..., cantidad=...) -> models.PlantillaComponente:
    linea = db.get(models.PlantillaComponente, linea_id)
    if linea is None:
        raise PlantillaError(404, "Línea de plantilla no encontrada")
    if posicion is not ...:
        linea.posicion = posicion
    if cantidad is not ...:
        if cantidad is None or cantidad < 1:
            raise PlantillaError(422, "La cantidad debe ser >= 1")
        linea.cantidad = cantidad
    db.flush()
    return linea


def borrar(db: Session, linea_id: int) -> None:
    linea = db.get(models.PlantillaComponente, linea_id)
    if linea is None:
        raise PlantillaError(404, "Línea de plantilla no encontrada")
    db.delete(linea)
    db.flush()
