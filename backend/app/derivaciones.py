"""Lógica pura de transiciones de estado de una derivación (RMA externo /
flujo interno). Una derivación avanza por etapas, sin saltos ni retrocesos."""
from __future__ import annotations

ORDEN = ["pendiente", "enviada", "en_proveedor", "recibida", "cerrada"]


def transicion_valida(actual: str, nuevo: str) -> bool:
    """True si `nuevo` es la misma etapa o la inmediatamente siguiente."""
    if actual not in ORDEN or nuevo not in ORDEN:
        return False
    delta = ORDEN.index(nuevo) - ORDEN.index(actual)
    return delta in (0, 1)
