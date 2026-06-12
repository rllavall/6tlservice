"""Lógica pura del ciclo de vida de productos (obsolescencia). Sin BD ni IO."""
from __future__ import annotations

from typing import Optional

ESTADOS = ["activo", "nrnd", "eol_anunciado", "ultima_compra", "obsoleto"]
SEVERIDAD = {e: i for i, e in enumerate(ESTADOS)}


def estado_valido(estado: Optional[str]) -> bool:
    return estado in SEVERIDAD


def severidad(estado: Optional[str]) -> int:
    """Severidad 0..4. Estado None/desconocido = 0 (línea base 'activo')."""
    return SEVERIDAD.get(estado, 0)


def requiere_url(estado: Optional[str]) -> bool:
    """Cualquier estado distinto de 'activo' debe traer fuente (anti-alucinación)."""
    return estado_valido(estado) and estado != "activo"


def es_cambio_notable(anterior: Optional[str], nuevo: Optional[str]) -> bool:
    """True solo si `nuevo` es válido y empeora (mayor severidad) respecto a `anterior`."""
    if not estado_valido(nuevo):
        return False
    return severidad(nuevo) > severidad(anterior)


def validar_hallazgo(estado: Optional[str], url: Optional[str]) -> None:
    """Lanza ValueError si el estado no es válido o si un no-'activo' viene sin url."""
    if not estado_valido(estado):
        raise ValueError(f"estado de ciclo de vida no válido: {estado!r}")
    if requiere_url(estado) and not url:
        raise ValueError(f"el estado {estado!r} requiere una url de fuente")
