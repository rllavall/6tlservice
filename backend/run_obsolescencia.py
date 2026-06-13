"""Orquestador semanal de obsolescencia (Task Scheduler, como run_digest.py).

Recorre los productos a revisar, pregunta el estado de ciclo de vida a la web del
fabricante (vía Claude Code headless por defecto) y registra los cambios,
enviando un informe de los que han empeorado. Escribe directo a BD (sin auth).

Uso:
    python run_obsolescencia.py                 # ejecuta y notifica
    python run_obsolescencia.py --limite 30     # tope de productos en esta pasada
    python run_obsolescencia.py --dry-run       # consulta y registra, NO envía informe
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from app.env_file import load_env_file

load_env_file()

from app.db import SessionLocal
from app import models, obsolescencia_service, notificaciones  # noqa: F401


def _claude_bin() -> str:
    """Resuelve el ejecutable de Claude Code headless. Orden: env CLAUDE_BIN ->
    PATH (`which`) -> instalación nativa en ~/.local/bin. El Programador de tareas
    no hereda el PATH del usuario, por eso no basta con 'claude' a secas."""
    env = os.environ.get("CLAUDE_BIN")
    if env and Path(env).exists():
        return env
    enpath = shutil.which("claude")
    if enpath:
        return enpath
    nativo = Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude")
    return str(nativo)


def _url_fabricante(db, producto) -> str | None:
    if producto.fabricante_id is None:
        return None
    f = db.get(models.Fabricante, producto.fabricante_id)
    return f.url_obsolescencia if f else None


def _descripcion_paso(name, inp):
    """Descripción legible de un tool_use de búsqueda web; None si no es WebSearch/WebFetch."""
    if name == "WebSearch":
        q = (inp or {}).get("query")
        return f"🔎 Buscando: «{q}»" if q else None
    if name == "WebFetch":
        url = (inp or {}).get("url") or ""
        dom = urlparse(url).netloc or url
        return f"🌐 Leyendo {dom}" if dom else None
    return None


def _tokens_de_usage(usage):
    """Tokens del bloque usage = input + output (EXCLUYE caché: cache_creation y
    cache_read no se cuentan, para reflejar el consumo real de la consulta sin el
    arrastre fijo del system prompt cacheado); 0 si falta."""
    u = usage or {}
    return sum(int(u.get(k, 0) or 0) for k in ("input_tokens", "output_tokens"))


def _procesar_stream(lineas, on_paso=None):
    """Consume líneas stream-json. Por cada tool_use de búsqueda llama on_paso.
    Devuelve (texto_result|None, tokens_total, hubo_result)."""
    texto = None
    tokens = 0
    for linea in lineas:
        linea = (linea or "").strip()
        if not linea:
            continue
        try:
            ev = json.loads(linea)
        except ValueError:
            continue
        tipo = ev.get("type")
        if tipo == "assistant":
            for b in ev.get("message", {}).get("content", []) or []:
                if b.get("type") != "tool_use":
                    continue
                desc = _descripcion_paso(b.get("name"), b.get("input"))
                if desc and on_paso is not None:
                    try:
                        on_paso({"descripcion": desc})
                    except Exception:
                        pass
        elif tipo == "result":
            texto = ev.get("result")
            tokens = _tokens_de_usage(ev.get("usage"))
    return texto, tokens, (texto is not None)


def _parsear_estado(out):
    """Extrae el dict {estado,fecha_evento,url_fuente,resumen} del texto, o None."""
    if not out:
        return None
    inicio, fin = out.find("{"), out.rfind("}")
    if inicio == -1 or fin == -1:
        return None
    try:
        data = json.loads(out[inicio:fin + 1])
    except ValueError:
        return None
    if not data.get("estado"):
        return None
    fe = data.get("fecha_evento")
    return {
        "estado": data["estado"],
        "fecha_evento": date.fromisoformat(fe) if fe else None,
        "url_fuente": data.get("url_fuente"),
        "resumen": data.get("resumen"),
    }


def _sin_estado(tokens, estado_consulta):
    return {"estado": None, "fecha_evento": None, "url_fuente": None, "resumen": None,
            "tokens_total": tokens, "estado_consulta": estado_consulta}


def consultar_fabricante(producto, url_obsolescencia, *, on_paso=None, timeout=None,
                         _popen=None, _timer_factory=threading.Timer):
    """Lanza Claude Code headless en streaming para investigar el ciclo de vida.

    Emite los pasos web vía on_paso({"descripcion": ...}), mide tokens y se
    autolimita con un timeout (default env OBSOLESCENCIA_TIMEOUT_SEG=90; al saltar
    mata el proceso). Devuelve SIEMPRE un dict con estado (str|None), fecha_evento,
    url_fuente, resumen, tokens_total y estado_consulta ∈ ok|sin_respuesta|timeout|error.
    _popen/_timer_factory son inyectables para test."""
    if timeout is None:
        timeout = int(os.environ.get("OBSOLESCENCIA_TIMEOUT_SEG", "90"))
    plantilla = (Path(__file__).with_name("obsolescencia_prompt.md")).read_text(encoding="utf-8")
    prompt = plantilla.format(
        fabricante=producto.fabricante or "",
        pn=producto.pn_fabricante or "",
        descripcion=producto.descripcion or "",
        url=url_obsolescencia or "(sin URL conocida; busca en abierto)",
    )
    cmd = [_claude_bin(), "--allowedTools", "WebSearch,WebFetch",
           "--output-format", "stream-json", "--verbose", "-p", prompt]

    def _abrir():
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")

    expirado = {"v": False}
    try:
        proc = (_popen or _abrir)()
    except Exception:
        return _sin_estado(0, "error")

    def _matar():
        expirado["v"] = True
        try:
            proc.kill()
        except Exception:
            pass

    timer = _timer_factory(timeout, _matar)
    timer.start()
    try:
        texto, tokens, _ = _procesar_stream(proc.stdout, on_paso)
    except Exception:
        timer.cancel()
        try:
            proc.kill()
        except Exception:
            pass
        return _sin_estado(0, "error")
    finally:
        timer.cancel()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    if expirado["v"]:
        return _sin_estado(tokens, "timeout")
    hallazgo = _parsear_estado(texto)
    if hallazgo:
        hallazgo["tokens_total"] = tokens
        hallazgo["estado_consulta"] = "ok"
        return hallazgo
    return _sin_estado(tokens, "sin_respuesta")


def ejecutar(db, hoy, *, limite=20, consultar=consultar_fabricante,
             notificar_fn=notificaciones.notificar):
    prods = obsolescencia_service.productos_a_revisar(db, hoy, limite=limite)
    for p in prods:
        url = _url_fabricante(db, p)
        v = consultar(p, url)
        if not v or not v.get("estado"):
            continue
        obsolescencia_service.registrar_hallazgo(
            db, p.id, v["estado"], hoy=hoy, fecha_evento=v.get("fecha_evento"),
            url=v.get("url_fuente"), resumen=v.get("resumen"))
    return obsolescencia_service.enviar_informe(db, hoy, notificar_fn=notificar_fn)


def main() -> int:
    dry = "--dry-run" in sys.argv
    limite = 20
    if "--limite" in sys.argv:
        limite = int(sys.argv[sys.argv.index("--limite") + 1])
    with SessionLocal() as db:
        if dry:
            prods = obsolescencia_service.productos_a_revisar(db, date.today(), limite=limite)
            for p in prods:
                v = consultar_fabricante(p, _url_fabricante(db, p))
                if v and v.get("estado"):
                    obsolescencia_service.registrar_hallazgo(
                        db, p.id, v["estado"], hoy=date.today(),
                        fecha_evento=v.get("fecha_evento"), url=v.get("url_fuente"),
                        resumen=v.get("resumen"))
            info = obsolescencia_service.construir_informe(db, date.today())
            print(f"[dry-run] cambios pendientes de notificar: {info['total']}")
            return 0
        r = ejecutar(db, date.today(), limite=limite)
    print(f"enviado: {r['enviado']}  total: {r['total']}  canales: {r.get('canales')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
