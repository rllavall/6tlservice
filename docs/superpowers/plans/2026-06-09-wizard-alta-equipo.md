# Wizard de alta de equipo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar de alta un equipo con su ubicación inicial y sus componentes en una sola operación atómica, y rediseñar la pantalla `/equipos/nuevo` como wizard de 4 pasos en inglés.

**Architecture:** Un endpoint nuevo `POST /api/equipos/alta` recibe todo el payload (equipo + ubicación opcional + componentes opcionales). Un módulo de servicio `app/alta_equipo.py` valida primero y luego compone los helpers existentes (`trazabilidad.registrar_movimiento`, `trazabilidad.montar_componente`, que hacen `flush` sin `commit`); el router hace el único `commit`/`rollback`, garantizando todo-o-nada. El frontend (Lovable) reescribe el wizard y hace una sola llamada en el paso de confirmación.

**Tech Stack:** FastAPI + SQLAlchemy + SQLite (backend, pytest TDD vía TestClient); TanStack Start + React (frontend, prompt Lovable).

**Spec:** `docs/superpowers/specs/2026-06-09-wizard-alta-equipo-design.md`

---

## File Structure

- **Create** `backend/app/alta_equipo.py` — servicio de orquestación atómica (`AltaError`, `alta_equipo_completa`). Responsabilidad única: validar y construir el grafo equipo→movimiento→componentes con `flush`, sin commit.
- **Modify** `backend/app/schemas.py` — añadir `EquipoAltaComponente` y `EquipoAltaCreate`.
- **Modify** `backend/app/routers/equipos.py` — añadir la ruta `POST /api/equipos/alta` (importa el servicio, hace commit/rollback, traduce `AltaError`→`HTTPException`).
- **Create** `backend/tests/test_alta_equipo.py` — tests HTTP del endpoint (patrón de `test_equipos.py`).
- **Create** `docs/lovable/27_wizard_alta_equipo.md` — prompt para reescribir el frontend del wizard. **Modify** `docs/lovable/README.md`.

No hay router nuevo que registrar en `main.py` (la ruta vive en el router `equipos`, ya incluido).

**Convenciones del repo a respetar:**
- El servicio usa `db.flush()` (no commit); el **router** hace `db.commit()`/`db.refresh()` y, en error, `db.rollback()` — igual que `routers/movimientos.py` y `routers/configuracion.py`.
- Constraint único en BD: `(producto_id, numero_serie)` tanto en `Equipo` como en `Componente`.
- Los tests usan el fixture `client` (auth simulada) de `tests/conftest.py`.
- `POST /api/equipos` ya autorrellena `meses_garantia` desde `producto.meses_garantia_default` cuando llega `None` (equipos.py:71-72). El alta hace lo MISMO, por consistencia y para no perder la garantía.
- Comandos: ejecutar desde `backend/` con el venv. En este equipo (Git Bash): `./.venv/Scripts/python.exe -m pytest ...`.

---

### Task 1: Schemas del alta

**Files:**
- Modify: `backend/app/schemas.py` (después de `EquipoUpdate`, ~línea 115)
- Test: `backend/tests/test_alta_equipo.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_alta_equipo.py`:

```python
import pytest


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={
        "part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema",
        "meses_garantia_default": 24,
    }).json()["id"]


@pytest.fixture
def prod_componente(client):
    return client.post("/api/productos", json={
        "part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digi",
    }).json()["id"]


@pytest.fixture
def cliente(client):
    return client.post("/api/clientes", json={"nombre": "Indra"}).json()["id"]


@pytest.fixture
def ubicacion(client, cliente):
    return client.post("/api/ubicaciones", json={
        "nombre": "Planta Aranjuez", "tipo": "fabrica_cliente", "cliente_id": cliente,
    }).json()["id"]


def test_alta_schema_defaults():
    from app.schemas import EquipoAltaCreate
    p = EquipoAltaCreate(numero_serie="EQ-1", producto_id=1)
    assert p.estado == "operativo"
    assert p.componentes == []
    assert p.ubicacion_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_alta_equipo.py::test_alta_schema_defaults -v`
Expected: FAIL con `ImportError: cannot import name 'EquipoAltaCreate'`.

- [ ] **Step 3: Add the schemas**

En `backend/app/schemas.py`, justo después de la clase `EquipoUpdate`:

```python
# --- Alta de equipo (wizard) ---
class EquipoAltaComponente(BaseModel):
    producto_id: int
    numero_serie: str
    posicion: Optional[str] = None
    notas: Optional[str] = None


class EquipoAltaCreate(BaseModel):
    numero_serie: str
    producto_id: int
    cliente_id: Optional[int] = None
    fecha_fabricacion: Optional[date] = None
    fecha_entrega: Optional[date] = None
    estado: Literal["operativo", "baja"] = "operativo"
    notas: Optional[str] = None
    meses_garantia: Optional[int] = None
    version: Optional[str] = None
    numero_serie_cliente: Optional[str] = None
    ubicacion_id: Optional[int] = None
    movimiento_fecha: Optional[date] = None
    movimiento_notas: Optional[str] = None
    componentes: list[EquipoAltaComponente] = Field(default_factory=list)
```

(`Field`, `date`, `Literal`, `Optional`, `BaseModel` ya están importados al principio de `schemas.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_alta_equipo.py::test_alta_schema_defaults -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_alta_equipo.py
git commit -m "feat(alta): schemas EquipoAltaCreate/Componente para el wizard de alta"
```

---

### Task 2: Servicio + endpoint, happy path (solo equipo) + prefill de garantía

**Files:**
- Create: `backend/app/alta_equipo.py`
- Modify: `backend/app/routers/equipos.py` (import de schema + nueva ruta tras `crear`, ~línea 81)
- Test: `backend/tests/test_alta_equipo.py`

- [ ] **Step 1: Write the failing test**

Añadir a `tests/test_alta_equipo.py`:

```python
def test_alta_solo_equipo_prefill_garantia(client, prod_equipo):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-100", "producto_id": prod_equipo,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["numero_serie"] == "EQ-100"
    # garantía autorrellenada desde el modelo (meses_garantia_default=24)
    assert body["meses_garantia"] == 24
    # creado de verdad
    assert client.get(f"/api/equipos/{body['id']}").status_code == 200


def test_alta_respeta_garantia_explicita(client, prod_equipo):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-101", "producto_id": prod_equipo, "meses_garantia": 12,
    })
    assert r.status_code == 201, r.text
    assert r.json()["meses_garantia"] == 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_alta_equipo.py -k alta_solo_equipo -v`
Expected: FAIL con 404 (la ruta `/api/equipos/alta` no existe todavía).

- [ ] **Step 3: Create the service**

Crear `backend/app/alta_equipo.py` con la implementación COMPLETA (incluye ya las validaciones que ejercitarán las tareas siguientes):

```python
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import models, trazabilidad
from app.schemas import EquipoAltaCreate


class AltaError(Exception):
    """Error de negocio del alta. Lleva el paso del wizard al que pertenece."""

    def __init__(self, status_code: int, step: str, message: str, index: Optional[int] = None):
        self.status_code = status_code
        self.step = step  # "unit" | "location" | "component"
        self.message = message
        self.index = index
        super().__init__(message)


def _serie_equipo_existe(db: Session, producto_id: int, numero_serie: str) -> bool:
    return (
        db.query(models.Equipo.id)
        .filter(models.Equipo.producto_id == producto_id, models.Equipo.numero_serie == numero_serie)
        .first()
        is not None
    )


def _serie_componente_existe(db: Session, producto_id: int, numero_serie: str) -> bool:
    return (
        db.query(models.Componente.id)
        .filter(models.Componente.producto_id == producto_id, models.Componente.numero_serie == numero_serie)
        .first()
        is not None
    )


def alta_equipo_completa(db: Session, payload: EquipoAltaCreate) -> models.Equipo:
    """Crea equipo + (opcional) movimiento de entrega + (opcional) componentes
    montados, todo con `flush` (sin commit). El llamador (router) hace el commit
    o el rollback. Lanza AltaError ante cualquier validación fallida."""

    # --- validar producto del equipo ---
    prod = db.get(models.Producto, payload.producto_id)
    if prod is None:
        raise AltaError(404, "unit", "Producto del equipo no encontrado")
    if prod.tipo != "equipo":
        raise AltaError(409, "unit", "El producto del equipo no es de tipo 'equipo'")

    # --- validar cliente ---
    if payload.cliente_id is not None and db.get(models.Cliente, payload.cliente_id) is None:
        raise AltaError(404, "unit", "Cliente no encontrado")

    # --- validar serie del equipo (única por producto) ---
    if _serie_equipo_existe(db, payload.producto_id, payload.numero_serie):
        raise AltaError(409, "unit", "Ya existe un equipo con ese (producto, número de serie)")

    # --- validar ubicación ---
    ubic = None
    if payload.ubicacion_id is not None:
        ubic = db.get(models.Ubicacion, payload.ubicacion_id)
        if ubic is None:
            raise AltaError(404, "location", "Ubicación no encontrada")
        if (
            payload.cliente_id is not None
            and ubic.cliente_id is not None
            and ubic.cliente_id != payload.cliente_id
        ):
            raise AltaError(409, "location", "La ubicación pertenece a otro cliente")

    # --- validar componentes (producto + serie, incl. duplicados en el propio payload) ---
    vistos: set[tuple[int, str]] = set()
    for i, c in enumerate(payload.componentes):
        cp = db.get(models.Producto, c.producto_id)
        if cp is None:
            raise AltaError(404, "component", "Producto del componente no encontrado", index=i)
        if cp.tipo != "componente":
            raise AltaError(409, "component", "El producto no es de tipo 'componente'", index=i)
        clave = (c.producto_id, c.numero_serie)
        if clave in vistos or _serie_componente_existe(db, c.producto_id, c.numero_serie):
            raise AltaError(409, "component", "Número de serie de componente duplicado", index=i)
        vistos.add(clave)

    # --- crear equipo (con prefill de garantía, como POST /api/equipos) ---
    meses = payload.meses_garantia
    if meses is None and prod.meses_garantia_default is not None:
        meses = prod.meses_garantia_default
    eq = models.Equipo(
        numero_serie=payload.numero_serie,
        producto_id=payload.producto_id,
        cliente_id=payload.cliente_id,
        fecha_fabricacion=payload.fecha_fabricacion,
        fecha_entrega=payload.fecha_entrega,
        estado=payload.estado,
        notas=payload.notas,
        meses_garantia=meses,
        version=payload.version,
        numero_serie_cliente=payload.numero_serie_cliente,
    )
    db.add(eq)
    db.flush()  # asigna eq.id

    # --- movimiento inicial de ubicación ---
    if ubic is not None:
        fecha_mov = payload.movimiento_fecha or payload.fecha_entrega or date.today()
        trazabilidad.registrar_movimiento(
            db, eq.id, ubic.id, fecha_mov, "entrega", usuario=None, notas=payload.movimiento_notas
        )

    # --- componentes iniciales ---
    for c in payload.componentes:
        comp = models.Componente(producto_id=c.producto_id, numero_serie=c.numero_serie, notas=c.notas)
        db.add(comp)
        db.flush()  # asigna comp.id
        trazabilidad.montar_componente(db, comp.id, eq.id, c.posicion, date.today(), "entrega_inicial")

    return eq
```

- [ ] **Step 4: Add the route**

En `backend/app/routers/equipos.py`:

1. Añadir `EquipoAltaCreate` a la línea de import de `app.schemas` (línea 12).
2. Añadir la ruta justo después de la función `crear` (tras la línea 81):

```python
@router.post("/alta", response_model=EquipoOut, status_code=201)
def alta(payload: EquipoAltaCreate, db: Session = Depends(get_db)) -> models.Equipo:
    from app.alta_equipo import AltaError, alta_equipo_completa

    try:
        eq = alta_equipo_completa(db, payload)
        db.commit()
    except AltaError as e:
        db.rollback()
        raise HTTPException(e.status_code, {"step": e.step, "index": e.index, "message": e.message})
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, {"step": "unit", "index": None, "message": "Conflicto de integridad al crear el alta"})
    db.refresh(eq)
    return eq
```

(`IntegrityError`, `HTTPException`, `Depends`, `Session`, `models` ya están importados en `equipos.py`. La ruta `/alta` no colisiona con `GET /{equipo_id}` porque son métodos distintos, ni con `POST ""`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_alta_equipo.py -v`
Expected: PASS (los dos tests de garantía y el de schema).

- [ ] **Step 6: Commit**

```bash
git add backend/app/alta_equipo.py backend/app/routers/equipos.py backend/tests/test_alta_equipo.py
git commit -m "feat(alta): endpoint atómico POST /api/equipos/alta (equipo + prefill garantía)"
```

---

### Task 3: Ubicación inicial (movimiento "entrega")

**Files:**
- Test: `backend/tests/test_alta_equipo.py`
- (La lógica ya está en `alta_equipo.py`; este test la fija.)

- [ ] **Step 1: Write the failing test**

```python
def test_alta_con_ubicacion_crea_movimiento(client, prod_equipo, cliente, ubicacion):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-200", "producto_id": prod_equipo,
        "cliente_id": cliente, "ubicacion_id": ubicacion,
    })
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    ficha = client.get(f"/api/equipos/{eid}").json()
    assert ficha["ubicacion_actual"] is not None
    assert ficha["ubicacion_actual"]["id"] == ubicacion
```

- [ ] **Step 2: Run test to verify status**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_alta_equipo.py::test_alta_con_ubicacion_crea_movimiento -v`
Expected: PASS (la implementación de Task 2 ya crea el movimiento). `EquipoFicha.ubicacion_actual` es un `UbicacionOut` con clave `id` (verificado en `schemas.py:231`).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_alta_equipo.py
git commit -m "test(alta): la ubicación inicial crea el movimiento de entrega"
```

---

### Task 4: Componentes iniciales (crear + montar)

**Files:**
- Test: `backend/tests/test_alta_equipo.py`

- [ ] **Step 1: Write the failing test**

```python
def test_alta_con_componentes_los_monta(client, prod_equipo, prod_componente):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-300", "producto_id": prod_equipo,
        "componentes": [
            {"producto_id": prod_componente, "numero_serie": "C-1", "posicion": "slot1"},
            {"producto_id": prod_componente, "numero_serie": "C-2"},
        ],
    })
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    comps = client.get(f"/api/componentes?equipo_id={eid}").json()
    series = sorted(c["numero_serie"] for c in comps)
    assert series == ["C-1", "C-2"]
```

- [ ] **Step 2: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_alta_equipo.py::test_alta_con_componentes_los_monta -v`
Expected: PASS (Task 2 ya crea y monta). Confirma que los dos componentes quedan con `equipo_id=eid`.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_alta_equipo.py
git commit -m "test(alta): componentes iniciales se crean y montan en el equipo"
```

---

### Task 5: Validación de tipos de producto

**Files:**
- Test: `backend/tests/test_alta_equipo.py`

- [ ] **Step 1: Write the failing test**

```python
def test_alta_rechaza_producto_equipo_no_equipo(client, prod_componente):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "X", "producto_id": prod_componente,
    })
    assert r.status_code == 409
    assert r.json()["detail"]["step"] == "unit"


def test_alta_rechaza_componente_no_componente(client, prod_equipo):
    # usar el producto de equipo como si fuera componente
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-400", "producto_id": prod_equipo,
        "componentes": [{"producto_id": prod_equipo, "numero_serie": "C-X"}],
    })
    assert r.status_code == 409
    assert r.json()["detail"]["step"] == "component"
    assert r.json()["detail"]["index"] == 0
    # atómico: el equipo NO se creó
    assert client.get("/api/equipos?numero_serie=EQ-400").json() == []
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_alta_equipo.py -k "rechaza" -v`
Expected: PASS (la validación de tipos está en `alta_equipo.py` y ocurre ANTES de crear nada, así que nada se persiste).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_alta_equipo.py
git commit -m "test(alta): rechazo de tipos de producto incorrectos (unit/component)"
```

---

### Task 6: Unicidad de serie + atomicidad

**Files:**
- Test: `backend/tests/test_alta_equipo.py`

- [ ] **Step 1: Write the failing test**

```python
def test_alta_serie_equipo_duplicada_409_nada_creado(client, prod_equipo):
    client.post("/api/equipos/alta", json={"numero_serie": "DUP", "producto_id": prod_equipo})
    r = client.post("/api/equipos/alta", json={"numero_serie": "DUP", "producto_id": prod_equipo})
    assert r.status_code == 409
    assert r.json()["detail"]["step"] == "unit"
    # sigue habiendo exactamente 1
    assert len(client.get(f"/api/equipos?producto_id={prod_equipo}").json()) == 1


def test_alta_componente_duplicado_en_payload_rollback_total(client, prod_equipo, prod_componente):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-500", "producto_id": prod_equipo,
        "componentes": [
            {"producto_id": prod_componente, "numero_serie": "SAME"},
            {"producto_id": prod_componente, "numero_serie": "SAME"},
        ],
    })
    assert r.status_code == 409
    assert r.json()["detail"]["step"] == "component"
    assert r.json()["detail"]["index"] == 1
    # rollback total: ni el equipo ni el primer componente quedaron
    assert client.get("/api/equipos?numero_serie=EQ-500").json() == []
    assert client.get("/api/componentes").json() == []
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_alta_equipo.py -k "duplicad" -v`
Expected: PASS. La serie de equipo se valida antes de crear; el componente duplicado (índice 1) se detecta en la pre-validación, así que el equipo nunca llega a `flush`+commit. Nada se persiste.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_alta_equipo.py
git commit -m "test(alta): unicidad de serie y atomicidad (rollback total)"
```

---

### Task 7: Ubicación de otro cliente / almacén sin cliente

**Files:**
- Test: `backend/tests/test_alta_equipo.py`

- [ ] **Step 1: Write the failing test**

```python
def test_alta_ubicacion_de_otro_cliente_rechaza(client, prod_equipo):
    c1 = client.post("/api/clientes", json={"nombre": "Cli-1"}).json()["id"]
    c2 = client.post("/api/clientes", json={"nombre": "Cli-2"}).json()["id"]
    ub2 = client.post("/api/ubicaciones", json={
        "nombre": "Planta C2", "tipo": "fabrica_cliente", "cliente_id": c2,
    }).json()["id"]
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-600", "producto_id": prod_equipo,
        "cliente_id": c1, "ubicacion_id": ub2,
    })
    assert r.status_code == 409
    assert r.json()["detail"]["step"] == "location"
    assert client.get("/api/equipos?numero_serie=EQ-600").json() == []


def test_alta_ubicacion_sin_cliente_se_acepta(client, prod_equipo, cliente):
    ub = client.post("/api/ubicaciones", json={
        "nombre": "Almacén 6TL", "tipo": "sede_6tl",
    }).json()["id"]
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-601", "producto_id": prod_equipo,
        "cliente_id": cliente, "ubicacion_id": ub,
    })
    assert r.status_code == 201, r.text
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_alta_equipo.py -k "ubicacion" -v`
Expected: PASS (la regla solo rechaza cuando hay cliente Y la ubicación tiene un cliente distinto).

- [ ] **Step 3: Run the FULL suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: toda la suite en verde (los tests previos no se rompen; el endpoint nuevo es aditivo).
**Nota:** parar cualquier `uvicorn` contra `postventa.db` antes de correr la suite (el seeder de ayuda toca esa BD al importar `app.main`).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_alta_equipo.py
git commit -m "test(alta): ubicación de otro cliente se rechaza; almacén sin cliente se acepta"
```

---

### Task 8: Prompt Lovable 27 — wizard de 4 pasos (frontend)

**Files:**
- Create: `docs/lovable/27_wizard_alta_equipo.md`
- Modify: `docs/lovable/README.md` (añadir la línea del prompt 27)

- [ ] **Step 1: Write the Lovable prompt**

Crear `docs/lovable/27_wizard_alta_equipo.md` con este contenido:

```markdown
# Prompt 27 — Rediseño del wizard de alta de equipo

**Archivo:** `src/routes/equipos.nuevo.tsx` (reescribir por completo).
**NO toques** ningún otro archivo de rutas ni los tipos no relacionados.

## Objetivo
Convertir el alta de equipo en un **wizard moderno de 4 pasos** con barra de
progreso, **todo el texto en inglés**, valores por defecto inteligentes, captura
de ubicación y un paso de revisión final. Una sola llamada al backend al
confirmar.

## Pasos
Barra de progreso arriba (1 Unit · 2 Customer & location · 3 Components · 4
Review), paso completado con ✓, actual resaltado. Botones **Back / Next**; Next
deshabilitado hasta que los obligatorios del paso estén. Todo el estado vive en
local; NADA se guarda hasta "Create unit".

1. **Unit** (obligatorios: Model + Serial number)
   - Model* — `GET /api/productos?tipo=equipo`, muestra `part_number — descripcion`.
   - Serial number*.
   - Customer serial no. (optional).
   - Version (optional).
   - Al elegir Model, precargar Warranty months (paso 2) con
     `producto.meses_garantia_default`.
2. **Customer & location** (dos subtarjetas)
   - Customer (optional) — `GET /api/clientes`.
   - Location (optional) — `GET /api/ubicaciones`, **filtrado por el Customer
     elegido** (si hay) más las ubicaciones sin cliente. Hint: "Sets where the
     unit is installed (creates the initial delivery movement)".
   - Manufacture date (optional).
   - Delivery date (optional) — **por defecto = hoy**.
   - Warranty months (precargado del modelo, editable).
   - Status — Active/Inactive (operativo/baja), por defecto Active.
   - Notes (optional).
3. **Initial components** (optional)
   - Editor de filas: Model (`tipo=componente`) + Serial number + Position +
     Notes. Añadir/quitar filas. Se puede saltar.
4. **Review & confirm**
   - Resumen read-only por secciones, cada una con enlace **Edit** que vuelve a
     su paso. Mostrar lo que se creará: la unidad, su ubicación (o "No
     location"), y la lista de componentes.
   - Avisos discretos: "No customer", "No location → won't show on the map",
     "Warranty not set".
   - Botón **Create unit**.

## Guardado (una sola llamada)
Al confirmar: `POST /api/equipos/alta` con el body:
```json
{
  "numero_serie": "...", "producto_id": 0, "cliente_id": null,
  "fecha_fabricacion": null, "fecha_entrega": "2026-06-09",
  "estado": "operativo", "notas": null, "meses_garantia": 24,
  "version": null, "numero_serie_cliente": null,
  "ubicacion_id": null, "movimiento_notas": null,
  "componentes": [
    {"producto_id": 0, "numero_serie": "...", "posicion": null, "notas": null}
  ]
}
```
Campos vacíos → enviar `null`/omitir; `componentes` → `[]` si no hay.
Respuesta 201 = el equipo creado → navegar a `/equipos/$id`.

## Manejo de errores
Si la respuesta NO es 201, el body es
`{ "detail": { "step": "unit"|"location"|"component", "index": number|null, "message": string } }`.
Mostrar `message` (toast) y **saltar al paso indicado** por `step` (para
`component`, además resaltar la fila `index`). Quedarse en el wizard sin perder
lo introducido.

## Estilo
Coherente con el resto de la app (lila `#9e007e`, componentes shadcn ya
presentes: Button, Input, Label, Select, Textarea). Wizard centrado, `max-w-3xl`.
Enlace "← Installed base" arriba.
```

- [ ] **Step 2: Update the README index**

Añadir a `docs/lovable/README.md` la línea correspondiente al prompt 27 (siguiendo el formato de las líneas 25/26 existentes), p. ej.:

```markdown
- `27_wizard_alta_equipo.md` — rediseño de `/equipos/nuevo` como wizard de 4 pasos (inglés) que usa `POST /api/equipos/alta`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/27_wizard_alta_equipo.md docs/lovable/README.md
git commit -m "docs(lovable): prompt 27 wizard de alta de equipo (4 pasos)"
```

---

## Notas de cierre (post-implementación)

- **Pegar el prompt 27** en Lovable, sincronizar el submódulo `frontend`, `bun x tsc --noEmit`, y hacer smoke contra `:8020` (login admin → `/equipos/nuevo` → alta completa → ver el equipo en el mapa y con sus componentes).
- **Auditoría:** el alta queda como un commit coherente; el listener ORM registra los inserts (equipo + movimiento + componentes) en la misma transacción.
- **Idioma del resto de la app:** unificación completa a inglés queda como follow-up separado (fuera de alcance).
- Tras mergear, considerar `git push` del backend a `github.com/rllavall/6tlservice`.
