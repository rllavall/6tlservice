# Notificaciones (email / Telegram) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Notificar por email y/o Telegram (best-effort) el digest de avisos+SLA (disparo externo) y los cambios de estado de incidencia. Sin dependencias nuevas (stdlib).

**Architecture:** `app/notificaciones.py` (canales best-effort, inyectables, config por entorno), `app/notificaciones_service.py` (composición digest/incidencia), endpoint `POST /api/notificaciones/digest` + hook en la transición de incidencia. Reutiliza `email_notify`, `avisos_service`, `sla_service`.

**Tech Stack:** FastAPI, Pydantic v2, stdlib smtplib/urllib, pytest.

**Convenciones:** `./.venv/Scripts/python.exe -m pytest` desde `backend/`. NO uvicorn. Routers protegidos con `dependencies=[Depends(get_current_user)]`. Fixtures `client`/`client_sin_auth`. `email_notify._config()` devuelve `{host,port,user,password,from,to}`; `email_notify._enviar_smtp(msg, cfg)`. `avisos_service.construir_avisos(db, hoy)` → `{...,"resumen":{preventivos_vencidos,preventivos_proximos,contratos_por_caducar}}`. `sla_service.construir_sla(db, hoy)` → `{...,"resumen":{en_riesgo,incumplidas},"incumplidas":[{"incidencia":<ORM>,...}]}`.

---

## Task 1: Canales `app/notificaciones.py`

**Files:**
- Create: `backend/app/notificaciones.py`
- Test: `backend/tests/test_notificaciones.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_notificaciones.py`:

```python
from app import notificaciones


def test_email_none_sin_smtp(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert notificaciones.enviar_email("a", "b") is None


def test_email_true_con_transporte(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("NOTIF_EMAIL_TO", "a@x.com, b@x.com")
    enviados = []
    assert notificaciones.enviar_email("Asunto", "Cuerpo", transporte=lambda msg, cfg: enviados.append(msg)) is True
    assert enviados and enviados[0]["To"] == "a@x.com, b@x.com"
    assert enviados[0]["Subject"] == "Asunto"


def test_email_false_si_transporte_lanza(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("NOTIF_EMAIL_TO", "a@x.com")
    def boom(msg, cfg):
        raise RuntimeError("smtp down")
    assert notificaciones.enviar_email("a", "b", transporte=boom) is False


def test_telegram_none_sin_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert notificaciones.enviar_telegram("hola") is None


def test_telegram_true_con_http_post(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    capt = []
    assert notificaciones.enviar_telegram("hola", http_post=lambda t, c, txt: capt.append((t, c, txt))) is True
    assert capt == [("tok", "123", "hola")]


def test_notificar_dispara_ambos():
    r = notificaciones.notificar("As", "Cu",
        email_fn=lambda a, c: True, telegram_fn=lambda txt: None)
    assert r == {"email": True, "telegram": None}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write the module** `backend/app/notificaciones.py`:

```python
"""Canales de notificación best-effort (email / Telegram). Sin dependencias externas.
Canal sin configurar (faltan variables de entorno) -> devuelve None (no-op). Nunca relanza."""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from email.message import EmailMessage
from typing import Optional

from app import email_notify

log = logging.getLogger(__name__)


def _destinatarios_email() -> list[str]:
    raw = os.environ.get("NOTIF_EMAIL_TO") or email_notify._config().get("to")
    return [e.strip() for e in raw.split(",") if e.strip()] if raw else []


def enviar_email(asunto: str, cuerpo: str, *, transporte=None) -> Optional[bool]:
    cfg = email_notify._config()
    destinatarios = _destinatarios_email()
    if not cfg["host"] or not destinatarios:
        return None
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(cuerpo)
    enviar = transporte or email_notify._enviar_smtp
    try:
        enviar(msg, cfg)
        return True
    except Exception:
        log.exception("Fallo enviando email de notificación")
        return False


def _http_post_telegram(token: str, chat_id: str, texto: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": texto}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def enviar_telegram(texto: str, *, http_post=None) -> Optional[bool]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return None
    poster = http_post or _http_post_telegram
    try:
        poster(token, chat_id, texto)
        return True
    except Exception:
        log.exception("Fallo enviando Telegram")
        return False


def notificar(asunto: str, cuerpo: str, *, email_fn=enviar_email, telegram_fn=enviar_telegram) -> dict:
    """Dispara todos los canales configurados. Devuelve {canal: True|False|None}."""
    return {
        "email": email_fn(asunto, cuerpo),
        "telegram": telegram_fn(f"{asunto}\n\n{cuerpo}"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app/notificaciones.py tests/test_notificaciones.py
git commit -m "feat: canales de notificación email/Telegram (best-effort, inyectables)"
```

---

## Task 2: Composición `app/notificaciones_service.py`

**Files:**
- Create: `backend/app/notificaciones_service.py`
- Test: `backend/tests/test_notificaciones_service.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_notificaciones_service.py`:

```python
from datetime import date
from types import SimpleNamespace

from app import models, notificaciones_service


def _equipo_contrato_vencido_preventivo(db):
    p = models.Producto(part_number="6TL-N", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    con = models.ContratoMantenimiento(codigo="CTR-N", nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1))
    db.add(con); db.flush()
    eq = models.Equipo(numero_serie="N1", producto_id=p.id, contrato_id=con.id)
    db.add(eq); db.flush()
    inc = models.Incidencia(codigo="RMA-9", tipo="rma", estado="abierta", equipo_id=eq.id,
        titulo="t", descripcion_problema="d", prioridad="media", fecha_apertura=date(2020, 1, 1))
    db.add(inc); db.flush()
    return eq, inc


def test_construir_digest_cuenta(db_session):
    _equipo_contrato_vencido_preventivo(db_session)
    d = notificaciones_service.construir_digest(db_session, date(2026, 6, 6))
    assert d["resumen"]["preventivos_vencidos"] >= 1
    assert d["resumen"]["sla_incumplidas"] >= 1
    assert d["total"] >= 2
    assert "Resumen" in d["asunto"] or "resumen" in d["asunto"].lower()
    assert isinstance(d["cuerpo"], str) and len(d["cuerpo"]) > 0


def test_notificar_incidencia_compone_mensaje():
    inc = SimpleNamespace(codigo="RMA-1", tipo="rma", titulo="No arranca", estado="en_reparacion", prioridad="alta")
    capt = {}
    def fake(asunto, cuerpo):
        capt["asunto"] = asunto; capt["cuerpo"] = cuerpo
        return {"email": None, "telegram": None}
    notificaciones_service.notificar_incidencia(inc, "en_reparacion", notificar_fn=fake)
    assert "RMA-1" in capt["asunto"]
    assert "en_reparacion" in capt["cuerpo"]


def test_enviar_digest_invoca_notificar(db_session):
    capt = {}
    def fake(asunto, cuerpo):
        capt["llamado"] = True
        return {"email": True, "telegram": None}
    r = notificaciones_service.enviar_digest(db_session, date(2026, 6, 6), notificar_fn=fake)
    assert capt.get("llamado") is True
    assert r["canales"] == {"email": True, "telegram": None}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_service.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write the service** `backend/app/notificaciones_service.py`:

```python
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app import avisos_service, notificaciones, sla_service


def construir_digest(db: Session, hoy: date) -> dict:
    av = avisos_service.construir_avisos(db, hoy)
    sl = sla_service.construir_sla(db, hoy)
    resumen = {
        "preventivos_vencidos": av["resumen"]["preventivos_vencidos"],
        "preventivos_proximos": av["resumen"]["preventivos_proximos"],
        "contratos_por_caducar": av["resumen"]["contratos_por_caducar"],
        "sla_en_riesgo": sl["resumen"]["en_riesgo"],
        "sla_incumplidas": sl["resumen"]["incumplidas"],
    }
    total = sum(resumen.values())
    asunto = f"[6TL Postventa] Resumen de avisos ({total})"
    lineas = [f"Resumen de avisos al {hoy.isoformat()}:", ""]
    lineas.append(f"- Preventivos vencidos: {resumen['preventivos_vencidos']}")
    lineas.append(f"- Preventivos proximos: {resumen['preventivos_proximos']}")
    lineas.append(f"- Contratos por caducar: {resumen['contratos_por_caducar']}")
    lineas.append(f"- SLA en riesgo: {resumen['sla_en_riesgo']}")
    lineas.append(f"- SLA incumplidas: {resumen['sla_incumplidas']}")
    incumplidas = [i["incidencia"].codigo for i in sl["incumplidas"][:10]]
    if incumplidas:
        lineas += ["", "Incidencias SLA incumplidas: " + ", ".join(incumplidas)]
    vencidos = [a["equipo"].numero_serie for a in av["preventivos"] if a["bucket"] == "vencido"][:10]
    if vencidos:
        lineas += ["", "Equipos con preventivo vencido: " + ", ".join(vencidos)]
    return {"asunto": asunto, "cuerpo": "\n".join(lineas), "resumen": resumen, "total": total}


def enviar_digest(db: Session, hoy: date, *, notificar_fn=notificaciones.notificar) -> dict:
    d = construir_digest(db, hoy)
    canales = notificar_fn(d["asunto"], d["cuerpo"])
    return {"asunto": d["asunto"], "resumen": d["resumen"], "total": d["total"], "canales": canales}


def mensaje_incidencia(inc, evento: str) -> tuple[str, str]:
    asunto = f"[6TL Postventa] Incidencia {inc.codigo}: {evento}"
    cuerpo = (
        f"Incidencia {inc.codigo} ({inc.tipo})\n"
        f"Evento: {evento}\n"
        f"Titulo: {inc.titulo}\n"
        f"Estado: {inc.estado}\n"
        f"Prioridad: {inc.prioridad}\n"
    )
    return asunto, cuerpo


def notificar_incidencia(inc, evento: str, *, notificar_fn=notificaciones.notificar) -> dict:
    asunto, cuerpo = mensaje_incidencia(inc, evento)
    return notificar_fn(asunto, cuerpo)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_service.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/notificaciones_service.py tests/test_notificaciones_service.py
git commit -m "feat: notificaciones_service (digest avisos+SLA + mensaje de incidencia)"
```

---

## Task 3: Endpoint `POST /api/notificaciones/digest` + hook en transición

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/notificaciones.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/incidencias.py` (endpoint `transicion`)
- Test: `backend/tests/test_notificaciones_api.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_notificaciones_api.py`:

```python
def test_digest_dry_run_no_envia(client):
    out = client.post("/api/notificaciones/digest?dry_run=true").json()
    assert out["enviado"] is False
    assert out["canales"] is None
    assert isinstance(out["cuerpo"], str)
    assert set(out["resumen"].keys()) == {
        "preventivos_vencidos", "preventivos_proximos", "contratos_por_caducar",
        "sla_en_riesgo", "sla_incumplidas"}


def test_digest_envia_sin_canales(client, monkeypatch):
    # garantiza canales sin configurar -> None, sin red real
    for var in ("SMTP_HOST", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(var, raising=False)
    out = client.post("/api/notificaciones/digest").json()
    assert out["enviado"] is True
    assert out["canales"] == {"email": None, "telegram": None}


def test_digest_protegido_401(client_sin_auth):
    assert client_sin_auth.post("/api/notificaciones/digest").status_code == 401


def test_transicion_incidencia_sigue_funcionando(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-TN", "tipo": "equipo", "descripcion": "B"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "TN1", "producto_id": prod["id"]}).json()
    inc = client.post("/api/incidencias", json={
        "tipo": "soporte_tecnico", "equipo_id": eq["id"], "titulo": "x",
        "descripcion_problema": "y", "prioridad": "media", "fecha_apertura": "2026-06-01"}).json()
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "diagnostico"})
    assert r.status_code == 200
    assert r.json()["estado"] == "diagnostico"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_api.py -v`
Expected: FAIL (404 digest).

- [ ] **Step 3: Add schema** en `backend/app/schemas.py` (sección nueva, tras SLA):

```python
# --- Notificaciones ---
class DigestOut(BaseModel):
    asunto: str
    cuerpo: str
    resumen: dict
    total: int
    enviado: bool
    canales: Optional[dict] = None
```

- [ ] **Step 4: Create the router** `backend/app/routers/notificaciones.py`:

```python
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import notificaciones_service
from app.db import get_db
from app.schemas import DigestOut

router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])


@router.post("/digest", response_model=DigestOut)
def digest(dry_run: bool = False, db: Session = Depends(get_db)) -> dict:
    hoy = date.today()
    d = notificaciones_service.construir_digest(db, hoy)
    if dry_run:
        return {**d, "enviado": False, "canales": None}
    r = notificaciones_service.enviar_digest(db, hoy)
    return {"asunto": d["asunto"], "cuerpo": d["cuerpo"], "resumen": d["resumen"],
            "total": d["total"], "enviado": True, "canales": r["canales"]}
```

- [ ] **Step 5: Register router** en `app/main.py`: `from app.routers import notificaciones` y
`app.include_router(notificaciones.router, dependencies=[Depends(get_current_user)])`.

- [ ] **Step 6: Add the best-effort hook** en `app/routers/incidencias.py`, endpoint `transicion` (~línea 141-153).
Añade `from app import notificaciones_service` a los imports del módulo. Justo antes de `return inc` (tras
`db.refresh(inc)`), añade:
```python
    try:
        notificaciones_service.notificar_incidencia(inc, payload.nuevo_estado)
    except Exception:
        pass
    return inc
```
(Con canales sin configurar es no-op; nunca rompe la transición.)

- [ ] **Step 7: Run the test**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_notificaciones_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Run FULL suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (todo verde; el hook no rompe los tests de transición existentes).

- [ ] **Step 9: Commit**

```bash
git add app/schemas.py app/routers/notificaciones.py app/main.py app/routers/incidencias.py tests/test_notificaciones_api.py
git commit -m "feat: POST /api/notificaciones/digest + hook best-effort en transición de incidencia"
```

---

## Task 4: Prompt Lovable 25

**Files:**
- Create: `docs/lovable/25_notificaciones.md`

- [ ] **Step 1: Write the prompt** con la cabecera de contexto estándar (como `docs/lovable/24_sla.md`). Cubre:
  1. Tipo `DigestOut` (`asunto`, `cuerpo:string`, `resumen:Record<string,number>`, `total:number`, `enviado:boolean`, `canales:Record<string,boolean|null>|null`) en `@/lib/types`.
  2. Pantalla/sección **Notificaciones** (admin, en el menú): botón **"Previsualizar"** → `POST /api/notificaciones/digest?dry_run=true` y muestra `cuerpo` (en `<pre>`) + tarjetas con `resumen`. Botón **"Enviar ahora"** → `POST /api/notificaciones/digest` (sin dry_run) y muestra el resultado `canales` (email/telegram: enviado/no configurado/fallo). Nota informativa: "el envío periódico se programa fuera de la app (p.ej. Task Scheduler llamando a este endpoint con autenticación); los canales se configuran por variables de entorno (SMTP_*, NOTIF_EMAIL_TO, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)".
  3. Consume solo `POST /api/notificaciones/digest`. No inventes endpoints/campos.

- [ ] **Step 2: Commit**

```bash
git add docs/lovable/25_notificaciones.md
git commit -m "docs: prompt Lovable 25 — notificaciones (digest)"
```

---

## Self-review (cobertura del spec)
- Canales best-effort + config entorno + inyectables → Task 1. Digest (avisos+SLA) + mensaje incidencia → Task 2. Endpoint digest + dry_run + hook transición + 401 → Task 3. Frontend → Task 4.
- ⚠️ Tests NUNCA configuran canales reales ni hacen red (transportes inyectados o canales None). Hook best-effort no rompe transiciones. Sin entidad ni migración.
