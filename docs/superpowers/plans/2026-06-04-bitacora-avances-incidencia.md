# Bitácora de avances de incidencia — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir una bitácora de avances a cada incidencia: entradas cronológicas (fecha/autor/tipo/texto) gestionables por API (crear/listar/editar/borrar) y expuestas en el expediente, para usarse desde un popup en la lista y desde la ficha.

**Architecture:** Nueva entidad `AvanceIncidencia` (tabla `avances_incidencia`, FK a incidencias) con un router de sub-recurso `/api/incidencias/{id}/avances`. La tabla la crea `create_all` al arrancar (no requiere migración de columnas). Las entradas se incluyen en `IncidenciaFicha`. El frontend (Lovable, prompt 14) añade un componente reutilizable usado en lista (modal) y ficha.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2 (Mapped), Pydantic v2, pytest. Frontend TanStack Start (prompt Lovable).

**Convenciones del repo:**
- Tests en `backend/tests/`, fixtures `db_session` y `client` en `conftest.py`.
- Ejecutar: desde `backend/`, `\.venv\Scripts\python.exe -m pytest -q`. Vía Bash:
  `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_avances.py -q`.
- Schemas en `app/schemas.py`; `_ORM` = `ConfigDict(from_attributes=True)`. Routers registrados en `app/main.py`.
- Commit por tarea; mensaje en español terminando con la línea Co-Authored-By habitual.

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---------|-----------------|--------|
| `backend/app/models.py` | + entidad `AvanceIncidencia` (tabla `avances_incidencia`). | Modificar (añadir al final) |
| `backend/app/schemas.py` | + `AvanceCreate`/`AvanceUpdate`/`AvanceOut`; + `avances` en `IncidenciaFicha`. | Modificar |
| `backend/app/routers/avances.py` | Router sub-recurso `/api/incidencias/{id}/avances` (GET/POST/PATCH/DELETE). | Crear |
| `backend/app/main.py` | Registrar router de avances. | Modificar |
| `backend/app/routers/incidencias.py` | Poblar `avances` en el expediente (`GET /api/incidencias/{id}`). | Modificar |
| `backend/tests/test_avances.py` | Tests del modelo + endpoints + expediente. | Crear |
| `docs/lovable/14_bitacora_avances.md` | Prompt Lovable de la bitácora. | Crear |
| `docs/lovable/README.md` | Añadir prompt 14 al índice. | Modificar |

---

## Task 1: Modelo `AvanceIncidencia` + schemas

**Files:**
- Modify: `backend/app/models.py` (añadir al final, tras `class Incidencia`)
- Modify: `backend/app/schemas.py` (sección Incidencia: tras `TransicionPayload`, antes de `IncidenciaFicha`)
- Test: `backend/tests/test_avances.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_avances.py`:

```python
from datetime import date


def test_modelo_avance_defaults(db_session):
    from app import models
    inc = models.Incidencia(
        codigo="RMA-7001", titulo="t", descripcion_problema="d",
        estado="abierta", fecha_apertura=date(2026, 6, 1),
    )
    db_session.add(inc); db_session.flush()
    av = models.AvanceIncidencia(incidencia_id=inc.id, fecha=date(2026, 6, 2), texto="Primer avance")
    db_session.add(av); db_session.flush()
    assert av.tipo == "avance"        # default
    assert av.autor is None
    assert av.texto == "Primer avance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_avances.py -q`
Expected: FAIL (`AttributeError: module 'app.models' has no attribute 'AvanceIncidencia'`).

- [ ] **Step 3: Add the model**

Al FINAL de `backend/app/models.py` añadir:

```python
class AvanceIncidencia(Base):
    __tablename__ = "avances_incidencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incidencia_id: Mapped[int] = mapped_column(ForeignKey("incidencias.id"))
    fecha: Mapped[date] = mapped_column(Date)
    autor: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tipo: Mapped[str] = mapped_column(String, default="avance")
    texto: Mapped[str] = mapped_column(String)
```

(`Integer`, `String`, `Date`, `ForeignKey`, `Optional`, `Mapped`, `mapped_column` ya están importados en `models.py`.)

- [ ] **Step 4: Add the schemas**

En `backend/app/schemas.py`, localiza la clase `TransicionPayload` y `IncidenciaFicha` (la sección `# --- Incidencia ---`). Inserta ESTO **entre** `TransicionPayload` y `IncidenciaFicha`:

```python
# --- Avances de incidencia (bitácora) ---
_TIPO_AVANCE = Literal["avance", "report", "llamada", "visita", "diagnostico", "otro"]


class AvanceCreate(BaseModel):
    fecha: Optional[date] = None   # el router pone hoy si no se envía
    autor: Optional[str] = None
    tipo: _TIPO_AVANCE = "avance"
    texto: str = Field(min_length=1)


class AvanceUpdate(BaseModel):
    fecha: Optional[date] = None
    autor: Optional[str] = None
    tipo: Optional[_TIPO_AVANCE] = None
    texto: Optional[str] = Field(default=None, min_length=1)


class AvanceOut(_ORM):
    id: int
    incidencia_id: int
    fecha: date
    autor: Optional[str] = None
    tipo: str
    texto: str
```

Y en la línea de import de pydantic (arriba del archivo), añade `Field`:
```python
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_avances.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/tests/test_avances.py
git commit -m "feat: modelo AvanceIncidencia + schemas de bitacora"
```
(Mensaje termina con la línea `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.)

---

## Task 2: Router CRUD `/api/incidencias/{id}/avances`

**Files:**
- Create: `backend/app/routers/avances.py`
- Modify: `backend/app/main.py` (registrar router)
- Test: `backend/tests/test_avances.py`

- [ ] **Step 1: Write the failing tests**

Añade a `backend/tests/test_avances.py`:

```python
def _seed_incidencia(client):
    p = client.post("/api/productos", json={"part_number": "PN-AV", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-AV", "producto_id": p["id"]}).json()
    return client.post("/api/incidencias", json={
        "equipo_id": eq["id"], "titulo": "t", "descripcion_problema": "x", "fecha_apertura": "2026-06-01",
    }).json()


def test_crear_avance(client):
    inc = _seed_incidencia(client)
    r = client.post(f"/api/incidencias/{inc['id']}/avances", json={
        "tipo": "report", "autor": "ana", "texto": "Llamada al cliente", "fecha": "2026-06-03",
    })
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["tipo"] == "report" and b["autor"] == "ana" and b["texto"] == "Llamada al cliente"
    assert b["incidencia_id"] == inc["id"]


def test_crear_avance_fecha_por_defecto_hoy(client):
    from datetime import date
    inc = _seed_incidencia(client)
    r = client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "sin fecha"})
    assert r.status_code == 201, r.text
    assert r.json()["fecha"] == date.today().isoformat()
    assert r.json()["tipo"] == "avance"  # default


def test_crear_avance_texto_vacio_422(client):
    inc = _seed_incidencia(client)
    r = client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": ""})
    assert r.status_code == 422


def test_crear_avance_incidencia_inexistente_404(client):
    r = client.post("/api/incidencias/9999/avances", json={"texto": "x"})
    assert r.status_code == 404


def test_listar_avances_orden_desc(client):
    inc = _seed_incidencia(client)
    client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "viejo", "fecha": "2026-06-01"})
    client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "nuevo", "fecha": "2026-06-05"})
    r = client.get(f"/api/incidencias/{inc['id']}/avances")
    assert r.status_code == 200
    assert [a["texto"] for a in r.json()] == ["nuevo", "viejo"]


def test_editar_avance(client):
    inc = _seed_incidencia(client)
    av = client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "borrador"}).json()
    r = client.patch(f"/api/incidencias/{inc['id']}/avances/{av['id']}", json={"texto": "corregido", "tipo": "visita"})
    assert r.status_code == 200, r.text
    assert r.json()["texto"] == "corregido" and r.json()["tipo"] == "visita"


def test_editar_avance_de_otra_incidencia_404(client):
    inc1 = _seed_incidencia(client)
    # segunda incidencia sobre el mismo equipo
    eqid = client.get(f"/api/incidencias/{inc1['id']}").json()["incidencia"]["equipo_id"]
    inc2 = client.post("/api/incidencias", json={
        "equipo_id": eqid, "titulo": "t2", "descripcion_problema": "x", "fecha_apertura": "2026-06-01",
    }).json()
    av = client.post(f"/api/incidencias/{inc1['id']}/avances", json={"texto": "de inc1"}).json()
    r = client.patch(f"/api/incidencias/{inc2['id']}/avances/{av['id']}", json={"texto": "hack"})
    assert r.status_code == 404


def test_borrar_avance(client):
    inc = _seed_incidencia(client)
    av = client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "a borrar"}).json()
    r = client.delete(f"/api/incidencias/{inc['id']}/avances/{av['id']}")
    assert r.status_code == 204
    # ya no aparece
    assert client.get(f"/api/incidencias/{inc['id']}/avances").json() == []
    # segundo borrado -> 404
    assert client.delete(f"/api/incidencias/{inc['id']}/avances/{av['id']}").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_avances.py -q`
Expected: FAIL (404 en todos los endpoints — router no existe).

- [ ] **Step 3: Create the router**

Crear `backend/app/routers/avances.py`:

```python
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import AvanceCreate, AvanceOut, AvanceUpdate

router = APIRouter(prefix="/api/incidencias", tags=["avances"])


def _incidencia_o_404(db: Session, incidencia_id: int) -> models.Incidencia:
    inc = db.get(models.Incidencia, incidencia_id)
    if inc is None:
        raise HTTPException(404, "Incidencia no encontrada")
    return inc


def _avance_o_404(db: Session, incidencia_id: int, avance_id: int) -> models.AvanceIncidencia:
    av = db.get(models.AvanceIncidencia, avance_id)
    if av is None or av.incidencia_id != incidencia_id:
        raise HTTPException(404, "Avance no encontrado")
    return av


@router.get("/{incidencia_id}/avances", response_model=list[AvanceOut])
def listar(incidencia_id: int, db: Session = Depends(get_db)) -> list[models.AvanceIncidencia]:
    _incidencia_o_404(db, incidencia_id)
    return (
        db.query(models.AvanceIncidencia)
        .filter(models.AvanceIncidencia.incidencia_id == incidencia_id)
        .order_by(models.AvanceIncidencia.fecha.desc(), models.AvanceIncidencia.id.desc())
        .all()
    )


@router.post("/{incidencia_id}/avances", response_model=AvanceOut, status_code=201)
def crear(incidencia_id: int, payload: AvanceCreate, db: Session = Depends(get_db)) -> models.AvanceIncidencia:
    _incidencia_o_404(db, incidencia_id)
    data = payload.model_dump()
    if data.get("fecha") is None:
        data["fecha"] = date.today()
    av = models.AvanceIncidencia(incidencia_id=incidencia_id, **data)
    db.add(av)
    db.commit()
    db.refresh(av)
    return av


@router.patch("/{incidencia_id}/avances/{avance_id}", response_model=AvanceOut)
def actualizar(incidencia_id: int, avance_id: int, payload: AvanceUpdate, db: Session = Depends(get_db)) -> models.AvanceIncidencia:
    av = _avance_o_404(db, incidencia_id, avance_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(av, k, v)
    db.commit()
    db.refresh(av)
    return av


@router.delete("/{incidencia_id}/avances/{avance_id}", status_code=204)
def borrar(incidencia_id: int, avance_id: int, db: Session = Depends(get_db)) -> Response:
    av = _avance_o_404(db, incidencia_id, avance_id)
    db.delete(av)
    db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Register the router in main.py**

En `backend/app/main.py`, tras el bloque del router `analitica` (la última registración), añadir:
```python
from app.routers import avances
app.include_router(avances.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_avances.py -q`
Expected: PASS (todos verde).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/avances.py backend/app/main.py backend/tests/test_avances.py
git commit -m "feat: endpoints bitacora /api/incidencias/{id}/avances (GET/POST/PATCH/DELETE)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 3: `avances` en el expediente (`GET /api/incidencias/{id}`)

**Files:**
- Modify: `backend/app/schemas.py` (`IncidenciaFicha`)
- Modify: `backend/app/routers/incidencias.py` (función `ficha`)
- Test: `backend/tests/test_avances.py`

- [ ] **Step 1: Write the failing test**

Añade a `backend/tests/test_avances.py`:

```python
def test_expediente_incluye_avances(client):
    inc = _seed_incidencia(client)
    client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "uno", "fecha": "2026-06-02"})
    client.post(f"/api/incidencias/{inc['id']}/avances", json={"texto": "dos", "fecha": "2026-06-04"})
    r = client.get(f"/api/incidencias/{inc['id']}")
    assert r.status_code == 200, r.text
    avances = r.json()["avances"]
    assert [a["texto"] for a in avances] == ["dos", "uno"]  # orden desc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_avances.py::test_expediente_incluye_avances -q`
Expected: FAIL (`KeyError: 'avances'`).

- [ ] **Step 3: Add the field to IncidenciaFicha**

En `backend/app/schemas.py`, en `class IncidenciaFicha`, añade al final de la clase:
```python
    avances: list[AvanceOut] = []
```
(`AvanceOut` ya está definido antes de `IncidenciaFicha` por la Task 1.)

- [ ] **Step 4: Populate it in the ficha endpoint**

En `backend/app/routers/incidencias.py`:
1. Añade `AvanceOut` al import de schemas (junto a los otros: `from app.schemas import (... AvanceOut ...)`).
2. En la función `ficha`, tras construir `movimientos` (antes del `return IncidenciaFicha(...)`), añade:
```python
    avances = (
        db.query(models.AvanceIncidencia)
        .filter(models.AvanceIncidencia.incidencia_id == incidencia_id)
        .order_by(models.AvanceIncidencia.fecha.desc(), models.AvanceIncidencia.id.desc())
        .all()
    )
```
3. En el `return IncidenciaFicha(...)`, añade el argumento:
```python
        avances=[AvanceOut.model_validate(a) for a in avances],
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_avances.py -q`
Expected: PASS (todos verde).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/incidencias.py backend/tests/test_avances.py
git commit -m "feat: avances en el expediente de incidencia (IncidenciaFicha.avances)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 4: Suite completa + smoke en vivo (tabla nueva auto-creada)

**Files:** ninguno (verificación).

- [ ] **Step 1: Run the full suite**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest -q`
Expected: PASS, todos verde (142 previos + los nuevos de Tasks 1-3).

- [ ] **Step 2: Smoke en vivo**

Arranca el backend (`create_all` crea la tabla `avances_incidencia` al importar `main`):
```
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```
En otra shell (sustituye `1` por un id de incidencia existente, p.ej. de `GET /api/incidencias`):
```
curl -s -X POST "http://127.0.0.1:8020/api/incidencias/1/avances" -H "Content-Type: application/json" -d "{\"texto\":\"smoke avance\",\"tipo\":\"report\"}"
curl -s "http://127.0.0.1:8020/api/incidencias/1/avances"
curl -s "http://127.0.0.1:8020/api/incidencias/1" 
```
Expected: el POST devuelve 201 con `fecha` = hoy; el GET lista el avance; el expediente incluye la clave `avances` con la entrada.

- [ ] **Step 3: Parar el backend**

`netstat -ano | findstr :8020` → `taskkill /PID <pid> /T /F`.

- [ ] **Step 4: Commit (solo si hubo ajustes)**

Si todo verde sin cambios, no hay commit.

---

## Task 5: Prompt Lovable 14 (bitácora en lista + ficha)

**Files:**
- Create: `docs/lovable/14_bitacora_avances.md`
- Modify: `docs/lovable/README.md`

- [ ] **Step 1: Write the Lovable prompt**

Crear `docs/lovable/14_bitacora_avances.md` con:

```markdown
# Prompt 14 — Bitácora de avances de incidencia (popup desde la lista + ficha)

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()`, tipos en `@/lib/types`, paleta lila
`#9e007e`). NO cambies nombres de campo del backend.

## 1. Tipos en `src/lib/types.ts`
- `AvanceTipo = "avance" | "report" | "llamada" | "visita" | "diagnostico" | "otro"`.
- `interface Avance { id: number; incidencia_id: number; fecha: string; autor: string | null; tipo: AvanceTipo; texto: string; }`
- Añade `avances: Avance[]` a `IncidenciaFicha`.

## 2. Componente `src/components/BitacoraIncidencia.tsx`
Props: `{ incidenciaId: number }`. 
- Carga `GET /api/incidencias/{incidenciaId}/avances` (orden ya viene desc = más reciente primero).
- **Timeline**: cada entrada muestra fecha, badge de `tipo`, `autor` (si hay) y `texto`. Botones por
  entrada: editar y borrar.
- **Formulario "Añadir avance"**: selector `tipo` (6 opciones, default avance), `fecha` (date, default hoy),
  `autor` (texto), `texto` (textarea, obligatorio). Submit → `POST /api/incidencias/{id}/avances`.
- **Editar**: `PATCH /api/incidencias/{id}/avances/{avanceId}` (texto/tipo/fecha/autor). **Borrar**:
  `DELETE /api/incidencias/{id}/avances/{avanceId}` (204). Refresca la lista tras cada acción.
- Estados de carga y vacío ("Sin avances todavía").

## 3. Lista de incidencias (`src/routes/incidencias.tsx`)
- El click en una fila abre un **modal/popup** (Dialog de shadcn) que muestra `<BitacoraIncidencia
  incidenciaId={inc.id} />` con la cabecera de la incidencia (código, título, estado).
- Dentro del modal, un botón **"Abrir expediente"** navega a `/incidencias/$id` (la ficha completa).
- (Si prefieres no perder la navegación directa, deja también un acceso a la ficha; pero el click
  principal de la fila abre el popup de bitácora.)

## 4. Ficha de incidencia (`src/routes/incidencias.$id.tsx`)
- Embebe `<BitacoraIncidencia incidenciaId={id} />` en una sección "Bitácora / Avances" del expediente
  (puede usar `ficha.avances` para el primer render y/o recargar vía el endpoint).

Usa EXACTAMENTE los nombres de campo de arriba; no inventes endpoints.
```

- [ ] **Step 2: Update README índice**

En `docs/lovable/README.md`, añade a la lista de prompts:
```markdown
- `14_bitacora_avances.md` — **Bitácora de avances** por incidencia. Popup desde la lista (`/incidencias`)
  + sección en la ficha. Backend `GET/POST/PATCH/DELETE /api/incidencias/{id}/avances` y `avances[]` en
  el expediente. Entrada = fecha + autor + tipo (avance/report/llamada/visita/diagnostico/otro) + texto.
```

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/14_bitacora_avances.md docs/lovable/README.md
git commit -m "docs: prompt Lovable 14 — bitacora de avances de incidencia"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

- [ ] **Step 4: (Manual, fuera del plan)** Pegar el prompt 14 en Lovable; luego `git pull` del submódulo
  `frontend`, `bun install`, `bun x tsc --noEmit`, validación de contrato y smoke visual.

---

## Self-review (cobertura del spec)

- **Entidad nueva con fecha/autor/tipo/texto:** Task 1. ✅
- **Crear/listar (desc)/editar (PATCH)/borrar:** Task 2. ✅
- **fecha default hoy, texto obligatorio (422), 404s (incidencia/avance de otra):** Task 2. ✅
- **`avances` en el expediente:** Task 3. ✅
- **Tabla nueva sin migración de columnas (create_all):** Task 4 (smoke confirma). ✅
- **No toca diagnostico/resolucion/notas ni transiciones:** ninguna tarea los modifica. ✅
- **Popup desde lista + componente en ficha:** Task 5 (prompt Lovable). ✅
- **Fuera de alcance (adjuntos, transición por avance, notificaciones):** no implementado. ✅

Consistencia de tipos: `AvanceCreate/Update/Out`, `_TIPO_AVANCE`, `models.AvanceIncidencia`,
endpoints `/api/incidencias/{incidencia_id}/avances[/{avance_id}]`, `IncidenciaFicha.avances` — usados
igual en Tasks 1-3 y el prompt 5.
```
