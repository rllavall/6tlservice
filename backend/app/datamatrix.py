"""Parseo puro de codigos DataMatrix de componentes (sin BD).

El lector (teclado-wedge) entrega la cadena ya decodificada. Aqui extraemos
`pn` (part number de fabricante) y `sn` (numero de serie) por capas: regla regex
por fabricante -> GS1 (Application Identifiers) -> crudo (la cadena como SN).
"""
from __future__ import annotations

import re

_PLACEHOLDER_PREFIJO = "S/N pendiente"
_GS = "\x1d"  # separador de grupo GS1 (FNC1)
_PREFIJOS_SIMBOLOGIA = ("]d2", "]C1", "]e0")

# AIs de longitud fija que nos interesan: AI -> (longitud_dato, clave)
_AI_FIJOS = {"01": (14, "pn")}
# AIs de longitud variable que nos interesan: AI -> clave
_AI_VARIABLES = {"21": "sn", "240": "pn", "10": "sn"}


def es_serie_placeholder(s: str | None) -> bool:
    """True si el numero de serie es un placeholder de alta (aun sin serial real)."""
    return bool(s) and s.startswith(_PLACEHOLDER_PREFIJO)


def _quitar_prefijo_simbologia(raw: str) -> str:
    for p in _PREFIJOS_SIMBOLOGIA:
        if raw.startswith(p):
            return raw[len(p):]
    return raw


def parsear_gs1(raw: str) -> dict:
    """Interpreta una cadena GS1 DataMatrix. Devuelve {pn, sn, formato='gs1'}.
    Campos variables terminan en GS (\\x1d) o al final de la cadena."""
    out = {"pn": None, "sn": None, "formato": "gs1"}
    s = _quitar_prefijo_simbologia(raw)
    i = 0
    n = len(s)
    while i < n:
        if s[i] == _GS:
            i += 1
            continue
        ai2 = s[i:i + 2]
        ai3 = s[i:i + 3]
        if ai2 in _AI_FIJOS:
            longitud, clave = _AI_FIJOS[ai2]
            dato = s[i + 2:i + 2 + longitud]
            if out.get(clave) is None:
                out[clave] = dato or None
            i += 2 + longitud
        elif ai3 in _AI_VARIABLES or ai2 in _AI_VARIABLES:
            ai = ai3 if ai3 in _AI_VARIABLES else ai2
            clave = _AI_VARIABLES[ai]
            j = s.find(_GS, i + len(ai))
            if j == -1:
                j = n
            dato = s[i + len(ai):j]
            if out.get(clave) is None:
                out[clave] = dato or None
            i = j + 1
        else:
            break
    return out


def parsear_con_regla(raw: str, regla: str) -> dict | None:
    """Aplica una regex con grupos nombrados pn/sn. None si no compila o no casa.
    La regla la define un operario autenticado (Fabricante.regla_datamatrix); debe ser
    un patrón razonable (sin backtracking catastrófico), no entrada de usuario anónimo."""
    try:
        patron = re.compile(regla)
    except re.error:
        return None
    m = patron.search(raw)
    if m is None:
        return None
    grupos = m.groupdict()
    return {"pn": grupos.get("pn") or None, "sn": grupos.get("sn") or None, "formato": "regla"}


def parsear(raw: str, reglas: list[str]) -> dict:
    """Capas: reglas (primer match con pn o sn) -> GS1 -> crudo (sn=raw)."""
    raw = (raw or "").strip()
    for regla in reglas:
        r = parsear_con_regla(raw, regla)
        if r and (r["pn"] or r["sn"]):
            return r
    g = parsear_gs1(raw)
    if g["pn"] or g["sn"]:
        return g
    return {"pn": None, "sn": raw or None, "formato": "crudo"}
