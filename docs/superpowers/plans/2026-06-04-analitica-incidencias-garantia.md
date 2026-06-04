# Analítica de incidencias + control de garantía — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir tipo de incidencia (rma/soporte_venta/soporte_tecnico/calibracion), control de garantía calculable por equipo, y un endpoint de analítica de incidencias, más el prompt Lovable de la pantalla `/analitica`.

**Architecture:** Backend FastAPI + SQLAlchemy + SQLite. Lógica de garantía y de agregación en módulos puros (`app/garantia.py`, `app/analitica_incidencias.py`) testeables sin red ni reloj. Migración idempotente (`app/migrations.py`) para columnas nuevas. Un único endpoint de agregación server-side. El frontend (Lovable, submódulo `frontend/`) solo pinta.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2 (Mapped), Pydantic v2, pytest. Frontend TanStack Start + recharts (vía prompt Lovable).

**Convenciones del repo (importantes):**
- Tests en `backend/tests/`, fixtures en `conftest.py`: `db_session` (sesión sobre SQLite en memoria) y `client` (TestClient con `get_db` override).
- Ejecutar tests: desde `backend/`, `\.venv\Scripts\python.exe -m pytest -q`.
- Backend en `:8020`. Arrancar: `backend\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8020`.
- Schemas Pydantic en `app/schemas.py`; `_ORM` = `model_config = ConfigDict(from_attributes=True)`.
- Commit por tarea. Mensajes en español, terminar con la línea Co-Authored-By habitual.

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---------|-----------------|--------|
| `backend/app/garantia.py` | Lógica pura de garantía (fin, estado, en_garantia). Sin imports de models. | Crear |
| `backend/app/models.py` | + `Producto.meses_garantia_default`, `Equipo.meses_garantia`, `Equipo.version`, props garantía en `Equipo`, `Incidencia.tipo`. | Modificar |
| `backend/app/migrations.py` | Declarar columnas nuevas (idempotente). | Modificar |
| `backend/app/schemas.py` | + campos garantía/version en Producto/Equipo, + `tipo` en Incidencia, + schemas de analítica. | Modificar |
| `backend/app/incidencias_service.py` | `generar_codigo(db, tipo)` por prefijo. | Modificar |
| `backend/app/routers/incidencias.py` | POST autodetecta `en_garantia` para RMA; filtro `tipo` en el listado. | Modificar |
| `backend/app/routers/equipos.py` | POST hereda `meses_garantia` del producto si no se indica. | Modificar |
| `backend/app/analitica_incidencias.py` | Agregación (distribuciones, KPIs, tendencia, fiabilidad, garantía). | Crear |
| `backend/app/routers/analitica.py` | `GET /api/analitica/incidencias`. | Crear |
| `backend/app/main.py` | Registrar router de analítica. | Modificar |
| `docs/lovable/13_analitica_garantia.md` | Prompt Lovable de la pantalla. | Crear |
| `docs/lovable/README.md` | Añadir prompt 13 al índice. | Modificar |

---

## Task 1: Módulo puro de garantía (`app/garantia.py`)

**Files:**
- Create: `backend/app/garantia.py`
- Test: `backend/tests/test_garantia.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_garantia.py
from datetime import date
from types import SimpleNamespace

from app import garantia


def _eq(fecha_entrega=None, meses_garantia=None):
    return SimpleNamespace(fecha_entrega=fecha_entrega, meses_garantia=meses_garantia)


def test_add_months_simple():
    assert garantia._add_months(date(2024, 1, 15), 24) == date(2026, 1, 15)


def test_add_months_clamp_fin_de_mes():
    # 31 ene + 1 mes -> 28/29 feb (no existe 31 feb)
    assert garantia._add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)


def test_fecha_fin_garantia():
    assert garantia.fecha_fin_garantia(_eq(date(2024, 1, 1), 24)) == date(2026, 1, 1)


def test_fecha_fin_garantia_sin_datos():
    assert garantia.fecha_fin_garantia(_eq(None, 24)) is None
    assert garantia.fecha_fin_garantia(_eq(date(2024, 1, 1), None)) is None


def test_estado_vigente():
    eq = _eq(date(2024, 1, 1), 24)  # fin 2026-01-01
    assert garantia.estado_garantia(eq, date(2025, 1, 1)) == "vigente"


def test_estado_por_vencer():
    eq = _eq(date(2024, 1, 1), 24)  # fin 2026-01-01
    assert garantia.estado_garantia(eq, date(2025, 12, 1)) == "por_vencer"  # 31 dias


def test_estado_vencida():
    eq = _eq(date(2024, 1, 1), 24)  # fin 2026-01-01
    assert garantia.estado_garantia(eq, date(2026, 6, 1)) == "vencida"


def test_estado_sin_datos():
    assert garantia.estado_garantia(_eq(None, None), date(2026, 1, 1)) == "sin_datos"


def test_equipo_en_garantia():
    eq = _eq(date(2024, 1, 1), 24)  # fin 2026-01-01
    assert garantia.equipo_en_garantia(eq, date(2025, 6, 1)) is True
    assert garantia.equipo_en_garantia(eq, date(2026, 6, 1)) is False
    assert garantia.equipo_en_garantia(_eq(None, None), date(2026, 1, 1)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_garantia.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.garantia'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/garantia.py
"""Lógica pura de garantía. No importa models: opera por duck-typing
(`equipo.fecha_entrega`, `equipo.meses_garantia`) y con `hoy`/`fecha` inyectables."""
from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

UMBRAL_POR_VENCER_DIAS = 90


def _add_months(d: date, months: int) -> date:
    m0 = d.month - 1 + months
    y = d.year + m0 // 12
    m = m0 % 12 + 1
    ultimo = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, ultimo))


def fecha_fin_garantia(equipo) -> Optional[date]:
    entrega = getattr(equipo, "fecha_entrega", None)
    meses = getattr(equipo, "meses_garantia", None)
    if entrega is None or meses is None:
        return None
    return _add_months(entrega, meses)


def estado_garantia(equipo, hoy: date, umbral_dias: int = UMBRAL_POR_VENCER_DIAS) -> str:
    fin = fecha_fin_garantia(equipo)
    if fin is None:
        return "sin_datos"
    if hoy > fin:
        return "vencida"
    if (fin - hoy).days <= umbral_dias:
        return "por_vencer"
    return "vigente"


def equipo_en_garantia(equipo, fecha: date) -> Optional[bool]:
    fin = fecha_fin_garantia(equipo)
    if fin is None:
        return None
    return fecha <= fin
```

- [ ] **Step 4: Run test to verify it passes**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_garantia.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/garantia.py backend/tests/test_garantia.py
git commit -m "feat: modulo puro de garantia (fin/estado/en_garantia)"
```

---

## Task 2: Columnas nuevas en modelos + migración + props de garantía

**Files:**
- Modify: `backend/app/models.py` (Producto ~50-59, Equipo ~62-76, Incidencia ~127-147)
- Modify: `backend/app/migrations.py:12-17`
- Test: `backend/tests/test_migrations.py`, `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing migration test**

Añadir al final de `backend/tests/test_migrations.py`:

```python
def test_agrega_columnas_garantia_y_tipo():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with eng.begin() as c:
        c.exec_driver_sql("CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT)")
        c.exec_driver_sql("CREATE TABLE equipos (id INTEGER PRIMARY KEY, numero_serie TEXT)")
        c.exec_driver_sql(
            "CREATE TABLE incidencias (id INTEGER PRIMARY KEY, codigo TEXT)"
        )
        c.exec_driver_sql("INSERT INTO incidencias (id, codigo) VALUES (1, 'RMA-0001')")
    add_missing_columns(eng)
    assert "meses_garantia_default" in _columnas(eng, "productos")
    assert "meses_garantia" in _columnas(eng, "equipos")
    assert "version" in _columnas(eng, "equipos")
    assert "tipo" in _columnas(eng, "incidencias")
    # la fila existente recibe el default 'rma'
    with eng.connect() as c:
        fila = c.execute(text("SELECT tipo FROM incidencias WHERE id=1")).fetchone()
    assert fila[0] == "rma"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_migrations.py::test_agrega_columnas_garantia_y_tipo -q`
Expected: FAIL (faltan columnas).

- [ ] **Step 3: Update migrations**

En `backend/app/migrations.py`, sustituir el dict `_COLUMNAS_NUEVAS` por:

```python
# tabla -> {columna: tipo SQL}
_COLUMNAS_NUEVAS: dict[str, dict[str, str]] = {
    "ubicaciones": {"latitud": "FLOAT", "longitud": "FLOAT"},
    # FKs añadidos por el sub-proyecto Incidencias; BDs anteriores no los tienen.
    "movimientos": {"incidencia_id": "INTEGER"},
    "cambios_configuracion": {"incidencia_id": "INTEGER"},
    # Garantía + tipo de incidencia (sub-proyecto analítica).
    "productos": {"meses_garantia_default": "INTEGER DEFAULT 24"},
    "equipos": {"meses_garantia": "INTEGER", "version": "TEXT"},
    "incidencias": {"tipo": "TEXT DEFAULT 'rma'"},
}
```

(SQLite rellena las filas existentes con el DEFAULT al hacer `ADD COLUMN`, por eso `RMA-0001` queda `tipo='rma'`.)

- [ ] **Step 4: Run migration test to verify it passes**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_migrations.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing model test**

Añadir al final de `backend/tests/test_models.py`:

```python
from datetime import date as _date


def test_equipo_props_garantia(db_session):
    from app import models
    p = models.Producto(part_number="PN1", tipo="equipo", descripcion="d", meses_garantia_default=24)
    db_session.add(p); db_session.flush()
    eq = models.Equipo(
        numero_serie="SN1", producto_id=p.id, version="Rev C",
        fecha_entrega=_date(2024, 1, 1), meses_garantia=24,
    )
    db_session.add(eq); db_session.flush()
    assert eq.version == "Rev C"
    assert eq.fecha_fin_garantia == _date(2026, 1, 1)
    assert eq.estado_garantia in {"vigente", "por_vencer", "vencida"}


def test_incidencia_tipo_default(db_session):
    from app import models, incidencias_service as svc
    inc = models.Incidencia(
        codigo="RMA-9001", titulo="t", descripcion_problema="d",
        estado="abierta", fecha_apertura=_date(2026, 6, 1),
    )
    db_session.add(inc); db_session.flush()
    assert inc.tipo == "rma"
```

(Si `test_models.py` no importa `date`, el alias `_date` evita choques. Ajusta los imports existentes si ya hay uno.)

- [ ] **Step 6: Run model test to verify it fails**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_models.py -q`
Expected: FAIL (atributos/columnas inexistentes).

- [ ] **Step 7: Update models**

En `backend/app/models.py`:

1. En `class Producto`, tras `notas`:
```python
    meses_garantia_default: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=24)
```

2. En `class Equipo`, tras `notas` (antes de las relaciones), añadir columnas y props:
```python
    meses_garantia: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    @property
    def fecha_fin_garantia(self):
        from app import garantia
        return garantia.fecha_fin_garantia(self)

    @property
    def estado_garantia(self) -> str:
        from datetime import date as _date
        from app import garantia
        return garantia.estado_garantia(self, _date.today())
```
(Las props van como atributos de instancia normales; `mapped_column`s deben ir antes que las `relationship`/props para legibilidad — colócalas justo tras `notas` y deja las props al final de la clase.)

3. En `class Incidencia`, tras `codigo` (o junto a `prioridad`):
```python
    tipo: Mapped[str] = mapped_column(String, default="rma")
```

Verifica que `Integer` y `String` ya están importados en `models.py` (lo están; se usan en otras columnas).

- [ ] **Step 8: Run tests to verify they pass**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_models.py tests/test_migrations.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models.py backend/app/migrations.py backend/tests/test_models.py backend/tests/test_migrations.py
git commit -m "feat: campos garantia/version/tipo en modelos + migracion idempotente"
```

---

## Task 3: Schemas de Producto/Equipo/Incidencia + herencia de meses_garantia

**Files:**
- Modify: `backend/app/schemas.py` (Producto 64-80, Equipo 84-110, Incidencia 225-271)
- Modify: `backend/app/routers/equipos.py:52-70`
- Test: `backend/tests/test_equipos.py`, `backend/tests/test_incidencias.py`

- [ ] **Step 1: Write the failing test**

Añadir a `backend/tests/test_equipos.py`:

```python
def test_equipo_create_hereda_meses_garantia_y_expone_garantia(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-G", "tipo": "equipo", "descripcion": "Equipo G",
        "meses_garantia_default": 12,
    }).json()
    r = client.post("/api/equipos", json={
        "numero_serie": "SN-G", "producto_id": p["id"],
        "fecha_entrega": "2024-01-01", "version": "Rev A",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version"] == "Rev A"
    assert body["meses_garantia"] == 12           # heredado del producto
    assert body["fecha_fin_garantia"] == "2025-01-01"
    assert body["estado_garantia"] in {"vigente", "por_vencer", "vencida"}


def test_equipo_create_meses_garantia_explicito_gana(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-G2", "tipo": "equipo", "descripcion": "Equipo G2",
        "meses_garantia_default": 12,
    }).json()
    r = client.post("/api/equipos", json={
        "numero_serie": "SN-G2", "producto_id": p["id"], "meses_garantia": 36,
    })
    assert r.json()["meses_garantia"] == 36
```

Añadir a `backend/tests/test_incidencias.py`:

```python
def test_incidencia_create_acepta_tipo_y_lo_devuelve(client):
    p = client.post("/api/productos", json={"part_number": "PN-I", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-I", "producto_id": p["id"]}).json()
    r = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "Cal anual", "descripcion_problema": "x",
        "tipo": "calibracion", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 201, r.text
    assert r.json()["tipo"] == "calibracion"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_equipos.py tests/test_incidencias.py -q`
Expected: FAIL (campos desconocidos / no devueltos).

- [ ] **Step 3: Update schemas**

En `backend/app/schemas.py`:

1. `ProductoCreate`: añadir antes de `notas` o al final:
```python
    meses_garantia_default: Optional[int] = 24
```
2. `ProductoOut`: añadir:
```python
    meses_garantia_default: Optional[int] = None
```
3. `EquipoCreate`: añadir:
```python
    meses_garantia: Optional[int] = None
    version: Optional[str] = None
```
4. `EquipoUpdate`: añadir:
```python
    meses_garantia: Optional[int] = None
    version: Optional[str] = None
```
5. `EquipoOut`: añadir:
```python
    meses_garantia: Optional[int] = None
    version: Optional[str] = None
    fecha_fin_garantia: Optional[date] = None
    estado_garantia: Optional[str] = None
```
6. `IncidenciaCreate`: añadir (antes del `model_validator`):
```python
    tipo: Literal["rma", "soporte_venta", "soporte_tecnico", "calibracion"] = "rma"
```
7. `IncidenciaUpdate`: añadir:
```python
    tipo: Optional[Literal["rma", "soporte_venta", "soporte_tecnico", "calibracion"]] = None
```
8. `IncidenciaOut`: añadir tras `codigo`:
```python
    tipo: str
```

- [ ] **Step 4: Update equipo create router (herencia)**

En `backend/app/routers/equipos.py`, función `crear` (línea ~52), sustituir el bloque de construcción:

```python
    eq = models.Equipo(**payload.model_dump())
```

por:

```python
    data = payload.model_dump()
    if data.get("meses_garantia") is None and prod.meses_garantia_default is not None:
        data["meses_garantia"] = prod.meses_garantia_default
    eq = models.Equipo(**data)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_equipos.py tests/test_incidencias.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/equipos.py backend/tests/test_equipos.py backend/tests/test_incidencias.py
git commit -m "feat: schemas garantia/version/tipo + herencia meses_garantia del producto"
```

---

## Task 4: Código por tipo + autodetección de en_garantia en RMA + filtro tipo

**Files:**
- Modify: `backend/app/incidencias_service.py:23-33`
- Modify: `backend/app/routers/incidencias.py:27-67`
- Test: `backend/tests/test_incidencia_service.py`, `backend/tests/test_incidencias.py`

- [ ] **Step 1: Write the failing test**

Añadir a `backend/tests/test_incidencia_service.py`:

```python
def test_generar_codigo_por_tipo(db_session):
    assert svc.generar_codigo(db_session, "rma") == "RMA-0001"
    assert svc.generar_codigo(db_session, "soporte_venta") == "SV-0001"
    assert svc.generar_codigo(db_session, "soporte_tecnico") == "ST-0001"
    assert svc.generar_codigo(db_session, "calibracion") == "CAL-0001"


def test_generar_codigo_secuencia_independiente_por_prefijo(db_session):
    _nueva(db_session, equipo_id=None, componente_id=None)  # RMA-0001
    db_session.add(models.Incidencia(
        codigo="SV-0001", titulo="t", descripcion_problema="d", estado="abierta",
        tipo="soporte_venta", fecha_apertura=date(2026, 6, 1),
    ))
    db_session.flush()
    assert svc.generar_codigo(db_session, "rma") == "RMA-0002"
    assert svc.generar_codigo(db_session, "soporte_venta") == "SV-0002"
```

Añadir a `backend/tests/test_incidencias.py`:

```python
def test_rma_autodetecta_en_garantia(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-W", "tipo": "equipo", "descripcion": "d", "meses_garantia_default": 24,
    }).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN-W", "producto_id": p["id"], "fecha_entrega": "2025-06-01",
    }).json()
    # RMA abierto dentro de garantia (fin = 2027-06-01)
    r = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "Fallo", "descripcion_problema": "x",
        "tipo": "rma", "fecha_apertura": "2026-06-01",
    })
    assert r.status_code == 201, r.text
    assert r.json()["en_garantia"] is True
    assert r.json()["codigo"].startswith("RMA-")


def test_rma_en_garantia_override_manual(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-W2", "tipo": "equipo", "descripcion": "d", "meses_garantia_default": 24,
    }).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN-W2", "producto_id": p["id"], "fecha_entrega": "2025-06-01",
    }).json()
    r = client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "Fallo", "descripcion_problema": "x",
        "tipo": "rma", "en_garantia": False, "fecha_apertura": "2026-06-01",
    })
    assert r.json()["en_garantia"] is False  # respeta el override


def test_filtro_por_tipo(client):
    p = client.post("/api/productos", json={"part_number": "PN-F", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-F", "producto_id": p["id"]}).json()
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "a", "descripcion_problema": "x", "tipo": "rma", "fecha_apertura": "2026-06-01"})
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "b", "descripcion_problema": "x", "tipo": "calibracion", "fecha_apertura": "2026-06-01"})
    r = client.get("/api/incidencias?tipo=calibracion")
    assert r.status_code == 200
    assert [i["tipo"] for i in r.json()] == ["calibracion"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_incidencia_service.py tests/test_incidencias.py -q`
Expected: FAIL.

- [ ] **Step 3: Update `generar_codigo`**

En `backend/app/incidencias_service.py`, sustituir la función `generar_codigo` por:

```python
_PREFIJO_TIPO = {
    "rma": "RMA",
    "soporte_venta": "SV",
    "soporte_tecnico": "ST",
    "calibracion": "CAL",
}


def generar_codigo(db: Session, tipo: str = "rma") -> str:
    """Siguiente código `PREFIJO-NNNN` (secuencia propia por prefijo de tipo)."""
    prefijo = _PREFIJO_TIPO.get(tipo, "RMA")
    nums = []
    for (codigo,) in db.query(models.Incidencia.codigo).all():
        if codigo and codigo.startswith(prefijo + "-"):
            try:
                nums.append(int(codigo.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"{prefijo}-{n:04d}"
```

- [ ] **Step 4: Update POST incidencia + filtro tipo**

En `backend/app/routers/incidencias.py`:

1. Añadir el import de garantía junto a los otros (línea ~8):
```python
from app import garantia
```
2. En `listar` (línea ~27), añadir parámetro `tipo` y su filtro:
```python
    tipo: Optional[str] = None,
```
(añádelo a la firma, junto a los demás `Optional`), y dentro del cuerpo, junto a los otros `if`:
```python
    if tipo is not None:
        q = q.filter(models.Incidencia.tipo == tipo)
```
3. Sustituir la función `crear` (línea ~53-67) por:
```python
@router.post("", response_model=IncidenciaOut, status_code=201)
def crear(payload: IncidenciaCreate, db: Session = Depends(get_db)) -> models.Incidencia:
    eq = None
    if payload.equipo_id is not None:
        eq = db.get(models.Equipo, payload.equipo_id)
        if eq is None:
            raise HTTPException(404, "Equipo no encontrado")
    if payload.componente_id is not None and db.get(models.Componente, payload.componente_id) is None:
        raise HTTPException(404, "Componente no encontrado")
    data = payload.model_dump()
    if data["tipo"] == "rma" and data.get("en_garantia") is None and eq is not None:
        data["en_garantia"] = garantia.equipo_en_garantia(eq, data["fecha_apertura"])
    inc = models.Incidencia(
        codigo=svc.generar_codigo(db, data["tipo"]),
        estado="abierta",
        **data,
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_incidencia_service.py tests/test_incidencias.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/incidencias_service.py backend/app/routers/incidencias.py backend/tests/test_incidencia_service.py backend/tests/test_incidencias.py
git commit -m "feat: codigo por tipo + autodeteccion en_garantia en RMA + filtro tipo"
```

---

## Task 5: Schemas de analítica + distribuciones + KPIs de tiempo

**Files:**
- Modify: `backend/app/schemas.py` (al final, sección nueva `# --- Analitica ---`)
- Create: `backend/app/analitica_incidencias.py`
- Test: `backend/tests/test_analitica.py`

- [ ] **Step 1: Add analítica schemas**

En `backend/app/schemas.py`, al final del archivo:

```python
# --- Analítica de incidencias ---
class ConteoItem(BaseModel):
    clave: str
    etiqueta: str
    valor: int


class KpiTiempoItem(BaseModel):
    clave: str
    etiqueta: str
    dias: Optional[float] = None
    n: int = 0


class KpiTiempo(BaseModel):
    mttr_dias: Optional[float] = None
    diagnostico_dias: Optional[float] = None
    edad_abiertas_dias: Optional[float] = None
    por_tipo: list[KpiTiempoItem] = []
    por_producto: list[KpiTiempoItem] = []
    por_tecnico: list[KpiTiempoItem] = []


class PuntoTendencia(BaseModel):
    mes: str  # YYYY-MM
    abiertas: int
    cerradas: int
    backlog: int


class RankingItem(BaseModel):
    id: Optional[int] = None
    etiqueta: str
    valor: int


class ResumenGarantia(BaseModel):
    equipos_por_estado: list[ConteoItem] = []
    rma_en_garantia: int = 0
    rma_fuera_garantia: int = 0
    rma_garantia_desconocida: int = 0


class AnaliticaIncidenciasOut(BaseModel):
    total: int
    por_tipo: list[ConteoItem] = []
    por_producto: list[ConteoItem] = []
    por_tecnico: list[ConteoItem] = []
    por_prioridad: list[ConteoItem] = []
    por_estado: list[ConteoItem] = []
    por_cliente: list[ConteoItem] = []
    kpis_tiempo: KpiTiempo = KpiTiempo()
    tendencia_mensual: list[PuntoTendencia] = []
    fiabilidad_productos: list[RankingItem] = []
    fiabilidad_equipos: list[RankingItem] = []
    garantia: ResumenGarantia = ResumenGarantia()
```

- [ ] **Step 2: Write the failing test (distribuciones + KPIs)**

```python
# backend/tests/test_analitica.py
from datetime import date

from app import analitica_incidencias as ana
from app import models


def _seed(db):
    """2 equipos del mismo producto, varias incidencias de distintos tipos."""
    p = models.Producto(part_number="PN-A", tipo="equipo", descripcion="Equipo A", meses_garantia_default=24)
    db.add(p); db.flush()
    cli = models.Cliente(nombre="Cli1"); db.add(cli); db.flush()
    eq1 = models.Equipo(numero_serie="S1", producto_id=p.id, cliente_id=cli.id,
                        fecha_entrega=date(2025, 1, 1), meses_garantia=24)
    eq2 = models.Equipo(numero_serie="S2", producto_id=p.id,
                        fecha_entrega=date(2020, 1, 1), meses_garantia=24)
    db.add_all([eq1, eq2]); db.flush()
    incs = [
        models.Incidencia(codigo="RMA-0001", tipo="rma", titulo="t", descripcion_problema="d",
            prioridad="alta", estado="cerrada", asignado_a="ana", en_garantia=True,
            equipo_id=eq1.id, fecha_apertura=date(2026, 1, 1),
            fecha_diagnostico=date(2026, 1, 3), fecha_resolucion=date(2026, 1, 11),
            fecha_cierre=date(2026, 1, 12)),
        models.Incidencia(codigo="CAL-0001", tipo="calibracion", titulo="t", descripcion_problema="d",
            prioridad="media", estado="abierta", asignado_a="luis",
            equipo_id=eq2.id, fecha_apertura=date(2026, 2, 1)),
        models.Incidencia(codigo="RMA-0002", tipo="rma", titulo="t", descripcion_problema="d",
            prioridad="baja", estado="resuelta", asignado_a="ana", en_garantia=False,
            equipo_id=eq2.id, fecha_apertura=date(2026, 3, 1),
            fecha_resolucion=date(2026, 3, 5)),
    ]
    db.add_all(incs); db.flush()
    return p, eq1, eq2


def _mapa(items):
    return {c.clave: c.valor for c in items}


def test_total_y_distribuciones(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    assert out.total == 3
    assert _mapa(out.por_tipo) == {"rma": 2, "calibracion": 1}
    assert _mapa(out.por_prioridad) == {"alta": 1, "media": 1, "baja": 1}
    assert _mapa(out.por_estado) == {"cerrada": 1, "abierta": 1, "resuelta": 1}
    assert _mapa(out.por_tecnico) == {"ana": 2, "luis": 1}
    # 1 incidencia de eq1 + 2 de eq2, mismo producto -> 3
    assert sum(c.valor for c in out.por_producto) == 3


def test_kpis_tiempo(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    # MTTR = media de (resolucion - apertura) sobre resueltas/cerradas:
    # RMA-0001: 10 dias, RMA-0002: 4 dias -> media 7.0
    assert out.kpis_tiempo.mttr_dias == 7.0
    # diagnostico: solo RMA-0001 (3-1)=2 dias
    assert out.kpis_tiempo.diagnostico_dias == 2.0
    # edad abiertas: solo CAL-0001 abierta, apertura 2026-02-01 -> hoy 2026-06-01 = 120 dias
    assert out.kpis_tiempo.edad_abiertas_dias == 120.0


def test_filtros_desde_hasta_y_tipo(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1), tipo="rma")
    assert out.total == 2
    out2 = ana.calcular(db_session, hoy=date(2026, 6, 1), desde=date(2026, 2, 15))
    assert out2.total == 1  # solo RMA-0002 (2026-03-01)


def test_vacio_no_rompe(db_session):
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    assert out.total == 0
    assert out.kpis_tiempo.mttr_dias is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_analitica.py -q`
Expected: FAIL (`No module named 'app.analitica_incidencias'`).

- [ ] **Step 4: Implement módulo (parte 1: filtros, distribuciones, KPIs)**

```python
# backend/app/analitica_incidencias.py
"""Agregación de incidencias para la pantalla de analítica.

Funciones puras sobre la sesión de BD; `hoy` se inyecta para tests deterministas.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import garantia, models
from app.schemas import (
    AnaliticaIncidenciasOut,
    ConteoItem,
    KpiTiempo,
    KpiTiempoItem,
    PuntoTendencia,
    RankingItem,
    ResumenGarantia,
)

_ETIQUETA_TIPO = {
    "rma": "RMA",
    "soporte_venta": "Soporte Venta",
    "soporte_tecnico": "Soporte Técnico",
    "calibracion": "Calibración",
}


def _producto_de(db: Session, inc: models.Incidencia) -> Optional[models.Producto]:
    if inc.equipo_id is not None:
        eq = db.get(models.Equipo, inc.equipo_id)
        return db.get(models.Producto, eq.producto_id) if eq is not None else None
    if inc.componente_id is not None:
        comp = db.get(models.Componente, inc.componente_id)
        return db.get(models.Producto, comp.producto_id) if comp is not None else None
    return None


def _cliente_id_de(db: Session, inc: models.Incidencia) -> Optional[int]:
    eq = db.get(models.Equipo, inc.equipo_id) if inc.equipo_id is not None else None
    if eq is None and inc.componente_id is not None:
        comp = db.get(models.Componente, inc.componente_id)
        if comp is not None and comp.equipo_id is not None:
            eq = db.get(models.Equipo, comp.equipo_id)
    return eq.cliente_id if eq is not None else None


def _incidencias_filtradas(db, desde, hasta, tipo, cliente_id) -> list[models.Incidencia]:
    q = db.query(models.Incidencia)
    if tipo is not None:
        q = q.filter(models.Incidencia.tipo == tipo)
    if desde is not None:
        q = q.filter(models.Incidencia.fecha_apertura >= desde)
    if hasta is not None:
        q = q.filter(models.Incidencia.fecha_apertura <= hasta)
    incs = q.all()
    if cliente_id is not None:
        incs = [i for i in incs if _cliente_id_de(db, i) == cliente_id]
    return incs


def _media(valores: list[int]) -> Optional[float]:
    return round(sum(valores) / len(valores), 1) if valores else None


def _conteos(claves_etiquetas: list[tuple[str, str]]) -> list[ConteoItem]:
    c = Counter(k for k, _ in claves_etiquetas)
    etiqueta = dict(claves_etiquetas)
    return [ConteoItem(clave=k, etiqueta=etiqueta[k], valor=v)
            for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]


def calcular(db: Session, hoy: date, desde: Optional[date] = None,
             hasta: Optional[date] = None, tipo: Optional[str] = None,
             cliente_id: Optional[int] = None) -> AnaliticaIncidenciasOut:
    incs = _incidencias_filtradas(db, desde, hasta, tipo, cliente_id)
    prod_por_inc = {i.id: _producto_de(db, i) for i in incs}

    def _prod_label(i):
        p = prod_por_inc.get(i.id)
        return (str(p.id), f"{p.part_number} — {p.descripcion}") if p else ("sin_producto", "Sin producto")

    # Distribuciones
    por_tipo = _conteos([(i.tipo, _ETIQUETA_TIPO.get(i.tipo, i.tipo)) for i in incs])
    por_prioridad = _conteos([(i.prioridad, i.prioridad) for i in incs])
    por_estado = _conteos([(i.estado, i.estado) for i in incs])
    por_tecnico = _conteos([(i.asignado_a or "sin_asignar", i.asignado_a or "Sin asignar") for i in incs])
    por_producto = _conteos([_prod_label(i) for i in incs])
    cli_pairs = []
    for i in incs:
        cid = _cliente_id_de(db, i)
        if cid is None:
            cli_pairs.append(("sin_cliente", "Sin cliente"))
        else:
            cli = db.get(models.Cliente, cid)
            cli_pairs.append((str(cid), cli.nombre if cli else f"Cliente {cid}"))
    por_cliente = _conteos(cli_pairs)

    # KPIs de tiempo
    def _resol_dias(i):
        if i.fecha_resolucion is not None:
            return (i.fecha_resolucion - i.fecha_apertura).days
        return None

    def _diag_dias(i):
        if i.fecha_diagnostico is not None:
            return (i.fecha_diagnostico - i.fecha_apertura).days
        return None

    mttr = _media([d for i in incs if (d := _resol_dias(i)) is not None])
    diag = _media([d for i in incs if (d := _diag_dias(i)) is not None])
    edad = _media([(hoy - i.fecha_apertura).days for i in incs if i.estado != "cerrada"])

    def _kpi_por(grupo_fn, etiqueta_fn) -> list[KpiTiempoItem]:
        grupos = defaultdict(list)
        for i in incs:
            d = _resol_dias(i)
            if d is not None:
                grupos[grupo_fn(i)].append(d)
        items = []
        for clave, valores in grupos.items():
            items.append(KpiTiempoItem(clave=clave, etiqueta=etiqueta_fn(clave), dias=_media(valores), n=len(valores)))
        return sorted(items, key=lambda it: it.clave)

    kpis = KpiTiempo(
        mttr_dias=mttr,
        diagnostico_dias=diag,
        edad_abiertas_dias=edad,
        por_tipo=_kpi_por(lambda i: i.tipo, lambda k: _ETIQUETA_TIPO.get(k, k)),
        por_producto=_kpi_por(lambda i: _prod_label(i)[0], lambda k: k),
        por_tecnico=_kpi_por(lambda i: i.asignado_a or "sin_asignar", lambda k: k),
    )

    return AnaliticaIncidenciasOut(
        total=len(incs),
        por_tipo=por_tipo,
        por_producto=por_producto,
        por_tecnico=por_tecnico,
        por_prioridad=por_prioridad,
        por_estado=por_estado,
        por_cliente=por_cliente,
        kpis_tiempo=kpis,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_analitica.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/analitica_incidencias.py backend/tests/test_analitica.py
git commit -m "feat: analitica de incidencias (schemas + distribuciones + KPIs de tiempo)"
```

---

## Task 6: Tendencia mensual + fiabilidad + resumen de garantía

**Files:**
- Modify: `backend/app/analitica_incidencias.py` (función `calcular`)
- Test: `backend/tests/test_analitica.py`

- [ ] **Step 1: Write the failing test**

Añadir a `backend/tests/test_analitica.py`:

```python
def test_tendencia_mensual(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    t = {p.mes: p for p in out.tendencia_mensual}
    # aperturas: ene, feb, mar 2026 (1 cada uno); cierre: ene 2026 (RMA-0001)
    assert t["2026-01"].abiertas == 1 and t["2026-01"].cerradas == 1
    assert t["2026-02"].abiertas == 1 and t["2026-02"].cerradas == 0
    # backlog acumulado: ene 1-1=0, feb 0+1=1, mar 1+1=2
    assert t["2026-01"].backlog == 0
    assert t["2026-02"].backlog == 1
    assert t["2026-03"].backlog == 2


def test_fiabilidad_y_garantia(db_session):
    _seed(db_session)
    out = ana.calcular(db_session, hoy=date(2026, 6, 1))
    # fiabilidad: el unico producto acumula 3 incidencias
    assert out.fiabilidad_productos[0].valor == 3
    # equipo eq2 tiene 2 incidencias, eq1 tiene 1 -> eq2 primero
    assert out.fiabilidad_equipos[0].valor == 2
    # garantia equipos: eq1 entrega 2025 fin 2027 -> vigente; eq2 entrega 2020 -> vencida
    estados = {c.clave: c.valor for c in out.garantia.equipos_por_estado}
    assert estados.get("vigente") == 1
    assert estados.get("vencida") == 1
    # RMA en/fuera garantia: RMA-0001 True, RMA-0002 False
    assert out.garantia.rma_en_garantia == 1
    assert out.garantia.rma_fuera_garantia == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_analitica.py::test_tendencia_mensual tests/test_analitica.py::test_fiabilidad_y_garantia -q`
Expected: FAIL (listas vacías).

- [ ] **Step 3: Extend `calcular`**

En `backend/app/analitica_incidencias.py`, dentro de `calcular`, **antes** del `return`, añadir:

```python
    # Tendencia mensual
    aperturas = Counter(i.fecha_apertura.strftime("%Y-%m") for i in incs)
    cierres = Counter(i.fecha_cierre.strftime("%Y-%m") for i in incs if i.fecha_cierre is not None)
    meses = sorted(set(aperturas) | set(cierres))
    tendencia = []
    backlog = 0
    for mes in meses:
        ab = aperturas.get(mes, 0)
        ce = cierres.get(mes, 0)
        backlog += ab - ce
        tendencia.append(PuntoTendencia(mes=mes, abiertas=ab, cerradas=ce, backlog=backlog))

    # Fiabilidad (rankings)
    fiab_prod = Counter()
    etiqueta_prod = {}
    fiab_eq = Counter()
    etiqueta_eq = {}
    for i in incs:
        clave, etq = _prod_label(i)
        fiab_prod[clave] += 1
        etiqueta_prod[clave] = etq
        if i.equipo_id is not None:
            fiab_eq[i.equipo_id] += 1
    for eid in list(fiab_eq):
        eq = db.get(models.Equipo, eid)
        etiqueta_eq[eid] = eq.numero_serie if eq is not None else f"Equipo {eid}"
    fiabilidad_productos = [
        RankingItem(id=None, etiqueta=etiqueta_prod[k], valor=v)
        for k, v in sorted(fiab_prod.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    ]
    fiabilidad_equipos = [
        RankingItem(id=k, etiqueta=etiqueta_eq[k], valor=v)
        for k, v in sorted(fiab_eq.items(), key=lambda kv: (-kv[1], str(kv[0])))[:10]
    ]

    # Resumen de garantía
    equipos = db.query(models.Equipo).all()
    estados = Counter(garantia.estado_garantia(eq, hoy) for eq in equipos)
    _ETQ_GAR = {"vigente": "Vigente", "por_vencer": "Por vencer", "vencida": "Vencida", "sin_datos": "Sin datos"}
    equipos_por_estado = [
        ConteoItem(clave=k, etiqueta=_ETQ_GAR.get(k, k), valor=v)
        for k, v in sorted(estados.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    rma = [i for i in incs if i.tipo == "rma"]
    rma_en = sum(1 for i in rma if i.en_garantia is True)
    rma_fuera = sum(1 for i in rma if i.en_garantia is False)
    rma_desc = sum(1 for i in rma if i.en_garantia is None)
    resumen_garantia = ResumenGarantia(
        equipos_por_estado=equipos_por_estado,
        rma_en_garantia=rma_en,
        rma_fuera_garantia=rma_fuera,
        rma_garantia_desconocida=rma_desc,
    )
```

Y ampliar el `return` para incluir los nuevos campos:

```python
    return AnaliticaIncidenciasOut(
        total=len(incs),
        por_tipo=por_tipo,
        por_producto=por_producto,
        por_tecnico=por_tecnico,
        por_prioridad=por_prioridad,
        por_estado=por_estado,
        por_cliente=por_cliente,
        kpis_tiempo=kpis,
        tendencia_mensual=tendencia,
        fiabilidad_productos=fiabilidad_productos,
        fiabilidad_equipos=fiabilidad_equipos,
        garantia=resumen_garantia,
    )
```

- [ ] **Step 4: Run all analítica tests to verify they pass**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_analitica.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/analitica_incidencias.py backend/tests/test_analitica.py
git commit -m "feat: analitica tendencia mensual + fiabilidad + resumen de garantia"
```

---

## Task 7: Router `/api/analitica/incidencias` + registro en main

**Files:**
- Create: `backend/app/routers/analitica.py`
- Modify: `backend/app/main.py:53-54` (registrar router)
- Test: `backend/tests/test_analitica_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_analitica_endpoint.py
def test_endpoint_vacio(client):
    r = client.get("/api/analitica/incidencias")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 0
    assert body["kpis_tiempo"]["mttr_dias"] is None
    assert body["garantia"]["rma_en_garantia"] == 0


def test_endpoint_con_datos_y_filtro(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-E", "tipo": "equipo", "descripcion": "Eq E", "meses_garantia_default": 24,
    }).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN-E", "producto_id": p["id"], "fecha_entrega": "2025-06-01",
    }).json()
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "a",
        "descripcion_problema": "x", "tipo": "rma", "fecha_apertura": "2026-06-01"})
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "b",
        "descripcion_problema": "x", "tipo": "calibracion", "fecha_apertura": "2026-06-01"})
    r = client.get("/api/analitica/incidencias")
    assert r.json()["total"] == 2
    r2 = client.get("/api/analitica/incidencias?tipo=rma")
    assert r2.json()["total"] == 1
    assert {c["clave"]: c["valor"] for c in r2.json()["por_tipo"]} == {"rma": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_analitica_endpoint.py -q`
Expected: FAIL (404, router no existe).

- [ ] **Step 3: Create router**

```python
# backend/app/routers/analitica.py
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import analitica_incidencias as ana
from app.db import get_db
from app.schemas import AnaliticaIncidenciasOut

router = APIRouter(prefix="/api/analitica", tags=["analitica"])


@router.get("/incidencias", response_model=AnaliticaIncidenciasOut)
def incidencias(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    tipo: Optional[str] = None,
    cliente_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> AnaliticaIncidenciasOut:
    return ana.calcular(db, hoy=date.today(), desde=desde, hasta=hasta, tipo=tipo, cliente_id=cliente_id)
```

- [ ] **Step 4: Register router in main**

En `backend/app/main.py`, tras el bloque del router `mapa` (línea ~53-54):

```python
from app.routers import analitica
app.include_router(analitica.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `\.venv\Scripts\python.exe -m pytest tests/test_analitica_endpoint.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/analitica.py backend/app/main.py backend/tests/test_analitica_endpoint.py
git commit -m "feat: endpoint GET /api/analitica/incidencias"
```

---

## Task 8: Suite completa + smoke en vivo + migración de la BD dev

**Files:** ninguno nuevo (verificación).

- [ ] **Step 1: Run the full suite**

Run (desde `backend/`): `\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS, todos verde (107 previos + los nuevos de Tasks 1-7). Si algo del seed/demo falla, revisar imports.

- [ ] **Step 2: Smoke en vivo contra la BD dev**

Arrancar el backend (la migración se aplica al import de `main`):
```
\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```
En otra shell, comprobar:
```
curl -s "http://127.0.0.1:8020/api/analitica/incidencias" 
```
Expected: 200 con `total` ≈ 58 (datos demo) y `por_tipo` con `rma` (las 58 existentes quedaron `tipo='rma'` por la migración). `garantia.equipos_por_estado` con buckets de los 78 equipos.

- [ ] **Step 3: Verificar un equipo expone garantía**

```
curl -s "http://127.0.0.1:8020/api/equipos/1"
```
Expected: el objeto `equipo` incluye `meses_garantia`, `version` (probablemente null en demo), `fecha_fin_garantia`, `estado_garantia`.

- [ ] **Step 4: Parar el backend**

`taskkill /PID <pid_uvicorn> /T /F` (buscar pid con `netstat -ano | findstr :8020`). ⚠️ uvicorn `--reload` deja reloaders zombie; usar `/T`.

- [ ] **Step 5: Commit (si hubo ajustes)**

Si todo verde y sin cambios, no hay commit. Si hubo arreglos, commitearlos con mensaje descriptivo.

---

## Task 9: Prompt Lovable 13 (pantalla `/analitica` + tipo + garantía)

**Files:**
- Create: `docs/lovable/13_analitica_garantia.md`
- Modify: `docs/lovable/README.md`

- [ ] **Step 1: Write the Lovable prompt**

Crear `docs/lovable/13_analitica_garantia.md` con este contenido:

```markdown
# Prompt 13 — Analítica de incidencias + control de garantía

Contexto: app de postventa (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`). Paleta lila `#9e007e`. Usa el helper
`api<T>()` de `src/lib/api` y `@/lib/types`. Gráficos con `recharts` (ya disponible vía shadcn).

## 1. Tipos nuevos en `src/lib/types.ts`
- `IncidenciaTipo = "rma" | "soporte_venta" | "soporte_tecnico" | "calibracion"`.
- Añade `tipo: IncidenciaTipo` a `Incidencia` / `IncidenciaOut`.
- Añade a `Equipo`/`EquipoFicha.equipo`: `meses_garantia: number | null`, `version: string | null`,
  `fecha_fin_garantia: string | null`, `estado_garantia: "vigente"|"por_vencer"|"vencida"|"sin_datos"|null`.
- Tipos de analítica espejo del backend: `ConteoItem{clave,etiqueta,valor}`,
  `KpiTiempoItem{clave,etiqueta,dias,n}`, `KpiTiempo{mttr_dias,diagnostico_dias,edad_abiertas_dias,por_tipo[],por_producto[],por_tecnico[]}`,
  `PuntoTendencia{mes,abiertas,cerradas,backlog}`, `RankingItem{id,etiqueta,valor}`,
  `ResumenGarantia{equipos_por_estado:ConteoItem[],rma_en_garantia,rma_fuera_garantia,rma_garantia_desconocida}`,
  `AnaliticaIncidencias{total,por_tipo,por_producto,por_tecnico,por_prioridad,por_estado,por_cliente,kpis_tiempo,tendencia_mensual,fiabilidad_productos,fiabilidad_equipos,garantia}`.

## 2. Ruta nueva `src/routes/analitica.tsx`
- `useQuery` a `GET /api/analitica/incidencias` con query string de filtros.
- Cabecera con filtros globales: rango de fechas (`desde`/`hasta`), `tipo` (select 4 opciones + "Todos"),
  cliente (select desde `/api/clientes`). Al cambiar, refetch.
- KPI cards arriba: Total incidencias, MTTR (días), Edad media abiertas (días), % RMA en garantía
  (`rma_en_garantia / (rma_en_garantia+rma_fuera_garantia)`).
- BarChart por: tipo, producto (top 10), técnico, prioridad, estado. Etiqueta = `etiqueta`, valor = `valor`.
- LineChart de `tendencia_mensual`: series `abiertas`, `cerradas`, `backlog` por `mes`.
- Tabla de `fiabilidad_productos` y `fiabilidad_equipos` (etiqueta + nº incidencias), enlazando el equipo a su ficha.
- Sección "Garantía": tarjetas/badges con `equipos_por_estado` (Vigente/Por vencer/Vencida/Sin datos)
  y RMA en/fuera/desconocida.
- Estados de carga y vacío ("Sin datos para los filtros seleccionados").

## 3. Alta/edición de incidencia (`incidencias.nueva.tsx`, panel de edición de `incidencias.$id.tsx`)
- Añadir selector **Tipo** (4 opciones, default RMA). Enviar `tipo` en el POST/PATCH.
- Para RMA con equipo: tras elegir equipo, mostrar (solo lectura) la garantía detectada; `en_garantia`
  llega autodetectada del backend pero sigue siendo editable.
- Mostrar badge de **tipo** en la lista (`incidencias.tsx`) y en la ficha.

## 4. Ficha + alta/edición del equipo (`equipos.$id.tsx`, `equipos.nuevo.tsx`, `equipos.$id.editar.tsx`)
- Campos editables `version` y `meses_garantia`.
- Mostrar PN/descripción (del producto), SN, año de fabricación (de `fecha_fabricacion`) y `version`.
- Badge de **estado de garantía** con color: vigente=verde, por_vencer=ámbar, vencida=rojo, sin_datos=gris;
  mostrar `fecha_fin_garantia` cuando exista.

## 5. Navegación
- Añadir entrada "Analítica" al menú/nav hacia `/analitica`.

No toques el backend ni el contrato: usa exactamente los nombres de campo anteriores.
```

- [ ] **Step 2: Update README índice**

En `docs/lovable/README.md`, añadir a la lista de prompts:
```markdown
- `13_analitica_garantia.md` — pantalla /analitica (estadísticas por tipo/producto/técnico, KPIs de
  tiempo, tendencia, fiabilidad) + selector de tipo en incidencia + control de garantía en la ficha del equipo.
```

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/13_analitica_garantia.md docs/lovable/README.md
git commit -m "docs: prompt Lovable 13 — analitica de incidencias + control de garantia"
```

- [ ] **Step 4: (Manual, fuera del plan) Pegar el prompt en Lovable**

El usuario pega el prompt 13 en Lovable; luego `git pull` del submódulo `frontend`, `bun install`,
`bun x tsc --noEmit`, validación de contrato y smoke visual de `/analitica`.

---

## Self-review (cobertura del spec)

- **Tipo de incidencia (enum + default rma):** Tasks 2, 3, 4. ✅
- **Código por prefijo de tipo:** Task 4. ✅
- **Garantía: meses_garantia en equipo + default en producto + derivados:** Tasks 1, 2, 3. ✅
- **Autodetección en_garantia en RMA (overridable):** Task 4. ✅
- **version a nivel de unidad + año fabricación como fecha:** Tasks 2, 3, 9. ✅
- **Endpoint analítica con 4 grupos + garantía + filtros:** Tasks 5, 6, 7. ✅
- **Migración idempotente con default 'rma' para filas existentes:** Task 2. ✅
- **Frontend (pantalla /analitica + tipo + garantía en ficha):** Task 9 (prompt Lovable). ✅
- **Fuera de alcance (alertas por vencer, SLA, coste, export):** no implementado, correcto. ✅

Tipos/firmas consistentes entre tareas: `calcular(db, hoy, desde, hasta, tipo, cliente_id)`,
`generar_codigo(db, tipo)`, `garantia.equipo_en_garantia(equipo, fecha)`, schemas `AnaliticaIncidenciasOut`
y subschemas — usados igual en Tasks 5/6/7 y en el prompt 9.
```
