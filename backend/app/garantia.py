"""Lógica pura de garantía. No importa models: opera por duck-typing
(`equipo.fecha_entrega`, `equipo.meses_garantia`) y con `hoy`/`fecha` inyectables."""
from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

UMBRAL_POR_VENCER_DIAS = 90


def _add_months(d: date, months: int) -> date:
    m0 = d.month - 1 + months
    y = d.year + m0 // 12
    m = m0 % 12 + 1
    ultimo = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, ultimo))


def fecha_fin_garantia(equipo) -> Optional[date]:
    entrega = getattr(equipo, "fecha_entrega", None)
    meses = getattr(equipo, "meses_garantia", None)
    if entrega is None or meses is None:
        return None
    return _add_months(entrega, meses)


def estado_garantia(equipo, hoy: date, umbral_dias: int = UMBRAL_POR_VENCER_DIAS) -> str:
    fin = fecha_fin_garantia(equipo)
    if fin is None:
        return "sin_datos"
    if hoy > fin:
        return "vencida"
    if (fin - hoy).days <= umbral_dias:
        return "por_vencer"
    return "vigente"


def equipo_en_garantia(equipo, fecha: date) -> Optional[bool]:
    fin = fecha_fin_garantia(equipo)
    if fin is None:
        return None
    return fecha <= fin
