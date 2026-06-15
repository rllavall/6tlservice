"""Motor de reglas puro: decide afecta_a_medida / bajo_coste de un componente.

Sin BD. Lee solo categoria_componente, fabricante, descripcion, part_number.
Marca `ambiguo=True` cuando las señales son débiles o en conflicto, para que un
agente LLM resuelva ese residuo (ver app/clasificacion_llm.py).
"""
from __future__ import annotations

from dataclasses import dataclass

# Marcas de instrumentación (sub-cadena del fabricante, case-insensitive).
# Espejo de _INSTRUMENTO_SUBSTR del clasificador de categoría.
_INSTRUMENTO_SUBSTR = (
    "keysight", "agilent", "national instruments", "pickering",
    "chroma", "ametek", "hocherl", "hoecherl", "höcherl", "rohde", "tektronix",
)
# Señales de que el elemento está en la cadena de medida.
_MEDIDA_KW = (
    "sense", "sonda", "probe", "referencia", "reference", "calibr", "precis",
    "sensor", "medida", "measurement", "dmm", "shunt", "termopar",
    "thermocouple", "rtd", "kelvin",
)
# Señales de estándar barato / no trazable individualmente.
_BARATO_KW = (
    "tornillo", "screw", "etiqueta", "label", "brida", "bracket", "soporte",
    "tapa", "cover", "patch", "latiguillo", "generic", "generico", "genérico",
    "standard", "estandar", "estándar",
)
_CAT_AFECTA = {"instrumento", "mass_interconnect"}
_CAT_VERSION = {"software", "fixture_adaptador"}
_CAT_GENERICA = {"wiring", "accesorios"}


@dataclass
class ResultadoClasificacion:
    afecta_a_medida: bool
    bajo_coste: bool
    ambiguo: bool
    motivo: str


def _tiene(texto: str, palabras) -> bool:
    t = (texto or "").lower()
    return any(p in t for p in palabras)


def clasificar_por_reglas(categoria_componente, fabricante, descripcion,
                          part_number) -> ResultadoClasificacion:
    desc = descripcion or ""
    fab = (fabricante or "").strip().lower()
    es_instr_marca = any(s in fab for s in _INSTRUMENTO_SUBSTR) or fab == "ni"
    medida = _tiene(desc, _MEDIDA_KW)
    barato = _tiene(desc, _BARATO_KW)

    # Categorías que la propia categoría ya resuelve sin flags.
    if categoria_componente in _CAT_VERSION:
        return ResultadoClasificacion(False, False, False,
                                      f"categoria {categoria_componente}: por version")
    if categoria_componente in _CAT_AFECTA:
        return ResultadoClasificacion(True, False, False,
                                      f"categoria {categoria_componente}: afecta a medida")

    # Señal léxica fuerte de medida gana sobre todo.
    if medida:
        return ResultadoClasificacion(True, False, False, "descripcion indica cadena de medida")

    # Conflicto: marca cara pero descripción de accesorio barato -> que decida el LLM.
    if es_instr_marca and barato:
        return ResultadoClasificacion(False, True, True,
                                      "marca de instrumentacion con descripcion barata (conflicto)")

    if barato:
        return ResultadoClasificacion(False, True, False, "descripcion de estandar barato")

    # Genéricas sin pista, o categoría nula -> ambiguo (LLM), default conservador media.
    if categoria_componente in _CAT_GENERICA or not categoria_componente:
        return ResultadoClasificacion(False, False, True,
                                      "sin senal decisiva; requiere revision")

    return ResultadoClasificacion(False, False, False, "sin senales especiales: media")
