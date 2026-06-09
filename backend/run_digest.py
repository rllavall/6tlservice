"""Envía el digest diario de avisos (preventivos + SLA) por los canales configurados.

Pensado para ejecutarse desde el Programador de tareas de Windows (ver
``run_digest.cmd``). No necesita el servidor API arrancado ni token: llama al
servicio directamente contra la base de datos. Los canales (Telegram/email) se
leen de ``backend/.env``; si no hay ninguno configurado, no envía nada.

Uso:
    python run_digest.py            # construye y envía el digest de hoy
    python run_digest.py --dry-run  # solo imprime el resumen, sin enviar
"""
from __future__ import annotations

import sys
from datetime import date

from app.env_file import load_env_file

load_env_file()

from app.db import SessionLocal
from app import models  # noqa: F401  (registra los mapeos ORM)
from app import notificaciones_service


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    with SessionLocal() as db:
        if dry_run:
            d = notificaciones_service.construir_digest(db, date.today())
            d["canales"] = None
        else:
            d = notificaciones_service.enviar_digest(db, date.today())
    print(d["asunto"])
    print(f"total avisos: {d['total']}  canales: {d.get('canales')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
