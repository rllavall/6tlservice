# 6TL Postventa — Trazabilidad + Base instalada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backbone of 6TL's after-sales platform — a FastAPI backend that tracks delivered ATE systems, their serialized key components, their worldwide location history, and their configuration-change history (component montages/desmontages over time).

**Architecture:** Catálogo (`Producto`) + serialized instances (`Equipo`, `Componente`) + two symmetric event logs (`Movimiento` = where it is, `CambioConfiguracion` = what it carries). Current state is cached on `Equipo`/`Componente`; the logs are the source of history. A thin service layer (`app/trazabilidad.py`) keeps cached state and logs consistent in a single operation. Cross-cutting queries (search by serial, equipment-by-part-number, equipment-at-location) are first-class.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Pydantic v2, SQLite, pytest + httpx. Backend served on **:8020**. Mirrors the existing `Planificacion ATE/backend` conventions.

**Project root:** `C:\Users\rllavall\6TL Postventa\` (git already initialized).
**Backend lives in:** `backend/` (so `frontend/` can be a sibling Lovable repo later).

> **Field-name contract (single source of truth — used by every task, do not deviate):**
> - `Ubicacion`: `id, nombre, tipo, empresa_cliente, pais, ciudad, notas`. `tipo ∈ {fabrica_cliente, sede_6tl, en_reparacion, en_transito}`.
> - `Producto`: `id, part_number, tipo, descripcion, fabricante, modelo, notas`. `tipo ∈ {equipo, componente}`. `part_number` unique.
> - `Equipo`: `id, numero_serie, producto_id, cliente, fecha_fabricacion, fecha_entrega, estado, notas`. `estado ∈ {operativo, baja}`. Unique `(producto_id, numero_serie)`.
> - `Componente`: `id, numero_serie, producto_id, equipo_id (nullable), posicion (nullable), fecha_montaje (nullable), notas`. Unique `(producto_id, numero_serie)`.
> - `Movimiento`: `id, equipo_id, ubicacion_destino_id, fecha, motivo, usuario, notas`. `motivo ∈ {entrega, traslado, reparacion, devolucion}`.
> - `CambioConfiguracion`: `id, componente_id, equipo_id, accion, posicion, fecha, motivo, usuario, notas`. `accion ∈ {montaje, desmontaje}`. `motivo ∈ {entrega_inicial, sustitucion, upgrade, reparacion, retirada}`.
> - **Ubicación actual** = `Movimiento` of the equipo with the latest `fecha` (tie-break: highest `id`). No movements → `None` (UI shows "Sede 6TL"). Backend returns `null`.

---

## Task 0: Project scaffold + health endpoint

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/app/db.py`
- Create: `backend/app/main.py`
- Create: `backend/app/routers/__init__.py` (empty)
- Create: `backend/tests/__init__.py` (empty)
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "6tl-postventa-backend"
version = "0.1.0"
description = "Backend de postventa 6TL — trazabilidad y base instalada"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sqlalchemy>=2.0",
    "pydantic>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 2: Create `backend/app/db.py`**

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_SQLITE_URL = "sqlite+pysqlite:///./postventa.db"


class Base(DeclarativeBase):
    pass


def engine_for_url(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


engine = engine_for_url(DEFAULT_SQLITE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Create `backend/app/main.py`** (routers added in later tasks)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine

# Import models so Base.metadata is populated before create_all.
from app import models  # noqa: F401  (registered in Task 1)

Base.metadata.create_all(engine)

app = FastAPI(title="6TL Postventa", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
```

> Note: `from app import models` will fail until Task 1 creates `models.py`. To keep Task 0 runnable on its own, temporarily comment that import line and the comment; Task 1 Step 1 uncomments it. (If you run tasks in order, simplest is to create an empty `app/models.py` now with just a module docstring, then fill it in Task 1.)

- [ ] **Step 4: Create empty `backend/app/models.py` placeholder so Task 0 imports cleanly**

```python
"""SQLAlchemy models for 6TL postventa. Populated in Task 1."""
```

- [ ] **Step 5: Create `backend/tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture
def memory_engine():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(memory_engine):
    SessionTest = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)
    with SessionTest() as s:
        yield s


@pytest.fixture
def client(memory_engine):
    """TestClient whose get_db dependency uses the in-memory engine."""
    SessionTest = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)

    def _override_get_db():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 6: Create `backend/tests/test_health.py`**

```python
def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 7: Create empty `backend/app/routers/__init__.py`, `backend/app/__init__.py`, `backend/tests/__init__.py`** (all empty files)

- [ ] **Step 8: Install and run the test**

Run (from `backend/`): `python -m venv .venv && .venv\Scripts\pip install -e ".[dev]" && .venv\Scripts\pytest tests/test_health.py -v`
Expected: PASS (1 passed).

- [ ] **Step 9: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests
git commit -m "scaffold: backend FastAPI + db + health endpoint"
```

---

## Task 1: Data model (6 entities)

**Files:**
- Modify: `backend/app/models.py` (replace placeholder)
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_models.py`**

```python
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import models


def test_create_full_graph(db_session):
    sede = models.Ubicacion(nombre="6TL Barcelona", tipo="sede_6tl")
    prod_eq = models.Producto(part_number="ATE-1000", tipo="equipo", descripcion="Sistema test")
    prod_comp = models.Producto(part_number="PXI-5122", tipo="componente", descripcion="Digitizer")
    db_session.add_all([sede, prod_eq, prod_comp])
    db_session.flush()

    eq = models.Equipo(numero_serie="EQ-001", producto_id=prod_eq.id, cliente="Indra", estado="operativo")
    db_session.add(eq)
    db_session.flush()

    comp = models.Componente(numero_serie="C-001", producto_id=prod_comp.id, equipo_id=eq.id, posicion="ranura 3")
    db_session.add(comp)
    db_session.flush()

    db_session.add(models.Movimiento(equipo_id=eq.id, ubicacion_destino_id=sede.id, fecha=date(2026, 1, 1), motivo="entrega"))
    db_session.add(models.CambioConfiguracion(componente_id=comp.id, equipo_id=eq.id, accion="montaje", fecha=date(2026, 1, 1), motivo="entrega_inicial"))
    db_session.flush()

    assert eq.id is not None and comp.equipo_id == eq.id


def test_serie_unique_per_producto(db_session):
    p = models.Producto(part_number="ATE-1000", tipo="equipo", descripcion="x")
    db_session.add(p)
    db_session.flush()
    db_session.add(models.Equipo(numero_serie="DUP", producto_id=p.id))
    db_session.flush()
    db_session.add(models.Equipo(numero_serie="DUP", producto_id=p.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_serie_different_producto_ok(db_session):
    p1 = models.Producto(part_number="A", tipo="equipo", descripcion="x")
    p2 = models.Producto(part_number="B", tipo="equipo", descripcion="y")
    db_session.add_all([p1, p2])
    db_session.flush()
    db_session.add(models.Equipo(numero_serie="S1", producto_id=p1.id))
    db_session.add(models.Equipo(numero_serie="S1", producto_id=p2.id))
    db_session.flush()  # no raise


def test_part_number_unique(db_session):
    db_session.add(models.Producto(part_number="X", tipo="equipo", descripcion="a"))
    db_session.flush()
    db_session.add(models.Producto(part_number="X", tipo="componente", descripcion="b"))
    with pytest.raises(IntegrityError):
        db_session.flush()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_models.py -v`
Expected: FAIL (AttributeError: module 'app.models' has no attribute 'Ubicacion').

- [ ] **Step 3: Replace `backend/app/models.py` with the full model**

```python
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

TIPOS_UBICACION = ["fabrica_cliente", "sede_6tl", "en_reparacion", "en_transito"]
TIPOS_PRODUCTO = ["equipo", "componente"]
ESTADOS_EQUIPO = ["operativo", "baja"]
MOTIVOS_MOVIMIENTO = ["entrega", "traslado", "reparacion", "devolucion"]
ACCIONES_CONFIG = ["montaje", "desmontaje"]
MOTIVOS_CONFIG = ["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"]


class Ubicacion(Base):
    __tablename__ = "ubicaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String)
    tipo: Mapped[str] = mapped_column(String)
    empresa_cliente: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pais: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ciudad: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_number: Mapped[str] = mapped_column(String, unique=True)
    tipo: Mapped[str] = mapped_column(String)
    descripcion: Mapped[str] = mapped_column(String)
    fabricante: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    modelo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Equipo(Base):
    __tablename__ = "equipos"
    __table_args__ = (UniqueConstraint("producto_id", "numero_serie", name="uq_equipo_serie"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_serie: Mapped[str] = mapped_column(String)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cliente: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha_fabricacion: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fecha_entrega: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estado: Mapped[str] = mapped_column(String, default="operativo")
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    producto: Mapped["Producto"] = relationship()
    componentes: Mapped[list["Componente"]] = relationship(back_populates="equipo")


class Componente(Base):
    __tablename__ = "componentes"
    __table_args__ = (UniqueConstraint("producto_id", "numero_serie", name="uq_componente_serie"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_serie: Mapped[str] = mapped_column(String)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    equipo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipos.id"), nullable=True)
    posicion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha_montaje: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    producto: Mapped["Producto"] = relationship()
    equipo: Mapped[Optional["Equipo"]] = relationship(back_populates="componentes")


class Movimiento(Base):
    __tablename__ = "movimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    ubicacion_destino_id: Mapped[int] = mapped_column(ForeignKey("ubicaciones.id"))
    fecha: Mapped[date] = mapped_column(Date)
    motivo: Mapped[str] = mapped_column(String)
    usuario: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    ubicacion_destino: Mapped["Ubicacion"] = relationship()


class CambioConfiguracion(Base):
    __tablename__ = "cambios_configuracion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    componente_id: Mapped[int] = mapped_column(ForeignKey("componentes.id"))
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    accion: Mapped[str] = mapped_column(String)
    posicion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fecha: Mapped[date] = mapped_column(Date)
    motivo: Mapped[str] = mapped_column(String)
    usuario: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    componente: Mapped["Componente"] = relationship()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_models.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat: data model (6 entities) with serie uniqueness"
```

---

## Task 2: Pydantic schemas

**Files:**
- Create: `backend/app/schemas.py`
- Test: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_schemas.py`**

```python
from datetime import date

from app import models, schemas


def test_equipo_out_from_orm(db_session):
    p = models.Producto(part_number="ATE-1", tipo="equipo", descripcion="x")
    db_session.add(p)
    db_session.flush()
    eq = models.Equipo(numero_serie="S", producto_id=p.id, fecha_entrega=date(2026, 1, 1))
    db_session.add(eq)
    db_session.flush()
    out = schemas.EquipoOut.model_validate(eq)
    assert out.numero_serie == "S"
    assert out.producto_id == p.id


def test_producto_create_requires_tipo():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        schemas.ProductoCreate(part_number="x", descripcion="y")  # tipo missing
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_schemas.py -v`
Expected: FAIL (module 'app.schemas' not found / has no attribute).

- [ ] **Step 3: Create `backend/app/schemas.py`**

```python
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Ubicacion ---
class UbicacionCreate(BaseModel):
    nombre: str
    tipo: Literal["fabrica_cliente", "sede_6tl", "en_reparacion", "en_transito"]
    empresa_cliente: Optional[str] = None
    pais: Optional[str] = None
    ciudad: Optional[str] = None
    notas: Optional[str] = None


class UbicacionOut(_ORM):
    id: int
    nombre: str
    tipo: str
    empresa_cliente: Optional[str] = None
    pais: Optional[str] = None
    ciudad: Optional[str] = None
    notas: Optional[str] = None


# --- Producto ---
class ProductoCreate(BaseModel):
    part_number: str
    tipo: Literal["equipo", "componente"]
    descripcion: str
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    notas: Optional[str] = None


class ProductoOut(_ORM):
    id: int
    part_number: str
    tipo: str
    descripcion: str
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    notas: Optional[str] = None


# --- Equipo ---
class EquipoCreate(BaseModel):
    numero_serie: str
    producto_id: int
    cliente: Optional[str] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: Literal["operativo", "baja"] = "operativo"
    notas: Optional[str] = None


class EquipoUpdate(BaseModel):
    cliente: Optional[str] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: Optional[Literal["operativo", "baja"]] = None
    notas: Optional[str] = None


class EquipoOut(_ORM):
    id: int
    numero_serie: str
    producto_id: int
    cliente: Optional[str] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: str
    notas: Optional[str] = None


# --- Componente ---
class ComponenteCreate(BaseModel):
    numero_serie: str
    producto_id: int
    equipo_id: Optional[int] = None
    posicion: Optional[str] = None
    fecha_montaje: Optional[date] = None
    notas: Optional[str] = None


class ComponenteOut(_ORM):
    id: int
    numero_serie: str
    producto_id: int
    equipo_id: Optional[int] = None
    posicion: Optional[str] = None
    fecha_montaje: Optional[date] = None
    notas: Optional[str] = None


# --- Movimiento ---
class MovimientoCreate(BaseModel):
    ubicacion_destino_id: int
    fecha: date
    motivo: Literal["entrega", "traslado", "reparacion", "devolucion"]
    usuario: Optional[str] = None
    notas: Optional[str] = None


class MovimientoOut(_ORM):
    id: int
    equipo_id: int
    ubicacion_destino_id: int
    fecha: date
    motivo: str
    usuario: Optional[str] = None
    notas: Optional[str] = None


# --- CambioConfiguracion ---
class CambioConfiguracionOut(_ORM):
    id: int
    componente_id: int
    equipo_id: int
    accion: str
    posicion: Optional[str] = None
    fecha: date
    motivo: str
    usuario: Optional[str] = None
    notas: Optional[str] = None


# --- Acciones de configuración (payloads) ---
class MontarPayload(BaseModel):
    equipo_id: int
    posicion: Optional[str] = None
    fecha: date
    motivo: Literal["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"]
    usuario: Optional[str] = None
    notas: Optional[str] = None


class DesmontarPayload(BaseModel):
    fecha: date
    motivo: Literal["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"]
    usuario: Optional[str] = None
    notas: Optional[str] = None


class SustituirPayload(BaseModel):
    componente_saliente_id: int
    componente_entrante_id: int
    posicion: Optional[str] = None
    fecha: date
    motivo: Literal["entrega_inicial", "sustitucion", "upgrade", "reparacion", "retirada"] = "sustitucion"
    usuario: Optional[str] = None
    notas: Optional[str] = None


# --- Ficha y búsqueda ---
class EquipoFicha(_ORM):
    equipo: EquipoOut
    producto: ProductoOut
    ubicacion_actual: Optional[UbicacionOut] = None
    componentes: list[ComponenteOut] = []
    historial_movimientos: list[MovimientoOut] = []
    historial_configuracion: list[CambioConfiguracionOut] = []


class ResultadoBusqueda(BaseModel):
    tipo: Literal["equipo", "componente", "ninguno"]
    equipo: Optional[EquipoOut] = None
    componente: Optional[ComponenteOut] = None
    equipo_del_componente: Optional[EquipoOut] = None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_schemas.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_schemas.py
git commit -m "feat: pydantic schemas for all entities + ficha/search"
```

---

## Task 3: Ubicaciones CRUD router

**Files:**
- Create: `backend/app/routers/ubicaciones.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_ubicaciones.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_ubicaciones.py`**

```python
def test_ubicacion_crud(client):
    r = client.post("/api/ubicaciones", json={"nombre": "Indra Madrid", "tipo": "fabrica_cliente", "pais": "España"})
    assert r.status_code == 201, r.text
    uid = r.json()["id"]

    r = client.get("/api/ubicaciones")
    assert r.status_code == 200
    assert any(u["id"] == uid for u in r.json())

    r = client.put(f"/api/ubicaciones/{uid}", json={"nombre": "Indra Madrid 2", "tipo": "fabrica_cliente"})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Indra Madrid 2"

    r = client.delete(f"/api/ubicaciones/{uid}")
    assert r.status_code == 204

    r = client.get(f"/api/ubicaciones/{uid}")
    assert r.status_code == 404


def test_ubicacion_invalid_tipo_422(client):
    r = client.post("/api/ubicaciones", json={"nombre": "x", "tipo": "marte"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_ubicaciones.py -v`
Expected: FAIL (404 on POST — route not registered).

- [ ] **Step 3: Create `backend/app/routers/ubicaciones.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import UbicacionCreate, UbicacionOut

router = APIRouter(prefix="/api/ubicaciones", tags=["ubicaciones"])


@router.get("", response_model=list[UbicacionOut])
def listar(db: Session = Depends(get_db)) -> list[models.Ubicacion]:
    return db.query(models.Ubicacion).order_by(models.Ubicacion.nombre).all()


@router.get("/{ubicacion_id}", response_model=UbicacionOut)
def obtener(ubicacion_id: int, db: Session = Depends(get_db)) -> models.Ubicacion:
    u = db.get(models.Ubicacion, ubicacion_id)
    if u is None:
        raise HTTPException(404, "Ubicación no encontrada")
    return u


@router.post("", response_model=UbicacionOut, status_code=201)
def crear(payload: UbicacionCreate, db: Session = Depends(get_db)) -> models.Ubicacion:
    u = models.Ubicacion(**payload.model_dump())
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.put("/{ubicacion_id}", response_model=UbicacionOut)
def actualizar(ubicacion_id: int, payload: UbicacionCreate, db: Session = Depends(get_db)) -> models.Ubicacion:
    u = db.get(models.Ubicacion, ubicacion_id)
    if u is None:
        raise HTTPException(404, "Ubicación no encontrada")
    for k, v in payload.model_dump().items():
        setattr(u, k, v)
    db.commit()
    db.refresh(u)
    return u


@router.delete("/{ubicacion_id}", status_code=204)
def borrar(ubicacion_id: int, db: Session = Depends(get_db)) -> Response:
    u = db.get(models.Ubicacion, ubicacion_id)
    if u is None:
        raise HTTPException(404, "Ubicación no encontrada")
    en_uso = db.query(models.Movimiento).filter_by(ubicacion_destino_id=ubicacion_id).first()
    if en_uso is not None:
        raise HTTPException(409, "Ubicación en uso por movimientos; no se puede borrar")
    db.delete(u)
    db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Register the router in `backend/app/main.py`**

Add import and include after the CORS block:

```python
from app.routers import ubicaciones

app.include_router(ubicaciones.router)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_ubicaciones.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/ubicaciones.py backend/app/main.py backend/tests/test_ubicaciones.py
git commit -m "feat: ubicaciones CRUD with in-use delete guard"
```

---

## Task 4: Productos (catálogo) CRUD router

**Files:**
- Create: `backend/app/routers/productos.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_productos.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_productos.py`**

```python
def test_producto_crud_and_filter(client):
    r = client.post("/api/productos", json={"part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    client.post("/api/productos", json={"part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digitizer"})

    r = client.get("/api/productos?tipo=equipo")
    assert r.status_code == 200
    tipos = {p["tipo"] for p in r.json()}
    assert tipos == {"equipo"}

    r = client.put(f"/api/productos/{pid}", json={"part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema v2"})
    assert r.json()["descripcion"] == "Sistema v2"


def test_producto_duplicate_part_number_409(client):
    client.post("/api/productos", json={"part_number": "DUP", "tipo": "equipo", "descripcion": "a"})
    r = client.post("/api/productos", json={"part_number": "DUP", "tipo": "componente", "descripcion": "b"})
    assert r.status_code == 409


def test_producto_delete_in_use_409(client):
    pid = client.post("/api/productos", json={"part_number": "P", "tipo": "equipo", "descripcion": "a"}).json()["id"]
    client.post("/api/equipos", json={"numero_serie": "S", "producto_id": pid})
    r = client.delete(f"/api/productos/{pid}")
    assert r.status_code == 409
```

> Note: `test_producto_delete_in_use_409` depends on the `/api/equipos` POST from Task 5. If running tasks strictly in order, this assertion will 404 on the equipos POST until Task 5 lands. Acceptable: the test is committed here and goes green once Task 5 is done. Alternatively, move this single test function into Task 5. Recommended: keep it here but expect it red until Task 5 (note in commit).

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_productos.py -v`
Expected: FAIL (routes not registered).

- [ ] **Step 3: Create `backend/app/routers/productos.py`**

```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import ProductoCreate, ProductoOut

router = APIRouter(prefix="/api/productos", tags=["productos"])


@router.get("", response_model=list[ProductoOut])
def listar(tipo: Optional[str] = None, db: Session = Depends(get_db)) -> list[models.Producto]:
    q = db.query(models.Producto)
    if tipo is not None:
        q = q.filter(models.Producto.tipo == tipo)
    return q.order_by(models.Producto.part_number).all()


@router.get("/{producto_id}", response_model=ProductoOut)
def obtener(producto_id: int, db: Session = Depends(get_db)) -> models.Producto:
    p = db.get(models.Producto, producto_id)
    if p is None:
        raise HTTPException(404, "Producto no encontrado")
    return p


@router.post("", response_model=ProductoOut, status_code=201)
def crear(payload: ProductoCreate, db: Session = Depends(get_db)) -> models.Producto:
    p = models.Producto(**payload.model_dump())
    db.add(p)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "part_number ya existe")
    db.refresh(p)
    return p


@router.put("/{producto_id}", response_model=ProductoOut)
def actualizar(producto_id: int, payload: ProductoCreate, db: Session = Depends(get_db)) -> models.Producto:
    p = db.get(models.Producto, producto_id)
    if p is None:
        raise HTTPException(404, "Producto no encontrado")
    for k, v in payload.model_dump().items():
        setattr(p, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "part_number ya existe")
    db.refresh(p)
    return p


@router.delete("/{producto_id}", status_code=204)
def borrar(producto_id: int, db: Session = Depends(get_db)) -> Response:
    p = db.get(models.Producto, producto_id)
    if p is None:
        raise HTTPException(404, "Producto no encontrado")
    usado_eq = db.query(models.Equipo).filter_by(producto_id=producto_id).first()
    usado_comp = db.query(models.Componente).filter_by(producto_id=producto_id).first()
    if usado_eq is not None or usado_comp is not None:
        raise HTTPException(409, "Producto en uso; no se puede borrar")
    db.delete(p)
    db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Register the router in `backend/app/main.py`**

```python
from app.routers import productos

app.include_router(productos.router)
```

- [ ] **Step 5: Run the test to verify it passes** (the in-use test goes green after Task 5)

Run: `.venv\Scripts\pytest tests/test_productos.py -v`
Expected: PASS for duplicate/filter tests; `test_producto_delete_in_use_409` passes once Task 5 lands.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/productos.py backend/app/main.py backend/tests/test_productos.py
git commit -m "feat: productos (catalogo) CRUD with unique + in-use guards"
```

---

## Task 5: Equipos CRUD + filters + producto-tipo validation

**Files:**
- Create: `backend/app/routers/equipos.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_equipos.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_equipos.py`**

```python
import pytest


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={"part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema"}).json()["id"]


@pytest.fixture
def prod_componente(client):
    return client.post("/api/productos", json={"part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digi"}).json()["id"]


def test_equipo_create_and_get(client, prod_equipo):
    r = client.post("/api/equipos", json={"numero_serie": "EQ-1", "producto_id": prod_equipo, "cliente": "Indra"})
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    r = client.get(f"/api/equipos/{eid}")
    assert r.status_code == 200
    assert r.json()["equipo"]["numero_serie"] == "EQ-1"  # ficha shape (Task 10)


def test_equipo_rejects_componente_producto(client, prod_componente):
    r = client.post("/api/equipos", json={"numero_serie": "X", "producto_id": prod_componente})
    assert r.status_code == 409
    assert "equipo" in r.json()["detail"].lower()


def test_equipo_duplicate_serie_same_producto_409(client, prod_equipo):
    client.post("/api/equipos", json={"numero_serie": "DUP", "producto_id": prod_equipo})
    r = client.post("/api/equipos", json={"numero_serie": "DUP", "producto_id": prod_equipo})
    assert r.status_code == 409


def test_equipo_list_filter_by_producto(client, prod_equipo):
    client.post("/api/equipos", json={"numero_serie": "A", "producto_id": prod_equipo})
    r = client.get(f"/api/equipos?producto_id={prod_equipo}")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_equipo_update(client, prod_equipo):
    eid = client.post("/api/equipos", json={"numero_serie": "U", "producto_id": prod_equipo}).json()["id"]
    r = client.put(f"/api/equipos/{eid}", json={"estado": "baja", "cliente": "Otro"})
    assert r.status_code == 200
    assert r.json()["estado"] == "baja"
```

> Note: `test_equipo_create_and_get` asserts the **ficha** shape (`{"equipo": {...}}`) which is delivered in Task 10. Until then, have `GET /api/equipos/{id}` return the ficha. To avoid a dependency inversion, **implement the ficha endpoint here in Task 5 Step 3** (the composed read), reusing the service from Task 7+. Simplest ordering: this task's GET-by-id returns the full ficha by calling `construir_ficha` (Task 10 defines it). If running strictly in order, return a minimal ficha here (equipo+producto only, empty lists/null ubicacion) and let Task 10 enrich it. The test only checks `equipo.numero_serie`, so the minimal ficha passes now.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_equipos.py -v`
Expected: FAIL (routes not registered).

- [ ] **Step 3: Create `backend/app/routers/equipos.py`** (minimal ficha now; enriched in Task 10)

```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import EquipoCreate, EquipoFicha, EquipoOut, EquipoUpdate, ProductoOut

router = APIRouter(prefix="/api/equipos", tags=["equipos"])


@router.get("", response_model=list[EquipoOut])
def listar(
    producto_id: Optional[int] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[models.Equipo]:
    q = db.query(models.Equipo)
    if producto_id is not None:
        q = q.filter(models.Equipo.producto_id == producto_id)
    if estado is not None:
        q = q.filter(models.Equipo.estado == estado)
    return q.order_by(models.Equipo.numero_serie).all()


@router.post("", response_model=EquipoOut, status_code=201)
def crear(payload: EquipoCreate, db: Session = Depends(get_db)) -> models.Equipo:
    prod = db.get(models.Producto, payload.producto_id)
    if prod is None:
        raise HTTPException(404, "Producto no encontrado")
    if prod.tipo != "equipo":
        raise HTTPException(409, "El producto referenciado no es de tipo 'equipo'")
    eq = models.Equipo(**payload.model_dump())
    db.add(eq)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un equipo con ese (producto, numero_serie)")
    db.refresh(eq)
    return eq


@router.put("/{equipo_id}", response_model=EquipoOut)
def actualizar(equipo_id: int, payload: EquipoUpdate, db: Session = Depends(get_db)) -> models.Equipo:
    eq = db.get(models.Equipo, equipo_id)
    if eq is None:
        raise HTTPException(404, "Equipo no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(eq, k, v)
    db.commit()
    db.refresh(eq)
    return eq


@router.get("/{equipo_id}", response_model=EquipoFicha)
def ficha(equipo_id: int, db: Session = Depends(get_db)) -> EquipoFicha:
    eq = db.get(models.Equipo, equipo_id)
    if eq is None:
        raise HTTPException(404, "Equipo no encontrado")
    prod = db.get(models.Producto, eq.producto_id)
    # Minimal ficha — enriched in Task 10.
    return EquipoFicha(
        equipo=EquipoOut.model_validate(eq),
        producto=ProductoOut.model_validate(prod),
        ubicacion_actual=None,
        componentes=[],
        historial_movimientos=[],
        historial_configuracion=[],
    )
```

- [ ] **Step 4: Register the router in `backend/app/main.py`**

```python
from app.routers import equipos

app.include_router(equipos.router)
```

- [ ] **Step 5: Run the tests to verify they pass** (also re-run productos in-use test)

Run: `.venv\Scripts\pytest tests/test_equipos.py tests/test_productos.py -v`
Expected: PASS (all green, including `test_producto_delete_in_use_409`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/equipos.py backend/app/main.py backend/tests/test_equipos.py
git commit -m "feat: equipos CRUD + filters + producto-tipo guard + minimal ficha"
```

---

## Task 6: Componentes CRUD + producto-tipo validation

**Files:**
- Create: `backend/app/routers/componentes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_componentes.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_componentes.py`**

```python
import pytest


@pytest.fixture
def prod_componente(client):
    return client.post("/api/productos", json={"part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digi"}).json()["id"]


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={"part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema"}).json()["id"]


def test_componente_create_unassigned(client, prod_componente):
    r = client.post("/api/componentes", json={"numero_serie": "C-1", "producto_id": prod_componente})
    assert r.status_code == 201, r.text
    assert r.json()["equipo_id"] is None


def test_componente_rejects_equipo_producto(client, prod_equipo):
    r = client.post("/api/componentes", json={"numero_serie": "C", "producto_id": prod_equipo})
    assert r.status_code == 409
    assert "componente" in r.json()["detail"].lower()


def test_componente_list_and_update(client, prod_componente):
    cid = client.post("/api/componentes", json={"numero_serie": "C-2", "producto_id": prod_componente}).json()["id"]
    r = client.get("/api/componentes")
    assert any(c["id"] == cid for c in r.json())
    r = client.put(f"/api/componentes/{cid}", json={"numero_serie": "C-2", "producto_id": prod_componente, "notas": "ok"})
    assert r.json()["notas"] == "ok"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_componentes.py -v`
Expected: FAIL (routes not registered).

- [ ] **Step 3: Create `backend/app/routers/componentes.py`**

```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import ComponenteCreate, ComponenteOut

router = APIRouter(prefix="/api/componentes", tags=["componentes"])


@router.get("", response_model=list[ComponenteOut])
def listar(
    equipo_id: Optional[int] = None,
    producto_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> list[models.Componente]:
    q = db.query(models.Componente)
    if equipo_id is not None:
        q = q.filter(models.Componente.equipo_id == equipo_id)
    if producto_id is not None:
        q = q.filter(models.Componente.producto_id == producto_id)
    return q.order_by(models.Componente.numero_serie).all()


@router.get("/{componente_id}", response_model=ComponenteOut)
def obtener(componente_id: int, db: Session = Depends(get_db)) -> models.Componente:
    c = db.get(models.Componente, componente_id)
    if c is None:
        raise HTTPException(404, "Componente no encontrado")
    return c


@router.post("", response_model=ComponenteOut, status_code=201)
def crear(payload: ComponenteCreate, db: Session = Depends(get_db)) -> models.Componente:
    prod = db.get(models.Producto, payload.producto_id)
    if prod is None:
        raise HTTPException(404, "Producto no encontrado")
    if prod.tipo != "componente":
        raise HTTPException(409, "El producto referenciado no es de tipo 'componente'")
    if payload.equipo_id is not None and db.get(models.Equipo, payload.equipo_id) is None:
        raise HTTPException(404, "Equipo no encontrado")
    c = models.Componente(**payload.model_dump())
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un componente con ese (producto, numero_serie)")
    db.refresh(c)
    return c


@router.put("/{componente_id}", response_model=ComponenteOut)
def actualizar(componente_id: int, payload: ComponenteCreate, db: Session = Depends(get_db)) -> models.Componente:
    c = db.get(models.Componente, componente_id)
    if c is None:
        raise HTTPException(404, "Componente no encontrado")
    # numero_serie/producto editable here; montaje state is managed via Task 8 endpoints.
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un componente con ese (producto, numero_serie)")
    db.refresh(c)
    return c
```

- [ ] **Step 4: Register the router in `backend/app/main.py`**

```python
from app.routers import componentes

app.include_router(componentes.router)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_componentes.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/componentes.py backend/app/main.py backend/tests/test_componentes.py
git commit -m "feat: componentes CRUD + producto-tipo guard"
```

---

## Task 7: Service layer — ubicación actual + registrar movimiento

**Files:**
- Create: `backend/app/trazabilidad.py`
- Create: `backend/app/routers/movimientos.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_movimientos.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_movimientos.py`**

```python
from datetime import date

import pytest

from app import models
from app.trazabilidad import ubicacion_actual


@pytest.fixture
def equipo_id(client):
    pid = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "x"}).json()["id"]
    return client.post("/api/equipos", json={"numero_serie": "S", "producto_id": pid}).json()["id"]


def test_ubicacion_actual_none_when_no_movimientos(db_session):
    p = models.Producto(part_number="ATE", tipo="equipo", descripcion="x")
    db_session.add(p)
    db_session.flush()
    eq = models.Equipo(numero_serie="S", producto_id=p.id)
    db_session.add(eq)
    db_session.flush()
    assert ubicacion_actual(db_session, eq.id) is None


def test_ubicacion_actual_is_latest_by_fecha(db_session):
    p = models.Producto(part_number="ATE", tipo="equipo", descripcion="x")
    u1 = models.Ubicacion(nombre="A", tipo="sede_6tl")
    u2 = models.Ubicacion(nombre="B", tipo="fabrica_cliente")
    db_session.add_all([p, u1, u2])
    db_session.flush()
    eq = models.Equipo(numero_serie="S", producto_id=p.id)
    db_session.add(eq)
    db_session.flush()
    db_session.add(models.Movimiento(equipo_id=eq.id, ubicacion_destino_id=u1.id, fecha=date(2026, 1, 1), motivo="entrega"))
    db_session.add(models.Movimiento(equipo_id=eq.id, ubicacion_destino_id=u2.id, fecha=date(2026, 6, 1), motivo="traslado"))
    db_session.flush()
    assert ubicacion_actual(db_session, eq.id).id == u2.id


def test_registrar_movimiento_endpoint(client, equipo_id):
    uid = client.post("/api/ubicaciones", json={"nombre": "Indra", "tipo": "fabrica_cliente"}).json()["id"]
    r = client.post(f"/api/equipos/{equipo_id}/movimientos", json={"ubicacion_destino_id": uid, "fecha": "2026-03-01", "motivo": "entrega"})
    assert r.status_code == 201, r.text
    assert r.json()["ubicacion_destino_id"] == uid
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_movimientos.py -v`
Expected: FAIL (cannot import `ubicacion_actual`).

- [ ] **Step 3: Create `backend/app/trazabilidad.py`** (service — grows in Tasks 8–9)

```python
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app import models


def ubicacion_actual(db: Session, equipo_id: int) -> Optional[models.Ubicacion]:
    """Ubicación del último movimiento (mayor fecha; desempate por id). None si no hay."""
    mov = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.equipo_id == equipo_id)
        .order_by(desc(models.Movimiento.fecha), desc(models.Movimiento.id))
        .first()
    )
    if mov is None:
        return None
    return db.get(models.Ubicacion, mov.ubicacion_destino_id)


def registrar_movimiento(
    db: Session,
    equipo_id: int,
    ubicacion_destino_id: int,
    fecha: date,
    motivo: str,
    usuario: Optional[str] = None,
    notas: Optional[str] = None,
) -> models.Movimiento:
    mov = models.Movimiento(
        equipo_id=equipo_id,
        ubicacion_destino_id=ubicacion_destino_id,
        fecha=fecha,
        motivo=motivo,
        usuario=usuario,
        notas=notas,
    )
    db.add(mov)
    db.flush()
    return mov
```

- [ ] **Step 4: Create `backend/app/routers/movimientos.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, trazabilidad
from app.db import get_db
from app.schemas import MovimientoCreate, MovimientoOut

router = APIRouter(prefix="/api/equipos", tags=["movimientos"])


@router.post("/{equipo_id}/movimientos", response_model=MovimientoOut, status_code=201)
def crear_movimiento(equipo_id: int, payload: MovimientoCreate, db: Session = Depends(get_db)) -> models.Movimiento:
    if db.get(models.Equipo, equipo_id) is None:
        raise HTTPException(404, "Equipo no encontrado")
    if db.get(models.Ubicacion, payload.ubicacion_destino_id) is None:
        raise HTTPException(404, "Ubicación destino no encontrada")
    mov = trazabilidad.registrar_movimiento(
        db, equipo_id, payload.ubicacion_destino_id, payload.fecha, payload.motivo, payload.usuario, payload.notas
    )
    db.commit()
    db.refresh(mov)
    return mov
```

- [ ] **Step 5: Register the router in `backend/app/main.py`**

```python
from app.routers import movimientos

app.include_router(movimientos.router)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_movimientos.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add backend/app/trazabilidad.py backend/app/routers/movimientos.py backend/app/main.py backend/tests/test_movimientos.py
git commit -m "feat: service ubicacion_actual + registrar movimiento endpoint"
```

---

## Task 8: Service — montar / desmontar componente

**Files:**
- Modify: `backend/app/trazabilidad.py`
- Create: `backend/app/routers/configuracion.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_montaje.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_montaje.py`**

```python
import pytest


@pytest.fixture
def setup(client):
    pe = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "x"}).json()["id"]
    pc = client.post("/api/productos", json={"part_number": "PXI", "tipo": "componente", "descripcion": "y"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "EQ", "producto_id": pe}).json()["id"]
    comp = client.post("/api/componentes", json={"numero_serie": "C", "producto_id": pc}).json()["id"]
    return {"equipo": eq, "componente": comp}


def test_montar_sets_state_and_logs(client, setup):
    r = client.post(f"/api/componentes/{setup['componente']}/montar",
                    json={"equipo_id": setup["equipo"], "posicion": "ranura 3", "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    assert r.status_code == 201, r.text
    assert r.json()["accion"] == "montaje"

    comp = client.get(f"/api/componentes/{setup['componente']}").json()
    assert comp["equipo_id"] == setup["equipo"]
    assert comp["posicion"] == "ranura 3"

    listed = client.get(f"/api/componentes?equipo_id={setup['equipo']}").json()
    assert len(listed) == 1


def test_montar_already_mounted_409(client, setup):
    body = {"equipo_id": setup["equipo"], "fecha": "2026-01-01", "motivo": "entrega_inicial"}
    client.post(f"/api/componentes/{setup['componente']}/montar", json=body)
    r = client.post(f"/api/componentes/{setup['componente']}/montar", json=body)
    assert r.status_code == 409


def test_desmontar_clears_state(client, setup):
    client.post(f"/api/componentes/{setup['componente']}/montar",
                json={"equipo_id": setup["equipo"], "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    r = client.post(f"/api/componentes/{setup['componente']}/desmontar", json={"fecha": "2026-02-01", "motivo": "retirada"})
    assert r.status_code == 201, r.text
    assert r.json()["accion"] == "desmontaje"
    comp = client.get(f"/api/componentes/{setup['componente']}").json()
    assert comp["equipo_id"] is None


def test_desmontar_when_not_mounted_409(client, setup):
    r = client.post(f"/api/componentes/{setup['componente']}/desmontar", json={"fecha": "2026-02-01", "motivo": "retirada"})
    assert r.status_code == 409
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_montaje.py -v`
Expected: FAIL (routes not registered).

- [ ] **Step 3: Add `montar_componente` and `desmontar_componente` to `backend/app/trazabilidad.py`**

Append to the file:

```python
class ConfiguracionError(Exception):
    """Estado de montaje inválido (ya montado / no montado)."""


def montar_componente(
    db: Session,
    componente_id: int,
    equipo_id: int,
    posicion: Optional[str],
    fecha: date,
    motivo: str,
    usuario: Optional[str] = None,
    notas: Optional[str] = None,
) -> models.CambioConfiguracion:
    comp = db.get(models.Componente, componente_id)
    if comp is None:
        raise LookupError("Componente no encontrado")
    if db.get(models.Equipo, equipo_id) is None:
        raise LookupError("Equipo no encontrado")
    if comp.equipo_id is not None:
        raise ConfiguracionError("El componente ya está montado; desmóntalo primero")
    comp.equipo_id = equipo_id
    comp.posicion = posicion
    comp.fecha_montaje = fecha
    evento = models.CambioConfiguracion(
        componente_id=componente_id, equipo_id=equipo_id, accion="montaje",
        posicion=posicion, fecha=fecha, motivo=motivo, usuario=usuario, notas=notas,
    )
    db.add(evento)
    db.flush()
    return evento


def desmontar_componente(
    db: Session,
    componente_id: int,
    fecha: date,
    motivo: str,
    usuario: Optional[str] = None,
    notas: Optional[str] = None,
) -> models.CambioConfiguracion:
    comp = db.get(models.Componente, componente_id)
    if comp is None:
        raise LookupError("Componente no encontrado")
    if comp.equipo_id is None:
        raise ConfiguracionError("El componente no está montado en ningún equipo")
    equipo_id = comp.equipo_id
    evento = models.CambioConfiguracion(
        componente_id=componente_id, equipo_id=equipo_id, accion="desmontaje",
        posicion=comp.posicion, fecha=fecha, motivo=motivo, usuario=usuario, notas=notas,
    )
    db.add(evento)
    comp.equipo_id = None
    comp.posicion = None
    db.flush()
    return evento
```

- [ ] **Step 4: Create `backend/app/routers/configuracion.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, trazabilidad
from app.db import get_db
from app.schemas import CambioConfiguracionOut, DesmontarPayload, MontarPayload

router = APIRouter(prefix="/api/componentes", tags=["configuracion"])


@router.post("/{componente_id}/montar", response_model=CambioConfiguracionOut, status_code=201)
def montar(componente_id: int, payload: MontarPayload, db: Session = Depends(get_db)) -> models.CambioConfiguracion:
    try:
        evento = trazabilidad.montar_componente(
            db, componente_id, payload.equipo_id, payload.posicion, payload.fecha, payload.motivo, payload.usuario, payload.notas
        )
    except LookupError as e:
        db.rollback()
        raise HTTPException(404, str(e))
    except trazabilidad.ConfiguracionError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(evento)
    return evento


@router.post("/{componente_id}/desmontar", response_model=CambioConfiguracionOut, status_code=201)
def desmontar(componente_id: int, payload: DesmontarPayload, db: Session = Depends(get_db)) -> models.CambioConfiguracion:
    try:
        evento = trazabilidad.desmontar_componente(
            db, componente_id, payload.fecha, payload.motivo, payload.usuario, payload.notas
        )
    except LookupError as e:
        db.rollback()
        raise HTTPException(404, str(e))
    except trazabilidad.ConfiguracionError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(evento)
    return evento
```

- [ ] **Step 5: Register the router in `backend/app/main.py`**

```python
from app.routers import configuracion

app.include_router(configuracion.router)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_montaje.py -v`
Expected: PASS (4 passed).

- [ ] **Step 7: Commit**

```bash
git add backend/app/trazabilidad.py backend/app/routers/configuracion.py backend/app/main.py backend/tests/test_montaje.py
git commit -m "feat: montar/desmontar componente with config log + state guards"
```

---

## Task 9: Service — sustituir componente (atomic)

**Files:**
- Modify: `backend/app/trazabilidad.py`
- Modify: `backend/app/routers/equipos.py` (add sustituir endpoint)
- Test: `backend/tests/test_sustituir.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_sustituir.py`**

```python
import pytest


@pytest.fixture
def setup(client):
    pe = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "x"}).json()["id"]
    pc = client.post("/api/productos", json={"part_number": "PXI", "tipo": "componente", "descripcion": "y"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "EQ", "producto_id": pe}).json()["id"]
    saliente = client.post("/api/componentes", json={"numero_serie": "OLD", "producto_id": pc}).json()["id"]
    entrante = client.post("/api/componentes", json={"numero_serie": "NEW", "producto_id": pc}).json()["id"]
    client.post(f"/api/componentes/{saliente}/montar", json={"equipo_id": eq, "posicion": "r3", "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    return {"equipo": eq, "saliente": saliente, "entrante": entrante}


def test_sustituir_swaps_and_logs_both(client, setup):
    r = client.post(f"/api/equipos/{setup['equipo']}/sustituir-componente", json={
        "componente_saliente_id": setup["saliente"],
        "componente_entrante_id": setup["entrante"],
        "posicion": "r3", "fecha": "2026-05-01", "motivo": "sustitucion",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["desmontaje"]["accion"] == "desmontaje"
    assert body["montaje"]["accion"] == "montaje"

    old = client.get(f"/api/componentes/{setup['saliente']}").json()
    new = client.get(f"/api/componentes/{setup['entrante']}").json()
    assert old["equipo_id"] is None
    assert new["equipo_id"] == setup["equipo"]
    assert new["posicion"] == "r3"


def test_sustituir_entrante_already_mounted_is_atomic_409(client, setup):
    # Mount entrante elsewhere-not-applicable: mount it on same equipo first to force conflict.
    client.post(f"/api/componentes/{setup['entrante']}/montar", json={"equipo_id": setup["equipo"], "fecha": "2026-02-01", "motivo": "upgrade"})
    r = client.post(f"/api/equipos/{setup['equipo']}/sustituir-componente", json={
        "componente_saliente_id": setup["saliente"],
        "componente_entrante_id": setup["entrante"],
        "fecha": "2026-05-01", "motivo": "sustitucion",
    })
    assert r.status_code == 409
    # Atomicity: saliente must remain mounted (rollback of the desmontaje).
    old = client.get(f"/api/componentes/{setup['saliente']}").json()
    assert old["equipo_id"] == setup["equipo"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_sustituir.py -v`
Expected: FAIL (route not registered).

- [ ] **Step 3: Add `sustituir_componente` to `backend/app/trazabilidad.py`**

Append:

```python
def sustituir_componente(
    db: Session,
    equipo_id: int,
    componente_saliente_id: int,
    componente_entrante_id: int,
    posicion: Optional[str],
    fecha: date,
    motivo: str,
    usuario: Optional[str] = None,
    notas: Optional[str] = None,
) -> dict:
    """Desmonta el saliente y monta el entrante en el mismo equipo. Atómico:
    si el montaje falla, NO se aplica el desmontaje (la sesión se revierte arriba)."""
    if db.get(models.Equipo, equipo_id) is None:
        raise LookupError("Equipo no encontrado")
    saliente = db.get(models.Componente, componente_saliente_id)
    if saliente is None:
        raise LookupError("Componente saliente no encontrado")
    if saliente.equipo_id != equipo_id:
        raise ConfiguracionError("El componente saliente no está montado en este equipo")
    # Both operations share the session; the router commits once at the end.
    desmontaje = desmontar_componente(db, componente_saliente_id, fecha, motivo, usuario, notas)
    montaje = montar_componente(db, componente_entrante_id, equipo_id, posicion, fecha, motivo, usuario, notas)
    return {"desmontaje": desmontaje, "montaje": montaje}
```

- [ ] **Step 4: Add the `SustitucionOut` schema to `backend/app/schemas.py`**

Append:

```python
class SustitucionOut(BaseModel):
    desmontaje: CambioConfiguracionOut
    montaje: CambioConfiguracionOut
```

- [ ] **Step 5: Add the sustituir endpoint to `backend/app/routers/equipos.py`**

Add imports at the top: `from app import trazabilidad` and extend the schemas import to include `SustituirPayload, SustitucionOut`. Then append:

```python
@router.post("/{equipo_id}/sustituir-componente", response_model=SustitucionOut)
def sustituir_componente(equipo_id: int, payload: SustituirPayload, db: Session = Depends(get_db)) -> SustitucionOut:
    try:
        res = trazabilidad.sustituir_componente(
            db, equipo_id, payload.componente_saliente_id, payload.componente_entrante_id,
            payload.posicion, payload.fecha, payload.motivo, payload.usuario, payload.notas,
        )
    except LookupError as e:
        db.rollback()
        raise HTTPException(404, str(e))
    except trazabilidad.ConfiguracionError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    return SustitucionOut(
        desmontaje=res["desmontaje"],
        montaje=res["montaje"],
    )
```

> Note: because `desmontar`/`montar` only `flush()` (not commit), the single `db.rollback()` in the `except` undoes the desmontaje too — that is what `test_sustituir_entrante_already_mounted_is_atomic_409` verifies.

- [ ] **Step 6: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_sustituir.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add backend/app/trazabilidad.py backend/app/schemas.py backend/app/routers/equipos.py backend/tests/test_sustituir.py
git commit -m "feat: sustituir-componente (atomic desmontaje+montaje)"
```

---

## Task 10: Enrich the equipo ficha (compose current state + both histories)

**Files:**
- Modify: `backend/app/routers/equipos.py` (replace the minimal ficha body)
- Test: `backend/tests/test_ficha.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_ficha.py`**

```python
import pytest


@pytest.fixture
def escenario(client):
    pe = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "Sistema"}).json()["id"]
    pc = client.post("/api/productos", json={"part_number": "PXI", "tipo": "componente", "descripcion": "Digi"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "EQ", "producto_id": pe}).json()["id"]
    comp = client.post("/api/componentes", json={"numero_serie": "C", "producto_id": pc}).json()["id"]
    uid = client.post("/api/ubicaciones", json={"nombre": "Indra", "tipo": "fabrica_cliente"}).json()["id"]
    client.post(f"/api/componentes/{comp}/montar", json={"equipo_id": eq, "posicion": "r3", "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    client.post(f"/api/equipos/{eq}/movimientos", json={"ubicacion_destino_id": uid, "fecha": "2026-02-01", "motivo": "entrega"})
    return {"equipo": eq, "ubicacion": uid}


def test_ficha_composes_everything(client, escenario):
    r = client.get(f"/api/equipos/{escenario['equipo']}")
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["equipo"]["numero_serie"] == "EQ"
    assert f["producto"]["part_number"] == "ATE"
    assert f["ubicacion_actual"]["id"] == escenario["ubicacion"]
    assert len(f["componentes"]) == 1 and f["componentes"][0]["posicion"] == "r3"
    assert len(f["historial_movimientos"]) == 1
    assert len(f["historial_configuracion"]) == 1


def test_ficha_no_movimientos_ubicacion_null(client):
    pe = client.post("/api/productos", json={"part_number": "P", "tipo": "equipo", "descripcion": "x"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "S", "producto_id": pe}).json()["id"]
    f = client.get(f"/api/equipos/{eq}").json()
    assert f["ubicacion_actual"] is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_ficha.py -v`
Expected: FAIL (componentes/historial empty in minimal ficha → assertions fail).

- [ ] **Step 3: Replace the `ficha` function body in `backend/app/routers/equipos.py`**

Add to the schemas import line: `CambioConfiguracionOut, ComponenteOut, MovimientoOut, UbicacionOut`. Replace the `ficha` function with:

```python
@router.get("/{equipo_id}", response_model=EquipoFicha)
def ficha(equipo_id: int, db: Session = Depends(get_db)) -> EquipoFicha:
    eq = db.get(models.Equipo, equipo_id)
    if eq is None:
        raise HTTPException(404, "Equipo no encontrado")
    prod = db.get(models.Producto, eq.producto_id)

    ubic = trazabilidad.ubicacion_actual(db, equipo_id)

    componentes = (
        db.query(models.Componente)
        .filter(models.Componente.equipo_id == equipo_id)
        .order_by(models.Componente.posicion)
        .all()
    )
    movimientos = (
        db.query(models.Movimiento)
        .filter(models.Movimiento.equipo_id == equipo_id)
        .order_by(models.Movimiento.fecha.desc(), models.Movimiento.id.desc())
        .all()
    )
    cambios = (
        db.query(models.CambioConfiguracion)
        .filter(models.CambioConfiguracion.equipo_id == equipo_id)
        .order_by(models.CambioConfiguracion.fecha.desc(), models.CambioConfiguracion.id.desc())
        .all()
    )

    return EquipoFicha(
        equipo=EquipoOut.model_validate(eq),
        producto=ProductoOut.model_validate(prod),
        ubicacion_actual=UbicacionOut.model_validate(ubic) if ubic is not None else None,
        componentes=[ComponenteOut.model_validate(c) for c in componentes],
        historial_movimientos=[MovimientoOut.model_validate(m) for m in movimientos],
        historial_configuracion=[CambioConfiguracionOut.model_validate(c) for c in cambios],
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_ficha.py tests/test_equipos.py -v`
Expected: PASS (all green).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/equipos.py backend/tests/test_ficha.py
git commit -m "feat: enrich equipo ficha (current config + ubicacion + both histories)"
```

---

## Task 11: Cross-cutting queries — search by serial, equipment-by-location

**Files:**
- Create: `backend/app/routers/busqueda.py`
- Modify: `backend/app/routers/ubicaciones.py` (add `/{id}/equipos`)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_busqueda.py`

- [ ] **Step 1: Write the failing test `backend/tests/test_busqueda.py`**

```python
import pytest


@pytest.fixture
def escenario(client):
    pe = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "Sistema"}).json()["id"]
    pc = client.post("/api/productos", json={"part_number": "PXI", "tipo": "componente", "descripcion": "Digi"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "EQ-SER", "producto_id": pe}).json()["id"]
    comp = client.post("/api/componentes", json={"numero_serie": "COMP-SER", "producto_id": pc}).json()["id"]
    uid = client.post("/api/ubicaciones", json={"nombre": "Indra", "tipo": "fabrica_cliente"}).json()["id"]
    client.post(f"/api/componentes/{comp}/montar", json={"equipo_id": eq, "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    client.post(f"/api/equipos/{eq}/movimientos", json={"ubicacion_destino_id": uid, "fecha": "2026-02-01", "motivo": "entrega"})
    return {"equipo": eq, "componente": comp, "ubicacion": uid, "prod_componente": pc}


def test_buscar_por_serie_equipo(client, escenario):
    r = client.get("/api/buscar?serie=EQ-SER")
    assert r.status_code == 200
    assert r.json()["tipo"] == "equipo"
    assert r.json()["equipo"]["id"] == escenario["equipo"]


def test_buscar_por_serie_componente_devuelve_su_equipo(client, escenario):
    r = client.get("/api/buscar?serie=COMP-SER")
    body = r.json()
    assert body["tipo"] == "componente"
    assert body["componente"]["id"] == escenario["componente"]
    assert body["equipo_del_componente"]["id"] == escenario["equipo"]


def test_buscar_no_encontrado(client):
    r = client.get("/api/buscar?serie=NOPE")
    assert r.status_code == 200
    assert r.json()["tipo"] == "ninguno"


def test_equipos_por_part_number(client, escenario):
    # equipos que llevan el part number 'PXI' (vía sus componentes)
    r = client.get("/api/equipos?part_number=PXI")
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert escenario["equipo"] in ids


def test_equipos_en_ubicacion(client, escenario):
    r = client.get(f"/api/ubicaciones/{escenario['ubicacion']}/equipos")
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert escenario["equipo"] in ids
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_busqueda.py -v`
Expected: FAIL (routes not present / part_number filter not implemented).

- [ ] **Step 3: Create `backend/app/routers/busqueda.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import ComponenteOut, EquipoOut, ResultadoBusqueda

router = APIRouter(prefix="/api/buscar", tags=["busqueda"])


@router.get("", response_model=ResultadoBusqueda)
def buscar(serie: str, db: Session = Depends(get_db)) -> ResultadoBusqueda:
    eq = db.query(models.Equipo).filter(models.Equipo.numero_serie == serie).first()
    if eq is not None:
        return ResultadoBusqueda(tipo="equipo", equipo=EquipoOut.model_validate(eq))
    comp = db.query(models.Componente).filter(models.Componente.numero_serie == serie).first()
    if comp is not None:
        equipo = db.get(models.Equipo, comp.equipo_id) if comp.equipo_id is not None else None
        return ResultadoBusqueda(
            tipo="componente",
            componente=ComponenteOut.model_validate(comp),
            equipo_del_componente=EquipoOut.model_validate(equipo) if equipo is not None else None,
        )
    return ResultadoBusqueda(tipo="ninguno")
```

- [ ] **Step 4: Add the `part_number` filter to `listar` in `backend/app/routers/equipos.py`**

Extend the `listar` signature with `part_number: Optional[str] = None` and add this branch before the `order_by`:

```python
    if part_number is not None:
        q = (
            q.join(models.Componente, models.Componente.equipo_id == models.Equipo.id)
            .join(models.Producto, models.Producto.id == models.Componente.producto_id)
            .filter(models.Producto.part_number == part_number)
            .distinct()
        )
```

Full updated signature:

```python
def listar(
    producto_id: Optional[int] = None,
    estado: Optional[str] = None,
    part_number: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[models.Equipo]:
```

- [ ] **Step 5: Add `/{id}/equipos` to `backend/app/routers/ubicaciones.py`**

Add imports `from app import trazabilidad` and `from app.schemas import EquipoOut`, then append:

```python
@router.get("/{ubicacion_id}/equipos", response_model=list[EquipoOut])
def equipos_en_ubicacion(ubicacion_id: int, db: Session = Depends(get_db)) -> list[models.Equipo]:
    if db.get(models.Ubicacion, ubicacion_id) is None:
        raise HTTPException(404, "Ubicación no encontrada")
    resultado = []
    for eq in db.query(models.Equipo).all():
        ubic = trazabilidad.ubicacion_actual(db, eq.id)
        if ubic is not None and ubic.id == ubicacion_id:
            resultado.append(eq)
    return resultado
```

> Note: this is an O(n) scan over equipos computing current location each. Fine for the manual-entry scale of v1. If the installed base grows large, replace with a single windowed SQL query (latest movimiento per equipo); out of scope now — `log()` the limitation in the README.

- [ ] **Step 6: Register the busqueda router in `backend/app/main.py`**

```python
from app.routers import busqueda

app.include_router(busqueda.router)
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_busqueda.py -v`
Expected: PASS (5 passed).

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/busqueda.py backend/app/routers/equipos.py backend/app/routers/ubicaciones.py backend/app/main.py backend/tests/test_busqueda.py
git commit -m "feat: cross-cutting queries (search-by-serie, by-part-number, by-location)"
```

---

## Task 12: Full suite green + README + run instructions

**Files:**
- Create: `backend/README.md`
- Test: full suite

- [ ] **Step 1: Run the entire suite**

Run (from `backend/`): `.venv\Scripts\pytest -v`
Expected: ALL PASS (test_health, test_models, test_schemas, test_ubicaciones, test_productos, test_equipos, test_componentes, test_movimientos, test_montaje, test_sustituir, test_ficha, test_busqueda).

- [ ] **Step 2: Create `backend/README.md`**

```markdown
# 6TL Postventa — Backend (trazabilidad + base instalada)

FastAPI + SQLAlchemy + SQLite. Sub-proyecto 1 de la plataforma postventa de 6TL.

## Setup
    python -m venv .venv
    .venv\Scripts\pip install -e ".[dev]"

## Tests
    .venv\Scripts\pytest -q

## Arrancar (puerto 8020 — evita choque con ATE/Quotify :8000 y dashboard :8010)
    .venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8020

Docs interactivas: http://127.0.0.1:8020/docs

## Modelo
6 entidades: Ubicacion, Producto (catálogo), Equipo, Componente, Movimiento (log de ubicación),
CambioConfiguracion (log de montajes/desmontajes). Ubicación actual = último movimiento; config
actual = componentes con equipo_id apuntando al equipo.

## Limitaciones conocidas (v1)
- `GET /api/ubicaciones/{id}/equipos` calcula la ubicación actual por equipo en un scan O(n).
  Suficiente a escala de captura manual; optimizar con query windowed si la base instalada crece.
- Sin auth (uso interno 6TL). Portal de cliente y roles = fase posterior.
```

- [ ] **Step 3: Smoke-test the running server manually**

Run: `.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8020` (in a separate shell), then `curl http://127.0.0.1:8020/api/health`
Expected: `{"status":"ok"}`. Stop the server (Ctrl+C).

- [ ] **Step 4: Commit**

```bash
git add backend/README.md
git commit -m "docs: backend README + run instructions (:8020)"
```

---

## Self-review notes (already applied)

- **Spec coverage:** every spec section maps to a task — model (T1), schemas (T2), CRUD ubicaciones/productos/equipos/componentes (T3–T6), movimiento+ubicación actual (T7), montar/desmontar (T8), sustituir atómico (T9), ficha compuesta (T10), consultas transversales buscar/part_number/ubicación (T11), testing+README+:8020 (T12).
- **Ordering dependency flagged:** `test_producto_delete_in_use_409` (T4) needs the equipos POST (T5); noted inline. The equipos ficha is minimal in T5 and enriched in T10; the T5 test only checks `equipo.numero_serie`, so it stays green throughout.
- **Type consistency:** field names match the contract block at the top across models, schemas, routers, and tests. Service functions: `ubicacion_actual`, `registrar_movimiento`, `montar_componente`, `desmontar_componente`, `sustituir_componente`, exception `ConfiguracionError`.
- **Out of scope (fases posteriores):** RMA, garantías, incidencias, soporte, calibración, firmware, fiabilidad/MTBF, repuestos, SLA, field service, costes, base de conocimiento, portal cliente, KPIs, documental, notificaciones, integraciones. Frontend Lovable se aborda tras el backend (prompts por pantalla), siguiendo tu método.
```
