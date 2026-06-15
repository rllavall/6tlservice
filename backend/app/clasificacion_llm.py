"""Agente LLM headless para clasificar componentes ambiguos (afecta_a_medida/bajo_coste).

`consultar_clasificacion` es inyectable: el default llama a Claude Code headless con
la descripcion del producto (sin herramientas web). Los tests inyectan un fake.
Parseo robusto y conservador: ante cualquier duda devuelve None (el servicio se queda
con el resultado de reglas; nunca escribe basura).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _claude_bin() -> str:
    env = os.environ.get("CLAUDE_BIN")
    if env and Path(env).exists():
        return env
    enpath = shutil.which("claude")
    if enpath:
        return enpath
    local = Path.home() / ".local" / "bin" / "claude.exe"
    return str(local) if local.exists() else "claude"


def _parsear_respuesta(out: str) -> Optional[dict]:
    if not out:
        return None
    inicio, fin = out.find("{"), out.rfind("}")
    if inicio < 0 or fin <= inicio:
        return None
    try:
        data = json.loads(out[inicio:fin + 1])
    except (ValueError, TypeError):
        return None
    am, bc, razon = data.get("afecta_a_medida"), data.get("bajo_coste"), data.get("razon")
    if not isinstance(am, bool) or not isinstance(bc, bool):
        return None
    if not isinstance(razon, str) or not razon.strip():
        return None
    if am and bc:  # incoherente: medida manda
        bc = False
    return {"afecta_a_medida": am, "bajo_coste": bc, "razon": razon.strip()}


def consultar_clasificacion(part_number, descripcion, fabricante, categoria,
                            *, timeout=None, _popen=None) -> Optional[dict]:
    """Devuelve {afecta_a_medida, bajo_coste, razon} o None si no decide."""
    if timeout is None:
        timeout = int(os.environ.get("CLASIFICACION_TIMEOUT_SEG", "60"))
    plantilla = Path(__file__).parent.parent / "clasificacion_prompt.md"
    prompt = plantilla.read_text(encoding="utf-8").format(
        fabricante=fabricante or "", pn=part_number or "",
        categoria=categoria or "", descripcion=descripcion or "")
    cmd = [_claude_bin(), "--output-format", "text", "-p", prompt]

    def _abrir():
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, text=True,
                                encoding="utf-8", errors="replace")
    try:
        proc = (_popen or _abrir)()
        out, _ = proc.communicate(timeout=timeout)
    except Exception:
        return None
    return _parsear_respuesta(out)
