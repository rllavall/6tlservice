from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import models, trazabilidad
from app.schemas import EquipoAltaCreate


class AltaError(Exception):
    """Error de negocio del alta. Lleva el paso del wizard al que pertenece."""

    def __init__(self, status_code: int, step: str, message: str, index: Optional[int] = None):
        self.status_code = status_code
        self.step = step  # "unit" | "location" | "component"
        self.message = message
        self.index = index
        super().__init__(message)


def _serie_equipo_existe(db: Session, producto_id: int, numero_serie: str) -> bool:
    return (
        db.query(models.Equipo.id)
        .filter(models.Equipo.producto_id == producto_id, models.Equipo.numero_serie == numero_serie)
        .first()
        is not None
    )


def _serie_componente_existe(db: Session, producto_id: int, numero_serie: str) -> bool:
    return (
        db.query(models.Componente.id)
        .filter(models.Componente.producto_id == producto_id, models.Componente.numero_serie == numero_serie)
        .first()
        is not None
    )


def alta_equipo_completa(db: Session, payload: EquipoAltaCreate) -> models.Equipo:
    """Crea equipo + (opcional) movimiento de entrega + (opcional) componentes
    montados, todo con `flush` (sin commit). El llamador (router) hace el commit
    o el rollback. Lanza AltaError ante cualquier validación fallida."""

    # --- validar producto del equipo ---
    prod = db.get(models.Producto, payload.producto_id)
    if prod is None:
        raise AltaError(404, "unit", "Producto del equipo no encontrado")
    if prod.tipo != "equipo":
        raise AltaError(409, "unit", "El producto del equipo no es de tipo 'equipo'")

    # --- validar cliente ---
    if payload.cliente_id is not None and db.get(models.Cliente, payload.cliente_id) is None:
        raise AltaError(404, "unit", "Cliente no encontrado")

    # --- validar serie del equipo (única por producto) ---
    if _serie_equipo_existe(db, payload.producto_id, payload.numero_serie):
        raise AltaError(409, "unit", "Ya existe un equipo con ese (producto, número de serie)")

    # --- validar ubicación ---
    ubic = None
    if payload.ubicacion_id is not None:
        ubic = db.get(models.Ubicacion, payload.ubicacion_id)
        if ubic is None:
            raise AltaError(404, "location", "Ubicación no encontrada")
        if (
            payload.cliente_id is not None
            and ubic.cliente_id is not None
            and ubic.cliente_id != payload.cliente_id
        ):
            raise AltaError(409, "location", "La ubicación pertenece a otro cliente")

    # --- validar componentes (producto + serie, incl. duplicados en el propio payload) ---
    vistos: set[tuple[int, str]] = set()
    for i, c in enumerate(payload.componentes):
        cp = db.get(models.Producto, c.producto_id)
        if cp is None:
            raise AltaError(404, "component", "Producto del componente no encontrado", index=i)
        if cp.tipo != "componente":
            raise AltaError(409, "component", "El producto no es de tipo 'componente'", index=i)
        clave = (c.producto_id, c.numero_serie)
        if clave in vistos or _serie_componente_existe(db, c.producto_id, c.numero_serie):
            raise AltaError(409, "component", "Número de serie de componente duplicado", index=i)
        vistos.add(clave)

    # --- crear equipo (con prefill de garantía, como POST /api/equipos) ---
    meses = payload.meses_garantia
    if meses is None and prod.meses_garantia_default is not None:
        meses = prod.meses_garantia_default
    eq = models.Equipo(
        numero_serie=payload.numero_serie,
        producto_id=payload.producto_id,
        cliente_id=payload.cliente_id,
        fecha_fabricacion=payload.fecha_fabricacion,
        fecha_entrega=payload.fecha_entrega,
        estado=payload.estado,
        notas=payload.notas,
        meses_garantia=meses,
        version=payload.version,
        numero_serie_cliente=payload.numero_serie_cliente,
    )
    db.add(eq)
    db.flush()  # asigna eq.id

    # --- movimiento inicial de ubicación ---
    if ubic is not None:
        fecha_mov = payload.movimiento_fecha or payload.fecha_entrega or date.today()
        trazabilidad.registrar_movimiento(
            db, eq.id, ubic.id, fecha_mov, "entrega", usuario=None, notas=payload.movimiento_notas
        )

    # --- componentes iniciales ---
    for c in payload.componentes:
        comp = models.Componente(producto_id=c.producto_id, numero_serie=c.numero_serie, notas=c.notas)
        db.add(comp)
        db.flush()  # asigna comp.id
        trazabilidad.montar_componente(db, comp.id, eq.id, c.posicion, date.today(), "entrega_inicial")

    return eq
