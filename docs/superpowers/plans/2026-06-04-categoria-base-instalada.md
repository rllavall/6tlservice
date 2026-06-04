# Categoría de familia en la base instalada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clasificar la base instalada por familia (ATE, YAV Module, fastATE Module, Test Fixture, Test Handler, Otro) mediante un campo `categoria` en el catálogo, expuesto en equipos/componentes y filtrable en la lista de equipos.

**Architecture:** `categoria` vive en `Producto` (fuente única). `Equipo` y `Componente` exponen una propiedad de solo lectura `categoria` que lee `self.producto.categoria` (ambos ya tienen la relación `producto`). El filtro `GET /api/equipos?categoria=` usa una subconsulta de productos. El frontend (Lovable, prompt 15) añade columna + filtro.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2 (Mapped), Pydantic v2, pytest.

**Convenciones:** tests en `backend/tests/` (fixtures `db_session`/`client` en `conftest.py`); ejecutar desde `backend/` con `.venv\Scripts\python.exe -m pytest -q`. Schemas en `app/schemas.py` (`_ORM` = `from_attributes=True`). Commit por tarea, mensaje en español terminando con la línea Co-Authored-By habitual. La migración idempotente vive en `app/migrations.py` (`_COLUMNAS_NUEVAS`).

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---------|-----------------|--------|
| `backend/app/models.py` | + columna `Producto.categoria`; + propiedad `categoria` en `Equipo` y `Componente`. | Modificar |
| `backend/app/migrations.py` | + `productos.categoria` en `_COLUMNAS_NUEVAS`. | Modificar |
| `backend/app/schemas.py` | + `categoria` en `ProductoCreate`/`ProductoOut`/`EquipoOut`/`ComponenteOut` + alias `_CATEGORIA`. | Modificar |
| `backend/app/routers/equipos.py` | + filtro `?categoria=` en `listar`. | Modificar |
| `backend/tests/test_productos.py` | categoría en producto + migración. | Modificar |
| `backend/tests/test_equipos.py` | propiedad `categoria` en equipo + filtro. | Modificar |
| `backend/tests/test_componentes.py` | propiedad `categoria` en componente. | Modificar |
| `backend/tests/test_migrations.py` | columna `categoria` añadida. | Modificar |
| `docs/lovable/15_categoria_base_instalada.md` | Prompt Lovable. | Crear |
| `docs/lovable/README.md` | Índice. | Modificar |

---

## Task 1: `Producto.categoria` + migración + schemas de producto

**Files:**
- Modify: `backend/app/models.py` (`class Producto`, tras `meses_garantia_default`)
- Modify: `backend/app/migrations.py` (entry `"productos"` de `_COLUMNAS_NUEVAS`)
- Modify: `backend/app/schemas.py` (`ProductoCreate`, `ProductoOut`)
- Test: `backend/tests/test_productos.py`, `backend/tests/test_migrations.py`

- [ ] **Step 1: Write the failing tests**

En `backend/tests/test_productos.py`, añade:

```python
def test_producto_acepta_y_devuelve_categoria(client):
    r = client.post("/api/productos", json={
        "part_number": "FASTATE-3000", "tipo": "equipo", "descripcion": "Sistema ATE",
        "categoria": "ate",
    })
    assert r.status_code == 201, r.text
    assert r.json()["categoria"] == "ate"


def test_producto_categoria_opcional(client):
    r = client.post("/api/productos", json={"part_number": "PN-NC", "tipo": "equipo", "descripcion": "x"})
    assert r.status_code == 201, r.text
    assert r.json()["categoria"] is None


def test_producto_categoria_invalida_422(client):
    r = client.post("/api/productos", json={
        "part_number": "PN-BAD", "tipo": "equipo", "descripcion": "x", "categoria": "no_existe",
    })
    assert r.status_code == 422
```

En `backend/tests/test_migrations.py`, añade (reusa `create_engine`, `text`, `StaticPool`, `add_missing_columns`, `_columnas` ya importados):

```python
def test_agrega_columna_categoria_a_productos():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with eng.begin() as c:
        c.exec_driver_sql("CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT)")
    add_missing_columns(eng)
    assert "categoria" in _columnas(eng, "productos")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_productos.py tests/test_migrations.py -q`
Expected: FAIL (categoria desconocida / columna ausente).

- [ ] **Step 3: Add the column to the model**

En `backend/app/models.py`, en `class Producto`, tras la línea `meses_garantia_default: ...`:
```python
    categoria: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

- [ ] **Step 4: Add the migration entry**

En `backend/app/migrations.py`, cambia la entrada `"productos"` de `_COLUMNAS_NUEVAS` (actualmente
`"productos": {"meses_garantia_default": "INTEGER DEFAULT 24"}`) por:
```python
    "productos": {"meses_garantia_default": "INTEGER DEFAULT 24", "categoria": "TEXT"},
```

- [ ] **Step 5: Add the schemas**

En `backend/app/schemas.py`, justo ANTES de `class ProductoCreate`, añade el alias:
```python
_CATEGORIA = Literal["ate", "yav_module", "fastate_module", "test_fixture", "test_handler", "otro"]
```
En `ProductoCreate`, añade el campo:
```python
    categoria: Optional[_CATEGORIA] = None
```
En `ProductoOut`, añade:
```python
    categoria: Optional[str] = None
```
(`Literal` y `Optional` ya están importados en schemas.py. El PUT de productos reutiliza `ProductoCreate`, así que la categoría también será editable.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_productos.py tests/test_migrations.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/migrations.py backend/app/schemas.py backend/tests/test_productos.py backend/tests/test_migrations.py
git commit -m "feat: Producto.categoria (familia) + migracion + schema"
```
(Mensaje termina con la línea `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.)

---

## Task 2: Propiedad `categoria` en Equipo y Componente + en sus *Out*

**Files:**
- Modify: `backend/app/models.py` (`class Equipo`, `class Componente`)
- Modify: `backend/app/schemas.py` (`EquipoOut`, `ComponenteOut`)
- Test: `backend/tests/test_equipos.py`, `backend/tests/test_componentes.py`

- [ ] **Step 1: Write the failing tests**

En `backend/tests/test_equipos.py`, añade:

```python
def test_equipo_expone_categoria_del_producto(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-CATEQ", "tipo": "equipo", "descripcion": "d", "categoria": "test_handler",
    }).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-CAT", "producto_id": p["id"]}).json()
    r = client.get(f"/api/equipos/{eq['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["equipo"]["categoria"] == "test_handler"


def test_equipo_categoria_none_si_producto_sin_categoria(client):
    p = client.post("/api/productos", json={"part_number": "PN-NOCAT", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-NOCAT", "producto_id": p["id"]})
    assert eq.json()["categoria"] is None
```

En `backend/tests/test_componentes.py`, añade:

```python
def test_componente_expone_categoria_del_producto(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-YAV", "tipo": "componente", "descripcion": "Modulo YAV", "categoria": "yav_module",
    }).json()
    r = client.post("/api/componentes", json={"numero_serie": "YAV-1", "producto_id": p["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["categoria"] == "yav_module"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_equipos.py tests/test_componentes.py -q`
Expected: FAIL (`categoria` no presente / KeyError).

- [ ] **Step 3: Add the property to Equipo**

En `backend/app/models.py`, `class Equipo`, al final de la clase (tras la propiedad `estado_garantia`):
```python
    @property
    def categoria(self):
        return self.producto.categoria if self.producto is not None else None
```

- [ ] **Step 4: Add the property to Componente**

En `backend/app/models.py`, `class Componente`, al final de la clase (tras la relación `equipo`):
```python
    @property
    def categoria(self):
        return self.producto.categoria if self.producto is not None else None
```

- [ ] **Step 5: Add the field to the Out schemas**

En `backend/app/schemas.py`:
- En `EquipoOut`, añade:
```python
    categoria: Optional[str] = None
```
- En `ComponenteOut`, añade:
```python
    categoria: Optional[str] = None
```
(`EquipoOut`/`ComponenteOut` heredan `_ORM` con `from_attributes=True`, así que leen la propiedad
`categoria` del modelo automáticamente.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_equipos.py tests/test_componentes.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/tests/test_equipos.py backend/tests/test_componentes.py
git commit -m "feat: equipo/componente exponen categoria del producto"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 3: Filtro `GET /api/equipos?categoria=`

**Files:**
- Modify: `backend/app/routers/equipos.py` (`listar`)
- Test: `backend/tests/test_equipos.py`

- [ ] **Step 1: Write the failing test**

En `backend/tests/test_equipos.py`, añade:

```python
def test_filtro_equipos_por_categoria(client):
    p_ate = client.post("/api/productos", json={"part_number": "PN-A1", "tipo": "equipo", "descripcion": "d", "categoria": "ate"}).json()
    p_fix = client.post("/api/productos", json={"part_number": "PN-F1", "tipo": "equipo", "descripcion": "d", "categoria": "test_fixture"}).json()
    client.post("/api/equipos", json={"numero_serie": "E-ATE-1", "producto_id": p_ate["id"]})
    client.post("/api/equipos", json={"numero_serie": "E-FIX-1", "producto_id": p_fix["id"]})
    r = client.get("/api/equipos?categoria=ate")
    assert r.status_code == 200
    assert [e["numero_serie"] for e in r.json()] == ["E-ATE-1"]
    # categoria sin equipos -> vacio
    assert client.get("/api/equipos?categoria=test_handler").json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_equipos.py::test_filtro_equipos_por_categoria -q`
Expected: FAIL (el filtro no existe; devuelve ambos equipos).

- [ ] **Step 3: Add the filter**

En `backend/app/routers/equipos.py`, función `listar`:
1. Añade el parámetro a la firma (junto a los otros `Optional`):
```python
    categoria: Optional[str] = None,
```
2. En el cuerpo, junto a los demás filtros (antes del `return q.order_by(...)`), añade — usa una
   SUBCONSULTA de productos para evitar choques con el join de `part_number` ya existente:
```python
    if categoria is not None:
        sub = db.query(models.Producto.id).filter(models.Producto.categoria == categoria)
        q = q.filter(models.Equipo.producto_id.in_(sub))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_equipos.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/equipos.py backend/tests/test_equipos.py
git commit -m "feat: filtro GET /api/equipos?categoria="
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 4: Suite completa + smoke en vivo

**Files:** ninguno (verificación).

- [ ] **Step 1: Run the full suite**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest -q`
Expected: PASS, todos verde (153 previos + los nuevos).

- [ ] **Step 2: Smoke en vivo**

Arranca el backend (la migración añade `productos.categoria` al importar `main`):
```
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```
En otra shell:
```
curl -s -X POST "http://127.0.0.1:8020/api/productos" -H "Content-Type: application/json" -d "{\"part_number\":\"SMOKE-ATE\",\"tipo\":\"equipo\",\"descripcion\":\"smoke\",\"categoria\":\"ate\"}"
curl -s "http://127.0.0.1:8020/api/equipos?categoria=ate"
```
Expected: el POST devuelve 201 con `categoria":"ate"`; el filtro responde 200. (Los productos demo
existentes tienen `categoria=null` hasta clasificarlos.) Borra el producto de smoke por id si quieres
dejar la BD limpia: `curl -s -X DELETE "http://127.0.0.1:8020/api/productos/<id>"`.

- [ ] **Step 3: Parar el backend**

`netstat -ano | findstr :8020` → `taskkill /PID <pid> /T /F`.

- [ ] **Step 4: Commit (solo si hubo ajustes)**

Si todo verde sin cambios, no hay commit.

---

## Task 5: Prompt Lovable 15 (categoría en base instalada)

**Files:**
- Create: `docs/lovable/15_categoria_base_instalada.md`
- Modify: `docs/lovable/README.md`

- [ ] **Step 1: Write the Lovable prompt**

Crear `docs/lovable/15_categoria_base_instalada.md` con:

```markdown
# Prompt 15 — Categoría de familia en la base instalada

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()`, tipos en `@/lib/types`, paleta lila
`#9e007e`, shadcn). NO cambies nombres de campo del backend.

## 1. Tipos en `src/lib/types.ts`
```ts
export type CategoriaProducto =
  | "ate" | "yav_module" | "fastate_module" | "test_fixture" | "test_handler" | "otro";

export const CATEGORIA_LABEL: Record<CategoriaProducto, string> = {
  ate: "ATE",
  yav_module: "YAV Module",
  fastate_module: "fastATE Module",
  test_fixture: "Test Fixture",
  test_handler: "Test Handler",
  otro: "Otro",
};
// Añade `categoria: CategoriaProducto | null` a Producto, Equipo/EquipoOut y Componente/ComponenteOut.
```

## 2. Base instalada (`src/routes/index.tsx` / tabla de equipos)
- Nueva **columna "Categoría"**: badge con `CATEGORIA_LABEL[equipo.categoria]` (o "—" si es null).
- Nuevo **filtro por categoría**: select ("Todas" + las 6) junto al buscador por nº de serie. Llama
  `GET /api/equipos?categoria=<slug>` (combinable con el filtro de serie ya existente).

## 3. Alta/edición de producto (catálogo, `src/routes/catalogo.tsx` o el form de producto)
- Selector `categoria` ("Sin categoría" + las 6). Envía/lee `categoria` (slug) en POST/PUT de producto.

## 4. Ficha de equipo (`src/routes/equipos.$id.tsx`)
- En la lista de componentes (configuración), muestra un badge con la `categoria` de cada componente
  (`CATEGORIA_LABEL[componente.categoria]`), p.ej. un ATE mostrará sus YAV Modules etiquetados.

Usa EXACTAMENTE los slugs de arriba; no inventes endpoints.
```

- [ ] **Step 2: Update README índice**

En `docs/lovable/README.md`, en la sección "Mejoras sueltas", añade:
```markdown
| 15 | `15_categoria_base_instalada.md` | **Categoría de familia** en la base instalada: columna + filtro por categoría (ATE/YAV Module/fastATE Module/Test Fixture/Test Handler/Otro). Backend `Producto.categoria`, `categoria` en `EquipoOut`/`ComponenteOut`, filtro `GET /api/equipos?categoria=`. Selector en el alta/edición de producto + badge por componente en la ficha. |
```

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/15_categoria_base_instalada.md docs/lovable/README.md
git commit -m "docs: prompt Lovable 15 — categoria de familia en la base instalada"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

- [ ] **Step 4: (Manual, fuera del plan)** Pegar el prompt 15 en Lovable; luego `git pull` del submódulo
  `frontend`, `bun install`, `bun x tsc --noEmit`, validación de contrato y smoke visual.

---

## Self-review (cobertura del spec)

- **`categoria` en Producto (lista cerrada + Otro, nullable):** Task 1. ✅
- **Migración idempotente añade `productos.categoria`:** Task 1. ✅
- **`ProductoCreate/Out` (+ PUT reusa Create) ganan categoria:** Task 1. ✅
- **Propiedad `categoria` derivada en Equipo y Componente, en sus *Out*:** Task 2. ✅
- **Filtro `GET /api/equipos?categoria=` combinable:** Task 3. ✅
- **Frontend: columna+filtro base instalada, selector en producto, badge por componente:** Task 5 (prompt). ✅
- **Fuera de alcance (categoría por unidad, agrupar/contar, analítica/mapa, reglas de montaje):** no implementado. ✅

Consistencia de tipos: `Producto.categoria`, propiedad `categoria` en Equipo/Componente, `_CATEGORIA`
(slugs `ate|yav_module|fastate_module|test_fixture|test_handler|otro`), `?categoria=` — usados igual en
Tasks 1-3 y el prompt 5.
```
