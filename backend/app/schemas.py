from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
_CATEGORIA = Literal["ate", "yav_module", "fastate_module", "test_fixture", "test_handler", "otro"]
_CATEGORIA_COMPONENTE = Literal["instrumento", "mass_interconnect", "wiring", "accesorios"]
_ESTADO_CICLO = Literal["activo", "nrnd", "eol_anunciado", "ultima_compra", "obsoleto"]


class ProductoCreate(BaseModel):
    part_number: str
    tipo: Literal["equipo", "componente"]
    descripcion: str
    fabricante: Optional[str] = None
    fabricante_id: Optional[int] = None
    modelo: Optional[str] = None
    notas: Optional[str] = None
    meses_garantia_default: Optional[int] = 24
    categoria: Optional[_CATEGORIA] = None
    pn_fabricante: Optional[str] = None
    categoria_componente: Optional[_CATEGORIA_COMPONENTE] = None


class ProductoOut(_ORM):
    id: int
    part_number: str
    tipo: str
    descripcion: str
    fabricante: Optional[str] = None
    fabricante_id: Optional[int] = None
    modelo: Optional[str] = None
    notas: Optional[str] = None
    meses_garantia_default: Optional[int] = None
    categoria: Optional[str] = None
    pn_fabricante: Optional[str] = None
    categoria_componente: Optional[str] = None
    estado_ciclo_vida: Optional[str] = None
    ciclo_vida_fecha: Optional[date] = None
    ciclo_vida_url: Optional[str] = None
    ciclo_vida_resumen: Optional[str] = None
    ciclo_vida_verificado_en: Optional[date] = None


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
    numero_serie_cliente: Optional[str] = None


class EquipoUpdate(BaseModel):
    cliente_id: Optional[int] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: Optional[Literal["operativo", "baja"]] = None
    notas: Optional[str] = None
    meses_garantia: Optional[int] = None
    version: Optional[str] = None
    numero_serie_cliente: Optional[str] = None


# --- Alta de equipo (wizard) ---
class EquipoAltaComponente(BaseModel):
    producto_id: int
    numero_serie: str
    posicion: Optional[str] = None
    notas: Optional[str] = None


class EquipoAltaCreate(BaseModel):
    numero_serie: str
    producto_id: int
    cliente_id: Optional[int] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: Literal["operativo", "baja"] = "operativo"
    notas: Optional[str] = None
    meses_garantia: Optional[int] = None
    version: Optional[str] = None
    numero_serie_cliente: Optional[str] = None
    ubicacion_id: Optional[int] = None
    movimiento_fecha: Optional[date] = None
    movimiento_notas: Optional[str] = None
    componentes: list[EquipoAltaComponente] = Field(default_factory=list)


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
    numero_serie_cliente: Optional[str] = None
    fecha_fin_garantia: Optional[date] = None
    estado_garantia: Optional[Literal["vigente", "por_vencer", "vencida", "sin_datos"]] = None
    categoria: Optional[str] = None
    bajo_contrato: bool = False
    contrato: Optional["ContratoResumen"] = None


# --- Componente ---
class ComponenteCreate(BaseModel):
    numero_serie: str
    producto_id: int
    equipo_id: Optional[int] = None
    posicion: Optional[str] = None
    fecha_montaje: Optional[date] = None
    notas: Optional[str] = None


class ComponenteUpdate(BaseModel):
    numero_serie: Optional[str] = None
    posicion: Optional[str] = None
    notas: Optional[str] = None


class ComponenteOut(_ORM):
    id: int
    numero_serie: str
    producto_id: int
    equipo_id: Optional[int] = None
    posicion: Optional[str] = None
    fecha_montaje: Optional[date] = None
    notas: Optional[str] = None
    categoria: Optional[str] = None
    categoria_componente: Optional[str] = None


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
    creada_en: Optional[datetime] = None
    respondida_en: Optional[datetime] = None
    resuelta_en: Optional[datetime] = None


class TransicionPayload(BaseModel):
    nuevo_estado: _ESTADO_INC
    fecha: Optional[date] = None


# --- Avances de incidencia (bitácora) ---
_TIPO_AVANCE = Literal["avance", "report", "llamada", "visita", "diagnostico", "otro"]


class AvanceCreate(BaseModel):
    fecha: Optional[date] = None   # el router pone hoy si no se envía
    autor: Optional[str] = None
    tipo: _TIPO_AVANCE = "avance"
    texto: str = Field(min_length=1)


class AvanceUpdate(BaseModel):
    fecha: Optional[date] = None
    autor: Optional[str] = None
    tipo: Optional[_TIPO_AVANCE] = None
    texto: Optional[str] = Field(default=None, min_length=1)


class AvanceOut(_ORM):
    id: int
    incidencia_id: int
    fecha: date
    autor: Optional[str] = None
    tipo: str
    texto: str


class IncidenciaFicha(_ORM):
    incidencia: IncidenciaOut
    equipo: Optional[EquipoOut] = None
    componente: Optional[ComponenteOut] = None
    cliente: Optional[ClienteOut] = None
    cambios_configuracion: list[CambioConfiguracionOut] = []
    movimientos: list[MovimientoOut] = []
    avances: list[AvanceOut] = []
    sla: Optional["SlaIncidencia"] = None


# --- Analítica de incidencias ---
class ConteoItem(BaseModel):
    clave: str
    etiqueta: str
    valor: int


class KpiTiempoItem(BaseModel):
    clave: str
    etiqueta: str
    dias: Optional[float] = None
    n: int = 0


class KpiTiempo(BaseModel):
    mttr_dias: Optional[float] = None
    diagnostico_dias: Optional[float] = None
    edad_abiertas_dias: Optional[float] = None
    por_tipo: list[KpiTiempoItem] = []
    por_producto: list[KpiTiempoItem] = []
    por_tecnico: list[KpiTiempoItem] = []


class PuntoTendencia(BaseModel):
    mes: str  # YYYY-MM
    abiertas: int
    cerradas: int
    backlog: int


class RankingItem(BaseModel):
    id: Optional[int] = None
    etiqueta: str
    valor: int


class ResumenGarantia(BaseModel):
    equipos_por_estado: list[ConteoItem] = []
    rma_en_garantia: int = 0
    rma_fuera_garantia: int = 0
    rma_garantia_desconocida: int = 0


class AnaliticaIncidenciasOut(BaseModel):
    total: int
    por_tipo: list[ConteoItem] = []
    por_producto: list[ConteoItem] = []
    por_tecnico: list[ConteoItem] = []
    por_prioridad: list[ConteoItem] = []
    por_estado: list[ConteoItem] = []
    por_cliente: list[ConteoItem] = []
    kpis_tiempo: KpiTiempo = KpiTiempo()
    tendencia_mensual: list[PuntoTendencia] = []
    fiabilidad_productos: list[RankingItem] = []
    fiabilidad_equipos: list[RankingItem] = []
    garantia: ResumenGarantia = ResumenGarantia()


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


class ResumenServicioOut(BaseModel):
    incidencias_abiertas: int
    incidencias_abiertas_alta: int
    rma_abierto: int
    en_reparacion: int
    cerradas_30d: int
    tiempo_medio_cierre_dias: Optional[float] = None


# --- Solicitud de soporte (formulario público) ---
_TIPO_INC = Literal["rma", "soporte_venta", "soporte_tecnico", "calibracion"]
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SolicitudCreate(BaseModel):
    nombre_contacto: str = Field(min_length=1)
    empresa: Optional[str] = None
    email_contacto: str
    telefono_contacto: Optional[str] = None
    numero_serie_texto: Optional[str] = None
    part_number_texto: Optional[str] = None
    titulo: str = Field(min_length=1)
    descripcion_problema: str = Field(min_length=1)
    website: Optional[str] = None   # honeypot: debe venir vacío

    @field_validator("email_contacto")
    @classmethod
    def _email_valido(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("email no válido")
        return v


class SolicitudOut(_ORM):
    id: int
    codigo: str
    estado: str
    fecha_solicitud: date
    nombre_contacto: str
    empresa: Optional[str] = None
    email_contacto: str
    telefono_contacto: Optional[str] = None
    numero_serie_texto: Optional[str] = None
    part_number_texto: Optional[str] = None
    titulo: str
    descripcion_problema: str
    incidencia_id: Optional[int] = None
    motivo_rechazo: Optional[str] = None
    fecha_resolucion: Optional[date] = None


class AprobarSolicitudPayload(BaseModel):
    equipo_id: Optional[int] = None
    componente_id: Optional[int] = None
    tipo: _TIPO_INC = "rma"
    prioridad: _PRIORIDAD = "media"
    asignado_a: Optional[str] = None
    en_garantia: Optional[bool] = None

    @model_validator(mode="after")
    def _requiere_sujeto(self) -> "AprobarSolicitudPayload":
        if self.equipo_id is None and self.componente_id is None:
            raise ValueError("Indica equipo_id o componente_id (al menos uno)")
        return self


class RechazarSolicitudPayload(BaseModel):
    motivo: str = Field(min_length=1)


# --- Contratos de mantenimiento ---
_NIVEL = Literal["bronze", "silver", "gold"]
_ESTADO_CONTRATO = Literal["pendiente", "vigente", "vencido", "cancelado"]


class ContratoCreate(BaseModel):
    cliente_id: Optional[int] = None
    nivel: _NIVEL
    fecha_inicio: date
    fecha_fin: date
    notas: Optional[str] = None

    @model_validator(mode="after")
    def _fechas_coherentes(self) -> "ContratoCreate":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio")
        return self


class ContratoUpdate(BaseModel):
    cliente_id: Optional[int] = None
    nivel: Optional[_NIVEL] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    cancelado: Optional[bool] = None
    notas: Optional[str] = None

    @model_validator(mode="after")
    def _fechas_coherentes(self) -> "ContratoUpdate":
        if self.fecha_inicio is not None and self.fecha_fin is not None \
                and self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio")
        return self


class ContratoResumen(_ORM):
    id: int
    codigo: str
    nivel: str
    estado: _ESTADO_CONTRATO
    vigente: bool


class ContratoOut(_ORM):
    id: int
    codigo: str
    cliente_id: Optional[int] = None
    nivel: str
    fecha_inicio: date
    fecha_fin: date
    cancelado: bool
    notas: Optional[str] = None
    estado: _ESTADO_CONTRATO
    vigente: bool
    nivel_detalle: Optional[dict] = None


class ContratoDetalle(_ORM):
    contrato: ContratoOut
    cliente: Optional[ClienteOut] = None
    equipos: list[EquipoOut] = []


class AsignarEquipoPayload(BaseModel):
    equipo_id: int


EquipoOut.model_rebuild()
EquipoFicha.model_rebuild()


# --- Preventivo ---
_TIPO_PREV = Literal["on_site", "remoto"]
_VEREDICTO = Literal["ok", "con_observaciones", "requiere_accion"]


class AccionPreventivaCreate(BaseModel):
    fecha: date
    tipo: _TIPO_PREV
    veredicto: _VEREDICTO
    tecnico: Optional[str] = None
    informe: Optional[str] = None
    proxima_fecha: Optional[date] = None


class AccionPreventivaOut(_ORM):
    id: int
    equipo_id: int
    contrato_id: Optional[int] = None
    fecha: date
    tecnico: Optional[str] = None
    tipo: str
    veredicto: str
    informe: Optional[str] = None
    proxima_fecha: Optional[date] = None
    incidencia_id: Optional[int] = None


class GenerarIncidenciaPrevPayload(BaseModel):
    tipo: Literal["rma", "soporte_venta", "soporte_tecnico", "calibracion"] = "soporte_tecnico"
    prioridad: Literal["baja", "media", "alta"] = "media"
    asignado_a: Optional[str] = None


# --- Avisos de servicio ---
class AvisoPreventivo(_ORM):
    equipo: EquipoOut
    contrato: ContratoResumen
    proxima_fecha: date
    dias_restantes: int
    bucket: Literal["vencido", "proximo"]
    ultima_fecha: Optional[date] = None


class AvisoContrato(_ORM):
    contrato: ContratoResumen
    cliente: Optional[ClienteOut] = None
    fecha_fin: date
    dias_restantes: int


class ResumenAvisos(BaseModel):
    preventivos_vencidos: int
    preventivos_proximos: int
    contratos_por_caducar: int


class AvisosOut(_ORM):
    preventivos: list[AvisoPreventivo] = []
    contratos_por_caducar: list[AvisoContrato] = []
    resumen: ResumenAvisos


# --- Auth ---
class UsuarioOut(_ORM):
    id: int
    username: str
    nombre: str
    rol: str
    activo: bool


class LoginPayload(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    usuario: UsuarioOut


# --- Auditoría ---
class AuditoriaLogOut(_ORM):
    id: int
    fecha_hora: datetime
    usuario_id: Optional[int] = None
    usuario_username: str
    entidad: str
    entidad_id: Optional[int] = None
    accion: str
    cambios: Optional[str] = None


# --- Ayuda contextual ---
class AyudaOut(_ORM):
    clave: str
    titulo: Optional[str] = None
    texto: str
    pantalla: Optional[str] = None


class AyudaUpsert(BaseModel):
    titulo: Optional[str] = None
    texto: str = Field(min_length=1)
    pantalla: Optional[str] = None


# --- SLA ---
_ESTADO_SLA = Literal["en_plazo", "en_riesgo", "incumplido", "sin_sla"]


class SlaMetrica(BaseModel):
    objetivo: datetime
    real: Optional[datetime] = None
    horas_restantes: Optional[int] = None
    estado: _ESTADO_SLA


class SlaIncidencia(BaseModel):
    nivel: str
    respuesta: SlaMetrica
    resolucion: SlaMetrica
    estado_global: _ESTADO_SLA


class SlaIncidenciaItem(_ORM):
    incidencia: IncidenciaOut
    sla: SlaIncidencia


class CumplimientoSla(BaseModel):
    total: int
    respuesta_pct: Optional[float] = None
    resolucion_pct: Optional[float] = None


class ResumenSla(BaseModel):
    en_riesgo: int
    incumplidas: int


class SlaOut(BaseModel):
    cumplimiento: CumplimientoSla
    en_riesgo: list[SlaIncidenciaItem] = []
    incumplidas: list[SlaIncidenciaItem] = []
    resumen: ResumenSla


IncidenciaFicha.model_rebuild()


# --- Notificaciones ---
class DigestOut(BaseModel):
    asunto: str
    cuerpo: str
    resumen: dict
    total: int
    enviado: bool
    canales: Optional[dict] = None


# --- Motor de Fabricantes y RMA ---
class FabricanteCreate(BaseModel):
    nombre: str
    email_service: Optional[str] = None
    email_rma: Optional[str] = None
    url_activacion_garantia: Optional[str] = None
    requiere_activacion_web: bool = False
    politica_rma: Optional[str] = None
    notas: Optional[str] = None
    url_obsolescencia: Optional[str] = None


class FabricanteUpdate(BaseModel):
    nombre: Optional[str] = None
    email_service: Optional[str] = None
    email_rma: Optional[str] = None
    url_activacion_garantia: Optional[str] = None
    requiere_activacion_web: Optional[bool] = None
    politica_rma: Optional[str] = None
    notas: Optional[str] = None
    url_obsolescencia: Optional[str] = None


class FabricanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email_service: Optional[str] = None
    email_rma: Optional[str] = None
    url_activacion_garantia: Optional[str] = None
    requiere_activacion_web: bool
    politica_rma: Optional[str] = None
    notas: Optional[str] = None
    url_obsolescencia: Optional[str] = None


class GarantiaActivarPayload(BaseModel):
    meses_garantia: Optional[int] = None
    responsable: Optional[str] = None


class GarantiaConfirmarPayload(BaseModel):
    fecha_activacion: date
    referencia: Optional[str] = None


class GarantiaFabricanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    componente_id: int
    fabricante_id: Optional[int] = None
    estado: str
    fecha_solicitud: Optional[date] = None
    fecha_activacion: Optional[date] = None
    meses_garantia: Optional[int] = None
    referencia_fabricante: Optional[str] = None
    responsable: Optional[str] = None
    fecha_fin: Optional[date] = None
    estado_cobertura: str


class DerivacionCreate(BaseModel):
    tipo: str
    fabricante_id: Optional[int] = None
    departamento: Optional[str] = None
    notas: Optional[str] = None


class DerivacionUpdate(BaseModel):
    estado: Optional[str] = None
    referencia_externa: Optional[str] = None
    notas: Optional[str] = None


class DerivacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    incidencia_id: int
    tipo: str
    fabricante_id: Optional[int] = None
    departamento: Optional[str] = None
    tu_referencia: str
    referencia_externa: Optional[str] = None
    estado: str
    fecha_creacion: date
    fecha_envio: Optional[date] = None
    fecha_cierre: Optional[date] = None
    notas: Optional[str] = None


# --- Obsolescencia ---
class HallazgoObsolescencia(BaseModel):
    producto_id: int
    estado: _ESTADO_CICLO
    fecha_evento: Optional[date] = None
    url: Optional[str] = None
    resumen: Optional[str] = None


class ProductoARevisarOut(BaseModel):
    id: int
    fabricante: Optional[str] = None
    pn_fabricante: Optional[str] = None
    descripcion: str
    estado_ciclo_vida: Optional[str] = None
    url_obsolescencia: Optional[str] = None


class NoticiaObsolescenciaOut(_ORM):
    id: int
    producto_id: int
    fecha_deteccion: date
    estado_anterior: Optional[str] = None
    estado_nuevo: str
    fecha_evento: Optional[date] = None
    url_fuente: Optional[str] = None
    resumen: Optional[str] = None
    notificado: bool


class ObsolescenciaResumenOut(BaseModel):
    conteos: dict[str, int]
    sin_verificar: int
    noticias: list[NoticiaObsolescenciaOut] = Field(default_factory=list)
