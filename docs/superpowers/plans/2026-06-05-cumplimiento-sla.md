# Cumplimiento de SLA por nivel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Medir cada incidencia (de equipo bajo contrato vigente) contra el SLA de su nivel (respuesta/resolución en días), exponer el SLA por incidencia y un endpoint de cumplimiento `GET /api/sla`.

**Architecture:** Lógica pura `app/sla.py` (duck-typed, `hoy` inyectable), servicio `app/sla_service.py` (BD), schemas + router + integración en `IncidenciaFicha`. Sin entidad ni migración nuevas.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest.

**Convenciones:** `./.venv/Scripts/python.exe -m pytest` desde `backend/`. NO uvicorn. Fixtures `client`/`client_sin_auth`. Routers protegidos con `dependencies=[Depends(get_current_user)]`. Estados incidencia: `abierta/diagnostico/en_reparacion/resuelta/cerrada`. `contratos.esta_vigente(con, hoy)`. `Equipo.contrato` relación.

---

## Task 1: Lógica pura `app/sla.py`

**Files:**
- Create: `backend/app/sla.py`
- Test: `backend/tests/test_sla_logica.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_sla_logica.py`:

```python
from datetime import date
from types import SimpleNamespace

from app import sla


def _inc(apertura, diag=None, ini_rep=None, reso=None, cierre=None):
    return SimpleNamespace(
        fecha_apertura=apertura, fecha_diagnostico=diag, fecha_inicio_reparacion=ini_rep,
        fecha_resolucion=reso, fecha_cierre=cierre)


def test_sla_niveles():
    assert sla.SLA_NIVELES["gold"]["respuesta_dias"] == 1
    assert sla.SLA_NIVELES["bronze"]["resolucion_dias"] == 15


def test_metrica_cumplida_en_plazo():
    m = sla.estado_metrica(date(2026, 6, 1), date(2026, 6, 2), 3, date(2026, 6, 10))
    assert m["estado"] == "en_plazo"
    assert m["objetivo_fecha"] == date(2026, 6, 4)


def test_metrica_cumplida_tarde_incumplido():
    m = sla.estado_metrica(date(2026, 6, 1), date(2026, 6, 9), 3, date(2026, 6, 10))
    assert m["estado"] == "incumplido"


def test_metrica_pendiente_en_riesgo():
    # objetivo dentro de poco, sin fecha real (gold resolucion 5d -> umbral riesgo = max(1,ceil(1.25))=2)
    m = sla.estado_metrica(date(2026, 6, 1), None, 5, date(2026, 6, 5))  # objetivo 06-06, quedan 1 día
    assert m["estado"] == "en_riesgo"


def test_metrica_pendiente_incumplido():
    m = sla.estado_metrica(date(2026, 6, 1), None, 3, date(2026, 6, 10))  # objetivo 06-04 < hoy
    assert m["estado"] == "incumplido"


def test_metrica_pendiente_en_plazo():
    m = sla.estado_metrica(date(2026, 6, 1), None, 15, date(2026, 6, 2))  # objetivo 06-16, lejos
    assert m["estado"] == "en_plazo"


def test_peor():
    assert sla.peor("en_plazo", "incumplido") == "incumplido"
    assert sla.peor("en_plazo", "en_riesgo") == "en_riesgo"
    assert sla.peor("en_plazo", "en_plazo") == "en_plazo"


def test_evaluar_usa_primera_fecha_respuesta():
    # respuesta real = fecha_inicio_reparacion (no hay diagnostico)
    inc = _inc(date(2026, 6, 1), diag=None, ini_rep=date(2026, 6, 2))
    ev = sla.evaluar(inc, "gold", date(2026, 6, 10))   # gold respuesta 1d -> objetivo 06-02; real 06-02 -> en_plazo
    assert ev["nivel"] == "gold"
    assert ev["respuesta"]["estado"] == "en_plazo"
    assert ev["respuesta"]["fecha_real"] == date(2026, 6, 2)
    assert ev["estado_global"] in {"en_plazo", "en_riesgo", "incumplido"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_sla_logica.py -v`
Expected: FAIL (`No module named 'app.sla'`)

- [ ] **Step 3: Write the module** `backend/app/sla.py`:

```python
"""Lógica pura de SLA por nivel de contrato. No importa models: duck-typing + `hoy` inyectable.
Granularidad en días (las fechas de incidencia son Date)."""
from __future__ import annotations

from datetime import date, timedelta
from math import ceil
from typing import Optional

SLA_NIVELES: dict[str, dict[str, int]] = {
    "gold": {"respuesta_dias": 1, "resolucion_dias": 5},
    "silver": {"respuesta_dias": 2, "resolucion_dias": 10},
    "bronze": {"respuesta_dias": 3, "resolucion_dias": 15},
}

_ORDEN = {"sin_sla": 0, "en_plazo": 1, "en_riesgo": 2, "incumplido": 3}


def _primera(*fechas: Optional[date]) -> Optional[date]:
    for f in fechas:
        if f is not None:
            return f
    return None


def estado_metrica(apertura: date, fecha_real: Optional[date], objetivo_dias: int, hoy: date) -> dict:
    objetivo = apertura + timedelta(days=objetivo_dias)
    if fecha_real is not None:
        estado = "en_plazo" if fecha_real <= objetivo else "incumplido"
    elif hoy > objetivo:
        estado = "incumplido"
    elif (objetivo - hoy).days <= max(1, ceil(objetivo_dias * 0.25)):
        estado = "en_riesgo"
    else:
        estado = "en_plazo"
    return {
        "objetivo_fecha": objetivo,
        "fecha_real": fecha_real,
        "dias_restantes": (objetivo - hoy).days,
        "estado": estado,
    }


def peor(*estados: str) -> str:
    return max(estados, key=lambda e: _ORDEN.get(e, 0)) if estados else "sin_sla"


def evaluar(incidencia, nivel: str, hoy: date) -> dict:
    objetivos = SLA_NIVELES[nivel]
    apertura = incidencia.fecha_apertura
    resp_real = _primera(
        getattr(incidencia, "fecha_diagnostico", None),
        getattr(incidencia, "fecha_inicio_reparacion", None),
        getattr(incidencia, "fecha_resolucion", None),
    )
    reso_real = _primera(
        getattr(incidencia, "fecha_resolucion", None),
        getattr(incidencia, "fecha_cierre", None),
    )
    respuesta = estado_metrica(apertura, resp_real, objetivos["respuesta_dias"], hoy)
    resolucion = estado_metrica(apertura, reso_real, objetivos["resolucion_dias"], hoy)
    return {
        "nivel": nivel,
        "respuesta": respuesta,
        "resolucion": resolucion,
        "estado_global": peor(respuesta["estado"], resolucion["estado"]),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_sla_logica.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add app/sla.py tests/test_sla_logica.py
git commit -m "feat: lógica pura de SLA (objetivos por nivel + estado por métrica)"
```

---

## Task 2: Servicio `app/sla_service.py`

**Files:**
- Create: `backend/app/sla_service.py`
- Test: `backend/tests/test_sla_service.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_sla_service.py`:

```python
from datetime import date

from app import models, sla_service


def _equipo_con_contrato(db, nivel="gold", vigente=True):
    p = models.Producto(part_number="6TL-SLA", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    fin = date(2100, 1, 1) if vigente else date(2021, 1, 1)
    con = models.ContratoMantenimiento(codigo="CTR-S1", nivel=nivel,
        fecha_inicio=date(2020, 1, 1), fecha_fin=fin)
    db.add(con); db.flush()
    eq = models.Equipo(numero_serie="S1", producto_id=p.id, contrato_id=con.id)
    db.add(eq); db.flush()
    return eq


def _inc(db, equipo_id, apertura, **fechas):
    inc = models.Incidencia(codigo="RMA-1", tipo="rma", estado="abierta",
        equipo_id=equipo_id, titulo="t", descripcion_problema="d", prioridad="media",
        fecha_apertura=apertura, **fechas)
    db.add(inc); db.flush()
    return inc


def test_incidencia_sin_contrato_sin_sla(db_session):
    p = models.Producto(part_number="6TL-X", tipo="equipo", descripcion="B")
    db_session.add(p); db_session.flush()
    eq = models.Equipo(numero_serie="X", producto_id=p.id)
    db_session.add(eq); db_session.flush()
    inc = _inc(db_session, eq.id, date(2026, 6, 1))
    assert sla_service.sla_de_incidencia(db_session, inc, date(2026, 6, 10)) is None


def test_incidencia_abierta_incumplida_aparece(db_session):
    eq = _equipo_con_contrato(db_session, nivel="gold")
    inc = _inc(db_session, eq.id, date(2026, 6, 1))   # gold resolucion 5d -> objetivo 06-06
    out = sla_service.construir_sla(db_session, date(2026, 6, 20))  # muy pasado
    ids = [i["incidencia"].id for i in out["incumplidas"]]
    assert inc.id in ids
    assert out["resumen"]["incumplidas"] >= 1


def test_cumplimiento_pct(db_session):
    eq = _equipo_con_contrato(db_session, nivel="gold")
    # resuelta en plazo: apertura 06-01, resolucion 06-03 (<= objetivo resolucion 06-06 y respuesta 06-02? no)
    _inc(db_session, eq.id, date(2026, 6, 1), estado="resuelta",
         fecha_diagnostico=date(2026, 6, 2), fecha_resolucion=date(2026, 6, 3))
    out = sla_service.construir_sla(db_session, date(2026, 6, 30))
    assert out["cumplimiento"]["total"] >= 1
    assert out["cumplimiento"]["resolucion_pct"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_sla_service.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write the service** `backend/app/sla_service.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import contratos, models, sla

_ABIERTAS = ("abierta", "diagnostico", "en_reparacion")


def _contrato_vigente_de(db: Session, incidencia, hoy: date):
    if incidencia.equipo_id is None:
        return None
    eq = db.get(models.Equipo, incidencia.equipo_id)
    if eq is None or eq.contrato is None or not contratos.esta_vigente(eq.contrato, hoy):
        return None
    return eq.contrato


def sla_de_incidencia(db: Session, incidencia, hoy: date) -> Optional[dict]:
    con = _contrato_vigente_de(db, incidencia, hoy)
    if con is None:
        return None
    return sla.evaluar(incidencia, con.nivel, hoy)


def construir_sla(db: Session, hoy: date) -> dict:
    en_riesgo: list[dict] = []
    incumplidas: list[dict] = []
    total = resp_ok = reso_ok = 0
    for inc in db.query(models.Incidencia).all():
        ev = sla_de_incidencia(db, inc, hoy)
        if ev is None:
            continue
        total += 1
        if ev["respuesta"]["estado"] == "en_plazo":
            resp_ok += 1
        if ev["resolucion"]["estado"] == "en_plazo":
            reso_ok += 1
        if inc.estado in _ABIERTAS:
            if ev["estado_global"] == "incumplido":
                incumplidas.append({"incidencia": inc, "sla": ev})
            elif ev["estado_global"] == "en_riesgo":
                en_riesgo.append({"incidencia": inc, "sla": ev})
    en_riesgo.sort(key=lambda x: x["sla"]["resolucion"]["dias_restantes"])
    incumplidas.sort(key=lambda x: x["sla"]["resolucion"]["dias_restantes"])
    cumplimiento = {
        "total": total,
        "respuesta_pct": round(100 * resp_ok / total, 1) if total else None,
        "resolucion_pct": round(100 * reso_ok / total, 1) if total else None,
    }
    return {
        "cumplimiento": cumplimiento,
        "en_riesgo": en_riesgo,
        "incumplidas": incumplidas,
        "resumen": {"en_riesgo": len(en_riesgo), "incumplidas": len(incumplidas)},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_sla_service.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/sla_service.py tests/test_sla_service.py
git commit -m "feat: sla_service (SLA por incidencia + cumplimiento + listas en riesgo/incumplidas)"
```

---

## Task 3: Schemas + router `GET /api/sla` + `IncidenciaFicha.sla`

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/sla.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/incidencias.py` (builder de `ficha`, ~línea 115)
- Test: `backend/tests/test_sla_api.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_sla_api.py`:

```python
def _equipo_contrato(client, nivel="gold"):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-SLAA", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": nivel, "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SLA1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    return eq["id"]


def _incidencia(client, equipo_id, apertura="2020-01-01"):
    return client.post("/api/incidencias", json={
        "tipo": "soporte_tecnico", "equipo_id": equipo_id, "titulo": "x",
        "descripcion_problema": "y", "prioridad": "media", "fecha_apertura": apertura}).json()


def test_sla_endpoint_incumplida(client):
    eid = _equipo_contrato(client)
    inc = _incidencia(client, eid, apertura="2020-01-01")  # abierta hace años -> incumplida
    out = client.get("/api/sla").json()
    ids = [i["incidencia"]["id"] for i in out["incumplidas"]]
    assert inc["id"] in ids
    item = next(i for i in out["incumplidas"] if i["incidencia"]["id"] == inc["id"])
    assert item["sla"]["estado_global"] == "incumplido"
    assert item["sla"]["nivel"] == "gold"
    assert set(out["resumen"].keys()) == {"en_riesgo", "incumplidas"}
    assert out["cumplimiento"]["total"] >= 1


def test_ficha_incidencia_incluye_sla(client):
    eid = _equipo_contrato(client)
    inc = _incidencia(client, eid, apertura="2020-01-01")
    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert ficha["sla"] is not None
    assert ficha["sla"]["nivel"] == "gold"


def test_ficha_incidencia_sin_contrato_sla_null(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-NOSLA", "tipo": "equipo", "descripcion": "B"}).json()
    eq = client.post("/api/equipos", json={"numero_serie": "NS1", "producto_id": prod["id"]}).json()
    inc = _incidencia(client, eq["id"])
    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert ficha["sla"] is None


def test_sla_protegido_401(client_sin_auth):
    assert client_sin_auth.get("/api/sla").status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_sla_api.py -v`
Expected: FAIL (404 + KeyError sla).

- [ ] **Step 3: Add schemas** en `backend/app/schemas.py` (sección nueva tras la de avisos):

```python
# --- SLA ---
_ESTADO_SLA = Literal["en_plazo", "en_riesgo", "incumplido", "sin_sla"]


class SlaMetrica(BaseModel):
    objetivo_fecha: date
    fecha_real: Optional[date] = None
    dias_restantes: int
    estado: _ESTADO_SLA


class SlaIncidencia(BaseModel):
    nivel: str
    respuesta: SlaMetrica
    resolucion: SlaMetrica
    estado_global: _ESTADO_SLA


class SlaIncidenciaItem(_ORM):
    incidencia: IncidenciaOut
    sla: SlaIncidencia


class CumplimientoSla(BaseModel):
    total: int
    respuesta_pct: Optional[float] = None
    resolucion_pct: Optional[float] = None


class ResumenSla(BaseModel):
    en_riesgo: int
    incumplidas: int


class SlaOut(BaseModel):
    cumplimiento: CumplimientoSla
    en_riesgo: list[SlaIncidenciaItem] = []
    incumplidas: list[SlaIncidenciaItem] = []
    resumen: ResumenSla
```

Y en la clase `IncidenciaFicha` añade el campo (tras `avances`):
```python
    sla: Optional[SlaIncidencia] = None
```
(`SlaIncidencia` se define ANTES o DESPUÉS de `IncidenciaFicha`? `IncidenciaFicha` está antes en el archivo;
usa forward-ref `Optional["SlaIncidencia"] = None` y añade `IncidenciaFicha.model_rebuild()` al final de la
sección SLA, junto a los demás `model_rebuild` si los hay.)

- [ ] **Step 4: Create the router** `backend/app/routers/sla.py`:

```python
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import sla_service
from app.db import get_db
from app.schemas import SlaOut

router = APIRouter(prefix="/api/sla", tags=["sla"])


@router.get("", response_model=SlaOut)
def cumplimiento(db: Session = Depends(get_db)) -> dict:
    return sla_service.construir_sla(db, date.today())
```

- [ ] **Step 5: Register router** en `app/main.py`: `from app.routers import sla` y
`app.include_router(sla.router, dependencies=[Depends(get_current_user)])`.

- [ ] **Step 6: Add `sla` to the incidencia ficha builder.** READ `app/routers/incidencias.py` función `ficha`
(~línea 82-124). Importa el servicio (`from app import sla_service` arriba) y, en la construcción de
`IncidenciaFicha(...)` (~línea 115), añade:
```python
        sla=sla_service.sla_de_incidencia(db, inc, date.today()),
```
Asegúrate de que `date` está importado en `incidencias.py` (lo está, se usa para fechas). El valor que devuelve
`sla_de_incidencia` es un dict (o None); FastAPI lo valida contra `Optional[SlaIncidencia]` (BaseModel) — el
dict tiene exactamente las claves `nivel/respuesta/resolucion/estado_global`, y `respuesta/resolucion` son dicts
con `objetivo_fecha/fecha_real/dias_restantes/estado`. Coincide con `SlaMetrica`/`SlaIncidencia`.

- [ ] **Step 7: Run the test**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_sla_api.py -v`
Expected: PASS (4 tests). Si la validación de `IncidenciaFicha.sla` falla por forward-ref, confirma el
`IncidenciaFicha.model_rebuild()` tras definir `SlaIncidencia`.

- [ ] **Step 8: Run FULL suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (todo verde; `IncidenciaFicha` cambió → confirma sin regresiones).

- [ ] **Step 9: Commit**

```bash
git add app/schemas.py app/routers/sla.py app/main.py app/routers/incidencias.py tests/test_sla_api.py
git commit -m "feat: GET /api/sla + SLA por incidencia en el expediente"
```

---

## Task 4: Prompt Lovable 24

**Files:**
- Create: `docs/lovable/24_sla.md`

- [ ] **Step 1: Write the prompt** con la cabecera de contexto estándar (como `docs/lovable/23_avisos_preventivo.md`). Debe cubrir:
  1. Tipos `SlaMetrica` (`objetivo_fecha`, `fecha_real:string|null`, `dias_restantes:number`, `estado:"en_plazo"|"en_riesgo"|"incumplido"|"sin_sla"`), `SlaIncidencia` (`nivel`, `respuesta:SlaMetrica`, `resolucion:SlaMetrica`, `estado_global`), `SlaIncidenciaItem` (`incidencia:Incidencia`, `sla:SlaIncidencia`), `CumplimientoSla`, `SlaOut` en `@/lib/types`.
  2. **Expediente de incidencia**: panel "SLA" con nivel + dos filas (Respuesta / Resolución): objetivo, días restantes, badge de estado (en_plazo=verde, en_riesgo=ámbar, incumplido=rojo, sin_sla=gris). Lee `ficha.sla` (puede ser null → "Sin SLA").
  3. **Pantalla SLA** (`/sla` o sección en analítica): tarjetas de cumplimiento (`cumplimiento.respuesta_pct`, `resolucion_pct`, `total`) + tablas "En riesgo" e "Incumplidas" (cada fila: incidencia código/título + badge estado_global + días restantes), enlace a la incidencia. Badge en menú = `resumen.en_riesgo + resumen.incumplidas`.
  4. Consume `GET /api/sla` y `ficha.sla`. No inventes endpoints/campos.

- [ ] **Step 2: Commit**

```bash
git add docs/lovable/24_sla.md
git commit -m "docs: prompt Lovable 24 — cumplimiento de SLA"
```

---

## Self-review (cobertura del spec)
- Objetivos por nivel + estado por métrica + peor + mapeo hitos → Task 1. Servicio (sin_sla, listas, cumplimiento) → Task 2. Endpoint + schemas + ficha.sla + 401 → Task 3. Frontend → Task 4.
- ⚠️ Tests con fechas absolutas. `IncidenciaFicha` gana `sla` (forward-ref + model_rebuild). Sin entidad ni migración.
