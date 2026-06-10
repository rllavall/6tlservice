"""Lógica pura de procedimiento por fabricante. Duck-typed: opera sobre
atributos (`email_service`, `email_rma`, `requiere_activacion_web`) y tolera None."""
from __future__ import annotations

from typing import Optional


def destino_activacion(fabricante) -> Optional[str]:
    """Email al que se pide la activación de garantía (None si no hay)."""
    if fabricante is None:
        return None
    return getattr(fabricante, "email_service", None)


def destino_rma(fabricante) -> Optional[str]:
    """Email para RMA; cae al de service si no hay uno específico."""
    if fabricante is None:
        return None
    return getattr(fabricante, "email_rma", None) or getattr(fabricante, "email_service", None)


def requiere_web(fabricante) -> bool:
    """True si la marca exige activar la garantía en su web."""
    if fabricante is None:
        return False
    return bool(getattr(fabricante, "requiere_activacion_web", False))
