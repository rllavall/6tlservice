"""Derivación pura: criticidad y nivel de trazabilidad de un componente.

Aplica las conclusiones de trazabilidad en entornos ATE (ver spec). Funciona sobre
cualquier objeto con los atributos `categoria_componente`, `afecta_a_medida`,
`bajo_coste` y `nivel_trazabilidad_override` (Producto, o un duck-type en tests).
Sin BD: lo consumen las propiedades del modelo y los schemas.
"""
from __future__ import annotations

CRITICIDADES = ("alta", "media", "baja")
NIVELES = ("serie", "version", "no_trazado")

# Categorías que, por naturaleza, son de alta criticidad.
_CAT_VERSION = {"software", "fixture_adaptador"}   # se controlan por versión/revisión
_CAT_SERIE_ALTA = {"instrumento", "mass_interconnect"}  # afectan a medida -> serie


def criticidad(producto) -> str:
    """alta | media | baja. El override de nivel NO altera la criticidad."""
    if getattr(producto, "afecta_a_medida", False):
        return "alta"
    cat = getattr(producto, "categoria_componente", None)
    if cat in _CAT_VERSION or cat in _CAT_SERIE_ALTA:
        return "alta"
    if getattr(producto, "bajo_coste", False):
        return "baja"
    return "media"


def nivel_trazabilidad(producto) -> str:
    """serie | version | no_trazado. El override (si no vacío) gana sobre la cascada."""
    override = getattr(producto, "nivel_trazabilidad_override", None)
    if override:
        return override
    if getattr(producto, "afecta_a_medida", False):
        return "serie"
    cat = getattr(producto, "categoria_componente", None)
    if cat in _CAT_VERSION:
        return "version"
    if cat in _CAT_SERIE_ALTA:
        return "serie"
    if getattr(producto, "bajo_coste", False):
        return "no_trazado"
    return "serie"
