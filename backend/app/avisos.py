"""Lógica pura de avisos de servicio (preventivo + caducidad de contrato).
No importa models: opera por duck-typing y con `hoy` inyectable."""
from __future__ import annotations

from datetime import date, timedelta

from app import contratos
from app.garantia import _add_months

UMBRAL_PREVENTIVO_DIAS = 30
UMBRAL_CONTRATO_DIAS = 60


def dias_restantes(fecha: date, hoy: date) -> int:
    return (fecha - hoy).days


def clasificar(proxima: date, hoy: date, umbral: int = UMBRAL_PREVENTIVO_DIAS) -> str:
    if proxima < hoy:
        return "vencido"
    if proxima <= hoy + timedelta(days=umbral):
        return "proximo"
    return "al_dia"


def proxima_fecha_equipo(equipo, contrato, ultima_accion, hoy: date) -> date:
    """Próxima fecha de preventivo. `ultima_accion` puede ser None (nunca revisado)."""
    meses = contratos.NIVELES[contrato.nivel]["preventivo_meses"]
    if ultima_accion is not None:
        if getattr(ultima_accion, "proxima_fecha", None) is not None:
            return ultima_accion.proxima_fecha
        return _add_months(ultima_accion.fecha, meses)
    return _add_months(contrato.fecha_inicio, meses)


def contrato_por_caducar(contrato, hoy: date, umbral: int = UMBRAL_CONTRATO_DIAS) -> bool:
    if not contratos.esta_vigente(contrato, hoy):
        return False
    return contrato.fecha_fin <= hoy + timedelta(days=umbral)
