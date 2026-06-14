# Captura de nº de serie por escaneo DataMatrix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Escanear el DataMatrix de un componente (lector teclado-wedge) y rellenar automáticamente su nº de serie en el banco, emparejando por PN de fabricante.

**Architecture:** Parser puro sin BD (`app/datamatrix.py`) → servicio que empareja y escribe (`app/escaneo_service.py`) → endpoint `POST /api/equipos/{id}/escaneo`. La resolución manual reutiliza `PATCH /api/componentes/{id}`. Regla de parseo por fabricante en `Fabricante.regla_datamatrix`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, SQLite, pytest. Frontend: TanStack Start/Vite (vía prompt Lovable).

**Spec:** `docs/superpowers/specs/2026-06-14-escaneo-datamatrix-design.md`

**Test harness:** `tests/conftest.py` ofrece `db_session` (Session en memoria) y `client` (TestClient con auth simulada). Ejecutar: `cd backend && .venv/Scripts/python -m pytest tests/<archivo> -q`. ⚠️ El seeder de ayuda toca `postventa.db` al importar; los tests usan SQLite en memoria, no la BD viva.

---

### Task 1: Columna `regla_datamatrix` en Fabricante (modelo + migración)

**Files:**
- Modify: `backend/app/models.py:337` (clase `Fabricante`, tras `url_obsolescencia`)
- Modify: `backend/app/migrations.py:25` (entrada `"fabricantes"`)
- Test: `backend/tests/test_escaneo_datamatrix_migracion.py` (crear)

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/tests/test_escaneo_datamatrix_migracion.py
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.migrations import add_missing_columns


def _cols(engine, tabla):
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({tabla})")).fetchall()
    return {r[1] for r in rows}


def test_migracion_anhade_regla_datamatrix_a_fabricantes():
    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # tabla fabricantes "vieja" sin la columna nueva
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE fabricantes (id INTEGER PRIMARY KEY, nombre TEXT)")
    add_missing_columns(eng)
    assert "regla_datamatrix" in _cols(eng, "fabricantes")


def test_migracion_es_idempotente_regla_datamatrix():
    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE fabricantes (id INTEGER PRIMARY KEY, nombre TEXT)")
    add_missing_columns(eng)
    add_missing_columns(eng)  # no debe lanzar
    assert "regla_datamatrix" in _cols(eng, "fabricantes")
```

- [ ] **Step 2: Ejecutar el test y verificar que falla**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_escaneo_datamatrix_migracion.py -q`
Expected: FAIL (`regla_datamatrix` no está en las columnas).

- [ ] **Step 3: Añadir la columna al modelo**

En `backend/app/models.py`, dentro de `class Fabricante`, justo después de la línea
`url_obsolescencia: Mapped[Optional[str]] = mapped_column(Text, nullable=True)`:

```python
    regla_datamatrix: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Añadir la columna a la migración**

En `backend/app/migrations.py`, cambiar la entrada de `fabricantes`:

```python
    "fabricantes": {"url_obsolescencia": "TEXT", "regla_datamatrix": "TEXT"},
```

- [ ] **Step 5: Ejecutar el test y verificar que pasa**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_escaneo_datamatrix_migracion.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/migrations.py backend/tests/test_escaneo_datamatrix_migracion.py
git commit -m "feat(escaneo): columna Fabricante.regla_datamatrix + migracion"
```

---

### Task 2: Parser puro `datamatrix.py`

**Files:**
- Create: `backend/app/datamatrix.py`
- Test: `backend/tests/test_datamatrix_parser.py` (crear)

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/tests/test_datamatrix_parser.py
from app import datamatrix


# --- es_serie_placeholder ---
def test_placeholder_detecta_prefijo():
    assert datamatrix.es_serie_placeholder("S/N pendiente (1.1)") is True

def test_placeholder_falso_para_serial_real():
    assert datamatrix.es_serie_placeholder("ABC123") is False

def test_placeholder_none():
    assert datamatrix.es_serie_placeholder(None) is False


# --- parsear_gs1 ---
def test_gs1_ai21_es_sn():
    r = datamatrix.parsear_gs1("21SN12345")
    assert r["sn"] == "SN12345"
    assert r["formato"] == "gs1"

def test_gs1_ai01_es_pn_gtin():
    r = datamatrix.parsear_gs1("0107612345678903")
    assert r["pn"] == "07612345678903"

def test_gs1_ignora_prefijo_simbologia():
    # ]d2 (simbología) + AI01 GTIN(14) "07612345678903" + AI21 "SN999"
    r = datamatrix.parsear_gs1("]d2010761234567890321SN999")
    assert r["pn"] == "07612345678903"
    assert r["sn"] == "SN999"

def test_gs1_separador_gs_para_campo_variable():
    # AI 21 (variable) terminado por GS, seguido de AI 240 (variable)
    raw = "21LOTE-7\x1d240PN-ABC"
    r = datamatrix.parsear_gs1(raw)
    assert r["sn"] == "LOTE-7"
    assert r["pn"] == "PN-ABC"

def test_gs1_no_gs1_devuelve_none():
    r = datamatrix.parsear_gs1("CADENA-LIBRE-SIN-AI")
    assert r["pn"] is None and r["sn"] is None


# --- parsear_con_regla ---
def test_regla_extrae_pn_y_sn():
    regla = r"^(?P<pn>[A-Z0-9]+)-(?P<sn>\d+)$"
    r = datamatrix.parsear_con_regla("ABC123-456", regla)
    assert r == {"pn": "ABC123", "sn": "456", "formato": "regla"}

def test_regla_no_casa_devuelve_none():
    assert datamatrix.parsear_con_regla("xxx", r"^\d+$") is None

def test_regla_invalida_devuelve_none():
    assert datamatrix.parsear_con_regla("abc", r"(?P<sn>[") is None


# --- parsear (capas) ---
def test_parsear_regla_gana_sobre_gs1():
    regla = r"^(?P<pn>[A-Z]+)(?P<sn>\d+)$"
    r = datamatrix.parsear("ABC123", [regla])
    assert r["formato"] == "regla" and r["pn"] == "ABC" and r["sn"] == "123"

def test_parsear_sin_regla_usa_gs1():
    r = datamatrix.parsear("21SN42", [])
    assert r["formato"] == "gs1" and r["sn"] == "SN42"

def test_parsear_cae_a_crudo():
    r = datamatrix.parsear("CADENA-LIBRE", [])
    assert r["formato"] == "crudo" and r["sn"] == "CADENA-LIBRE" and r["pn"] is None

def test_parsear_ignora_regla_invalida_y_sigue():
    r = datamatrix.parsear("21SN42", [r"(?P<sn>["])
    assert r["formato"] == "gs1" and r["sn"] == "SN42"
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_datamatrix_parser.py -q`
Expected: FAIL (módulo `app.datamatrix` no existe).

- [ ] **Step 3: Implementar el parser**

```python
# backend/app/datamatrix.py
"""Parseo puro de códigos DataMatrix de componentes (sin BD).

El lector (teclado-wedge) entrega la cadena ya decodificada. Aquí extraemos
`pn` (part number de fabricante) y `sn` (nº de serie) por capas: regla regex
por fabricante -> GS1 (Application Identifiers) -> crudo (la cadena como SN).
"""
from __future__ import annotations

import re

_PLACEHOLDER_PREFIJO = "S/N pendiente"
_GS = "\x1d"  # separador de grupo GS1 (FNC1)
_PREFIJOS_SIMBOLOGIA = ("]d2", "]C1", "]e0")

# AIs de longitud fija que nos interesan: AI -> (longitud_dato, clave)
_AI_FIJOS = {"01": (14, "pn")}
# AIs de longitud variable que nos interesan: AI -> clave
_AI_VARIABLES = {"21": "sn", "240": "pn", "10": "sn"}


def es_serie_placeholder(s: str | None) -> bool:
    """True si el nº de serie es un placeholder de alta (aún sin serial real)."""
    return bool(s) and s.startswith(_PLACEHOLDER_PREFIJO)


def _quitar_prefijo_simbologia(raw: str) -> str:
    for p in _PREFIJOS_SIMBOLOGIA:
        if raw.startswith(p):
            return raw[len(p):]
    return raw


def parsear_gs1(raw: str) -> dict:
    """Interpreta una cadena GS1 DataMatrix. Devuelve {pn, sn, formato='gs1'}.
    Campos variables terminan en GS (\\x1d) o al final de la cadena."""
    out = {"pn": None, "sn": None, "formato": "gs1"}
    s = _quitar_prefijo_simbologia(raw)
    i = 0
    n = len(s)
    while i < n:
        if s[i] == _GS:
            i += 1
            continue
        ai2 = s[i:i + 2]
        ai3 = s[i:i + 3]
        if ai2 in _AI_FIJOS:
            longitud, clave = _AI_FIJOS[ai2]
            dato = s[i + 2:i + 2 + longitud]
            if out.get(clave) is None:
                out[clave] = dato or None
            i += 2 + longitud
        elif ai3 in _AI_VARIABLES or ai2 in _AI_VARIABLES:
            ai = ai3 if ai3 in _AI_VARIABLES else ai2
            clave = _AI_VARIABLES[ai]
            j = s.find(_GS, i + len(ai))
            if j == -1:
                j = n
            dato = s[i + len(ai):j]
            if out.get(clave) is None:
                out[clave] = dato or None
            i = j + 1
        else:
            # No reconocemos el AI: no es GS1 procesable -> abortamos.
            break
    return out


def parsear_con_regla(raw: str, regla: str) -> dict | None:
    """Aplica una regex con grupos nombrados pn/sn. None si no compila o no casa."""
    try:
        patron = re.compile(regla)
    except re.error:
        return None
    m = patron.search(raw)
    if m is None:
        return None
    grupos = m.groupdict()
    return {"pn": grupos.get("pn") or None, "sn": grupos.get("sn") or None, "formato": "regla"}


def parsear(raw: str, reglas: list[str]) -> dict:
    """Capas: reglas (primer match con pn o sn) -> GS1 -> crudo (sn=raw)."""
    raw = (raw or "").strip()
    for regla in reglas:
        r = parsear_con_regla(raw, regla)
        if r and (r["pn"] or r["sn"]):
            return r
    g = parsear_gs1(raw)
    if g["pn"] or g["sn"]:
        return g
    return {"pn": None, "sn": raw or None, "formato": "crudo"}
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_datamatrix_parser.py -q`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/datamatrix.py backend/tests/test_datamatrix_parser.py
git commit -m "feat(escaneo): parser puro datamatrix (regla/GS1/crudo)"
```

---

### Task 3: Servicio `escaneo_service.resolver_escaneo`

**Files:**
- Create: `backend/app/escaneo_service.py`
- Test: `backend/tests/test_escaneo_service.py` (crear)

**Contexto de modelos** (para construir fixtures): `Producto(part_number, tipo, descripcion, pn_fabricante, fabricante_id)`; `Componente(numero_serie, producto_id, equipo_id, posicion)`; `Equipo(numero_serie, producto_id)`; `Fabricante(nombre, regla_datamatrix)`. UniqueConstraint `(producto_id, numero_serie)` en componentes.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/tests/test_escaneo_service.py
import pytest

from app import escaneo_service, models


def _equipo_con_banco(db, *, fabricante=None, pn_fab="PN-A", regla=None, serie="S/N pendiente (1.1)"):
    """Crea un equipo (banco) con un producto-equipo y un componente placeholder."""
    fab = None
    if fabricante:
        fab = models.Fabricante(nombre=fabricante, regla_datamatrix=regla)
        db.add(fab); db.flush()
    p_eq = models.Producto(part_number="BANCO-1", tipo="equipo", descripcion="Banco")
    db.add(p_eq); db.flush()
    eq = models.Equipo(numero_serie="EQ-1", producto_id=p_eq.id)
    db.add(eq); db.flush()
    p_comp = models.Producto(part_number="COMP-1", tipo="componente", descripcion="Comp",
                             pn_fabricante=pn_fab, fabricante_id=fab.id if fab else None)
    db.add(p_comp); db.flush()
    comp = models.Componente(numero_serie=serie, producto_id=p_comp.id,
                             equipo_id=eq.id, posicion="1.1")
    db.add(comp); db.commit()
    return eq, comp, p_comp


def test_asignado_rellena_placeholder(db_session):
    eq, comp, _ = _equipo_con_banco(db_session, pn_fab="PN-A")
    # PN coincide via GS1 AI 240 + SN via AI 21
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A\x1d21SER-99")
    assert r["estado"] == "asignado"
    assert r["componente_id"] == comp.id
    db_session.refresh(comp)
    assert comp.numero_serie == "SER-99"


def test_ambiguo_no_escribe(db_session):
    eq, comp1, p1 = _equipo_con_banco(db_session, pn_fab="PN-A")
    # segundo componente mismo pn_fabricante
    comp2 = models.Componente(numero_serie="S/N pendiente (1.2)", producto_id=p1.id,
                              equipo_id=eq.id, posicion="1.2")
    db_session.add(comp2); db_session.commit()
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A\x1d21SER-99")
    assert r["estado"] == "ambiguo"
    assert len(r["candidatos"]) == 2
    db_session.refresh(comp1)
    assert comp1.numero_serie.startswith("S/N pendiente")


def test_ocupado_no_pisa_serial_real(db_session):
    eq, comp, _ = _equipo_con_banco(db_session, pn_fab="PN-A", serie="SERIAL-REAL")
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A\x1d21SER-99")
    assert r["estado"] == "ocupado"
    db_session.refresh(comp)
    assert comp.numero_serie == "SERIAL-REAL"


def test_sin_match_devuelve_placeholders(db_session):
    eq, comp, _ = _equipo_con_banco(db_session, pn_fab="PN-A")
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-OTRO\x1d21SER-99")
    assert r["estado"] == "sin_match"
    assert any(c["componente_id"] == comp.id for c in r["candidatos"])


def test_sin_sn(db_session):
    eq, comp, _ = _equipo_con_banco(db_session, pn_fab="PN-A")
    # solo PN, sin SN
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A")
    assert r["estado"] == "sin_sn"


def test_duplicado(db_session):
    eq, comp, p = _equipo_con_banco(db_session, pn_fab="PN-A")
    # ya existe otro componente del MISMO producto con SER-99
    otro = models.Componente(numero_serie="SER-99", producto_id=p.id, equipo_id=eq.id, posicion="1.2")
    db_session.add(otro); db_session.commit()
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "240PN-A\x1d21SER-99")
    assert r["estado"] == "duplicado"
    db_session.refresh(comp)
    assert comp.numero_serie.startswith("S/N pendiente")


def test_usa_regla_del_fabricante(db_session):
    eq, comp, _ = _equipo_con_banco(
        db_session, fabricante="ACME", pn_fab="PNX",
        regla=r"^(?P<pn>[A-Z]+)\*(?P<sn>\d+)$")
    r = escaneo_service.resolver_escaneo(db_session, eq.id, "PNX*7777")
    assert r["estado"] == "asignado"
    db_session.refresh(comp)
    assert comp.numero_serie == "7777"


def test_equipo_inexistente(db_session):
    r = escaneo_service.resolver_escaneo(db_session, 9999, "240PN-A\x1d21SER-99")
    assert r["estado"] == "equipo_no_existe"
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_escaneo_service.py -q`
Expected: FAIL (módulo no existe).

- [ ] **Step 3: Implementar el servicio**

```python
# backend/app/escaneo_service.py
"""Resuelve un escaneo DataMatrix contra los componentes de un banco (equipo).

Empareja el PN parseado con el `pn_fabricante` de los componentes y, si es
inequívoco y el componente está en placeholder, rellena su `numero_serie`.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import datamatrix, models


def _norm(s: str | None) -> str | None:
    return s.strip().upper() if s else None


def _candidato(comp: models.Componente, prod: models.Producto) -> dict:
    return {
        "componente_id": comp.id,
        "posicion": comp.posicion,
        "part_number": prod.part_number,
        "pn_fabricante": prod.pn_fabricante,
        "numero_serie": comp.numero_serie,
    }


def resolver_escaneo(db: Session, equipo_id: int, raw: str) -> dict:
    equipo = db.get(models.Equipo, equipo_id)
    if equipo is None:
        return {"estado": "equipo_no_existe", "formato": None, "pn": None, "sn": None,
                "componente_id": None, "posicion": None, "part_number": None, "candidatos": []}

    # Componentes del banco + su producto (para pn_fabricante/part_number).
    comps = db.query(models.Componente).filter(models.Componente.equipo_id == equipo_id).all()
    pares = []  # (componente, producto)
    reglas: list[str] = []
    fab_ids = set()
    for c in comps:
        prod = db.get(models.Producto, c.producto_id)
        if prod is None:
            continue
        pares.append((c, prod))
        if prod.fabricante_id and prod.fabricante_id not in fab_ids:
            fab_ids.add(prod.fabricante_id)
            fab = db.get(models.Fabricante, prod.fabricante_id)
            if fab and fab.regla_datamatrix:
                reglas.append(fab.regla_datamatrix)

    cand = datamatrix.parsear(raw, reglas)
    pn, sn, formato = cand["pn"], cand["sn"], cand["formato"]

    base = {"estado": None, "formato": formato, "pn": pn, "sn": sn,
            "componente_id": None, "posicion": None, "part_number": None, "candidatos": []}

    # Empareja por PN de fabricante.
    pn_norm = _norm(pn)
    casan = [(c, p) for (c, p) in pares if pn_norm and _norm(p.pn_fabricante) == pn_norm]

    if not casan:
        # Sin PN o PN que no casa: ofrecer placeholders del banco para resolución manual.
        base["estado"] = "sin_match"
        base["candidatos"] = [_candidato(c, p) for (c, p) in pares
                              if datamatrix.es_serie_placeholder(c.numero_serie)]
        return base

    if len(casan) > 1:
        base["estado"] = "ambiguo"
        base["candidatos"] = [_candidato(c, p) for (c, p) in casan]
        return base

    comp, prod = casan[0]
    base["componente_id"] = comp.id
    base["posicion"] = comp.posicion
    base["part_number"] = prod.part_number

    if not sn:
        base["estado"] = "sin_sn"
        base["candidatos"] = [_candidato(comp, prod)]
        return base

    if not datamatrix.es_serie_placeholder(comp.numero_serie):
        base["estado"] = "ocupado"
        base["candidatos"] = [_candidato(comp, prod)]
        return base

    comp.numero_serie = sn
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        base["estado"] = "duplicado"
        base["candidatos"] = [_candidato(comp, prod)]
        return base
    db.refresh(comp)
    base["estado"] = "asignado"
    base["numero_serie"] = comp.numero_serie
    return base
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_escaneo_service.py -q`
Expected: PASS (todos). Si `test_duplicado` falla por estado de sesión, asegúrate de que el `rollback()` precede a la lectura de `comp` (ya está en el código).

- [ ] **Step 5: Commit**

```bash
git add backend/app/escaneo_service.py backend/tests/test_escaneo_service.py
git commit -m "feat(escaneo): servicio resolver_escaneo (asignado/ambiguo/ocupado/sin_match/sin_sn/duplicado)"
```

---

### Task 4: Schemas + endpoint `POST /api/equipos/{id}/escaneo` + Fabricante.regla_datamatrix en schemas

**Files:**
- Modify: `backend/app/schemas.py` (añadir `EscaneoIn`, `EscaneoCandidato`, `EscaneoResultado`; añadir `regla_datamatrix` a `FabricanteCreate/Update/Out`)
- Modify: `backend/app/routers/equipos.py` (import + endpoint)
- Test: `backend/tests/test_escaneo_endpoint.py` (crear); `backend/tests/test_fabricante_regla_datamatrix.py` (crear)

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/tests/test_escaneo_endpoint.py
from app import models


def _banco(db):
    p_eq = models.Producto(part_number="BANCO-1", tipo="equipo", descripcion="Banco")
    db.add(p_eq); db.flush()
    eq = models.Equipo(numero_serie="EQ-1", producto_id=p_eq.id)
    db.add(eq); db.flush()
    p_comp = models.Producto(part_number="COMP-1", tipo="componente", descripcion="Comp",
                             pn_fabricante="PN-A")
    db.add(p_comp); db.flush()
    comp = models.Componente(numero_serie="S/N pendiente (1.1)", producto_id=p_comp.id,
                             equipo_id=eq.id, posicion="1.1")
    db.add(comp); db.commit()
    return eq.id, comp.id


def test_escaneo_asignado_200(client, db_session):
    eq_id, comp_id = _banco(db_session)
    resp = client.post(f"/api/equipos/{eq_id}/escaneo", json={"raw": "240PN-A\x1d21SER-99"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["estado"] == "asignado"
    assert body["componente_id"] == comp_id
    assert body["sn"] == "SER-99"


def test_escaneo_equipo_inexistente_404(client):
    resp = client.post("/api/equipos/99999/escaneo", json={"raw": "240PN-A\x1d21SER-99"})
    assert resp.status_code == 404


def test_escaneo_raw_vacio_422(client, db_session):
    eq_id, _ = _banco(db_session)
    resp = client.post(f"/api/equipos/{eq_id}/escaneo", json={"raw": "   "})
    assert resp.status_code == 422
```

```python
# backend/tests/test_fabricante_regla_datamatrix.py
def test_crear_fabricante_con_regla(client):
    resp = client.post("/api/fabricantes", json={"nombre": "ACME-DM", "regla_datamatrix": r"^(?P<sn>\d+)$"})
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["regla_datamatrix"] == r"^(?P<sn>\d+)$"
```

⚠️ Verifica el método/prefijo reales del router de fabricantes (`backend/app/routers/fabricantes.py`)
y el `status_code` de creación antes de fijar el test; ajusta la URL/code si difiere.

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_escaneo_endpoint.py tests/test_fabricante_regla_datamatrix.py -q`
Expected: FAIL (endpoint no existe / `regla_datamatrix` no en schema).

- [ ] **Step 3: Añadir schemas de escaneo**

En `backend/app/schemas.py`, cerca de los schemas de Componente (tras `ComponenteOut`, ~línea 201):

```python
class EscaneoIn(BaseModel):
    raw: str

    @field_validator("raw")
    @classmethod
    def _no_vacio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("raw no puede estar vacío")
        return v


class EscaneoCandidato(_ORM):
    componente_id: int
    posicion: Optional[str] = None
    part_number: str
    pn_fabricante: Optional[str] = None
    numero_serie: str


class EscaneoResultado(BaseModel):
    estado: str
    formato: Optional[str] = None
    pn: Optional[str] = None
    sn: Optional[str] = None
    componente_id: Optional[int] = None
    posicion: Optional[str] = None
    part_number: Optional[str] = None
    candidatos: list[EscaneoCandidato] = Field(default_factory=list)
```

- [ ] **Step 4: Añadir `regla_datamatrix` a los schemas de Fabricante**

En `FabricanteCreate` (~línea 781), `FabricanteUpdate` (~792) y `FabricanteOut` (~803),
añadir en cada uno:

```python
    regla_datamatrix: Optional[str] = None
```

- [ ] **Step 5: Añadir el endpoint en el router de equipos**

En `backend/app/routers/equipos.py`, ampliar el import de `app` y de schemas, y añadir el endpoint.

Cambiar la línea 10 de import a:
```python
from app import models, trazabilidad, escaneo_service
```
Añadir `EscaneoIn, EscaneoResultado` a la importación de `app.schemas` (línea 12).

Añadir el endpoint (p. ej. tras `sustituir_componente`):

```python
@router.post("/{equipo_id}/escaneo", response_model=EscaneoResultado)
def escaneo(equipo_id: int, payload: EscaneoIn, db: Session = Depends(get_db)) -> dict:
    """Resuelve un escaneo DataMatrix contra los componentes del banco.
    Rellena el nº de serie solo en el caso inequívoco; el resto se resuelve a mano."""
    resultado = escaneo_service.resolver_escaneo(db, equipo_id, payload.raw)
    if resultado["estado"] == "equipo_no_existe":
        raise HTTPException(404, "Equipo no encontrado")
    return resultado
```

- [ ] **Step 6: Ejecutar y verificar que pasan**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_escaneo_endpoint.py tests/test_fabricante_regla_datamatrix.py -q`
Expected: PASS (todos).

- [ ] **Step 7: Suite completa (no romper nada)**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: todos los tests previos siguen verdes + los nuevos. ⚠️ Parar uvicorn antes (el seeder de ayuda toca `postventa.db`).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/equipos.py backend/tests/test_escaneo_endpoint.py backend/tests/test_fabricante_regla_datamatrix.py
git commit -m "feat(escaneo): endpoint POST /api/equipos/{id}/escaneo + regla_datamatrix en schemas Fabricante"
```

---

### Task 5: Prompt Lovable 38 (frontend, solo documento)

**Files:**
- Create: `docs/lovable/38_escaneo_datamatrix.md`
- Modify: `docs/lovable/README.md` (añadir línea del prompt 38, si existe el índice)

- [ ] **Step 1: Escribir el prompt Lovable**

Crear `docs/lovable/38_escaneo_datamatrix.md` con un prompt que describa, con contrato exacto:
- Ruta nueva `/escaneo` (TanStack Start). Requiere login (token en `localStorage["token"]`, el
  helper `api()` ya inyecta el Bearer).
- Selector de banco (equipo): `GET /api/equipos` (filtrar a los que tienen componentes / categoría banco).
- Al elegir banco: `GET /api/componentes?equipo_id={id}` → tabla con `posicion`, `part_number`,
  `numero_serie`, resaltando los que empiezan por "S/N pendiente"; cabecera con progreso
  "X de N con serie real".
- Input de escaneo **autofocus** que captura la cadena del lector (un `<input>` que en `onKeyDown`
  Enter dispara el POST y se vacía). `POST /api/equipos/{id}/escaneo` body `{ raw }` →
  `EscaneoResultado { estado, formato, pn, sn, componente_id, posicion, part_number, candidatos[] }`.
  - `estado === "asignado"` → toast verde (posición + sn), refrescar lista, re-enfocar input.
  - `estado` en `ambiguo|ocupado|sin_match|sin_sn` → panel de resolución manual: mostrar `pn`/`sn`,
    listar `candidatos` (componente_id, posicion, part_number, numero_serie), permitir elegir uno
    y editar el SN → `PATCH /api/componentes/{componente_id}` body `{ numero_serie }` (409 → toast
    "ya existe ese nº de serie para el producto") → refrescar.
  - `estado === "duplicado"` → toast de error.
- (Opcional, no bloqueante) en el formulario de Fabricantes, añadir textarea `regla_datamatrix`
  (regex con grupos `(?P<pn>...)`/`(?P<sn>...)`), enviado en `POST/PUT /api/fabricantes`.
- Instrucciones Lovable: file-paths exactos, NO tocar otras rutas, tipos TS a añadir en `src/lib/types.ts`
  (`EscaneoResultado`, `EscaneoCandidato`, `EstadoEscaneo`).

- [ ] **Step 2: Commit**

```bash
git add docs/lovable/38_escaneo_datamatrix.md docs/lovable/README.md
git commit -m "docs(lovable): prompt 38 pantalla de escaneo DataMatrix"
```

---

## Cierre

Tras la Task 5: revisión holística final (Opus) sobre toda la rama, luego
`superpowers:finishing-a-development-branch`. El prompt Lovable 38 se pega aparte (no es código de este repo backend).
