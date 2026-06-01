from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

TIPOS_UBICACION = ["fabrica_cliente", "sede_6tl", "en_reparacion", "en_transito"]
TIPOS_PRODUCTO = ["equipo", "componente"]
ESTADOS_EQUIPO = ["operativo", "baja"]
MOTIVOS_MOVIMIENTO = ["entrega", "traslado", "reparacion", "devolucion"]
ACCIONES_CONFIG = ["montaje", "desmontaje"]
MOTIVOS_CONFIG = ["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"]


class Ubicacion(Base):
    __tablename__ = "ubicaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String)
    tipo: Mapped[str] = mapped_column(String)
    empresa_cliente: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pais: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ciudad: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_number: Mapped[str] = mapped_column(String, unique=True)
    tipo: Mapped[str] = mapped_column(String)
    descripcion: Mapped[str] = mapped_column(String)
    fabricante: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    modelo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Equipo(Base):
    __tablename__ = "equipos"
    __table_args__ = (UniqueConstraint("producto_id", "numero_serie", name="uq_equipo_serie"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_serie: Mapped[str] = mapped_column(String)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cliente: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha_fabricacion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_entrega: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(String, default="operativo")
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    producto: Mapped["Producto"] = relationship()
    componentes: Mapped[list["Componente"]] = relationship(back_populates="equipo")


class Componente(Base):
    __tablename__ = "componentes"
    __table_args__ = (UniqueConstraint("producto_id", "numero_serie", name="uq_componente_serie"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_serie: Mapped[str] = mapped_column(String)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    equipo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipos.id"), nullable=True)
    posicion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha_montaje: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    producto: Mapped["Producto"] = relationship()
    equipo: Mapped[Optional["Equipo"]] = relationship(back_populates="componentes")


class Movimiento(Base):
    __tablename__ = "movimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    ubicacion_destino_id: Mapped[int] = mapped_column(ForeignKey("ubicaciones.id"))
    fecha: Mapped[date] = mapped_column(Date)
    motivo: Mapped[str] = mapped_column(String)
    usuario: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    ubicacion_destino: Mapped["Ubicacion"] = relationship()


class CambioConfiguracion(Base):
    __tablename__ = "cambios_configuracion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    componente_id: Mapped[int] = mapped_column(ForeignKey("componentes.id"))
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    accion: Mapped[str] = mapped_column(String)
    posicion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha: Mapped[date] = mapped_column(Date)
    motivo: Mapped[str] = mapped_column(String)
    usuario: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    componente: Mapped["Componente"] = relationship()
