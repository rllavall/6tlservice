# 6TL Postventa — Incidencias / RMA — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir el núcleo de postventa — registrar incidencias/RMA contra equipos o componentes, seguir un flujo de reparación de 5 estados, y enlazar las acciones de trazabilidad existentes (sustituciones, movimientos) como un expediente consultable.

**Architecture:** Una entidad nueva `Incidencia` + router `/api/incidencias` (CRUD, transición de estado, expediente) + servicio `incidencias_service.py` (generación de código, máquina de estados). Enlace "enfoque A": una FK opcional `incidencia_id` (nullable, default NULL) en las tablas `cambios_configuracion` y `movimientos`, propagada por las operaciones existentes vía un parámetro opcional. Todo aditivo y retrocompatible.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.x (Mapped/mapped_column), SQLite, Pydantic v2, pytest + TestClient. Backend en `:8020`. Ejecutar comandos desde `backend/` con `.venv\Scripts\python.exe`.

**Convenciones del repo (ya establecidas, respétalas):**
- Enums como listas a nivel de módulo en `models.py`; `Literal[...]` en los schemas Pydantic.
- Routers finos; lógica de dominio en módulos de servicio (`trazabilidad.py`).
- Errores: `LookupError` → `HTTPException(404)`, error de dominio → `HTTPException(409)`. `db.rollback()` antes de lanzar; `db.commit()` + `db.refresh()` al final del happy path.
- Tests: fixtures `client` (TestClient con DB en memoria) y `db_session` en `conftest.py`. Un archivo de test por área.
- Comando de tests: `.venv\Scripts\python.exe -m pytest -q` desde `backend/`.

---

## Task 1: Modelo de datos — entidad `Incidencia` + FKs de enlace

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_incidencia_models.py` (Create)

- [ ] **Step 1: Write the failing test `backend/tests/test_incidencia_models.py`**

```python
from datetime import date

from app import models


def test_incidencia_table_and_fields(db_session):
    inc = models.Incidencia(
        codigo="RMA-0001",
        equipo_id=None,
        componente_id=None,
        titulo="No arranca",
        descripcion_problema="El equipo no enciende",
        prioridad="media",
        estado="abierta",
        fecha_apertura=date(2026, 6, 1),
    )
    db_session.add(inc)
    db_session.flush()
    assert inc.id is not None
    assert inc.estado == "abierta"
    # defaults / nullable
    assert inc.asignado_a is None
    assert inc.en_garantia is None
    assert inc.fecha_cierre is None


def test_enlace_incidencia_id_en_eventos(db_session):
    # CambioConfiguracion y Movimiento aceptan incidencia_id opcional
    cc = models.CambioConfiguracion(
        componente_id=1, equipo_id=1, accion="montaje",
        fecha=date(2026, 6, 1), motivo="reparacion", incidencia_id=None,
    )
    mv = models.Movimiento(
        equipo_id=1, ubicacion_destino_id=1, fecha=date(2026, 6, 1),
        motivo="reparacion", incidencia_id=None,
    )
    db_session.add_all([cc, mv])
    db_session.flush()
    assert cc.incidencia_id is None
    assert mv.incidencia_id is None


def test_constantes_incidencia():
    assert models.ESTADOS_INCIDENCIA == [
        "abierta", "diagnostico", "en_reparacion", "resuelta", "cerrada",
    ]
    assert models.PRIORIDADES_INCIDENCIA == ["baja", "media", "alta"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_models.py -q`
Expected: FAIL — `AttributeError: module 'app.models' has no attribute 'Incidencia'`.

- [ ] **Step 3: Add the constants near the other enum lists in `backend/app/models.py`**

Después de la línea `MOTIVOS_CONFIG = [...]` añade:

```python
ESTADOS_INCIDENCIA = ["abierta", "diagnostico", "en_reparacion", "resuelta", "cerrada"]
PRIORIDADES_INCIDENCIA = ["baja", "media", "alta"]
```

- [ ] **Step 4: Add the `Incidencia` class at the end of `backend/app/models.py`**

```python
class Incidencia(Base):
    __tablename__ = "incidencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String, unique=True)
    equipo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipos.id"), nullable=True)
    componente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("componentes.id"), nullable=True)
    titulo: Mapped[str] = mapped_column(String)
    descripcion_problema: Mapped[str] = mapped_column(String)
    prioridad: Mapped[str] = mapped_column(String, default="media")
    estado: Mapped[str] = mapped_column(String, default="abierta")
    asignado_a: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    en_garantia: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    diagnostico: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resolucion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha_apertura: Mapped[date] = mapped_column(Date)
    fecha_diagnostico: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_inicio_reparacion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_resolucion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_cierre: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

- [ ] **Step 5: Add `Boolean` to the SQLAlchemy import at the top of `models.py`**

Cambia la línea de import:

```python
from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
```

- [ ] **Step 6: Add `incidencia_id` to `Movimiento` and `CambioConfiguracion`**

En la clase `Movimiento`, tras la columna `notas`:

```python
    incidencia_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidencias.id"), nullable=True)
```

En la clase `CambioConfiguracion`, tras la columna `notas`:

```python
    incidencia_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidencias.id"), nullable=True)
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_models.py -q`
Expected: PASS (3 passed).

- [ ] **Step 8: Run the full suite to confirm no regressions**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (53 passed: 50 previos + 3 nuevos).

- [ ] **Step 9: Commit**

```bash
git add backend/app/models.py backend/tests/test_incidencia_models.py
git commit -m "feat: Incidencia model + incidencia_id FK on movimientos/cambios"
```

---

## Task 2: Schemas Pydantic de `Incidencia`

**Files:**
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_incidencia_schemas.py` (Create)

- [ ] **Step 1: Write the failing test `backend/tests/test_incidencia_schemas.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas import IncidenciaCreate, TransicionPayload


def test_incidencia_create_requires_al_menos_un_sujeto():
    with pytest.raises(ValidationError):
        IncidenciaCreate(titulo="x", descripcion_problema="y", fecha_apertura="2026-06-01")


def test_incidencia_create_ok_con_equipo():
    m = IncidenciaCreate(
        equipo_id=1, titulo="x", descripcion_problema="y", fecha_apertura="2026-06-01"
    )
    assert m.equipo_id == 1
    assert m.prioridad == "media"  # default


def test_incidencia_create_ok_con_componente():
    m = IncidenciaCreate(
        componente_id=3, titulo="x", descripcion_problema="y", fecha_apertura="2026-06-01"
    )
    assert m.componente_id == 3


def test_transicion_payload_valida_estado():
    ok = TransicionPayload(nuevo_estado="diagnostico")
    assert ok.fecha is None
    with pytest.raises(ValidationError):
        TransicionPayload(nuevo_estado="inventado")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_schemas.py -q`
Expected: FAIL — `ImportError: cannot import name 'IncidenciaCreate'`.

- [ ] **Step 3: Add the schemas at the end of `backend/app/schemas.py`**

Primero añade `model_validator` al import de pydantic en la cabecera del archivo:

```python
from pydantic import BaseModel, ConfigDict, model_validator
```

Luego, al final del archivo:

```python
# --- Incidencia ---
_PRIORIDAD = Literal["baja", "media", "alta"]
_ESTADO_INC = Literal["abierta", "diagnostico", "en_reparacion", "resuelta", "cerrada"]


class IncidenciaCreate(BaseModel):
    equipo_id: Optional[int] = None
    componente_id: Optional[int] = None
    titulo: str
    descripcion_problema: str
    prioridad: _PRIORIDAD = "media"
    asignado_a: Optional[str] = None
    en_garantia: Optional[bool] = None
    fecha_apertura: date

    @model_validator(mode="after")
    def _al_menos_un_sujeto(self) -> "IncidenciaCreate":
        if self.equipo_id is None and self.componente_id is None:
            raise ValueError("La incidencia requiere equipo_id o componente_id (al menos uno)")
        return self


class IncidenciaUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion_problema: Optional[str] = None
    prioridad: Optional[_PRIORIDAD] = None
    asignado_a: Optional[str] = None
    en_garantia: Optional[bool] = None
    diagnostico: Optional[str] = None
    resolucion: Optional[str] = None
    notas: Optional[str] = None


class IncidenciaOut(_ORM):
    id: int
    codigo: str
    equipo_id: Optional[int] = None
    componente_id: Optional[int] = None
    titulo: str
    descripcion_problema: str
    prioridad: str
    estado: str
    asignado_a: Optional[str] = None
    en_garantia: Optional[bool] = None
    diagnostico: Optional[str] = None
    resolucion: Optional[str] = None
    fecha_apertura: date
    fecha_diagnostico: Optional[date] = None
    fecha_inicio_reparacion: Optional[date] = None
    fecha_resolucion: Optional[date] = None
    fecha_cierre: Optional[date] = None
    notas: Optional[str] = None


class TransicionPayload(BaseModel):
    nuevo_estado: _ESTADO_INC
    fecha: Optional[date] = None


class IncidenciaFicha(_ORM):
    incidencia: IncidenciaOut
    equipo: Optional[EquipoOut] = None
    componente: Optional[ComponenteOut] = None
    cliente: Optional[ClienteOut] = None
    cambios_configuracion: list[CambioConfiguracionOut] = []
    movimientos: list[MovimientoOut] = []
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_schemas.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_incidencia_schemas.py
git commit -m "feat: pydantic schemas for Incidencia (+ at-least-one-subject validator)"
```

---

## Task 3: Servicio `incidencias_service.py` — código + máquina de estados

**Files:**
- Create: `backend/app/incidencias_service.py`
- Test: `backend/tests/test_incidencia_service.py` (Create)

- [ ] **Step 1: Write the failing test `backend/tests/test_incidencia_service.py`**

```python
from datetime import date

import pytest

from app import incidencias_service as svc
from app import models


def _nueva(db, **kw):
    inc = models.Incidencia(
        codigo=svc.generar_codigo(db),
        titulo="t", descripcion_problema="d", prioridad="media",
        estado="abierta", fecha_apertura=date(2026, 6, 1), **kw,
    )
    db.add(inc)
    db.flush()
    return inc


def test_generar_codigo_secuencial(db_session):
    assert svc.generar_codigo(db_session) == "RMA-0001"
    _nueva(db_session, equipo_id=None, componente_id=None)
    assert svc.generar_codigo(db_session) == "RMA-0002"


def test_transicion_lineal_sella_fecha(db_session):
    inc = _nueva(db_session, equipo_id=None, componente_id=None)
    svc.transicionar(db_session, inc, "diagnostico", date(2026, 6, 2))
    assert inc.estado == "diagnostico"
    assert inc.fecha_diagnostico == date(2026, 6, 2)


def test_salto_prohibido(db_session):
    inc = _nueva(db_session, equipo_id=None, componente_id=None)
    with pytest.raises(svc.IncidenciaError):
        svc.transicionar(db_session, inc, "resuelta", date(2026, 6, 2))


def test_resuelta_exige_resolucion(db_session):
    inc = _nueva(db_session, equipo_id=None, componente_id=None)
    svc.transicionar(db_session, inc, "diagnostico", date(2026, 6, 2))
    svc.transicionar(db_session, inc, "en_reparacion", date(2026, 6, 3))
    with pytest.raises(svc.IncidenciaError):
        svc.transicionar(db_session, inc, "resuelta", date(2026, 6, 4))
    inc.resolucion = "Sustituida fuente"
    svc.transicionar(db_session, inc, "resuelta", date(2026, 6, 4))
    assert inc.estado == "resuelta"
    assert inc.fecha_resolucion == date(2026, 6, 4)


def test_reabrir_limpia_fechas_conserva_inicio(db_session):
    inc = _nueva(db_session, equipo_id=None, componente_id=None)
    svc.transicionar(db_session, inc, "diagnostico", date(2026, 6, 2))
    svc.transicionar(db_session, inc, "en_reparacion", date(2026, 6, 3))
    inc.resolucion = "ok"
    svc.transicionar(db_session, inc, "resuelta", date(2026, 6, 4))
    svc.transicionar(db_session, inc, "cerrada", date(2026, 6, 5))
    # reabrir
    svc.transicionar(db_session, inc, "en_reparacion", date(2026, 6, 10))
    assert inc.estado == "en_reparacion"
    assert inc.fecha_resolucion is None
    assert inc.fecha_cierre is None
    assert inc.fecha_inicio_reparacion == date(2026, 6, 3)  # conservada
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.incidencias_service'`.

- [ ] **Step 3: Create `backend/app/incidencias_service.py`**

```python
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import models

ORDEN = {e: i for i, e in enumerate(models.ESTADOS_INCIDENCIA)}
FECHA_DE_ESTADO = {
    "diagnostico": "fecha_diagnostico",
    "en_reparacion": "fecha_inicio_reparacion",
    "resuelta": "fecha_resolucion",
    "cerrada": "fecha_cierre",
}


class IncidenciaError(Exception):
    """Transición inválida o guarda de contenido no cumplida (→ 409)."""


def generar_codigo(db: Session) -> str:
    """Siguiente código RMA-NNNN (max sufijo existente + 1)."""
    nums = []
    for (codigo,) in db.query(models.Incidencia.codigo).all():
        if codigo and codigo.startswith("RMA-"):
            try:
                nums.append(int(codigo.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"RMA-{n:04d}"


def transicionar(
    db: Session, inc: models.Incidencia, nuevo_estado: str, fecha: Optional[date]
) -> models.Incidencia:
    actual = inc.estado
    es_reabrir = actual in ("resuelta", "cerrada") and nuevo_estado == "en_reparacion"
    es_avance = ORDEN.get(nuevo_estado, -1) == ORDEN.get(actual, -99) + 1

    if not (es_avance or es_reabrir):
        raise IncidenciaError(
            f"Transición no permitida: {actual} → {nuevo_estado}"
        )
    if nuevo_estado == "resuelta" and not (inc.resolucion and inc.resolucion.strip()):
        raise IncidenciaError("Para resolver la incidencia hace falta una resolución")

    fecha = fecha or date.today()

    if es_reabrir:
        inc.fecha_resolucion = None
        inc.fecha_cierre = None
        inc.estado = "en_reparacion"
        # se conserva fecha_inicio_reparacion original
        db.flush()
        return inc

    inc.estado = nuevo_estado
    campo = FECHA_DE_ESTADO.get(nuevo_estado)
    if campo is not None:
        setattr(inc, campo, fecha)
    db.flush()
    return inc
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_service.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/incidencias_service.py backend/tests/test_incidencia_service.py
git commit -m "feat: incidencias_service — RMA code + state-machine transitions"
```

---

## Task 4: Router `/api/incidencias` — crear + listar

**Files:**
- Create: `backend/app/routers/incidencias.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_incidencias.py` (Create)

- [ ] **Step 1: Write the failing test `backend/tests/test_incidencias.py`**

```python
def _seed_equipo(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    return client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": p["id"]}).json()


def test_crear_incidencia_genera_codigo(client):
    eq = _seed_equipo(client)
    r = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "No arranca",
        "descripcion_problema": "nada", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["codigo"] == "RMA-0001"
    assert body["estado"] == "abierta"


def test_crear_sin_sujeto_422(client):
    r = client.post("/api/incidencias", json={
        "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 422


def test_crear_equipo_inexistente_404(client):
    r = client.post("/api/incidencias", json={
        "equipo_id": 999, "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 404


def test_listar_y_filtros(client):
    eq = _seed_equipo(client)
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "a", "descripcion_problema": "y", "fecha_apertura": "2026-06-01", "prioridad": "alta"})
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "b", "descripcion_problema": "y", "fecha_apertura": "2026-06-02", "prioridad": "baja"})
    assert len(client.get("/api/incidencias").json()) == 2
    assert len(client.get("/api/incidencias?prioridad=alta").json()) == 1
    assert len(client.get(f"/api/incidencias?equipo_id={eq['id']}").json()) == 2
    assert len(client.get("/api/incidencias?estado=abierta").json()) == 2
    assert len(client.get("/api/incidencias?abiertas=true").json()) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencias.py -q`
Expected: FAIL — 404 on `/api/incidencias` (router not registered).

- [ ] **Step 3: Create `backend/app/routers/incidencias.py`**

```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import incidencias_service as svc
from app import models
from app.db import get_db
from app.schemas import IncidenciaCreate, IncidenciaOut

router = APIRouter(prefix="/api/incidencias", tags=["incidencias"])


@router.get("", response_model=list[IncidenciaOut])
def listar(
    estado: Optional[str] = None,
    prioridad: Optional[str] = None,
    equipo_id: Optional[int] = None,
    componente_id: Optional[int] = None,
    asignado_a: Optional[str] = None,
    abiertas: Optional[bool] = None,
    db: Session = Depends(get_db),
) -> list[models.Incidencia]:
    q = db.query(models.Incidencia)
    if estado is not None:
        q = q.filter(models.Incidencia.estado == estado)
    if prioridad is not None:
        q = q.filter(models.Incidencia.prioridad == prioridad)
    if equipo_id is not None:
        q = q.filter(models.Incidencia.equipo_id == equipo_id)
    if componente_id is not None:
        q = q.filter(models.Incidencia.componente_id == componente_id)
    if asignado_a is not None:
        q = q.filter(models.Incidencia.asignado_a == asignado_a)
    if abiertas:
        q = q.filter(models.Incidencia.estado != "cerrada")
    return q.order_by(models.Incidencia.id.desc()).all()


@router.post("", response_model=IncidenciaOut, status_code=201)
def crear(payload: IncidenciaCreate, db: Session = Depends(get_db)) -> models.Incidencia:
    if payload.equipo_id is not None and db.get(models.Equipo, payload.equipo_id) is None:
        raise HTTPException(404, "Equipo no encontrado")
    if payload.componente_id is not None and db.get(models.Componente, payload.componente_id) is None:
        raise HTTPException(404, "Componente no encontrado")
    inc = models.Incidencia(
        codigo=svc.generar_codigo(db),
        estado="abierta",
        **payload.model_dump(),
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc
```

- [ ] **Step 4: Register the router in `backend/app/main.py`**

Tras el bloque de `busqueda` (líneas 42-43), añade:

```python
from app.routers import incidencias
app.include_router(incidencias.router)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencias.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/incidencias.py backend/app/main.py backend/tests/test_incidencias.py
git commit -m "feat: /api/incidencias create + list with filters"
```

---

## Task 5: Router — expediente (`GET /api/incidencias/{id}`)

**Files:**
- Modify: `backend/app/routers/incidencias.py`
- Test: `backend/tests/test_incidencia_ficha.py` (Create)

- [ ] **Step 1: Write the failing test `backend/tests/test_incidencia_ficha.py`**

```python
def _seed(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    cli = client.post("/api/clientes", json={"nombre": "ACME"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": p["id"], "cliente_id": cli["id"]}).json()
    return p, cli, eq


def test_ficha_compone_snapshot(client):
    _p, cli, eq = _seed(client)
    inc = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01",
    }).json()
    r = client.get(f"/api/incidencias/{inc['id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["incidencia"]["codigo"] == "RMA-0001"
    assert body["equipo"]["id"] == eq["id"]
    assert body["cliente"]["nombre"] == "ACME"
    assert body["componente"] is None
    assert body["cambios_configuracion"] == []
    assert body["movimientos"] == []


def test_ficha_404(client):
    assert client.get("/api/incidencias/999").status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_ficha.py -q`
Expected: FAIL — 405/404 (endpoint inexistente).

- [ ] **Step 3: Extend the imports in `backend/app/routers/incidencias.py`**

Reemplaza la línea de import de schemas por:

```python
from app.schemas import (
    CambioConfiguracionOut,
    ClienteOut,
    ComponenteOut,
    EquipoOut,
    IncidenciaCreate,
    IncidenciaFicha,
    IncidenciaOut,
    MovimientoOut,
)
```

- [ ] **Step 4: Add the ficha endpoint at the end of `backend/app/routers/incidencias.py`**

```python
@router.get("/{incidencia_id}", response_model=IncidenciaFicha)
def ficha(incidencia_id: int, db: Session = Depends(get_db)) -> IncidenciaFicha:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")

    eq = db.get(models.Equipo, inc.equipo_id) if inc.equipo_id is not None else None
    comp = db.get(models.Componente, inc.componente_id) if inc.componente_id is not None else None
    # cliente: del equipo de la incidencia, o del equipo del componente si está montado
    cli = None
    eq_para_cliente = eq
    if eq_para_cliente is None and comp is not None and comp.equipo_id is not None:
        eq_para_cliente = db.get(models.Equipo, comp.equipo_id)
    if eq_para_cliente is not None and eq_para_cliente.cliente_id is not None:
        cli = db.get(models.Cliente, eq_para_cliente.cliente_id)

    cambios = (
        db.query(models.CambioConfiguracion)
        .filter(models.CambioConfiguracion.incidencia_id == incidencia_id)
        .order_by(models.CambioConfiguracion.fecha.desc(), models.CambioConfiguracion.id.desc())
        .all()
    )
    movimientos = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.incidencia_id == incidencia_id)
        .order_by(models.Movimiento.fecha.desc(), models.Movimiento.id.desc())
        .all()
    )

    return IncidenciaFicha(
        incidencia=IncidenciaOut.model_validate(inc),
        equipo=EquipoOut.model_validate(eq) if eq is not None else None,
        componente=ComponenteOut.model_validate(comp) if comp is not None else None,
        cliente=ClienteOut.model_validate(cli) if cli is not None else None,
        cambios_configuracion=[CambioConfiguracionOut.model_validate(c) for c in cambios],
        movimientos=[MovimientoOut.model_validate(m) for m in movimientos],
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_ficha.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/incidencias.py backend/tests/test_incidencia_ficha.py
git commit -m "feat: incidencia expediente (GET /api/incidencias/{id})"
```

---

## Task 6: Router — PATCH + DELETE (guarded) + transición

**Files:**
- Modify: `backend/app/routers/incidencias.py`
- Test: `backend/tests/test_incidencia_transiciones.py` (Create)

- [ ] **Step 1: Write the failing test `backend/tests/test_incidencia_transiciones.py`**

```python
def _inc(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": p["id"]}).json()
    return client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01",
    }).json()


def test_patch_campos_libres(client):
    inc = _inc(client)
    r = client.patch(f"/api/incidencias/{inc['id']}", json={"asignado_a": "Cim", "prioridad": "alta"})
    assert r.status_code == 200, r.text
    assert r.json()["asignado_a"] == "Cim"
    assert r.json()["prioridad"] == "alta"


def test_transicion_lineal_y_fechas(client):
    inc = _inc(client)
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "diagnostico", "fecha": "2026-06-02"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "diagnostico"
    assert r.json()["fecha_diagnostico"] == "2026-06-02"


def test_transicion_salto_409(client):
    inc = _inc(client)
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "resuelta"})
    assert r.status_code == 409


def test_transicion_resuelta_exige_resolucion(client):
    inc = _inc(client)
    client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "diagnostico"})
    client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "en_reparacion"})
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "resuelta"})
    assert r.status_code == 409
    client.patch(f"/api/incidencias/{inc['id']}", json={"resolucion": "Sustituida fuente"})
    r = client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "resuelta", "fecha": "2026-06-04"})
    assert r.status_code == 200
    assert r.json()["fecha_resolucion"] == "2026-06-04"


def test_delete_guarded(client):
    inc = _inc(client)
    # abierta y sin enlaces -> 204
    assert client.delete(f"/api/incidencias/{inc['id']}").status_code == 204
    # ya borrada -> 404
    assert client.delete(f"/api/incidencias/{inc['id']}").status_code == 404


def test_delete_no_abierta_409(client):
    inc = _inc(client)
    client.post(f"/api/incidencias/{inc['id']}/transicion", json={"nuevo_estado": "diagnostico"})
    assert client.delete(f"/api/incidencias/{inc['id']}").status_code == 409
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_transiciones.py -q`
Expected: FAIL — 405 (PATCH/DELETE/transicion no existen).

- [ ] **Step 3: Extend imports in `backend/app/routers/incidencias.py`**

Añade a la lista de imports de schemas `IncidenciaUpdate` y `TransicionPayload`:

```python
from app.schemas import (
    CambioConfiguracionOut,
    ClienteOut,
    ComponenteOut,
    EquipoOut,
    IncidenciaCreate,
    IncidenciaFicha,
    IncidenciaOut,
    IncidenciaUpdate,
    MovimientoOut,
    TransicionPayload,
)
```

- [ ] **Step 4: Add PATCH, transición and DELETE at the end of `backend/app/routers/incidencias.py`**

```python
@router.patch("/{incidencia_id}", response_model=IncidenciaOut)
def actualizar(incidencia_id: int, payload: IncidenciaUpdate, db: Session = Depends(get_db)) -> models.Incidencia:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(inc, k, v)
    db.commit()
    db.refresh(inc)
    return inc


@router.post("/{incidencia_id}/transicion", response_model=IncidenciaOut)
def transicion(incidencia_id: int, payload: TransicionPayload, db: Session = Depends(get_db)) -> models.Incidencia:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    try:
        svc.transicionar(db, inc, payload.nuevo_estado, payload.fecha)
    except svc.IncidenciaError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(inc)
    return inc


@router.delete("/{incidencia_id}", status_code=204)
def borrar(incidencia_id: int, db: Session = Depends(get_db)) -> None:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    if inc.estado != "abierta":
        raise HTTPException(409, "Solo se pueden borrar incidencias en estado 'abierta'")
    enlazados = (
        db.query(models.CambioConfiguracion).filter(models.CambioConfiguracion.incidencia_id == incidencia_id).count()
        + db.query(models.Movimiento).filter(models.Movimiento.incidencia_id == incidencia_id).count()
    )
    if enlazados:
        raise HTTPException(409, "La incidencia tiene eventos de trazabilidad enlazados")
    db.delete(inc)
    db.commit()
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_transiciones.py -q`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/incidencias.py backend/tests/test_incidencia_transiciones.py
git commit -m "feat: incidencia PATCH + transicion endpoint + guarded DELETE"
```

---

## Task 7: Enlace — `incidencia_id` opcional en operaciones de trazabilidad

**Files:**
- Modify: `backend/app/trazabilidad.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/configuracion.py`
- Modify: `backend/app/routers/equipos.py`
- Modify: `backend/app/routers/movimientos.py`
- Test: `backend/tests/test_incidencia_enlace.py` (Create)

- [ ] **Step 1: Write the failing test `backend/tests/test_incidencia_enlace.py`**

```python
def _setup(client):
    pe = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    pc = client.post("/api/productos", json={"part_number": "PN-C", "tipo": "componente", "descripcion": "C"}).json()
    ub = client.post("/api/ubicaciones", json={"nombre": "Taller", "tipo": "en_reparacion"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": pe["id"]}).json()
    comp = client.post("/api/componentes", json={"numero_serie": "C1", "producto_id": pc["id"]}).json()
    inc = client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "x", "descripcion_problema": "y", "fecha_apertura": "2026-06-01"}).json()
    return pe, pc, ub, eq, comp, inc


def test_montar_con_incidencia_aparece_en_expediente(client):
    _pe, _pc, _ub, eq, comp, inc = _setup(client)
    r = client.post(f"/api/componentes/{comp['id']}/montar", json={
        "equipo_id": eq["id"], "fecha": "2026-06-02", "motivo": "reparacion", "incidencia_id": inc["id"],
    })
    assert r.status_code == 201, r.text
    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert len(ficha["cambios_configuracion"]) == 1
    assert ficha["cambios_configuracion"][0]["componente_id"] == comp["id"]


def test_movimiento_con_incidencia_aparece_en_expediente(client):
    _pe, _pc, ub, eq, _comp, inc = _setup(client)
    r = client.post(f"/api/equipos/{eq['id']}/movimientos", json={
        "ubicacion_destino_id": ub["id"], "fecha": "2026-06-02", "motivo": "reparacion", "incidencia_id": inc["id"],
    })
    assert r.status_code == 201, r.text
    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert len(ficha["movimientos"]) == 1


def test_montar_sin_incidencia_sigue_funcionando(client):
    _pe, _pc, _ub, eq, comp, _inc = _setup(client)
    r = client.post(f"/api/componentes/{comp['id']}/montar", json={
        "equipo_id": eq["id"], "fecha": "2026-06-02", "motivo": "reparacion",
    })
    assert r.status_code == 201, r.text
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_enlace.py -q`
Expected: FAIL — `cambios_configuracion`/`movimientos` vacíos (el `incidencia_id` se ignora porque los payloads/servicios aún no lo aceptan).

- [ ] **Step 3: Add `incidencia_id` to the service functions in `backend/app/trazabilidad.py`**

En `registrar_movimiento`, añade el parámetro y propágalo:

```python
def registrar_movimiento(
    db: Session,
    equipo_id: int,
    ubicacion_destino_id: int,
    fecha: date,
    motivo: str,
    usuario: Optional[str] = None,
    notas: Optional[str] = None,
    incidencia_id: Optional[int] = None,
) -> models.Movimiento:
    mov = models.Movimiento(
        equipo_id=equipo_id,
        ubicacion_destino_id=ubicacion_destino_id,
        fecha=fecha,
        motivo=motivo,
        usuario=usuario,
        notas=notas,
        incidencia_id=incidencia_id,
    )
    db.add(mov)
    db.flush()
    return mov
```

En `montar_componente`, añade el parámetro `incidencia_id: Optional[int] = None` al final de la firma y pásalo al construir `CambioConfiguracion`:

```python
    evento = models.CambioConfiguracion(
        componente_id=componente_id, equipo_id=equipo_id, accion="montaje",
        posicion=posicion, fecha=fecha, motivo=motivo, usuario=usuario, notas=notas,
        incidencia_id=incidencia_id,
    )
```

En `desmontar_componente`, añade `incidencia_id: Optional[int] = None` al final de la firma y pásalo al construir `CambioConfiguracion`:

```python
    evento = models.CambioConfiguracion(
        componente_id=componente_id, equipo_id=equipo_id, accion="desmontaje",
        posicion=comp.posicion, fecha=fecha, motivo=motivo, usuario=usuario, notas=notas,
        incidencia_id=incidencia_id,
    )
```

En `sustituir_componente`, añade `incidencia_id: Optional[int] = None` al final de la firma y propágalo a las dos llamadas internas:

```python
    desmontaje = desmontar_componente(db, componente_saliente_id, fecha, motivo, usuario, notas, incidencia_id)
    montaje = montar_componente(db, componente_entrante_id, equipo_id, posicion, fecha, motivo, usuario, notas, incidencia_id)
```

- [ ] **Step 4: Add `incidencia_id` to the payloads in `backend/app/schemas.py`**

Añade `incidencia_id: Optional[int] = None` como último campo en: `MovimientoCreate`, `MontarPayload`, `DesmontarPayload` y `SustituirPayload`. Por ejemplo, `MovimientoCreate` queda:

```python
class MovimientoCreate(BaseModel):
    ubicacion_destino_id: int
    fecha: date
    motivo: Literal["entrega", "traslado", "reparacion", "devolucion"]
    usuario: Optional[str] = None
    notas: Optional[str] = None
    incidencia_id: Optional[int] = None
```

(Repite el mismo añadido al final de `MontarPayload`, `DesmontarPayload` y `SustituirPayload`.)

- [ ] **Step 5: Pass `incidencia_id` through the routers**

En `backend/app/routers/movimientos.py`, en la llamada a `trazabilidad.registrar_movimiento`, añade `payload.incidencia_id`:

```python
    mov = trazabilidad.registrar_movimiento(
        db, equipo_id, payload.ubicacion_destino_id, payload.fecha, payload.motivo, payload.usuario, payload.notas, payload.incidencia_id
    )
```

En `backend/app/routers/configuracion.py`, en `montar` añade `payload.incidencia_id` al final de la llamada:

```python
        evento = trazabilidad.montar_componente(
            db, componente_id, payload.equipo_id, payload.posicion, payload.fecha, payload.motivo, payload.usuario, payload.notas, payload.incidencia_id
        )
```

y en `desmontar`:

```python
        evento = trazabilidad.desmontar_componente(
            db, componente_id, payload.fecha, payload.motivo, payload.usuario, payload.notas, payload.incidencia_id
        )
```

En `backend/app/routers/equipos.py`, en `sustituir_componente`, añade `payload.incidencia_id` al final de la llamada:

```python
        res = trazabilidad.sustituir_componente(
            db, equipo_id, payload.componente_saliente_id, payload.componente_entrante_id,
            payload.posicion, payload.fecha, payload.motivo, payload.usuario, payload.notas, payload.incidencia_id,
        )
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_enlace.py -q`
Expected: PASS (3 passed).

- [ ] **Step 7: Run the full suite (retrocompat de los tests existentes)**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (todos verdes; los tests de montaje/sustitución/movimientos previos siguen pasando sin cambios).

- [ ] **Step 8: Commit**

```bash
git add backend/app/trazabilidad.py backend/app/schemas.py backend/app/routers/ backend/tests/test_incidencia_enlace.py
git commit -m "feat: optional incidencia_id wired through montar/desmontar/sustituir/movimiento"
```

---

## Task 8: Enriquecer `EquipoFicha` con sus incidencias

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/equipos.py`
- Test: `backend/tests/test_incidencia_en_ficha_equipo.py` (Create)

- [ ] **Step 1: Write the failing test `backend/tests/test_incidencia_en_ficha_equipo.py`**

```python
def test_ficha_equipo_lista_incidencias(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ", "tipo": "equipo", "descripcion": "Eq"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S1", "producto_id": p["id"]}).json()
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "a", "descripcion_problema": "y", "fecha_apertura": "2026-06-01"})
    ficha = client.get(f"/api/equipos/{eq['id']}").json()
    assert "incidencias" in ficha
    assert len(ficha["incidencias"]) == 1
    assert ficha["incidencias"][0]["codigo"] == "RMA-0001"


def test_ficha_equipo_sin_incidencias_vacia(client):
    p = client.post("/api/productos", json={"part_number": "PN-EQ2", "tipo": "equipo", "descripcion": "Eq"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "S2", "producto_id": p["id"]}).json()
    ficha = client.get(f"/api/equipos/{eq['id']}").json()
    assert ficha["incidencias"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_en_ficha_equipo.py -q`
Expected: FAIL — `KeyError: 'incidencias'` (el campo no existe en la ficha).

- [ ] **Step 3: Add `incidencias` to `EquipoFicha` in `backend/app/schemas.py`**

`EquipoFicha` referencia `IncidenciaOut`, que está definido **más abajo** en el archivo. Como `EquipoFicha` ya usa otras clases definidas antes que él y `IncidenciaOut` viene después, añade el campo con una referencia diferida (string) para evitar problemas de orden, y reconstruye el modelo al final del archivo.

Añade el campo a `EquipoFicha`:

```python
class EquipoFicha(_ORM):
    equipo: EquipoOut
    producto: ProductoOut
    cliente: Optional[ClienteOut] = None
    ubicacion_actual: Optional[UbicacionOut] = None
    componentes: list[ComponenteOut] = []
    historial_movimientos: list[MovimientoOut] = []
    historial_configuracion: list[CambioConfiguracionOut] = []
    incidencias: list["IncidenciaOut"] = []
```

Y al **final del archivo** (después de definir `IncidenciaOut`/`IncidenciaFicha`), añade:

```python
EquipoFicha.model_rebuild()
```

- [ ] **Step 4: Populate `incidencias` in the ficha endpoint in `backend/app/routers/equipos.py`**

Añade `IncidenciaOut` al import de schemas de ese archivo. Luego, en `ficha(...)`, antes del `return`, consulta las incidencias:

```python
    incidencias = (
        db.query(models.Incidencia)
        .filter(models.Incidencia.equipo_id == equipo_id)
        .order_by(models.Incidencia.id.desc())
        .all()
    )
```

y añade al `return EquipoFicha(...)` el argumento:

```python
        incidencias=[IncidenciaOut.model_validate(i) for i in incidencias],
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_incidencia_en_ficha_equipo.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (todos verdes; el test de ficha de equipo existente sigue pasando con el campo nuevo).

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/equipos.py backend/tests/test_incidencia_en_ficha_equipo.py
git commit -m "feat: EquipoFicha includes equipo's incidencias"
```

---

## Task 9: Suite completa verde + seed demo + prompts Lovable

**Files:**
- Modify: `backend/_seed_demo.py` (untracked — no se commitea)
- Create: `docs/lovable/08_incidencias_lista.md`
- Create: `docs/lovable/09_incidencias_ficha.md`
- Create: `docs/lovable/10_incidencias_alta.md`
- Modify: `docs/lovable/README.md`

- [ ] **Step 1: Run the full suite and confirm it is green**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS. Conteo esperado ≈ 50 previos + 3 (T1) + 4 (T2) + 5 (T3) + 4 (T4) + 2 (T5) + 6 (T6) + 3 (T7) + 2 (T8) = **79 passed**.

- [ ] **Step 2: Extend `backend/_seed_demo.py` with one demo incidencia**

Antes de la línea final `print("Seed OK: ...")`, añade una incidencia de ejemplo contra el equipo `eq` y enlaza un movimiento a taller:

```python
    inc = post("/api/incidencias", {
        "equipo_id": eq["id"], "titulo": "Fuente no enciende",
        "descripcion_problema": "El equipo arranca pero la fuente PXI no da tensión.",
        "prioridad": "alta", "asignado_a": "Cim", "fecha_apertura": "2026-05-28",
    })
    # mover a taller enlazado a la incidencia
    post(f"/api/equipos/{eq['id']}/movimientos", {
        "ubicacion_destino_id": 3, "fecha": "2026-05-29", "motivo": "reparacion",
        "usuario": "Cim", "incidencia_id": inc["id"],
    })
    # avanzar a diagnóstico
    post(f"/api/incidencias/{inc['id']}/transicion", {"nuevo_estado": "diagnostico", "fecha": "2026-05-29"})
```

> Nota: `ubicacion_destino_id: 3` es el "Taller reparación 6TL" sembrado antes. Si cambia el orden de las ubicaciones en el seed, ajusta el id.

- [ ] **Step 3: Verify the seed live (manual smoke)**

Arranca el backend y siembra:

```
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```

En otra shell: `.venv\Scripts\python _seed_demo.py` → debe imprimir `Seed OK`. Comprueba:
`curl http://127.0.0.1:8020/api/incidencias` → 1 incidencia `RMA-0001` en estado `diagnostico`;
`curl http://127.0.0.1:8020/api/incidencias/1` → expediente con 1 movimiento enlazado.

- [ ] **Step 4: Write the Lovable prompt `docs/lovable/08_incidencias_lista.md`**

Prompt para la **lista de incidencias** (`/incidencias`): tabla con columnas `codigo`, equipo/componente (texto), `titulo`, `prioridad` (badge), `estado` (badge con color: abierta→gris, diagnostico→azul, en_reparacion→ámbar, resuelta→verde, cerrada→neutro), `asignado_a`, `fecha_apertura`. Filtros: `estado`, `prioridad`, toggle "solo abiertas" (→ `?abiertas=true`). Botón "Nueva incidencia" (navega a alta). Consume `GET /api/incidencias`. Usa el design system del prompt 00 (identidad 6TL). Incluye la nota de contrato: nombres de campo exactos del schema `IncidenciaOut`.

- [ ] **Step 5: Write the Lovable prompt `docs/lovable/09_incidencias_ficha.md`**

Prompt para la **ficha/expediente** (`/incidencias/$id`): consume `GET /api/incidencias/{id}` (`IncidenciaFicha`). Cabecera con `codigo` + badge de estado + **timeline** de las 5 fases mostrando las fechas (`fecha_apertura`, `fecha_diagnostico`, `fecha_inicio_reparacion`, `fecha_resolucion`, `fecha_cierre`). Bloques: datos de equipo/componente/cliente (enlazados a sus fichas), "Componentes sustituidos en esta reparación" (`cambios_configuracion`), "Movimientos" (`movimientos`). Acciones: avanzar estado vía `POST /api/incidencias/{id}/transicion` (si el destino es `resuelta`, exigir el campo `resolucion` primero vía `PATCH`), editar (`PATCH`), reabrir (transición a `en_reparacion` desde resuelta/cerrada). Botón borrar solo visible si `estado=abierta`.

- [ ] **Step 6: Write the Lovable prompt `docs/lovable/10_incidencias_alta.md`**

Prompt para el **alta** (`/incidencias/nueva`): formulario con selector de equipo **o** componente (al menos uno; usa `GET /api/equipos` y `GET /api/componentes`), `titulo`, `descripcion_problema`, `prioridad`, `asignado_a`, `en_garantia` (checkbox tri-estado o select Sí/No/—). Envía `POST /api/incidencias`. Maneja el 422 (falta sujeto) y 404 (FK). Tras crear, navega a la ficha. Añade el enganche desde la **ficha de equipo** (prompt 02): nueva sección "Incidencias" que lista `EquipoFicha.incidencias` + botón "Abrir incidencia" precargando el equipo; y en los modales sustituir/montar/desmontar/mover, un selector opcional "¿Forma parte de una incidencia abierta?" que añade `incidencia_id` al body.

- [ ] **Step 7: Update `docs/lovable/README.md`**

Añade las filas 08/09/10 a la tabla de prompts y una nota de que pertenecen al **sub-proyecto 2 (Incidencias/RMA)**, con el contrato `IncidenciaOut`/`IncidenciaFicha` y la nota de que las operaciones de trazabilidad aceptan ahora un `incidencia_id` opcional.

- [ ] **Step 8: Commit (docs + plan progress)**

```bash
git add docs/lovable/
git commit -m "docs: Lovable prompts 08-10 (Incidencias/RMA) + README"
```

> `_seed_demo.py` está en `.gitignore` (no se commitea).

---

## Cierre

- Backend: 9 tareas, ~79 tests verdes, retrocompatibilidad demostrada (los 50 previos siguen pasando).
- Frontend: prompts 08-10 listos para pegar en Lovable (acción manual del usuario), más enganches en la ficha de equipo y los modales de trazabilidad.
- Pendiente tras pegar prompts: validación de contrato + smoke visual (Chrome headless no lanza en este entorno).
