# Solicitud de soporte del cliente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que un cliente cree una solicitud de soporte desde un formulario público (sin login), avisar por correo a support@6tlengineering.com, y que un técnico la apruebe (creando la incidencia) o la rechace.

**Architecture:** Nueva entidad `SolicitudSoporte` + un endpoint público `POST /api/solicitudes` + endpoints internos de listado/aprobar/rechazar (lógica en `app/solicitudes_service.py`). El aviso por correo vive en `app/email_notify.py` (SMTP por variables de entorno, best-effort, transporte inyectable). La tabla nueva la crea `create_all`. Frontend (Lovable, prompt 18): página pública sin shell + pantalla interna `/solicitudes`.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2 (Mapped), Pydantic v2, smtplib, pytest.

**Convenciones:** tests en `backend/tests/` (fixtures `db_session`/`client`); ejecutar desde `backend/` con `.venv\Scripts\python.exe -m pytest -q`. Commit por tarea, mensaje en español terminando con la línea Co-Authored-By habitual.

**Contexto del código:**
- `app/incidencias_service.py` tiene `generar_codigo(db, tipo="rma")` (`PREFIJO-NNNN`) y `_PREFIJO_TIPO`.
- `app/garantia.py` tiene `equipo_en_garantia(equipo, fecha) -> Optional[bool]`.
- `app/models.py`: `Incidencia` con campos codigo/tipo/equipo_id/componente_id/titulo/descripcion_problema/prioridad/estado/asignado_a/en_garantia/fecha_apertura. `Integer/String/Date/ForeignKey/Boolean` y `Optional/date` ya importados.
- `app/schemas.py`: `_PRIORIDAD = Literal["baja","media","alta"]` ya existe; el tipo de incidencia es `Literal["rma","soporte_venta","soporte_tecnico","calibracion"]`. `_ORM` = `from_attributes=True`.
- Routers se registran al final de `app/main.py` (último bloque = `avances`).

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---------|-----------------|--------|
| `backend/app/models.py` | + entidad `SolicitudSoporte`. | Modificar |
| `backend/app/schemas.py` | + `SolicitudCreate`/`SolicitudOut`/`AprobarSolicitudPayload`/`RechazarSolicitudPayload`. | Modificar |
| `backend/app/solicitudes_service.py` | `generar_codigo`, `aprobar`, `rechazar`, `SolicitudError`. | Crear |
| `backend/app/email_notify.py` | aviso SMTP best-effort (inyectable). | Crear |
| `backend/app/routers/solicitudes.py` | endpoints público + internos. | Crear |
| `backend/app/main.py` | registrar router. | Modificar |
| `backend/tests/test_email_notify.py` | tests del módulo de correo. | Crear |
| `backend/tests/test_solicitudes.py` | tests entidad + endpoints. | Crear |
| `docs/lovable/18_solicitud_soporte.md` | prompt Lovable. | Crear |
| `docs/lovable/README.md` | índice. | Modificar |

---

## Task 1: Entidad `SolicitudSoporte` + schemas + `generar_codigo`

**Files:**
- Modify: `backend/app/models.py` (al final)
- Modify: `backend/app/schemas.py` (sección nueva al final)
- Create: `backend/app/solicitudes_service.py`
- Test: `backend/tests/test_solicitudes.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_solicitudes.py`:

```python
from datetime import date

from app import models
from app import solicitudes_service as svc


def test_modelo_solicitud_defaults(db_session):
    s = models.SolicitudSoporte(
        codigo="SOL-0001", nombre_contacto="Ana", email_contacto="ana@x.com",
        titulo="t", descripcion_problema="d", fecha_solicitud=date(2026, 6, 5),
    )
    db_session.add(s); db_session.flush()
    assert s.estado == "pendiente"
    assert s.empresa is None and s.incidencia_id is None


def test_generar_codigo_solicitud(db_session):
    assert svc.generar_codigo(db_session) == "SOL-0001"
    db_session.add(models.SolicitudSoporte(
        codigo="SOL-0001", nombre_contacto="a", email_contacto="a@x.com",
        titulo="t", descripcion_problema="d", fecha_solicitud=date(2026, 6, 5),
    ))
    db_session.flush()
    assert svc.generar_codigo(db_session) == "SOL-0002"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_solicitudes.py -q`
Expected: FAIL (`AttributeError: ... 'SolicitudSoporte'` / `No module named 'app.solicitudes_service'`).

- [ ] **Step 3: Add the model**

Al FINAL de `backend/app/models.py`:

```python
class SolicitudSoporte(Base):
    __tablename__ = "solicitudes_soporte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String, unique=True)
    estado: Mapped[str] = mapped_column(String, default="pendiente")
    fecha_solicitud: Mapped[date] = mapped_column(Date)
    nombre_contacto: Mapped[str] = mapped_column(String)
    empresa: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email_contacto: Mapped[str] = mapped_column(String)
    telefono_contacto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    numero_serie_texto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    part_number_texto: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    titulo: Mapped[str] = mapped_column(String)
    descripcion_problema: Mapped[str] = mapped_column(String)
    incidencia_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidencias.id"), nullable=True)
    motivo_rechazo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha_resolucion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
```

- [ ] **Step 4: Add the schemas**

Al FINAL de `backend/app/schemas.py`:

```python
# --- Solicitud de soporte (formulario público) ---
_TIPO_INC = Literal["rma", "soporte_venta", "soporte_tecnico", "calibracion"]


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SolicitudCreate(BaseModel):
    nombre_contacto: str = Field(min_length=1)
    empresa: Optional[str] = None
    email_contacto: str
    telefono_contacto: Optional[str] = None
    numero_serie_texto: Optional[str] = None
    part_number_texto: Optional[str] = None
    titulo: str = Field(min_length=1)
    descripcion_problema: str = Field(min_length=1)
    website: Optional[str] = None   # honeypot: debe venir vacío

    @field_validator("email_contacto")
    @classmethod
    def _email_valido(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("email no válido")
        return v


class SolicitudOut(_ORM):
    id: int
    codigo: str
    estado: str
    fecha_solicitud: date
    nombre_contacto: str
    empresa: Optional[str] = None
    email_contacto: str
    telefono_contacto: Optional[str] = None
    numero_serie_texto: Optional[str] = None
    part_number_texto: Optional[str] = None
    titulo: str
    descripcion_problema: str
    incidencia_id: Optional[int] = None
    motivo_rechazo: Optional[str] = None
    fecha_resolucion: Optional[date] = None


class AprobarSolicitudPayload(BaseModel):
    equipo_id: Optional[int] = None
    componente_id: Optional[int] = None
    tipo: _TIPO_INC = "rma"
    prioridad: _PRIORIDAD = "media"
    asignado_a: Optional[str] = None
    en_garantia: Optional[bool] = None


class RechazarSolicitudPayload(BaseModel):
    motivo: str = Field(min_length=1)
```

Y en la línea de import de pydantic (arriba), añade `field_validator`:
```python
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
```
Y añade `import re` en los imports de arriba del archivo (si no está ya). Se valida el email con un
regex simple (sin la dependencia `email-validator`, que NO está instalada).

- [ ] **Step 5: Create the service**

Crear `backend/app/solicitudes_service.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models


class SolicitudError(Exception):
    """Error de negocio en solicitudes (→ 409)."""


def generar_codigo(db: Session) -> str:
    """Siguiente código `SOL-NNNN`."""
    nums = []
    for (codigo,) in db.query(models.SolicitudSoporte.codigo).all():
        if codigo and codigo.startswith("SOL-"):
            try:
                nums.append(int(codigo.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"SOL-{n:04d}"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_solicitudes.py -q`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/app/solicitudes_service.py backend/tests/test_solicitudes.py
git commit -m "feat: entidad SolicitudSoporte + schemas + generar_codigo"
```
(Mensaje termina con `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.)

---

## Task 2: Módulo de correo `email_notify.py`

**Files:**
- Create: `backend/app/email_notify.py`
- Test: `backend/tests/test_email_notify.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_email_notify.py`:

```python
from datetime import date
from types import SimpleNamespace

from app import email_notify


def _sol():
    return SimpleNamespace(
        codigo="SOL-0007", nombre_contacto="Ana", empresa="ACME",
        email_contacto="ana@acme.com", telefono_contacto="600",
        numero_serie_texto="SN-1", part_number_texto="PN-1",
        titulo="No arranca", descripcion_problema="Se apaga solo",
        fecha_solicitud=date(2026, 6, 5),
    )


def test_construir_mensaje_incluye_codigo_y_destino():
    cfg = {"from": "support@6tlengineering.com", "to": "support@6tlengineering.com",
           "host": "smtp.x", "port": 587, "user": None, "password": None}
    msg = email_notify.construir_mensaje(_sol(), cfg)
    assert "SOL-0007" in msg["Subject"]
    assert msg["To"] == "support@6tlengineering.com"
    assert "No arranca" in msg.get_content()


def test_sin_config_smtp_no_envia(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    enviados = []
    ok = email_notify.enviar_aviso_solicitud(_sol(), transporte=lambda m, c: enviados.append(m))
    assert ok is False and enviados == []   # sin host no intenta enviar


def test_envia_con_transporte_inyectado(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    enviados = []
    ok = email_notify.enviar_aviso_solicitud(_sol(), transporte=lambda m, c: enviados.append(m))
    assert ok is True and len(enviados) == 1


def test_fallo_de_envio_es_best_effort(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    def _boom(m, c):
        raise RuntimeError("smtp down")
    ok = email_notify.enviar_aviso_solicitud(_sol(), transporte=_boom)
    assert ok is False   # no relanza
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_email_notify.py -q`
Expected: FAIL (`No module named 'app.email_notify'`).

- [ ] **Step 3: Create the module**

Crear `backend/app/email_notify.py`:

```python
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)


def _config() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "from": os.environ.get("SMTP_FROM", "support@6tlengineering.com"),
        "to": os.environ.get("SOPORTE_EMAIL_TO", "support@6tlengineering.com"),
    }


def construir_mensaje(solicitud, cfg: dict) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Nueva solicitud de soporte {solicitud.codigo}"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    empresa = f" ({solicitud.empresa})" if solicitud.empresa else ""
    cuerpo = (
        f"Nueva solicitud de soporte {solicitud.codigo}\n\n"
        f"Contacto: {solicitud.nombre_contacto}{empresa}\n"
        f"Email: {solicitud.email_contacto}\n"
        f"Teléfono: {solicitud.telefono_contacto or '-'}\n"
        f"Equipo (texto): SN={solicitud.numero_serie_texto or '-'} / "
        f"PN={solicitud.part_number_texto or '-'}\n\n"
        f"Título: {solicitud.titulo}\n\n"
        f"{solicitud.descripcion_problema}\n"
    )
    msg.set_content(cuerpo)
    return msg


def _enviar_smtp(msg: EmailMessage, cfg: dict) -> None:
    with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
        s.starttls()
        if cfg["user"]:
            s.login(cfg["user"], cfg["password"])
        s.send_message(msg)


def enviar_aviso_solicitud(solicitud, transporte=None) -> bool:
    """Envía el aviso de una nueva solicitud. Best-effort: nunca relanza.

    `transporte` es un callable `(msg, cfg) -> None` (inyectable para tests);
    por defecto usa SMTP real. Devuelve True si se envió, False si no.
    """
    cfg = _config()
    if not cfg["host"]:
        log.info("SMTP no configurado; no se envía aviso de %s", solicitud.codigo)
        return False
    enviar = transporte or _enviar_smtp
    try:
        enviar(construir_mensaje(solicitud, cfg), cfg)
        return True
    except Exception:
        log.exception("Fallo enviando aviso de solicitud %s", solicitud.codigo)
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_email_notify.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/email_notify.py backend/tests/test_email_notify.py
git commit -m "feat: modulo email_notify (aviso SMTP best-effort, inyectable)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 3: Endpoint público `POST /api/solicitudes` + email + registro

**Files:**
- Create: `backend/app/routers/solicitudes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_solicitudes.py`

- [ ] **Step 1: Write the failing tests**

Añade a `backend/tests/test_solicitudes.py` (arriba, junto a los imports, añade `from app import email_notify`):

```python
def test_crear_solicitud_publica(client, monkeypatch):
    enviados = []
    monkeypatch.setattr(email_notify, "enviar_aviso_solicitud", lambda s: enviados.append(s.codigo) or True)
    r = client.post("/api/solicitudes", json={
        "nombre_contacto": "Ana", "email_contacto": "ana@acme.com",
        "titulo": "No arranca", "descripcion_problema": "Se apaga solo",
        "numero_serie_texto": "SN-9",
    })
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["codigo"].startswith("SOL-") and b["estado"] == "pendiente"
    assert "website" not in b
    assert enviados == [b["codigo"]]   # se disparó el aviso


def test_crear_solicitud_honeypot_400(client, monkeypatch):
    monkeypatch.setattr(email_notify, "enviar_aviso_solicitud", lambda s: True)
    r = client.post("/api/solicitudes", json={
        "nombre_contacto": "Bot", "email_contacto": "bot@x.com",
        "titulo": "x", "descripcion_problema": "y", "website": "http://spam",
    })
    assert r.status_code == 400


def test_crear_solicitud_email_invalido_422(client):
    r = client.post("/api/solicitudes", json={
        "nombre_contacto": "Ana", "email_contacto": "no-es-email",
        "titulo": "x", "descripcion_problema": "y",
    })
    assert r.status_code == 422


def test_email_falla_no_rompe_alta(client, monkeypatch):
    # si el envío revienta dentro del router, el alta debe seguir creándose
    def _boom(s):
        raise RuntimeError("smtp down")
    monkeypatch.setattr(email_notify, "enviar_aviso_solicitud", _boom)
    r = client.post("/api/solicitudes", json={
        "nombre_contacto": "Ana", "email_contacto": "ana@acme.com",
        "titulo": "x", "descripcion_problema": "y",
    })
    assert r.status_code == 201, r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_solicitudes.py -k "publica or honeypot or invalido or rompe" -q`
Expected: FAIL (404, router no existe).

- [ ] **Step 3: Create the router**

Crear `backend/app/routers/solicitudes.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import email_notify, models
from app import solicitudes_service as svc
from app.db import get_db
from app.schemas import SolicitudCreate, SolicitudOut

router = APIRouter(prefix="/api/solicitudes", tags=["solicitudes"])


@router.post("", response_model=SolicitudOut, status_code=201)
def crear(payload: SolicitudCreate, db: Session = Depends(get_db)) -> models.SolicitudSoporte:
    if payload.website:  # honeypot relleno -> bot
        raise HTTPException(400, "Solicitud rechazada")
    data = payload.model_dump(exclude={"website"})
    sol = models.SolicitudSoporte(
        codigo=svc.generar_codigo(db),
        estado="pendiente",
        fecha_solicitud=date.today(),
        **data,
    )
    db.add(sol)
    db.commit()
    db.refresh(sol)
    try:
        email_notify.enviar_aviso_solicitud(sol)
    except Exception:  # best-effort: el aviso nunca rompe el alta
        pass
    return sol


@router.get("", response_model=list[SolicitudOut])
def listar(estado: Optional[str] = None, db: Session = Depends(get_db)) -> list[models.SolicitudSoporte]:
    q = db.query(models.SolicitudSoporte)
    if estado is not None:
        q = q.filter(models.SolicitudSoporte.estado == estado)
    return q.order_by(models.SolicitudSoporte.id.desc()).all()


@router.get("/{solicitud_id}", response_model=SolicitudOut)
def obtener(solicitud_id: int, db: Session = Depends(get_db)) -> models.SolicitudSoporte:
    sol = db.get(models.SolicitudSoporte, solicitud_id)
    if sol is None:
        raise HTTPException(404, "Solicitud no encontrada")
    return sol
```

- [ ] **Step 4: Register the router**

En `backend/app/main.py`, tras el bloque del router `avances`, añade:
```python
from app.routers import solicitudes
app.include_router(solicitudes.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_solicitudes.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/solicitudes.py backend/app/main.py backend/tests/test_solicitudes.py
git commit -m "feat: endpoint publico POST /api/solicitudes + listado + aviso correo"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 4: Aprobar / rechazar (service + endpoints)

**Files:**
- Modify: `backend/app/solicitudes_service.py` (+ `aprobar`, `rechazar`)
- Modify: `backend/app/routers/solicitudes.py` (+ 2 endpoints)
- Test: `backend/tests/test_solicitudes.py`

- [ ] **Step 1: Write the failing tests**

Añade a `backend/tests/test_solicitudes.py`:

```python
def _seed_solicitud(client, monkeypatch):
    monkeypatch.setattr(email_notify, "enviar_aviso_solicitud", lambda s: True)
    return client.post("/api/solicitudes", json={
        "nombre_contacto": "Ana", "email_contacto": "ana@acme.com",
        "titulo": "No arranca", "descripcion_problema": "Se apaga solo",
    }).json()


def test_aprobar_crea_incidencia(client, monkeypatch):
    sol = _seed_solicitud(client, monkeypatch)
    p = client.post("/api/productos", json={"part_number": "PN-S", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-S", "producto_id": p["id"]}).json()
    r = client.post(f"/api/solicitudes/{sol['id']}/aprobar", json={
        "equipo_id": eq["id"], "tipo": "rma", "prioridad": "alta", "asignado_a": "ramon",
    })
    assert r.status_code == 201, r.text
    inc = r.json()
    assert inc["codigo"].startswith("RMA-") and inc["titulo"] == "No arranca" and inc["prioridad"] == "alta"
    # la solicitud queda aprobada y enlazada
    s2 = client.get(f"/api/solicitudes/{sol['id']}").json()
    assert s2["estado"] == "aprobada" and s2["incidencia_id"] == inc["id"]


def test_aprobar_sin_sujeto_422_o_400(client, monkeypatch):
    sol = _seed_solicitud(client, monkeypatch)
    r = client.post(f"/api/solicitudes/{sol['id']}/aprobar", json={"tipo": "rma", "prioridad": "media"})
    assert r.status_code in (400, 422)


def test_aprobar_dos_veces_409(client, monkeypatch):
    sol = _seed_solicitud(client, monkeypatch)
    p = client.post("/api/productos", json={"part_number": "PN-S2", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-S2", "producto_id": p["id"]}).json()
    client.post(f"/api/solicitudes/{sol['id']}/aprobar", json={"equipo_id": eq["id"], "tipo": "rma", "prioridad": "media"})
    r = client.post(f"/api/solicitudes/{sol['id']}/aprobar", json={"equipo_id": eq["id"], "tipo": "rma", "prioridad": "media"})
    assert r.status_code == 409


def test_rechazar(client, monkeypatch):
    sol = _seed_solicitud(client, monkeypatch)
    r = client.post(f"/api/solicitudes/{sol['id']}/rechazar", json={"motivo": "Duplicada"})
    assert r.status_code == 200, r.text
    s2 = client.get(f"/api/solicitudes/{sol['id']}").json()
    assert s2["estado"] == "rechazada" and s2["motivo_rechazo"] == "Duplicada"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_solicitudes.py -k "aprobar or rechazar" -q`
Expected: FAIL (404, endpoints no existen).

- [ ] **Step 3: Add service functions**

Añade a `backend/app/solicitudes_service.py` (imports nuevos arriba):

```python
from datetime import date

from app import garantia
from app import incidencias_service as inc_svc
```

y al final del archivo:

```python
def aprobar(db: Session, sol: models.SolicitudSoporte, payload) -> models.Incidencia:
    if sol.estado != "pendiente":
        raise SolicitudError("La solicitud ya no está pendiente")
    eq = None
    if payload.equipo_id is not None:
        eq = db.get(models.Equipo, payload.equipo_id)
        if eq is None:
            raise LookupError("Equipo no encontrado")
    if payload.componente_id is not None and db.get(models.Componente, payload.componente_id) is None:
        raise LookupError("Componente no encontrado")
    if payload.equipo_id is None and payload.componente_id is None:
        raise SolicitudError("Indica equipo_id o componente_id (al menos uno)")

    en_gar = payload.en_garantia
    if payload.tipo == "rma" and en_gar is None and eq is not None:
        en_gar = garantia.equipo_en_garantia(eq, date.today())

    inc = models.Incidencia(
        codigo=inc_svc.generar_codigo(db, payload.tipo),
        tipo=payload.tipo,
        estado="abierta",
        equipo_id=payload.equipo_id,
        componente_id=payload.componente_id,
        titulo=sol.titulo,
        descripcion_problema=sol.descripcion_problema,
        prioridad=payload.prioridad,
        asignado_a=payload.asignado_a,
        en_garantia=en_gar,
        fecha_apertura=date.today(),
    )
    db.add(inc)
    db.flush()
    sol.estado = "aprobada"
    sol.incidencia_id = inc.id
    sol.fecha_resolucion = date.today()
    db.commit()
    db.refresh(inc)
    return inc


def rechazar(db: Session, sol: models.SolicitudSoporte, motivo: str) -> None:
    if sol.estado != "pendiente":
        raise SolicitudError("La solicitud ya no está pendiente")
    sol.estado = "rechazada"
    sol.motivo_rechazo = motivo
    sol.fecha_resolucion = date.today()
    db.commit()
```

- [ ] **Step 4: Add the endpoints**

En `backend/app/routers/solicitudes.py`:
1. Amplía los imports de schemas: `from app.schemas import SolicitudCreate, SolicitudOut, AprobarSolicitudPayload, RechazarSolicitudPayload, IncidenciaOut`.
2. Añade al final:

```python
@router.post("/{solicitud_id}/aprobar", response_model=IncidenciaOut, status_code=201)
def aprobar(solicitud_id: int, payload: AprobarSolicitudPayload, db: Session = Depends(get_db)) -> models.Incidencia:
    sol = db.get(models.SolicitudSoporte, solicitud_id)
    if sol is None:
        raise HTTPException(404, "Solicitud no encontrada")
    try:
        return svc.aprobar(db, sol, payload)
    except LookupError as e:
        db.rollback()
        raise HTTPException(404, str(e))
    except svc.SolicitudError as e:
        db.rollback()
        raise HTTPException(409, str(e))


@router.post("/{solicitud_id}/rechazar", response_model=SolicitudOut)
def rechazar(solicitud_id: int, payload: RechazarSolicitudPayload, db: Session = Depends(get_db)) -> models.SolicitudSoporte:
    sol = db.get(models.SolicitudSoporte, solicitud_id)
    if sol is None:
        raise HTTPException(404, "Solicitud no encontrada")
    try:
        svc.rechazar(db, sol, payload.motivo)
    except svc.SolicitudError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.refresh(sol)
    return sol
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_solicitudes.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/solicitudes_service.py backend/app/routers/solicitudes.py backend/tests/test_solicitudes.py
git commit -m "feat: aprobar/rechazar solicitud (aprobar crea la incidencia)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 5: Suite completa + smoke en vivo

**Files:** ninguno (verificación).

- [ ] **Step 1: Run the full suite**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest -q`
Expected: PASS, todos verde (166 previos + los nuevos).

- [ ] **Step 2: Smoke en vivo (sin SMTP configurado → no envía, pero crea)**

Arranca el backend (`create_all` crea la tabla `solicitudes_soporte`):
```
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```
En otra shell:
```
curl -s -X POST "http://127.0.0.1:8020/api/solicitudes" -H "Content-Type: application/json" -d "{\"nombre_contacto\":\"Ana\",\"email_contacto\":\"ana@acme.com\",\"titulo\":\"Smoke\",\"descripcion_problema\":\"prueba\"}"
curl -s "http://127.0.0.1:8020/api/solicitudes?estado=pendiente"
```
Expected: POST 201 con `codigo` `SOL-NNNN`, `estado` pendiente; el GET lista la solicitud. (Sin SMTP_HOST en el entorno, el log dirá "SMTP no configurado"; el alta funciona igual.) Borra la solicitud de smoke por sqlite si quieres dejar limpio (no hay DELETE en la API).

- [ ] **Step 3: Parar el backend**

`netstat -ano | findstr :8020` → `taskkill /PID <pid> /T /F`.

- [ ] **Step 4: Commit (solo si hubo ajustes)**

Si todo verde sin cambios, no hay commit.

---

## Task 6: Prompt Lovable 18 (formulario público + pantalla de solicitudes)

**Files:**
- Create: `docs/lovable/18_solicitud_soporte.md`
- Modify: `docs/lovable/README.md`

- [ ] **Step 1: Write the Lovable prompt**

Crear `docs/lovable/18_solicitud_soporte.md` con:

```markdown
# Prompt 18 — Solicitud de soporte del cliente (formulario público + pantalla interna)

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()`, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`). NO cambies nombres de campo.

## 1. Tipos en `src/lib/types.ts`
- `SolicitudEstado = "pendiente" | "aprobada" | "rechazada"`.
- `interface SolicitudSoporte { id:number; codigo:string; estado:SolicitudEstado; fecha_solicitud:string;
  nombre_contacto:string; empresa:string|null; email_contacto:string; telefono_contacto:string|null;
  numero_serie_texto:string|null; part_number_texto:string|null; titulo:string; descripcion_problema:string;
  incidencia_id:number|null; motivo_rechazo:string|null; fecha_resolucion:string|null; }`

## 2. Página PÚBLICA (sin la navegación interna)
- Ruta nueva (sugerida `/solicitud`; ajústala si prefieres otra) que se renderice SIN el shell/menú
  interno de la app (es para clientes, no muestra navegación ni datos internos).
- Formulario: `nombre_contacto`*, `empresa`, `email_contacto`*, `telefono_contacto`,
  `numero_serie_texto`, `part_number_texto`, `titulo`*, `descripcion_problema`* (textarea), y un campo
  OCULTO honeypot `website` (input no visible, sin autocompletar). (* = obligatorio.)
- `POST /api/solicitudes` con esos campos. Tras 201 → pantalla de agradecimiento mostrando el `codigo`
  ("Hemos recibido tu solicitud {codigo}"). Maneja 400 (rechazo honeypot) y 422 (email inválido).

## 3. Pantalla INTERNA `/solicitudes` (en la app, con su nav)
- Lista (`GET /api/solicitudes?estado=`) con filtro por estado + badge (pendiente/aprobada/rechazada).
- Fila → detalle (o modal) con los datos del cliente y el problema.
- **Aprobar** (solo si pendiente): modal donde el técnico elige el **Equipo** real (selector de
  `/api/equipos`) o componente, **tipo** (rma/soporte_venta/soporte_tecnico/calibracion), **prioridad**
  (baja/media/alta), **asignado_a**, y opcional **en_garantia** → `POST /api/solicitudes/{id}/aprobar`.
  Al 201 (devuelve la incidencia) navega a `/incidencias/$id` de la incidencia creada.
- **Rechazar** (solo si pendiente): pide `motivo` → `POST /api/solicitudes/{id}/rechazar`.
- Entrada "Solicitudes" en el menú interno (con contador de pendientes si quieres).

Usa EXACTAMENTE los nombres de campo de arriba; no inventes endpoints.
```

- [ ] **Step 2: Update README índice**

En `docs/lovable/README.md`, en "Mejoras sueltas", añade:
```markdown
| 18 | `18_solicitud_soporte.md` | **Solicitud de soporte del cliente**: formulario PÚBLICO (sin nav interna) que crea una solicitud + pantalla interna `/solicitudes` (aprobar→crea incidencia / rechazar). Backend `POST /api/solicitudes` (público, honeypot, aviso correo a support@6tlengineering.com), `GET /api/solicitudes`, `POST .../aprobar`, `POST .../rechazar`. |
```

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/18_solicitud_soporte.md docs/lovable/README.md
git commit -m "docs: prompt Lovable 18 — solicitud de soporte del cliente"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

- [ ] **Step 4: (Manual, fuera del plan)** Pegar el prompt 18 en Lovable; `git pull` del submódulo, `bun
  install`, `bun x tsc --noEmit`, smoke. Y configurar las variables SMTP (`SMTP_HOST/PORT/USER/PASSWORD`)
  en el entorno del backend para que los avisos salgan de verdad.

---

## Self-review (cobertura del spec)

- **Entidad `SolicitudSoporte` con todos los campos:** Task 1. ✅
- **`SOL-NNNN`:** Task 1 (`generar_codigo`). ✅
- **POST público + honeypot + validación email + dispara correo:** Task 3. ✅
- **Correo SMTP best-effort + inyectable + sin config no rompe:** Task 2 (+ uso en Task 3). ✅
- **GET lista/filtro + detalle:** Task 3. ✅
- **Aprobar crea incidencia (código por tipo, copia titulo/descr, en_garantia auto en RMA), enlaza, 409 si no pendiente, 404 equipo, requiere sujeto:** Task 4. ✅
- **Rechazar + motivo + 409:** Task 4. ✅
- **Tabla nueva sin migración (create_all):** Task 5 smoke confirma. ✅
- **Frontend público sin shell + pantalla interna:** Task 6 (prompt). ✅
- **Fuera de alcance (auth/rate-limit, email al cliente, captcha, URL definitiva):** no implementado. ✅

Consistencia de tipos: `SolicitudSoporte`, `SolicitudCreate/Out`, `AprobarSolicitudPayload`
(`tipo`/`prioridad`/`equipo_id`/`componente_id`/`asignado_a`/`en_garantia`), `RechazarSolicitudPayload`
(`motivo`), `svc.generar_codigo/aprobar/rechazar/SolicitudError`, `email_notify.enviar_aviso_solicitud`
— usados igual en Tasks 1-4 y el prompt 6. Email validado con regex (sin dependencia nueva).
```
