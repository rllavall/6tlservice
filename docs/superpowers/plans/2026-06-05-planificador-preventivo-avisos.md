# Planificador de preventivo + avisos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Una agenda calculada read-only del preventivo por equipo + un panel de avisos consolidado (preventivos vencidos/próximos + contratos por caducar), expuesto en `GET /api/avisos`.

**Architecture:** Lógica pura en `app/avisos.py` (duck-typed, `hoy` inyectable, como `garantia.py`/`contratos.py`), orquestada por `app/avisos_service.py` con consultas a BD, expuesta por un router protegido. Sin entidad ni migración nuevas.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest + TestClient.

**Convenciones del repo:** ejecuta `./.venv/Scripts/python.exe -m pytest` desde `backend/`. NO arranques uvicorn. Fixtures: `client` (auth simulada user 1), `client_sin_auth` (auth real → 401). Routers se registran en `app/main.py` con `dependencies=[Depends(get_current_user)]`. `app/contratos.py` tiene `NIVELES[nivel]["preventivo_meses"]` y `esta_vigente(contrato, hoy)`. `app/garantia.py` tiene `_add_months(d, months)`.

---

## Task 1: Lógica pura `app/avisos.py`

**Files:**
- Create: `backend/app/avisos.py`
- Test: `backend/tests/test_avisos_logica.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_avisos_logica.py`:

```python
from datetime import date
from types import SimpleNamespace

from app import avisos


def _con(inicio=date(2020, 1, 1), fin=date(2100, 1, 1), nivel="bronze", cancelado=False):
    return SimpleNamespace(fecha_inicio=inicio, fecha_fin=fin, nivel=nivel, cancelado=cancelado)


def test_clasificar_buckets():
    hoy = date(2026, 6, 5)
    assert avisos.clasificar(date(2026, 6, 1), hoy) == "vencido"
    assert avisos.clasificar(date(2026, 6, 20), hoy) == "proximo"   # dentro de 30d
    assert avisos.clasificar(date(2026, 9, 1), hoy) == "al_dia"     # fuera de 30d


def test_dias_restantes_signo():
    hoy = date(2026, 6, 5)
    assert avisos.dias_restantes(date(2026, 6, 10), hoy) == 5
    assert avisos.dias_restantes(date(2026, 6, 1), hoy) == -4


def test_proxima_desde_ultima_accion_con_proxima_fecha():
    con = _con(nivel="bronze")
    ultima = SimpleNamespace(fecha=date(2025, 1, 1), proxima_fecha=date(2026, 1, 1))
    assert avisos.proxima_fecha_equipo(object(), con, ultima, date(2026, 6, 5)) == date(2026, 1, 1)


def test_proxima_desde_ultima_accion_sin_proxima_fecha_usa_cadencia():
    con = _con(nivel="gold")  # semestral = 6 meses
    ultima = SimpleNamespace(fecha=date(2026, 1, 1), proxima_fecha=None)
    assert avisos.proxima_fecha_equipo(object(), con, ultima, date(2026, 6, 5)) == date(2026, 7, 1)


def test_proxima_nunca_revisado_desde_inicio_mas_cadencia():
    con = _con(inicio=date(2026, 1, 1), nivel="bronze")  # anual = 12 meses
    assert avisos.proxima_fecha_equipo(object(), con, None, date(2026, 6, 5)) == date(2027, 1, 1)


def test_contrato_por_caducar():
    hoy = date(2026, 6, 5)
    # vigente y caduca dentro de 60 días
    assert avisos.contrato_por_caducar(_con(fin=date(2026, 7, 1)), hoy) is True
    # vigente pero caduca lejos
    assert avisos.contrato_por_caducar(_con(fin=date(2027, 1, 1)), hoy) is False
    # cancelado nunca caduca-aviso
    assert avisos.contrato_por_caducar(_con(fin=date(2026, 7, 1), cancelado=True), hoy) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_avisos_logica.py -v`
Expected: FAIL (`No module named 'app.avisos'`)

- [ ] **Step 3: Write the module** `backend/app/avisos.py`:

```python
"""Lógica pura de avisos de servicio (preventivo + caducidad de contrato).
No importa models: opera por duck-typing y con `hoy` inyectable."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from app import contratos
from app.garantia import _add_months

UMBRAL_PREVENTIVO_DIAS = 30
UMBRAL_CONTRATO_DIAS = 60


def dias_restantes(fecha: date, hoy: date) -> int:
    return (fecha - hoy).days


def clasificar(proxima: date, hoy: date, umbral: int = UMBRAL_PREVENTIVO_DIAS) -> str:
    if proxima < hoy:
        return "vencido"
    if proxima <= hoy + timedelta(days=umbral):
        return "proximo"
    return "al_dia"


def proxima_fecha_equipo(equipo, contrato, ultima_accion, hoy: date) -> date:
    """Próxima fecha de preventivo. `ultima_accion` puede ser None (nunca revisado)."""
    meses = contratos.NIVELES[contrato.nivel]["preventivo_meses"]
    if ultima_accion is not None:
        if getattr(ultima_accion, "proxima_fecha", None) is not None:
            return ultima_accion.proxima_fecha
        return _add_months(ultima_accion.fecha, meses)
    return _add_months(contrato.fecha_inicio, meses)


def contrato_por_caducar(contrato, hoy: date, umbral: int = UMBRAL_CONTRATO_DIAS) -> bool:
    if not contratos.esta_vigente(contrato, hoy):
        return False
    return contrato.fecha_fin <= hoy + timedelta(days=umbral)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_avisos_logica.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app/avisos.py tests/test_avisos_logica.py
git commit -m "feat: lógica pura de avisos (buckets preventivo + caducidad contrato)"
```

---

## Task 2: Servicio `app/avisos_service.py`

**Files:**
- Create: `backend/app/avisos_service.py`
- Test: `backend/tests/test_avisos_service.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_avisos_service.py`:

```python
from datetime import date

from app import avisos_service
from app import models


def _producto(db):
    p = models.Producto(part_number="6TL-AV", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    return p


def _contrato(db, codigo, nivel="bronze", inicio=date(2020, 1, 1), fin=date(2100, 1, 1)):
    c = models.ContratoMantenimiento(codigo=codigo, nivel=nivel, fecha_inicio=inicio, fecha_fin=fin)
    db.add(c); db.flush()
    return c


def test_equipo_nunca_revisado_vencido_aparece(db_session):
    # bronze, contrato iniciado hace mucho => próxima = inicio+12m, muy vencida
    p = _producto(db_session)
    con = _contrato(db_session, "CTR-0001", nivel="bronze", inicio=date(2020, 1, 1))
    eq = models.Equipo(numero_serie="V1", producto_id=p.id, contrato_id=con.id)
    db_session.add(eq); db_session.flush()
    out = avisos_service.construir_avisos(db_session, date(2026, 6, 5))
    ids = [a["equipo"].id for a in out["preventivos"]]
    assert eq.id in ids
    aviso = next(a for a in out["preventivos"] if a["equipo"].id == eq.id)
    assert aviso["bucket"] == "vencido"
    assert aviso["dias_restantes"] < 0
    assert aviso["ultima_fecha"] is None


def test_equipo_sin_contrato_vigente_excluido(db_session):
    p = _producto(db_session)
    venc = _contrato(db_session, "CTR-VENC", inicio=date(2020, 1, 1), fin=date(2021, 1, 1))
    eq = models.Equipo(numero_serie="X1", producto_id=p.id, contrato_id=venc.id)
    db_session.add(eq); db_session.flush()
    out = avisos_service.construir_avisos(db_session, date(2026, 6, 5))
    assert all(a["equipo"].id != eq.id for a in out["preventivos"])


def test_equipo_al_dia_no_aparece(db_session):
    # gold semestral, acción reciente con próxima lejana
    p = _producto(db_session)
    con = _contrato(db_session, "CTR-AL", nivel="gold")
    eq = models.Equipo(numero_serie="A1", producto_id=p.id, contrato_id=con.id)
    db_session.add(eq); db_session.flush()
    db_session.add(models.AccionPreventiva(
        equipo_id=eq.id, fecha=date(2026, 6, 1), tipo="on_site", veredicto="ok",
        proxima_fecha=date(2026, 12, 1)))
    db_session.flush()
    out = avisos_service.construir_avisos(db_session, date(2026, 6, 5))
    assert all(a["equipo"].id != eq.id for a in out["preventivos"])


def test_orden_y_resumen_y_contrato_por_caducar(db_session):
    p = _producto(db_session)
    # contrato que caduca pronto (vigente, fin dentro de 60d)
    con = _contrato(db_session, "CTR-CAD", nivel="bronze", inicio=date(2020, 1, 1), fin=date(2026, 7, 1))
    eq = models.Equipo(numero_serie="C1", producto_id=p.id, contrato_id=con.id)
    db_session.add(eq); db_session.flush()
    out = avisos_service.construir_avisos(db_session, date(2026, 6, 5))
    # el contrato aparece en por_caducar
    assert any(c["contrato"].id == con.id for c in out["contratos_por_caducar"])
    # resumen coherente
    r = out["resumen"]
    assert r["preventivos_vencidos"] >= 1
    assert r["contratos_por_caducar"] >= 1
    # preventivos ordenados por dias_restantes asc
    dr = [a["dias_restantes"] for a in out["preventivos"]]
    assert dr == sorted(dr)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_avisos_service.py -v`
Expected: FAIL (`No module named 'app.avisos_service'`)

- [ ] **Step 3: Write the service** `backend/app/avisos_service.py`:

```python
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app import avisos, contratos, models


def construir_avisos(db: Session, hoy: date) -> dict:
    preventivos: list[dict] = []
    equipos = db.query(models.Equipo).filter(models.Equipo.contrato_id.isnot(None)).all()
    for eq in equipos:
        con = eq.contrato
        if con is None or not contratos.esta_vigente(con, hoy):
            continue
        ultima = (db.query(models.AccionPreventiva)
                  .filter(models.AccionPreventiva.equipo_id == eq.id)
                  .order_by(models.AccionPreventiva.fecha.desc(), models.AccionPreventiva.id.desc())
                  .first())
        proxima = avisos.proxima_fecha_equipo(eq, con, ultima, hoy)
        bucket = avisos.clasificar(proxima, hoy)
        if bucket == "al_dia":
            continue
        preventivos.append({
            "equipo": eq,
            "contrato": con,
            "proxima_fecha": proxima,
            "dias_restantes": avisos.dias_restantes(proxima, hoy),
            "bucket": bucket,
            "ultima_fecha": ultima.fecha if ultima is not None else None,
        })
    preventivos.sort(key=lambda a: a["dias_restantes"])

    contratos_cad: list[dict] = []
    for con in db.query(models.ContratoMantenimiento).all():
        if avisos.contrato_por_caducar(con, hoy):
            cliente = db.get(models.Cliente, con.cliente_id) if con.cliente_id else None
            contratos_cad.append({
                "contrato": con,
                "cliente": cliente,
                "fecha_fin": con.fecha_fin,
                "dias_restantes": avisos.dias_restantes(con.fecha_fin, hoy),
            })
    contratos_cad.sort(key=lambda c: c["dias_restantes"])

    resumen = {
        "preventivos_vencidos": sum(1 for a in preventivos if a["bucket"] == "vencido"),
        "preventivos_proximos": sum(1 for a in preventivos if a["bucket"] == "proximo"),
        "contratos_por_caducar": len(contratos_cad),
    }
    return {"preventivos": preventivos, "contratos_por_caducar": contratos_cad, "resumen": resumen}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_avisos_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/avisos_service.py tests/test_avisos_service.py
git commit -m "feat: avisos_service (construye agenda preventivo + contratos por caducar)"
```

---

## Task 3: Schemas + router `GET /api/avisos`

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/avisos.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_avisos_api.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_avisos_api.py`:

```python
def _equipo_vencido(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-AVA", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": "bronze", "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "AV1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    return eq["id"], con


def test_avisos_lista_preventivo_vencido(client):
    eid, _ = _equipo_vencido(client)
    out = client.get("/api/avisos").json()
    ids = [a["equipo"]["id"] for a in out["preventivos"]]
    assert eid in ids
    aviso = next(a for a in out["preventivos"] if a["equipo"]["id"] == eid)
    assert aviso["bucket"] == "vencido"
    assert aviso["contrato"]["nivel"] == "bronze"
    assert out["resumen"]["preventivos_vencidos"] >= 1


def test_avisos_contrato_por_caducar(client):
    # contrato vigente que caduca pronto (depende de la fecha de hoy: usa un fin lejano NO debe aparecer;
    # este test crea uno con fin a 100 años => NO por caducar, y verifica que la clave existe y es lista)
    out = client.get("/api/avisos").json()
    assert "contratos_por_caducar" in out and isinstance(out["contratos_por_caducar"], list)
    assert set(out["resumen"].keys()) == {"preventivos_vencidos", "preventivos_proximos", "contratos_por_caducar"}


def test_avisos_protegido_401(client_sin_auth):
    assert client_sin_auth.get("/api/avisos").status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_avisos_api.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Add schemas** en `backend/app/schemas.py` (sección nueva, tras la de preventivo):

```python
# --- Avisos de servicio ---
class AvisoPreventivo(_ORM):
    equipo: EquipoOut
    contrato: ContratoResumen
    proxima_fecha: date
    dias_restantes: int
    bucket: Literal["vencido", "proximo"]
    ultima_fecha: Optional[date] = None


class AvisoContrato(_ORM):
    contrato: ContratoResumen
    cliente: Optional[ClienteOut] = None
    fecha_fin: date
    dias_restantes: int


class ResumenAvisos(BaseModel):
    preventivos_vencidos: int
    preventivos_proximos: int
    contratos_por_caducar: int


class AvisosOut(_ORM):
    preventivos: list[AvisoPreventivo] = []
    contratos_por_caducar: list[AvisoContrato] = []
    resumen: ResumenAvisos
```

- [ ] **Step 4: Write the router** `backend/app/routers/avisos.py`:

```python
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import avisos_service
from app.db import get_db
from app.schemas import AvisosOut

router = APIRouter(prefix="/api/avisos", tags=["avisos"])


@router.get("", response_model=AvisosOut)
def listar(db: Session = Depends(get_db)) -> dict:
    return avisos_service.construir_avisos(db, date.today())
```

- [ ] **Step 5: Register the router** en `backend/app/main.py`: `from app.routers import avisos` y
`app.include_router(avisos.router, dependencies=[Depends(get_current_user)])` (junto a los protegidos).

- [ ] **Step 6: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_avisos_api.py -v`
Expected: PASS (3 tests). Si la validación del response_model falla al serializar un `equipo`/`contrato` ORM
anidado, confirma que `AvisoPreventivo`/`AvisoContrato` extienden `_ORM` y que `EquipoOut`/`ContratoResumen`
ya tienen `from_attributes` (lo tienen). No cambies el service.

- [ ] **Step 7: Run FULL suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (todo verde).

- [ ] **Step 8: Commit**

```bash
git add app/schemas.py app/routers/avisos.py app/main.py tests/test_avisos_api.py
git commit -m "feat: GET /api/avisos (panel de avisos preventivo + contratos por caducar)"
```

---

## Task 4: Prompt Lovable 23

**Files:**
- Create: `docs/lovable/23_avisos_preventivo.md`

- [ ] **Step 1: Write the prompt**

Crea `docs/lovable/23_avisos_preventivo.md` con la cabecera de contexto estándar (idéntica a
`docs/lovable/22_contratos_preventivo.md`: TanStack Start, `VITE_API_BASE ?? http://127.0.0.1:8020`, helper
`api<T>()` con Bearer, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`, "NO cambies nombres de campo").
Debe cubrir:

1. **Tipos** en `src/lib/types.ts`:
   ```ts
   interface AvisoPreventivo { equipo:Equipo; contrato:ContratoResumen; proxima_fecha:string; dias_restantes:number; bucket:"vencido"|"proximo"; ultima_fecha:string|null }
   interface AvisoContrato { contrato:ContratoResumen; cliente:Cliente|null; fecha_fin:string; dias_restantes:number }
   interface ResumenAvisos { preventivos_vencidos:number; preventivos_proximos:number; contratos_por_caducar:number }
   interface AvisosOut { preventivos:AvisoPreventivo[]; contratos_por_caducar:AvisoContrato[]; resumen:ResumenAvisos }
   ```
2. **Pantalla `/avisos`** (en el menú) que llama `GET /api/avisos`:
   - Sección **Preventivos**: tabla con equipo (nº serie + producto), contrato/nivel, `proxima_fecha`,
     `dias_restantes` (badge `bucket`: vencido=rojo, proximo=ámbar), enlace a la ficha del equipo y botón
     "Registrar preventivo" (reusa el formulario del prompt 22). Filtro por bucket (Vencidos/Próximos/Todos).
   - Sección **Contratos por caducar**: tabla con contrato (codigo+nivel), cliente, `fecha_fin`, `dias_restantes`.
3. **Badge en el menú** junto a "Avisos" con `resumen.preventivos_vencidos + resumen.contratos_por_caducar`.
4. (Opcional) un contador "Preventivos vencidos" en la cabecera de KPIs "Resumen de servicio".

No inventes endpoints ni campos. Solo consume `GET /api/avisos`.

- [ ] **Step 2: Commit**

```bash
git add docs/lovable/23_avisos_preventivo.md
git commit -m "docs: prompt Lovable 23 — panel de avisos de preventivo"
```

---

## Self-review (cobertura del spec)
- Cálculo próxima (última acción / nunca-revisado) → Task 1. Buckets + caducidad → Task 1. Orquestación BD + exclusión sin-contrato-vigente + orden + resumen → Task 2. Endpoint + schemas + 401 → Task 3. Frontend → Task 4.
- ⚠️ Tests con fechas absolutas (2020→2100) para no depender de "hoy"; el endpoint usa `date.today()` (el test de API solo verifica forma/clases y el caso "muy vencido" que es estable).
- Sin entidad ni migración nuevas (read-only).
