# Report de obsolescencia por banco — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generar un report de obsolescencia acotado a un banco (equipo): estado de ciclo de vida de todos sus componentes, consultable por API JSON y exportable a Excel/PDF, con refresco síncrono acotado.

**Architecture:** Una función pura `informe_banco` compila el report desde el estado ya almacenado en los productos (única fuente de verdad para JSON y exportaciones). `refrescar_banco` reutiliza el orquestador existente (`registrar_hallazgo` + `consultar` inyectable) acotado a los productos del banco. Un router nuevo bajo `/api/equipos/{id}/obsolescencia` expone lectura, exportación y refresco.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, openpyxl (xlsx), reportlab (pdf), pytest.

**Spec:** `docs/superpowers/specs/2026-06-12-report-obsolescencia-banco-design.md`

**Trabajo desde:** `backend/` (CWD). Tests: `.venv/Scripts/python -m pytest`. Rama: `feat/report-obsolescencia-banco` (ya creada, contiene el spec).

**Convención reutilizada:**
- `app/obsolescencia.py`: `ESTADOS`, `severidad(estado)` (None→0), `SEVERIDAD`.
- `app/obsolescencia_service.py`: `registrar_hallazgo(db, producto_id, estado, *, hoy, fecha_evento, url, resumen)` (set estado + crea `NoticiaObsolescencia` si empeora).
- `run_obsolescencia.py`: `consultar_fabricante(producto, url)` → `{estado, fecha_evento, url_fuente, resumen}` o `None`.
- Modelos: `Equipo.componentes` (→`Componente`), `Componente.producto` (→`Producto`, lleva los `ciclo_vida_*`), `Componente.categoria_componente` (property), `Equipo.cliente_id`/`contrato_id`, `Producto.fabricante_id`→`Fabricante.url_obsolescencia`, `Cliente.nombre`, `ContratoMantenimiento.nivel`.
- Tests: fixtures `client` (auth simulada), `client_sin_auth` (auth real), `db_session` (mismo motor en memoria que `client`).

---

## Task 0: Dependencias openpyxl + reportlab

**Files:**
- Modify: `backend/pyproject.toml:6-11`

- [ ] **Step 1: Añadir las dos dependencias**

En `pyproject.toml`, dejar el bloque `dependencies` así:

```toml
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sqlalchemy>=2.0",
    "pydantic>=2.6",
    "openpyxl>=3.1",
    "reportlab>=4.0",
]
```

- [ ] **Step 2: Instalar en el venv**

Run: `.venv/Scripts/python -m pip install "openpyxl>=3.1" "reportlab>=4.0"`
Expected: instala ambas (o "Requirement already satisfied").

- [ ] **Step 3: Verificar import**

Run: `.venv/Scripts/python -c "import openpyxl, reportlab; print('ok')"`
Expected: imprime `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: openpyxl + reportlab para exportar reports"
```

---

## Task 1: `informe_banco` — compilar el report desde el estado almacenado

**Files:**
- Create: `backend/app/obsolescencia_banco.py`
- Test: `backend/tests/test_obsolescencia_banco.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/tests/test_obsolescencia_banco.py
from datetime import date

from app import models, obsolescencia_banco


def _seed_banco(db):
    """Banco con 3 componentes: obsoleto, activo, sin verificar."""
    pe = models.Producto(part_number="IUTB-01", tipo="equipo", descripcion="iUTB")
    cli = models.Cliente(nombre="Indra")
    db.add_all([pe, cli]); db.flush()
    eq = models.Equipo(numero_serie="SN-TEST", producto_id=pe.id, cliente_id=cli.id,
                        estado="operativo")
    db.add(eq); db.flush()

    p_obs = models.Producto(part_number="P-OBS", tipo="componente", descripcion="Relé",
                            fabricante="Acme", pn_fabricante="ACM-9",
                            estado_ciclo_vida="obsoleto", ciclo_vida_url="http://acme/eol",
                            ciclo_vida_verificado_en=date(2026, 1, 1))
    p_act = models.Producto(part_number="P-ACT", tipo="componente", descripcion="Cable",
                            fabricante="Beta", pn_fabricante="BET-1",
                            estado_ciclo_vida="activo",
                            ciclo_vida_verificado_en=date(2026, 6, 1))
    p_nv = models.Producto(part_number="P-NV", tipo="componente", descripcion="Tornillo")
    db.add_all([p_obs, p_act, p_nv]); db.flush()
    db.add_all([
        models.Componente(numero_serie="C1", producto_id=p_obs.id, equipo_id=eq.id, posicion="3"),
        models.Componente(numero_serie="C2", producto_id=p_act.id, equipo_id=eq.id, posicion="1"),
        models.Componente(numero_serie="C3", producto_id=p_nv.id, equipo_id=eq.id, posicion="2"),
    ])
    db.commit()
    return eq.id


def test_informe_banco_ordena_por_severidad_y_resume(db_session):
    eq_id = _seed_banco(db_session)
    inf = obsolescencia_banco.informe_banco(db_session, eq_id, date(2026, 6, 12))

    assert inf["banco"]["numero_serie"] == "SN-TEST"
    assert inf["banco"]["cliente"] == "Indra"
    # el obsoleto va primero (mayor severidad)
    assert inf["componentes"][0]["part_number"] == "P-OBS"
    assert inf["componentes"][0]["severidad"] > 0
    assert inf["resumen"]["total"] == 3
    assert inf["resumen"]["en_riesgo"] == 1
    assert inf["resumen"]["sin_verificar"] == 1
    assert inf["resumen"]["conteos"]["obsoleto"] == 1
    assert inf["resumen"]["verificado_mas_antiguo"] == date(2026, 1, 1)
```

- [ ] **Step 2: Ejecutar para verlo fallar**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py -q`
Expected: FAIL (`module 'app' has no attribute 'obsolescencia_banco'` / ImportError).

- [ ] **Step 3: Implementar `informe_banco`**

```python
# backend/app/obsolescencia_banco.py
"""Report de obsolescencia acotado a un banco (equipo): estado de ciclo de vida
de sus componentes (lectura del estado almacenado) + refresco síncrono acotado."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app import models, obsolescencia, obsolescencia_service


def _url_fabricante(db: Session, producto: models.Producto) -> str | None:
    if producto.fabricante_id is None:
        return None
    f = db.get(models.Fabricante, producto.fabricante_id)
    return f.url_obsolescencia if f else None


def informe_banco(db: Session, equipo_id: int, hoy: date) -> dict:
    equipo = db.get(models.Equipo, equipo_id)
    if equipo is None:
        raise ValueError(f"equipo {equipo_id} no existe")

    cliente = db.get(models.Cliente, equipo.cliente_id) if equipo.cliente_id else None
    contrato_nivel = None
    if equipo.contrato_id is not None:
        c = db.get(models.ContratoMantenimiento, equipo.contrato_id)
        contrato_nivel = c.nivel if c else None

    filas = []
    conteos = {e: 0 for e in obsolescencia.ESTADOS}
    sin_verificar = 0
    en_riesgo = 0
    verificados = []
    for comp in equipo.componentes:
        p = comp.producto
        estado = p.estado_ciclo_vida
        sev = obsolescencia.severidad(estado)
        if estado in conteos:
            conteos[estado] += 1
        if estado is None:
            sin_verificar += 1
        if sev > 0:
            en_riesgo += 1
        if p.ciclo_vida_verificado_en is not None:
            verificados.append(p.ciclo_vida_verificado_en)
        filas.append({
            "componente_id": comp.id,
            "posicion": comp.posicion,
            "part_number": p.part_number,
            "fabricante": p.fabricante,
            "pn_fabricante": p.pn_fabricante,
            "descripcion": p.descripcion,
            "numero_serie": comp.numero_serie,
            "categoria_componente": comp.categoria_componente,
            "estado_ciclo_vida": estado,
            "severidad": sev,
            "ciclo_vida_fecha": p.ciclo_vida_fecha,
            "ciclo_vida_url": p.ciclo_vida_url,
            "ciclo_vida_resumen": p.ciclo_vida_resumen,
            "ciclo_vida_verificado_en": p.ciclo_vida_verificado_en,
        })

    filas.sort(key=lambda f: (-f["severidad"], f["posicion"] or "", f["part_number"]))

    return {
        "banco": {
            "equipo_id": equipo.id,
            "numero_serie": equipo.numero_serie,
            "producto": equipo.producto.part_number if equipo.producto else "",
            "descripcion": equipo.producto.descripcion if equipo.producto else None,
            "cliente": cliente.nombre if cliente else None,
            "estado": equipo.estado,
            "contrato_nivel": contrato_nivel,
        },
        "componentes": filas,
        "resumen": {
            "conteos": conteos,
            "en_riesgo": en_riesgo,
            "sin_verificar": sin_verificar,
            "total": len(filas),
            "verificado_mas_antiguo": min(verificados) if verificados else None,
        },
    }
```

- [ ] **Step 4: Ejecutar para verlo pasar**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py -q`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add app/obsolescencia_banco.py tests/test_obsolescencia_banco.py
git commit -m "feat(obsolescencia): informe_banco compila el report del banco"
```

---

## Task 2: `productos_de_equipo` + `refrescar_banco` (consultar inyectable)

**Files:**
- Modify: `backend/app/obsolescencia_banco.py`
- Test: `backend/tests/test_obsolescencia_banco.py` (añadir tests)

- [ ] **Step 1: Escribir los tests que fallan**

Añadir al final de `tests/test_obsolescencia_banco.py`:

```python
def test_productos_de_equipo_solo_verificables_no_verificados_primero(db_session):
    eq_id = _seed_banco(db_session)
    prods = obsolescencia_banco.productos_de_equipo(db_session, eq_id)
    pns = [p.part_number for p in prods]
    # P-NV no tiene fabricante/pn -> excluido; P-ACT está verificado, P-OBS también
    assert "P-NV" not in pns
    assert set(pns) == {"P-OBS", "P-ACT"}


def test_refrescar_banco_registra_estado_crea_noticia_y_respeta_limite(db_session):
    eq_id = _seed_banco(db_session)
    llamados = []

    def fake_consultar(producto, url):
        llamados.append(producto.part_number)
        # empeora P-ACT (activo -> obsoleto); el resto sin cambio concluyente
        if producto.part_number == "P-ACT":
            return {"estado": "obsoleto", "fecha_evento": None,
                    "url_fuente": "http://beta/eol", "resumen": "EOL"}
        return None

    inf = obsolescencia_banco.refrescar_banco(
        db_session, eq_id, date(2026, 6, 12), limite=10, consultar=fake_consultar)

    # P-ACT quedó obsoleto y generó noticia (empeora)
    p_act = db_session.query(models.Producto).filter_by(part_number="P-ACT").one()
    assert p_act.estado_ciclo_vida == "obsoleto"
    noticias = db_session.query(models.NoticiaObsolescencia).filter_by(producto_id=p_act.id).all()
    assert len(noticias) == 1
    assert inf["resumen"]["total"] == 3


def test_refrescar_banco_respeta_limite(db_session):
    eq_id = _seed_banco(db_session)
    llamados = []

    def fake_consultar(producto, url):
        llamados.append(producto.part_number)
        return None

    obsolescencia_banco.refrescar_banco(
        db_session, eq_id, date(2026, 6, 12), limite=1, consultar=fake_consultar)
    assert len(llamados) == 1
```

- [ ] **Step 2: Ejecutar para verlos fallar**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py -q`
Expected: FAIL (`module 'app.obsolescencia_banco' has no attribute 'productos_de_equipo'`).

- [ ] **Step 3: Implementar las dos funciones**

Añadir a `app/obsolescencia_banco.py`:

```python
def productos_de_equipo(db: Session, equipo_id: int) -> list[models.Producto]:
    """Productos distintos de los componentes del banco con fabricante+pn_fabricante
    (verificables). No verificados primero, luego por verificado_en ascendente."""
    equipo = db.get(models.Equipo, equipo_id)
    if equipo is None:
        return []
    vistos: dict[int, models.Producto] = {}
    for comp in equipo.componentes:
        p = comp.producto
        if p.fabricante and p.pn_fabricante and p.id not in vistos:
            vistos[p.id] = p
    prods = list(vistos.values())
    prods.sort(key=lambda p: (p.ciclo_vida_verificado_en is not None,
                              p.ciclo_vida_verificado_en or date.min))
    return prods


def refrescar_banco(db: Session, equipo_id: int, hoy: date, *,
                    limite: int = 10, consultar) -> dict:
    """Re-verifica hasta `limite` productos del banco vía `consultar` (inyectable),
    registra los hallazgos y devuelve el report actualizado. Best-effort: un
    `consultar` que devuelve None o falla no rompe el refresco."""
    for p in productos_de_equipo(db, equipo_id)[:limite]:
        try:
            v = consultar(p, _url_fabricante(db, p))
        except Exception:
            v = None
        if not v:
            continue
        obsolescencia_service.registrar_hallazgo(
            db, p.id, v["estado"], hoy=hoy, fecha_evento=v.get("fecha_evento"),
            url=v.get("url_fuente"), resumen=v.get("resumen"))
    return informe_banco(db, equipo_id, hoy)
```

- [ ] **Step 4: Ejecutar para verlos pasar**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app/obsolescencia_banco.py tests/test_obsolescencia_banco.py
git commit -m "feat(obsolescencia): productos_de_equipo + refrescar_banco acotado"
```

---

## Task 3: Schemas de salida

**Files:**
- Modify: `backend/app/schemas.py` (añadir al final del bloque de obsolescencia, junto a `ObsolescenciaResumenOut`)

- [ ] **Step 1: Añadir los schemas**

```python
# --- Report de obsolescencia por banco ---
class ObsolescenciaBancoCabecera(BaseModel):
    equipo_id: int
    numero_serie: str
    producto: str
    descripcion: Optional[str] = None
    cliente: Optional[str] = None
    estado: str
    contrato_nivel: Optional[str] = None


class ObsolescenciaBancoComponenteOut(BaseModel):
    componente_id: int
    posicion: Optional[str] = None
    part_number: str
    fabricante: Optional[str] = None
    pn_fabricante: Optional[str] = None
    descripcion: str
    numero_serie: str
    categoria_componente: Optional[str] = None
    estado_ciclo_vida: Optional[str] = None
    severidad: int
    ciclo_vida_fecha: Optional[date] = None
    ciclo_vida_url: Optional[str] = None
    ciclo_vida_resumen: Optional[str] = None
    ciclo_vida_verificado_en: Optional[date] = None


class ObsolescenciaBancoResumen(BaseModel):
    conteos: dict[str, int]
    en_riesgo: int
    sin_verificar: int
    total: int
    verificado_mas_antiguo: Optional[date] = None


class ObsolescenciaBancoOut(BaseModel):
    banco: ObsolescenciaBancoCabecera
    componentes: list[ObsolescenciaBancoComponenteOut]
    resumen: ObsolescenciaBancoResumen
```

- [ ] **Step 2: Verificar que importa**

Run: `.venv/Scripts/python -c "from app.schemas import ObsolescenciaBancoOut; print('ok')"`
Expected: imprime `ok`. (`date`, `Optional`, `BaseModel` ya están importados en schemas.py.)

- [ ] **Step 3: Commit**

```bash
git add app/schemas.py
git commit -m "feat(obsolescencia): schemas del report de banco"
```

---

## Task 4: Exportadores xlsx + pdf

**Files:**
- Create: `backend/app/obsolescencia_export.py`
- Test: `backend/tests/test_obsolescencia_export.py`

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/tests/test_obsolescencia_export.py
import io
import zipfile

from datetime import date

from app import obsolescencia_export


def _informe():
    return {
        "banco": {"equipo_id": 1, "numero_serie": "SN-XLS", "producto": "IUTB-01",
                  "descripcion": "iUTB", "cliente": "Indra", "estado": "operativo",
                  "contrato_nivel": None},
        "componentes": [
            {"componente_id": 1, "posicion": "3", "part_number": "P-OBS",
             "fabricante": "Acme", "pn_fabricante": "ACM-9", "descripcion": "Relé",
             "numero_serie": "C1", "categoria_componente": "instrumento",
             "estado_ciclo_vida": "obsoleto", "severidad": 4,
             "ciclo_vida_fecha": date(2026, 1, 1), "ciclo_vida_url": "http://acme/eol",
             "ciclo_vida_resumen": "EOL", "ciclo_vida_verificado_en": date(2026, 1, 1)},
            {"componente_id": 2, "posicion": "1", "part_number": "P-ACT",
             "fabricante": "Beta", "pn_fabricante": "BET-1", "descripcion": "Cable",
             "numero_serie": "C2", "categoria_componente": "wiring",
             "estado_ciclo_vida": "activo", "severidad": 0,
             "ciclo_vida_fecha": None, "ciclo_vida_url": None,
             "ciclo_vida_resumen": None, "ciclo_vida_verificado_en": date(2026, 6, 1)},
        ],
        "resumen": {"conteos": {"activo": 1, "nrnd": 0, "eol_anunciado": 0,
                                "ultima_compra": 0, "obsoleto": 1},
                    "en_riesgo": 1, "sin_verificar": 0, "total": 2,
                    "verificado_mas_antiguo": date(2026, 1, 1)},
    }


def test_a_xlsx_es_zip_y_contiene_la_serie():
    data = obsolescencia_export.a_xlsx(_informe())
    assert data[:4] == b"PK\x03\x04"            # cabecera ZIP (xlsx)
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = z.read("xl/sharedStrings.xml").decode("utf-8")
    assert "SN-XLS" in shared
    assert "P-OBS" in shared


def test_a_pdf_tiene_cabecera_pdf():
    data = obsolescencia_export.a_pdf(_informe())
    assert data[:5] == b"%PDF-"
    assert len(data) > 1000
```

- [ ] **Step 2: Ejecutar para verlos fallar**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_export.py -q`
Expected: FAIL (ImportError de `app.obsolescencia_export`).

- [ ] **Step 3: Implementar los exportadores**

```python
# backend/app/obsolescencia_export.py
"""Exporta el report de obsolescencia de un banco (dict de obsolescencia_banco)
a Excel (.xlsx) y PDF. No toca BD."""
from __future__ import annotations

import io

# (clave en el dict de informe_banco, encabezado visible)
_COLUMNAS = [
    ("posicion", "Posición"),
    ("part_number", "P/N 6TL"),
    ("fabricante", "Fabricante"),
    ("pn_fabricante", "P/N fabricante"),
    ("descripcion", "Descripción"),
    ("numero_serie", "Nº serie"),
    ("estado_ciclo_vida", "Estado"),
    ("ciclo_vida_fecha", "Fecha evento"),
    ("ciclo_vida_verificado_en", "Verificado"),
    ("ciclo_vida_url", "Fuente"),
    ("ciclo_vida_resumen", "Resumen"),
]
_CAB = dict(_COLUMNAS)


def _txt(v) -> str:
    return "" if v is None else str(v)


def _subtitulo(b: dict, r: dict) -> str:
    return (f"Cliente: {_txt(b['cliente'])} · Estado: {b['estado']} · "
            f"En riesgo: {r['en_riesgo']}/{r['total']} · Sin verificar: {r['sin_verificar']}")


def a_xlsx(informe: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    b, r = informe["banco"], informe["resumen"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Componentes"
    ws.append([f"Obsolescencia banco {b['numero_serie']} ({b['producto']})"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([_subtitulo(b, r)])
    ws.append([])
    ws.append([cab for _, cab in _COLUMNAS])
    for celda in ws[ws.max_row]:
        celda.font = Font(bold=True)

    riesgo_fill = PatternFill("solid", fgColor="FFC7CE")
    col_estado = [c for c, _ in _COLUMNAS].index("estado_ciclo_vida") + 1
    for fila in informe["componentes"]:
        ws.append([_txt(fila[clave]) for clave, _ in _COLUMNAS])
        if fila["severidad"] > 0:
            ws.cell(row=ws.max_row, column=col_estado).fill = riesgo_fill

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def a_pdf(informe: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                     Table, TableStyle)

    b, r = informe["banco"], informe["resumen"]
    estilos = getSampleStyleSheet()
    elementos = [
        Paragraph(f"Obsolescencia banco {b['numero_serie']} ({b['producto']})", estilos["Title"]),
        Paragraph(_subtitulo(b, r), estilos["Normal"]),
        Spacer(1, 6 * mm),
    ]

    columnas = ["posicion", "part_number", "fabricante", "pn_fabricante",
                "numero_serie", "estado_ciclo_vida", "ciclo_vida_fecha",
                "ciclo_vida_verificado_en"]
    datos = [[_CAB[c] for c in columnas]]
    estilo = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9e007e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])
    for i, fila in enumerate(informe["componentes"], start=1):
        datos.append([_txt(fila[c]) for c in columnas])
        if fila["severidad"] > 0:
            estilo.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FFC7CE"))

    tabla = Table(datos, repeatRows=1)
    tabla.setStyle(estilo)
    elementos.append(tabla)

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=10 * mm,
                      rightMargin=10 * mm, topMargin=10 * mm, bottomMargin=10 * mm).build(elementos)
    return buf.getvalue()
```

- [ ] **Step 4: Ejecutar para verlos pasar**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_export.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/obsolescencia_export.py tests/test_obsolescencia_export.py
git commit -m "feat(obsolescencia): exportar report de banco a xlsx y pdf"
```

---

## Task 5: Dependency `get_consultar_fabricante` + router + registro en main

**Files:**
- Modify: `backend/app/deps.py` (añadir dependency)
- Create: `backend/app/routers/obsolescencia_banco.py`
- Modify: `backend/app/main.py` (registrar el router, junto al resto)
- Test: `backend/tests/test_obsolescencia_banco_router.py`

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/tests/test_obsolescencia_banco_router.py
from datetime import date

from app import models
from app.deps import get_consultar_fabricante
from app.main import app


def _seed(db):
    pe = models.Producto(part_number="IUTB-01", tipo="equipo", descripcion="iUTB")
    cli = models.Cliente(nombre="Indra")
    db.add_all([pe, cli]); db.flush()
    eq = models.Equipo(numero_serie="SN-RT", producto_id=pe.id, cliente_id=cli.id,
                       estado="operativo")
    db.add(eq); db.flush()
    pc = models.Producto(part_number="P-ACT", tipo="componente", descripcion="Cable",
                         fabricante="Beta", pn_fabricante="BET-1", estado_ciclo_vida="activo")
    db.add(pc); db.flush()
    db.add(models.Componente(numero_serie="C1", producto_id=pc.id, equipo_id=eq.id, posicion="1"))
    db.commit()
    return eq.id


def test_get_report_200(client, db_session):
    eq_id = _seed(db_session)
    resp = client.get(f"/api/equipos/{eq_id}/obsolescencia")
    assert resp.status_code == 200
    body = resp.json()
    assert body["banco"]["numero_serie"] == "SN-RT"
    assert body["resumen"]["total"] == 1
    assert body["componentes"][0]["part_number"] == "P-ACT"


def test_get_report_404(client):
    assert client.get("/api/equipos/9999/obsolescencia").status_code == 404


def test_export_xlsx_headers(client, db_session):
    eq_id = _seed(db_session)
    resp = client.get(f"/api/equipos/{eq_id}/obsolescencia/export?formato=xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == \
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in resp.headers["content-disposition"]
    assert "SN-RT" in resp.headers["content-disposition"]
    assert resp.content[:4] == b"PK\x03\x04"


def test_export_pdf_headers(client, db_session):
    eq_id = _seed(db_session)
    resp = client.get(f"/api/equipos/{eq_id}/obsolescencia/export?formato=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


def test_export_formato_invalido_422(client, db_session):
    eq_id = _seed(db_session)
    assert client.get(f"/api/equipos/{eq_id}/obsolescencia/export?formato=csv").status_code == 422


def test_report_requiere_auth(client_sin_auth, db_session):
    eq_id = _seed(db_session)
    assert client_sin_auth.get(f"/api/equipos/{eq_id}/obsolescencia").status_code == 401


def test_refrescar_usa_consultar_inyectado(client, db_session):
    eq_id = _seed(db_session)

    def fake_consultar(producto, url):
        return {"estado": "obsoleto", "fecha_evento": None,
                "url_fuente": "http://beta/eol", "resumen": "EOL"}

    app.dependency_overrides[get_consultar_fabricante] = lambda: fake_consultar
    try:
        resp = client.post(f"/api/equipos/{eq_id}/obsolescencia/refrescar?limite=5")
    finally:
        app.dependency_overrides.pop(get_consultar_fabricante, None)

    assert resp.status_code == 200
    assert resp.json()["componentes"][0]["estado_ciclo_vida"] == "obsoleto"
    p = db_session.query(models.Producto).filter_by(part_number="P-ACT").one()
    db_session.refresh(p)
    assert p.estado_ciclo_vida == "obsoleto"
```

- [ ] **Step 2: Ejecutar para verlos fallar**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco_router.py -q`
Expected: FAIL (ImportError de `get_consultar_fabricante` / 404 en todas las rutas porque el router no existe).

- [ ] **Step 3a: Añadir la dependency en `app/deps.py`**

Añadir al final de `app/deps.py`:

```python
def get_consultar_fabricante():
    """Dependencia: función que consulta el estado de ciclo de vida de un producto
    (Claude Code headless). Inyectable — en tests se sobreescribe por un doble, así
    el import real de run_obsolescencia (con sus efectos de arranque) nunca ocurre."""
    from run_obsolescencia import consultar_fabricante
    return consultar_fabricante
```

- [ ] **Step 3b: Crear el router `app/routers/obsolescencia_banco.py`**

```python
# backend/app/routers/obsolescencia_banco.py
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models, obsolescencia_banco, obsolescencia_export
from app.db import get_db
from app.deps import get_consultar_fabricante
from app.schemas import ObsolescenciaBancoOut

router = APIRouter(prefix="/api/equipos", tags=["obsolescencia"])

_MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def _equipo_o_404(db: Session, equipo_id: int) -> models.Equipo:
    eq = db.get(models.Equipo, equipo_id)
    if eq is None:
        raise HTTPException(status_code=404, detail="equipo no encontrado")
    return eq


@router.get("/{equipo_id}/obsolescencia", response_model=ObsolescenciaBancoOut)
def report(equipo_id: int, db: Session = Depends(get_db)):
    _equipo_o_404(db, equipo_id)
    return obsolescencia_banco.informe_banco(db, equipo_id, date.today())


@router.get("/{equipo_id}/obsolescencia/export")
def exportar(equipo_id: int, formato: str = "xlsx", db: Session = Depends(get_db)):
    _equipo_o_404(db, equipo_id)
    if formato not in _MEDIA:
        raise HTTPException(status_code=422, detail="formato debe ser 'xlsx' o 'pdf'")
    informe = obsolescencia_banco.informe_banco(db, equipo_id, date.today())
    datos = (obsolescencia_export.a_xlsx(informe) if formato == "xlsx"
             else obsolescencia_export.a_pdf(informe))
    nombre = f"obsolescencia_{informe['banco']['numero_serie']}_{date.today().isoformat()}.{formato}"
    return Response(content=datos, media_type=_MEDIA[formato],
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/{equipo_id}/obsolescencia/refrescar", response_model=ObsolescenciaBancoOut)
def refrescar(equipo_id: int, limite: int = 10, db: Session = Depends(get_db),
              consultar=Depends(get_consultar_fabricante)):
    _equipo_o_404(db, equipo_id)
    return obsolescencia_banco.refrescar_banco(
        db, equipo_id, date.today(), limite=limite, consultar=consultar)
```

- [ ] **Step 3c: Registrar el router en `app/main.py`**

Tras el bloque del router `obsolescencia` (líneas 105-106, `app.include_router(obsolescencia.router, ...)`), añadir:

```python
from app.routers import obsolescencia_banco
app.include_router(obsolescencia_banco.router, dependencies=[Depends(get_current_user)])
```

- [ ] **Step 4: Ejecutar para verlos pasar**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco_router.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add app/deps.py app/routers/obsolescencia_banco.py app/main.py tests/test_obsolescencia_banco_router.py
git commit -m "feat(obsolescencia): endpoints report/export/refrescar por banco"
```

---

## Task 6: Suite completa + verificación end-to-end

- [ ] **Step 1: Toda la suite en verde**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS (los 427 previos + los nuevos de Tasks 1/2/4/5). Si algún test global toca la `postventa.db` real, parar uvicorn antes.

- [ ] **Step 2: Smoke en vivo (opcional, requiere arrancar el backend)**

Arrancar: `.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8020`
Con un token válido (login `admin`), contra el banco real (id 1):
- `GET /api/equipos/1/obsolescencia` → JSON con `banco`/`componentes`/`resumen`.
- `GET /api/equipos/1/obsolescencia/export?formato=xlsx` → descarga .xlsx.
- `GET /api/equipos/1/obsolescencia/export?formato=pdf` → descarga .pdf.
(El refresco real llama a Claude headless y tarda; probarlo con `?limite=1`.)

- [ ] **Step 3: Commit final (si hubo ajustes del smoke)**

```bash
git add -A
git commit -m "test: suite verde report de obsolescencia por banco"
```

---

## Notas de integración

- **Desviación menor respecto al spec:** el spec menciona "router `app/routers/obsolescencia.py`", pero ese router usa prefix `/api/obsolescencia`. Para `/api/equipos/{id}/obsolescencia` se crea un router nuevo `obsolescencia_banco.py` con prefix `/api/equipos` (más cohesivo y sin tocar el router global). Mismo efecto: endpoints protegidos.
- **Frontend Lovable:** fuera de alcance de este plan (prompt aparte tras el backend, como el resto de features).
- **Rama:** `feat/report-obsolescencia-banco`. Al terminar, mergear a `master` (subagent-driven hace el merge final tras la review holística).
```
