"""Carga de variables de entorno desde un fichero `.env` (sin dependencias).

El backend lee la configuración (SMTP, Telegram, auth) de ``os.environ``. En
producción esas variables las inyecta el orquestador (Docker/systemd), pero en
desarrollo es cómodo tenerlas en ``backend/.env``. Este módulo parsea ese fichero
y rellena ``os.environ`` **sin pisar** las variables ya presentes en el entorno
(el entorno real siempre gana sobre el fichero).
"""
from __future__ import annotations

import os
from pathlib import Path


def parse_env(texto: str) -> dict[str, str]:
    """Parsea el contenido de un `.env` a un dict.

    Reglas: ignora líneas en blanco y comentarios (`#`); admite el prefijo
    opcional ``export``; separa por el primer ``=``; recorta espacios y un par
    de comillas envolventes (simples o dobles) del valor.
    """
    resultado: dict[str, str] = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if linea.startswith("export "):
            linea = linea[len("export "):].strip()
        if "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        if not clave:
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        resultado[clave] = valor
    return resultado


def load_env_file(ruta: str | os.PathLike | None = None, *, override: bool = False) -> dict[str, str]:
    """Carga ``ruta`` (por defecto ``backend/.env``) en ``os.environ``.

    Devuelve el dict de pares aplicados. Si el fichero no existe, no hace nada.
    Las variables ya presentes en el entorno no se sobrescriben salvo
    ``override=True``.
    """
    if ruta is None:
        ruta = Path(__file__).resolve().parent.parent / ".env"
    ruta = Path(ruta)
    if not ruta.is_file():
        return {}
    pares = parse_env(ruta.read_text(encoding="utf-8"))
    aplicados: dict[str, str] = {}
    for clave, valor in pares.items():
        if override or clave not in os.environ:
            os.environ[clave] = valor
            aplicados[clave] = valor
    return aplicados
