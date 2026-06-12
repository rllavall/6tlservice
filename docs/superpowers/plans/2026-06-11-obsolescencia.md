# Gestión de obsolescencia — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vigilar semanalmente el estado de ciclo de vida de los productos del catálogo (EOL/PCN/obsolescencia), persistir el estado en el producto y notificar los cambios por los canales existentes.

**Architecture:** Backend FastAPI + SQLAlchemy 2.0 + SQLite. Capas: modelo/migración → lógica pura (`obsolescencia.py`) → servicio BD (`obsolescencia_service.py`) → router protegido → orquestador semanal (`run_obsolescencia.py`, con `consultar_fabricante` inyectable). El research web lo hace Claude Code headless (glue documentado, no testeado).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (Mapped/mapped_column), pytest, TestClient en SQLite memoria.

**Convenciones del repo (importantes):**
- Todos los comandos de test se ejecutan **desde `backend/`** con el venv: `.\.venv\Scripts\python.exe -m pytest ...`. En PowerShell usar `Push-Location backend; try { ... } finally { Pop-Location }`.
- La BD de dev es `backend/postventa.db` (URL relativa al CWD → ejecutar siempre desde `backend/`).
- Migraciones: `app/migrations.py::add_missing_columns` añade columnas que falten con ALTER (idempotente); `create_all` crea tablas nuevas pero **no** añade columnas a tablas existentes.
- Tests usan fixtures de `backend/tests/conftest.py`: `db_session` (Session sobre SQLite memoria), `client` (TestClient con auth simulada), `client_sin_auth` (auth real, para tests de 401).
- ⚠️ El seeder de ayuda toca `postventa.db` al importar `app.main`; los tests usan motor en memoria, no la BD de dev. No arrancar uvicorn durante los tests.

---

## File Structure

- `backend/app/models.py` (modificar) — columnas nuevas en `Producto` y `Fabricante`, modelo `NoticiaObsolescencia`.
- `backend/app/migrations.py` (modificar) — columnas nuevas en `productos` y `fabricantes`.
- `backend/app/obsolescencia.py` (crear) — lógica pura: taxonomía, severidad, transición/cambio notable, regla URL.
- `backend/app/obsolescencia_service.py` (crear) — BD: lista de trabajo, registrar hallazgo, resumen, informe.
- `backend/app/schemas.py` (modificar) — campos nuevos en `ProductoOut`/`Fabricante*`, schemas de obsolescencia.
- `backend/app/routers/obsolescencia.py` (crear) — endpoints protegidos.
- `backend/app/main.py` (modificar) — registrar el router.
- `backend/run_obsolescencia.py` (crear) — orquestador semanal (entrypoint Task Scheduler).
- `backend/run_obsolescencia.cmd` (crear) — wrapper Windows.
- `backend/obsolescencia_prompt.md` (crear) — prompt para `claude -p` headless.
- Tests: `tests/test_obsolescencia_modelo.py`, `test_migrations.py` (modificar), `tests/test_obsolescencia_logica.py`, `tests/test_obsolescencia_schemas.py`, `tests/test_obsolescencia_service.py`, `tests/test_obsolescencia_api.py`, `tests/test_run_obsolescencia.py`.

---

## Task 1: Modelo + migración

**Files:**
- Modify: `backend/app/models.py` (clase `Producto` ~líneas 53-67, `Fabricante` ~líneas 319-329; añadir clase nueva al final de la sección de modelos)
- Modify: `backend/app/migrations.py:12-24` (dict `_COLUMNAS_NUEVAS`)
- Test: `backend/tests/test_obsolescencia_modelo.py` (crear), `backend/tests/test_migrations.py` (modificar)

- [ ] **Step 1: Write the failing test (modelo)**

Crear `backend/tests/test_obsolescencia_modelo.py`:

```python
from datetime import date

from app import models


def test_producto_tiene_campos_ciclo_vida(db_session):
    p = models.Producto(part_number="X1", tipo="componente", descripcion="Demo",
                         fabricante="Keysight", pn_fabricante="ABC")
    p.estado_ciclo_vida = "nrnd"
    p.ciclo_vida_fecha = date(2026, 1, 1)
    p.ciclo_vida_url = "https://k.example/pcn"
    p.ciclo_vida_resumen = "NRND por PCN-123"
    p.ciclo_vida_verificado_en = date(2026, 6, 11)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "nrnd"
    assert p.ciclo_vida_fecha == date(2026, 1, 1)
    assert p.ciclo_vida_verificado_en == date(2026, 6, 11)


def test_fabricante_tiene_url_obsolescencia(db_session):
    f = models.Fabricante(nombre="Keysight", url_obsolescencia="https://k.example/eol")
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    assert f.url_obsolescencia == "https://k.example/eol"


def test_noticia_obsolescencia_persiste(db_session):
    p = models.Producto(part_number="X2", tipo="componente", descripcion="Demo2",
                        fabricante="NI", pn_fabricante="DEF")
    db_session.add(p)
    db_session.commit()
    n = models.NoticiaObsolescencia(
        producto_id=p.id, fecha_deteccion=date(2026, 6, 11),
        estado_anterior="activo", estado_nuevo="obsoleto",
        fecha_evento=date(2026, 12, 31), url_fuente="https://ni.example/eol",
        resumen="Discontinuado", notificado=False)
    db_session.add(n)
    db_session.commit()
    db_session.refresh(n)
    assert n.id is not None
    assert n.estado_nuevo == "obsoleto"
    assert n.notificado is False
```

- [ ] **Step 2: Run test to verify it fails**

Run (desde `backend/`): `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_modelo.py -q`
Expected: FAIL (`AttributeError` / no existe `NoticiaObsolescencia`).

- [ ] **Step 3: Implement — columnas en Producto**

En `backend/app/models.py`, dentro de `class Producto`, tras `categoria_componente` (línea ~67) añadir:

```python
    estado_ciclo_vida: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ciclo_vida_fecha: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ciclo_vida_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ciclo_vida_resumen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ciclo_vida_verificado_en: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
```

En `class Fabricante`, tras `notas` (línea ~329) añadir:

```python
    url_obsolescencia: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

Al final de la zona de modelos (p. ej. tras `class GarantiaFabricante`), añadir:

```python
class NoticiaObsolescencia(Base):
    __tablename__ = "noticias_obsolescencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    fecha_deteccion: Mapped[date] = mapped_column(Date)
    estado_anterior: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String)
    fecha_evento: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    url_fuente: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resumen: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notificado: Mapped[bool] = mapped_column(Boolean, default=False)
```

Nota: `Integer, String, Text, Boolean, Date, ForeignKey, Mapped, mapped_column, Optional` ya están importados en `models.py` (los usan `Producto`/`Fabricante`/`GarantiaFabricante`). Verifícalo; si falta `Text` o `Boolean`, añádelo al import de `sqlalchemy`.

- [ ] **Step 4: Run modelo test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_modelo.py -q`
Expected: PASS (3 tests). En el motor en memoria `create_all` ya crea las columnas/tabla.

- [ ] **Step 5: Write the failing test (migración)**

En `backend/tests/test_migrations.py`, añadir al final (mira el patrón de los tests existentes del fichero; usan un engine SQLite temporal con tablas “viejas” sin las columnas):

```python
def test_migracion_anade_columnas_obsolescencia(tmp_path):
    from sqlalchemy import create_engine, text
    from app.migrations import add_missing_columns

    db = tmp_path / "old.db"
    eng = create_engine(f"sqlite+pysqlite:///{db}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT)")
        conn.exec_driver_sql("CREATE TABLE fabricantes (id INTEGER PRIMARY KEY, nombre TEXT)")

    add_missing_columns(eng)

    with eng.connect() as conn:
        prod_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(productos)"))}
        fab_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(fabricantes)"))}
    assert {"estado_ciclo_vida", "ciclo_vida_fecha", "ciclo_vida_url",
            "ciclo_vida_resumen", "ciclo_vida_verificado_en"} <= prod_cols
    assert "url_obsolescencia" in fab_cols
    eng.dispose()
```

- [ ] **Step 6: Run migración test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_migrations.py::test_migracion_anade_columnas_obsolescencia -q`
Expected: FAIL (faltan columnas en el dict).

- [ ] **Step 7: Implement — migración**

En `backend/app/migrations.py`, dentro de `_COLUMNAS_NUEVAS`, ampliar `productos` y añadir `fabricantes`:

```python
    "productos": {"meses_garantia_default": "INTEGER DEFAULT 24", "categoria": "TEXT",
                  "pn_fabricante": "TEXT", "fabricante_id": "INTEGER",
                  "categoria_componente": "TEXT",
                  "estado_ciclo_vida": "TEXT", "ciclo_vida_fecha": "DATE",
                  "ciclo_vida_url": "TEXT", "ciclo_vida_resumen": "TEXT",
                  "ciclo_vida_verificado_en": "DATE"},
    "fabricantes": {"url_obsolescencia": "TEXT"},
```

(La tabla `noticias_obsolescencia` la crea `create_all`; no necesita entrada aquí.)

- [ ] **Step 8: Run all migración + modelo tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_migrations.py tests/test_obsolescencia_modelo.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models.py backend/app/migrations.py backend/tests/test_obsolescencia_modelo.py backend/tests/test_migrations.py
git commit -m "feat(obsolescencia): modelo y migracion de ciclo de vida"
```

---

## Task 2: Lógica pura — `app/obsolescencia.py`

**Files:**
- Create: `backend/app/obsolescencia.py`
- Test: `backend/tests/test_obsolescencia_logica.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_obsolescencia_logica.py`:

```python
import pytest

from app import obsolescencia as ob


def test_estados_y_severidad():
    assert ob.ESTADOS == ["activo", "nrnd", "eol_anunciado", "ultima_compra", "obsoleto"]
    assert ob.severidad("activo") == 0
    assert ob.severidad("obsoleto") == 4
    assert ob.severidad(None) == 0          # sin verificar = baseline
    assert ob.severidad("desconocido") == 0


def test_estado_valido():
    assert ob.estado_valido("nrnd") is True
    assert ob.estado_valido("activo") is True
    assert ob.estado_valido("zzz") is False
    assert ob.estado_valido(None) is False


def test_requiere_url():
    assert ob.requiere_url("activo") is False
    assert ob.requiere_url("nrnd") is True
    assert ob.requiere_url("obsoleto") is True


def test_es_cambio_notable_solo_si_empeora():
    assert ob.es_cambio_notable(None, "activo") is False     # primera vez activo: no avisa
    assert ob.es_cambio_notable(None, "obsoleto") is True
    assert ob.es_cambio_notable("activo", "nrnd") is True
    assert ob.es_cambio_notable("nrnd", "nrnd") is False      # se mantiene: no duplica
    assert ob.es_cambio_notable("obsoleto", "activo") is False  # recuperación: no avisa
    assert ob.es_cambio_notable("activo", "zzz") is False     # estado inválido


def test_validar_hallazgo():
    ob.validar_hallazgo("activo", None)                 # ok sin url
    ob.validar_hallazgo("obsoleto", "https://x")        # ok con url
    with pytest.raises(ValueError):
        ob.validar_hallazgo("obsoleto", None)           # downgrade sin fuente
    with pytest.raises(ValueError):
        ob.validar_hallazgo("zzz", "https://x")         # estado inválido
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_logica.py -q`
Expected: FAIL (módulo no existe).

- [ ] **Step 3: Implement**

Crear `backend/app/obsolescencia.py`:

```python
"""Lógica pura del ciclo de vida de productos (obsolescencia). Sin BD ni IO."""
from __future__ import annotations

from typing import Optional

ESTADOS = ["activo", "nrnd", "eol_anunciado", "ultima_compra", "obsoleto"]
SEVERIDAD = {e: i for i, e in enumerate(ESTADOS)}


def estado_valido(estado: Optional[str]) -> bool:
    return estado in SEVERIDAD


def severidad(estado: Optional[str]) -> int:
    """Severidad 0..4. Estado None/desconocido = 0 (línea base 'activo')."""
    return SEVERIDAD.get(estado, 0)


def requiere_url(estado: Optional[str]) -> bool:
    """Cualquier estado distinto de 'activo' debe traer fuente (anti-alucinación)."""
    return estado_valido(estado) and estado != "activo"


def es_cambio_notable(anterior: Optional[str], nuevo: Optional[str]) -> bool:
    """True solo si `nuevo` es válido y empeora (mayor severidad) respecto a `anterior`."""
    if not estado_valido(nuevo):
        return False
    return severidad(nuevo) > severidad(anterior)


def validar_hallazgo(estado: Optional[str], url: Optional[str]) -> None:
    """Lanza ValueError si el estado no es válido o si un no-'activo' viene sin url."""
    if not estado_valido(estado):
        raise ValueError(f"estado de ciclo de vida no válido: {estado!r}")
    if requiere_url(estado) and not url:
        raise ValueError(f"el estado {estado!r} requiere una url de fuente")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_logica.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/obsolescencia.py backend/tests/test_obsolescencia_logica.py
git commit -m "feat(obsolescencia): logica pura de estados y validacion"
```

---

## Task 3: Schemas

**Files:**
- Modify: `backend/app/schemas.py` (`ProductoOut` ~83-95, `FabricanteCreate/Update/Out` ~773-802; añadir bloque nuevo de schemas de obsolescencia)
- Test: `backend/tests/test_obsolescencia_schemas.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_obsolescencia_schemas.py`:

```python
from datetime import date

import pytest
from pydantic import ValidationError

from app import schemas


def test_hallazgo_valida_estado():
    h = schemas.HallazgoObsolescencia(producto_id=1, estado="obsoleto",
                                      url="https://x", resumen="EOL")
    assert h.estado == "obsoleto"
    with pytest.raises(ValidationError):
        schemas.HallazgoObsolescencia(producto_id=1, estado="zzz")


def test_producto_out_expone_ciclo_vida():
    campos = schemas.ProductoOut.model_fields
    for c in ["estado_ciclo_vida", "ciclo_vida_fecha", "ciclo_vida_url",
              "ciclo_vida_resumen", "ciclo_vida_verificado_en"]:
        assert c in campos


def test_fabricante_schemas_tienen_url_obsolescencia():
    assert "url_obsolescencia" in schemas.FabricanteCreate.model_fields
    assert "url_obsolescencia" in schemas.FabricanteUpdate.model_fields
    assert "url_obsolescencia" in schemas.FabricanteOut.model_fields


def test_producto_a_revisar_out():
    o = schemas.ProductoARevisarOut(id=1, fabricante="NI", pn_fabricante="DEF",
                                    descripcion="x", estado_ciclo_vida=None,
                                    url_obsolescencia="https://ni/eol")
    assert o.pn_fabricante == "DEF"


def test_resumen_out():
    r = schemas.ObsolescenciaResumenOut(conteos={"activo": 2}, sin_verificar=5, noticias=[])
    assert r.sin_verificar == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_schemas.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

En `backend/app/schemas.py`:

(a) Tras `_CATEGORIA_COMPONENTE` (línea ~66) añadir:

```python
_ESTADO_CICLO = Literal["activo", "nrnd", "eol_anunciado", "ultima_compra", "obsoleto"]
```

(b) En `class ProductoOut` (tras `categoria_componente`, línea ~95) añadir:

```python
    estado_ciclo_vida: Optional[str] = None
    ciclo_vida_fecha: Optional[date] = None
    ciclo_vida_url: Optional[str] = None
    ciclo_vida_resumen: Optional[str] = None
    ciclo_vida_verificado_en: Optional[date] = None
```

(c) En `FabricanteCreate`, `FabricanteUpdate` y `FabricanteOut` añadir, junto a `notas`:

```python
    url_obsolescencia: Optional[str] = None
```

(d) Al final del fichero, añadir el bloque de obsolescencia:

```python
# --- Obsolescencia ---
class HallazgoObsolescencia(BaseModel):
    producto_id: int
    estado: _ESTADO_CICLO
    fecha_evento: Optional[date] = None
    url: Optional[str] = None
    resumen: Optional[str] = None


class ProductoARevisarOut(BaseModel):
    id: int
    fabricante: Optional[str] = None
    pn_fabricante: Optional[str] = None
    descripcion: str
    estado_ciclo_vida: Optional[str] = None
    url_obsolescencia: Optional[str] = None


class NoticiaObsolescenciaOut(_ORM):
    id: int
    producto_id: int
    fecha_deteccion: date
    estado_anterior: Optional[str] = None
    estado_nuevo: str
    fecha_evento: Optional[date] = None
    url_fuente: Optional[str] = None
    resumen: Optional[str] = None
    notificado: bool


class ObsolescenciaResumenOut(BaseModel):
    conteos: dict[str, int]
    sin_verificar: int
    noticias: list[NoticiaObsolescenciaOut] = Field(default_factory=list)
```

Nota: `_ORM`, `BaseModel`, `Field`, `Literal`, `Optional`, `date`, `ConfigDict` ya se usan en el fichero. `_ORM` es la base con `from_attributes=True` que usan `ProductoOut`/`ComponenteOut`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_schemas.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_obsolescencia_schemas.py
git commit -m "feat(obsolescencia): schemas de hallazgo, producto-a-revisar y resumen"
```

---

## Task 4: Servicio — lista de trabajo, registrar hallazgo, resumen

**Files:**
- Create: `backend/app/obsolescencia_service.py`
- Test: `backend/tests/test_obsolescencia_service.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_obsolescencia_service.py`:

```python
from datetime import date, timedelta

from app import models, obsolescencia_service as svc


def _prod(db, pn, fab="Keysight", pnf="ABC", **kw):
    p = models.Producto(part_number=pn, tipo="componente", descripcion=pn,
                        fabricante=fab, pn_fabricante=pnf, **kw)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_productos_a_revisar_solo_con_fabricante_y_pn(db_session):
    _prod(db_session, "A")                                   # con fab+pn -> sí
    p2 = models.Producto(part_number="B", tipo="componente", descripcion="B")
    db_session.add(p2); db_session.commit()                  # sin fab/pn -> no
    res = svc.productos_a_revisar(db_session, date(2026, 6, 11))
    pns = {p.part_number for p in res}
    assert pns == {"A"}


def test_productos_a_revisar_respeta_dias(db_session):
    p = _prod(db_session, "A")
    p.ciclo_vida_verificado_en = date(2026, 6, 11)           # verificado hoy
    db_session.commit()
    # con dias=7 y hoy=2026-06-15 todavía no toca (verificado hace 4 días)
    assert svc.productos_a_revisar(db_session, date(2026, 6, 15), dias=7) == []
    # hoy=2026-06-20 (9 días después) sí toca
    assert len(svc.productos_a_revisar(db_session, date(2026, 6, 20), dias=7)) == 1


def test_productos_a_revisar_limite(db_session):
    for i in range(5):
        _prod(db_session, f"P{i}", pnf=f"PN{i}")
    res = svc.productos_a_revisar(db_session, date(2026, 6, 11), limite=2)
    assert len(res) == 2


def test_registrar_hallazgo_crea_noticia_si_empeora(db_session):
    p = _prod(db_session, "A")
    r = svc.registrar_hallazgo(db_session, p.id, "obsoleto", hoy=date(2026, 6, 11),
                               fecha_evento=date(2026, 12, 31), url="https://x", resumen="EOL")
    assert r["registrado"] is True and r["cambio"] is True
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "obsoleto"
    assert p.ciclo_vida_verificado_en == date(2026, 6, 11)
    assert db_session.query(models.NoticiaObsolescencia).count() == 1


def test_registrar_hallazgo_activo_no_crea_noticia(db_session):
    p = _prod(db_session, "A")
    r = svc.registrar_hallazgo(db_session, p.id, "activo", hoy=date(2026, 6, 11))
    assert r["cambio"] is False
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "activo"
    assert p.ciclo_vida_verificado_en == date(2026, 6, 11)
    assert db_session.query(models.NoticiaObsolescencia).count() == 0


def test_registrar_hallazgo_sin_url_se_descarta(db_session):
    p = _prod(db_session, "A")
    r = svc.registrar_hallazgo(db_session, p.id, "obsoleto", hoy=date(2026, 6, 11), url=None)
    assert r["registrado"] is False and r["motivo"] == "sin_url"
    db_session.refresh(p)
    assert p.estado_ciclo_vida is None          # no se tocó
    assert db_session.query(models.NoticiaObsolescencia).count() == 0


def test_registrar_hallazgo_mismo_estado_no_duplica(db_session):
    p = _prod(db_session, "A")
    svc.registrar_hallazgo(db_session, p.id, "nrnd", hoy=date(2026, 6, 11), url="https://x")
    r2 = svc.registrar_hallazgo(db_session, p.id, "nrnd", hoy=date(2026, 6, 18), url="https://x")
    assert r2["cambio"] is False
    assert db_session.query(models.NoticiaObsolescencia).count() == 1
    db_session.refresh(p)
    assert p.ciclo_vida_verificado_en == date(2026, 6, 18)   # sí actualiza verificado


def test_resumen_obsolescencia(db_session):
    p1 = _prod(db_session, "A"); p2 = _prod(db_session, "B", pnf="B")
    svc.registrar_hallazgo(db_session, p1.id, "obsoleto", hoy=date(2026, 6, 11), url="https://x")
    svc.registrar_hallazgo(db_session, p2.id, "activo", hoy=date(2026, 6, 11))
    r = svc.resumen_obsolescencia(db_session)
    assert r["conteos"]["obsoleto"] == 1
    assert r["conteos"]["activo"] == 1
    assert len(r["noticias"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_service.py -q`
Expected: FAIL (módulo no existe).

- [ ] **Step 3: Implement**

Crear `backend/app/obsolescencia_service.py`:

```python
"""Servicio de obsolescencia: lista de trabajo, registro de hallazgos y resumen.
Escribe directo a BD (lo usa el orquestador semanal sin auth y el router con auth)."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, obsolescencia


def productos_a_revisar(db: Session, hoy: date, *, dias: int = 7, limite: int | None = None):
    """Productos con fabricante+pn_fabricante no verificados en los últimos `dias`.
    No verificados primero; `limite` reparte el catálogo entre ejecuciones."""
    umbral = hoy - timedelta(days=dias)
    q = (
        db.query(models.Producto)
        .filter(models.Producto.fabricante.isnot(None))
        .filter(models.Producto.pn_fabricante.isnot(None))
        .filter(or_(models.Producto.ciclo_vida_verificado_en.is_(None),
                    models.Producto.ciclo_vida_verificado_en <= umbral))
        .order_by(models.Producto.ciclo_vida_verificado_en.is_(None).desc(),
                  models.Producto.ciclo_vida_verificado_en.asc())
    )
    if limite is not None:
        q = q.limit(limite)
    return q.all()


def registrar_hallazgo(db: Session, producto_id: int, estado: str, *, hoy: date,
                       fecha_evento: date | None = None, url: str | None = None,
                       resumen: str | None = None) -> dict:
    p = db.get(models.Producto, producto_id)
    if p is None:
        return {"registrado": False, "motivo": "no_existe", "cambio": False}
    if not obsolescencia.estado_valido(estado):
        return {"registrado": False, "motivo": "estado_invalido", "cambio": False}
    if obsolescencia.requiere_url(estado) and not url:
        return {"registrado": False, "motivo": "sin_url", "cambio": False}

    anterior = p.estado_ciclo_vida
    notable = obsolescencia.es_cambio_notable(anterior, estado)

    p.estado_ciclo_vida = estado
    p.ciclo_vida_fecha = fecha_evento
    p.ciclo_vida_url = url
    p.ciclo_vida_resumen = resumen
    p.ciclo_vida_verificado_en = hoy

    if notable:
        db.add(models.NoticiaObsolescencia(
            producto_id=p.id, fecha_deteccion=hoy, estado_anterior=anterior,
            estado_nuevo=estado, fecha_evento=fecha_evento, url_fuente=url,
            resumen=resumen, notificado=False))
    db.commit()
    return {"registrado": True, "cambio": notable, "motivo": None}


def resumen_obsolescencia(db: Session, *, limite_noticias: int = 20) -> dict:
    conteos = {e: 0 for e in obsolescencia.ESTADOS}
    sin_verificar = 0
    for (estado,) in db.query(models.Producto.estado_ciclo_vida).all():
        if estado in conteos:
            conteos[estado] += 1
        else:
            sin_verificar += 1
    noticias = (
        db.query(models.NoticiaObsolescencia)
        .order_by(models.NoticiaObsolescencia.fecha_deteccion.desc(),
                  models.NoticiaObsolescencia.id.desc())
        .limit(limite_noticias).all()
    )
    return {"conteos": conteos, "sin_verificar": sin_verificar, "noticias": noticias}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_service.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/obsolescencia_service.py backend/tests/test_obsolescencia_service.py
git commit -m "feat(obsolescencia): servicio de lista de trabajo, registro y resumen"
```

---

## Task 5: Servicio — informe / notificación

**Files:**
- Modify: `backend/app/obsolescencia_service.py` (añadir `construir_informe` y `enviar_informe`)
- Test: `backend/tests/test_obsolescencia_service.py` (añadir)

- [ ] **Step 1: Write the failing test**

Añadir a `backend/tests/test_obsolescencia_service.py`:

```python
def test_enviar_informe_envia_solo_no_notificadas_y_marca(db_session):
    p = _prod(db_session, "A")
    svc.registrar_hallazgo(db_session, p.id, "obsoleto", hoy=date(2026, 6, 11), url="https://x")
    capturado = {}

    def fake_notificar(asunto, cuerpo):
        capturado["asunto"] = asunto
        capturado["cuerpo"] = cuerpo
        return {"email": True, "telegram": True}

    r = svc.enviar_informe(db_session, date(2026, 6, 11), notificar_fn=fake_notificar)
    assert r["enviado"] is True and r["total"] == 1
    assert "A" in capturado["cuerpo"] and "obsoleto" in capturado["cuerpo"]
    # marcada como notificada
    assert db_session.query(models.NoticiaObsolescencia).filter_by(notificado=True).count() == 1
    # segunda llamada: nada que enviar
    r2 = svc.enviar_informe(db_session, date(2026, 6, 12), notificar_fn=fake_notificar)
    assert r2["enviado"] is False and r2["total"] == 0


def test_enviar_informe_no_envia_si_vacio(db_session):
    llamado = {"n": 0}

    def fake_notificar(asunto, cuerpo):
        llamado["n"] += 1
        return {}

    r = svc.enviar_informe(db_session, date(2026, 6, 11), notificar_fn=fake_notificar)
    assert r["enviado"] is False
    assert llamado["n"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_service.py -k informe -q`
Expected: FAIL (`enviar_informe` no existe).

- [ ] **Step 3: Implement**

Añadir a `backend/app/obsolescencia_service.py` (import nuevo arriba: `from app import notificaciones`):

```python
def construir_informe(db: Session, hoy: date) -> dict:
    noticias = (
        db.query(models.NoticiaObsolescencia)
        .filter(models.NoticiaObsolescencia.notificado.is_(False))
        .order_by(models.NoticiaObsolescencia.fecha_deteccion.asc(),
                  models.NoticiaObsolescencia.id.asc())
        .all()
    )
    total = len(noticias)
    asunto = f"[6TL Postventa] Cambios de obsolescencia ({total})"
    lineas = [f"Cambios de ciclo de vida detectados al {hoy.isoformat()}:", ""]
    for n in noticias:
        p = db.get(models.Producto, n.producto_id)
        ref = p.part_number if p else f"producto#{n.producto_id}"
        linea = f"- {ref}: {n.estado_anterior or 'sin verificar'} -> {n.estado_nuevo}"
        if n.url_fuente:
            linea += f"  ({n.url_fuente})"
        lineas.append(linea)
    return {"asunto": asunto, "cuerpo": "\n".join(lineas), "total": total, "noticias": noticias}


def enviar_informe(db: Session, hoy: date, *, notificar_fn=notificaciones.notificar) -> dict:
    info = construir_informe(db, hoy)
    if info["total"] == 0:
        return {"asunto": info["asunto"], "cuerpo": info["cuerpo"], "total": 0,
                "canales": {"email": None, "telegram": None}, "enviado": False}
    canales = notificar_fn(info["asunto"], info["cuerpo"])
    for n in info["noticias"]:
        n.notificado = True
    db.commit()
    return {"asunto": info["asunto"], "cuerpo": info["cuerpo"], "total": info["total"],
            "canales": canales, "enviado": True}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_service.py -q`
Expected: PASS (todos, 10 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/obsolescencia_service.py backend/tests/test_obsolescencia_service.py
git commit -m "feat(obsolescencia): informe semanal con guard de no-envio vacio"
```

---

## Task 6: Router + registro en main

**Files:**
- Create: `backend/app/routers/obsolescencia.py`
- Modify: `backend/app/main.py` (registrar router, junto a los demás ~línea 103)
- Test: `backend/tests/test_obsolescencia_api.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_obsolescencia_api.py`:

```python
from datetime import date

from app import models


def _prod(client_db, pn, fab="Keysight", pnf="ABC", fabricante_id=None):
    # helper que inserta vía la sesión de BD del cliente (usa el override get_db)
    pass


def test_productos_a_revisar_endpoint(client, db_session_factory=None):
    # crea productos directamente en la BD del cliente
    from app.db import get_db
    db = next(client.app.dependency_overrides[get_db]())
    f = models.Fabricante(nombre="Keysight", url_obsolescencia="https://k/eol")
    db.add(f); db.commit(); db.refresh(f)
    p = models.Producto(part_number="A", tipo="componente", descripcion="A",
                        fabricante="Keysight", pn_fabricante="ABC", fabricante_id=f.id)
    db.add(p); db.commit()

    r = client.get("/api/obsolescencia/productos-a-revisar")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["pn_fabricante"] == "ABC"
    assert data[0]["url_obsolescencia"] == "https://k/eol"


def test_post_hallazgos_y_resumen(client):
    from app.db import get_db
    db = next(client.app.dependency_overrides[get_db]())
    p = models.Producto(part_number="A", tipo="componente", descripcion="A",
                        fabricante="NI", pn_fabricante="DEF")
    db.add(p); db.commit(); db.refresh(p)

    r = client.post("/api/obsolescencia/hallazgos", json=[
        {"producto_id": p.id, "estado": "obsoleto", "url": "https://x", "resumen": "EOL"},
    ])
    assert r.status_code == 200
    assert r.json()["cambios"] == 1

    r2 = client.get("/api/obsolescencia")
    assert r2.status_code == 200
    body = r2.json()
    assert body["conteos"]["obsoleto"] == 1
    assert len(body["noticias"]) == 1


def test_hallazgo_estado_invalido_422(client):
    r = client.post("/api/obsolescencia/hallazgos", json=[
        {"producto_id": 1, "estado": "zzz"}])
    assert r.status_code == 422


def test_obsolescencia_protegido_401(client_sin_auth):
    assert client_sin_auth.get("/api/obsolescencia").status_code == 401
    assert client_sin_auth.get("/api/obsolescencia/productos-a-revisar").status_code == 401
    assert client_sin_auth.post("/api/obsolescencia/hallazgos", json=[]).status_code == 401
```

Nota: el patrón `next(client.app.dependency_overrides[get_db]())` para sembrar datos lo usan otros tests del repo (revisa `tests/test_avisos_api.py` o `test_sla.py` y replica su forma exacta de obtener la sesión si difiere; el objetivo es insertar productos antes de llamar al endpoint).

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_api.py -q`
Expected: FAIL (404 / router no existe).

- [ ] **Step 3: Implement — router**

Crear `backend/app/routers/obsolescencia.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, obsolescencia_service
from app.db import get_db
from app.schemas import (HallazgoObsolescencia, ObsolescenciaResumenOut,
                         ProductoARevisarOut)

router = APIRouter(prefix="/api/obsolescencia", tags=["obsolescencia"])


@router.get("", response_model=ObsolescenciaResumenOut)
def resumen(db: Session = Depends(get_db)):
    return obsolescencia_service.resumen_obsolescencia(db)


@router.get("/productos-a-revisar", response_model=list[ProductoARevisarOut])
def productos_a_revisar(dias: int = 7, limite: Optional[int] = None,
                        db: Session = Depends(get_db)):
    prods = obsolescencia_service.productos_a_revisar(db, date.today(), dias=dias, limite=limite)
    salida = []
    for p in prods:
        url = None
        if p.fabricante_id is not None:
            f = db.get(models.Fabricante, p.fabricante_id)
            url = f.url_obsolescencia if f else None
        salida.append(ProductoARevisarOut(
            id=p.id, fabricante=p.fabricante, pn_fabricante=p.pn_fabricante,
            descripcion=p.descripcion, estado_ciclo_vida=p.estado_ciclo_vida,
            url_obsolescencia=url))
    return salida


@router.post("/hallazgos")
def registrar_hallazgos(payload: list[HallazgoObsolescencia],
                        db: Session = Depends(get_db)):
    hoy = date.today()
    detalle = [
        obsolescencia_service.registrar_hallazgo(
            db, h.producto_id, h.estado, hoy=hoy, fecha_evento=h.fecha_evento,
            url=h.url, resumen=h.resumen)
        for h in payload
    ]
    return {"procesados": len(detalle),
            "cambios": sum(1 for d in detalle if d["cambio"]),
            "detalle": detalle}
```

- [ ] **Step 4: Implement — registro en main**

En `backend/app/main.py`, tras el bloque de `fabricantes` (línea ~103) añadir:

```python
from app.routers import obsolescencia
app.include_router(obsolescencia.router, dependencies=[Depends(get_current_user)])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_obsolescencia_api.py -q`
Expected: PASS. Si el helper de siembra falla, ajústalo al patrón real del repo (ver nota del Step 1) sin cambiar las aserciones.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/obsolescencia.py backend/app/main.py backend/tests/test_obsolescencia_api.py
git commit -m "feat(obsolescencia): router protegido y registro en main"
```

---

## Task 7: Orquestador semanal — `run_obsolescencia.py`

**Files:**
- Create: `backend/run_obsolescencia.py`
- Test: `backend/tests/test_run_obsolescencia.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_run_obsolescencia.py`:

```python
from datetime import date

from app import models
import run_obsolescencia as runo


def _prod(db, pn, fab="Keysight", pnf="ABC"):
    p = models.Producto(part_number=pn, tipo="componente", descripcion=pn,
                        fabricante=fab, pn_fabricante=pnf)
    db.add(p); db.commit(); db.refresh(p)
    return p


def test_ejecutar_recorre_registra_y_notifica(db_session):
    p1 = _prod(db_session, "A")
    p2 = _prod(db_session, "B", pnf="DEF")

    # stub: A pasa a obsoleto (con url), B sigue activo
    veredictos = {
        "A": {"estado": "obsoleto", "url_fuente": "https://x", "resumen": "EOL",
              "fecha_evento": date(2026, 12, 31)},
        "B": {"estado": "activo", "url_fuente": None, "resumen": None, "fecha_evento": None},
    }

    def fake_consultar(producto, url_obsolescencia):
        return veredictos[producto.part_number]

    enviados = {}

    def fake_notificar(asunto, cuerpo):
        enviados["cuerpo"] = cuerpo
        return {"email": True, "telegram": None}

    r = runo.ejecutar(db_session, date(2026, 6, 11), limite=10,
                      consultar=fake_consultar, notificar_fn=fake_notificar)

    db_session.refresh(p1); db_session.refresh(p2)
    assert p1.estado_ciclo_vida == "obsoleto"
    assert p2.estado_ciclo_vida == "activo"
    assert r["enviado"] is True and r["total"] == 1          # solo A genera noticia
    assert "A" in enviados["cuerpo"]


def test_ejecutar_salta_veredicto_none(db_session):
    p = _prod(db_session, "A")

    def fake_consultar(producto, url_obsolescencia):
        return None                                          # research no concluyente

    r = runo.ejecutar(db_session, date(2026, 6, 11),
                      consultar=fake_consultar, notificar_fn=lambda a, c: {})
    db_session.refresh(p)
    assert p.estado_ciclo_vida is None
    assert r["enviado"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_run_obsolescencia.py -q`
Expected: FAIL (módulo no existe).

- [ ] **Step 3: Implement**

Crear `backend/run_obsolescencia.py`:

```python
"""Orquestador semanal de obsolescencia (Task Scheduler, como run_digest.py).

Recorre los productos a revisar, pregunta el estado de ciclo de vida a la web del
fabricante (vía Claude Code headless por defecto) y registra los cambios,
enviando un informe de los que han empeorado. Escribe directo a BD (sin auth).

Uso:
    python run_obsolescencia.py                 # ejecuta y notifica
    python run_obsolescencia.py --limite 30     # tope de productos en esta pasada
    python run_obsolescencia.py --dry-run       # consulta y registra, NO envía informe
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date

from app.env_file import load_env_file

load_env_file()

from app.db import SessionLocal
from app import models, obsolescencia_service, notificaciones  # noqa: F401


def _url_fabricante(db, producto) -> str | None:
    if producto.fabricante_id is None:
        return None
    f = db.get(models.Fabricante, producto.fabricante_id)
    return f.url_obsolescencia if f else None


def consultar_fabricante(producto, url_obsolescencia):
    """Lanza Claude Code headless para investigar el estado de ciclo de vida.

    Devuelve {estado, fecha_evento, url_fuente, resumen} o None si no concluyente.
    `claude -p` recibe el prompt de `obsolescencia_prompt.md` con los datos del
    producto y debe responder SOLO un JSON. Si algo falla, devuelve None (se
    reintenta la semana siguiente)."""
    from pathlib import Path

    plantilla = (Path(__file__).with_name("obsolescencia_prompt.md")).read_text(encoding="utf-8")
    prompt = plantilla.format(
        fabricante=producto.fabricante or "",
        pn=producto.pn_fabricante or "",
        descripcion=producto.descripcion or "",
        url=url_obsolescencia or "(sin URL conocida; busca en abierto)",
    )
    try:
        out = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, timeout=180, check=True,
        ).stdout.strip()
        inicio, fin = out.find("{"), out.rfind("}")
        if inicio == -1 or fin == -1:
            return None
        data = json.loads(out[inicio:fin + 1])
        if not data.get("estado"):
            return None
        fe = data.get("fecha_evento")
        return {
            "estado": data["estado"],
            "fecha_evento": date.fromisoformat(fe) if fe else None,
            "url_fuente": data.get("url_fuente"),
            "resumen": data.get("resumen"),
        }
    except Exception:
        return None


def ejecutar(db, hoy, *, limite=20, consultar=consultar_fabricante,
             notificar_fn=notificaciones.notificar):
    prods = obsolescencia_service.productos_a_revisar(db, hoy, limite=limite)
    for p in prods:
        url = _url_fabricante(db, p)
        v = consultar(p, url)
        if not v:
            continue
        obsolescencia_service.registrar_hallazgo(
            db, p.id, v["estado"], hoy=hoy, fecha_evento=v.get("fecha_evento"),
            url=v.get("url_fuente"), resumen=v.get("resumen"))
    return obsolescencia_service.enviar_informe(db, hoy, notificar_fn=notificar_fn)


def main() -> int:
    dry = "--dry-run" in sys.argv
    limite = 20
    if "--limite" in sys.argv:
        limite = int(sys.argv[sys.argv.index("--limite") + 1])
    with SessionLocal() as db:
        if dry:
            prods = obsolescencia_service.productos_a_revisar(db, date.today(), limite=limite)
            for p in prods:
                v = consultar_fabricante(p, _url_fabricante(db, p))
                if v:
                    obsolescencia_service.registrar_hallazgo(
                        db, p.id, v["estado"], hoy=date.today(),
                        fecha_evento=v.get("fecha_evento"), url=v.get("url_fuente"),
                        resumen=v.get("resumen"))
            info = obsolescencia_service.construir_informe(db, date.today())
            print(f"[dry-run] cambios pendientes de notificar: {info['total']}")
            return 0
        r = ejecutar(db, date.today(), limite=limite)
    print(f"enviado: {r['enviado']}  total: {r['total']}  canales: {r.get('canales')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_run_obsolescencia.py -q`
Expected: PASS (2 tests). El test inyecta `consultar`/`notificar_fn`, así que nunca llama a `claude`.

- [ ] **Step 5: Commit**

```bash
git add backend/run_obsolescencia.py backend/tests/test_run_obsolescencia.py
git commit -m "feat(obsolescencia): orquestador semanal con consultar_fabricante inyectable"
```

---

## Task 8: Glue (wrapper + prompt + docs) — sin tests

**Files:**
- Create: `backend/obsolescencia_prompt.md`
- Create: `backend/run_obsolescencia.cmd`
- Modify: `docs/` o nota de ops (registro de la tarea en Task Scheduler)

- [ ] **Step 1: Crear el prompt para `claude -p`**

Crear `backend/obsolescencia_prompt.md`:

```markdown
Eres un analista de obsolescencia de componentes electrónicos. Investiga el estado
de ciclo de vida del siguiente producto consultando la web del fabricante.

Fabricante: {fabricante}
Part number del fabricante: {pn}
Descripción: {descripcion}
Página PCN/EOL conocida: {url}

Pasos:
1. Si hay una URL conocida, consúltala primero (WebFetch). Si no, busca en abierto
   "{fabricante} {pn} end of life / PCN / discontinued / obsolete".
2. Determina el estado de ciclo de vida actual del part number.

Responde ÚNICAMENTE con un objeto JSON (sin texto alrededor) con esta forma:
{{"estado": "<activo|nrnd|eol_anunciado|ultima_compra|obsoleto>",
  "fecha_evento": "<YYYY-MM-DD o null>",
  "url_fuente": "<url de la fuente o null>",
  "resumen": "<una frase>"}}

Reglas:
- Si NO encuentras evidencia de cambio, responde estado "activo" con url_fuente null.
- Cualquier estado distinto de "activo" DEBE incluir url_fuente; si no tienes fuente
  fiable, responde "activo".
- No inventes. Ante la duda, "activo".
```

Nota: las llaves del JSON van **dobladas** (`{{` `}}`) porque la plantilla se formatea con `str.format` en `consultar_fabricante`; los marcadores `{fabricante}`, `{pn}`, `{descripcion}`, `{url}` quedan simples.

- [ ] **Step 2: Crear el wrapper Windows**

Crear `backend/run_obsolescencia.cmd`:

```bat
@echo off
REM Wrapper para el Programador de tareas de Windows (ejecución semanal).
cd /d "%~dp0"
".venv\Scripts\python.exe" run_obsolescencia.py >> logs\obsolescencia.log 2>&1
```

Crear la carpeta de logs si no existe: `backend/logs/` (añadir un `.gitkeep` o confiar en que ya existe por el digest).

- [ ] **Step 3: Smoke del wrapper (dry-run, NO llama a claude si no está)**

Run (desde `backend/`): `.\.venv\Scripts\python.exe run_obsolescencia.py --dry-run --limite 1`
Expected: imprime `[dry-run] cambios pendientes de notificar: N`. Si `claude` no está en PATH, `consultar_fabricante` captura la excepción y devuelve None → 0 cambios. No debe romper.

- [ ] **Step 4: Documentar el alta de la tarea programada**

Añadir al final de `backend/run_obsolescencia.py` NADA más; en su lugar dejar la instrucción de ops aquí (el implementador NO crea la tarea, la propone al usuario):

Comando de alta sugerido (semanal, lunes 07:30), para que el usuario lo apruebe:

```powershell
schtasks /Create /TN "6TL Postventa - Obsolescencia semanal" /TR "\"%CD%\run_obsolescencia.cmd\"" /SC WEEKLY /D MON /ST 07:30 /F
```

- [ ] **Step 5: Commit**

```bash
git add backend/obsolescencia_prompt.md backend/run_obsolescencia.cmd
git commit -m "chore(obsolescencia): prompt headless, wrapper y nota de programacion"
```

---

## Task 9: Suite completa + verificación final

- [ ] **Step 1: Ejecutar toda la suite**

Run (desde `backend/`): `.\.venv\Scripts\python.exe -m pytest -q`
Expected: todos los tests previos (393 antes de esta feature) + los nuevos en verde. ⚠️ Si el seeder de ayuda intenta tocar `postventa.db`, asegúrate de que uvicorn no está corriendo.

- [ ] **Step 2: Smoke en vivo (opcional, requiere backend arrancado)**

Con el backend en :8020 y un token válido: `GET /api/obsolescencia` → 200 con `conteos` (todo en `sin_verificar` al principio). No ejecutar el orquestador real todavía (lo hará el usuario al programar la tarea).

- [ ] **Step 3: Commit final si quedaron cambios sueltos**

```bash
git add -A && git commit -m "test(obsolescencia): verificacion de suite completa"
```

---

## Notas de cierre

- **Frontend Lovable** queda como follow-up (badge de estado + ruta `/obsolescencia` + URL de fabricante editable). No bloquea el backend.
- **`claude -p` headless** es el punto más frágil; por eso `consultar_fabricante` está aislada e inyectable, el orquestador tiene tope por ejecución y la regla "sin URL no se degrada" evita falsos obsoletos.
- **Programar la tarea** la decide el usuario (igual que el digest); el plan solo deja el comando sugerido.
