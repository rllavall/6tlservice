from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

TIPOS_UBICACION = ["fabrica_cliente", "sede_6tl", "en_reparacion", "en_transito"]
TIPOS_PRODUCTO = ["equipo", "componente"]
ESTADOS_EQUIPO = ["operativo", "baja"]
MOTIVOS_MOVIMIENTO = ["entrega", "traslado", "reparacion", "devolucion"]
ACCIONES_CONFIG = ["montaje", "desmontaje"]
MOTIVOS_CONFIG = ["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"]
ESTADOS_INCIDENCIA = ["abierta", "diagnostico", "en_reparacion", "resuelta", "cerrada"]
PRIORIDADES_INCIDENCIA = ["baja", "media", "alta"]
ESTADOS_GARANTIA_FAB = ["no_aplica", "pendiente_activacion", "activada", "rechazada"]
TIPOS_DERIVACION = ["externa_fabricante", "interna_departamento"]
ESTADOS_DERIVACION = ["pendiente", "enviada", "en_proveedor", "recibida", "cerrada"]


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String)
    cif: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    persona_contacto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email_contacto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    telefono_contacto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Ubicacion(Base):
    __tablename__ = "ubicaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String)
    tipo: Mapped[str] = mapped_column(String)
    cliente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clientes.id"), nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    codigo_postal: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ciudad: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    provincia: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pais: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    latitud: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitud: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
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
    meses_garantia_default: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=24)
    categoria: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pn_fabricante: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fabricante_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fabricantes.id"), nullable=True)
    categoria_componente: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    estado_ciclo_vida: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ciclo_vida_fecha: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ciclo_vida_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ciclo_vida_resumen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ciclo_vida_verificado_en: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ciclo_vida_cita: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Equipo(Base):
    __tablename__ = "equipos"
    __table_args__ = (UniqueConstraint("producto_id", "numero_serie", name="uq_equipo_serie"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_serie: Mapped[str] = mapped_column(String)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cliente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clientes.id"), nullable=True)
    fecha_fabricacion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_entrega: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(String, default="operativo")
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    meses_garantia: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    numero_serie_cliente: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    contrato_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contratos.id"), nullable=True)

    producto: Mapped["Producto"] = relationship()
    componentes: Mapped[list["Componente"]] = relationship(back_populates="equipo")
    contrato: Mapped[Optional["ContratoMantenimiento"]] = relationship(back_populates="equipos")

    @property
    def fecha_fin_garantia(self):
        from app import garantia
        return garantia.fecha_fin_garantia(self)

    @property
    def estado_garantia(self) -> str:
        from datetime import date as _date
        from app import garantia
        return garantia.estado_garantia(self, _date.today())

    @property
    def bajo_contrato(self) -> bool:
        from datetime import date as _date
        from app import contratos
        return self.contrato is not None and contratos.esta_vigente(self.contrato, _date.today())

    @property
    def categoria(self):
        return self.producto.categoria if self.producto is not None else None


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

    @property
    def categoria(self):
        return self.producto.categoria if self.producto is not None else None

    @property
    def categoria_componente(self):
        return self.producto.categoria_componente if self.producto is not None else None


class Movimiento(Base):
    __tablename__ = "movimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    ubicacion_destino_id: Mapped[int] = mapped_column(ForeignKey("ubicaciones.id"))
    fecha: Mapped[date] = mapped_column(Date)
    motivo: Mapped[str] = mapped_column(String)
    usuario: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    incidencia_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidencias.id"), nullable=True)

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
    incidencia_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidencias.id"), nullable=True)

    componente: Mapped["Componente"] = relationship()


class Incidencia(Base):
    __tablename__ = "incidencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String, unique=True)
    tipo: Mapped[str] = mapped_column(String, default="rma")
    equipo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipos.id"), nullable=True)
    componente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("componentes.id"), nullable=True)
    titulo: Mapped[str] = mapped_column(String)
    descripcion_problema: Mapped[str] = mapped_column(String)
    prioridad: Mapped[str] = mapped_column(String, default="media")
    estado: Mapped[str] = mapped_column(String, default="abierta")
    asignado_a: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    en_garantia: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    diagnostico: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resolucion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha_apertura: Mapped[date] = mapped_column(Date)
    fecha_diagnostico: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_inicio_reparacion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_resolucion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_cierre: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    creada_en: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now, nullable=True)
    respondida_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resuelta_en: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class AvanceIncidencia(Base):
    __tablename__ = "avances_incidencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incidencia_id: Mapped[int] = mapped_column(ForeignKey("incidencias.id"))
    fecha: Mapped[date] = mapped_column(Date)
    autor: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tipo: Mapped[str] = mapped_column(String, default="avance")
    texto: Mapped[str] = mapped_column(String)


class SolicitudSoporte(Base):
    __tablename__ = "solicitudes_soporte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String, unique=True)
    estado: Mapped[str] = mapped_column(String, default="pendiente")
    fecha_solicitud: Mapped[date] = mapped_column(Date)
    nombre_contacto: Mapped[str] = mapped_column(String)
    empresa: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email_contacto: Mapped[str] = mapped_column(String)
    telefono_contacto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    numero_serie_texto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    part_number_texto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    titulo: Mapped[str] = mapped_column(String)
    descripcion_problema: Mapped[str] = mapped_column(String)
    incidencia_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidencias.id"), nullable=True)
    motivo_rechazo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha_resolucion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class ContratoMantenimiento(Base):
    __tablename__ = "contratos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String, unique=True)
    cliente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clientes.id"), nullable=True)
    nivel: Mapped[str] = mapped_column(String)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    cancelado: Mapped[bool] = mapped_column(Boolean, default=False)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    equipos: Mapped[list["Equipo"]] = relationship(back_populates="contrato")

    @property
    def estado(self) -> str:
        from datetime import date as _date
        from app import contratos
        return contratos.estado_contrato(self, _date.today())

    @property
    def vigente(self) -> bool:
        return self.estado == "vigente"

    @property
    def nivel_detalle(self):
        from app import contratos
        return contratos.nivel_detalle(self.nivel)


class AccionPreventiva(Base):
    __tablename__ = "acciones_preventivo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    contrato_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contratos.id"), nullable=True)
    fecha: Mapped[date] = mapped_column(Date)
    tecnico: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tipo: Mapped[str] = mapped_column(String)               # on_site | remoto
    veredicto: Mapped[str] = mapped_column(String)          # ok | con_observaciones | requiere_accion
    informe: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    proxima_fecha: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    incidencia_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidencias.id"), nullable=True)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    nombre: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    rol: Mapped[str] = mapped_column(String, default="admin")
    fecha_alta: Mapped[date] = mapped_column(Date)


class Sesion(Base):
    __tablename__ = "sesiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime)
    fecha_expiracion: Mapped[datetime] = mapped_column(DateTime)

    usuario: Mapped["Usuario"] = relationship()


class AuditoriaLog(Base):
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime)
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    usuario_username: Mapped[str] = mapped_column(String)
    entidad: Mapped[str] = mapped_column(String)
    entidad_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    accion: Mapped[str] = mapped_column(String)
    cambios: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AyudaTopico(Base):
    __tablename__ = "ayuda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave: Mapped[str] = mapped_column(String, unique=True, index=True)
    titulo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    texto: Mapped[str] = mapped_column(String)
    pantalla: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Fabricante(Base):
    __tablename__ = "fabricantes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, unique=True)
    email_service: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email_rma: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    url_activacion_garantia: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    requiere_activacion_web: Mapped[bool] = mapped_column(Boolean, default=False)
    politica_rma: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    url_obsolescencia: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class GarantiaFabricante(Base):
    __tablename__ = "garantias_fabricante"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    componente_id: Mapped[int] = mapped_column(ForeignKey("componentes.id"), unique=True)
    fabricante_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fabricantes.id"), nullable=True)
    estado: Mapped[str] = mapped_column(String, default="pendiente_activacion")
    fecha_solicitud: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_activacion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    meses_garantia: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    referencia_fabricante: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    responsable: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    @property
    def fecha_fin(self):
        from app import garantia_fabricante
        return garantia_fabricante.fecha_fin(self)

    @property
    def estado_cobertura(self) -> str:
        from datetime import date as _date
        from app import garantia_fabricante
        return garantia_fabricante.estado_cobertura(self, _date.today())


class Derivacion(Base):
    __tablename__ = "derivaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incidencia_id: Mapped[int] = mapped_column(ForeignKey("incidencias.id"))
    tipo: Mapped[str] = mapped_column(String)
    fabricante_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fabricantes.id"), nullable=True)
    departamento: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tu_referencia: Mapped[str] = mapped_column(String, unique=True)
    referencia_externa: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    estado: Mapped[str] = mapped_column(String, default="pendiente")
    fecha_creacion: Mapped[date] = mapped_column(Date)
    fecha_envio: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_cierre: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class NoticiaObsolescencia(Base):
    __tablename__ = "noticias_obsolescencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    fecha_deteccion: Mapped[date] = mapped_column(Date)
    estado_anterior: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String)
    fecha_evento: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    url_fuente: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resumen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cita: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notificado: Mapped[bool] = mapped_column(Boolean, default=False)
