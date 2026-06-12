# Progreso en vivo del refresco de obsolescencia por banco — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el botón "Refrescar estado" del report de obsolescencia de un banco lance el chequeo en segundo plano y un popup muestre el avance en vivo (barra X/N + componente actual + log de resultados), vía un job en memoria sondeado por el frontend.

**Architecture:** `refrescar_banco` gana un callback `on_progreso` (sin cambiar su comportamiento síncrono). Un store en memoria (`obsolescencia_jobs.py`) corre el refresco en un hilo daemon y va escribiendo el progreso; dos endpoints nuevos (`iniciar`/`progreso`) lo exponen. El frontend (prompt Lovable) abre un popup que sondea el progreso cada 1 s.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite, `check_same_thread=False`), Pydantic v2, threading (stdlib), pytest.

**Spec:** `docs/superpowers/specs/2026-06-12-progreso-refresco-obsolescencia-banco-design.md`

**Trabajo desde:** `backend/` (CWD). Tests: `.venv/Scripts/python -m pytest`. Rama: `feat/progreso-refresco-obsolescencia` (ya creada, contiene el spec).

**Reutilizado (NO modificar salvo lo indicado):**
- `app/obsolescencia_banco.py`: `informe_banco(db,equipo_id,hoy)`, `productos_de_equipo(db,equipo_id)`, `_url_fabricante(db,p)`, `refrescar_banco(db,equipo_id,hoy,*,limite=10,consultar)` (Task 1 le añade `on_progreso`).
- `app/obsolescencia_service.py::registrar_hallazgo(...)` devuelve `{"registrado":bool,"cambio":bool,"motivo":...}` y deja `producto.estado_ciclo_vida` actualizado tras un registro válido.
- `app/db.py`: `SessionLocal` (engine con `check_same_thread=False`), `get_db`.
- `app/deps.py::get_consultar_fabricante` (Depends inyectable; en tests se override).
- Router `app/routers/obsolescencia_banco.py` (prefix `/api/equipos`, ya registrado en main con auth) con helper `_equipo_o_404(db, equipo_id)` y `Query`.
- Tests: `tests/conftest.py` → `client` (auth simulada, override `get_db`+`get_current_user`), `client_sin_auth` (auth real), `db_session` + `memory_engine` (mismo motor SQLite en memoria; `StaticPool`).

---

## Task 1: `refrescar_banco` emite progreso (`on_progreso`)

**Files:**
- Modify: `backend/app/obsolescencia_banco.py:104-119` (la función `refrescar_banco`)
- Test: `backend/tests/test_obsolescencia_banco.py` (APPEND un test)

- [ ] **Step 1: Append the failing test** a `tests/test_obsolescencia_banco.py` (reusa el `_seed_banco` y los imports ya presentes):

```python
def test_refrescar_banco_emite_progreso(db_session):
    eq_id = _seed_banco(db_session)

    def fake(p, url):
        if p.part_number == "P-ACT":
            return {"estado": "obsoleto", "fecha_evento": None,
                    "url_fuente": "http://b/eol", "resumen": "x"}
        return None

    ev = []
    obsolescencia_banco.refrescar_banco(
        db_session, eq_id, date(2026, 6, 12), limite=10,
        consultar=fake, on_progreso=ev.append)

    # P-OBS (verificado 2026-01-01) va antes que P-ACT (2026-06-01)
    pares = [(e["tipo"], e["producto"].part_number) for e in ev]
    assert ("actual", "P-OBS") in pares and ("resultado", "P-OBS") in pares
    assert ("actual", "P-ACT") in pares and ("resultado", "P-ACT") in pares
    # 'actual' precede a su 'resultado' para P-ACT
    ia = next(i for i, e in enumerate(ev)
              if e["tipo"] == "actual" and e["producto"].part_number == "P-ACT")
    ir = next(i for i, e in enumerate(ev)
              if e["tipo"] == "resultado" and e["producto"].part_number == "P-ACT")
    assert ia < ir
    r_act = next(e for e in ev if e["tipo"] == "resultado" and e["producto"].part_number == "P-ACT")
    assert r_act["estado_anterior"] == "activo"
    assert r_act["estado_nuevo"] == "obsoleto"
    assert r_act["cambio"] is True
    r_obs = next(e for e in ev if e["tipo"] == "resultado" and e["producto"].part_number == "P-OBS")
    assert r_obs["cambio"] is False  # fake devolvió None para P-OBS
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py::test_refrescar_banco_emite_progreso -q`
Expected: FAIL (`refrescar_banco() got an unexpected keyword argument 'on_progreso'`).

- [ ] **Step 3: Reemplazar `refrescar_banco`** en `app/obsolescencia_banco.py` por esta versión (añade `on_progreso=None` y emite eventos; sin callback, comportamiento idéntico):

```python
def refrescar_banco(db: Session, equipo_id: int, hoy: date, *,
                    limite: int = 10, consultar, on_progreso=None) -> dict:
    """Re-verifica hasta `limite` productos del banco vía `consultar` (inyectable),
    registra los hallazgos y devuelve el report actualizado. Best-effort: un
    `consultar` que devuelve None o falla no rompe el refresco.

    Si se pasa `on_progreso`, se invoca con un dict por evento:
    `{"tipo":"actual","indice","total","producto"}` antes de consultar cada
    producto, y `{"tipo":"resultado","indice","total","producto",
    "estado_anterior","estado_nuevo","cambio"}` después de registrar."""
    prods = productos_de_equipo(db, equipo_id)[:limite]
    total = len(prods)
    for i, p in enumerate(prods, start=1):
        if on_progreso is not None:
            on_progreso({"tipo": "actual", "indice": i, "total": total, "producto": p})
        anterior = p.estado_ciclo_vida
        try:
            v = consultar(p, _url_fabricante(db, p))
        except Exception:
            v = None
        cambio = False
        if v:
            res = obsolescencia_service.registrar_hallazgo(
                db, p.id, v["estado"], hoy=hoy, fecha_evento=v.get("fecha_evento"),
                url=v.get("url_fuente"), resumen=v.get("resumen"))
            cambio = bool(res.get("cambio"))
        if on_progreso is not None:
            on_progreso({"tipo": "resultado", "indice": i, "total": total, "producto": p,
                         "estado_anterior": anterior, "estado_nuevo": p.estado_ciclo_vida,
                         "cambio": cambio})
    return informe_banco(db, equipo_id, hoy)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py -q`
Expected: PASS (todos los de ese fichero, incluidos los previos de `refrescar_banco`).

- [ ] **Step 5: Commit**

```bash
git add app/obsolescencia_banco.py tests/test_obsolescencia_banco.py
git commit -m "feat(obsolescencia): refrescar_banco emite progreso por on_progreso"
```

---

## Task 2: Schemas de progreso

**Files:**
- Modify: `backend/app/schemas.py` (APPEND tras `ObsolescenciaBancoOut`)

- [ ] **Step 1: Add the schemas** al final del bloque de obsolescencia-banco en `schemas.py` (después de `class ObsolescenciaBancoOut`):

```python
# --- Progreso del refresco de obsolescencia por banco ---
class RefrescoIniciado(BaseModel):
    job_id: str
    total: int


class RefrescoActual(BaseModel):
    part_number: str
    fabricante: Optional[str] = None
    descripcion: str


class RefrescoResultadoItem(BaseModel):
    part_number: str
    descripcion: str
    estado_anterior: Optional[str] = None
    estado_nuevo: Optional[str] = None
    cambio: bool


class RefrescoProgreso(BaseModel):
    job_id: str
    equipo_id: int
    total: int
    indice: int
    estado: str  # en_curso | terminado | error
    actual: Optional[RefrescoActual] = None
    resultados: list[RefrescoResultadoItem] = Field(default_factory=list)
    report: Optional[ObsolescenciaBancoOut] = None
    error: Optional[str] = None
```

- [ ] **Step 2: Verify imports**

Run: `.venv/Scripts/python -c "from app.schemas import RefrescoIniciado, RefrescoProgreso; print('ok')"`
Expected: imprime `ok`. (`BaseModel`, `Optional`, `Field`, `date` ya están importados; `ObsolescenciaBancoOut` está definido antes en el fichero.)

- [ ] **Step 3: Commit**

```bash
git add app/schemas.py
git commit -m "feat(obsolescencia): schemas de progreso del refresco"
```

---

## Task 3: Store de jobs en memoria (`obsolescencia_jobs.py`)

**Files:**
- Create: `backend/app/obsolescencia_jobs.py`
- Test: `backend/tests/test_obsolescencia_jobs.py`

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_obsolescencia_jobs.py`:

```python
from datetime import date

from sqlalchemy.orm import sessionmaker

from app import models, obsolescencia_jobs


def _seed_verificable(db):
    """Equipo con 1 componente verificable (fabricante+pn, estado activo)."""
    pe = models.Producto(part_number="EQ-1", tipo="equipo", descripcion="Banco")
    db.add(pe); db.flush()
    eq = models.Equipo(numero_serie="SNJ", producto_id=pe.id, estado="operativo")
    db.add(eq); db.flush()
    pc = models.Producto(part_number="P-ACT", tipo="componente", descripcion="Cable",
                         fabricante="Beta", pn_fabricante="BET-1", estado_ciclo_vida="activo")
    db.add(pc); db.flush()
    db.add(models.Componente(numero_serie="C1", producto_id=pc.id, equipo_id=eq.id, posicion="1"))
    db.commit()
    return eq.id


def test_ejecutar_job_termina_con_progreso_y_report(memory_engine, db_session):
    eq_id = _seed_verificable(db_session)
    Factory = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)

    def fake(p, url):
        return {"estado": "obsoleto", "fecha_evento": None,
                "url_fuente": "http://b/eol", "resumen": "x"}

    job_id = obsolescencia_jobs.crear_job(eq_id, 1)
    obsolescencia_jobs.ejecutar(job_id, eq_id, limite=5, consultar=fake, db_factory=Factory)

    snap = obsolescencia_jobs.snapshot(job_id)
    assert snap["estado"] == "terminado"
    assert snap["indice"] == 1
    assert snap["total"] == 1
    assert snap["actual"] is None
    assert len(snap["resultados"]) == 1
    assert snap["resultados"][0]["part_number"] == "P-ACT"
    assert snap["resultados"][0]["estado_nuevo"] == "obsoleto"
    assert snap["resultados"][0]["cambio"] is True
    assert snap["report"]["resumen"]["total"] == 1


def test_snapshot_job_desconocido_es_none():
    assert obsolescencia_jobs.snapshot("noexiste") is None


def test_ejecutar_job_error_si_equipo_inexistente(memory_engine):
    Factory = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)
    job_id = obsolescencia_jobs.crear_job(9999, 0)
    obsolescencia_jobs.ejecutar(job_id, 9999, limite=5,
                                consultar=lambda p, u: None, db_factory=Factory)
    snap = obsolescencia_jobs.snapshot(job_id)
    assert snap["estado"] == "error"
    assert snap["error"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_jobs.py -q`
Expected: FAIL (ImportError de `app.obsolescencia_jobs`).

- [ ] **Step 3: Implement** — create `backend/app/obsolescencia_jobs.py`:

```python
"""Store en memoria + runner del refresco de obsolescencia por banco con progreso.
Proceso único (uvicorn on-prem): un job = un refresco en curso de un equipo.
No persiste: un reinicio del backend pierde los jobs (aceptable)."""
from __future__ import annotations

import secrets
import threading
from datetime import date

from app import obsolescencia_banco
from app.db import SessionLocal

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def crear_job(equipo_id: int, total: int) -> str:
    job_id = secrets.token_hex(8)
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "equipo_id": equipo_id,
            "total": total,
            "indice": 0,
            "estado": "en_curso",
            "actual": None,
            "resultados": [],
            "report": None,
            "error": None,
        }
    return job_id


def snapshot(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        copia = dict(job)
        copia["resultados"] = list(job["resultados"])
        copia["actual"] = dict(job["actual"]) if job["actual"] else None
        return copia


def _hacer_callback(job_id: str):
    def cb(ev: dict) -> None:
        p = ev["producto"]
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is None:
                return
            if ev["tipo"] == "actual":
                job["indice"] = ev["indice"]
                job["actual"] = {"part_number": p.part_number,
                                 "fabricante": p.fabricante,
                                 "descripcion": p.descripcion}
            elif ev["tipo"] == "resultado":
                job["resultados"].append({
                    "part_number": p.part_number,
                    "descripcion": p.descripcion,
                    "estado_anterior": ev["estado_anterior"],
                    "estado_nuevo": ev["estado_nuevo"],
                    "cambio": ev["cambio"],
                })
    return cb


def ejecutar(job_id: str, equipo_id: int, *, limite: int, consultar,
             db_factory=SessionLocal) -> None:
    """Corre el refresco (síncrono) y va volcando el progreso al store. Pensado
    para ejecutarse en un hilo. `db_factory` inyectable para tests."""
    db = db_factory()
    try:
        report = obsolescencia_banco.refrescar_banco(
            db, equipo_id, date.today(), limite=limite, consultar=consultar,
            on_progreso=_hacer_callback(job_id))
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is not None:
                job["report"] = report
                job["actual"] = None
                job["estado"] = "terminado"
    except Exception as exc:
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is not None:
                job["estado"] = "error"
                job["error"] = str(exc)
    finally:
        db.close()


def lanzar(job_id: str, equipo_id: int, *, limite: int, consultar) -> None:
    """Arranca `ejecutar` en un hilo daemon (no bloquea la petición HTTP)."""
    threading.Thread(
        target=ejecutar, args=(job_id, equipo_id),
        kwargs={"limite": limite, "consultar": consultar}, daemon=True,
    ).start()
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_jobs.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/obsolescencia_jobs.py tests/test_obsolescencia_jobs.py
git commit -m "feat(obsolescencia): store de jobs en memoria + runner con progreso"
```

---

## Task 4: Endpoints `iniciar` + `progreso`

**Files:**
- Modify: `backend/app/routers/obsolescencia_banco.py` (imports + 2 rutas nuevas)
- Test: `backend/tests/test_obsolescencia_banco_router.py` (APPEND tests)

- [ ] **Step 1: Write the failing tests** — APPEND a `tests/test_obsolescencia_banco_router.py` (el fichero ya tiene `_seed(db)`, e importa `models`, `get_consultar_fabricante`, `app`):

```python
def test_refrescar_iniciar_y_progreso(client, db_session, memory_engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app import obsolescencia_jobs

    eq_id = _seed(db_session)  # 1 componente verificable (P-ACT, activo)
    Factory = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)

    # consultar inyectado (sin red) + lanzar inline (sin hilo) usando el motor de test
    app.dependency_overrides[get_consultar_fabricante] = lambda: (
        lambda p, url: {"estado": "obsoleto", "fecha_evento": None,
                        "url_fuente": "http://b/eol", "resumen": "x"})
    monkeypatch.setattr(
        obsolescencia_jobs, "lanzar",
        lambda job_id, equipo_id, **kw: obsolescencia_jobs.ejecutar(
            job_id, equipo_id, db_factory=Factory, **kw))
    try:
        r = client.post(f"/api/equipos/{eq_id}/obsolescencia/refrescar/iniciar?limite=5")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1 and body["job_id"]

        g = client.get(f"/api/equipos/{eq_id}/obsolescencia/refrescar/{body['job_id']}")
        assert g.status_code == 200
        prog = g.json()
        assert prog["estado"] == "terminado"
        assert prog["indice"] == 1
        assert prog["resultados"][0]["estado_nuevo"] == "obsoleto"
        assert prog["report"]["resumen"]["total"] == 1
    finally:
        app.dependency_overrides.pop(get_consultar_fabricante, None)


def test_refrescar_iniciar_equipo_inexistente_404(client):
    app.dependency_overrides[get_consultar_fabricante] = lambda: (lambda p, url: None)
    try:
        r = client.post("/api/equipos/9999/obsolescencia/refrescar/iniciar")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_consultar_fabricante, None)


def test_refrescar_progreso_job_desconocido_404(client):
    assert client.get("/api/equipos/1/obsolescencia/refrescar/nope").status_code == 404


def test_refrescar_progreso_requiere_auth(client_sin_auth):
    assert client_sin_auth.get("/api/equipos/1/obsolescencia/refrescar/x").status_code == 401
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco_router.py -q`
Expected: FAIL (404 en `/refrescar/iniciar` y `/refrescar/{job}` porque las rutas no existen; el de auth puede pasar ya).

- [ ] **Step 3a: Update imports** en `app/routers/obsolescencia_banco.py`. La línea de import del paquete `app` actualmente es:

```python
from app import models, obsolescencia_banco, obsolescencia_export
```
Déjala como:
```python
from app import models, obsolescencia_banco, obsolescencia_export, obsolescencia_jobs
```
Y en el import de schemas, añade los nuevos:
```python
from app.schemas import ObsolescenciaBancoOut, RefrescoIniciado, RefrescoProgreso
```
(la línea actual importa solo `ObsolescenciaBancoOut`).

- [ ] **Step 3b: Add the two routes** al final de `app/routers/obsolescencia_banco.py`:

```python
@router.post("/{equipo_id}/obsolescencia/refrescar/iniciar", response_model=RefrescoIniciado)
def refrescar_iniciar(equipo_id: int, limite: int = Query(default=10, ge=1, le=50),
                      db: Session = Depends(get_db),
                      consultar=Depends(get_consultar_fabricante)):
    _equipo_o_404(db, equipo_id)
    total = len(obsolescencia_banco.productos_de_equipo(db, equipo_id)[:limite])
    job_id = obsolescencia_jobs.crear_job(equipo_id, total)
    obsolescencia_jobs.lanzar(job_id, equipo_id, limite=limite, consultar=consultar)
    return {"job_id": job_id, "total": total}


@router.get("/{equipo_id}/obsolescencia/refrescar/{job_id}", response_model=RefrescoProgreso)
def refrescar_progreso(equipo_id: int, job_id: str):
    snap = obsolescencia_jobs.snapshot(job_id)
    if snap is None or snap["equipo_id"] != equipo_id:
        raise HTTPException(status_code=404, detail="job no encontrado")
    return snap
```

(El GET de progreso lee del store en memoria, no necesita `db`. `Query`, `Depends`, `HTTPException`,
`get_consultar_fabricante`, `_equipo_o_404` ya existen en el fichero del router. Si `Query` no estuviera
importado, añádelo al import de fastapi.)

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco_router.py -q`
Expected: PASS (los previos + 4 nuevos). Luego la suite completa `.venv/Scripts/python -m pytest -q` sin regresiones.

- [ ] **Step 5: Commit**

```bash
git add app/routers/obsolescencia_banco.py tests/test_obsolescencia_banco_router.py
git commit -m "feat(obsolescencia): endpoints iniciar/progreso del refresco por banco"
```

---

## Task 5: Prompt Lovable del popup de progreso

**Files:**
- Create: `docs/lovable/34_progreso_refresco_obsolescencia.md`
- Modify: `docs/lovable/README.md` (añadir fila 34 en la tabla)

Esta tarea **no toca código del frontend** (lo genera Lovable al pegar el prompt). Solo se redacta el prompt y se commitea. No hay pytest.

- [ ] **Step 1: Write the prompt** — create `docs/lovable/34_progreso_refresco_obsolescencia.md` con este contenido:

````markdown
# Prompt 34 — Popup de progreso del refresco de obsolescencia por banco

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, helper `api<T>()` en `@/lib/api`
(inyecta Bearer), tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`, componentes `<EstadoCicloBadge
estado url />` (prompt 32) y `ReportObsolescenciaDialog` (prompt 33)). **NO cambies nombres de campo del
backend. No inventes endpoints ni campos fuera de los listados.** Todo va protegido (el `api()` manda token).

Hoy el botón **"Refrescar estado"** del `ReportObsolescenciaDialog` llama a un refresco síncrono y muestra
un spinner ciego. Este prompt lo cambia: el refresco corre en segundo plano en el backend y un **popup
muestra el avance en vivo** (barra X/N + componente actual + log de resultados), sondeando cada 1 s.

## 1. Tipos en `src/lib/types.ts`
```ts
export interface RefrescoIniciado {
  job_id: string;
  total: number;
}

export interface RefrescoActual {
  part_number: string;
  fabricante: string | null;
  descripcion: string;
}

export interface RefrescoResultadoItem {
  part_number: string;
  descripcion: string;
  estado_anterior: EstadoCicloVida | null;
  estado_nuevo: EstadoCicloVida | null;
  cambio: boolean;
}

export interface RefrescoProgreso {
  job_id: string;
  equipo_id: number;
  total: number;
  indice: number;
  estado: "en_curso" | "terminado" | "error";
  actual: RefrescoActual | null;
  resultados: RefrescoResultadoItem[];
  report: ObsolescenciaBancoReport | null;  // presente cuando estado==="terminado"
  error: string | null;
}
```

## 2. Componente `RefrescoObsolescenciaProgresoDialog`
Props: `{ equipoId: number; open: boolean; onOpenChange: (v:boolean)=>void; onTerminado: (report: ObsolescenciaBancoReport)=>void }`.

Comportamiento:
- Al abrir (`open` pasa a true): `POST /api/equipos/{equipoId}/obsolescencia/refrescar/iniciar?limite=10`
  con `api<RefrescoIniciado>(..., { method: "POST" })` → guarda `{ job_id, total }`.
- **Sondeo**: cada **1000 ms** (`setInterval`) `api<RefrescoProgreso>('/api/equipos/{equipoId}/obsolescencia/refrescar/{job_id}')`.
  Guarda la respuesta en estado. **Limpia el interval** al desmontar, al cerrar, y cuando `estado` deja de ser `"en_curso"`.
- Render mientras `en_curso`:
  - **Barra de progreso** con `indice / total` (shadcn `Progress`, value = `total ? indice/total*100 : 0`) + texto `Chequeando {indice}/{total}`.
  - **Tarjeta "actual"** (si `actual`): `actual.part_number` + `actual.fabricante ?? "—"` + `actual.descripcion`, con un spinner pequeño.
  - **Log en vivo**: lista (orden de llegada) de `resultados[]`: `part_number` + `descripcion` + `<EstadoCicloBadge estado={r.estado_nuevo} />`; si `r.cambio`, marca la fila (icono/realce, p.ej. punto lila) indicando que cambió.
- `estado === "terminado"`: para el sondeo; muestra "Completado · {nº de resultados con cambio} cambios"; botón **Cerrar** que llama `onTerminado(prog.report)` (si `report`) y `onOpenChange(false)`.
- `estado === "error"`: muestra `error` + botón Cerrar. No rompe el dialog padre.
- Errores de red en el sondeo (p.ej. 404 del job): corta el interval y muestra un aviso + Cerrar.

## 3. Wiring en `ReportObsolescenciaDialog` (prompt 33)
- El botón **"Refrescar estado"** ya NO llama al refresco síncrono: ahora abre `RefrescoObsolescenciaProgresoDialog`
  (estado local `openRefresco`).
- `onTerminado={(report) => { /* refresca la tabla del report con el report recibido, o vuelve a hacer
  GET /api/equipos/{id}/obsolescencia */ }}`.
- El resto del `ReportObsolescenciaDialog` no se toca.

## 4. Notas
- Endpoints (solo estos): `POST /api/equipos/{id}/obsolescencia/refrescar/iniciar?limite=10` → `RefrescoIniciado`;
  `GET /api/equipos/{id}/obsolescencia/refrescar/{job_id}` → `RefrescoProgreso`.
- El refresco es lento (consulta a fabricantes con un agente): es normal que pasen segundos entre resultados.
- Si el usuario cierra el popup a mitad, el backend sigue hasta terminar; no hay cancelación.
- Reutiliza `EstadoCicloVida`/`EstadoCicloBadge` del prompt 32 y `ObsolescenciaBancoReport` del prompt 33.
````

- [ ] **Step 2: Add the README row** — en `docs/lovable/README.md`, en la tabla de prompts, tras la fila `| 33 | ...`, añade:

```markdown
| 34 | `34_progreso_refresco_obsolescencia.md` | **Popup de progreso del refresco por banco**: el botón "Refrescar estado" del report abre un popup con barra X/N + componente actual + log en vivo (sondeo cada 1 s). Backend `POST .../refrescar/iniciar`, `GET .../refrescar/{job_id}`. |
```

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/34_progreso_refresco_obsolescencia.md docs/lovable/README.md
git commit -m "docs(lovable): prompt 34 popup de progreso del refresco de obsolescencia"
```

---

## Task 6: Suite completa + verificación

- [ ] **Step 1: Full suite green**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS (los previos 441 + los nuevos de Tasks 1/3/4). Si algún test global lockea la `postventa.db` real, parar uvicorn antes.

- [ ] **Step 2: Smoke en vivo (opcional, requiere backend)**

Arrancar: `.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8020`. Con un token válido y el banco real (id 1):
- `POST /api/equipos/1/obsolescencia/refrescar/iniciar?limite=1` → `{job_id, total}`.
- `GET /api/equipos/1/obsolescencia/refrescar/{job_id}` repetido → ver `estado` pasar de `en_curso` (con `actual`/`resultados` poblándose) a `terminado` con `report`. (Con `limite=1` solo consulta 1 componente → 1 llamada a Claude headless.)

- [ ] **Step 3: Commit final (si hubo ajustes)**

```bash
git add -A
git commit -m "test: suite verde progreso del refresco de obsolescencia"
```

---

## Notas de integración

- **Concurrencia/SQLite:** el job corre en un hilo daemon con su propia `SessionLocal` (`check_same_thread=False` ya configurado). `registrar_hallazgo` commitea por producto; el GET de progreso lee del store en memoria (no de la BD), así que no compite por la conexión.
- **Frontend:** Task 5 solo redacta el prompt Lovable; la implementación real aterriza cuando el usuario lo pega y se sincroniza el submódulo (patrón habitual).
- **Rama:** `feat/progreso-refresco-obsolescencia`. Al terminar el backend (Tasks 1-4,6), mergear a `master`. El prompt (Task 5) viaja en el mismo merge.
```
