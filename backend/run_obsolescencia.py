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
from datetime import date
from pathlib import Path

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


def consultar_fabricante(producto, url_obsolescencia):
    """Lanza Claude Code headless para investigar el estado de ciclo de vida.

    Devuelve {estado, fecha_evento, url_fuente, resumen} o None si no concluyente."""
    plantilla = (Path(__file__).with_name("obsolescencia_prompt.md")).read_text(encoding="utf-8")
    prompt = plantilla.format(
        fabricante=producto.fabricante or "",
        pn=producto.pn_fabricante or "",
        descripcion=producto.descripcion or "",
        url=url_obsolescencia or "(sin URL conocida; busca en abierto)",
    )
    try:
        # --allowedTools concede WebSearch/WebFetch sin prompt interactivo (en
        # headless el modo 'default' auto-deniega y el agente se queda sin web).
        out = subprocess.run(
            [_claude_bin(), "--allowedTools", "WebSearch,WebFetch", "-p", prompt],
            capture_output=True, text=True, timeout=300, check=True,
            stdin=subprocess.DEVNULL,
        ).stdout.strip()
        inicio, fin = out.find("{"), out.rfind("}")
        if inicio == -1 or fin == -1:
            return None
        data = json.loads(out[inicio:fin + 1])
        if not data.get("estado"):
            return None
        fe = data.get("fecha_evento")
        return {
            "estado": data["estado"],
            "fecha_evento": date.fromisoformat(fe) if fe else None,
            "url_fuente": data.get("url_fuente"),
            "resumen": data.get("resumen"),
        }
    except Exception:
        return None


def ejecutar(db, hoy, *, limite=20, consultar=consultar_fabricante,
             notificar_fn=notificaciones.notificar):
    prods = obsolescencia_service.productos_a_revisar(db, hoy, limite=limite)
    for p in prods:
        url = _url_fabricante(db, p)
        v = consultar(p, url)
        if not v:
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
                if v:
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
