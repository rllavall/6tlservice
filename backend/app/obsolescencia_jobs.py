"""Store en memoria + runner del refresco de obsolescencia por banco con progreso.
Proceso único (uvicorn on-prem): un job = un refresco en curso de un equipo.
No persiste: un reinicio del backend pierde los jobs (aceptable)."""
from __future__ import annotations

import secrets
import threading
from datetime import date

from app import obsolescencia_banco
from app.db import SessionLocal

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def crear_job(equipo_id: int, total: int) -> str:
    job_id = secrets.token_hex(8)
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "equipo_id": equipo_id,
            "total": total,
            "indice": 0,
            "estado": "en_curso",
            "actual": None,
            "resultados": [],
            "tokens_total": 0,
            "report": None,
            "error": None,
        }
    return job_id


def snapshot(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        copia = dict(job)
        copia["resultados"] = list(job["resultados"])
        copia["actual"] = dict(job["actual"]) if job["actual"] else None
        if copia["actual"] is not None:
            copia["actual"]["pasos"] = list(job["actual"].get("pasos", []))
        return copia


def _hacer_callback(job_id: str):
    def cb(ev: dict) -> None:
        p = ev["producto"]
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is None:
                return
            if ev["tipo"] == "actual":
                job["indice"] = ev["indice"]
                job["actual"] = {"part_number": p.part_number,
                                 "fabricante": p.fabricante,
                                 "descripcion": p.descripcion,
                                 "pasos": []}
            elif ev["tipo"] == "paso":
                if job["actual"] is not None and ev.get("descripcion"):
                    job["actual"]["pasos"].append(ev["descripcion"])
            elif ev["tipo"] == "resultado":
                job["resultados"].append({
                    "part_number": p.part_number,
                    "descripcion": p.descripcion,
                    "estado_anterior": ev["estado_anterior"],
                    "estado_nuevo": ev["estado_nuevo"],
                    "cambio": ev["cambio"],
                    "tokens": ev.get("tokens", 0),
                    "estado_consulta": ev.get("estado_consulta", "ok"),
                })
                job["tokens_total"] += ev.get("tokens", 0)
    return cb


def ejecutar(job_id: str, equipo_id: int, *, limite: int, consultar,
             db_factory=SessionLocal) -> None:
    """Corre el refresco (síncrono) y va volcando el progreso al store. Pensado
    para ejecutarse en un hilo. `db_factory` inyectable para tests."""
    db = db_factory()
    try:
        report = obsolescencia_banco.refrescar_banco(
            db, equipo_id, date.today(), limite=limite, consultar=consultar,
            on_progreso=_hacer_callback(job_id))
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is not None:
                job["report"] = report
                job["actual"] = None
                job["estado"] = "terminado"
    except Exception as exc:
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is not None:
                job["estado"] = "error"
                job["error"] = str(exc)
    finally:
        db.close()


def lanzar(job_id: str, equipo_id: int, *, limite: int, consultar) -> None:
    """Arranca `ejecutar` en un hilo daemon (no bloquea la petición HTTP)."""
    threading.Thread(
        target=ejecutar, args=(job_id, equipo_id),
        kwargs={"limite": limite, "consultar": consultar}, daemon=True,
    ).start()
