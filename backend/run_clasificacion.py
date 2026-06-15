"""Lote de auto-clasificacion de trazabilidad (backfill / Task Scheduler).

Recorre los productos componente, aplica reglas y LLM (para ambiguos) y escribe
afecta_a_medida/bajo_coste con origen='agente', respetando lo manual. Escribe
directo a BD (sin auth).

Uso (desde backend/):
    .venv\\Scripts\\python.exe run_clasificacion.py --dry-run
    .venv\\Scripts\\python.exe run_clasificacion.py            # escribe
    .venv\\Scripts\\python.exe run_clasificacion.py --sin-llm  # solo reglas
    .venv\\Scripts\\python.exe run_clasificacion.py --limite 50
"""
from __future__ import annotations

import argparse

from app.env_file import load_env_file

load_env_file()

from app.db import SessionLocal
from app import auditoria, clasificacion_service


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sin-llm", action="store_true")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    auditoria.registrar_listeners()
    db = SessionLocal()
    db.info["usuario_username"] = "clasificacion automatica"
    db.info["usuario_id"] = None
    try:
        r = clasificacion_service.clasificar_lote(
            db, usar_llm=not args.sin_llm, limite=args.limite, dry_run=args.dry_run)
        print(f"Procesados: {r.procesados} | reglas: {r.por_reglas} | LLM: {r.por_llm} "
              f"| omitidos manual: {r.omitidos_manual} | sin cambios: {r.sin_cambios}")
        for c in r.cambios:
            print(f"  {c['part_number']:18} afecta={c['afecta_a_medida']} "
                  f"bajo_coste={c['bajo_coste']}  {c['motivo']}")
        print("DRY-RUN: nada escrito." if args.dry_run else "ESCRITO.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
