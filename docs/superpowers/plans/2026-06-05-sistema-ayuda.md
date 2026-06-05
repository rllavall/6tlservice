# Sistema de ayuda contextual — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Catálogo de ayuda editable en el backend (clave → texto) servido por una API CRUD protegida + sembrado inicial, para que el frontend pinte tooltips contextuales ("?") sin re-desplegar.

**Architecture:** Tabla nueva `ayuda` (modelo `AyudaTopico`), schemas `AyudaOut`/`AyudaUpsert`, router CRUD `ayuda.py` (GET lista/uno, PUT upsert por clave, DELETE) registrado protegido, y un seeder `ayuda_seed.py` (`CATALOGO_INICIAL` + `sembrar_ayuda` insert-if-missing) cableado al arranque. Aditivo: la tabla la crea `create_all`; las ediciones quedan auditadas por el listener existente. Frontend = prompt Lovable 20 (componente `<HelpTip clave=...>`).

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2 (`Mapped`), Pydantic v2, pytest.

**Convenciones:** tests en `backend/tests/`; ejecutar desde `backend/` con `.venv\Scripts\python.exe -m pytest -q`. Commit por tarea, mensaje en español terminando con `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Baseline actual: **198 tests verde**.

**Contexto del código (ya verificado):**
- `app/models.py`: `Mapped`/`mapped_column`, `from app.db import Base`, imports `Integer, String, ...` ya presentes; `Optional` importado.
- `app/schemas.py`: `class _ORM(BaseModel): model_config = ConfigDict(from_attributes=True)`; importa `from typing import Literal, Optional` y `from pydantic import BaseModel, ConfigDict, Field, model_validator` (`Field` y `Optional` ya disponibles).
- `app/db.py`: `Base`, `engine`, `SessionLocal`, `get_db`.
- `app/main.py`: `create_all(engine)` → `add_missing_columns(engine)` → `registrar_listeners()`; luego `app`, CORS, los routers internos registrados con `dependencies=[Depends(get_current_user)]` (ya hay `from fastapi import Depends` y `from app.deps import get_current_user`), el router `auth` público, y `GET /api/health`.
- `tests/conftest.py`: `db_session` (SQLite en memoria, `create_all` de TODAS las tablas), `client` (override de `get_db` + `get_current_user` con usuario de prueba → no exige token), `client_sin_auth` (auth real).
- ⚠️ **Antes de correr la suite, parar el backend si está vivo** (`netstat -ano | findstr :8020` → `taskkill /PID <pid> /T /F`): al importar `app.main`, el arranque ejecuta DDL/seed contra `postventa.db` y un proceso uvicorn vivo puede bloquear el fichero.

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---------|-----------------|--------|
| `backend/app/models.py` | + modelo `AyudaTopico`. | Modificar |
| `backend/app/schemas.py` | + `AyudaOut`/`AyudaUpsert`. | Modificar |
| `backend/app/routers/ayuda.py` | CRUD `/api/ayuda`. | Crear |
| `backend/app/ayuda_seed.py` | `CATALOGO_INICIAL` + `sembrar_ayuda`. | Crear |
| `backend/app/main.py` | registrar router protegido + cablear seeder. | Modificar |
| `backend/tests/test_ayuda_model.py` | test del modelo. | Crear |
| `backend/tests/test_ayuda_endpoint.py` | tests CRUD + protección. | Crear |
| `backend/tests/test_ayuda_seed.py` | tests del seeder. | Crear |
| `docs/lovable/20_ayuda_contextual.md` + `README.md` | prompt Lovable. | Crear/Modificar |

---

## Task 1: Modelo `AyudaTopico` + schemas

**Files:**
- Modify: `backend/app/models.py` (clase nueva al final)
- Modify: `backend/app/schemas.py` (schemas nuevos al final)
- Test: `backend/tests/test_ayuda_model.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_ayuda_model.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app import models


def test_crea_topico(db_session):
    t = models.AyudaTopico(clave="equipos.estado", titulo="Estado", texto="Operativo o baja.", pantalla="equipos")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    assert t.id is not None and t.clave == "equipos.estado"


def test_titulo_y_pantalla_opcionales(db_session):
    t = models.AyudaTopico(clave="x.y", texto="solo texto")
    db_session.add(t)
    db_session.commit()
    assert t.titulo is None and t.pantalla is None


def test_clave_unica(db_session):
    db_session.add(models.AyudaTopico(clave="dup", texto="a"))
    db_session.commit()
    db_session.add(models.AyudaTopico(clave="dup", texto="b"))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_ayuda_model.py -q`
Expected: FAIL (`AttributeError: ... 'AyudaTopico'`).

- [ ] **Step 3: Add the model**

AÑADE al FINAL de `backend/app/models.py`:

```python
class AyudaTopico(Base):
    __tablename__ = "ayuda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave: Mapped[str] = mapped_column(String, unique=True, index=True)
    titulo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    texto: Mapped[str] = mapped_column(String)
    pantalla: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

- [ ] **Step 4: Add the schemas**

AÑADE al FINAL de `backend/app/schemas.py`:

```python
# --- Ayuda contextual ---
class AyudaOut(_ORM):
    clave: str
    titulo: Optional[str] = None
    texto: str
    pantalla: Optional[str] = None


class AyudaUpsert(BaseModel):
    titulo: Optional[str] = None
    texto: str = Field(min_length=1)
    pantalla: Optional[str] = None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_ayuda_model.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/tests/test_ayuda_model.py
git commit -m "feat: modelo AyudaTopico + schemas de ayuda"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 2: Router CRUD `/api/ayuda` (protegido)

**Files:**
- Create: `backend/app/routers/ayuda.py`
- Modify: `backend/app/main.py` (registrar router protegido)
- Test: `backend/tests/test_ayuda_endpoint.py`

- [ ] **Step 1: Write the failing tests**

Crear `backend/tests/test_ayuda_endpoint.py`:

```python
def test_put_crea_y_get_uno(client):
    r = client.put("/api/ayuda/test.clave", json={"texto": "hola", "titulo": "T", "pantalla": "p"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["clave"] == "test.clave" and b["texto"] == "hola" and b["titulo"] == "T"
    assert "id" not in b
    g = client.get("/api/ayuda/test.clave")
    assert g.status_code == 200 and g.json()["texto"] == "hola"


def test_put_actualiza_no_duplica(client):
    client.put("/api/ayuda/test.clave", json={"texto": "v1"})
    r = client.put("/api/ayuda/test.clave", json={"texto": "v2"})
    assert r.json()["texto"] == "v2"
    todos = [x for x in client.get("/api/ayuda").json() if x["clave"] == "test.clave"]
    assert len(todos) == 1


def test_put_texto_vacio_422(client):
    assert client.put("/api/ayuda/x.y", json={"texto": ""}).status_code == 422


def test_get_uno_inexistente_404(client):
    assert client.get("/api/ayuda/no.existe").status_code == 404


def test_lista_filtra_por_pantalla(client):
    client.put("/api/ayuda/a.k", json={"texto": "t", "pantalla": "equipos"})
    client.put("/api/ayuda/b.k", json={"texto": "t", "pantalla": "mapa"})
    data = client.get("/api/ayuda", params={"pantalla": "equipos"}).json()
    assert all(x["pantalla"] == "equipos" for x in data)
    assert any(x["clave"] == "a.k" for x in data)


def test_delete(client):
    client.put("/api/ayuda/del.k", json={"texto": "t"})
    assert client.delete("/api/ayuda/del.k").status_code == 204
    assert client.get("/api/ayuda/del.k").status_code == 404
    assert client.delete("/api/ayuda/del.k").status_code == 404


def test_ayuda_protegido_sin_token_401(client_sin_auth):
    assert client_sin_auth.get("/api/ayuda").status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_ayuda_endpoint.py -q`
Expected: FAIL (404, router no registrado).

- [ ] **Step 3: Create the router**

Crear `backend/app/routers/ayuda.py`:

```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import AyudaOut, AyudaUpsert

router = APIRouter(prefix="/api/ayuda", tags=["ayuda"])


def _por_clave(db: Session, clave: str) -> Optional[models.AyudaTopico]:
    return db.query(models.AyudaTopico).filter(models.AyudaTopico.clave == clave).first()


@router.get("", response_model=list[AyudaOut])
def listar(pantalla: Optional[str] = None, db: Session = Depends(get_db)) -> list[models.AyudaTopico]:
    q = db.query(models.AyudaTopico)
    if pantalla is not None:
        q = q.filter(models.AyudaTopico.pantalla == pantalla)
    return q.order_by(models.AyudaTopico.clave).all()


@router.get("/{clave}", response_model=AyudaOut)
def obtener(clave: str, db: Session = Depends(get_db)) -> models.AyudaTopico:
    t = _por_clave(db, clave)
    if t is None:
        raise HTTPException(404, "Tópico de ayuda no encontrado")
    return t


@router.put("/{clave}", response_model=AyudaOut)
def upsert(clave: str, payload: AyudaUpsert, db: Session = Depends(get_db)) -> models.AyudaTopico:
    t = _por_clave(db, clave)
    if t is None:
        t = models.AyudaTopico(clave=clave)
        db.add(t)
    t.titulo = payload.titulo
    t.texto = payload.texto
    t.pantalla = payload.pantalla
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{clave}", status_code=204)
def borrar(clave: str, db: Session = Depends(get_db)) -> None:
    t = _por_clave(db, clave)
    if t is None:
        raise HTTPException(404, "Tópico de ayuda no encontrado")
    db.delete(t)
    db.commit()
```

- [ ] **Step 4: Register the router (protegido)**

En `backend/app/main.py`, junto a los otros routers internos (p.ej. tras el bloque de `auditoria`), añade:

```python
from app.routers import ayuda
app.include_router(ayuda.router, dependencies=[Depends(get_current_user)])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_ayuda_endpoint.py -q`
Expected: PASS (7 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/ayuda.py backend/app/main.py backend/tests/test_ayuda_endpoint.py
git commit -m "feat: router CRUD /api/ayuda (protegido, upsert por clave)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 3: Seeder `ayuda_seed.py` + cableado al arranque

**Files:**
- Create: `backend/app/ayuda_seed.py`
- Modify: `backend/app/main.py` (cablear el seeder)
- Test: `backend/tests/test_ayuda_seed.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_ayuda_seed.py`:

```python
from app import models
from app.ayuda_seed import CATALOGO_INICIAL, sembrar_ayuda


def test_sembrar_inserta_las_que_faltan(db_session):
    n = sembrar_ayuda(db_session)
    assert n == len(CATALOGO_INICIAL) and n > 0
    assert db_session.query(models.AyudaTopico).count() == n


def test_sembrar_es_idempotente(db_session):
    sembrar_ayuda(db_session)
    total = db_session.query(models.AyudaTopico).count()
    assert sembrar_ayuda(db_session) == 0           # segunda vez no inserta nada
    assert db_session.query(models.AyudaTopico).count() == total


def test_sembrar_no_pisa_texto_existente(db_session):
    clave = CATALOGO_INICIAL[0]["clave"]
    db_session.add(models.AyudaTopico(clave=clave, texto="MI TEXTO EDITADO"))
    db_session.commit()
    sembrar_ayuda(db_session)
    t = db_session.query(models.AyudaTopico).filter_by(clave=clave).first()
    assert t.texto == "MI TEXTO EDITADO"            # no se sobrescribe


def test_catalogo_sin_claves_duplicadas():
    claves = [item["clave"] for item in CATALOGO_INICIAL]
    assert len(claves) == len(set(claves))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_ayuda_seed.py -q`
Expected: FAIL (`No module named 'app.ayuda_seed'`).

- [ ] **Step 3: Create the seeder**

Crear `backend/app/ayuda_seed.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models

CATALOGO_INICIAL = [
    {"clave": "equipos.estado", "titulo": "Estado del equipo", "pantalla": "equipos",
     "texto": "Operativo = el equipo está en servicio. Baja = retirado del servicio (reversible desde la ficha)."},
    {"clave": "equipos.categoria", "titulo": "Categoría", "pantalla": "equipos",
     "texto": "Familia del equipo: ATE, YAV Module, FastATE Module, Test Fixture, Test Handler u Otro. Se hereda del producto del catálogo."},
    {"clave": "equipos.version", "titulo": "Versión", "pantalla": "equipos",
     "texto": "Revisión de hardware/firmware de esta unidad concreta."},
    {"clave": "equipos.numero_serie_cliente", "titulo": "Nº de serie del cliente", "pantalla": "equipos",
     "texto": "Número de serie con el que el cliente identifica el equipo (opcional, distinto del nuestro)."},
    {"clave": "garantia.estado", "titulo": "Estado de garantía", "pantalla": "garantia",
     "texto": "Vigente, Por vencer (≤90 días), Vencida o Sin datos. Se calcula desde la fecha de fabricación/entrega y los meses de garantía."},
    {"clave": "garantia.meses", "titulo": "Meses de garantía", "pantalla": "garantia",
     "texto": "Meses de garantía de la unidad. Si está vacío, se hereda del producto (por defecto 24)."},
    {"clave": "incidencias.tipo", "titulo": "Tipo de incidencia", "pantalla": "incidencias",
     "texto": "RMA (devolución/reparación), Soporte de venta (SV), Soporte técnico (ST) o Calibración (CAL). El código de la incidencia lleva ese prefijo."},
    {"clave": "incidencias.prioridad", "titulo": "Prioridad", "pantalla": "incidencias",
     "texto": "Baja, Media o Alta. Orienta el orden de atención."},
    {"clave": "incidencias.estado", "titulo": "Estado", "pantalla": "incidencias",
     "texto": "Flujo: Abierta → Diagnóstico → En reparación → Resuelta → Cerrada. Se puede reabrir una resuelta o cerrada."},
    {"clave": "incidencias.en_garantia", "titulo": "En garantía", "pantalla": "incidencias",
     "texto": "Indica si la incidencia está cubierta por garantía. En RMA se autodetecta del equipo al crearla (editable)."},
    {"clave": "incidencias.avances", "titulo": "Bitácora de avances", "pantalla": "incidencias",
     "texto": "Registro cronológico de la incidencia: reportes, llamadas, visitas, diagnósticos y avances."},
    {"clave": "mapa.pin", "titulo": "Pines del mapa", "pantalla": "mapa",
     "texto": "Cada pin es una ubicación con coordenadas y al menos un equipo operativo; agrupa los equipos de esa ubicación."},
    {"clave": "mapa.incluir_baja", "titulo": "Incluir bajas", "pantalla": "mapa",
     "texto": "Si se activa, también se muestran los equipos dados de baja (no solo los operativos)."},
    {"clave": "analitica.mttr", "titulo": "MTTR", "pantalla": "analitica",
     "texto": "Tiempo medio de reparación: de la apertura a la resolución de las incidencias."},
    {"clave": "resumen.tiempo_medio_cierre", "titulo": "Tiempo medio de cierre", "pantalla": "resumen",
     "texto": "Tiempo medio de cierre en los últimos 30 días: de la apertura al cierre de la incidencia."},
    {"clave": "auditoria.historial", "titulo": "Historial de cambios", "pantalla": "auditoria",
     "texto": "Quién creó, editó o borró cada dato de esta ficha y cuándo."},
]


def sembrar_ayuda(db: Session) -> int:
    """Inserta las claves del catálogo que falten (no pisa las existentes). Devuelve cuántas insertó."""
    existentes = {clave for (clave,) in db.query(models.AyudaTopico.clave).all()}
    nuevos = 0
    for item in CATALOGO_INICIAL:
        if item["clave"] in existentes:
            continue
        db.add(models.AyudaTopico(
            clave=item["clave"], titulo=item.get("titulo"),
            texto=item["texto"], pantalla=item.get("pantalla"),
        ))
        nuevos += 1
    if nuevos:
        db.commit()
    return nuevos
```

- [ ] **Step 4: Wire the seeder at startup**

En `backend/app/main.py`, tras `registrar_listeners()` (y antes de crear `app`, o justo después; debe ser a nivel de módulo), añade:

```python
from app.db import SessionLocal
from app.ayuda_seed import sembrar_ayuda

with SessionLocal() as _db:
    sembrar_ayuda(_db)
```

(`SessionLocal` quizá no esté importado aún en main.py; el import de arriba lo cubre. Si ya estuviera importado junto a `Base, engine`, no lo dupliques.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_ayuda_seed.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/ayuda_seed.py backend/app/main.py backend/tests/test_ayuda_seed.py
git commit -m "feat: seeder de ayuda (catalogo inicial insert-if-missing) cableado al arranque"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 4: Suite completa + smoke en vivo

**Files:** ninguno (verificación).

- [ ] **Step 1: Parar el backend si está vivo**

`netstat -ano | findstr :8020` → si hay PID escuchando, `taskkill /PID <pid> /T /F`.

- [ ] **Step 2: Run the full suite**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest -q -p no:warnings`
Expected: PASS, todo verde (198 previos + ~14 nuevos).

- [ ] **Step 3: Smoke en vivo (el arranque siembra el catálogo)**

Arranca el backend:
```
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```
En otra shell, con un token de `admin` (login):
```
curl -s -X POST http://127.0.0.1:8020/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"<la-tuya>\"}"
```
Toma el `token` y:
```
curl -s "http://127.0.0.1:8020/api/ayuda" -H "Authorization: Bearer <token>"
curl -s -X PUT "http://127.0.0.1:8020/api/ayuda/equipos.estado" -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d "{\"texto\":\"Texto editado de prueba\",\"titulo\":\"Estado\",\"pantalla\":\"equipos\"}"
curl -s "http://127.0.0.1:8020/api/ayuda/equipos.estado" -H "Authorization: Bearer <token>"
```
Expected: el GET lista ~16 tópicos sembrados; el PUT actualiza `equipos.estado` y el GET refleja el texto editado. Sin token → `401`.

- [ ] **Step 4: Parar el backend**

`netstat -ano | findstr :8020` → `taskkill /PID <pid> /T /F`.

- [ ] **Step 5: Commit (solo si hubo ajustes)**

Si todo verde sin cambios, no hay commit.

---

## Task 5: Prompt Lovable 20 (HelpTip contextual)

**Files:**
- Create: `docs/lovable/20_ayuda_contextual.md`
- Modify: `docs/lovable/README.md`

- [ ] **Step 1: Write the Lovable prompt**

Crear `docs/lovable/20_ayuda_contextual.md`:

```markdown
# Prompt 20 — Ayuda contextual (tooltips "?")

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()` que ya inyecta el Bearer token, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`).
NO cambies nombres de campo.

## 1. Tipo en `src/lib/types.ts`
- `interface AyudaTopico { clave:string; titulo:string|null; texto:string; pantalla:string|null }`

## 2. Carga del catálogo (una vez)
- Al entrar en la app autenticada, llama `GET /api/ayuda` y guarda un mapa `clave → AyudaTopico`
  en un contexto/store (p.ej. `AyudaProvider` con React Context, o un hook `useAyuda()`).
  Con recargar la página basta; no hace falta invalidación fina.

## 3. Componente `<HelpTip clave="...">`
- Pinta un icono **"?"** pequeño (botón con `aria-label`, icono `HelpCircle` de lucide) junto a una
  etiqueta. Al hover/click muestra un Tooltip/Popover de shadcn con el `titulo` (en negrita, si existe)
  y el `texto` del tópico cuya `clave` coincide.
- Si la `clave` no está en el catálogo, **no pinta nada** (y `console.warn` en desarrollo).

## 4. Colocación (usa EXACTAMENTE estas claves, ya sembradas en el backend)
- Base instalada / ficha de equipo: `equipos.estado`, `equipos.categoria`, `equipos.version`,
  `equipos.numero_serie_cliente`, `garantia.estado`, `garantia.meses`.
- Incidencias (lista/ficha/alta): `incidencias.tipo`, `incidencias.prioridad`, `incidencias.estado`,
  `incidencias.en_garantia`, `incidencias.avances`.
- Mapa: `mapa.pin`, `mapa.incluir_baja`.
- Analítica / cabecera KPIs: `analitica.mttr`, `resumen.tiempo_medio_cierre`.
- Sección de historial de cambios (auditoría) de la ficha: `auditoria.historial`.

Coloca el `<HelpTip clave="...">` junto a la etiqueta del campo/sección correspondiente. No cambies la
lógica existente; solo añade el icono de ayuda. No inventes claves ni endpoints.
```

- [ ] **Step 2: Update README índice**

En `docs/lovable/README.md`, añade (en la sección que corresponda):
```markdown
| 20 | `20_ayuda_contextual.md` | **Ayuda contextual**: componente `<HelpTip clave=...>` (tooltip "?") que carga el catálogo `GET /api/ayuda` y muestra el texto por clave, colocado junto a campos/secciones clave. Backend: `GET/PUT/DELETE /api/ayuda` (catálogo editable, sembrado). |
```

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/20_ayuda_contextual.md docs/lovable/README.md
git commit -m "docs: prompt Lovable 20 — ayuda contextual"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

- [ ] **Step 4: (Manual, fuera del plan)** Pegar el prompt 20 en Lovable; `git pull` del submódulo,
  `bun install`, `bun x tsc --noEmit`, smoke.

---

## Self-review (cobertura del spec)

- **Modelo `AyudaTopico` (clave única + titulo/pantalla opcionales):** Task 1. ✅
- **Schemas `AyudaOut` (sin id) / `AyudaUpsert` (texto min_length=1):** Task 1. ✅
- **`GET /api/ayuda?pantalla=` orden por clave:** Task 2. ✅
- **`GET /api/ayuda/{clave}` 404:** Task 2. ✅
- **`PUT /api/ayuda/{clave}` upsert por clave (crea/actualiza, no duplica), 422 texto vacío:** Task 2. ✅
- **`DELETE /api/ayuda/{clave}` 204/404:** Task 2. ✅
- **Router protegido (401 sin token):** Task 2 (`client_sin_auth`). ✅
- **Seeder `CATALOGO_INICIAL` + `sembrar_ayuda` insert-if-missing, idempotente, no pisa existentes:** Task 3. ✅
- **Seeder cableado al arranque tras create_all/migrations/listeners:** Task 3. ✅
- **Ediciones auditadas (gratis por el listener):** no requiere código nuevo; se verifica de hecho en el smoke. ✅
- **Frontend HelpTip + carga única + claves sembradas:** Task 5 (prompt). ✅
- **Fuera de alcance (pantalla de edición, roles, versionado, i18n):** no implementado. ✅

Consistencia de tipos: `AyudaTopico` (modelo, tabla `ayuda`), `AyudaOut`/`AyudaUpsert` (schemas),
`ayuda_seed.CATALOGO_INICIAL`/`sembrar_ayuda`, router `/api/ayuda` con `clave` como path param — usados
igual en Tasks 1-3 y el prompt 5. Las 16 claves del catálogo coinciden entre el seeder (Task 3) y la
colocación del prompt (Task 5).
```
