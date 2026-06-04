# Resumen de servicio (KPIs cabecera) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer un endpoint `GET /api/analitica/resumen` con los 4 KPIs "en vivo" de la cabecera de postventa (incidencias abiertas, RMA abierto, en reparación, tiempo medio de cierre 30d) y actualizar la cabecera del frontend.

**Architecture:** Una función pura `resumen_servicio(db, hoy)` en `app/analitica_incidencias.py` calcula los 4 números desde la tabla de incidencias; un schema `ResumenServicioOut` y un endpoint fino en `app/routers/analitica.py` la exponen. El endpoint de analítica completa NO se toca. El frontend (Lovable, prompt 16) re-cablea las 4 tarjetas.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2, Pydantic v2, pytest.

**Convenciones:** tests en `backend/tests/` (fixtures `db_session`/`client`); ejecutar desde `backend/` con `.venv\Scripts\python.exe -m pytest -q`. Commit por tarea, mensaje en español terminando con la línea Co-Authored-By habitual.

**Contexto del módulo:** `backend/app/analitica_incidencias.py` ya importa `from datetime import date, timedelta`, tiene el helper `_media(valores) -> Optional[float]` (redondeo a 1 decimal, `None` si vacío), `from sqlalchemy.orm import Session`, `from app import garantia, models`, y un bloque `from app.schemas import (AnaliticaIncidenciasOut, ConteoItem, KpiTiempo, KpiTiempoItem, PuntoTendencia, RankingItem, ResumenGarantia)`. `models.Incidencia` tiene `estado`, `tipo`, `prioridad`, `fecha_apertura` (date), `fecha_cierre` (Optional[date]).

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---------|-----------------|--------|
| `backend/app/schemas.py` | + `ResumenServicioOut`. | Modificar |
| `backend/app/analitica_incidencias.py` | + función `resumen_servicio(db, hoy)`. | Modificar |
| `backend/app/routers/analitica.py` | + endpoint `GET /api/analitica/resumen`. | Modificar |
| `backend/tests/test_resumen_servicio.py` | tests de la función + endpoint. | Crear |
| `docs/lovable/16_resumen_servicio.md` | Prompt Lovable. | Crear |
| `docs/lovable/README.md` | Índice. | Modificar |

---

## Task 1: Schema + función `resumen_servicio`

**Files:**
- Modify: `backend/app/schemas.py` (al final, sección Analítica)
- Modify: `backend/app/analitica_incidencias.py` (import + nueva función al final)
- Test: `backend/tests/test_resumen_servicio.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_resumen_servicio.py`:

```python
from datetime import date

from app import analitica_incidencias as ana
from app import models


def _inc(db, codigo, tipo="rma", prioridad="media", estado="abierta",
         apertura=date(2026, 6, 1), cierre=None):
    i = models.Incidencia(
        codigo=codigo, tipo=tipo, prioridad=prioridad, estado=estado,
        titulo="t", descripcion_problema="d", fecha_apertura=apertura, fecha_cierre=cierre,
    )
    db.add(i); db.flush()
    return i


def _seed(db):
    _inc(db, "RMA-0001", tipo="rma", prioridad="alta", estado="abierta")
    _inc(db, "RMA-0002", tipo="rma", prioridad="media", estado="en_reparacion")
    _inc(db, "CAL-0001", tipo="calibracion", prioridad="media", estado="diagnostico")
    # cerrada dentro de los 30 dias (hoy=2026-06-05 -> inicio 2026-05-06): 10 dias
    _inc(db, "RMA-0003", tipo="rma", estado="cerrada", apertura=date(2026, 5, 20), cierre=date(2026, 5, 30))
    # cerrada dentro de los 30 dias: 20 dias
    _inc(db, "ST-0001", tipo="soporte_tecnico", estado="cerrada", apertura=date(2026, 5, 15), cierre=date(2026, 6, 4))
    # cerrada FUERA de los 30 dias (cierre 2026-04-20 < 2026-05-06) -> excluida
    _inc(db, "RMA-0004", tipo="rma", estado="cerrada", apertura=date(2026, 4, 1), cierre=date(2026, 4, 20))


def test_resumen_cuenta_abiertas_rma_reparacion(db_session):
    _seed(db_session)
    r = ana.resumen_servicio(db_session, hoy=date(2026, 6, 5))
    assert r.incidencias_abiertas == 3        # RMA-0001, RMA-0002, CAL-0001
    assert r.incidencias_abiertas_alta == 1   # RMA-0001
    assert r.rma_abierto == 2                  # RMA-0001, RMA-0002 (las rma cerradas no cuentan)
    assert r.en_reparacion == 1                # RMA-0002


def test_resumen_tiempo_medio_cierre_30d(db_session):
    _seed(db_session)
    r = ana.resumen_servicio(db_session, hoy=date(2026, 6, 5))
    assert r.cerradas_30d == 2                  # RMA-0003 (10d) + ST-0001 (20d); RMA-0004 excluida
    assert r.tiempo_medio_cierre_dias == 15.0   # (10 + 20) / 2


def test_resumen_vacio(db_session):
    r = ana.resumen_servicio(db_session, hoy=date(2026, 6, 5))
    assert r.incidencias_abiertas == 0
    assert r.rma_abierto == 0
    assert r.en_reparacion == 0
    assert r.cerradas_30d == 0
    assert r.tiempo_medio_cierre_dias is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_resumen_servicio.py -q`
Expected: FAIL (`AttributeError: ... has no attribute 'resumen_servicio'`).

- [ ] **Step 3: Add the schema**

En `backend/app/schemas.py`, al FINAL del archivo (tras los schemas de Analítica existentes):
```python
class ResumenServicioOut(BaseModel):
    incidencias_abiertas: int
    incidencias_abiertas_alta: int
    rma_abierto: int
    en_reparacion: int
    cerradas_30d: int
    tiempo_medio_cierre_dias: Optional[float] = None
```

- [ ] **Step 4: Add the function**

En `backend/app/analitica_incidencias.py`:
1. Añade `ResumenServicioOut` al bloque `from app.schemas import (...)` (junto a los otros).
2. Al FINAL del archivo, añade:
```python
def resumen_servicio(db: Session, hoy: date) -> ResumenServicioOut:
    incs = db.query(models.Incidencia).all()
    abiertas = [i for i in incs if i.estado != "cerrada"]
    inicio_30d = hoy - timedelta(days=30)
    cerradas_30d = [
        i for i in incs
        if i.fecha_cierre is not None and i.fecha_cierre >= inicio_30d
    ]
    tiempos = [(i.fecha_cierre - i.fecha_apertura).days for i in cerradas_30d]
    return ResumenServicioOut(
        incidencias_abiertas=len(abiertas),
        incidencias_abiertas_alta=sum(1 for i in abiertas if i.prioridad == "alta"),
        rma_abierto=sum(1 for i in abiertas if i.tipo == "rma"),
        en_reparacion=sum(1 for i in incs if i.estado == "en_reparacion"),
        cerradas_30d=len(cerradas_30d),
        tiempo_medio_cierre_dias=_media(tiempos),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_resumen_servicio.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/analitica_incidencias.py backend/tests/test_resumen_servicio.py
git commit -m "feat: resumen_servicio (KPIs cabecera) + schema ResumenServicioOut"
```
(Mensaje termina con la línea `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.)

---

## Task 2: Endpoint `GET /api/analitica/resumen`

**Files:**
- Modify: `backend/app/routers/analitica.py`
- Test: `backend/tests/test_resumen_servicio.py`

- [ ] **Step 1: Write the failing test**

Añade a `backend/tests/test_resumen_servicio.py`:

```python
def test_endpoint_resumen_vacio(client):
    r = client.get("/api/analitica/resumen")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["incidencias_abiertas"] == 0
    assert b["tiempo_medio_cierre_dias"] is None


def test_endpoint_resumen_con_datos(client):
    p = client.post("/api/productos", json={"part_number": "PN-R", "tipo": "equipo", "descripcion": "d"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-R", "producto_id": p["id"]}).json()
    client.post("/api/incidencias", json={"equipo_id": eq["id"], "titulo": "a", "descripcion_problema": "x",
        "tipo": "rma", "prioridad": "alta", "fecha_apertura": "2026-06-01"})
    r = client.get("/api/analitica/resumen")
    assert r.status_code == 200
    b = r.json()
    assert b["incidencias_abiertas"] == 1
    assert b["incidencias_abiertas_alta"] == 1
    assert b["rma_abierto"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_resumen_servicio.py -k endpoint -q`
Expected: FAIL (404, endpoint no existe).

- [ ] **Step 3: Add the endpoint**

En `backend/app/routers/analitica.py`, importa `ResumenServicioOut` (añádelo a `from app.schemas import ...`,
que actualmente importa `AnaliticaIncidenciasOut`) y añade el endpoint tras el de `incidencias`:
```python
@router.get("/resumen", response_model=ResumenServicioOut)
def resumen(db: Session = Depends(get_db)) -> ResumenServicioOut:
    return ana.resumen_servicio(db, hoy=date.today())
```
(`date`, `Depends`, `get_db`, `ana` y `Session` ya están importados en ese router.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_resumen_servicio.py -q`
Expected: PASS (todos verde).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/analitica.py backend/tests/test_resumen_servicio.py
git commit -m "feat: endpoint GET /api/analitica/resumen"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 3: Suite completa + smoke en vivo

**Files:** ninguno (verificación).

- [ ] **Step 1: Run the full suite**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest -q`
Expected: PASS, todos verde (161 previos + los nuevos).

- [ ] **Step 2: Smoke en vivo**

Arranca el backend:
```
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```
En otra shell:
```
curl -s "http://127.0.0.1:8020/api/analitica/resumen"
```
Expected: 200 con las claves `incidencias_abiertas`, `incidencias_abiertas_alta`, `rma_abierto`,
`en_reparacion`, `cerradas_30d`, `tiempo_medio_cierre_dias`. Con los datos demo (58 incidencias, todas
`tipo=rma`), `incidencias_abiertas` y `rma_abierto` coincidirán; revisar que los números cuadran con
`GET /api/incidencias?abiertas=true`.

- [ ] **Step 3: Parar el backend**

`netstat -ano | findstr :8020` → `taskkill /PID <pid> /T /F`.

- [ ] **Step 4: Commit (solo si hubo ajustes)**

Si todo verde sin cambios, no hay commit.

---

## Task 4: Prompt Lovable 16 (cabecera de resumen)

**Files:**
- Create: `docs/lovable/16_resumen_servicio.md`
- Modify: `docs/lovable/README.md`

- [ ] **Step 1: Write the Lovable prompt**

Crear `docs/lovable/16_resumen_servicio.md` con:

```markdown
# Prompt 16 — Cabecera "Resumen de servicio · EN VIVO" (KPIs)

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()`, tipos en `@/lib/types`, paleta lila `#9e007e`, shadcn). NO cambies nombres de campo.

## 1. Tipo en `src/lib/types.ts`
```ts
export interface ResumenServicio {
  incidencias_abiertas: number;
  incidencias_abiertas_alta: number;
  rma_abierto: number;
  en_reparacion: number;
  cerradas_30d: number;
  tiempo_medio_cierre_dias: number | null;
}
```

## 2. Cabecera "Resumen de servicio · EN VIVO / Operaciones de postventa"
Llama `GET /api/analitica/resumen` (`useQuery`) y pinta **4 tarjetas** (sustituyendo las actuales,
y ELIMINANDO la tarjeta "SLA en riesgo"):
1. **Incidencias abiertas** = `incidencias_abiertas`; subtítulo "{incidencias_abiertas_alta} de alta prioridad".
2. **RMA abierto** = `rma_abierto`; subtítulo "sin cerrar".
3. **En reparación** = `en_reparacion`; subtítulo "trabajos en curso".
4. **Tiempo medio de cierre** = `tiempo_medio_cierre_dias` (formatea como "{n} d", o "—" si es null);
   subtítulo "{cerradas_30d} cerradas · 30d".

Mantén el enlace "Ver analítica completa →" hacia `/analitica`. Estilo y layout iguales a los actuales
(mismas tarjetas, solo cambian etiquetas/valores/fuente de datos).
```

- [ ] **Step 2: Update README índice**

En `docs/lovable/README.md`, en "Mejoras sueltas", añade:
```markdown
| 16 | `16_resumen_servicio.md` | **Cabecera "Resumen de servicio · EN VIVO"**: 4 KPIs (Incidencias abiertas · RMA abierto · En reparación · Tiempo medio de cierre 30d), elimina "SLA en riesgo". Backend `GET /api/analitica/resumen` → `ResumenServicioOut`. |
```

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/16_resumen_servicio.md docs/lovable/README.md
git commit -m "docs: prompt Lovable 16 — cabecera resumen de servicio (KPIs)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

- [ ] **Step 4: (Manual, fuera del plan)** Pegar el prompt 16 en Lovable; luego `git pull` del submódulo
  `frontend`, `bun install`, `bun x tsc --noEmit`, validación de contrato y smoke visual de la cabecera.

---

## Self-review (cobertura del spec)

- **`resumen_servicio` con los 6 campos (abiertas, alta, rma_abierto, en_reparacion, cerradas_30d, tiempo_medio_cierre):** Task 1. ✅
- **Ventana 30 días por `fecha_cierre`; tiempo = apertura→cierre; null si vacío:** Task 1 (test excluye la cerrada de hace 40+ días). ✅
- **"abiertas" = estado != cerrada, todos los tipos:** Task 1. ✅
- **Endpoint `GET /api/analitica/resumen` sin filtros:** Task 2. ✅
- **No toca `/analitica/incidencias` ni su MTTR:** ninguna tarea lo modifica. ✅
- **Frontend: 4 tarjetas nuevas, elimina SLA en riesgo:** Task 4 (prompt). ✅
- **Fuera de alcance (MTTR pantalla completa, SLA configurable, subtítulos extra):** no implementado. ✅

Consistencia de tipos: `ResumenServicioOut` (6 campos), `resumen_servicio(db, hoy)`, endpoint
`/api/analitica/resumen` — usados igual en Tasks 1-2 y el prompt 4.
```
