from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Ubicacion ---
class UbicacionCreate(BaseModel):
    nombre: str
    tipo: Literal["fabrica_cliente", "sede_6tl", "en_reparacion", "en_transito"]
    empresa_cliente: Optional[str] = None
    pais: Optional[str] = None
    ciudad: Optional[str] = None
    notas: Optional[str] = None


class UbicacionOut(_ORM):
    id: int
    nombre: str
    tipo: str
    empresa_cliente: Optional[str] = None
    pais: Optional[str] = None
    ciudad: Optional[str] = None
    notas: Optional[str] = None


# --- Producto ---
class ProductoCreate(BaseModel):
    part_number: str
    tipo: Literal["equipo", "componente"]
    descripcion: str
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    notas: Optional[str] = None


class ProductoOut(_ORM):
    id: int
    part_number: str
    tipo: str
    descripcion: str
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    notas: Optional[str] = None


# --- Equipo ---
class EquipoCreate(BaseModel):
    numero_serie: str
    producto_id: int
    cliente: Optional[str] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: Literal["operativo", "baja"] = "operativo"
    notas: Optional[str] = None


class EquipoUpdate(BaseModel):
    cliente: Optional[str] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: Optional[Literal["operativo", "baja"]] = None
    notas: Optional[str] = None


class EquipoOut(_ORM):
    id: int
    numero_serie: str
    producto_id: int
    cliente: Optional[str] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: str
    notas: Optional[str] = None


# --- Componente ---
class ComponenteCreate(BaseModel):
    numero_serie: str
    producto_id: int
    equipo_id: Optional[int] = None
    posicion: Optional[str] = None
    fecha_montaje: Optional[date] = None
    notas: Optional[str] = None


class ComponenteOut(_ORM):
    id: int
    numero_serie: str
    producto_id: int
    equipo_id: Optional[int] = None
    posicion: Optional[str] = None
    fecha_montaje: Optional[date] = None
    notas: Optional[str] = None


# --- Movimiento ---
class MovimientoCreate(BaseModel):
    ubicacion_destino_id: int
    fecha: date
    motivo: Literal["entrega", "traslado", "reparacion", "devolucion"]
    usuario: Optional[str] = None
    notas: Optional[str] = None


class MovimientoOut(_ORM):
    id: int
    equipo_id: int
    ubicacion_destino_id: int
    fecha: date
    motivo: str
    usuario: Optional[str] = None
    notas: Optional[str] = None


# --- CambioConfiguracion ---
class CambioConfiguracionOut(_ORM):
    id: int
    componente_id: int
    equipo_id: int
    accion: str
    posicion: Optional[str] = None
    fecha: date
    motivo: str
    usuario: Optional[str] = None
    notas: Optional[str] = None


# --- Acciones de configuración (payloads) ---
class MontarPayload(BaseModel):
    equipo_id: int
    posicion: Optional[str] = None
    fecha: date
    motivo: Literal["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"]
    usuario: Optional[str] = None
    notas: Optional[str] = None


class DesmontarPayload(BaseModel):
    fecha: date
    motivo: Literal["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"]
    usuario: Optional[str] = None
    notas: Optional[str] = None


class SustituirPayload(BaseModel):
    componente_saliente_id: int
    componente_entrante_id: int
    posicion: Optional[str] = None
    fecha: date
    motivo: Literal["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"] = "sustitucion"
    usuario: Optional[str] = None
    notas: Optional[str] = None


# --- Ficha y búsqueda ---
class EquipoFicha(_ORM):
    equipo: EquipoOut
    producto: ProductoOut
    ubicacion_actual: Optional[UbicacionOut] = None
    componentes: list[ComponenteOut] = []
    historial_movimientos: list[MovimientoOut] = []
    historial_configuracion: list[CambioConfiguracionOut] = []


class ResultadoBusqueda(BaseModel):
    tipo: Literal["equipo", "componente", "ninguno"]
    equipo: Optional[EquipoOut] = None
    componente: Optional[ComponenteOut] = None
    equipo_del_componente: Optional[EquipoOut] = None
