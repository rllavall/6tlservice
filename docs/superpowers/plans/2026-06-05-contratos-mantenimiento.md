# Contratos de mantenimiento, P/N de fabricante y preventivo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir P/N de fabricante a productos, un dominio de contratos de mantenimiento (niveles Bronze/Silver/Gold) con cobertura derivada por equipo, y registro de acciones de preventivo que pueden generar incidencias correctivas.

**Architecture:** Backend FastAPI + SQLAlchemy ORM sobre SQLite. Lógica de estado derivada en módulos puros duck-typed (como `app/garantia.py`). Columnas nuevas vía `app/migrations.py` (idempotente); tablas nuevas vía `create_all`. Routers protegidos con `dependencies=[Depends(get_current_user)]` al incluirlos. Auditoría automática por el listener ORM existente.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2.0 (Mapped), Pydantic v2, pytest + TestClient.

**Convenciones del repo (leer antes de empezar):**
- Ejecuta pytest con el venv: `./.venv/Scripts/python.exe -m pytest` desde `backend/`. **Para el server uvicorn antes de correr la suite** (siembra/abre `postventa.db`).
- Fixtures en `tests/conftest.py`: `db_session` (BD en memoria), `client` (auth simulada, usuario id 1), `client_sin_auth` (auth real, para tests de 401).
- Schemas: base `_ORM` (`from_attributes=True`), `Literal`, `Field`, `model_validator` ya importados en `app/schemas.py`.
- Todos los comandos `git`/`pytest` se ejecutan desde `backend/` salvo que se indique.

---

## Task 1: `Producto.pn_fabricante`

**Files:**
- Modify: `backend/app/models.py` (clase `Producto`, ~línea 50)
- Modify: `backend/app/migrations.py` (dict `_COLUMNAS_NUEVAS`)
- Modify: `backend/app/schemas.py` (`ProductoCreate` ~68, `ProductoOut` ~79)
- Test: `backend/tests/test_pn_fabricante.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pn_fabricante.py
from app import models


def test_producto_pn_fabricante_se_guarda_y_expone(db_session):
    p = models.Producto(
        part_number="6TL-100", tipo="componente", descripcion="Tarjeta RF",
        pn_fabricante="NI-PXIe-5840",
    )
    db_session.add(p); db_session.flush()
    assert p.pn_fabricante == "NI-PXIe-5840"


def test_producto_pn_fabricante_opcional(db_session):
    p = models.Producto(part_number="6TL-101", tipo="componente", descripcion="Cable")
    db_session.add(p); db_session.flush()
    assert p.pn_fabricante is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pn_fabricante.py -v`
Expected: FAIL (`'pn_fabricante' is an invalid keyword argument for Producto`)

- [ ] **Step 3: Add the column to the model**

En `backend/app/models.py`, clase `Producto`, tras `categoria`:

```python
    categoria: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pn_fabricante: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pn_fabricante.py -v`
Expected: PASS

- [ ] **Step 5: Add migration + expose in schemas**

En `backend/app/migrations.py`, en la entrada `"productos"` del dict `_COLUMNAS_NUEVAS`:

```python
    "productos": {"meses_garantia_default": "INTEGER DEFAULT 24", "categoria": "TEXT", "pn_fabricante": "TEXT"},
```

En `backend/app/schemas.py`, añade `pn_fabricante: Optional[str] = None` a `ProductoCreate` (tras `categoria`) y a `ProductoOut` (tras `categoria`).

- [ ] **Step 6: Test the schema round-trips via API**

```python
# añade a backend/tests/test_pn_fabricante.py
def test_alta_producto_con_pn_fabricante_api(client):
    r = client.post("/api/productos", json={
        "part_number": "6TL-200", "tipo": "componente", "descripcion": "Fuente",
        "pn_fabricante": "KEYSIGHT-N6700",
    })
    assert r.status_code == 201, r.text
    assert r.json()["pn_fabricante"] == "KEYSIGHT-N6700"
```

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pn_fabricante.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/migrations.py app/schemas.py tests/test_pn_fabricante.py
git commit -m "feat: P/N de fabricante en Producto (modelo + migración + schemas)"
```

---

## Task 2: Lógica pura de contratos (`app/contratos.py`)

**Files:**
- Create: `backend/app/contratos.py`
- Test: `backend/tests/test_contratos_logica.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_contratos_logica.py
from datetime import date
from types import SimpleNamespace

from app import contratos


def _c(inicio, fin, cancelado=False, nivel="bronze"):
    return SimpleNamespace(fecha_inicio=inicio, fecha_fin=fin, cancelado=cancelado, nivel=nivel)


def test_estado_vigente():
    c = _c(date(2026, 1, 1), date(2026, 12, 31))
    assert contratos.estado_contrato(c, date(2026, 6, 5)) == "vigente"
    assert contratos.esta_vigente(c, date(2026, 6, 5)) is True


def test_estado_pendiente():
    c = _c(date(2026, 7, 1), date(2026, 12, 31))
    assert contratos.estado_contrato(c, date(2026, 6, 5)) == "pendiente"


def test_estado_vencido():
    c = _c(date(2025, 1, 1), date(2025, 12, 31))
    assert contratos.estado_contrato(c, date(2026, 6, 5)) == "vencido"


def test_estado_cancelado_tiene_prioridad():
    c = _c(date(2026, 1, 1), date(2026, 12, 31), cancelado=True)
    assert contratos.estado_contrato(c, date(2026, 6, 5)) == "cancelado"
    assert contratos.esta_vigente(c, date(2026, 6, 5)) is False


def test_nivel_detalle():
    assert contratos.NIVELES["bronze"]["preventivo"] == "anual"
    assert contratos.NIVELES["gold"]["soporte"] == "24/7"
    assert contratos.NIVELES["silver"]["preventivo_meses"] == 6


def test_sugerir_proxima_fecha_por_nivel():
    assert contratos.sugerir_proxima_fecha(date(2026, 6, 5), "bronze") == date(2027, 6, 5)
    assert contratos.sugerir_proxima_fecha(date(2026, 6, 5), "gold") == date(2026, 12, 5)
    assert contratos.sugerir_proxima_fecha(date(2026, 6, 5), None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_logica.py -v`
Expected: FAIL (`No module named 'app.contratos'`)

- [ ] **Step 3: Write the module**

```python
# backend/app/contratos.py
"""Lógica pura de contratos de mantenimiento. No importa models: opera por
duck-typing (`contrato.fecha_inicio/fecha_fin/cancelado/nivel`) y con `hoy` inyectable."""
from __future__ import annotations

from datetime import date
from typing import Optional

from app.garantia import _add_months

# Atributos derivados de cada nivel de servicio (propuesta iUTB INDRA).
NIVELES: dict[str, dict] = {
    "bronze": {"preventivo": "anual", "soporte": "horario_laborable", "respuesta": "estandar", "preventivo_meses": 12},
    "silver": {"preventivo": "semestral", "soporte": "horario_laborable", "respuesta": "mejorada", "preventivo_meses": 6},
    "gold": {"preventivo": "semestral", "soporte": "24/7", "respuesta": "prioritaria", "preventivo_meses": 6},
}


def estado_contrato(contrato, hoy: date) -> str:
    if getattr(contrato, "cancelado", False):
        return "cancelado"
    if hoy < contrato.fecha_inicio:
        return "pendiente"
    if hoy <= contrato.fecha_fin:
        return "vigente"
    return "vencido"


def esta_vigente(contrato, hoy: date) -> bool:
    return estado_contrato(contrato, hoy) == "vigente"


def nivel_detalle(nivel: Optional[str]) -> Optional[dict]:
    return NIVELES.get(nivel) if nivel else None


def sugerir_proxima_fecha(fecha: date, nivel: Optional[str]) -> Optional[date]:
    detalle = NIVELES.get(nivel) if nivel else None
    if detalle is None:
        return None
    return _add_months(fecha, detalle["preventivo_meses"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_logica.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app/contratos.py tests/test_contratos_logica.py
git commit -m "feat: lógica pura de contratos (estado derivado, niveles, próxima fecha)"
```

---

## Task 3: Modelos `ContratoMantenimiento` + `Equipo.contrato_id`

**Files:**
- Modify: `backend/app/models.py` (nueva clase + campos/propiedades en `Equipo`)
- Modify: `backend/app/migrations.py`
- Test: `backend/tests/test_contratos_modelo.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_contratos_modelo.py
from datetime import date

from app import models


def _producto(db):
    p = models.Producto(part_number="6TL-EQ", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    return p


def test_contrato_estado_y_nivel_detalle(db_session):
    c = models.ContratoMantenimiento(
        codigo="CTR-0001", cliente_id=None, nivel="gold",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db_session.add(c); db_session.flush()
    assert c.estado == "vigente"
    assert c.vigente is True
    assert c.nivel_detalle["soporte"] == "24/7"


def test_equipo_bajo_contrato_derivado(db_session):
    p = _producto(db_session)
    vig = models.ContratoMantenimiento(
        codigo="CTR-0002", nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    venc = models.ContratoMantenimiento(
        codigo="CTR-0003", nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2021, 1, 1),
    )
    db_session.add_all([vig, venc]); db_session.flush()

    e_sin = models.Equipo(numero_serie="SN1", producto_id=p.id)
    e_vig = models.Equipo(numero_serie="SN2", producto_id=p.id, contrato_id=vig.id)
    e_venc = models.Equipo(numero_serie="SN3", producto_id=p.id, contrato_id=venc.id)
    db_session.add_all([e_sin, e_vig, e_venc]); db_session.flush()

    assert e_sin.bajo_contrato is False
    assert e_vig.bajo_contrato is True
    assert e_venc.bajo_contrato is False   # contrato vencido no cuenta
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_modelo.py -v`
Expected: FAIL (`module 'app.models' has no attribute 'ContratoMantenimiento'`)

- [ ] **Step 3: Add the model + Equipo fields**

En `backend/app/models.py`, dentro de la clase `Equipo`, añade el campo FK (tras `numero_serie_cliente`):

```python
    numero_serie_cliente: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    contrato_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contratos.id"), nullable=True)
```

Y, en `Equipo`, junto a las demás `@property` (tras `estado_garantia`), añade:

```python
    contrato: Mapped[Optional["ContratoMantenimiento"]] = relationship(back_populates="equipos")

    @property
    def bajo_contrato(self) -> bool:
        from datetime import date as _date
        from app import contratos
        return self.contrato is not None and contratos.esta_vigente(self.contrato, _date.today())
```

Añade la clase nueva (al final de la sección de entidades, p.ej. tras `SolicitudSoporte`):

```python
class ContratoMantenimiento(Base):
    __tablename__ = "contratos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String, unique=True)
    cliente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clientes.id"), nullable=True)
    nivel: Mapped[str] = mapped_column(String)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    cancelado: Mapped[bool] = mapped_column(Boolean, default=False)
    notas: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    equipos: Mapped[list["Equipo"]] = relationship(back_populates="contrato")

    @property
    def estado(self) -> str:
        from datetime import date as _date
        from app import contratos
        return contratos.estado_contrato(self, _date.today())

    @property
    def vigente(self) -> bool:
        return self.estado == "vigente"

    @property
    def nivel_detalle(self):
        from app import contratos
        return contratos.nivel_detalle(self.nivel)
```

Asegúrate de que `Boolean` está importado en la cabecera de `models.py` (junto a `Integer, String, Date, ForeignKey`). Si no, añádelo al `from sqlalchemy import ...`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_modelo.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Add migration for the new Equipo column**

En `backend/app/migrations.py`, en `_COLUMNAS_NUEVAS`, amplía la entrada `"equipos"`:

```python
    "equipos": {"meses_garantia": "INTEGER", "version": "TEXT", "numero_serie_cliente": "TEXT", "contrato_id": "INTEGER"},
```

- [ ] **Step 6: Run full suite to confirm no regressions**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (todo verde)

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/migrations.py tests/test_contratos_modelo.py
git commit -m "feat: modelo ContratoMantenimiento + Equipo.contrato_id + bajo_contrato derivado"
```

---

## Task 4: `contratos_service` (código + asignación con validación)

**Files:**
- Create: `backend/app/contratos_service.py`
- Test: `backend/tests/test_contratos_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_contratos_service.py
from datetime import date

import pytest

from app import contratos_service as svc
from app import models


def _cliente(db, nombre="ACME"):
    c = models.Cliente(nombre=nombre)
    db.add(c); db.flush()
    return c


def _producto(db):
    p = models.Producto(part_number="6TL-EQ", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    return p


def _contrato(db, cliente_id):
    c = models.ContratoMantenimiento(
        codigo=svc.generar_codigo(db), cliente_id=cliente_id, nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db.add(c); db.flush()
    return c


def test_generar_codigo_secuencial(db_session):
    assert svc.generar_codigo(db_session) == "CTR-0001"
    db_session.add(models.ContratoMantenimiento(
        codigo="CTR-0001", nivel="bronze", fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    ))
    db_session.flush()
    assert svc.generar_codigo(db_session) == "CTR-0002"


def test_vincular_equipo_ok(db_session):
    cli = _cliente(db_session)
    con = _contrato(db_session, cli.id)
    p = _producto(db_session)
    eq = models.Equipo(numero_serie="SN1", producto_id=p.id, cliente_id=cli.id)
    db_session.add(eq); db_session.flush()
    svc.vincular_equipo(db_session, con, eq)
    assert eq.contrato_id == con.id


def test_vincular_equipo_cliente_distinto_falla(db_session):
    cli_a = _cliente(db_session, "A")
    cli_b = _cliente(db_session, "B")
    con = _contrato(db_session, cli_a.id)
    p = _producto(db_session)
    eq = models.Equipo(numero_serie="SN2", producto_id=p.id, cliente_id=cli_b.id)
    db_session.add(eq); db_session.flush()
    with pytest.raises(svc.ContratoError):
        svc.vincular_equipo(db_session, con, eq)


def test_vincular_equipo_sin_cliente_permitido(db_session):
    cli = _cliente(db_session)
    con = _contrato(db_session, cli.id)
    p = _producto(db_session)
    eq = models.Equipo(numero_serie="SN3", producto_id=p.id, cliente_id=None)
    db_session.add(eq); db_session.flush()
    svc.vincular_equipo(db_session, con, eq)
    assert eq.contrato_id == con.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_service.py -v`
Expected: FAIL (`No module named 'app.contratos_service'`)

- [ ] **Step 3: Write the service**

```python
# backend/app/contratos_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app import models


class ContratoError(Exception):
    """Error de negocio en contratos (→ HTTP 409)."""


def generar_codigo(db: Session) -> str:
    """Siguiente código `CTR-NNNN`."""
    nums = []
    for (codigo,) in db.query(models.ContratoMantenimiento.codigo).all():
        if codigo and codigo.startswith("CTR-"):
            try:
                nums.append(int(codigo.split("-", 1)[1]))
            except ValueError:
                pass
    n = (max(nums) + 1) if nums else 1
    return f"CTR-{n:04d}"


def vincular_equipo(db: Session, contrato: models.ContratoMantenimiento, equipo: models.Equipo) -> None:
    if equipo.cliente_id is not None and contrato.cliente_id is not None \
            and equipo.cliente_id != contrato.cliente_id:
        raise ContratoError("El equipo pertenece a otro cliente que el titular del contrato")
    equipo.contrato_id = contrato.id
    db.flush()


def desvincular_equipo(db: Session, equipo: models.Equipo) -> None:
    equipo.contrato_id = None
    db.flush()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/contratos_service.py tests/test_contratos_service.py
git commit -m "feat: contratos_service (generar_codigo + vincular/desvincular con validación de cliente)"
```

---

## Task 5: Schemas de contrato + ampliación de `EquipoOut`

**Files:**
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_contratos_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_contratos_schemas.py
from datetime import date

from app import models
from app.schemas import ContratoOut, EquipoOut


def test_contrato_out_incluye_estado_y_detalle(db_session):
    c = models.ContratoMantenimiento(
        codigo="CTR-0001", nivel="gold",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db_session.add(c); db_session.flush()
    out = ContratoOut.model_validate(c)
    assert out.estado == "vigente"
    assert out.vigente is True
    assert out.nivel_detalle["soporte"] == "24/7"


def test_equipo_out_expone_bajo_contrato_y_resumen(db_session):
    p = models.Producto(part_number="6TL-EQ", tipo="equipo", descripcion="Banco")
    con = models.ContratoMantenimiento(
        codigo="CTR-0002", nivel="bronze",
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db_session.add_all([p, con]); db_session.flush()
    eq = models.Equipo(numero_serie="SN1", producto_id=p.id, contrato_id=con.id)
    db_session.add(eq); db_session.flush()
    out = EquipoOut.model_validate(eq)
    assert out.bajo_contrato is True
    assert out.contrato.codigo == "CTR-0002"
    assert out.contrato.estado == "vigente"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_schemas.py -v`
Expected: FAIL (`cannot import name 'ContratoOut'`)

- [ ] **Step 3: Add the schemas**

En `backend/app/schemas.py`, añade una sección nueva (p.ej. tras la sección de Solicitud o al final, antes de `# --- Auth ---`):

```python
# --- Contratos de mantenimiento ---
_NIVEL = Literal["bronze", "silver", "gold"]
_ESTADO_CONTRATO = Literal["pendiente", "vigente", "vencido", "cancelado"]


class ContratoCreate(BaseModel):
    cliente_id: Optional[int] = None
    nivel: _NIVEL
    fecha_inicio: date
    fecha_fin: date
    notas: Optional[str] = None


class ContratoUpdate(BaseModel):
    cliente_id: Optional[int] = None
    nivel: Optional[_NIVEL] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    cancelado: Optional[bool] = None
    notas: Optional[str] = None


class ContratoResumen(_ORM):
    id: int
    codigo: str
    nivel: str
    estado: _ESTADO_CONTRATO
    vigente: bool


class ContratoOut(_ORM):
    id: int
    codigo: str
    cliente_id: Optional[int] = None
    nivel: str
    fecha_inicio: date
    fecha_fin: date
    cancelado: bool
    notas: Optional[str] = None
    estado: _ESTADO_CONTRATO
    vigente: bool
    nivel_detalle: Optional[dict] = None


class ContratoDetalle(_ORM):
    contrato: ContratoOut
    cliente: Optional[ClienteOut] = None
    equipos: list[EquipoOut] = []


class AsignarEquipoPayload(BaseModel):
    equipo_id: int
```

En `EquipoOut` (clase ~116), añade dos campos tras `categoria`:

```python
    categoria: Optional[str] = None
    bajo_contrato: bool = False
    contrato: Optional[ContratoResumen] = None
```

> Nota: `EquipoOut` se define ANTES que `ContratoResumen` en el archivo. Pydantic v2 resuelve el forward ref si declaras el tipo como `Optional["ContratoResumen"]` o añades `EquipoOut.model_rebuild()` tras definir `ContratoResumen`. Usa el string forward-ref y, al final del bloque de contratos, añade:

```python
EquipoOut.model_rebuild()
```

Es decir, en `EquipoOut`: `contrato: Optional["ContratoResumen"] = None`, y tras la definición de `ContratoResumen`/bloque, `EquipoOut.model_rebuild()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_schemas.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full suite (EquipoOut cambió: verifica que no rompe nada)**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (todo verde)

- [ ] **Step 6: Commit**

```bash
git add app/schemas.py tests/test_contratos_schemas.py
git commit -m "feat: schemas de contrato + bajo_contrato/contrato en EquipoOut"
```

---

## Task 6: Router de contratos (CRUD + asignar/desasignar)

**Files:**
- Create: `backend/app/routers/contratos.py`
- Modify: `backend/app/main.py` (import + include_router)
- Test: `backend/tests/test_contratos_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_contratos_api.py
def _crear_contrato(client, cliente_id=None):
    return client.post("/api/contratos", json={
        "cliente_id": cliente_id, "nivel": "silver",
        "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01",
    })


def test_crud_contrato(client):
    r = _crear_contrato(client)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["codigo"].startswith("CTR-")
    assert r.json()["estado"] == "vigente"

    r = client.get(f"/api/contratos/{cid}")
    assert r.status_code == 200
    assert r.json()["contrato"]["nivel"] == "silver"
    assert r.json()["equipos"] == []

    r = client.put(f"/api/contratos/{cid}", json={"cancelado": True})
    assert r.status_code == 200
    assert r.json()["estado"] == "cancelado"

    r = client.get("/api/contratos?estado=cancelado")
    assert any(c["id"] == cid for c in r.json())


def test_asignar_y_desasignar_equipo(client):
    cli = client.post("/api/clientes", json={"nombre": "ACME"}).json()
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQ", "tipo": "equipo", "descripcion": "Banco"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN1", "producto_id": prod["id"], "cliente_id": cli["id"]}).json()
    con = _crear_contrato(client, cliente_id=cli["id"]).json()

    r = client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    assert r.status_code == 200, r.text
    detalle = client.get(f"/api/contratos/{con['id']}").json()
    assert [e["id"] for e in detalle["equipos"]] == [eq["id"]]

    # equipo aparece bajo_contrato
    eq_out = client.get(f"/api/equipos/{eq['id']}").json()["equipo"]
    assert eq_out["bajo_contrato"] is True

    r = client.delete(f"/api/contratos/{con['id']}/equipos/{eq['id']}")
    assert r.status_code == 200
    detalle = client.get(f"/api/contratos/{con['id']}").json()
    assert detalle["equipos"] == []


def test_asignar_equipo_cliente_distinto_409(client):
    cli_a = client.post("/api/clientes", json={"nombre": "A"}).json()
    cli_b = client.post("/api/clientes", json={"nombre": "B"}).json()
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQ2", "tipo": "equipo", "descripcion": "Banco"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN9", "producto_id": prod["id"], "cliente_id": cli_b["id"]}).json()
    con = _crear_contrato(client, cliente_id=cli_a["id"]).json()
    r = client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    assert r.status_code == 409


def test_delete_contrato_con_equipos_409(client):
    cli = client.post("/api/clientes", json={"nombre": "ACME"}).json()
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQ3", "tipo": "equipo", "descripcion": "Banco"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "SN5", "producto_id": prod["id"], "cliente_id": cli["id"]}).json()
    con = _crear_contrato(client, cliente_id=cli["id"]).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    r = client.delete(f"/api/contratos/{con['id']}")
    assert r.status_code == 409


def test_contratos_protegido_401(client_sin_auth):
    assert client_sin_auth.get("/api/contratos").status_code == 401


def test_delete_contrato_vacio_ok(client):
    con = _crear_contrato(client).json()
    r = client.delete(f"/api/contratos/{con['id']}")
    assert r.status_code in (200, 204)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_api.py -v`
Expected: FAIL (404 en las rutas; el router no existe)

- [ ] **Step 3: Write the router**

```python
# backend/app/routers/contratos.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import contratos_service as svc
from app import models
from app.db import get_db
from app.schemas import (
    AsignarEquipoPayload, ContratoCreate, ContratoDetalle, ContratoOut, ContratoUpdate,
)

router = APIRouter(prefix="/api/contratos", tags=["contratos"])


@router.post("", response_model=ContratoOut, status_code=201)
def crear(payload: ContratoCreate, db: Session = Depends(get_db)) -> models.ContratoMantenimiento:
    con = models.ContratoMantenimiento(codigo=svc.generar_codigo(db), **payload.model_dump())
    db.add(con)
    db.commit()
    db.refresh(con)
    return con


@router.get("", response_model=list[ContratoOut])
def listar(estado: Optional[str] = None, cliente_id: Optional[int] = None,
           db: Session = Depends(get_db)) -> list[models.ContratoMantenimiento]:
    q = db.query(models.ContratoMantenimiento)
    if cliente_id is not None:
        q = q.filter(models.ContratoMantenimiento.cliente_id == cliente_id)
    items = q.order_by(models.ContratoMantenimiento.id.desc()).all()
    if estado is not None:   # estado es derivado → filtrar en memoria
        items = [c for c in items if c.estado == estado]
    return items


@router.get("/{contrato_id}", response_model=ContratoDetalle)
def detalle(contrato_id: int, db: Session = Depends(get_db)) -> ContratoDetalle:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    cliente = db.get(models.Cliente, con.cliente_id) if con.cliente_id else None
    return ContratoDetalle(contrato=con, cliente=cliente, equipos=con.equipos)


@router.put("/{contrato_id}", response_model=ContratoOut)
def editar(contrato_id: int, payload: ContratoUpdate,
           db: Session = Depends(get_db)) -> models.ContratoMantenimiento:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(con, k, v)
    db.commit()
    db.refresh(con)
    return con


@router.delete("/{contrato_id}", status_code=204)
def borrar(contrato_id: int, db: Session = Depends(get_db)) -> None:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    tiene_acciones = db.query(models.AccionPreventiva).filter(
        models.AccionPreventiva.contrato_id == contrato_id).first() is not None
    if con.equipos or tiene_acciones:
        raise HTTPException(409, "El contrato tiene equipos o acciones; cancélalo en su lugar (cancelado=true)")
    db.delete(con)
    db.commit()


@router.post("/{contrato_id}/equipos", response_model=ContratoOut)
def asignar_equipo(contrato_id: int, payload: AsignarEquipoPayload,
                   db: Session = Depends(get_db)) -> models.ContratoMantenimiento:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    eq = db.get(models.Equipo, payload.equipo_id)
    if eq is None:
        raise HTTPException(404, "Equipo no encontrado")
    try:
        svc.vincular_equipo(db, con, eq)
    except svc.ContratoError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(con)
    return con


@router.delete("/{contrato_id}/equipos/{equipo_id}", response_model=ContratoOut)
def desasignar_equipo(contrato_id: int, equipo_id: int,
                      db: Session = Depends(get_db)) -> models.ContratoMantenimiento:
    con = db.get(models.ContratoMantenimiento, contrato_id)
    if con is None:
        raise HTTPException(404, "Contrato no encontrado")
    eq = db.get(models.Equipo, equipo_id)
    if eq is None or eq.contrato_id != contrato_id:
        raise HTTPException(404, "Equipo no vinculado a este contrato")
    svc.desvincular_equipo(db, eq)
    db.commit()
    db.refresh(con)
    return con
```

> Nota: `AccionPreventiva` se referencia en `borrar`. La clase se crea en la Task 8. Si ejecutas las tareas en orden, `test_delete_contrato_con_equipos_409` no llega a tocar acciones, pero el import de `models.AccionPreventiva` fallaría hasta la Task 8. **Para evitarlo, ejecuta la Task 8 (modelo `AccionPreventiva`) ANTES de correr la suite completa de esta tarea, o** usa una comprobación tolerante: `getattr(models, "AccionPreventiva", None)`. Implementación tolerante recomendada:

```python
    _AP = getattr(models, "AccionPreventiva", None)
    tiene_acciones = False
    if _AP is not None:
        tiene_acciones = db.query(_AP).filter(_AP.contrato_id == contrato_id).first() is not None
```

Usa esta versión tolerante en `borrar` para que la tarea sea independiente del orden.

- [ ] **Step 4: Register the router**

En `backend/app/main.py`, junto a los demás imports de routers (~línea 81 import; añade tras `from app.routers import solicitudes`):

```python
from app.routers import contratos
```

Y junto a los `include_router` protegidos (tras `app.include_router(ayuda.router, dependencies=[Depends(get_current_user)])`):

```python
app.include_router(contratos.router, dependencies=[Depends(get_current_user)])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_contratos_api.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add app/routers/contratos.py app/main.py tests/test_contratos_api.py
git commit -m "feat: router /api/contratos (CRUD + asignar/desasignar equipos, protegido)"
```

---

## Task 7: Filtro `?bajo_contrato=` en base instalada

**Files:**
- Modify: `backend/app/routers/equipos.py` (función `listar`)
- Test: `backend/tests/test_equipos_filtro_contrato.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_equipos_filtro_contrato.py
def _setup(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQF", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": "bronze", "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    e_con = client.post("/api/equipos", json={
        "numero_serie": "C1", "producto_id": prod["id"]}).json()
    e_sin = client.post("/api/equipos", json={
        "numero_serie": "S1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": e_con["id"]})
    return e_con["id"], e_sin["id"]


def test_filtro_bajo_contrato_true(client):
    con_id, sin_id = _setup(client)
    ids = [e["id"] for e in client.get("/api/equipos?bajo_contrato=true").json()]
    assert con_id in ids and sin_id not in ids


def test_filtro_bajo_contrato_false(client):
    con_id, sin_id = _setup(client)
    ids = [e["id"] for e in client.get("/api/equipos?bajo_contrato=false").json()]
    assert sin_id in ids and con_id not in ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_equipos_filtro_contrato.py -v`
Expected: FAIL (el filtro aún no existe → ambos equipos vuelven en las dos llamadas)

- [ ] **Step 3: Add the filter**

En `backend/app/routers/equipos.py`, función `listar` (firma ~línea 18): añade el parámetro `bajo_contrato: Optional[bool] = None` y, tras construir la lista de resultados (donde hoy se devuelve la query), filtra en memoria por la propiedad derivada. Localiza el `return` final de `listar` y sustitúyelo por un filtrado:

```python
    bajo_contrato: Optional[bool] = None,
    # ... (resto de parámetros existentes) ...
```

Y antes del `return`, materializa y filtra:

```python
    equipos = q.all()
    if bajo_contrato is not None:
        equipos = [e for e in equipos if e.bajo_contrato == bajo_contrato]
    return equipos
```

> Si `listar` hoy retorna `q.all()` directamente, reemplaza ese return por las tres líneas anteriores. No cambies los filtros existentes (cliente/categoría/estado); el de contrato se aplica sobre el resultado.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_equipos_filtro_contrato.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/routers/equipos.py tests/test_equipos_filtro_contrato.py
git commit -m "feat: filtro ?bajo_contrato= en GET /api/equipos"
```

---

## Task 8: Modelo `AccionPreventiva`

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_preventivo_modelo.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_preventivo_modelo.py
from datetime import date

from app import models


def test_accion_preventiva_se_guarda(db_session):
    p = models.Producto(part_number="6TL-EQP", tipo="equipo", descripcion="Banco")
    db_session.add(p); db_session.flush()
    eq = models.Equipo(numero_serie="SN1", producto_id=p.id)
    db_session.add(eq); db_session.flush()
    a = models.AccionPreventiva(
        equipo_id=eq.id, fecha=date(2026, 6, 5), tecnico="Cim",
        tipo="on_site", veredicto="ok",
    )
    db_session.add(a); db_session.flush()
    assert a.id is not None
    assert a.contrato_id is None and a.incidencia_id is None and a.informe is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_preventivo_modelo.py -v`
Expected: FAIL (`module 'app.models' has no attribute 'AccionPreventiva'`)

- [ ] **Step 3: Add the model**

En `backend/app/models.py`, añade (tras `ContratoMantenimiento`):

```python
class AccionPreventiva(Base):
    __tablename__ = "acciones_preventivo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    contrato_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contratos.id"), nullable=True)
    fecha: Mapped[date] = mapped_column(Date)
    tecnico: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tipo: Mapped[str] = mapped_column(String)               # on_site | remoto
    veredicto: Mapped[str] = mapped_column(String)          # ok | con_observaciones | requiere_accion
    informe: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    proxima_fecha: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    incidencia_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidencias.id"), nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_preventivo_modelo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_preventivo_modelo.py
git commit -m "feat: modelo AccionPreventiva (preventivo por equipo)"
```

---

## Task 9: `preventivo_service` (crear + generar incidencia)

**Files:**
- Create: `backend/app/preventivo_service.py`
- Test: `backend/tests/test_preventivo_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_preventivo_service.py
from datetime import date

import pytest

from app import models
from app import preventivo_service as svc


def _equipo(db, contrato_id=None):
    p = models.Producto(part_number="6TL-EQS", tipo="equipo", descripcion="Banco")
    db.add(p); db.flush()
    eq = models.Equipo(numero_serie="SN1", producto_id=p.id, contrato_id=contrato_id)
    db.add(eq); db.flush()
    return eq


def _contrato(db, nivel="bronze"):
    c = models.ContratoMantenimiento(
        codigo="CTR-0001", nivel=nivel,
        fecha_inicio=date(2020, 1, 1), fecha_fin=date(2100, 1, 1),
    )
    db.add(c); db.flush()
    return c


def test_crear_autoasocia_contrato_vigente_y_sugiere_proxima(db_session):
    con = _contrato(db_session, "bronze")  # preventivo anual
    eq = _equipo(db_session, contrato_id=con.id)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="on_site",
                  veredicto="ok", tecnico="Cim", informe=None, proxima_fecha=None)
    assert a.contrato_id == con.id
    assert a.proxima_fecha == date(2027, 6, 5)   # +12 meses (bronze)


def test_crear_sin_contrato_proxima_vacia(db_session):
    eq = _equipo(db_session, contrato_id=None)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="remoto",
                  veredicto="ok", tecnico=None, informe=None, proxima_fecha=None)
    assert a.contrato_id is None
    assert a.proxima_fecha is None


def test_crear_respeta_proxima_explicita(db_session):
    con = _contrato(db_session)
    eq = _equipo(db_session, contrato_id=con.id)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="on_site",
                  veredicto="ok", tecnico=None, informe=None, proxima_fecha=date(2026, 9, 1))
    assert a.proxima_fecha == date(2026, 9, 1)


def test_generar_incidencia_enlaza(db_session):
    eq = _equipo(db_session)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="on_site",
                  veredicto="requiere_accion", tecnico=None, informe="ruido", proxima_fecha=None)
    inc = svc.generar_incidencia(db_session, a, tipo="soporte_tecnico", prioridad="alta", asignado_a="Cim")
    assert inc.equipo_id == eq.id
    assert inc.estado == "abierta"
    assert a.incidencia_id == inc.id


def test_generar_incidencia_doble_falla(db_session):
    eq = _equipo(db_session)
    a = svc.crear(db_session, eq, fecha=date(2026, 6, 5), tipo="on_site",
                  veredicto="requiere_accion", tecnico=None, informe=None, proxima_fecha=None)
    svc.generar_incidencia(db_session, a, tipo="soporte_tecnico", prioridad="media", asignado_a=None)
    with pytest.raises(svc.PreventivoError):
        svc.generar_incidencia(db_session, a, tipo="soporte_tecnico", prioridad="media", asignado_a=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_preventivo_service.py -v`
Expected: FAIL (`No module named 'app.preventivo_service'`)

- [ ] **Step 3: Write the service**

```python
# backend/app/preventivo_service.py
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app import contratos
from app import incidencias_service as inc_svc
from app import models


class PreventivoError(Exception):
    """Error de negocio en preventivo (→ HTTP 409)."""


def crear(db: Session, equipo: models.Equipo, *, fecha: date, tipo: str, veredicto: str,
          tecnico: Optional[str], informe: Optional[str],
          proxima_fecha: Optional[date]) -> models.AccionPreventiva:
    # Auto-asocia el contrato vigente del equipo (snapshot de bajo qué contrato se hizo).
    contrato = equipo.contrato if (equipo.contrato is not None and equipo.contrato.vigente) else None
    if proxima_fecha is None and contrato is not None:
        proxima_fecha = contratos.sugerir_proxima_fecha(fecha, contrato.nivel)
    accion = models.AccionPreventiva(
        equipo_id=equipo.id,
        contrato_id=contrato.id if contrato is not None else None,
        fecha=fecha, tecnico=tecnico, tipo=tipo, veredicto=veredicto,
        informe=informe, proxima_fecha=proxima_fecha,
    )
    db.add(accion)
    db.flush()
    return accion


def generar_incidencia(db: Session, accion: models.AccionPreventiva, *, tipo: str,
                       prioridad: str, asignado_a: Optional[str]) -> models.Incidencia:
    if accion.incidencia_id is not None:
        raise PreventivoError("Esta acción de preventivo ya tiene una incidencia")
    inc = models.Incidencia(
        codigo=inc_svc.generar_codigo(db, tipo),
        tipo=tipo,
        estado="abierta",
        equipo_id=accion.equipo_id,
        titulo=f"Correctivo desde preventivo del {accion.fecha.isoformat()}",
        descripcion_problema=accion.informe or "Generada desde acción de preventivo",
        prioridad=prioridad,
        asignado_a=asignado_a,
        fecha_apertura=date.today(),
    )
    db.add(inc)
    db.flush()
    accion.incidencia_id = inc.id
    db.flush()
    return inc
```

> Verifica los nombres de campo de `models.Incidencia` (titulo, descripcion_problema, prioridad, estado, equipo_id, fecha_apertura) contra `solicitudes_service.aprobar`, que crea Incidencia igual. Ajusta si difieren.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_preventivo_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/preventivo_service.py tests/test_preventivo_service.py
git commit -m "feat: preventivo_service (crear con auto-contrato/próxima fecha + generar incidencia)"
```

---

## Task 10: Schemas + router de preventivo

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/preventivo.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_preventivo_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_preventivo_api.py
def _equipo_con_contrato(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQA", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": "gold", "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "P1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    return eq["id"]


def test_crear_y_listar_preventivo(client):
    eid = _equipo_con_contrato(client)
    r = client.post(f"/api/equipos/{eid}/preventivos", json={
        "fecha": "2026-06-05", "tipo": "on_site", "veredicto": "ok", "tecnico": "Cim"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["proxima_fecha"] == "2026-12-05"   # gold = semestral
    lista = client.get(f"/api/equipos/{eid}/preventivos").json()
    assert len(lista) == 1 and lista[0]["veredicto"] == "ok"


def test_generar_incidencia_desde_preventivo(client):
    eid = _equipo_con_contrato(client)
    a = client.post(f"/api/equipos/{eid}/preventivos", json={
        "fecha": "2026-06-05", "tipo": "on_site", "veredicto": "requiere_accion",
        "informe": "fuga"}).json()
    r = client.post(f"/api/preventivos/{a['id']}/generar-incidencia", json={
        "tipo": "soporte_tecnico", "prioridad": "alta"})
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "abierta"
    # repetir falla
    r2 = client.post(f"/api/preventivos/{a['id']}/generar-incidencia", json={
        "tipo": "soporte_tecnico", "prioridad": "alta"})
    assert r2.status_code == 409


def test_preventivo_protegido_401(client_sin_auth):
    assert client_sin_auth.get("/api/equipos/1/preventivos").status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_preventivo_api.py -v`
Expected: FAIL (404; rutas inexistentes)

- [ ] **Step 3: Add schemas**

En `backend/app/schemas.py`, sección nueva (tras los schemas de contrato):

```python
# --- Preventivo ---
_TIPO_PREV = Literal["on_site", "remoto"]
_VEREDICTO = Literal["ok", "con_observaciones", "requiere_accion"]


class AccionPreventivaCreate(BaseModel):
    fecha: date
    tipo: _TIPO_PREV
    veredicto: _VEREDICTO
    tecnico: Optional[str] = None
    informe: Optional[str] = None
    proxima_fecha: Optional[date] = None


class AccionPreventivaOut(_ORM):
    id: int
    equipo_id: int
    contrato_id: Optional[int] = None
    fecha: date
    tecnico: Optional[str] = None
    tipo: str
    veredicto: str
    informe: Optional[str] = None
    proxima_fecha: Optional[date] = None
    incidencia_id: Optional[int] = None


class GenerarIncidenciaPrevPayload(BaseModel):
    tipo: Literal["rma", "soporte_venta", "soporte_tecnico", "calibracion"] = "soporte_tecnico"
    prioridad: Literal["baja", "media", "alta"] = "media"
    asignado_a: Optional[str] = None
```

- [ ] **Step 4: Write the router**

```python
# backend/app/routers/preventivo.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app import preventivo_service as svc
from app.db import get_db
from app.schemas import AccionPreventivaCreate, AccionPreventivaOut, GenerarIncidenciaPrevPayload, IncidenciaOut

router = APIRouter(prefix="/api", tags=["preventivo"])


@router.get("/equipos/{equipo_id}/preventivos", response_model=list[AccionPreventivaOut])
def listar(equipo_id: int, db: Session = Depends(get_db)) -> list[models.AccionPreventiva]:
    if db.get(models.Equipo, equipo_id) is None:
        raise HTTPException(404, "Equipo no encontrado")
    return (db.query(models.AccionPreventiva)
            .filter(models.AccionPreventiva.equipo_id == equipo_id)
            .order_by(models.AccionPreventiva.fecha.desc(), models.AccionPreventiva.id.desc())
            .all())


@router.post("/equipos/{equipo_id}/preventivos", response_model=AccionPreventivaOut, status_code=201)
def crear(equipo_id: int, payload: AccionPreventivaCreate,
          db: Session = Depends(get_db)) -> models.AccionPreventiva:
    eq = db.get(models.Equipo, equipo_id)
    if eq is None:
        raise HTTPException(404, "Equipo no encontrado")
    accion = svc.crear(
        db, eq, fecha=payload.fecha, tipo=payload.tipo, veredicto=payload.veredicto,
        tecnico=payload.tecnico, informe=payload.informe, proxima_fecha=payload.proxima_fecha,
    )
    db.commit()
    db.refresh(accion)
    return accion


@router.post("/preventivos/{accion_id}/generar-incidencia", response_model=IncidenciaOut, status_code=201)
def generar_incidencia(accion_id: int, payload: GenerarIncidenciaPrevPayload,
                       db: Session = Depends(get_db)) -> models.Incidencia:
    accion = db.get(models.AccionPreventiva, accion_id)
    if accion is None:
        raise HTTPException(404, "Acción de preventivo no encontrada")
    try:
        inc = svc.generar_incidencia(db, accion, tipo=payload.tipo, prioridad=payload.prioridad,
                                     asignado_a=payload.asignado_a)
    except svc.PreventivoError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    db.refresh(inc)
    return inc
```

- [ ] **Step 5: Register the router**

En `backend/app/main.py`: `from app.routers import preventivo` y
`app.include_router(preventivo.router, dependencies=[Depends(get_current_user)])`.

- [ ] **Step 6: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_preventivo_api.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add app/schemas.py app/routers/preventivo.py app/main.py tests/test_preventivo_api.py
git commit -m "feat: API de preventivo (/api/equipos/{id}/preventivos + generar-incidencia)"
```

---

## Task 11: Cobertura de contrato visible en el expediente de incidencia

`IncidenciaFicha` ya incluye `equipo: EquipoOut`, y `EquipoOut` ya expone `bajo_contrato`/`contrato` (Task 5). Esta tarea solo **verifica** que la cobertura se ve en vivo en el expediente — sin código nuevo salvo que el test falle.

**Files:**
- Test: `backend/tests/test_incidencia_cobertura_contrato.py`

- [ ] **Step 1: Write the test**

```python
# backend/tests/test_incidencia_cobertura_contrato.py
def test_expediente_incidencia_muestra_bajo_contrato(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-EQI", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": "silver", "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "I1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    inc = client.post("/api/incidencias", json={
        "tipo": "soporte_tecnico", "equipo_id": eq["id"],
        "titulo": "fallo", "descripcion_problema": "x", "prioridad": "media"}).json()

    ficha = client.get(f"/api/incidencias/{inc['id']}").json()
    assert ficha["equipo"]["bajo_contrato"] is True
    assert ficha["equipo"]["contrato"]["codigo"] == con["codigo"]
```

- [ ] **Step 2: Run the test**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_incidencia_cobertura_contrato.py -v`
Expected: PASS sin código nuevo. (Si el alta de incidencia o el endpoint de ficha usan otra ruta/campos, ajusta el test a los contratos reales del router `incidencias.py` — NO cambies la lógica del router.)

- [ ] **Step 3: Run the FULL suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (toda la suite verde, incluidos los 229 previos + los nuevos)

- [ ] **Step 4: Commit**

```bash
git add tests/test_incidencia_cobertura_contrato.py
git commit -m "test: cobertura de contrato visible en vivo en el expediente de incidencia"
```

---

## Task 12: Prompt Lovable 22 (frontend)

**Files:**
- Create: `docs/lovable/22_contratos_preventivo.md`

- [ ] **Step 1: Write the prompt**

Crea `docs/lovable/22_contratos_preventivo.md` siguiendo el estilo de `docs/lovable/21_solicitudes_soporte.md` (cabecera de contexto idéntica: TanStack Start, `VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()` con Bearer, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`, "NO cambies nombres de campo"). Debe cubrir:

1. **Tipos** en `src/lib/types.ts`: `Contrato` (id, codigo, cliente_id, nivel `"bronze"|"silver"|"gold"`, fecha_inicio, fecha_fin, cancelado, notas, estado `"pendiente"|"vigente"|"vencido"|"cancelado"`, vigente, nivel_detalle), `ContratoResumen`, `AccionPreventiva` (id, equipo_id, contrato_id, fecha, tecnico, tipo `"on_site"|"remoto"`, veredicto `"ok"|"con_observaciones"|"requiere_accion"`, informe, proxima_fecha, incidencia_id). Añadir `pn_fabricante` a `Producto` y `bajo_contrato`/`contrato` a `Equipo`.
2. **Catálogo (producto):** campo P/N de fabricante en alta/edición; mostrarlo en la "Configuración actual" del equipo junto al `part_number` 6TL.
3. **Pantalla Contratos** `/contratos` (en el menú): lista (codigo, cliente, nivel badge, estado/vigencia) vía `GET /api/contratos?estado=`; alta/edición (`POST/PUT /api/contratos`); ficha `GET /api/contratos/{id}` con `contrato` + `nivel_detalle` (preventivo/soporte/respuesta) + tabla de equipos cubiertos con asignar (`POST /api/contratos/{id}/equipos` body `{equipo_id}`, reusar selector de equipos) y desasignar (`DELETE /api/contratos/{id}/equipos/{equipo_id}`). DELETE de contrato con equipos → 409: mostrar aviso de cancelar.
4. **Base instalada / ficha de equipo:** badge "Bajo contrato" (verde si `bajo_contrato`) + filtro `GET /api/equipos?bajo_contrato=true|false`. Sección **Preventivo**: historial `GET /api/equipos/{id}/preventivos` + botón "Registrar preventivo" (`POST` con fecha/tipo/veredicto/tecnico/informe/proxima_fecha; proxima_fecha se autocompleta server-side si se deja vacía) + desde una acción con veredicto ≠ ok, botón "Generar incidencia" (`POST /api/preventivos/{id}/generar-incidencia` body `{tipo,prioridad,asignado_a}` → navega a la incidencia creada).
5. **Incidencias:** indicador informativo de cobertura de contrato junto al de garantía (lee `equipo.bajo_contrato` y `equipo.contrato` del expediente — ya viene en la respuesta, sin endpoint nuevo).

No inventes endpoints ni campos fuera de los listados.

- [ ] **Step 2: Commit**

```bash
git add docs/lovable/22_contratos_preventivo.md
git commit -m "docs: prompt Lovable 22 — contratos + preventivo + P/N fabricante"
```

---

## Self-review notes (cobertura del spec)
- P/N fabricante → Task 1. Contratos (modelo/estado/niveles) → Tasks 2-3-5-6. Cobertura derivada + filtro → Tasks 3-7. Validación cliente → Task 4/6. Preventivo (acciones+informe+próxima+generar incidencia) → Tasks 8-9-10. Cobertura en incidencias → Task 11. Frontend → Task 12. Auditoría → automática (sin tarea). Migraciones → Tasks 1 y 3.
- ⚠️ Tests con estado derivado usan fechas absolutas amplias (2020→2100) para no depender de "hoy". Si algún test necesita un caso "por vencer", fija fechas concretas.
- ⚠️ `EquipoOut` gana campos → la full suite tras Task 5 detecta regresiones de serialización.
