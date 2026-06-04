"""Geocodificación de ubicaciones vía Nominatim (OpenStreetMap, gratis).

El `fetch` es inyectable para que los tests no toquen la red.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Callable, Optional

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "6TL-Postventa/1.0 (postventa@6tl.example)"

Fetch = Callable[[str], list]


def _http_fetch(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (URL fija)
        return json.loads(resp.read().decode("utf-8"))


def geocode(query: str, *, fetch: Fetch = _http_fetch) -> Optional[tuple[float, float]]:
    """Devuelve (lat, lon) para `query`, o None si no hay resultado o falla la red."""
    query = (query or "").strip()
    if not query:
        return None
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    url = f"{NOMINATIM_URL}?{params}"
    try:
        data = fetch(url)
    except Exception:
        return None
    if not data:
        return None
    try:
        return float(data[0]["lat"]), float(data[0]["lon"])
    except (KeyError, ValueError, TypeError, IndexError):
        return None


def geocode_ubicacion(
    direccion: Optional[str] = None,
    ciudad: Optional[str] = None,
    provincia: Optional[str] = None,
    pais: Optional[str] = None,
    *,
    fetch: Fetch = _http_fetch,
) -> Optional[tuple[float, float]]:
    """Geocodifica probando de la más específica a la más genérica.

    Si la dirección completa no resuelve (p. ej. un polígono que Nominatim no conoce),
    reintenta con ciudad+provincia+país y luego ciudad+país.
    """
    candidatos = [
        [direccion, ciudad, provincia, pais],
        [ciudad, provincia, pais],
        [ciudad, pais],
    ]
    vistos: set[str] = set()
    for partes in candidatos:
        query = ", ".join(p for p in partes if p)
        if not query or query in vistos:
            continue
        vistos.add(query)
        coords = geocode(query, fetch=fetch)
        if coords is not None:
            return coords
    return None
