# Auto-clasificación de trazabilidad — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-rellenar los flags `afecta_a_medida` y `bajo_coste` de cada producto componente mediante un motor de reglas (síncrono al crear/editar) + un agente LLM para los casos ambiguos (por lote), respetando lo fijado a mano.

**Architecture:** Módulo puro de reglas (`app/clasificacion_trazabilidad.py`, estilo `app/criticidad.py`) + agente LLM inyectable (estilo `consultar_fabricante` de obsolescencia) + servicio orquestador sobre BD que escribe `clasificacion_origen='agente'` y nunca pisa `origen='manual'`, todo auditado. Trigger síncrono de reglas en el router de productos; lote vía endpoint protegido + CLI.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, SQLite, pytest. venv en `backend/.venv` (ejecutar tests con `.venv/Scripts/python.exe -m pytest`).

---

## Notas de entorno (leer antes de empezar)
- CWD para todo: `backend/`. Tests: `.venv/Scripts/python.exe -m pytest`.
- ⚠️ Parar cualquier `uvicorn` en marcha antes de tests (el seeder de ayuda toca `postventa.db` al importar). Hay un uvicorn de dev corriendo en :8020 — pararlo o ignorar (los tests usan SQLite en memoria, pero evita el `--reload` re-importando).
- Fixtures de test en `tests/conftest.py`: `client` (auth simulada, `db.info` con usuario de prueba), `client_sin_auth` (auth real, para 401), `db_session` (sesión sobre motor en memoria).
- Auditoría: el servicio escribe con `db.info["usuario_username"]` ya puesto por el override/auth; los scripts CLI lo ponen a mano (ver `_clasificar_categoria_componente.py`).
- Las propiedades `criticidad`/`nivel_trazabilidad` del modelo NO se tocan: delegan en `app/criticidad.py` y solo leen `afecta_a_medida`/`bajo_coste`/categoría/override.

## File Structure
- Create: `app/clasificacion_trazabilidad.py` — motor de reglas puro (sin BD).
- Create: `app/clasificacion_service.py` — orquestación sobre BD (producto + lote), auditoría.
- Create: `app/clasificacion_llm.py` — `consultar_clasificacion` headless inyectable + parseo.
- Create: `app/routers/clasificacion.py` — `POST /api/clasificacion-trazabilidad/lote`.
- Create: `clasificacion_prompt.md` — plantilla de prompt para el LLM (en `backend/`).
- Create: `run_clasificacion.py` (+ `run_clasificacion.cmd`) — CLI de lote/backfill.
- Modify: `app/models.py` — columnas `clasificacion_origen`, `clasificacion_motivo` en `Producto`.
- Modify: `app/migrations.py` — añadir esas 2 columnas al dict `productos`.
- Modify: `app/schemas.py` — exponerlas en `ProductoOut`.
- Modify: `app/routers/productos.py` — trigger de reglas al vuelo en `crear`/`actualizar`.
- Modify: `app/main.py` — `include_router(clasificacion.router, dependencies=[Depends(get_current_user)])`.
- Test: `tests/test_clasificacion_trazabilidad.py`, `tests/test_clasificacion_service.py`, `tests/test_clasificacion_llm.py`, `tests/test_clasificacion_router.py`, `tests/test_productos_trigger_clasificacion.py`, `tests/test_migrations_clasificacion.py`.

---

## Task 1: Motor de reglas puro

**Files:**
- Create: `app/clasificacion_trazabilidad.py`
- Test: `tests/test_clasificacion_trazabilidad.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_clasificacion_trazabilidad.py
import pytest
from app.clasificacion_trazabilidad import clasificar_por_reglas, ResultadoClasificacion


def test_instrumento_afecta_a_medida_no_ambiguo():
    r = clasificar_por_reglas("instrumento", "Keysight", "DMM 6.5 digitos", "34461A")
    assert r.afecta_a_medida is True
    assert r.bajo_coste is False
    assert r.ambiguo is False
    assert r.motivo


def test_mass_interconnect_afecta_a_medida():
    r = clasificar_por_reglas("mass_interconnect", "Virginia Panel", "Receiver", "VP-90")
    assert r.afecta_a_medida is True
    assert r.ambiguo is False


def test_wiring_con_keyword_barata_es_bajo_coste():
    r = clasificar_por_reglas("wiring", None, "Patch cord generico 1m", "PC-1M")
    assert r.bajo_coste is True
    assert r.afecta_a_medida is False
    assert r.ambiguo is False


def test_wiring_con_keyword_de_medida_afecta_y_no_bajo_coste():
    r = clasificar_por_reglas("wiring", None, "Cable de sense Kelvin 4 hilos", "SNS-4")
    assert r.afecta_a_medida is True
    assert r.bajo_coste is False
    assert r.ambiguo is False


def test_accesorios_sin_keyword_es_ambiguo():
    r = clasificar_por_reglas("accesorios", None, "Modulo auxiliar", "AUX-1")
    assert r.ambiguo is True


def test_accesorios_tornillo_es_bajo_coste_no_ambiguo():
    r = clasificar_por_reglas("accesorios", None, "Tornillo M3 inox", "M3")
    assert r.bajo_coste is True
    assert r.ambiguo is False


def test_software_flags_false():
    r = clasificar_por_reglas("software", "6TL", "Licencia TestStand", "SW-1")
    assert r.afecta_a_medida is False
    assert r.bajo_coste is False
    assert r.ambiguo is False


def test_fixture_adaptador_flags_false():
    r = clasificar_por_reglas("fixture_adaptador", "6TL", "Fixture banco X", "FX-1")
    assert r.afecta_a_medida is False
    assert r.bajo_coste is False


def test_marca_instrumentacion_pero_descr_barata_es_ambiguo():
    r = clasificar_por_reglas("accesorios", "Keysight", "Etiqueta adhesiva", "LBL-1")
    assert r.ambiguo is True


def test_categoria_nula_sin_keyword_es_ambiguo():
    r = clasificar_por_reglas(None, None, "Pieza", "X1")
    assert r.ambiguo is True


def test_funciona_sobre_duck_type_via_kwargs():
    # firma posicional estable
    r = clasificar_por_reglas("instrumento", "", "", "")
    assert isinstance(r, ResultadoClasificacion)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_clasificacion_trazabilidad.py -q`
Expected: FAIL (`ModuleNotFoundError: app.clasificacion_trazabilidad`).

- [ ] **Step 3: Implement the module**

```python
# app/clasificacion_trazabilidad.py
"""Motor de reglas puro: decide afecta_a_medida / bajo_coste de un componente.

Sin BD. Lee solo categoria_componente, fabricante, descripcion, part_number.
Marca `ambiguo=True` cuando las señales son débiles o en conflicto, para que un
agente LLM resuelva ese residuo (ver app/clasificacion_llm.py).
"""
from __future__ import annotations

from dataclasses import dataclass

# Marcas de instrumentación (sub-cadena del fabricante, case-insensitive).
# Espejo de _INSTRUMENTO_SUBSTR del clasificador de categoría.
_INSTRUMENTO_SUBSTR = (
    "keysight", "agilent", "national instruments", "pickering",
    "chroma", "ametek", "hocherl", "hoecherl", "höcherl", "rohde", "tektronix",
)
# Señales de que el elemento está en la cadena de medida.
_MEDIDA_KW = (
    "sense", "sonda", "probe", "referencia", "reference", "calibr", "precis",
    "sensor", "medida", "measurement", "dmm", "shunt", "termopar",
    "thermocouple", "rtd", "kelvin",
)
# Señales de estándar barato / no trazable individualmente.
_BARATO_KW = (
    "tornillo", "screw", "etiqueta", "label", "brida", "bracket", "soporte",
    "tapa", "cover", "patch", "latiguillo", "generic", "generico", "genérico",
    "standard", "estandar", "estándar",
)
_CAT_AFECTA = {"instrumento", "mass_interconnect"}
_CAT_VERSION = {"software", "fixture_adaptador"}
_CAT_GENERICA = {"wiring", "accesorios"}


@dataclass
class ResultadoClasificacion:
    afecta_a_medida: bool
    bajo_coste: bool
    ambiguo: bool
    motivo: str


def _tiene(texto: str, palabras) -> bool:
    t = (texto or "").lower()
    return any(p in t for p in palabras)


def clasificar_por_reglas(categoria_componente, fabricante, descripcion,
                          part_number) -> ResultadoClasificacion:
    desc = descripcion or ""
    fab = (fabricante or "").strip().lower()
    es_instr_marca = any(s in fab for s in _INSTRUMENTO_SUBSTR) or fab == "ni"
    medida = _tiene(desc, _MEDIDA_KW)
    barato = _tiene(desc, _BARATO_KW)

    # Categorías que la propia categoría ya resuelve sin flags.
    if categoria_componente in _CAT_VERSION:
        return ResultadoClasificacion(False, False, False,
                                      f"categoria {categoria_componente}: por version")
    if categoria_componente in _CAT_AFECTA:
        return ResultadoClasificacion(True, False, False,
                                      f"categoria {categoria_componente}: afecta a medida")

    # Señal léxica fuerte de medida gana sobre todo.
    if medida:
        return ResultadoClasificacion(True, False, False, "descripcion indica cadena de medida")

    # Conflicto: marca cara pero descripción de accesorio barato -> que decida el LLM.
    if es_instr_marca and barato:
        return ResultadoClasificacion(False, True, True,
                                      "marca de instrumentacion con descripcion barata (conflicto)")

    if barato:
        return ResultadoClasificacion(False, True, False, "descripcion de estandar barato")

    # Genéricas sin pista, o categoría nula -> ambiguo (LLM), default conservador media.
    if categoria_componente in _CAT_GENERICA or not categoria_componente:
        return ResultadoClasificacion(False, False, True,
                                      "sin senal decisiva; requiere revision")

    return ResultadoClasificacion(False, False, False, "sin senales especiales: media")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_clasificacion_trazabilidad.py -q`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add app/clasificacion_trazabilidad.py tests/test_clasificacion_trazabilidad.py
git commit -m "Clasificacion trazabilidad: motor de reglas puro afecta_a_medida/bajo_coste"
```

---

## Task 2: Columnas de modelo + migración + schema

**Files:**
- Modify: `app/models.py` (clase `Producto`, junto a `nivel_trazabilidad_override`)
- Modify: `app/migrations.py` (dict `_COLUMNAS_NUEVAS["productos"]`)
- Modify: `app/schemas.py` (`ProductoOut`)
- Test: `tests/test_migrations_clasificacion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migrations_clasificacion.py
from sqlalchemy import create_engine, text
from app.db import Base
from app import migrations


def _crear_db_sin_columnas(path_url):
    eng = create_engine(path_url)
    with eng.begin() as c:
        c.exec_driver_sql(
            "CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT,"
            " tipo TEXT, descripcion TEXT)")
    return eng


def test_migracion_añade_columnas_clasificacion(tmp_path):
    url = f"sqlite:///{tmp_path/'m.db'}"
    eng = _crear_db_sin_columnas(url)
    migrations.add_missing_columns(eng)
    with eng.connect() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(productos)"))}
    assert "clasificacion_origen" in cols
    assert "clasificacion_motivo" in cols


def test_migracion_es_idempotente(tmp_path):
    url = f"sqlite:///{tmp_path/'m.db'}"
    eng = _crear_db_sin_columnas(url)
    migrations.add_missing_columns(eng)
    migrations.add_missing_columns(eng)  # no debe lanzar
    with eng.connect() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(productos)"))}
    assert "clasificacion_origen" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrations_clasificacion.py -q`
Expected: FAIL (columna no presente).

- [ ] **Step 3: Implement**

En `app/models.py`, en la clase `Producto`, justo después de
`nivel_trazabilidad_override: ... = mapped_column(String, nullable=True)`:

```python
    clasificacion_origen: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    clasificacion_motivo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

En `app/migrations.py`, dentro de `_COLUMNAS_NUEVAS["productos"]`, añade dos entradas
al dict (antes de cerrar la llave de `productos`):

```python
                  "clasificacion_origen": "TEXT", "clasificacion_motivo": "TEXT",
```

En `app/schemas.py`, en `ProductoOut`, tras `ciclo_vida_origen: Optional[str] = None`:

```python
    clasificacion_origen: Optional[str] = None
    clasificacion_motivo: Optional[str] = None
```

- [ ] **Step 4: Run test + full suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrations_clasificacion.py -q && .venv/Scripts/python.exe -m pytest -q`
Expected: PASS (nuevos 2 + suite previa sigue verde).

- [ ] **Step 5: Commit**

```bash
git add app/models.py app/migrations.py app/schemas.py tests/test_migrations_clasificacion.py
git commit -m "Clasificacion trazabilidad: columnas origen/motivo + migracion + ProductoOut"
```

---

## Task 3: Agente LLM inyectable (consultar_clasificacion)

**Files:**
- Create: `app/clasificacion_llm.py`
- Create: `clasificacion_prompt.md`
- Test: `tests/test_clasificacion_llm.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_clasificacion_llm.py
from app.clasificacion_llm import _parsear_respuesta


def test_parsea_json_estricto():
    out = '{"afecta_a_medida": true, "bajo_coste": false, "razon": "es un DMM"}'
    r = _parsear_respuesta(out)
    assert r == {"afecta_a_medida": True, "bajo_coste": False, "razon": "es un DMM"}


def test_parsea_json_envuelto_en_texto():
    out = 'Claro:\n{"afecta_a_medida": false, "bajo_coste": true, "razon": "cable"}\nFin.'
    r = _parsear_respuesta(out)
    assert r["bajo_coste"] is True


def test_respuesta_invalida_devuelve_none():
    assert _parsear_respuesta("no soy json") is None


def test_respuesta_sin_razon_devuelve_none():
    out = '{"afecta_a_medida": true, "bajo_coste": false}'
    assert _parsear_respuesta(out) is None


def test_respuesta_tipos_incorrectos_devuelve_none():
    out = '{"afecta_a_medida": "si", "bajo_coste": false, "razon": "x"}'
    assert _parsear_respuesta(out) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_clasificacion_llm.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

Crea `clasificacion_prompt.md` en `backend/`:

```markdown
Eres un ingeniero de test ATE. Clasifica este COMPONENTE para trazabilidad.

Fabricante: {fabricante}
Part number: {pn}
Categoria: {categoria}
Descripcion: {descripcion}

Decide DOS booleanos:
- afecta_a_medida: true si el componente influye en el resultado de la medida
  (instrumentos, sondas, referencias, sensores, cableado de sense/Kelvin, shunts).
- bajo_coste: true si es un elemento estandar barato no trazable individualmente
  (tornilleria, etiquetas, latiguillos genericos, soportes).
Si afecta_a_medida es true, bajo_coste debe ser false.

Responde SOLO con un JSON en una linea, sin texto alrededor:
{{"afecta_a_medida": <bool>, "bajo_coste": <bool>, "razon": "<motivo breve>"}}
```

Crea `app/clasificacion_llm.py`:

```python
"""Agente LLM headless para clasificar componentes ambiguos (afecta_a_medida/bajo_coste).

`consultar_clasificacion` es inyectable: el default llama a Claude Code headless con
la descripcion del producto (sin herramientas web). Los tests inyectan un fake.
Parseo robusto y conservador: ante cualquier duda devuelve None (el servicio se queda
con el resultado de reglas; nunca escribe basura).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _claude_bin() -> str:
    env = os.environ.get("CLAUDE_BIN")
    if env and Path(env).exists():
        return env
    enpath = shutil.which("claude")
    if enpath:
        return enpath
    local = Path.home() / ".local" / "bin" / "claude.exe"
    return str(local) if local.exists() else "claude"


def _parsear_respuesta(out: str) -> Optional[dict]:
    if not out:
        return None
    inicio, fin = out.find("{"), out.rfind("}")
    if inicio < 0 or fin <= inicio:
        return None
    try:
        data = json.loads(out[inicio:fin + 1])
    except (ValueError, TypeError):
        return None
    am, bc, razon = data.get("afecta_a_medida"), data.get("bajo_coste"), data.get("razon")
    if not isinstance(am, bool) or not isinstance(bc, bool):
        return None
    if not isinstance(razon, str) or not razon.strip():
        return None
    if am and bc:  # incoherente: medida manda
        bc = False
    return {"afecta_a_medida": am, "bajo_coste": bc, "razon": razon.strip()}


def consultar_clasificacion(part_number, descripcion, fabricante, categoria,
                            *, timeout=None, _popen=None) -> Optional[dict]:
    """Devuelve {afecta_a_medida, bajo_coste, razon} o None si no decide."""
    if timeout is None:
        timeout = int(os.environ.get("CLASIFICACION_TIMEOUT_SEG", "60"))
    plantilla = Path(__file__).parent.parent / "clasificacion_prompt.md"
    prompt = plantilla.read_text(encoding="utf-8").format(
        fabricante=fabricante or "", pn=part_number or "",
        categoria=categoria or "", descripcion=descripcion or "")
    cmd = [_claude_bin(), "--output-format", "text", "-p", prompt]

    def _abrir():
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, text=True,
                                encoding="utf-8", errors="replace")
    try:
        proc = (_popen or _abrir)()
        out, _ = proc.communicate(timeout=timeout)
    except Exception:
        return None
    return _parsear_respuesta(out)
```

> Nota: el `clasificacion_prompt.md` vive en `backend/` (junto a `obsolescencia_prompt.md`); por eso se resuelve con `Path(__file__).parent.parent`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_clasificacion_llm.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/clasificacion_llm.py clasificacion_prompt.md tests/test_clasificacion_llm.py
git commit -m "Clasificacion trazabilidad: agente LLM headless inyectable + parseo robusto"
```

---

## Task 4: Servicio (clasificar_producto + clasificar_lote)

**Files:**
- Create: `app/clasificacion_service.py`
- Test: `tests/test_clasificacion_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_clasificacion_service.py
import pytest
from app import models, auditoria
from app.clasificacion_service import clasificar_producto, clasificar_lote


@pytest.fixture
def _audit():
    auditoria.registrar_listeners()  # idempotente
    yield


def _prod(db, **kw):
    base = dict(part_number=kw.pop("pn", "P1"), tipo="componente",
                descripcion=kw.pop("descripcion", ""), categoria_componente=kw.pop("cat", None),
                fabricante=kw.pop("fab", None))
    p = models.Producto(**base, **kw)
    db.add(p); db.commit(); db.refresh(p)
    return p


def test_reglas_escriben_flags_y_origen(db_session, _audit):
    db_session.info["usuario_username"] = "tester"
    p = _prod(db_session, pn="DMM1", descripcion="DMM", cat="instrumento")
    res = clasificar_producto(db_session, p, usar_llm=False)
    assert p.afecta_a_medida is True
    assert p.clasificacion_origen == "agente"
    assert p.clasificacion_motivo
    assert res.estado == "clasificado"


def test_respeta_origen_manual(db_session, _audit):
    p = _prod(db_session, pn="X", descripcion="DMM", cat="instrumento")
    p.clasificacion_origen = "manual"; p.afecta_a_medida = False
    db_session.commit()
    res = clasificar_producto(db_session, p, usar_llm=False)
    assert res.estado == "omitido_manual"
    assert p.afecta_a_medida is False  # no lo pisa


def test_ambiguo_usa_llm_cuando_disponible(db_session, _audit):
    p = _prod(db_session, pn="A", descripcion="Modulo auxiliar", cat="accesorios")
    fake = lambda *a, **k: {"afecta_a_medida": True, "bajo_coste": False, "razon": "LLM dice medida"}
    clasificar_producto(db_session, p, usar_llm=True, consultar=fake)
    assert p.afecta_a_medida is True
    assert "LLM" in p.clasificacion_motivo


def test_ambiguo_llm_invalido_cae_a_reglas(db_session, _audit):
    p = _prod(db_session, pn="A2", descripcion="Modulo auxiliar", cat="accesorios")
    fake = lambda *a, **k: None  # LLM no decide
    clasificar_producto(db_session, p, usar_llm=True, consultar=fake)
    assert p.afecta_a_medida is False and p.bajo_coste is False
    assert p.clasificacion_origen == "agente"


def test_lote_recorre_componentes_y_cuenta(db_session, _audit):
    _prod(db_session, pn="I1", descripcion="DMM", cat="instrumento")
    _prod(db_session, pn="W1", descripcion="Patch generico", cat="wiring")
    man = _prod(db_session, pn="M1", descripcion="DMM", cat="instrumento")
    man.clasificacion_origen = "manual"; db_session.commit()
    fake = lambda *a, **k: {"afecta_a_medida": False, "bajo_coste": True, "razon": "x"}
    resumen = clasificar_lote(db_session, usar_llm=True, consultar=fake)
    assert resumen.procesados == 2  # I1 y W1, no el manual
    assert resumen.omitidos_manual == 1


def test_lote_dry_run_no_escribe(db_session, _audit):
    p = _prod(db_session, pn="I9", descripcion="DMM", cat="instrumento")
    clasificar_lote(db_session, usar_llm=False, dry_run=True)
    db_session.refresh(p)
    assert p.clasificacion_origen is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_clasificacion_service.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# app/clasificacion_service.py
"""Orquesta la auto-clasificacion sobre BD: reglas + LLM para ambiguos.

Escribe afecta_a_medida/bajo_coste con clasificacion_origen='agente' y motivo.
NUNCA toca productos con clasificacion_origen='manual'. La auditoria se registra
sola via los listeners ORM (usuario tomado de db.info).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app import models
from app.clasificacion_trazabilidad import clasificar_por_reglas
from app.clasificacion_llm import consultar_clasificacion


@dataclass
class ResultadoAplicado:
    estado: str          # clasificado | omitido_manual | sin_cambios
    via: str | None      # reglas | llm | None
    afecta_a_medida: bool | None = None
    bajo_coste: bool | None = None
    motivo: str | None = None


@dataclass
class ResumenLote:
    procesados: int = 0
    por_reglas: int = 0
    por_llm: int = 0
    omitidos_manual: int = 0
    sin_cambios: int = 0
    cambios: list = field(default_factory=list)


def clasificar_producto(db: Session, producto, *, usar_llm: bool = False,
                        consultar=consultar_clasificacion,
                        dry_run: bool = False) -> ResultadoAplicado:
    if producto.clasificacion_origen == "manual":
        return ResultadoAplicado("omitido_manual", None)

    r = clasificar_por_reglas(producto.categoria_componente, producto.fabricante,
                              producto.descripcion, producto.part_number)
    via, afecta, bajo, motivo = "reglas", r.afecta_a_medida, r.bajo_coste, r.motivo

    if r.ambiguo and usar_llm:
        llm = consultar(producto.part_number, producto.descripcion,
                        producto.fabricante, producto.categoria_componente)
        if llm is not None:
            via = "llm"
            afecta, bajo = llm["afecta_a_medida"], llm["bajo_coste"]
            motivo = f"LLM: {llm['razon']}"

    sin_cambios = (producto.afecta_a_medida == afecta and producto.bajo_coste == bajo
                   and producto.clasificacion_origen == "agente")
    if not dry_run:
        producto.afecta_a_medida = afecta
        producto.bajo_coste = bajo
        producto.clasificacion_origen = "agente"
        producto.clasificacion_motivo = motivo
        db.commit()
    estado = "sin_cambios" if sin_cambios else "clasificado"
    return ResultadoAplicado(estado, via, afecta, bajo, motivo)


def clasificar_lote(db: Session, *, usar_llm: bool = True,
                    consultar=consultar_clasificacion, limite: int | None = None,
                    dry_run: bool = False) -> ResumenLote:
    q = (db.query(models.Producto)
         .filter(models.Producto.tipo == "componente")
         .order_by(models.Producto.part_number))
    resumen = ResumenLote()
    for p in q.all():
        if p.clasificacion_origen == "manual":
            resumen.omitidos_manual += 1
            continue
        if limite is not None and resumen.procesados >= limite:
            break
        res = clasificar_producto(db, p, usar_llm=usar_llm, consultar=consultar,
                                  dry_run=dry_run)
        resumen.procesados += 1
        if res.via == "llm":
            resumen.por_llm += 1
        elif res.via == "reglas":
            resumen.por_reglas += 1
        if res.estado == "sin_cambios":
            resumen.sin_cambios += 1
        else:
            resumen.cambios.append({
                "producto_id": p.id, "part_number": p.part_number,
                "afecta_a_medida": res.afecta_a_medida, "bajo_coste": res.bajo_coste,
                "origen": "agente", "motivo": res.motivo})
    return resumen
```

> Nota sobre `test_lote_recorre_componentes_y_cuenta`: hay 2 componentes agente (I1, W1) + 1 manual (M1). El conteo esperado es `procesados==2`, `omitidos_manual==1`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_clasificacion_service.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add app/clasificacion_service.py tests/test_clasificacion_service.py
git commit -m "Clasificacion trazabilidad: servicio clasificar_producto + clasificar_lote (respeta manual, audita)"
```

---

## Task 5: Trigger de reglas al vuelo en el router de productos

**Files:**
- Modify: `app/routers/productos.py` (`crear` y `actualizar`)
- Test: `tests/test_productos_trigger_clasificacion.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_productos_trigger_clasificacion.py
def _payload(**kw):
    base = dict(part_number="PN1", tipo="componente", descripcion="DMM 6.5",
                categoria_componente="instrumento")
    base.update(kw)
    return base


def test_crear_sin_flags_aplica_reglas(client):
    r = client.post("/api/productos", json=_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["afecta_a_medida"] is True
    assert body["clasificacion_origen"] == "agente"


def test_crear_con_flag_explicito_es_manual(client):
    r = client.post("/api/productos", json=_payload(afecta_a_medida=False))
    assert r.status_code == 201
    body = r.json()
    assert body["clasificacion_origen"] == "manual"
    assert body["afecta_a_medida"] is False  # respeta lo que mando el usuario


def test_actualizar_con_override_es_manual(client):
    cid = client.post("/api/productos", json=_payload()).json()["id"]
    r = client.put(f"/api/productos/{cid}",
                   json=_payload(nivel_trazabilidad_override="no_trazado"))
    assert r.status_code == 200
    assert r.json()["clasificacion_origen"] == "manual"


def test_actualizar_sin_flags_reaplica_reglas(client):
    cid = client.post("/api/productos", json=_payload()).json()["id"]
    r = client.put(f"/api/productos/{cid}",
                   json=_payload(descripcion="Patch cord generico", categoria_componente="wiring"))
    assert r.status_code == 200
    body = r.json()
    assert body["bajo_coste"] is True
    assert body["clasificacion_origen"] == "agente"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_productos_trigger_clasificacion.py -q`
Expected: FAIL (origen None / flags no aplicados).

- [ ] **Step 3: Implement**

En `app/routers/productos.py`, añade el import arriba:

```python
from app.clasificacion_service import clasificar_producto
```

Y un helper + su uso. Define antes de los endpoints:

```python
_FLAGS_MANUALES = {"afecta_a_medida", "bajo_coste", "nivel_trazabilidad_override"}


def _aplicar_clasificacion(db, p, payload):
    """Si el body trae flags explicitos -> manual; si no, reglas (solo componentes)."""
    if p.tipo != "componente":
        return
    if _FLAGS_MANUALES & payload.model_fields_set:
        p.clasificacion_origen = "manual"
        db.commit()
    else:
        clasificar_producto(db, p, usar_llm=False)
```

En `crear`, sustituye el cuerpo tras `db.refresh(p)` por:

```python
    db.refresh(p)
    _aplicar_clasificacion(db, p, payload)
    db.refresh(p)
    return p
```

En `actualizar`, igual tras el `db.refresh(p)` final:

```python
    db.refresh(p)
    _aplicar_clasificacion(db, p, payload)
    db.refresh(p)
    return p
```

- [ ] **Step 4: Run tests + full suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_productos_trigger_clasificacion.py -q && .venv/Scripts/python.exe -m pytest -q`
Expected: PASS (4 nuevos + suite verde).

- [ ] **Step 5: Commit**

```bash
git add app/routers/productos.py tests/test_productos_trigger_clasificacion.py
git commit -m "Clasificacion trazabilidad: trigger de reglas al crear/editar producto (manual vs agente)"
```

---

## Task 6: Endpoint de lote + CLI

**Files:**
- Create: `app/routers/clasificacion.py`
- Modify: `app/main.py`
- Create: `run_clasificacion.py`, `run_clasificacion.cmd`
- Test: `tests/test_clasificacion_router.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_clasificacion_router.py
def _comp(client, pn, cat, descripcion="x"):
    # crea con flag explicito para NO disparar reglas y poder probar el lote
    return client.post("/api/productos", json=dict(
        part_number=pn, tipo="componente", descripcion=descripcion,
        categoria_componente=cat, afecta_a_medida=False)).json()


def test_lote_protegido_sin_token_401(client_sin_auth):
    r = client_sin_auth.post("/api/clasificacion-trazabilidad/lote")
    assert r.status_code == 401


def test_lote_dry_run_no_escribe(client):
    c = _comp(client, "I1", "instrumento", "DMM")
    r = client.post("/api/clasificacion-trazabilidad/lote?dry_run=true")
    assert r.status_code == 200
    # como se creo manual, el lote lo omite
    assert r.json()["omitidos_manual"] >= 1


def test_lote_clasifica_componentes_agente(client):
    # producto agente (sin flags) ya quedo clasificado por el trigger; el lote
    # re-evalua y reporta sin_cambios o cambios
    client.post("/api/productos", json=dict(
        part_number="W1", tipo="componente", descripcion="Patch generico",
        categoria_componente="wiring"))
    r = client.post("/api/clasificacion-trazabilidad/lote")
    assert r.status_code == 200
    body = r.json()
    assert "procesados" in body and "cambios" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_clasificacion_router.py -q`
Expected: FAIL (404 / ruta no existe).

- [ ] **Step 3: Implement**

Crea `app/routers/clasificacion.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.clasificacion_service import clasificar_lote

router = APIRouter(prefix="/api/clasificacion-trazabilidad", tags=["clasificacion"])


@router.post("/lote")
def lote(dry_run: bool = False, usar_llm: bool = True, limite: int | None = None,
         db: Session = Depends(get_db)) -> dict:
    r = clasificar_lote(db, usar_llm=usar_llm, limite=limite, dry_run=dry_run)
    return {
        "procesados": r.procesados, "por_reglas": r.por_reglas, "por_llm": r.por_llm,
        "omitidos_manual": r.omitidos_manual, "sin_cambios": r.sin_cambios,
        "cambios": r.cambios,
    }
```

> Nota: el endpoint usa `usar_llm=True` por defecto, pero en los tests el LLM real
> nunca se invoca porque los componentes de prueba no son `ambiguo` (instrumento/wiring
> con keyword) o están `manual`. Para lotes reales con ambiguos, el LLM se llamará.

En `app/main.py`, junto a los otros `include_router`, añade el import y el registro:

```python
from app.routers import clasificacion
...
app.include_router(clasificacion.router, dependencies=[Depends(get_current_user)])
```

Crea `run_clasificacion.py` en `backend/` (estilo `run_obsolescencia.py`):

```python
"""Lote de auto-clasificacion de trazabilidad (backfill / Task Scheduler).

Recorre los productos componente, aplica reglas y LLM (para ambiguos) y escribe
afecta_a_medida/bajo_coste con origen='agente', respetando lo manual. Escribe
directo a BD (sin auth).

Uso (desde backend/):
    .venv\\Scripts\\python.exe run_clasificacion.py --dry-run
    .venv\\Scripts\\python.exe run_clasificacion.py            # escribe
    .venv\\Scripts\\python.exe run_clasificacion.py --sin-llm  # solo reglas
    .venv\\Scripts\\python.exe run_clasificacion.py --limite 50
"""
from __future__ import annotations

import argparse

from app.env_file import load_env_file

load_env_file()

from app.db import SessionLocal
from app import auditoria, clasificacion_service


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sin-llm", action="store_true")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    auditoria.registrar_listeners()
    db = SessionLocal()
    db.info["usuario_username"] = "clasificacion automatica"
    db.info["usuario_id"] = None
    try:
        r = clasificacion_service.clasificar_lote(
            db, usar_llm=not args.sin_llm, limite=args.limite, dry_run=args.dry_run)
        print(f"Procesados: {r.procesados} | reglas: {r.por_reglas} | LLM: {r.por_llm} "
              f"| omitidos manual: {r.omitidos_manual} | sin cambios: {r.sin_cambios}")
        for c in r.cambios:
            print(f"  {c['part_number']:18} afecta={c['afecta_a_medida']} "
                  f"bajo_coste={c['bajo_coste']}  {c['motivo']}")
        print("DRY-RUN: nada escrito." if args.dry_run else "ESCRITO.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

Crea `run_clasificacion.cmd` en `backend/`:

```bat
@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" run_clasificacion.py %*
```

- [ ] **Step 4: Run tests + full suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_clasificacion_router.py -q && .venv/Scripts/python.exe -m pytest -q`
Expected: PASS (3 nuevos + suite verde).

- [ ] **Step 5: Commit**

```bash
git add app/routers/clasificacion.py app/main.py run_clasificacion.py run_clasificacion.cmd tests/test_clasificacion_router.py
git commit -m "Clasificacion trazabilidad: endpoint POST /lote + CLI run_clasificacion"
```

---

## Task 7: Backfill del catálogo vivo (operación, no código)

**Files:** ninguno (operación sobre `backend/postventa.db`).

- [ ] **Step 1: Backup de la BD viva**

```bash
cp postventa.db "postventa.db.preclasificacion-$(date +%Y%m%d-%H%M%S).bak"
```

- [ ] **Step 2: Dry-run para ver el plan**

Run: `.venv/Scripts/python.exe run_clasificacion.py --dry-run`
Revisar el listado: cuántos por reglas, cuántos ambiguos (irían al LLM), distribución.

- [ ] **Step 3: Ejecutar solo reglas primero (rápido, gratis)**

Run: `.venv/Scripts/python.exe run_clasificacion.py --sin-llm`
Expected: escribe los deterministas; los ambiguos quedan con default conservador + origen=agente.

- [ ] **Step 4: Ejecutar el pase con LLM para los ambiguos**

Run: `.venv/Scripts/python.exe run_clasificacion.py`
(Requiere binario `claude` headless disponible. Si no, omitir y dejar reglas.)

- [ ] **Step 5: Verificar en vivo**

Arrancar backend (:8020) y comprobar con curl que `ProductoOut` trae
`clasificacion_origen`/`clasificacion_motivo` y que `criticidad`/`nivel_trazabilidad`
reflejan los flags. Confirmar que los productos editados a mano (si los hubiera)
siguen con `origen=manual`.

No hay commit (es la BD, gitignored).

---

## Cierre
- Suite completa verde: `.venv/Scripts/python.exe -m pytest -q`.
- Actualizar memoria del proyecto (`project_6tl_postventa.md` + índice).
- Follow-up (fuera de este plan): prompt Lovable 40 (badge Auto/Manual + tooltip motivo + editar-a-mano) y, si se quiere, tarea programada en Task Scheduler reusando `run_clasificacion.cmd`.
