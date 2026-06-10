# Motor de Fabricantes y RMA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un maestro de fabricantes, un bucle de activación de garantía por componente y derivaciones (RMA externo / flujo interno) ligadas a incidencia, en el backend de 6TL Postventa.

**Architecture:** Patrón existente del proyecto — modelos SQLAlchemy 2.0 (`Mapped`) en `app/models.py`; lógica pura duck-typed en módulos `app/*.py` (como `app/garantia.py`); servicios `app/*_service.py` que reciben `Session` y lanzan una excepción de negocio (→ HTTP 409); routers en `app/routers/*.py` registrados en `app/main.py` con `Depends(get_current_user)`; emails best-effort con transporte inyectable (como `app/email_notify.py`); migración idempotente en `app/migrations.py`. Tests con pytest y SQLite en memoria (`tests/conftest.py`: fixtures `db_session`, `client`, `client_sin_auth`).

**Tech Stack:** Python, FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest, SQLite.

**Convenciones a respetar:**
- Todos los ficheros backend cuelgan de `C:\Users\rllavall\6TL Postventa\backend\`. Las rutas de abajo son relativas a esa carpeta.
- Ejecutar pytest **desde `backend/`**: `python -m pytest tests/ -q`.
- ⚠️ El seeder de ayuda toca `postventa.db` al importar `app.main`; **parar uvicorn antes de correr tests**.
- Los tests usan SQLite en memoria, no la BD real.
- Trabajamos en la rama `feature/motor-fabricantes-rma` (ya creada).

---

## File Structure

**Nuevos:**
- `app/fabricantes.py` — lógica pura: a qué email se escribe por marca, si requiere web.
- `app/garantia_fabricante.py` — lógica pura: `fecha_fin` y `estado_cobertura` de una garantía de fabricante.
- `app/garantia_fabricante_service.py` — servicio: activar / confirmar garantía.
- `app/derivaciones.py` — lógica pura: validez de transiciones de estado.
- `app/derivaciones_service.py` — servicio: crear derivación, avanzar estado, cerrar (avanza incidencia).
- `app/fabricantes_email.py` — emails best-effort de activación de garantía y de RMA.
- `app/fabricantes_seed.py` — siembra `Fabricante` desde el texto libre `Producto.fabricante`.
- `app/routers/fabricantes.py` — CRUD `/api/fabricantes`.
- `app/routers/garantia_fabricante.py` — `/api/componentes/{id}/garantia/*` y `/api/garantias/pendientes`.
- `app/routers/derivaciones.py` — `/api/incidencias/{id}/derivaciones` y `PATCH /api/derivaciones/{id}`.
- Tests: `tests/test_fabricantes_modelo.py`, `tests/test_fabricantes_logica.py`, `tests/test_garantia_fabricante_logica.py`, `tests/test_garantia_fabricante_service.py`, `tests/test_fabricantes_email.py`, `tests/test_derivaciones_logica.py`, `tests/test_derivaciones_service.py`, `tests/test_fabricantes_api.py`, `tests/test_garantia_fabricante_api.py`, `tests/test_derivaciones_api.py`, `tests/test_fabricantes_seed.py`.

**Modificados:**
- `app/models.py` — 3 entidades nuevas + `Producto.fabricante_id` + constantes.
- `app/migrations.py` — `productos.fabricante_id` en `_COLUMNAS_NUEVAS`.
- `app/schemas.py` — schemas de fabricante, garantía y derivación.
- `app/ayuda_seed.py` — tópicos de ayuda nuevos.
- `app/main.py` — registrar routers nuevos + llamar a la siembra de fabricantes.
- `tests/test_migrations.py` — cobertura de `productos.fabricante_id`.

---

## Task 1: Modelos (Fabricante, GarantiaFabricante, Derivacion + Producto.fabricante_id)

**Files:**
- Modify: `app/models.py`
- Test: `tests/test_fabricantes_modelo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fabricantes_modelo.py
from datetime import date

from app import models


def test_fabricante_se_crea(db_session):
    f = models.Fabricante(nombre="National Instruments", email_service="svc@ni.com",
                          requiere_activacion_web=True)
    db_session.add(f)
    db_session.commit()
    assert f.id is not None
    assert f.requiere_activacion_web is True


def test_producto_enlaza_fabricante(db_session):
    f = models.Fabricante(nombre="Keysight")
    db_session.add(f)
    db_session.commit()
    p = models.Producto(part_number="PN-1", tipo="componente", descripcion="DMM",
                        fabricante_id=f.id)
    db_session.add(p)
    db_session.commit()
    assert p.fabricante_id == f.id


def test_garantia_fabricante_y_derivacion_se_crean(db_session):
    g = models.GarantiaFabricante(componente_id=1, estado="pendiente_activacion",
                                  fecha_solicitud=date(2026, 6, 1), meses_garantia=24)
    d = models.Derivacion(incidencia_id=1, tipo="externa_fabricante",
                          tu_referencia="RMA-0001", estado="pendiente",
                          fecha_creacion=date(2026, 6, 1))
    db_session.add_all([g, d])
    db_session.commit()
    assert g.id is not None and d.id is not None
    assert g.estado == "pendiente_activacion"
    assert d.estado == "pendiente"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fabricantes_modelo.py -q`
Expected: FAIL (`AttributeError: module 'app.models' has no attribute 'Fabricante'`).

- [ ] **Step 3: Add constants near the other constant lists at the top of `app/models.py` (after line 18)**

```python
ESTADOS_GARANTIA_FAB = ["no_aplica", "pendiente_activacion", "activada", "rechazada"]
TIPOS_DERIVACION = ["externa_fabricante", "interna_departamento"]
ESTADOS_DERIVACION = ["pendiente", "enviada", "en_proveedor", "recibida", "cerrada"]
```

- [ ] **Step 4: Add `fabricante_id` to `Producto` (inside class `Producto`, after the `pn_fabricante` line ~62)**

```python
    fabricante_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fabricantes.id"), nullable=True)
```

- [ ] **Step 5: Add the three new classes at the end of `app/models.py` (after `AyudaTopico`)**

```python
class Fabricante(Base):
    __tablename__ = "fabricantes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, unique=True)
    email_service: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email_rma: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    url_activacion_garantia: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    requiere_activacion_web: Mapped[bool] = mapped_column(Boolean, default=False)
    politica_rma: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class GarantiaFabricante(Base):
    __tablename__ = "garantias_fabricante"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    componente_id: Mapped[int] = mapped_column(ForeignKey("componentes.id"), unique=True)
    fabricante_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fabricantes.id"), nullable=True)
    estado: Mapped[str] = mapped_column(String, default="pendiente_activacion")
    fecha_solicitud: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_activacion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    meses_garantia: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    referencia_fabricante: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    responsable: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    @property
    def fecha_fin(self):
        from app import garantia_fabricante
        return garantia_fabricante.fecha_fin(self)

    @property
    def estado_cobertura(self) -> str:
        from datetime import date as _date
        from app import garantia_fabricante
        return garantia_fabricante.estado_cobertura(self, _date.today())


class Derivacion(Base):
    __tablename__ = "derivaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incidencia_id: Mapped[int] = mapped_column(ForeignKey("incidencias.id"))
    tipo: Mapped[str] = mapped_column(String)
    fabricante_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fabricantes.id"), nullable=True)
    departamento: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tu_referencia: Mapped[str] = mapped_column(String, unique=True)
    referencia_externa: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    estado: Mapped[str] = mapped_column(String, default="pendiente")
    fecha_creacion: Mapped[date] = mapped_column(Date)
    fecha_envio: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_cierre: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_fabricantes_modelo.py -q`
Expected: PASS (3 passed). Note: `app/garantia_fabricante.py` aún no existe pero las propiedades sólo lo importan al ser llamadas, no en el test del modelo.

- [ ] **Step 7: Commit**

```bash
git add app/models.py tests/test_fabricantes_modelo.py
git commit -m "feat(models): Fabricante, GarantiaFabricante, Derivacion + Producto.fabricante_id"
```

---

## Task 2: Migración de columna `productos.fabricante_id`

**Files:**
- Modify: `app/migrations.py:18`
- Test: `tests/test_migrations.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_migrations.py`)**

```python
def test_agrega_fabricante_id_a_productos():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with eng.begin() as c:
        c.exec_driver_sql("CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT)")
    add_missing_columns(eng)
    assert "fabricante_id" in _columnas(eng, "productos")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migrations.py::test_agrega_fabricante_id_a_productos -q`
Expected: FAIL (`assert 'fabricante_id' in {...}`).

- [ ] **Step 3: Add the column to `_COLUMNAS_NUEVAS["productos"]` in `app/migrations.py` (line 18)**

```python
    "productos": {"meses_garantia_default": "INTEGER DEFAULT 24", "categoria": "TEXT",
                  "pn_fabricante": "TEXT", "fabricante_id": "INTEGER"},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_migrations.py -q`
Expected: PASS (todos los tests de migración verdes).

- [ ] **Step 5: Commit**

```bash
git add app/migrations.py tests/test_migrations.py
git commit -m "feat(migrations): añade productos.fabricante_id idempotente"
```

---

## Task 3: Lógica pura de fabricantes (`app/fabricantes.py`)

**Files:**
- Create: `app/fabricantes.py`
- Test: `tests/test_fabricantes_logica.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fabricantes_logica.py
from types import SimpleNamespace

from app import fabricantes


def test_destino_activacion_usa_email_service():
    f = SimpleNamespace(email_service="svc@ni.com", email_rma=None)
    assert fabricantes.destino_activacion(f) == "svc@ni.com"


def test_destino_rma_cae_a_service_si_no_hay_email_rma():
    f = SimpleNamespace(email_service="svc@ni.com", email_rma=None)
    assert fabricantes.destino_rma(f) == "svc@ni.com"


def test_destino_rma_prefiere_email_rma():
    f = SimpleNamespace(email_service="svc@ni.com", email_rma="rma@ni.com")
    assert fabricantes.destino_rma(f) == "rma@ni.com"


def test_requiere_web():
    assert fabricantes.requiere_web(SimpleNamespace(requiere_activacion_web=True)) is True
    assert fabricantes.requiere_web(SimpleNamespace(requiere_activacion_web=False)) is False


def test_funciones_toleran_none():
    assert fabricantes.destino_activacion(None) is None
    assert fabricantes.destino_rma(None) is None
    assert fabricantes.requiere_web(None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fabricantes_logica.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.fabricantes'`).

- [ ] **Step 3: Write the implementation**

```python
# app/fabricantes.py
"""Lógica pura de procedimiento por fabricante. Duck-typed: opera sobre
atributos (`email_service`, `email_rma`, `requiere_activacion_web`) y tolera None."""
from __future__ import annotations

from typing import Optional


def destino_activacion(fabricante) -> Optional[str]:
    """Email al que se pide la activación de garantía (None si no hay)."""
    if fabricante is None:
        return None
    return getattr(fabricante, "email_service", None)


def destino_rma(fabricante) -> Optional[str]:
    """Email para RMA; cae al de service si no hay uno específico."""
    if fabricante is None:
        return None
    return getattr(fabricante, "email_rma", None) or getattr(fabricante, "email_service", None)


def requiere_web(fabricante) -> bool:
    """True si la marca exige activar la garantía en su web."""
    if fabricante is None:
        return False
    return bool(getattr(fabricante, "requiere_activacion_web", False))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fabricantes_logica.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/fabricantes.py tests/test_fabricantes_logica.py
git commit -m "feat(fabricantes): lógica pura de destino de email por marca"
```

---

## Task 4: Lógica pura de garantía de fabricante (`app/garantia_fabricante.py`)

**Files:**
- Create: `app/garantia_fabricante.py`
- Test: `tests/test_garantia_fabricante_logica.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_garantia_fabricante_logica.py
from datetime import date
from types import SimpleNamespace

from app import garantia_fabricante as gf


def _g(activacion, meses):
    return SimpleNamespace(fecha_activacion=activacion, meses_garantia=meses)


def test_fecha_fin_suma_meses():
    assert gf.fecha_fin(_g(date(2026, 1, 31), 24)) == date(2028, 1, 31)


def test_fecha_fin_none_si_sin_activar():
    assert gf.fecha_fin(_g(None, 24)) is None
    assert gf.fecha_fin(_g(date(2026, 1, 1), None)) is None


def test_estado_cobertura_sin_activar():
    assert gf.estado_cobertura(_g(None, 24), date(2026, 6, 1)) == "sin_activar"


def test_estado_cobertura_vigente_por_vencer_vencida():
    g = _g(date(2026, 1, 1), 12)  # fin = 2027-01-01
    assert gf.estado_cobertura(g, date(2026, 6, 1)) == "vigente"
    assert gf.estado_cobertura(g, date(2026, 12, 1)) == "por_vencer"  # <= 90 días
    assert gf.estado_cobertura(g, date(2027, 2, 1)) == "vencida"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_garantia_fabricante_logica.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.garantia_fabricante'`).

- [ ] **Step 3: Write the implementation (reutiliza `_add_months` de `app/garantia.py`)**

```python
# app/garantia_fabricante.py
"""Lógica pura de la garantía del fabricante (a nivel componente). Duck-typed
sobre `fecha_activacion` y `meses_garantia`; `hoy` inyectable."""
from __future__ import annotations

from datetime import date
from typing import Optional

from app.garantia import _add_months

UMBRAL_POR_VENCER_DIAS = 90


def fecha_fin(garantia) -> Optional[date]:
    inicio = getattr(garantia, "fecha_activacion", None)
    meses = getattr(garantia, "meses_garantia", None)
    if inicio is None or meses is None:
        return None
    return _add_months(inicio, meses)


def estado_cobertura(garantia, hoy: date, umbral_dias: int = UMBRAL_POR_VENCER_DIAS) -> str:
    fin = fecha_fin(garantia)
    if fin is None:
        return "sin_activar"
    if hoy > fin:
        return "vencida"
    if (fin - hoy).days <= umbral_dias:
        return "por_vencer"
    return "vigente"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_garantia_fabricante_logica.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/garantia_fabricante.py tests/test_garantia_fabricante_logica.py
git commit -m "feat(garantia-fab): cobertura derivada desde fecha de activación"
```

---

## Task 5: Lógica pura de transiciones de derivación (`app/derivaciones.py`)

**Files:**
- Create: `app/derivaciones.py`
- Test: `tests/test_derivaciones_logica.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_derivaciones_logica.py
from app import derivaciones


def test_transicion_valida_avanza_un_paso():
    assert derivaciones.transicion_valida("pendiente", "enviada") is True
    assert derivaciones.transicion_valida("enviada", "en_proveedor") is True
    assert derivaciones.transicion_valida("en_proveedor", "recibida") is True
    assert derivaciones.transicion_valida("recibida", "cerrada") is True


def test_transicion_invalida_salta_pasos_o_retrocede():
    assert derivaciones.transicion_valida("pendiente", "cerrada") is False
    assert derivaciones.transicion_valida("enviada", "pendiente") is False
    assert derivaciones.transicion_valida("cerrada", "recibida") is False


def test_misma_etapa_es_valida_idempotente():
    assert derivaciones.transicion_valida("enviada", "enviada") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_derivaciones_logica.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.derivaciones'`).

- [ ] **Step 3: Write the implementation**

```python
# app/derivaciones.py
"""Lógica pura de transiciones de estado de una derivación (RMA externo /
flujo interno). Una derivación avanza por etapas, sin saltos ni retrocesos."""
from __future__ import annotations

ORDEN = ["pendiente", "enviada", "en_proveedor", "recibida", "cerrada"]


def transicion_valida(actual: str, nuevo: str) -> bool:
    """True si `nuevo` es la misma etapa o la inmediatamente siguiente."""
    if actual not in ORDEN or nuevo not in ORDEN:
        return False
    delta = ORDEN.index(nuevo) - ORDEN.index(actual)
    return delta in (0, 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_derivaciones_logica.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/derivaciones.py tests/test_derivaciones_logica.py
git commit -m "feat(derivaciones): validación pura de transiciones de estado"
```

---

## Task 6: Emails de fabricante (`app/fabricantes_email.py`)

**Files:**
- Create: `app/fabricantes_email.py`
- Test: `tests/test_fabricantes_email.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fabricantes_email.py
from types import SimpleNamespace

from app import fabricantes_email as fe


def test_construir_email_activacion_incluye_serie_y_destino():
    cfg = {"from": "support@6tlengineering.com", "to": "interno@6tl.com"}
    componente = SimpleNamespace(numero_serie="SN-123")
    fabricante = SimpleNamespace(nombre="National", email_service="svc@ni.com", email_rma=None)
    msg = fe.construir_email_activacion(componente, fabricante, cfg)
    assert "SN-123" in msg.get_content()
    assert "National" in msg.get_content()
    assert msg["To"] == "interno@6tl.com"


def test_construir_email_rma_incluye_referencias():
    cfg = {"from": "support@6tlengineering.com", "to": "interno@6tl.com"}
    derivacion = SimpleNamespace(tu_referencia="RMA-0007", referencia_externa=None)
    fabricante = SimpleNamespace(nombre="Keysight", email_service=None, email_rma="rma@key.com")
    msg = fe.construir_email_rma(derivacion, fabricante, cfg)
    assert "RMA-0007" in msg.get_content()
    assert "Keysight" in msg.get_content()


def test_enviar_es_best_effort_y_usa_transporte_inyectado():
    enviados = []
    cfg = {"from": "a@b.c", "to": "d@e.f"}
    componente = SimpleNamespace(numero_serie="SN-9")
    fabricante = SimpleNamespace(nombre="NI", email_service="svc@ni.com", email_rma=None)
    ok = fe.enviar_activacion(componente, fabricante, transporte=lambda m, c: enviados.append(m))
    assert ok is True
    assert len(enviados) == 1


def test_enviar_devuelve_false_si_transporte_lanza():
    def _boom(m, c):
        raise RuntimeError("smtp caído")
    componente = SimpleNamespace(numero_serie="SN-9")
    fabricante = SimpleNamespace(nombre="NI", email_service="svc@ni.com", email_rma=None)
    assert fe.enviar_activacion(componente, fabricante, transporte=_boom) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fabricantes_email.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.fabricantes_email'`).

- [ ] **Step 3: Write the implementation**

```python
# app/fabricantes_email.py
"""Emails best-effort para activación de garantía y RMA hacia fabricante.
Nunca relanzan. El transporte `(msg, cfg) -> None` es inyectable para tests."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from app import fabricantes as fab

log = logging.getLogger(__name__)


def _config() -> dict:
    return {
        "from": os.environ.get("SMTP_FROM", "support@6tlengineering.com"),
        "to": os.environ.get("FABRICANTES_EMAIL_TO", "support@6tlengineering.com"),
        "host": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", "587") or "587"),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
    }


def _enviar_smtp(msg: EmailMessage, cfg: dict) -> None:
    with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
        s.starttls()
        if cfg["user"]:
            s.login(cfg["user"], cfg["password"])
        s.send_message(msg)


def construir_email_activacion(componente, fabricante, cfg: dict) -> EmailMessage:
    msg = EmailMessage()
    nombre = getattr(fabricante, "nombre", "fabricante")
    serie = getattr(componente, "numero_serie", "-")
    destino_fab = fab.destino_activacion(fabricante) or "-"
    msg["Subject"] = f"Activación de garantía {nombre} — SN {serie}"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    cuerpo = (
        f"Solicitud de activación de garantía.\n\n"
        f"Fabricante: {nombre}\n"
        f"Número de serie: {serie}\n"
        f"Email del fabricante: {destino_fab}\n"
        f"Requiere activación web: {'sí' if fab.requiere_web(fabricante) else 'no'}\n\n"
        f"Activa la garantía con el fabricante y registra la fecha y la referencia "
        f"en la ficha del componente.\n"
    )
    msg.set_content(cuerpo)
    return msg


def construir_email_rma(derivacion, fabricante, cfg: dict) -> EmailMessage:
    msg = EmailMessage()
    nombre = getattr(fabricante, "nombre", "fabricante")
    tu_ref = getattr(derivacion, "tu_referencia", "-")
    ref_ext = getattr(derivacion, "referencia_externa", None) or "(pendiente)"
    destino_fab = fab.destino_rma(fabricante) or "-"
    msg["Subject"] = f"RMA {tu_ref} hacia {nombre}"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    cuerpo = (
        f"Apertura de RMA hacia fabricante.\n\n"
        f"Fabricante: {nombre}\n"
        f"Referencia interna (nuestra): {tu_ref}\n"
        f"Referencia del fabricante: {ref_ext}\n"
        f"Email del fabricante: {destino_fab}\n"
    )
    msg.set_content(cuerpo)
    return msg


def _enviar(construir, *args, transporte=None) -> bool:
    cfg = _config()
    enviar = transporte or _enviar_smtp
    if transporte is None and not cfg["host"]:
        log.info("SMTP no configurado; no se envía email de fabricante")
        return False
    try:
        enviar(construir(*args, cfg), cfg)
        return True
    except Exception:
        log.exception("Fallo enviando email de fabricante")
        return False


def enviar_activacion(componente, fabricante, transporte=None) -> bool:
    return _enviar(construir_email_activacion, componente, fabricante, transporte=transporte)


def enviar_rma(derivacion, fabricante, transporte=None) -> bool:
    return _enviar(construir_email_rma, derivacion, fabricante, transporte=transporte)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fabricantes_email.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/fabricantes_email.py tests/test_fabricantes_email.py
git commit -m "feat(fabricantes): emails best-effort de activación y RMA"
```

---

## Task 7: Servicio de garantía de fabricante (`app/garantia_fabricante_service.py`)

**Files:**
- Create: `app/garantia_fabricante_service.py`
- Test: `tests/test_garantia_fabricante_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_garantia_fabricante_service.py
from datetime import date

import pytest

from app import garantia_fabricante_service as svc
from app import models


def _componente_con_fabricante(db):
    fab = models.Fabricante(nombre="National", email_service="svc@ni.com")
    db.add(fab)
    db.flush()
    prod = models.Producto(part_number="PN-DMM", tipo="componente", descripcion="DMM",
                          fabricante_id=fab.id, meses_garantia_default=24)
    db.add(prod)
    db.flush()
    comp = models.Componente(numero_serie="SN-1", producto_id=prod.id)
    db.add(comp)
    db.flush()
    return comp, fab


def test_activar_crea_registro_pendiente(db_session):
    comp, fab = _componente_con_fabricante(db_session)
    g = svc.activar(db_session, comp, meses_garantia=24, responsable="Galarzo",
                    hoy=date(2026, 6, 1))
    assert g.estado == "pendiente_activacion"
    assert g.fecha_solicitud == date(2026, 6, 1)
    assert g.fabricante_id == fab.id
    assert g.responsable == "Galarzo"


def test_activar_dos_veces_reusa_el_registro(db_session):
    comp, _ = _componente_con_fabricante(db_session)
    g1 = svc.activar(db_session, comp, meses_garantia=24, hoy=date(2026, 6, 1))
    g2 = svc.activar(db_session, comp, meses_garantia=12, hoy=date(2026, 6, 2))
    assert g1.id == g2.id  # 1:1 con el componente
    assert g2.meses_garantia == 12


def test_confirmar_activa_y_fija_inicio(db_session):
    comp, _ = _componente_con_fabricante(db_session)
    g = svc.activar(db_session, comp, meses_garantia=24, hoy=date(2026, 6, 1))
    svc.confirmar(db_session, g, fecha_activacion=date(2026, 6, 5), referencia="NI-998")
    assert g.estado == "activada"
    assert g.fecha_activacion == date(2026, 6, 5)
    assert g.referencia_fabricante == "NI-998"


def test_confirmar_sobre_no_pendiente_lanza(db_session):
    comp, _ = _componente_con_fabricante(db_session)
    g = svc.activar(db_session, comp, meses_garantia=24, hoy=date(2026, 6, 1))
    svc.confirmar(db_session, g, fecha_activacion=date(2026, 6, 5))
    with pytest.raises(svc.GarantiaError):
        svc.confirmar(db_session, g, fecha_activacion=date(2026, 6, 9))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_garantia_fabricante_service.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.garantia_fabricante_service'`).

- [ ] **Step 3: Write the implementation**

```python
# app/garantia_fabricante_service.py
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import models


class GarantiaError(Exception):
    """Error de negocio en garantía de fabricante (→ HTTP 409)."""


def obtener(db: Session, componente_id: int) -> Optional[models.GarantiaFabricante]:
    return (
        db.query(models.GarantiaFabricante)
        .filter(models.GarantiaFabricante.componente_id == componente_id)
        .first()
    )


def activar(db: Session, componente: models.Componente, meses_garantia: Optional[int] = None,
            responsable: Optional[str] = None, hoy: Optional[date] = None) -> models.GarantiaFabricante:
    """Crea (o reusa, 1:1) la garantía del componente en `pendiente_activacion`."""
    hoy = hoy or date.today()
    fabricante_id = componente.producto.fabricante_id if componente.producto else None
    if meses_garantia is None and componente.producto is not None:
        meses_garantia = componente.producto.meses_garantia_default
    g = obtener(db, componente.id)
    if g is None:
        g = models.GarantiaFabricante(componente_id=componente.id)
        db.add(g)
    g.fabricante_id = fabricante_id
    g.estado = "pendiente_activacion"
    g.fecha_solicitud = hoy
    g.meses_garantia = meses_garantia
    if responsable is not None:
        g.responsable = responsable
    db.flush()
    return g


def confirmar(db: Session, garantia: models.GarantiaFabricante, fecha_activacion: date,
              referencia: Optional[str] = None) -> models.GarantiaFabricante:
    """Registra el feedback del fabricante: pasa a `activada` y arranca el conteo."""
    if garantia.estado != "pendiente_activacion":
        raise GarantiaError(f"La garantía no está pendiente de activación (estado={garantia.estado})")
    garantia.estado = "activada"
    garantia.fecha_activacion = fecha_activacion
    if referencia is not None:
        garantia.referencia_fabricante = referencia
    db.flush()
    return garantia
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_garantia_fabricante_service.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/garantia_fabricante_service.py tests/test_garantia_fabricante_service.py
git commit -m "feat(garantia-fab): servicio activar/confirmar (bucle cerrado)"
```

---

## Task 8: Servicio de derivaciones (`app/derivaciones_service.py`)

**Files:**
- Create: `app/derivaciones_service.py`
- Test: `tests/test_derivaciones_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_derivaciones_service.py
from datetime import date

import pytest

from app import derivaciones_service as svc
from app import models


def _incidencia(db):
    inc = models.Incidencia(codigo="INC-0001", titulo="DMM no arranca",
                            descripcion_problema="...", fecha_apertura=date(2026, 6, 1))
    db.add(inc)
    db.flush()
    return inc


def test_generar_referencia_incrementa(db_session):
    assert svc.generar_referencia(db_session) == "RMA-0001"
    db_session.add(models.Derivacion(incidencia_id=1, tipo="interna_departamento",
                                     tu_referencia="RMA-0001", estado="pendiente",
                                     fecha_creacion=date(2026, 6, 1)))
    db_session.flush()
    assert svc.generar_referencia(db_session) == "RMA-0002"


def test_crear_externa_asigna_referencia_y_pendiente(db_session):
    inc = _incidencia(db_session)
    d = svc.crear(db_session, inc, tipo="externa_fabricante", fabricante_id=5,
                  hoy=date(2026, 6, 2))
    assert d.tu_referencia == "RMA-0001"
    assert d.estado == "pendiente"
    assert d.tipo == "externa_fabricante"
    assert d.fabricante_id == 5
    assert d.fecha_creacion == date(2026, 6, 2)


def test_crear_interna_exige_departamento(db_session):
    inc = _incidencia(db_session)
    with pytest.raises(svc.DerivacionError):
        svc.crear(db_session, inc, tipo="interna_departamento", hoy=date(2026, 6, 2))


def test_avanzar_un_paso_y_registrar_referencia_externa(db_session):
    inc = _incidencia(db_session)
    d = svc.crear(db_session, inc, tipo="externa_fabricante", fabricante_id=5,
                  hoy=date(2026, 6, 2))
    svc.avanzar(db_session, d, "enviada", hoy=date(2026, 6, 3))
    assert d.estado == "enviada"
    assert d.fecha_envio == date(2026, 6, 3)
    svc.avanzar(db_session, d, "en_proveedor", referencia_externa="NI-RMA-77")
    assert d.referencia_externa == "NI-RMA-77"


def test_avanzar_salto_invalido_lanza(db_session):
    inc = _incidencia(db_session)
    d = svc.crear(db_session, inc, tipo="externa_fabricante", fabricante_id=5,
                  hoy=date(2026, 6, 2))
    with pytest.raises(svc.DerivacionError):
        svc.avanzar(db_session, d, "cerrada")


def test_cerrar_resuelve_la_incidencia(db_session):
    inc = _incidencia(db_session)
    d = svc.crear(db_session, inc, tipo="externa_fabricante", fabricante_id=5,
                  hoy=date(2026, 6, 2))
    for estado in ("enviada", "en_proveedor", "recibida", "cerrada"):
        svc.avanzar(db_session, d, estado, hoy=date(2026, 6, 10))
    assert d.estado == "cerrada"
    assert d.fecha_cierre == date(2026, 6, 10)
    assert inc.estado == "resuelta"
    assert inc.fecha_resolucion == date(2026, 6, 10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_derivaciones_service.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.derivaciones_service'`).

- [ ] **Step 3: Write the implementation**

```python
# app/derivaciones_service.py
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import derivaciones, models


class DerivacionError(Exception):
    """Error de negocio en derivaciones (→ HTTP 409)."""


def generar_referencia(db: Session) -> str:
    """Siguiente `RMA-NNNN` mirando `Derivacion.tu_referencia`."""
    nums = []
    for (ref,) in db.query(models.Derivacion.tu_referencia).all():
        if ref and ref.startswith("RMA-"):
            try:
                nums.append(int(ref.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"RMA-{n:04d}"


def crear(db: Session, incidencia: models.Incidencia, tipo: str,
          fabricante_id: Optional[int] = None, departamento: Optional[str] = None,
          hoy: Optional[date] = None) -> models.Derivacion:
    hoy = hoy or date.today()
    if tipo not in models.TIPOS_DERIVACION:
        raise DerivacionError(f"Tipo de derivación inválido: {tipo}")
    if tipo == "externa_fabricante" and fabricante_id is None:
        raise DerivacionError("Una derivación externa requiere fabricante_id")
    if tipo == "interna_departamento" and not departamento:
        raise DerivacionError("Una derivación interna requiere departamento")
    d = models.Derivacion(
        incidencia_id=incidencia.id,
        tipo=tipo,
        fabricante_id=fabricante_id,
        departamento=departamento,
        tu_referencia=generar_referencia(db),
        estado="pendiente",
        fecha_creacion=hoy,
    )
    db.add(d)
    db.flush()
    return d


def avanzar(db: Session, derivacion: models.Derivacion, nuevo_estado: str,
            referencia_externa: Optional[str] = None, hoy: Optional[date] = None) -> models.Derivacion:
    hoy = hoy or date.today()
    if not derivaciones.transicion_valida(derivacion.estado, nuevo_estado):
        raise DerivacionError(
            f"Transición inválida {derivacion.estado} -> {nuevo_estado}")
    derivacion.estado = nuevo_estado
    if referencia_externa is not None:
        derivacion.referencia_externa = referencia_externa
    if nuevo_estado == "enviada" and derivacion.fecha_envio is None:
        derivacion.fecha_envio = hoy
    if nuevo_estado == "cerrada":
        derivacion.fecha_cierre = hoy
        _resolver_incidencia(db, derivacion.incidencia_id, hoy)
    db.flush()
    return derivacion


def _resolver_incidencia(db: Session, incidencia_id: int, hoy: date) -> None:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None or inc.estado in ("resuelta", "cerrada"):
        return
    inc.estado = "resuelta"
    inc.fecha_resolucion = hoy
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_derivaciones_service.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add app/derivaciones_service.py tests/test_derivaciones_service.py
git commit -m "feat(derivaciones): servicio crear/avanzar/cerrar (cierra incidencia)"
```

---

## Task 9: Schemas (fabricante, garantía, derivación)

**Files:**
- Modify: `app/schemas.py` (añadir al final)
- Test: `tests/test_fabricantes_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fabricantes_schemas.py
from datetime import date

from app import schemas


def test_fabricante_create_defaults():
    f = schemas.FabricanteCreate(nombre="National")
    assert f.requiere_activacion_web is False


def test_garantia_out_incluye_derivados():
    out = schemas.GarantiaFabricanteOut(
        id=1, componente_id=1, fabricante_id=2, estado="activada",
        fecha_solicitud=date(2026, 6, 1), fecha_activacion=date(2026, 6, 5),
        meses_garantia=24, referencia_fabricante="NI-1", responsable="Galarzo",
        fecha_fin=date(2028, 6, 5), estado_cobertura="vigente",
    )
    assert out.estado_cobertura == "vigente"


def test_derivacion_create_y_update():
    c = schemas.DerivacionCreate(tipo="interna_departamento", departamento="Producción")
    assert c.departamento == "Producción"
    u = schemas.DerivacionUpdate(estado="enviada")
    assert u.estado == "enviada"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fabricantes_schemas.py -q`
Expected: FAIL (`AttributeError: module 'app.schemas' has no attribute 'FabricanteCreate'`).

- [ ] **Step 3: Append to `app/schemas.py` (usa el mismo estilo Pydantic v2 que el resto del fichero; `model_config = ConfigDict(from_attributes=True)` para los `*Out`)**

```python
# --- Motor de Fabricantes y RMA ---
from datetime import date as _date_fab  # noqa: E402  (alias local, ver resto del fichero)
from typing import Optional as _Opt_fab  # noqa: E402
from pydantic import BaseModel as _BM_fab, ConfigDict as _CD_fab  # noqa: E402


class FabricanteCreate(_BM_fab):
    nombre: str
    email_service: _Opt_fab[str] = None
    email_rma: _Opt_fab[str] = None
    url_activacion_garantia: _Opt_fab[str] = None
    requiere_activacion_web: bool = False
    politica_rma: _Opt_fab[str] = None
    notas: _Opt_fab[str] = None


class FabricanteUpdate(_BM_fab):
    nombre: _Opt_fab[str] = None
    email_service: _Opt_fab[str] = None
    email_rma: _Opt_fab[str] = None
    url_activacion_garantia: _Opt_fab[str] = None
    requiere_activacion_web: _Opt_fab[bool] = None
    politica_rma: _Opt_fab[str] = None
    notas: _Opt_fab[str] = None


class FabricanteOut(_BM_fab):
    model_config = _CD_fab(from_attributes=True)
    id: int
    nombre: str
    email_service: _Opt_fab[str] = None
    email_rma: _Opt_fab[str] = None
    url_activacion_garantia: _Opt_fab[str] = None
    requiere_activacion_web: bool
    politica_rma: _Opt_fab[str] = None
    notas: _Opt_fab[str] = None


class GarantiaActivarPayload(_BM_fab):
    meses_garantia: _Opt_fab[int] = None
    responsable: _Opt_fab[str] = None


class GarantiaConfirmarPayload(_BM_fab):
    fecha_activacion: _date_fab
    referencia: _Opt_fab[str] = None


class GarantiaFabricanteOut(_BM_fab):
    model_config = _CD_fab(from_attributes=True)
    id: int
    componente_id: int
    fabricante_id: _Opt_fab[int] = None
    estado: str
    fecha_solicitud: _Opt_fab[_date_fab] = None
    fecha_activacion: _Opt_fab[_date_fab] = None
    meses_garantia: _Opt_fab[int] = None
    referencia_fabricante: _Opt_fab[str] = None
    responsable: _Opt_fab[str] = None
    fecha_fin: _Opt_fab[_date_fab] = None
    estado_cobertura: str


class DerivacionCreate(_BM_fab):
    tipo: str
    fabricante_id: _Opt_fab[int] = None
    departamento: _Opt_fab[str] = None
    notas: _Opt_fab[str] = None


class DerivacionUpdate(_BM_fab):
    estado: _Opt_fab[str] = None
    referencia_externa: _Opt_fab[str] = None
    notas: _Opt_fab[str] = None


class DerivacionOut(_BM_fab):
    model_config = _CD_fab(from_attributes=True)
    id: int
    incidencia_id: int
    tipo: str
    fabricante_id: _Opt_fab[int] = None
    departamento: _Opt_fab[str] = None
    tu_referencia: str
    referencia_externa: _Opt_fab[str] = None
    estado: str
    fecha_creacion: _date_fab
    fecha_envio: _Opt_fab[_date_fab] = None
    fecha_cierre: _Opt_fab[_date_fab] = None
    notas: _Opt_fab[str] = None
```

> Nota para el implementador: si `app/schemas.py` ya importa `date`, `Optional`, `BaseModel`, `ConfigDict` a nivel de módulo, usa esos nombres directamente y elimina los alias `_*_fab`. Los alias evitan colisiones si los reusas; revisa la cabecera del fichero antes.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fabricantes_schemas.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py tests/test_fabricantes_schemas.py
git commit -m "feat(schemas): fabricante, garantía y derivación"
```

---

## Task 10: Router CRUD de fabricantes (`app/routers/fabricantes.py`)

**Files:**
- Create: `app/routers/fabricantes.py`
- Modify: `app/main.py` (registrar router)
- Test: `tests/test_fabricantes_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fabricantes_api.py
def test_crud_fabricante(client):
    r = client.post("/api/fabricantes", json={"nombre": "National", "email_service": "svc@ni.com"})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]

    r = client.get("/api/fabricantes")
    assert r.status_code == 200
    assert any(f["id"] == fid for f in r.json())

    r = client.put(f"/api/fabricantes/{fid}", json={"requiere_activacion_web": True})
    assert r.status_code == 200
    assert r.json()["requiere_activacion_web"] is True

    r = client.delete(f"/api/fabricantes/{fid}")
    assert r.status_code == 204
    assert client.get(f"/api/fabricantes/{fid}").status_code == 404


def test_nombre_duplicado_da_409(client):
    client.post("/api/fabricantes", json={"nombre": "Keysight"})
    r = client.post("/api/fabricantes", json={"nombre": "Keysight"})
    assert r.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fabricantes_api.py -q`
Expected: FAIL (404 en todas las rutas — router no registrado).

- [ ] **Step 3: Write the router**

```python
# app/routers/fabricantes.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import FabricanteCreate, FabricanteOut, FabricanteUpdate

router = APIRouter(prefix="/api/fabricantes", tags=["fabricantes"])


def _o_404(db: Session, fabricante_id: int) -> models.Fabricante:
    f = db.get(models.Fabricante, fabricante_id)
    if f is None:
        raise HTTPException(404, "Fabricante no encontrado")
    return f


@router.post("", response_model=FabricanteOut, status_code=201)
def crear(payload: FabricanteCreate, db: Session = Depends(get_db)) -> models.Fabricante:
    f = models.Fabricante(**payload.model_dump())
    db.add(f)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un fabricante con ese nombre")
    db.refresh(f)
    return f


@router.get("", response_model=list[FabricanteOut])
def listar(db: Session = Depends(get_db)) -> list[models.Fabricante]:
    return db.query(models.Fabricante).order_by(models.Fabricante.nombre).all()


@router.get("/{fabricante_id}", response_model=FabricanteOut)
def detalle(fabricante_id: int, db: Session = Depends(get_db)) -> models.Fabricante:
    return _o_404(db, fabricante_id)


@router.put("/{fabricante_id}", response_model=FabricanteOut)
def editar(fabricante_id: int, payload: FabricanteUpdate,
           db: Session = Depends(get_db)) -> models.Fabricante:
    f = _o_404(db, fabricante_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(f, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un fabricante con ese nombre")
    db.refresh(f)
    return f


@router.delete("/{fabricante_id}", status_code=204)
def borrar(fabricante_id: int, db: Session = Depends(get_db)) -> None:
    f = _o_404(db, fabricante_id)
    db.delete(f)
    db.commit()
```

- [ ] **Step 4: Register the router in `app/main.py` (junto a los demás `include_router`, antes de `auth`)**

```python
from app.routers import fabricantes
app.include_router(fabricantes.router, dependencies=[Depends(get_current_user)])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_fabricantes_api.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/routers/fabricantes.py app/main.py tests/test_fabricantes_api.py
git commit -m "feat(api): CRUD /api/fabricantes"
```

---

## Task 11: Router de garantía de fabricante (`app/routers/garantia_fabricante.py`)

**Files:**
- Create: `app/routers/garantia_fabricante.py`
- Modify: `app/main.py` (registrar router)
- Test: `tests/test_garantia_fabricante_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_garantia_fabricante_api.py
def _crea_componente(client):
    fab = client.post("/api/fabricantes", json={"nombre": "National", "email_service": "svc@ni.com"}).json()
    prod = client.post("/api/productos", json={
        "part_number": "PN-DMM", "tipo": "componente", "descripcion": "DMM",
        "fabricante_id": fab["id"], "meses_garantia_default": 24,
    }).json()
    comp = client.post("/api/componentes", json={
        "numero_serie": "SN-1", "producto_id": prod["id"],
    }).json()
    return comp["id"], fab["id"]


def test_activar_confirmar_y_pendientes(client):
    comp_id, _ = _crea_componente(client)

    r = client.post(f"/api/componentes/{comp_id}/garantia/activar",
                    json={"responsable": "Galarzo"})
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "pendiente_activacion"

    r = client.get("/api/garantias/pendientes")
    assert r.status_code == 200
    assert any(g["componente_id"] == comp_id for g in r.json())

    r = client.post(f"/api/componentes/{comp_id}/garantia/confirmar",
                    json={"fecha_activacion": "2026-06-05", "referencia": "NI-9"})
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "activada"
    assert body["fecha_fin"] == "2028-06-05"

    # tras confirmar ya no aparece en pendientes
    r = client.get("/api/garantias/pendientes")
    assert not any(g["componente_id"] == comp_id for g in r.json())


def test_confirmar_sin_activar_da_404(client):
    comp_id, _ = _crea_componente(client)
    r = client.post(f"/api/componentes/{comp_id}/garantia/confirmar",
                    json={"fecha_activacion": "2026-06-05"})
    assert r.status_code == 404
```

> Nota: si los payloads de `/api/productos` o `/api/componentes` difieren, ajústalos a sus schemas reales (`app/schemas.py`). El resto del test no cambia.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_garantia_fabricante_api.py -q`
Expected: FAIL (404 en `/garantia/activar`).

- [ ] **Step 3: Write the router**

```python
# app/routers/garantia_fabricante.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import fabricantes as fab
from app import fabricantes_email, garantia_fabricante_service as svc, models
from app.db import get_db
from app.schemas import GarantiaActivarPayload, GarantiaConfirmarPayload, GarantiaFabricanteOut

router = APIRouter(prefix="/api", tags=["garantia-fabricante"])


def _componente_o_404(db: Session, componente_id: int) -> models.Componente:
    c = db.get(models.Componente, componente_id)
    if c is None:
        raise HTTPException(404, "Componente no encontrado")
    return c


@router.post("/componentes/{componente_id}/garantia/activar",
             response_model=GarantiaFabricanteOut, status_code=201)
def activar(componente_id: int, payload: GarantiaActivarPayload,
            db: Session = Depends(get_db)) -> models.GarantiaFabricante:
    comp = _componente_o_404(db, componente_id)
    g = svc.activar(db, comp, meses_garantia=payload.meses_garantia,
                    responsable=payload.responsable)
    fabricante = db.get(models.Fabricante, g.fabricante_id) if g.fabricante_id else None
    if fabricante is not None and fab.destino_activacion(fabricante):
        fabricantes_email.enviar_activacion(comp, fabricante)
    db.commit()
    db.refresh(g)
    return g


@router.post("/componentes/{componente_id}/garantia/confirmar",
             response_model=GarantiaFabricanteOut)
def confirmar(componente_id: int, payload: GarantiaConfirmarPayload,
              db: Session = Depends(get_db)) -> models.GarantiaFabricante:
    _componente_o_404(db, componente_id)
    g = svc.obtener(db, componente_id)
    if g is None:
        raise HTTPException(404, "El componente no tiene garantía de fabricante iniciada")
    try:
        svc.confirmar(db, g, fecha_activacion=payload.fecha_activacion, referencia=payload.referencia)
    except svc.GarantiaError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(g)
    return g


@router.get("/componentes/{componente_id}/garantia", response_model=GarantiaFabricanteOut)
def detalle(componente_id: int, db: Session = Depends(get_db)) -> models.GarantiaFabricante:
    _componente_o_404(db, componente_id)
    g = svc.obtener(db, componente_id)
    if g is None:
        raise HTTPException(404, "El componente no tiene garantía de fabricante")
    return g


@router.get("/garantias/pendientes", response_model=list[GarantiaFabricanteOut])
def pendientes(db: Session = Depends(get_db)) -> list[models.GarantiaFabricante]:
    return (
        db.query(models.GarantiaFabricante)
        .filter(models.GarantiaFabricante.estado == "pendiente_activacion")
        .order_by(models.GarantiaFabricante.fecha_solicitud)
        .all()
    )
```

- [ ] **Step 4: Register the router in `app/main.py` (tras `fabricantes`)**

```python
from app.routers import garantia_fabricante
app.include_router(garantia_fabricante.router, dependencies=[Depends(get_current_user)])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_garantia_fabricante_api.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/routers/garantia_fabricante.py app/main.py tests/test_garantia_fabricante_api.py
git commit -m "feat(api): activar/confirmar garantía de fabricante + cola de pendientes"
```

---

## Task 12: Router de derivaciones (`app/routers/derivaciones.py`)

**Files:**
- Create: `app/routers/derivaciones.py`
- Modify: `app/main.py` (registrar router)
- Test: `tests/test_derivaciones_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_derivaciones_api.py
from datetime import date

from app import models


def _incidencia(db_session):
    inc = models.Incidencia(codigo="INC-9", titulo="t", descripcion_problema="d",
                            fecha_apertura=date(2026, 6, 1))
    db_session.add(inc)
    db_session.commit()
    return inc.id


def test_crear_listar_y_avanzar_derivacion(client, db_session):
    inc_id = _incidencia(db_session)
    fab = client.post("/api/fabricantes", json={"nombre": "National", "email_service": "svc@ni.com"}).json()

    r = client.post(f"/api/incidencias/{inc_id}/derivaciones",
                    json={"tipo": "externa_fabricante", "fabricante_id": fab["id"]})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["tu_referencia"] == "RMA-0001"
    assert d["estado"] == "pendiente"

    r = client.get(f"/api/incidencias/{inc_id}/derivaciones")
    assert r.status_code == 200 and len(r.json()) == 1

    r = client.patch(f"/api/derivaciones/{d['id']}",
                     json={"estado": "enviada", "referencia_externa": "NI-77"})
    assert r.status_code == 200
    assert r.json()["estado"] == "enviada"
    assert r.json()["referencia_externa"] == "NI-77"


def test_interna_sin_departamento_da_409(client, db_session):
    inc_id = _incidencia(db_session)
    r = client.post(f"/api/incidencias/{inc_id}/derivaciones",
                    json={"tipo": "interna_departamento"})
    assert r.status_code == 409


def test_transicion_invalida_da_409(client, db_session):
    inc_id = _incidencia(db_session)
    fab = client.post("/api/fabricantes", json={"nombre": "NI"}).json()
    d = client.post(f"/api/incidencias/{inc_id}/derivaciones",
                    json={"tipo": "externa_fabricante", "fabricante_id": fab["id"]}).json()
    r = client.patch(f"/api/derivaciones/{d['id']}", json={"estado": "cerrada"})
    assert r.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_derivaciones_api.py -q`
Expected: FAIL (404 en `/derivaciones`).

- [ ] **Step 3: Write the router**

```python
# app/routers/derivaciones.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import derivaciones_service as svc
from app import fabricantes as fab
from app import fabricantes_email, models
from app.db import get_db
from app.schemas import DerivacionCreate, DerivacionOut, DerivacionUpdate

router = APIRouter(prefix="/api", tags=["derivaciones"])


def _incidencia_o_404(db: Session, incidencia_id: int) -> models.Incidencia:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    return inc


@router.get("/incidencias/{incidencia_id}/derivaciones", response_model=list[DerivacionOut])
def listar(incidencia_id: int, db: Session = Depends(get_db)) -> list[models.Derivacion]:
    _incidencia_o_404(db, incidencia_id)
    return (
        db.query(models.Derivacion)
        .filter(models.Derivacion.incidencia_id == incidencia_id)
        .order_by(models.Derivacion.id.desc())
        .all()
    )


@router.post("/incidencias/{incidencia_id}/derivaciones",
             response_model=DerivacionOut, status_code=201)
def crear(incidencia_id: int, payload: DerivacionCreate,
          db: Session = Depends(get_db)) -> models.Derivacion:
    inc = _incidencia_o_404(db, incidencia_id)
    try:
        d = svc.crear(db, inc, tipo=payload.tipo, fabricante_id=payload.fabricante_id,
                      departamento=payload.departamento)
    except svc.DerivacionError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    if payload.notas is not None:
        d.notas = payload.notas
    if d.tipo == "externa_fabricante" and d.fabricante_id is not None:
        fabricante = db.get(models.Fabricante, d.fabricante_id)
        if fabricante is not None and fab.destino_rma(fabricante):
            fabricantes_email.enviar_rma(d, fabricante)
    db.commit()
    db.refresh(d)
    return d


@router.patch("/derivaciones/{derivacion_id}", response_model=DerivacionOut)
def actualizar(derivacion_id: int, payload: DerivacionUpdate,
               db: Session = Depends(get_db)) -> models.Derivacion:
    d = db.get(models.Derivacion, derivacion_id)
    if d is None:
        raise HTTPException(404, "Derivación no encontrada")
    if payload.notas is not None:
        d.notas = payload.notas
    if payload.estado is not None:
        try:
            svc.avanzar(db, d, payload.estado, referencia_externa=payload.referencia_externa)
        except svc.DerivacionError as e:
            db.rollback()
            raise HTTPException(409, str(e))
    elif payload.referencia_externa is not None:
        d.referencia_externa = payload.referencia_externa
    db.commit()
    db.refresh(d)
    return d
```

- [ ] **Step 4: Register the router in `app/main.py` (tras `garantia_fabricante`)**

```python
from app.routers import derivaciones
app.include_router(derivaciones.router, dependencies=[Depends(get_current_user)])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_derivaciones_api.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add app/routers/derivaciones.py app/main.py tests/test_derivaciones_api.py
git commit -m "feat(api): derivaciones por incidencia + PATCH de transición"
```

---

## Task 13: Siembra de fabricantes desde el texto libre (`app/fabricantes_seed.py`)

**Files:**
- Create: `app/fabricantes_seed.py`
- Modify: `app/main.py` (llamar a la siembra al arrancar)
- Test: `tests/test_fabricantes_seed.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fabricantes_seed.py
from app import fabricantes_seed, models


def test_siembra_crea_fabricantes_y_enlaza(db_session):
    db_session.add_all([
        models.Producto(part_number="P1", tipo="componente", descripcion="DMM", fabricante="National"),
        models.Producto(part_number="P2", tipo="componente", descripcion="Fuente", fabricante="National"),
        models.Producto(part_number="P3", tipo="componente", descripcion="Osc", fabricante="Keysight"),
        models.Producto(part_number="P4", tipo="equipo", descripcion="Banco", fabricante=None),
    ])
    db_session.commit()

    creados = fabricantes_seed.sembrar_fabricantes_desde_texto(db_session)
    db_session.commit()

    assert creados == 2  # National, Keysight
    nombres = {f.nombre for f in db_session.query(models.Fabricante).all()}
    assert nombres == {"National", "Keysight"}
    p1 = db_session.query(models.Producto).filter_by(part_number="P1").one()
    assert p1.fabricante_id is not None


def test_siembra_es_idempotente(db_session):
    db_session.add(models.Producto(part_number="P1", tipo="componente",
                                   descripcion="DMM", fabricante="National"))
    db_session.commit()
    assert fabricantes_seed.sembrar_fabricantes_desde_texto(db_session) == 1
    db_session.commit()
    assert fabricantes_seed.sembrar_fabricantes_desde_texto(db_session) == 0
    db_session.commit()
    assert db_session.query(models.Fabricante).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fabricantes_seed.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.fabricantes_seed'`).

- [ ] **Step 3: Write the implementation**

```python
# app/fabricantes_seed.py
"""Siembra `Fabricante` a partir del texto libre `Producto.fabricante` y enlaza
`Producto.fabricante_id`. Idempotente: empareja por nombre, no duplica."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models


def sembrar_fabricantes_desde_texto(db: Session) -> int:
    """Crea fabricantes que falten y enlaza productos. Devuelve nº de fabricantes creados.

    No hace commit: el llamante decide la transacción.
    """
    existentes = {f.nombre: f for f in db.query(models.Fabricante).all()}
    creados = 0
    productos = (
        db.query(models.Producto)
        .filter(models.Producto.fabricante.isnot(None))
        .all()
    )
    for p in productos:
        nombre = (p.fabricante or "").strip()
        if not nombre:
            continue
        fabricante = existentes.get(nombre)
        if fabricante is None:
            fabricante = models.Fabricante(nombre=nombre)
            db.add(fabricante)
            db.flush()
            existentes[nombre] = fabricante
            creados += 1
        if p.fabricante_id is None:
            p.fabricante_id = fabricante.id
    return creados
```

- [ ] **Step 4: Call the seed at startup in `app/main.py` (junto a `sembrar_ayuda`, dentro del mismo `with SessionLocal()`)**

Modifica el bloque existente (líneas ~26-30):

```python
from app.db import SessionLocal
from app.ayuda_seed import sembrar_ayuda
from app.fabricantes_seed import sembrar_fabricantes_desde_texto

with SessionLocal() as _db:
    sembrar_ayuda(_db)
    sembrar_fabricantes_desde_texto(_db)
    _db.commit()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_fabricantes_seed.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/fabricantes_seed.py app/main.py tests/test_fabricantes_seed.py
git commit -m "feat(fabricantes): siembra desde texto libre Producto.fabricante"
```

---

## Task 14: Tópicos de ayuda contextual

**Files:**
- Modify: `app/ayuda_seed.py`
- Test: `tests/test_ayuda_seed.py` (añadir aserción)

- [ ] **Step 1: Inspect `app/ayuda_seed.py`**

Run: `python -m pytest tests/test_ayuda_seed.py -q` y abre `app/ayuda_seed.py` para ver la estructura (lista/dict de `(clave, titulo, texto, pantalla)`). Sigue exactamente ese formato.

- [ ] **Step 2: Write the failing test (añade a `tests/test_ayuda_seed.py`)**

```python
def test_siembra_incluye_topicos_de_fabricantes(db_session):
    from app.ayuda_seed import sembrar_ayuda
    from app import models
    sembrar_ayuda(db_session)
    db_session.commit()
    claves = {t.clave for t in db_session.query(models.AyudaTopico).all()}
    assert "fabricantes.maestro" in claves
    assert "garantia.activar" in claves
    assert "derivaciones.crear" in claves
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_ayuda_seed.py::test_siembra_incluye_topicos_de_fabricantes -q`
Expected: FAIL (claves no presentes).

- [ ] **Step 4: Add the topics to the seed list in `app/ayuda_seed.py`** (replica el formato exacto de las entradas existentes; estos son los textos)

```python
    ("fabricantes.maestro", "Maestro de fabricantes",
     "Ficha por marca (National, Keysight…): a qué email se escribe para activar "
     "garantía y para RMA, si exige activación en su web, y su política de RMA. "
     "Es la base para automatizar avisos y derivaciones.", "fabricantes"),
    ("garantia.activar", "Activar garantía del fabricante",
     "Inicia la activación de la garantía del instrumento con el fabricante. El "
     "sistema redacta el aviso y deja la garantía 'pendiente de activación' hasta "
     "que registres el feedback (fecha real y referencia), que arranca el conteo.", "componentes"),
    ("garantia.confirmar", "Confirmar activación",
     "Registra la respuesta del fabricante: fecha real de inicio y referencia. A "
     "partir de esa fecha la garantía cuenta y se calcula su vencimiento.", "componentes"),
    ("derivaciones.crear", "Derivar incidencia (RMA / interno)",
     "Abre una derivación desde la incidencia: externa hacia un fabricante (con tu "
     "referencia y la suya) o interna hacia un departamento. Misma mecánica para "
     "ambos; al cerrarse, resuelve la incidencia.", "incidencias"),
```

> Si el formato real usa un dict u objetos en vez de tuplas `(clave, titulo, texto, pantalla)`, adáptalo a ese formato manteniendo las mismas claves y textos.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_ayuda_seed.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/ayuda_seed.py tests/test_ayuda_seed.py
git commit -m "feat(ayuda): tópicos de fabricantes, garantía y derivaciones"
```

---

## Task 15: Suite completa verde + verificación final

**Files:** ninguno (verificación).

- [ ] **Step 1: Stop any running uvicorn** (el seeder de ayuda toca `postventa.db` al importar)

Run (PowerShell): `Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*6TL Postventa*' } | Stop-Process -Force`
(Si no hay procesos, no hace nada.)

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS — todos los tests previos (memoria indica ~333) **más** los nuevos de este plan, sin fallos.

- [ ] **Step 3: Smoke import del app completo** (verifica que `main.py` registra los routers y siembra sin romper)

Run: `python -c "from app.main import app; print([r.path for r in app.routes if 'fabricantes' in r.path or 'garantia' in r.path or 'derivaciones' in r.path])"`
Expected: imprime las rutas nuevas (`/api/fabricantes`, `/api/componentes/{componente_id}/garantia/...`, `/api/garantias/pendientes`, `/api/incidencias/{incidencia_id}/derivaciones`, `/api/derivaciones/{derivacion_id}`).

- [ ] **Step 4: Commit (si quedara algo suelto) y push de la rama**

```bash
git add -A
git commit -m "test: suite completa verde — Motor de Fabricantes y RMA" --allow-empty
git push -u origin feature/motor-fabricantes-rma
```

---

## Self-Review (cobertura del spec)

- **Maestro de fabricantes (#1)** → Task 1 (modelo), Task 2 (migración FK), Task 10 (CRUD), Task 13 (siembra desde texto). ✅
- **Garantía a nivel componente + bucle de activación (#2)** → Task 1 (modelo `GarantiaFabricante`), Task 4 (cobertura derivada), Task 7 (activar/confirmar), Task 11 (API + cola "pendiente del Galarzo" + email). ✅
- **Derivación interna/externa (#3)** → Task 1 (modelo `Derivacion`), Task 5 (transiciones), Task 8 (servicio + cierra incidencia), Task 12 (API + email RMA). ✅
- **Email best-effort + confirmación manual** → Task 6 (emails), integrados en Task 11 y Task 12; confirmación siempre por endpoint manual. ✅
- **Auth + auditoría heredadas** → routers registrados con `Depends(get_current_user)` (Tasks 10-12); el listener de auditoría es global. ✅
- **Ayuda contextual** → Task 14. ✅
- **Migración idempotente + siembra idempotente** → Task 2 (test idempotencia) y Task 13 (test idempotencia). ✅
- **Fuera de alcance** (back-to-back #4, IA #7, upsell #6, alta desde albarán #5): no hay tasks, correcto.

**Consistencia de nombres verificada:** `Fabricante`, `GarantiaFabricante`, `Derivacion`; `fabricantes.destino_activacion/destino_rma/requiere_web`; `garantia_fabricante.fecha_fin/estado_cobertura`; `derivaciones.transicion_valida`; `garantia_fabricante_service.activar/confirmar/obtener/GarantiaError`; `derivaciones_service.crear/avanzar/generar_referencia/DerivacionError`; `fabricantes_email.enviar_activacion/enviar_rma`; `fabricantes_seed.sembrar_fabricantes_desde_texto`. Coherentes entre tasks.
