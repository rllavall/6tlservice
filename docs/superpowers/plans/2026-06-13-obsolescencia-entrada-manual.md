# Entrada manual del estado de ciclo de vida — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir fijar a mano el estado de ciclo de vida de un producto desde el popup del report del banco (para webs que bloquean bots, p. ej. Keysight), distinguiéndolo del automático, sin que el agente lo pise salvo que consiga un hallazgo fiable ("agente gana").

**Architecture:** Nuevo `Producto.ciclo_vida_origen` (`'agente'|'manual'`). El servicio gana `registrar_manual` (no exige url, guarda la nota del usuario en `ciclo_vida_cita`, marca origen='manual', crea noticia si notable); `registrar_hallazgo` marca origen='agente' (y como siempre sobreescribe en `ok`, "agente gana" sale solo; `no_encontrado` no toca el estado → el manual sobrevive). Endpoint `PATCH /api/productos/{id}/ciclo-vida`. El origen fluye al report y se muestra como badge "Manual".

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, Pydantic v2, SQLite, pytest. Frontend TanStack Start (prompt Lovable).

**Repo root:** `C:\Users\rllavall\6TL Postventa` (git en la raíz, código en `backend/`). Rama: `feat/obsolescencia-entrada-manual` (ya creada).

**⚠️ Entorno:** ejecutar pytest/python desde `backend/` con `.venv/Scripts/python`. El seeder de ayuda toca `postventa.db` al importar la app → parar uvicorn antes de la suite completa. Auth ya aplicada a nivel `include_router` (la ruta `/api/productos` hereda `get_current_user`); NO añadir auth por endpoint.

---

### Task 1: Columnas `Producto.ciclo_vida_origen` y `NoticiaObsolescencia.origen`

**Files:**
- Modify: `backend/app/models.py` (Producto tras `ciclo_vida_cita`; NoticiaObsolescencia tras `cita`)
- Modify: `backend/app/migrations.py` (`_COLUMNAS_NUEVAS`)
- Test: `backend/tests/test_migrations.py`, `backend/tests/test_obsolescencia_modelo.py`

- [ ] **Step 1: Write the failing migration test** — append to `backend/tests/test_migrations.py`:

```python
def test_migracion_anade_origen_ciclo_vida(tmp_path):
    from sqlalchemy import create_engine, text
    from app.migrations import add_missing_columns

    db = tmp_path / "old3.db"
    eng = create_engine(f"sqlite+pysqlite:///{db}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT)")
        conn.exec_driver_sql(
            "CREATE TABLE noticias_obsolescencia (id INTEGER PRIMARY KEY, producto_id INTEGER)")
    add_missing_columns(eng)
    with eng.connect() as conn:
        prod_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(productos)"))}
        not_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(noticias_obsolescencia)"))}
    assert "ciclo_vida_origen" in prod_cols
    assert "origen" in not_cols
    eng.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_migrations.py::test_migracion_anade_origen_ciclo_vida -v`
Expected: FAIL (`ciclo_vida_origen` not present).

- [ ] **Step 3: Add columns to migrations**

In `backend/app/migrations.py`, in `_COLUMNAS_NUEVAS`: append `"ciclo_vida_origen": "TEXT"` to the `productos` dict (after `ciclo_vida_cita`), and add `"origen": "TEXT"` to the existing `noticias_obsolescencia` entry. The two entries become:

```python
    "productos": {"meses_garantia_default": "INTEGER DEFAULT 24", "categoria": "TEXT",
                  "pn_fabricante": "TEXT", "fabricante_id": "INTEGER",
                  "categoria_componente": "TEXT",
                  "estado_ciclo_vida": "TEXT", "ciclo_vida_fecha": "DATE",
                  "ciclo_vida_url": "TEXT", "ciclo_vida_resumen": "TEXT",
                  "ciclo_vida_verificado_en": "DATE", "ciclo_vida_cita": "TEXT",
                  "ciclo_vida_origen": "TEXT"},
    "fabricantes": {"url_obsolescencia": "TEXT"},
    "noticias_obsolescencia": {"cita": "TEXT", "origen": "TEXT"},
```

- [ ] **Step 4: Add columns to models**

In `backend/app/models.py`, in `class Producto`, AFTER the `ciclo_vida_cita` line add:

```python
    ciclo_vida_origen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

In `class NoticiaObsolescencia`, AFTER the `cita` line add:

```python
    origen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- [ ] **Step 5: Write model persistence test** — append to `backend/tests/test_obsolescencia_modelo.py`:

```python
def test_producto_y_noticia_persisten_origen(db_session):
    p = models.Producto(part_number="X-ORIG", tipo="componente", descripcion="Demo",
                         fabricante="Keysight", pn_fabricante="KS-1")
    p.ciclo_vida_origen = "manual"
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    assert p.ciclo_vida_origen == "manual"
    n = models.NoticiaObsolescencia(
        producto_id=p.id, fecha_deteccion=date(2026, 6, 13),
        estado_anterior="activo", estado_nuevo="obsoleto", origen="manual", notificado=False)
    db_session.add(n); db_session.commit(); db_session.refresh(n)
    assert n.origen == "manual"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_migrations.py tests/test_obsolescencia_modelo.py -v`
Expected: PASS (incl. the two new tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/migrations.py backend/tests/test_migrations.py backend/tests/test_obsolescencia_modelo.py
git commit -m "feat(obsolescencia): columnas ciclo_vida_origen y noticia.origen + migracion"
```
(Append blank line + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.)

---

### Task 2: `registrar_manual` + `registrar_hallazgo` marca origen='agente'

**Files:**
- Modify: `backend/app/obsolescencia_service.py` (`registrar_hallazgo`; añadir `registrar_manual`)
- Test: `backend/tests/test_obsolescencia_service.py`

- [ ] **Step 1: Write failing tests** — append to `backend/tests/test_obsolescencia_service.py`:

```python
def test_registrar_manual_sin_url_guarda_estado_nota_y_origen(db_session):
    p = _prod(db_session, "A")
    r = svc.registrar_manual(db_session, p.id, "obsoleto", hoy=date(2026, 6, 13),
                             nota="Confirmado EOL por email del fabricante")
    assert r["registrado"] is True and r["cambio"] is True   # no exige url
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "obsoleto"
    assert p.ciclo_vida_cita == "Confirmado EOL por email del fabricante"
    assert p.ciclo_vida_origen == "manual"
    assert p.ciclo_vida_verificado_en == date(2026, 6, 13)
    n = db_session.query(models.NoticiaObsolescencia).filter_by(producto_id=p.id).one()
    assert n.origen == "manual" and n.cita == "Confirmado EOL por email del fabricante"


def test_registrar_manual_estado_invalido_se_rechaza(db_session):
    p = _prod(db_session, "A")
    r = svc.registrar_manual(db_session, p.id, "no_existe", hoy=date(2026, 6, 13))
    assert r["registrado"] is False and r["motivo"] == "estado_invalido"
    db_session.refresh(p)
    assert p.estado_ciclo_vida is None


def test_agente_gana_sobreescribe_manual_y_marca_origen_agente(db_session):
    p = _prod(db_session, "A")
    svc.registrar_manual(db_session, p.id, "nrnd", hoy=date(2026, 6, 13), nota="manual")
    # el agente consigue un hallazgo fiable -> sobreescribe y deja origen='agente'
    svc.registrar_hallazgo(db_session, p.id, "obsoleto", hoy=date(2026, 6, 20),
                           url="https://x", resumen="EOL", cita="Status: Obsolete")
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "obsoleto"
    assert p.ciclo_vida_origen == "agente"
    assert p.ciclo_vida_cita == "Status: Obsolete"


def test_marcar_revisado_no_pisa_el_manual(db_session):
    p = _prod(db_session, "A")
    svc.registrar_manual(db_session, p.id, "obsoleto", hoy=date(2026, 6, 13), nota="manual")
    svc.marcar_revisado(db_session, p.id, date(2026, 6, 20))   # caso no_encontrado del agente
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "obsoleto"        # intacto
    assert p.ciclo_vida_origen == "manual"          # sigue manual
    assert p.ciclo_vida_verificado_en == date(2026, 6, 20)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_service.py -k "manual or agente_gana" -v`
Expected: FAIL — `AttributeError: ... 'registrar_manual'` and origen assertions.

- [ ] **Step 3: Implement**

In `backend/app/obsolescencia_service.py`:

(a) In `registrar_hallazgo`, after the line `p.ciclo_vida_verificado_en = hoy` add:

```python
    p.ciclo_vida_origen = "agente"
```

and in the `models.NoticiaObsolescencia(...)` constructor add `origen="agente",` (e.g. right after `cita=cita,`).

(b) Add a new function immediately after `registrar_hallazgo` (before `marcar_revisado` is fine):

```python
def registrar_manual(db: Session, producto_id: int, estado: str, *, hoy: date,
                     fecha_evento: date | None = None, url: str | None = None,
                     nota: str | None = None) -> dict:
    """Fija a mano el estado de ciclo de vida (para webs que bloquean bots). No exige
    url (a diferencia del agente); guarda `nota` como cita y marca origen='manual'.
    Crea NoticiaObsolescencia si el cambio es notable."""
    p = db.get(models.Producto, producto_id)
    if p is None:
        return {"registrado": False, "motivo": "no_existe", "cambio": False}
    if not obsolescencia.estado_valido(estado):
        return {"registrado": False, "motivo": "estado_invalido", "cambio": False}

    anterior = p.estado_ciclo_vida
    notable = obsolescencia.es_cambio_notable(anterior, estado)

    p.estado_ciclo_vida = estado
    p.ciclo_vida_fecha = fecha_evento
    p.ciclo_vida_url = url
    p.ciclo_vida_resumen = nota
    p.ciclo_vida_cita = nota
    p.ciclo_vida_verificado_en = hoy
    p.ciclo_vida_origen = "manual"

    if notable:
        db.add(models.NoticiaObsolescencia(
            producto_id=p.id, fecha_deteccion=hoy, estado_anterior=anterior,
            estado_nuevo=estado, fecha_evento=fecha_evento, url_fuente=url,
            resumen=nota, cita=nota, origen="manual", notificado=False))
    db.commit()
    return {"registrado": True, "cambio": notable, "motivo": None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_service.py -v`
Expected: PASS (todos, incl. previos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/obsolescencia_service.py backend/tests/test_obsolescencia_service.py
git commit -m "feat(obsolescencia): registrar_manual + origen agente/manual"
```
(Append Co-Authored-By trailer.)

---

### Task 3: Endpoint `PATCH /api/productos/{id}/ciclo-vida` + schemas

**Files:**
- Modify: `backend/app/schemas.py` (`CicloVidaManualIn`; `ProductoOut += ciclo_vida_cita, ciclo_vida_origen`)
- Modify: `backend/app/routers/productos.py`
- Test: `backend/tests/test_productos_ciclo_vida_manual.py` (CREATE)

- [ ] **Step 1: Add schemas**

In `backend/app/schemas.py`:

(a) In `class ProductoOut`, after `ciclo_vida_verificado_en: Optional[date] = None` add:

```python
    ciclo_vida_cita: Optional[str] = None
    ciclo_vida_origen: Optional[str] = None
```

(b) Add a new input schema near the other obsolescence schemas (e.g. after `HallazgoObsolescencia`):

```python
class CicloVidaManualIn(BaseModel):
    estado: _ESTADO_CICLO
    fecha_evento: Optional[date] = None
    url: Optional[str] = None
    nota: Optional[str] = None
```

- [ ] **Step 2: Write the failing endpoint test** — create `backend/tests/test_productos_ciclo_vida_manual.py`:

```python
from datetime import date

from app import models


def _prod(db, pn="P-MAN", fab="Keysight", pnf="KS-9"):
    p = models.Producto(part_number=pn, tipo="componente", descripcion=pn,
                        fabricante=fab, pn_fabricante=pnf)
    db.add(p); db.commit(); db.refresh(p)
    return p


def test_patch_ciclo_vida_manual_fija_estado(client, db_session):
    p = _prod(db_session)
    r = client.patch(f"/api/productos/{p.id}/ciclo-vida",
                     json={"estado": "obsoleto", "nota": "EOL confirmado por distribuidor"})
    assert r.status_code == 200
    body = r.json()
    assert body["estado_ciclo_vida"] == "obsoleto"
    assert body["ciclo_vida_origen"] == "manual"
    assert body["ciclo_vida_cita"] == "EOL confirmado por distribuidor"


def test_patch_ciclo_vida_manual_producto_inexistente_404(client):
    r = client.patch("/api/productos/999999/ciclo-vida", json={"estado": "activo"})
    assert r.status_code == 404


def test_patch_ciclo_vida_manual_estado_invalido_422(client, db_session):
    p = _prod(db_session, pn="P-MAN2", pnf="KS-10")
    r = client.patch(f"/api/productos/{p.id}/ciclo-vida", json={"estado": "kaput"})
    assert r.status_code == 422
```

NOTE: the `client` fixture is authenticated (see other router tests like `test_productos_*`/`test_obsolescencia_banco_router.py` — if `client` is NOT pre-authed, mirror exactly how those existing passing router tests obtain an authorized client; do not invent a new auth mechanism).

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_productos_ciclo_vida_manual.py -v`
Expected: FAIL — 404/route-not-found (endpoint missing).

- [ ] **Step 4: Implement the endpoint**

In `backend/app/routers/productos.py`:

(a) Update imports at the top:

```python
from datetime import date
```
and extend the schema import line to include the new schema:
```python
from app.schemas import CicloVidaManualIn, ProductoCreate, ProductoOut
```
and import the service:
```python
from app import models, obsolescencia_service
```
(replace the existing `from app import models` line).

(b) Add the endpoint (e.g. after `obtener`):

```python
@router.patch("/{producto_id}/ciclo-vida", response_model=ProductoOut)
def fijar_ciclo_vida_manual(producto_id: int, payload: CicloVidaManualIn,
                            db: Session = Depends(get_db)) -> models.Producto:
    p = db.get(models.Producto, producto_id)
    if p is None:
        raise HTTPException(404, "Producto no encontrado")
    obsolescencia_service.registrar_manual(
        db, producto_id, payload.estado, hoy=date.today(),
        fecha_evento=payload.fecha_evento, url=payload.url, nota=payload.nota)
    db.refresh(p)
    return p
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_productos_ciclo_vida_manual.py tests/test_productos_api.py -v` (run the existing productos test too if it exists, to catch regressions; if `test_productos_api.py` doesn't exist, omit it)
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/productos.py backend/tests/test_productos_ciclo_vida_manual.py
git commit -m "feat(obsolescencia): PATCH /api/productos/{id}/ciclo-vida (entrada manual)"
```
(Append Co-Authored-By trailer.)

---

### Task 4: Exponer `ciclo_vida_origen` y `producto_id` en el report del banco

El frontend necesita `producto_id` para llamar al PATCH manual (la fila hoy solo trae
`componente_id`). Lo añadimos aquí junto con `ciclo_vida_origen`.

**Files:**
- Modify: `backend/app/obsolescencia_banco.py` (`informe_banco` fila)
- Modify: `backend/app/schemas.py` (`ObsolescenciaBancoComponenteOut`)
- Test: `backend/tests/test_obsolescencia_banco.py`

- [ ] **Step 1: Write failing test** — append to `backend/tests/test_obsolescencia_banco.py`:

```python
def test_informe_banco_incluye_origen_y_producto_id(db_session):
    eq_id = _seed_banco(db_session)
    p_obs = db_session.query(models.Producto).filter_by(part_number="P-OBS").one()
    p_obs.ciclo_vida_origen = "manual"
    db_session.commit()
    inf = obsolescencia_banco.informe_banco(db_session, eq_id, date(2026, 6, 13))
    fila = next(f for f in inf["componentes"] if f["part_number"] == "P-OBS")
    assert fila["ciclo_vida_origen"] == "manual"
    assert fila["producto_id"] == p_obs.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py::test_informe_banco_incluye_origen_y_producto_id -v`
Expected: FAIL — `KeyError: 'ciclo_vida_origen'` (and/or `'producto_id'`).

- [ ] **Step 3: Implement**

(a) In `backend/app/obsolescencia_banco.py`, `informe_banco`, add to the `filas.append({...})` dict. Add `"producto_id": p.id,` near the top of the dict (e.g. right after `"componente_id": comp.id,`) and `"ciclo_vida_origen": p.ciclo_vida_origen,` right after the `"ciclo_vida_cita": p.ciclo_vida_cita,` line:

```python
            "componente_id": comp.id,
            "producto_id": p.id,
```
...
```python
            "ciclo_vida_cita": p.ciclo_vida_cita,
            "ciclo_vida_origen": p.ciclo_vida_origen,
```

(b) In `backend/app/schemas.py`, `class ObsolescenciaBancoComponenteOut`: add `producto_id: int` (right after `componente_id: int`) and `ciclo_vida_origen: Optional[str] = None` (after `ciclo_vida_cita`):

```python
    componente_id: int
    producto_id: int
```
...
```python
    ciclo_vida_cita: Optional[str] = None
    ciclo_vida_origen: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py tests/test_obsolescencia_banco_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/obsolescencia_banco.py backend/app/schemas.py backend/tests/test_obsolescencia_banco.py
git commit -m "feat(obsolescencia): informe_banco expone ciclo_vida_origen"
```
(Append Co-Authored-By trailer.)

---

### Task 5: Full suite + prompt Lovable 37

**Files:**
- Create: `docs/lovable/37_entrada_manual_obsolescencia.md`
- Modify: `docs/lovable/README.md`
- Test: full backend suite

- [ ] **Step 1: Run the full backend suite (regresión)**

Run (parar uvicorn antes): `.venv/Scripts/python -m pytest -q`
Expected: PASS de toda la suite. Si algo rompe por el origen nuevo, ajustarlo.

- [ ] **Step 2: Write the Lovable prompt 37** — create `docs/lovable/37_entrada_manual_obsolescencia.md`:

```markdown
# Prompt 37 — Entrada manual del estado de ciclo de vida en el report del banco

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, helper `api<T>()` en
`@/lib/api` (inyecta Bearer), tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`,
componentes `<EstadoCicloBadge estado url resumen />` y `ReportObsolescenciaDialog`
(prompts 32/34/35/36)). **NO cambies nombres de campo del backend. No inventes endpoints
ni campos fuera de los listados.** Todo va protegido (el `api()` manda token).

Para fabricantes cuya web bloquea bots (p. ej. Keysight) el agente no puede determinar el
estado y el componente se queda en "No encontrado". El usuario debe poder **fijar el
estado a mano** desde la tabla del report del banco.

## 1. Tipos en `src/lib/types.ts`
- `ObsolescenciaBancoComponente` += `producto_id: number` y
  `ciclo_vida_origen: string | null` ("agente" | "manual").

## 2. Endpoint (ya existe en backend)
`PATCH /api/productos/{producto_id}/ciclo-vida` con body:
`{ "estado": "activo"|"nrnd"|"eol_anunciado"|"ultima_compra"|"obsoleto", "fecha_evento"?: "YYYY-MM-DD"|null, "url"?: string|null, "nota"?: string|null }`
Devuelve el producto actualizado. Usa `c.producto_id` de la fila del report (ahora
disponible) como `{producto_id}`.

## 3. UI en `ReportObsolescenciaDialog` (tabla de componentes)
- En cada fila, junto al estado, un **botón lápiz** (icono `Pencil`, ghost, pequeño) que
  abre un diálogo "Fijar estado a mano":
  - `estado`: select con los 5 valores (etiquetas legibles: Activo / NRND / EOL anunciado /
    Última compra / Obsoleto).
  - `fecha_evento`: input date (opcional).
  - `url`: input (opcional).
  - `nota`: textarea (opcional) — "justificación / fuente". Se mostrará como la cita.
  - Botón Guardar → `api(PATCH /api/productos/{producto_id}/ciclo-vida, body)` → al éxito,
    `toast.success`, cerrar el diálogo y **refrescar el report** (re-fetch del
    `GET /api/equipos/{id}/obsolescencia`). Manejar error con `toast.error`.
- Badge **"✋ Manual"** (pequeño, gris/lila) junto al `<EstadoCicloBadge>` cuando
  `ciclo_vida_origen === "manual"`. No mostrar nada extra cuando es "agente"/null.

## 4. Notas
- El resto del popup (prompts 34/35/36) no cambia.
- Tras guardar manual, el badge "Manual" debe aparecer y la cita (nota) verse en el botón
  "i" de prueba de origen (prompt 36).
```

- [ ] **Step 3: Add README row** — en `docs/lovable/README.md`, añadir fila 37 con el mismo formato que la 36 (descripción: "Entrada manual del estado de ciclo de vida (lápiz por fila + badge Manual) para webs que bloquean bots").

- [ ] **Step 4: Commit**

```bash
git add docs/lovable/37_entrada_manual_obsolescencia.md docs/lovable/README.md
git commit -m "docs(lovable): prompt 37 entrada manual de obsolescencia"
```
(Append Co-Authored-By trailer.)

---

## Notas finales para el ejecutor

- El `producto_id` necesario para el PATCH manual se añade a la fila del report en Task 4
  (la fila solo traía `componente_id`); así el frontend puede llamar al endpoint.
- Tras todas las tasks, dispatch de un **revisor holístico** (Opus) del diff de rama: foco
  en precedencia (agente sobreescribe manual; `no_encontrado`/`marcar_revisado` NO pisa el
  manual) y en que `registrar_manual` no exige url.
- Luego **superpowers:finishing-a-development-branch** (merge a master + push, según pida el usuario).
- Prompt Lovable 37 NO se pega aquí; queda escrito.
