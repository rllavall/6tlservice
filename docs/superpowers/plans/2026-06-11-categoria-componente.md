# Categoría de componente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir una categoría funcional de componente (`Instrumento` / `Mass Interconnect` / `Wiring` / `Accesories`) al catálogo de productos, heredada por cada componente, con validación, exposición en API, filtros de lista y un script de auto-clasificación de los productos existentes.

**Architecture:** El dato vive en `Producto` (catálogo) como columna nullable `categoria_componente`. El `Componente` la **hereda** vía propiedad de solo lectura, exactamente como ya hace con `categoria`. Se valida con un `Literal` en `schemas.py`, se expone en `ProductoOut`/`ComponenteOut`, y se filtra en los listados de `/api/productos` y `/api/componentes` por subconsulta sobre `Producto.id`. La migración idempotente de `app/migrations.py` añade la columna a la BD persistente. Un script throwaway clasifica los 119 productos por reglas.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (Mapped/mapped_column), SQLite, Pydantic v2, pytest. Backend en `C:\Users\rllavall\6TL Postventa\backend`, ejecutado con `.venv\Scripts\python.exe`. Todos los tests usan el fixture `client` (in-memory, override de auth) de `tests/conftest.py`.

**Convención de ejecución de tests (Windows / PowerShell):**
Ejecutar SIEMPRE desde `backend/`. El seeder de ayuda toca `postventa.db` al importar, así que **parar uvicorn antes de correr tests** si el server de dev está vivo.
```
cd "C:\Users\rllavall\6TL Postventa\backend"
.venv\Scripts\python.exe -m pytest -q
```

---

## File Structure

- **Modify** `backend/app/models.py` — añade columna `categoria_componente` a `Producto` (~línea 65) y propiedad heredada en `Componente` (~línea 127).
- **Modify** `backend/app/schemas.py` — constante `_CATEGORIA_COMPONENTE` (junto a `_CATEGORIA`, línea 65), campo en `ProductoCreate`, en `ProductoOut`, en `ComponenteOut`.
- **Modify** `backend/app/migrations.py` — entrada `categoria_componente: "TEXT"` en el dict de `productos`.
- **Modify** `backend/app/routers/productos.py` — filtro `categoria_componente` en `listar`.
- **Modify** `backend/app/routers/componentes.py` — filtro `categoria_componente` en `listar`.
- **Modify** `backend/tests/test_migrations.py` — test de la nueva columna.
- **Modify** `backend/tests/test_productos.py` — tests de validación + filtro.
- **Modify** `backend/tests/test_componentes.py` — tests de herencia + filtro.
- **Create** `backend/_clasificar_categoria_componente.py` — script throwaway de auto-clasificación (gitignored por `_*.py`).

Slugs y etiquetas:

| slug                | etiqueta visible    |
|---------------------|---------------------|
| `instrumento`       | Instrumento         |
| `mass_interconnect` | Mass Interconnect   |
| `wiring`            | Wiring              |
| `accesorios`        | Accesories          |

---

## Task 1: Migración — columna `categoria_componente` en `productos`

**Files:**
- Modify: `backend/app/migrations.py:18-19`
- Test: `backend/tests/test_migrations.py`

- [ ] **Step 1: Write the failing test**

Añadir al final de `backend/tests/test_migrations.py`:

```python
def test_agrega_categoria_componente_a_productos():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with eng.begin() as c:
        c.exec_driver_sql("CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT)")
    add_missing_columns(eng)
    assert "categoria_componente" in _columnas(eng, "productos")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_migrations.py::test_agrega_categoria_componente_a_productos -q`
Expected: FAIL — `assert 'categoria_componente' in {...}` (la columna no existe aún).

- [ ] **Step 3: Write minimal implementation**

En `backend/app/migrations.py`, ampliar el dict de `productos` (líneas 18-19) para que quede:

```python
    "productos": {"meses_garantia_default": "INTEGER DEFAULT 24", "categoria": "TEXT",
                  "pn_fabricante": "TEXT", "fabricante_id": "INTEGER",
                  "categoria_componente": "TEXT"},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_migrations.py -q`
Expected: PASS (todos los tests de migración, incluido el nuevo).

- [ ] **Step 5: Commit**

```bash
git add backend/app/migrations.py backend/tests/test_migrations.py
git commit -m "feat(categoria-componente): migración idempotente añade columna a productos"
```

---

## Task 2: Modelo — columna en `Producto` + propiedad heredada en `Componente`

**Files:**
- Modify: `backend/app/models.py:65` (Producto) y `backend/app/models.py:127-129` (Componente)
- Test: `backend/tests/test_componentes.py`

- [ ] **Step 1: Write the failing test**

Añadir al final de `backend/tests/test_componentes.py`:

```python
def test_componente_hereda_categoria_componente_del_producto(client):
    prod = client.post("/api/productos", json={
        "part_number": "VP-510104206", "tipo": "componente", "descripcion": "Receiver module",
        "categoria_componente": "mass_interconnect",
    }).json()
    eq_prod = client.post("/api/productos", json={
        "part_number": "EQ-CC", "tipo": "equipo", "descripcion": "Equipo",
    }).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-CC", "producto_id": eq_prod["id"]}).json()
    comp = client.post("/api/componentes", json={
        "numero_serie": "C-1", "producto_id": prod["id"], "equipo_id": eq["id"],
    }).json()
    assert comp["categoria_componente"] == "mass_interconnect"
```

Este test depende también de Task 3 (schema) y Task 4 (ComponenteOut). Es esperado: lo dejamos escrito y rojo; pasará al cerrar la cadena. Para mantener el ciclo TDD por tarea, en esta tarea verificamos el modelo con un test unitario de ORM directo (siguiente bloque).

Añadir además este test unitario que sólo ejercita el modelo (no la API), también al final de `test_componentes.py`:

```python
def test_modelo_componente_categoria_componente_property(db_session):
    from app import models
    p = models.Producto(part_number="P-MOD", tipo="componente", descripcion="x",
                         categoria_componente="wiring")
    db_session.add(p)
    db_session.flush()
    c = models.Componente(numero_serie="S-MOD", producto_id=p.id)
    db_session.add(c)
    db_session.flush()
    db_session.refresh(c)
    assert c.categoria_componente == "wiring"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_componentes.py::test_modelo_componente_categoria_componente_property -q`
Expected: FAIL — `TypeError: 'categoria_componente' is an invalid keyword argument for Producto` (la columna no existe en el modelo).

- [ ] **Step 3: Write minimal implementation**

En `backend/app/models.py`, dentro de `class Producto` (tras la línea 65 `pn_fabricante`), añadir:

```python
    categoria_componente: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

En `backend/app/models.py`, dentro de `class Componente`, tras la propiedad `categoria` existente (línea 127-129), añadir:

```python
    @property
    def categoria_componente(self):
        return self.producto.categoria_componente if self.producto is not None else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_componentes.py::test_modelo_componente_categoria_componente_property -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_componentes.py
git commit -m "feat(categoria-componente): columna en Producto y propiedad heredada en Componente"
```

---

## Task 3: Schema — validación en `ProductoCreate` + salida en `ProductoOut`

**Files:**
- Modify: `backend/app/schemas.py:65` (constante), `:68-78` (ProductoCreate), `:81-92` (ProductoOut)
- Test: `backend/tests/test_productos.py`

- [ ] **Step 1: Write the failing test**

Añadir al final de `backend/tests/test_productos.py`:

```python
def test_producto_acepta_y_devuelve_categoria_componente(client):
    r = client.post("/api/productos", json={
        "part_number": "KS-34470A", "tipo": "componente", "descripcion": "DMM",
        "categoria_componente": "instrumento",
    })
    assert r.status_code == 201, r.text
    assert r.json()["categoria_componente"] == "instrumento"


def test_producto_categoria_componente_opcional(client):
    r = client.post("/api/productos", json={
        "part_number": "CC-NC", "tipo": "componente", "descripcion": "x",
    })
    assert r.status_code == 201, r.text
    assert r.json()["categoria_componente"] is None


def test_producto_categoria_componente_invalida_422(client):
    r = client.post("/api/productos", json={
        "part_number": "CC-BAD", "tipo": "componente", "descripcion": "x",
        "categoria_componente": "no_existe",
    })
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_productos.py::test_producto_acepta_y_devuelve_categoria_componente -q`
Expected: FAIL — el campo no existe; la respuesta no tiene `categoria_componente` (KeyError en el assert).

- [ ] **Step 3: Write minimal implementation**

En `backend/app/schemas.py`, junto a `_CATEGORIA` (línea 65), añadir la constante:

```python
_CATEGORIA_COMPONENTE = Literal["instrumento", "mass_interconnect", "wiring", "accesorios"]
```

En `class ProductoCreate` (tras `pn_fabricante`, línea 78), añadir:

```python
    categoria_componente: Optional[_CATEGORIA_COMPONENTE] = None
```

En `class ProductoOut` (tras `pn_fabricante`, línea 92), añadir:

```python
    categoria_componente: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_productos.py -q`
Expected: PASS (los 3 nuevos + los existentes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_productos.py
git commit -m "feat(categoria-componente): validación y salida en schemas de Producto"
```

---

## Task 4: Schema — exponer `categoria_componente` heredada en `ComponenteOut`

**Files:**
- Modify: `backend/app/schemas.py:174-182` (ComponenteOut)
- Test: `backend/tests/test_componentes.py` (test de API de Task 2, ahora debe pasar)

- [ ] **Step 1: Confirmar el test rojo existente**

El test `test_componente_hereda_categoria_componente_del_producto` (añadido en Task 2) ejercita la API y todavía falla porque `ComponenteOut` no expone el campo.

Run: `.venv\Scripts\python.exe -m pytest tests/test_componentes.py::test_componente_hereda_categoria_componente_del_producto -q`
Expected: FAIL — la respuesta JSON no incluye `categoria_componente` (KeyError en el assert).

- [ ] **Step 2: Write minimal implementation**

En `backend/app/schemas.py`, dentro de `class ComponenteOut` (tras `categoria`, línea 182), añadir:

```python
    categoria_componente: Optional[str] = None
```

- [ ] **Step 3: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_componentes.py -q`
Expected: PASS (incluye el test de API de herencia y el unitario de Task 2).

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas.py
git commit -m "feat(categoria-componente): ComponenteOut expone la categoría heredada"
```

---

## Task 5: Filtro de lista en `/api/productos`

**Files:**
- Modify: `backend/app/routers/productos.py:16-21` (función `listar`)
- Test: `backend/tests/test_productos.py`

- [ ] **Step 1: Write the failing test**

Añadir al final de `backend/tests/test_productos.py`:

```python
def test_productos_filtra_por_categoria_componente(client):
    client.post("/api/productos", json={
        "part_number": "INS-1", "tipo": "componente", "descripcion": "DMM",
        "categoria_componente": "instrumento",
    })
    client.post("/api/productos", json={
        "part_number": "WIR-1", "tipo": "componente", "descripcion": "Cable",
        "categoria_componente": "wiring",
    })
    r = client.get("/api/productos?categoria_componente=instrumento")
    assert r.status_code == 200
    pns = {p["part_number"] for p in r.json()}
    assert pns == {"INS-1"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_productos.py::test_productos_filtra_por_categoria_componente -q`
Expected: FAIL — el parámetro se ignora; devuelve ambos productos, `pns == {"INS-1", "WIR-1"}`.

- [ ] **Step 3: Write minimal implementation**

En `backend/app/routers/productos.py`, reemplazar la firma y el cuerpo de `listar` (líneas 16-21) por:

```python
@router.get("", response_model=list[ProductoOut])
def listar(
    tipo: Optional[str] = None,
    categoria_componente: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[models.Producto]:
    q = db.query(models.Producto)
    if tipo is not None:
        q = q.filter(models.Producto.tipo == tipo)
    if categoria_componente is not None:
        q = q.filter(models.Producto.categoria_componente == categoria_componente)
    return q.order_by(models.Producto.part_number).all()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_productos.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/productos.py backend/tests/test_productos.py
git commit -m "feat(categoria-componente): filtro en GET /api/productos"
```

---

## Task 6: Filtro de lista en `/api/componentes`

**Files:**
- Modify: `backend/app/routers/componentes.py:16-27` (función `listar`)
- Test: `backend/tests/test_componentes.py`

- [ ] **Step 1: Write the failing test**

Añadir al final de `backend/tests/test_componentes.py`:

```python
def test_componentes_filtra_por_categoria_componente(client):
    eq_prod = client.post("/api/productos", json={
        "part_number": "EQ-F", "tipo": "equipo", "descripcion": "Equipo",
    }).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-F", "producto_id": eq_prod["id"]}).json()
    p_ins = client.post("/api/productos", json={
        "part_number": "INS-F", "tipo": "componente", "descripcion": "DMM",
        "categoria_componente": "instrumento",
    }).json()
    p_wir = client.post("/api/productos", json={
        "part_number": "WIR-F", "tipo": "componente", "descripcion": "Cable",
        "categoria_componente": "wiring",
    }).json()
    client.post("/api/componentes", json={"numero_serie": "CI", "producto_id": p_ins["id"], "equipo_id": eq["id"]})
    client.post("/api/componentes", json={"numero_serie": "CW", "producto_id": p_wir["id"], "equipo_id": eq["id"]})

    r = client.get("/api/componentes?categoria_componente=instrumento")
    assert r.status_code == 200
    series = {c["numero_serie"] for c in r.json()}
    assert series == {"CI"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_componentes.py::test_componentes_filtra_por_categoria_componente -q`
Expected: FAIL — el parámetro se ignora; devuelve ambos componentes, `series == {"CI", "CW"}`.

- [ ] **Step 3: Write minimal implementation**

En `backend/app/routers/componentes.py`, reemplazar la firma y el cuerpo de `listar` (líneas 16-27) por:

```python
@router.get("", response_model=list[ComponenteOut])
def listar(
    equipo_id: Optional[int] = None,
    producto_id: Optional[int] = None,
    categoria_componente: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[models.Componente]:
    q = db.query(models.Componente)
    if equipo_id is not None:
        q = q.filter(models.Componente.equipo_id == equipo_id)
    if producto_id is not None:
        q = q.filter(models.Componente.producto_id == producto_id)
    if categoria_componente is not None:
        sub = db.query(models.Producto.id).filter(
            models.Producto.categoria_componente == categoria_componente
        )
        q = q.filter(models.Componente.producto_id.in_(sub))
    return q.order_by(models.Componente.numero_serie).all()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_componentes.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/componentes.py backend/tests/test_componentes.py
git commit -m "feat(categoria-componente): filtro en GET /api/componentes"
```

---

## Task 7: Suite completa verde

**Files:** ninguno (verificación).

- [ ] **Step 1: Run full suite**

Parar uvicorn de dev si está vivo (el seeder de ayuda toca `postventa.db` al importar). Luego:

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS. Recuento esperado = baseline previo + 7 tests nuevos (1 migración + 2 herencia componente + 3 producto schema/filtro... contabilizar: Task1 +1, Task2 +2, Task3 +3, Task5 +1, Task6 +1 = +8). Confirmar que el total sube en 8 respecto al baseline y que no hay regresiones.

- [ ] **Step 2: Commit (sólo si hubiera ajustes)**

Si todo está verde sin cambios, no hay commit. Si hubo que tocar algo para que pase la suite, commitear con mensaje descriptivo.

---

## Task 8: Script de auto-clasificación de los 119 productos

**Files:**
- Create: `backend/_clasificar_categoria_componente.py` (throwaway, gitignored por `_*.py`)

Este script NO lleva tests (es throwaway, patrón establecido del repo). Se ejecuta una vez con backup previo. La lógica de reglas es pura y simple; el usuario revisa el resultado.

- [ ] **Step 1: Crear el script**

Crear `backend/_clasificar_categoria_componente.py` con este contenido exacto:

```python
"""Throwaway: auto-clasifica Producto.categoria_componente por reglas.

Reglas (primera que casa gana):
  1. mass_interconnect  -> 'Virginia Panel' en fabricante/descr. o P/N empieza por 'VP'
  2. wiring             -> descr. contiene lead/cable/patch/cord/wire/wiring/harness
  3. instrumento        -> fabricante en lista de instrumentación
  4. accesorios         -> el resto (6TL, Cliff CP30xxx, tornillería, ...)

Sólo toca productos tipo='componente' con categoria_componente nula (no pisa lo
ya clasificado a mano). Audita como usuario='alta manual'.

Uso (desde backend/):
  .venv\\Scripts\\python.exe _clasificar_categoria_componente.py            # dry-run
  .venv\\Scripts\\python.exe _clasificar_categoria_componente.py --commit   # escribe
"""
from __future__ import annotations

import sys

from app import auditoria, models
from app.db import SessionLocal

_INSTRUMENTO_FABRICANTES = {
    "keysight", "agilent", "national instruments", "ni", "pickering",
    "chroma", "ametek", "hocherl", "hocherl & hackl", "hoecherl",
}
_WIRING_KEYWORDS = ("lead", "cable", "patch", "cord", "wire", "wiring", "harness")


def clasificar(part_number: str, descripcion: str, fabricante: str | None) -> str:
    pn = (part_number or "").strip().upper()
    desc = (descripcion or "").lower()
    fab = (fabricante or "").strip().lower()

    if "virginia panel" in fab or "virginia panel" in desc or pn.startswith("VP"):
        return "mass_interconnect"
    if any(k in desc for k in _WIRING_KEYWORDS):
        return "wiring"
    if fab in _INSTRUMENTO_FABRICANTES:
        return "instrumento"
    return "accesorios"


def main(commit: bool) -> None:
    auditoria.registrar_listeners()  # idempotente
    db = SessionLocal()
    db.info["usuario_username"] = "alta manual"
    db.info["usuario_id"] = None
    conteo: dict[str, int] = {}
    accesorios: list[str] = []
    try:
        prods = (
            db.query(models.Producto)
            .filter(models.Producto.tipo == "componente")
            .filter(models.Producto.categoria_componente.is_(None))
            .order_by(models.Producto.part_number)
            .all()
        )
        for p in prods:
            cat = clasificar(p.part_number, p.descripcion, p.fabricante)
            conteo[cat] = conteo.get(cat, 0) + 1
            if cat == "accesorios":
                accesorios.append(f"  {p.part_number} — {p.descripcion} ({p.fabricante or 's/fab'})")
            if commit:
                p.categoria_componente = cat
        if commit:
            db.commit()
        print(f"Productos componente sin clasificar procesados: {len(prods)}")
        for cat in ("instrumento", "mass_interconnect", "wiring", "accesorios"):
            print(f"  {cat:18} {conteo.get(cat, 0)}")
        print("\nClasificados como ACCESORIOS (revisar dudosos):")
        print("\n".join(accesorios) if accesorios else "  (ninguno)")
        print("\n" + ("ESCRITO (--commit)" if commit else "DRY-RUN: nada escrito. Repite con --commit."))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main(commit="--commit" in sys.argv)
```

- [ ] **Step 2: Backup de la BD viva**

Run (desde `backend/`):
```
copy postventa.db postventa.db.precategoriacomp-20260611.bak
```
Expected: `1 archivo(s) copiado(s)`.

- [ ] **Step 3: Dry-run y revisión**

Parar uvicorn de dev primero. Luego:
Run: `.venv\Scripts\python.exe _clasificar_categoria_componente.py`
Expected: imprime el conteo por categoría y la lista de `accesorios`. Revisar que los repartos tienen sentido (VP→mass_interconnect ~9, cables→wiring ~30, instrumentación→instrumento ~45, resto→accesorios). Nada se escribe.

- [ ] **Step 4: Confirmación del usuario antes de escribir**

PARAR aquí y mostrar al usuario el conteo + la lista de accesorios. El usuario confirma o pide ajustar reglas. **No ejecutar `--commit` sin su visto bueno** (decisión "auto + tú revisas" del diseño).

- [ ] **Step 5: Escribir (tras visto bueno)**

Run: `.venv\Scripts\python.exe _clasificar_categoria_componente.py --commit`
Expected: `ESCRITO (--commit)`.

- [ ] **Step 6: Verificación en vivo**

Arrancar backend y comprobar:
Run: `.venv\Scripts\python.exe -c "from app.db import SessionLocal; from app import models; db=SessionLocal(); from sqlalchemy import func; print(db.query(models.Producto.categoria_componente, func.count()).filter(models.Producto.tipo=='componente').group_by(models.Producto.categoria_componente).all())"`
Expected: reparto no nulo entre las 4 categorías.

No hay commit de código en esta tarea (el script es gitignored, los datos viven en `postventa.db`).

---

## Task 9: Prompt Lovable (frontend)

**Files:** ninguno en backend. Redactar el prompt para Lovable (selector + badge + filtro). Se PEGA manualmente por el usuario; no se implementa aquí.

- [ ] **Step 1: Redactar el prompt 29 (categoría de componente)**

Escribir un prompt Lovable que añada:
1. **Selector** "Categoría de componente" en el formulario de alta/edición de **producto** (campo `categoria_componente`), visible/relevante sólo cuando `tipo === "componente"`. Opciones: `Instrumento` (`instrumento`), `Mass Interconnect` (`mass_interconnect`), `Wiring` (`wiring`), `Accesories` (`accesorios`), más "(sin clasificar)" = `null`.
2. **Badge** de categoría por componente en la lista de componentes de la ficha del equipo, leyendo `componente.categoria_componente`. Color distinto por categoría; sin badge si es `null`.
3. **Filtro** por categoría de componente en el listado/catálogo, usando `GET /api/productos?categoria_componente=<slug>` y/o `GET /api/componentes?categoria_componente=<slug>`.

Indicar en el prompt el contrato exacto: el campo `categoria_componente` existe en `ProductoOut` y en `ComponenteOut`, y los dos endpoints aceptan el query param `categoria_componente`. Recordar a Lovable: NO tocar el `categoria` existente (eje distinto), NO renombrar campos, respetar los slugs.

- [ ] **Step 2: Guardar el prompt**

Guardar el prompt junto a los demás prompts Lovable del proyecto (misma carpeta/convención que los prompts 27/28). Dejar anotado en memoria que está "SIN pegar".

---

## Self-Review

- **Spec coverage:**
  - Modelo `Producto.categoria_componente` nullable → Task 2. ✅
  - Propiedad heredada `Componente.categoria_componente` → Task 2. ✅
  - Migración idempotente → Task 1. ✅
  - Validación `Literal` 4 slugs → Task 3. ✅
  - `ProductoOut` / `ComponenteOut` exponen el campo → Tasks 3 y 4. ✅
  - Filtro `GET /api/productos?categoria_componente=` → Task 5. ✅
  - Filtro `GET /api/componentes?categoria_componente=` → Task 6. ✅
  - Script auto-clasificación con reglas (Cliff→accesorios explícito en regla 4) → Task 8. ✅
  - Frontend selector/badge/filtro → Task 9. ✅
  - Fuera de alcance (sin tabla de categorías, sin tocar `categoria`) respetado. ✅
- **Placeholder scan:** sin TBD/TODO; todo el código está completo en cada step.
- **Type consistency:** `categoria_componente` (slug en inglés/español según tabla) usado idéntico en modelo, schema, routers y script. Slugs: `instrumento`/`mass_interconnect`/`wiring`/`accesorios`. Etiqueta visible `Accesories`. `_CATEGORIA_COMPONENTE` definido una vez en `schemas.py` y reutilizado.
- **Nota de dependencia cruzada:** el test de API de herencia (Task 2 Step 1) depende de Tasks 3+4; queda documentado y se cierra en Task 4. El test unitario de modelo de Task 2 es autónomo y cierra el ciclo TDD de esa tarea.
