"""Lógica pura de la garantía del fabricante (a nivel componente). Duck-typed
sobre `fecha_activacion` y `meses_garantia`; `hoy` inyectable."""
from __future__ import annotations

from datetime import date
from typing import Optional

from app.garantia import _add_months

UMBRAL_POR_VENCER_DIAS = 90


def fecha_fin(garantia) -> Optional[date]:
    inicio = getattr(garantia, "fecha_activacion", None)
    meses = getattr(garantia, "meses_garantia", None)
    if inicio is None or meses is None:
        return None
    return _add_months(inicio, meses)


def estado_cobertura(garantia, hoy: date, umbral_dias: int = UMBRAL_POR_VENCER_DIAS) -> str:
    fin = fecha_fin(garantia)
    if fin is None:
        return "sin_activar"
    if hoy > fin:
        return "vencida"
    if (fin - hoy).days <= umbral_dias:
        return "por_vencer"
    return "vigente"
