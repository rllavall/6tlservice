"""Lógica pura de contratos de mantenimiento. No importa models: opera por
duck-typing (`contrato.fecha_inicio/fecha_fin/cancelado/nivel`) y con `hoy` inyectable."""
from __future__ import annotations

from datetime import date
from typing import Optional

from app.garantia import _add_months

# Atributos derivados de cada nivel de servicio (propuesta iUTB INDRA).
NIVELES: dict[str, dict] = {
    "bronze": {"preventivo": "anual", "soporte": "horario_laborable", "respuesta": "estandar", "preventivo_meses": 12},
    "silver": {"preventivo": "semestral", "soporte": "horario_laborable", "respuesta": "mejorada", "preventivo_meses": 6},
    "gold": {"preventivo": "semestral", "soporte": "24/7", "respuesta": "prioritaria", "preventivo_meses": 6},
}


def estado_contrato(contrato, hoy: date) -> str:
    if getattr(contrato, "cancelado", False):
        return "cancelado"
    if hoy < contrato.fecha_inicio:
        return "pendiente"
    if hoy <= contrato.fecha_fin:
        return "vigente"
    return "vencido"


def esta_vigente(contrato, hoy: date) -> bool:
    return estado_contrato(contrato, hoy) == "vigente"


def nivel_detalle(nivel: Optional[str]) -> Optional[dict]:
    detalle = NIVELES.get(nivel) if nivel else None
    return dict(detalle) if detalle is not None else None  # copia: no exponer la constante por referencia


def sugerir_proxima_fecha(fecha: date, nivel: Optional[str]) -> Optional[date]:
    detalle = NIVELES.get(nivel) if nivel else None
    if detalle is None:
        return None
    return _add_months(fecha, detalle["preventivo_meses"])
