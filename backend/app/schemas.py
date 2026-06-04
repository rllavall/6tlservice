from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Cliente ---
class ClienteCreate(BaseModel):
    nombre: str
    cif: Optional[str] = None
    persona_contacto: Optional[str] = None
    email_contacto: Optional[str] = None
    telefono_contacto: Optional[str] = None
    notas: Optional[str] = None


class ClienteOut(_ORM):
    id: int
    nombre: str
    cif: Optional[str] = None
    persona_contacto: Optional[str] = None
    email_contacto: Optional[str] = None
    telefono_contacto: Optional[str] = None
    notas: Optional[str] = None


# --- Ubicacion ---
class UbicacionCreate(BaseModel):
    nombre: str
    tipo: Literal["fabrica_cliente", "sede_6tl", "en_reparacion", "en_transito"]
    cliente_id: Optional[int] = None
    direccion: Optional[str] = None
    codigo_postal: Optional[str] = None
    ciudad: Optional[str] = None
    provincia: Optional[str] = None
    pais: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    notas: Optional[str] = None


class UbicacionOut(_ORM):
    id: int
    nombre: str
    tipo: str
    cliente_id: Optional[int] = None
    direccion: Optional[str] = None
    codigo_postal: Optional[str] = None
    ciudad: Optional[str] = None
    provincia: Optional[str] = None
    pais: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    notas: Optional[str] = None


# --- Producto ---
class ProductoCreate(BaseModel):
    part_number: str
    tipo: Literal["equipo", "componente"]
    descripcion: str
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    notas: Optional[str] = None
    meses_garantia_default: Optional[int] = 24


class ProductoOut(_ORM):
    id: int
    part_number: str
    tipo: str
    descripcion: str
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    notas: Optional[str] = None
    meses_garantia_default: Optional[int] = None


# --- Equipo ---
class EquipoCreate(BaseModel):
    numero_serie: str
    producto_id: int
    cliente_id: Optional[int] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: Literal["operativo", "baja"] = "operativo"
    notas: Optional[str] = None
    meses_garantia: Optional[int] = None
    version: Optional[str] = None


class EquipoUpdate(BaseModel):
    cliente_id: Optional[int] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: Optional[Literal["operativo", "baja"]] = None
    notas: Optional[str] = None
    meses_garantia: Optional[int] = None
    version: Optional[str] = None


class EquipoOut(_ORM):
    id: int
    numero_serie: str
    producto_id: int
    cliente_id: Optional[int] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: str
    notas: Optional[str] = None
    meses_garantia: Optional[int] = None
    version: Optional[str] = None
    fecha_fin_garantia: Optional[date] = None
    estado_garantia: Optional[str] = None


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
    incidencia_id: Optional[int] = None


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
    incidencia_id: Optional[int] = None


class DesmontarPayload(BaseModel):
    fecha: date
    motivo: Literal["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"]
    usuario: Optional[str] = None
    notas: Optional[str] = None
    incidencia_id: Optional[int] = None


class SustituirPayload(BaseModel):
    componente_saliente_id: int
    componente_entrante_id: int
    posicion: Optional[str] = None
    fecha: date
    motivo: Literal["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"] = "sustitucion"
    usuario: Optional[str] = None
    notas: Optional[str] = None
    incidencia_id: Optional[int] = None


class SustitucionOut(BaseModel):
    desmontaje: CambioConfiguracionOut
    montaje: CambioConfiguracionOut


# --- Ficha y búsqueda ---
class EquipoFicha(_ORM):
    equipo: EquipoOut
    producto: ProductoOut
    cliente: Optional[ClienteOut] = None
    ubicacion_actual: Optional[UbicacionOut] = None
    componentes: list[ComponenteOut] = []
    historial_movimientos: list[MovimientoOut] = []
    historial_configuracion: list[CambioConfiguracionOut] = []
    incidencias: list["IncidenciaOut"] = []


class ResultadoBusqueda(BaseModel):
    tipo: Literal["equipo", "componente", "ninguno"]
    equipo: Optional[EquipoOut] = None
    componente: Optional[ComponenteOut] = None
    equipo_del_componente: Optional[EquipoOut] = None


# --- Incidencia ---
_PRIORIDAD = Literal["baja", "media", "alta"]
_ESTADO_INC = Literal["abierta", "diagnostico", "en_reparacion", "resuelta", "cerrada"]


class IncidenciaCreate(BaseModel):
    equipo_id: Optional[int] = None
    componente_id: Optional[int] = None
    titulo: str
    descripcion_problema: str
    prioridad: _PRIORIDAD = "media"
    asignado_a: Optional[str] = None
    en_garantia: Optional[bool] = None
    fecha_apertura: date
    tipo: Literal["rma", "soporte_venta", "soporte_tecnico", "calibracion"] = "rma"

    @model_validator(mode="after")
    def _al_menos_un_sujeto(self) -> "IncidenciaCreate":
        if self.equipo_id is None and self.componente_id is None:
            raise ValueError("La incidencia requiere equipo_id o componente_id (al menos uno)")
        return self


class IncidenciaUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion_problema: Optional[str] = None
    prioridad: Optional[_PRIORIDAD] = None
    asignado_a: Optional[str] = None
    en_garantia: Optional[bool] = None
    diagnostico: Optional[str] = None
    resolucion: Optional[str] = None
    notas: Optional[str] = None
    tipo: Optional[Literal["rma", "soporte_venta", "soporte_tecnico", "calibracion"]] = None


class IncidenciaOut(_ORM):
    id: int
    codigo: str
    tipo: str
    equipo_id: Optional[int] = None
    componente_id: Optional[int] = None
    titulo: str
    descripcion_problema: str
    prioridad: str
    estado: str
    asignado_a: Optional[str] = None
    en_garantia: Optional[bool] = None
    diagnostico: Optional[str] = None
    resolucion: Optional[str] = None
    fecha_apertura: date
    fecha_diagnostico: Optional[date] = None
    fecha_inicio_reparacion: Optional[date] = None
    fecha_resolucion: Optional[date] = None
    fecha_cierre: Optional[date] = None
    notas: Optional[str] = None


class TransicionPayload(BaseModel):
    nuevo_estado: _ESTADO_INC
    fecha: Optional[date] = None


class IncidenciaFicha(_ORM):
    incidencia: IncidenciaOut
    equipo: Optional[EquipoOut] = None
    componente: Optional[ComponenteOut] = None
    cliente: Optional[ClienteOut] = None
    cambios_configuracion: list[CambioConfiguracionOut] = []
    movimientos: list[MovimientoOut] = []


EquipoFicha.model_rebuild()


# --- Mapa ---
class MapaClienteRef(BaseModel):
    id: int
    nombre: str


class MapaEquipoOut(BaseModel):
    id: int
    numero_serie: str
    producto: str
    estado: str


class MapaUbicacionOut(BaseModel):
    ubicacion_id: int
    nombre: str
    tipo: str
    ciudad: Optional[str] = None
    provincia: Optional[str] = None
    pais: Optional[str] = None
    latitud: float
    longitud: float
    cliente: Optional[MapaClienteRef] = None
    num_equipos: int
    equipos: list[MapaEquipoOut] = []
