# Autenticación + auditoría interna — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir login simple (usuario/contraseña + token de sesión `Bearer`) y un log de auditoría completo que registre automáticamente quién da de alta, edita o borra cada dato (con diff de campos), dejando el hueco para permisos por rol en el futuro.

**Architecture:** Tres piezas aditivas. (1) Auth: modelos `Usuario`/`Sesion`, `seguridad.py` (pbkdf2 stdlib), `auth_service.py`, router `auth.py`, dependencia `get_current_user`. (2) Protección: los 12 routers internos se registran con `dependencies=[Depends(get_current_user)]`; el fixture de tests sobreescribe la dependencia para no romper los 166 tests. (3) Auditoría: modelo `AuditoriaLog` + listener de sesión SQLAlchemy (`before_flush`/`after_flush`) que captura los cambios e inserta filas en la misma transacción, leyendo el usuario de `db.info`; router de consulta `auditoria.py`. CLI `crear_usuario` para el bootstrap.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2 (`Mapped`), Pydantic v2, `hashlib`/`hmac`/`secrets` (stdlib, sin `passlib`/`jwt`), pytest.

**Convenciones:** tests en `backend/tests/`; ejecutar desde `backend/` con `.venv\Scripts\python.exe -m pytest -q`. Commit por tarea, mensaje en español terminando con `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Baseline actual: **166 tests verde**.

**Contexto del código (ya verificado):**
- `app/db.py`: `Base`, `engine`, `SessionLocal = sessionmaker(... expire_on_commit=False ...)`, `get_db`.
- `app/models.py`: importa `from datetime import date` y `from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, UniqueConstraint`. Entidades con patrón `Mapped`/`mapped_column`.
- `app/schemas.py`: importa `from datetime import date` y `from pydantic import BaseModel, ConfigDict, Field, model_validator`; tiene `class _ORM(BaseModel): model_config = ConfigDict(from_attributes=True)`.
- `app/main.py`: hace `create_all` + `add_missing_columns`, define `app`, CORS, y registra 12 routers (`clientes, ubicaciones, productos, equipos, componentes, movimientos, configuracion, busqueda, incidencias, mapa, analitica, avances`), luego `GET /api/health`.
- `tests/conftest.py`: fixtures `memory_engine` (SQLite `:memory:` + `Base.metadata.create_all`), `db_session`, y `client` (que hace `app.dependency_overrides[get_db] = _override_get_db`).
- **NOTA DE INTEGRACIÓN (fuera de este plan):** la feature "Solicitud de soporte" vive en otra rama y aporta `POST /api/solicitudes` (público) + endpoints internos. Al fusionar esa rama con ésta habrá que: dejar el `POST /api/solicitudes` **sin** `get_current_user`, y añadir `Depends(get_current_user)` a sus endpoints internos (`GET` lista, `GET /{id}`, `aprobar`, `rechazar`). No forma parte de este plan.

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---------|-----------------|--------|
| `backend/app/seguridad.py` | hash/verify de contraseñas (pbkdf2 stdlib). | Crear |
| `backend/app/models.py` | + `Usuario`, `Sesion`, `AuditoriaLog`. | Modificar |
| `backend/app/schemas.py` | + schemas de login/usuario/auditoría. | Modificar |
| `backend/app/auth_service.py` | autenticar / crear_sesion / validar_token / cerrar_sesion + excepciones. | Crear |
| `backend/app/deps.py` | dependencia `get_current_user` (valida token + sella `db.info`). | Crear |
| `backend/app/routers/auth.py` | `POST /login`, `POST /logout`, `GET /me`. | Crear |
| `backend/app/auditoria.py` | listener de sesión que captura alta/edición/borrado con diff. | Crear |
| `backend/app/routers/auditoria.py` | `GET /api/auditoria` (consulta filtrable). | Crear |
| `backend/app/crear_usuario.py` | CLI de bootstrap de usuarios. | Crear |
| `backend/app/main.py` | registrar routers `auth`/`auditoria`, proteger los 12 internos, enganchar el listener. | Modificar |
| `backend/tests/conftest.py` | override de `get_current_user` (compat) + fixture `client_sin_auth`. | Modificar |
| `backend/tests/test_*.py` | tests nuevos por pieza. | Crear |
| `docs/lovable/19_auth_auditoria.md` + `README.md` | prompt Lovable (login + historial por ficha). | Crear/Modificar |

---

## Task 1: `seguridad.py` — hash/verify de contraseñas

**Files:**
- Create: `backend/app/seguridad.py`
- Test: `backend/tests/test_seguridad.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_seguridad.py`:

```python
from app import seguridad


def test_hash_distinto_por_salt():
    h1 = seguridad.hash_password("secreto")
    h2 = seguridad.hash_password("secreto")
    assert h1 != h2                      # salt aleatorio
    assert h1.startswith("pbkdf2_sha256$")


def test_verify_ok_y_ko():
    h = seguridad.hash_password("secreto")
    assert seguridad.verify_password("secreto", h) is True
    assert seguridad.verify_password("otra", h) is False


def test_verify_hash_malformado_devuelve_false():
    assert seguridad.verify_password("x", "no-es-un-hash") is False
    assert seguridad.verify_password("x", "") is False
    assert seguridad.verify_password("x", "pbkdf2_sha256$abc$def") is False  # faltan campos
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_seguridad.py -q`
Expected: FAIL (`No module named 'app.seguridad'`).

- [ ] **Step 3: Create the module**

Crear `backend/app/seguridad.py`:

```python
from __future__ import annotations

import hashlib
import hmac
import secrets

_ALG = "pbkdf2_sha256"
ITERACIONES = 200_000


def hash_password(password: str, *, iteraciones: int = ITERACIONES) -> str:
    """Devuelve un hash autocontenido `pbkdf2_sha256$<iter>$<salt_hex>$<hash_hex>`."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iteraciones)
    return f"{_ALG}${iteraciones}${salt.hex()}${dk.hex()}"


def verify_password(password: str, almacenado: str) -> bool:
    """Compara `password` contra el hash almacenado. False ante formato inválido (no lanza)."""
    try:
        alg, iter_str, salt_hex, hash_hex = almacenado.split("$")
        if alg != _ALG:
            return False
        iteraciones = int(iter_str)
        salt = bytes.fromhex(salt_hex)
        esperado = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iteraciones)
    return hmac.compare_digest(dk, esperado)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_seguridad.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/seguridad.py backend/tests/test_seguridad.py
git commit -m "feat: modulo seguridad (hash/verify pbkdf2 stdlib)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 2: Modelos `Usuario`/`Sesion` + `auth_service.py`

**Files:**
- Modify: `backend/app/models.py` (imports arriba + 2 clases al final)
- Create: `backend/app/auth_service.py`
- Test: `backend/tests/test_auth_service.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_auth_service.py`:

```python
from datetime import date, datetime, timedelta

import pytest

from app import auth_service as svc
from app import models, seguridad


def _crear_usuario(db, username="ramon", password="secreto", activo=True):
    u = models.Usuario(
        username=username, nombre="Ramón",
        password_hash=seguridad.hash_password(password),
        activo=activo, rol="admin", fecha_alta=date(2026, 6, 5),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_autenticar_ok(db_session):
    u = _crear_usuario(db_session)
    assert svc.autenticar(db_session, "ramon", "secreto").id == u.id


def test_autenticar_password_mala(db_session):
    _crear_usuario(db_session)
    with pytest.raises(svc.CredencialesInvalidas):
        svc.autenticar(db_session, "ramon", "mala")


def test_autenticar_usuario_inactivo(db_session):
    _crear_usuario(db_session, activo=False)
    with pytest.raises(svc.CredencialesInvalidas):
        svc.autenticar(db_session, "ramon", "secreto")


def test_autenticar_usuario_inexistente(db_session):
    with pytest.raises(svc.CredencialesInvalidas):
        svc.autenticar(db_session, "nadie", "x")


def test_crear_y_validar_token(db_session):
    u = _crear_usuario(db_session)
    s = svc.crear_sesion(db_session, u)
    assert s.token and s.usuario_id == u.id
    assert svc.validar_token(db_session, s.token).id == u.id


def test_validar_token_expirado(db_session):
    u = _crear_usuario(db_session)
    ayer = datetime(2026, 1, 1)
    s = svc.crear_sesion(db_session, u, ahora=ayer)
    with pytest.raises(svc.SesionInvalida):
        svc.validar_token(db_session, s.token, ahora=datetime(2026, 6, 5))


def test_validar_token_inexistente(db_session):
    with pytest.raises(svc.SesionInvalida):
        svc.validar_token(db_session, "no-existe")


def test_cerrar_sesion(db_session):
    u = _crear_usuario(db_session)
    s = svc.crear_sesion(db_session, u)
    svc.cerrar_sesion(db_session, s.token)
    with pytest.raises(svc.SesionInvalida):
        svc.validar_token(db_session, s.token)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_auth_service.py -q`
Expected: FAIL (`No module named 'app.auth_service'` / `Usuario` no existe).

- [ ] **Step 3: Add the models**

En `backend/app/models.py`, AMPLÍA los imports de arriba (deja el resto igual):

```python
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
```

Y AÑADE al FINAL del archivo:

```python
class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    nombre: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    rol: Mapped[str] = mapped_column(String, default="admin")
    fecha_alta: Mapped[date] = mapped_column(Date)


class Sesion(Base):
    __tablename__ = "sesiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime)
    fecha_expiracion: Mapped[datetime] = mapped_column(DateTime)

    usuario: Mapped["Usuario"] = relationship()
```

(`Text` y `datetime` se usarán también en Task 5; impórtalos ya.)

- [ ] **Step 4: Create the service**

Crear `backend/app/auth_service.py`:

```python
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import models, seguridad


class CredencialesInvalidas(Exception):
    """Login fallido (usuario/contraseña incorrectos o usuario inactivo)."""


class SesionInvalida(Exception):
    """Token inexistente, expirado, o de usuario inactivo."""


def _dias_sesion() -> int:
    try:
        return int(os.environ.get("AUTH_SESION_DIAS", "7"))
    except ValueError:
        return 7


def autenticar(db: Session, username: str, password: str) -> models.Usuario:
    u = db.query(models.Usuario).filter(models.Usuario.username == username).first()
    if u is None or not u.activo or not seguridad.verify_password(password, u.password_hash):
        raise CredencialesInvalidas("Usuario o contraseña incorrectos")
    return u


def crear_sesion(db: Session, usuario: models.Usuario, *, ahora: Optional[datetime] = None) -> models.Sesion:
    ahora = ahora or datetime.now()
    s = models.Sesion(
        token=secrets.token_urlsafe(32),
        usuario_id=usuario.id,
        fecha_creacion=ahora,
        fecha_expiracion=ahora + timedelta(days=_dias_sesion()),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def validar_token(db: Session, token: str, *, ahora: Optional[datetime] = None) -> models.Usuario:
    ahora = ahora or datetime.now()
    s = db.query(models.Sesion).filter(models.Sesion.token == token).first()
    if s is None or s.fecha_expiracion < ahora:
        raise SesionInvalida("Sesión inválida o expirada")
    u = db.get(models.Usuario, s.usuario_id)
    if u is None or not u.activo:
        raise SesionInvalida("Usuario inactivo")
    return u


def cerrar_sesion(db: Session, token: str) -> None:
    s = db.query(models.Sesion).filter(models.Sesion.token == token).first()
    if s is not None:
        db.delete(s)
        db.commit()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_auth_service.py -q`
Expected: PASS (8 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/auth_service.py backend/tests/test_auth_service.py
git commit -m "feat: modelos Usuario/Sesion + auth_service (login/token)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 3: Schemas + dependencia `get_current_user` + router `auth.py`

**Files:**
- Modify: `backend/app/schemas.py` (imports + schemas nuevos al final)
- Create: `backend/app/deps.py`
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py` (registrar router `auth`)
- Test: `backend/tests/test_auth_router.py`

NOTA: en esta tarea **NO** se protegen aún los routers internos (eso es la Task 4, junto al override de tests). Aquí solo se añaden los endpoints de auth, que conviven con los 166 tests sin romperlos.

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_auth_router.py`:

```python
from datetime import date

from app import models, seguridad


def _crear_usuario(client_db, username="ramon", password="secreto", activo=True):
    db = client_db
    u = models.Usuario(
        username=username, nombre="Ramón",
        password_hash=seguridad.hash_password(password),
        activo=activo, rol="admin", fecha_alta=date(2026, 6, 5),
    )
    db.add(u)
    db.commit()


def test_login_ok_devuelve_token_y_usuario(client, db_session):
    _crear_usuario(db_session)
    r = client.post("/api/auth/login", json={"username": "ramon", "password": "secreto"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["token"]
    assert b["usuario"]["username"] == "ramon" and b["usuario"]["rol"] == "admin"
    assert "password_hash" not in b["usuario"]


def test_login_password_mala_401(client, db_session):
    _crear_usuario(db_session)
    r = client.post("/api/auth/login", json={"username": "ramon", "password": "mala"})
    assert r.status_code == 401


def test_login_inactivo_401(client, db_session):
    _crear_usuario(db_session, activo=False)
    r = client.post("/api/auth/login", json={"username": "ramon", "password": "secreto"})
    assert r.status_code == 401


def test_me_con_token_ok_sin_token_401(client, db_session):
    _crear_usuario(db_session)
    tok = client.post("/api/auth/login", json={"username": "ramon", "password": "secreto"}).json()["token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.json()["username"] == "ramon"
    assert client.get("/api/auth/me").status_code == 401


def test_logout_invalida_token(client, db_session):
    _crear_usuario(db_session)
    tok = client.post("/api/auth/login", json={"username": "ramon", "password": "secreto"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401
```

IMPORTANTE: estos tests comparten el mismo motor en memoria entre `db_session` y `client` (ambos derivan de `memory_engine` en `conftest`). Eso ya funciona con el `conftest` actual.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_auth_router.py -q`
Expected: FAIL (404, router `auth` no registrado).

- [ ] **Step 3: Add the schemas**

En `backend/app/schemas.py`, cambia el import de datetime de arriba a:

```python
from datetime import date, datetime
```

Y AÑADE al FINAL del archivo:

```python
# --- Auth ---
class UsuarioOut(_ORM):
    id: int
    username: str
    nombre: str
    rol: str
    activo: bool


class LoginPayload(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    usuario: UsuarioOut


# --- Auditoría ---
class AuditoriaLogOut(_ORM):
    id: int
    fecha_hora: datetime
    usuario_id: Optional[int] = None
    usuario_username: str
    entidad: str
    entidad_id: int
    accion: str
    cambios: Optional[str] = None
```

- [ ] **Step 4: Create the dependency**

Crear `backend/app/deps.py`:

```python
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import auth_service, models
from app.db import get_db


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> models.Usuario:
    """Valida el token Bearer y sella el usuario en la sesión de BD (para auditoría)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "No autenticado")
    token = authorization.split(" ", 1)[1].strip()
    try:
        usuario = auth_service.validar_token(db, token)
    except auth_service.SesionInvalida:
        raise HTTPException(401, "Sesión inválida o expirada")
    db.info["usuario_id"] = usuario.id
    db.info["usuario_username"] = usuario.username
    return usuario
```

- [ ] **Step 5: Create the router**

Crear `backend/app/routers/auth.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import auth_service, models
from app.db import get_db
from app.deps import get_current_user
from app.schemas import LoginOut, LoginPayload, UsuarioOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    try:
        usuario = auth_service.autenticar(db, payload.username, payload.password)
    except auth_service.CredencialesInvalidas:
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    sesion = auth_service.crear_sesion(db, usuario)
    return {"token": sesion.token, "usuario": usuario}


@router.post("/logout", status_code=204)
def logout(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
) -> None:
    token = authorization.split(" ", 1)[1].strip()
    auth_service.cerrar_sesion(db, token)


@router.get("/me", response_model=UsuarioOut)
def me(usuario: models.Usuario = Depends(get_current_user)) -> models.Usuario:
    return usuario
```

- [ ] **Step 6: Register the router**

En `backend/app/main.py`, tras el bloque de `avances` (y antes del `@app.get("/api/health")`), añade:

```python
from app.routers import auth
app.include_router(auth.router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_auth_router.py -q`
Expected: PASS (5 passed).

Y la suite completa sigue verde:
Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest -q -p no:warnings`
Expected: PASS (166 previos + 8 + 3 + 5 nuevos).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas.py backend/app/deps.py backend/app/routers/auth.py backend/app/main.py backend/tests/test_auth_router.py
git commit -m "feat: router auth (login/logout/me) + dependencia get_current_user"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 4: Proteger los 12 routers internos + compat de tests

**Files:**
- Modify: `backend/app/main.py` (dependencia a nivel de `include_router`)
- Modify: `backend/tests/conftest.py` (override de `get_current_user` + fixture `client_sin_auth`)
- Test: `backend/tests/test_proteccion.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_proteccion.py`:

```python
from datetime import date

from app import models, seguridad


def test_endpoint_interno_sin_token_da_401(client_sin_auth):
    # client_sin_auth NO sobreescribe get_current_user -> exige token de verdad
    assert client_sin_auth.get("/api/equipos").status_code == 401


def test_endpoint_interno_con_token_ok(client_sin_auth, db_session):
    db_session.add(models.Usuario(
        username="ramon", nombre="R", password_hash=seguridad.hash_password("s"),
        activo=True, rol="admin", fecha_alta=date(2026, 6, 5),
    ))
    db_session.commit()
    tok = client_sin_auth.post("/api/auth/login", json={"username": "ramon", "password": "s"}).json()["token"]
    r = client_sin_auth.get("/api/equipos", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200


def test_health_y_login_son_publicos(client_sin_auth):
    assert client_sin_auth.get("/api/health").status_code == 200
    # login con credenciales inexistentes responde 401 (no 'no autenticado' por falta de token)
    assert client_sin_auth.post("/api/auth/login", json={"username": "x", "password": "y"}).status_code == 401


def test_client_con_override_no_exige_token(client):
    # el fixture `client` (override activo) deja pasar sin token -> compat de los 166 tests
    assert client.get("/api/equipos").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_proteccion.py -q`
Expected: FAIL (`fixture 'client_sin_auth' not found` y/o `/api/equipos` devuelve 200 sin token porque aún no hay protección).

- [ ] **Step 3: Protect the routers in main.py**

En `backend/app/main.py`:

1. Añade el import de la dependencia cerca de los otros imports de FastAPI (debajo de `from fastapi.middleware.cors import CORSMiddleware`):

```python
from fastapi import Depends
from app.deps import get_current_user
```

(Si `Depends` ya está importado de `fastapi`, no lo dupliques.)

2. Cambia las 12 líneas `app.include_router(X.router)` de los routers internos para que sean:

```python
app.include_router(clientes.router, dependencies=[Depends(get_current_user)])
app.include_router(ubicaciones.router, dependencies=[Depends(get_current_user)])
app.include_router(productos.router, dependencies=[Depends(get_current_user)])
app.include_router(equipos.router, dependencies=[Depends(get_current_user)])
app.include_router(componentes.router, dependencies=[Depends(get_current_user)])
app.include_router(movimientos.router, dependencies=[Depends(get_current_user)])
app.include_router(configuracion.router, dependencies=[Depends(get_current_user)])
app.include_router(busqueda.router, dependencies=[Depends(get_current_user)])
app.include_router(incidencias.router, dependencies=[Depends(get_current_user)])
app.include_router(mapa.router, dependencies=[Depends(get_current_user)])
app.include_router(analitica.router, dependencies=[Depends(get_current_user)])
app.include_router(avances.router, dependencies=[Depends(get_current_user)])
```

**NO** toques el include de `auth` (login debe ser público; logout/me ya se protegen solos por su propia dependencia). El `import`/registro de cada router (`from app.routers import X`) se queda igual; solo cambia la llamada `include_router`.

- [ ] **Step 4: Update conftest (override + nuevo fixture)**

En `backend/tests/conftest.py`:

1. Amplía el import de `app.db`:

```python
from app.db import Base, get_db
```
(ya está). Añade tras los imports:

```python
from fastapi import Depends
from app.deps import get_current_user
from app import models
```

2. En el fixture `client`, AÑADE el override de `get_current_user` (que además sella `db.info`, igual que el real), dejando intacto el de `get_db`:

```python
@pytest.fixture
def client(memory_engine):
    """TestClient cuyo get_db usa el motor en memoria y con auth simulada (usuario de prueba)."""
    SessionTest = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)

    def _override_get_db():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    def _override_current_user(db=Depends(get_db)):
        usuario = db.get(models.Usuario, 1)
        db.info["usuario_id"] = usuario.id if usuario else None
        db.info["usuario_username"] = usuario.username if usuario else "test"
        return usuario

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

Necesitarás `from fastapi import Depends` arriba en conftest.

3. AÑADE un fixture nuevo `client_sin_auth` que SOLO sobreescribe `get_db` (auth real):

```python
@pytest.fixture
def client_sin_auth(memory_engine):
    """TestClient con auth REAL (sin override de get_current_user) para tests de protección."""
    SessionTest = sessionmaker(bind=memory_engine, autoflush=False, expire_on_commit=False)

    def _override_get_db():
        db = SessionTest()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_proteccion.py -q`
Expected: PASS (4 passed).

Suite completa (los 166 previos siguen verdes gracias al override):
Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest -q -p no:warnings`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/conftest.py backend/tests/test_proteccion.py
git commit -m "feat: proteger routers internos con get_current_user + compat de tests"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 5: `AuditoriaLog` + listener de captura automática

**Files:**
- Modify: `backend/app/models.py` (+ `AuditoriaLog` al final)
- Create: `backend/app/auditoria.py`
- Modify: `backend/app/main.py` (importar el módulo para enganchar el listener)
- Test: `backend/tests/test_auditoria.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_auditoria.py`:

```python
import json
from datetime import date

from app import models, seguridad


def _con_usuario(db):
    db.info["usuario_id"] = None
    db.info["usuario_username"] = "ramon"


def test_alta_genera_log(db_session):
    _con_usuario(db_session)
    db_session.add(models.Cliente(nombre="ACME"))
    db_session.commit()
    logs = db_session.query(models.AuditoriaLog).filter_by(entidad="clientes").all()
    assert len(logs) == 1
    log = logs[0]
    assert log.accion == "alta" and log.usuario_username == "ramon" and log.entidad_id is not None
    cambios = json.loads(log.cambios)
    assert cambios["nombre"][1] == "ACME"


def test_edicion_genera_log_con_diff(db_session):
    _con_usuario(db_session)
    c = models.Cliente(nombre="ACME")
    db_session.add(c)
    db_session.commit()
    c.nombre = "ACME 2"
    db_session.commit()
    log = db_session.query(models.AuditoriaLog).filter_by(entidad="clientes", accion="edicion").one()
    cambios = json.loads(log.cambios)
    assert cambios["nombre"] == ["ACME", "ACME 2"]


def test_edicion_sin_cambios_reales_no_genera_log(db_session):
    _con_usuario(db_session)
    c = models.Cliente(nombre="ACME")
    db_session.add(c)
    db_session.commit()
    c.nombre = "ACME"  # mismo valor
    db_session.commit()
    assert db_session.query(models.AuditoriaLog).filter_by(accion="edicion").count() == 0


def test_borrado_genera_log(db_session):
    _con_usuario(db_session)
    c = models.Cliente(nombre="ACME")
    db_session.add(c)
    db_session.commit()
    cid = c.id
    db_session.delete(c)
    db_session.commit()
    log = db_session.query(models.AuditoriaLog).filter_by(entidad="clientes", accion="borrado").one()
    assert log.entidad_id == cid


def test_sin_usuario_registra_sistema(db_session):
    # sin sellar db.info
    db_session.add(models.Cliente(nombre="X"))
    db_session.commit()
    log = db_session.query(models.AuditoriaLog).filter_by(entidad="clientes").one()
    assert log.usuario_username == "sistema"


def test_password_hash_redactado(db_session):
    _con_usuario(db_session)
    db_session.add(models.Usuario(
        username="u", nombre="U", password_hash=seguridad.hash_password("s"),
        activo=True, rol="admin", fecha_alta=date(2026, 6, 5),
    ))
    db_session.commit()
    log = db_session.query(models.AuditoriaLog).filter_by(entidad="usuarios").one()
    cambios = json.loads(log.cambios)
    assert cambios["password_hash"][1] == "***"


def test_sesion_y_auditoria_excluidas(db_session):
    _con_usuario(db_session)
    u = models.Usuario(
        username="u", nombre="U", password_hash=seguridad.hash_password("s"),
        activo=True, rol="admin", fecha_alta=date(2026, 6, 5),
    )
    db_session.add(u)
    db_session.commit()
    from app import auth_service
    auth_service.crear_sesion(db_session, u)  # crea una Sesion
    # no debe haber log de entidad 'sesiones' ni 'auditoria'
    assert db_session.query(models.AuditoriaLog).filter(
        models.AuditoriaLog.entidad.in_(["sesiones", "auditoria"])
    ).count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_auditoria.py -q`
Expected: FAIL (`AuditoriaLog` no existe / no hay listener).

- [ ] **Step 3: Add the model**

AÑADE al FINAL de `backend/app/models.py`:

```python
class AuditoriaLog(Base):
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime)
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    usuario_username: Mapped[str] = mapped_column(String)
    entidad: Mapped[str] = mapped_column(String)
    entidad_id: Mapped[int] = mapped_column(Integer)
    accion: Mapped[str] = mapped_column(String)
    cambios: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Create the listener module**

Crear `backend/app/auditoria.py`:

```python
from __future__ import annotations

import json
import logging
from datetime import date, datetime

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app import models

log = logging.getLogger(__name__)

# Entidades que NO se auditan.
_EXCLUIDAS = {models.AuditoriaLog, models.Sesion}
# Campos cuyo valor se redacta en el diff.
_CAMPOS_SENSIBLES = {"password_hash", "token"}


def _serializar(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)


def _columnas(obj) -> list[str]:
    return [c.key for c in inspect(obj).mapper.column_attrs]


def _valores_actuales(obj) -> dict:
    out = {}
    for col in _columnas(obj):
        val = "***" if col in _CAMPOS_SENSIBLES else _serializar(getattr(obj, col))
        out[col] = val
    return out


def _diff_edicion(obj) -> dict:
    """Devuelve {campo: [antes, después]} solo de los campos que cambiaron de verdad."""
    estado = inspect(obj)
    cambios = {}
    for col in _columnas(obj):
        hist = estado.attrs[col].history
        if not hist.has_changes():
            continue
        antes = hist.deleted[0] if hist.deleted else None
        despues = hist.added[0] if hist.added else None
        if col in _CAMPOS_SENSIBLES:
            cambios[col] = ["***", "***"]
        else:
            cambios[col] = [_serializar(antes), _serializar(despues)]
    return cambios


def _usuario(session: Session):
    return (
        session.info.get("usuario_id"),
        session.info.get("usuario_username") or "sistema",
    )


def _registrar(session: Session) -> None:
    """before_flush: captura altas/ediciones/borrados pendientes en session.info['_audit']."""
    pendientes = session.info.setdefault("_audit", [])
    uid, uname = _usuario(session)
    ahora = datetime.now()

    for obj in session.new:
        if type(obj) in _EXCLUIDAS:
            continue
        pendientes.append({"obj": obj, "entidad": obj.__tablename__, "accion": "alta",
                           "cambios": {k: [None, v] for k, v in _valores_actuales(obj).items()},
                           "uid": uid, "uname": uname, "ahora": ahora})

    for obj in session.dirty:
        if type(obj) in _EXCLUIDAS or not session.is_modified(obj, include_collections=False):
            continue
        diff = _diff_edicion(obj)
        if not diff:
            continue
        pendientes.append({"obj": obj, "entidad": obj.__tablename__, "accion": "edicion",
                           "cambios": diff, "uid": uid, "uname": uname, "ahora": ahora,
                           "entidad_id": inspect(obj).identity[0] if inspect(obj).identity else None})

    for obj in session.deleted:
        if type(obj) in _EXCLUIDAS:
            continue
        pendientes.append({"obj": None, "entidad": obj.__tablename__, "accion": "borrado",
                           "cambios": _valores_actuales(obj), "uid": uid, "uname": uname, "ahora": ahora,
                           "entidad_id": inspect(obj).identity[0] if inspect(obj).identity else None})


def _emitir(session: Session) -> None:
    """after_flush: con los PK ya asignados, inserta las filas de auditoría (core insert, misma transacción)."""
    pendientes = session.info.pop("_audit", [])
    if not pendientes:
        return
    filas = []
    for p in pendientes:
        entidad_id = p.get("entidad_id")
        if entidad_id is None and p["obj"] is not None:
            ident = inspect(p["obj"]).identity
            entidad_id = ident[0] if ident else None
        filas.append({
            "fecha_hora": p["ahora"], "usuario_id": p["uid"], "usuario_username": p["uname"],
            "entidad": p["entidad"], "entidad_id": entidad_id, "accion": p["accion"],
            "cambios": json.dumps(p["cambios"], ensure_ascii=False),
        })
    session.execute(models.AuditoriaLog.__table__.insert(), filas)


_ENGANCHADO = False


def registrar_listeners() -> None:
    """Engancha los listeners de auditoría a la clase Session (idempotente vía flag de módulo)."""
    global _ENGANCHADO
    if _ENGANCHADO:
        return
    event.listen(Session, "before_flush", lambda s, fc, i: _registrar(s))
    event.listen(Session, "after_flush", lambda s, fc: _emitir(s))
    _ENGANCHADO = True
```

(Se usa un flag de módulo `_ENGANCHADO` en vez de `event.contains`, porque al registrar lambdas
`event.contains` no las reconocería y podría re-enganchar.)

- [ ] **Step 5: Hook the listener at startup and in tests**

En `backend/app/main.py`, tras `add_missing_columns(engine)` (antes de crear `app` o justo después, da igual mientras sea al importar), añade:

```python
from app.auditoria import registrar_listeners
registrar_listeners()
```

Como `conftest.py` importa `from app.main import app`, los listeners quedan enganchados también en los tests (van sobre la clase `Session`, no sobre un engine concreto).

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_auditoria.py -q`
Expected: PASS (7 passed).

Suite completa (ahora cada escritura de los tests genera filas de auditoría en su BD en memoria; no deben romperse):
Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest -q -p no:warnings`
Expected: PASS. Si algún test fallara por serialización, revisa `_serializar` (debe cubrir date/datetime/bool/None/str/int/float).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/auditoria.py backend/app/main.py backend/tests/test_auditoria.py
git commit -m "feat: log de auditoria automatico (listener ORM con diff de campos)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 6: Router de consulta `GET /api/auditoria`

**Files:**
- Create: `backend/app/routers/auditoria.py`
- Modify: `backend/app/main.py` (registrar router protegido)
- Test: `backend/tests/test_auditoria_endpoint.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_auditoria_endpoint.py`:

```python
def test_auditoria_filtra_por_entidad(client):
    # el fixture `client` sella usuario de prueba; crear un cliente genera un log
    client.post("/api/clientes", json={"nombre": "ACME"})
    r = client.get("/api/auditoria", params={"entidad": "clientes"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 1
    assert all(item["entidad"] == "clientes" for item in data)
    assert data[0]["accion"] == "alta"


def test_auditoria_filtra_por_entidad_id(client):
    c = client.post("/api/clientes", json={"nombre": "ACME"}).json()
    otro = client.post("/api/clientes", json={"nombre": "OTRA"}).json()
    r = client.get("/api/auditoria", params={"entidad": "clientes", "entidad_id": c["id"]})
    ids = {item["entidad_id"] for item in r.json()}
    assert ids == {c["id"]}


def test_auditoria_orden_desc_y_limite(client):
    for n in range(3):
        client.post("/api/clientes", json={"nombre": f"C{n}"})
    r = client.get("/api/auditoria", params={"limit": 2})
    data = r.json()
    assert len(data) == 2
    assert data[0]["id"] > data[1]["id"]   # más reciente primero
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_auditoria_endpoint.py -q`
Expected: FAIL (404, router no registrado).

- [ ] **Step 3: Create the router**

Crear `backend/app/routers/auditoria.py`:

```python
from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import AuditoriaLogOut

router = APIRouter(prefix="/api/auditoria", tags=["auditoria"])


@router.get("", response_model=list[AuditoriaLogOut])
def listar(
    entidad: Optional[str] = None,
    entidad_id: Optional[int] = None,
    usuario_id: Optional[int] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[models.AuditoriaLog]:
    q = db.query(models.AuditoriaLog)
    if entidad is not None:
        q = q.filter(models.AuditoriaLog.entidad == entidad)
    if entidad_id is not None:
        q = q.filter(models.AuditoriaLog.entidad_id == entidad_id)
    if usuario_id is not None:
        q = q.filter(models.AuditoriaLog.usuario_id == usuario_id)
    if desde is not None:
        q = q.filter(models.AuditoriaLog.fecha_hora >= datetime.combine(desde, time.min))
    if hasta is not None:
        q = q.filter(models.AuditoriaLog.fecha_hora <= datetime.combine(hasta, time.max))
    return q.order_by(models.AuditoriaLog.id.desc()).limit(limit).all()
```

- [ ] **Step 4: Register the router (protegido)**

En `backend/app/main.py`, junto a los otros routers internos, añade (con la dependencia de auth):

```python
from app.routers import auditoria
app.include_router(auditoria.router, dependencies=[Depends(get_current_user)])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_auditoria_endpoint.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/auditoria.py backend/app/main.py backend/tests/test_auditoria_endpoint.py
git commit -m "feat: endpoint GET /api/auditoria (consulta filtrable del log)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 7: CLI `crear_usuario`

**Files:**
- Create: `backend/app/crear_usuario.py`
- Test: `backend/tests/test_crear_usuario.py`

- [ ] **Step 1: Write the failing test**

Crear `backend/tests/test_crear_usuario.py`:

```python
import pytest

from app import crear_usuario, models, seguridad


def test_crear_usuario_persiste_hash(db_session):
    u = crear_usuario.crear_usuario(db_session, "ramon", "secreto", nombre="Ramón", rol="admin")
    assert u.id is not None
    assert u.username == "ramon" and u.nombre == "Ramón" and u.rol == "admin" and u.activo is True
    assert u.password_hash != "secreto"
    assert seguridad.verify_password("secreto", u.password_hash) is True


def test_crear_usuario_duplicado_falla(db_session):
    crear_usuario.crear_usuario(db_session, "ramon", "secreto")
    with pytest.raises(crear_usuario.UsuarioYaExiste):
        crear_usuario.crear_usuario(db_session, "ramon", "otra")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_crear_usuario.py -q`
Expected: FAIL (`No module named 'app.crear_usuario'`).

- [ ] **Step 3: Create the module + CLI**

Crear `backend/app/crear_usuario.py`:

```python
from __future__ import annotations

import argparse
import getpass
import sys
from datetime import date

from sqlalchemy.orm import Session

from app import models, seguridad
from app.db import SessionLocal


class UsuarioYaExiste(Exception):
    pass


def crear_usuario(db: Session, username: str, password: str, *, nombre: str | None = None,
                  rol: str = "admin") -> models.Usuario:
    if db.query(models.Usuario).filter(models.Usuario.username == username).first() is not None:
        raise UsuarioYaExiste(f"El usuario '{username}' ya existe")
    u = models.Usuario(
        username=username, nombre=nombre or username,
        password_hash=seguridad.hash_password(password),
        activo=True, rol=rol, fecha_alta=date.today(),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crea un usuario en la BD de 6TL Postventa.")
    parser.add_argument("username")
    parser.add_argument("--nombre", default=None)
    parser.add_argument("--rol", default="admin")
    args = parser.parse_args(argv)

    password = getpass.getpass("Contraseña: ")
    if not password:
        print("Contraseña vacía; abortado.", file=sys.stderr)
        return 2
    db = SessionLocal()
    try:
        u = crear_usuario(db, args.username, password, nombre=args.nombre, rol=args.rol)
    except UsuarioYaExiste as e:
        print(str(e), file=sys.stderr)
        return 1
    finally:
        db.close()
    print(f"Usuario '{u.username}' creado (id={u.id}, rol={u.rol}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest tests/test_crear_usuario.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/crear_usuario.py backend/tests/test_crear_usuario.py
git commit -m "feat: CLI crear_usuario (bootstrap de usuarios)"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

---

## Task 8: Suite completa + smoke en vivo

**Files:** ninguno (verificación).

- [ ] **Step 1: Run the full suite**

Run: `cd "C:/Users/rllavall/6TL Postventa/backend" && .venv/Scripts/python.exe -m pytest -q -p no:warnings`
Expected: PASS, todo verde (166 previos + ~32 nuevos).

- [ ] **Step 2: Smoke en vivo**

Arranca el backend (crea `usuarios`/`sesiones`/`auditoria`):
```
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```
En otra shell:
1. Crea un usuario: `.venv\Scripts\python.exe -m app.crear_usuario ramon --nombre Ramon` (teclea una contraseña).
2. Endpoint interno sin token → 401:
   `curl -s -o NUL -w "%{http_code}\n" http://127.0.0.1:8020/api/equipos`  → `401`
3. Login:
   `curl -s -X POST http://127.0.0.1:8020/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"ramon\",\"password\":\"<la-tuya>\"}"` → `{ "token": "...", "usuario": {...} }`
4. Con el token, endpoint interno → 200:
   `curl -s -o NUL -w "%{http_code}\n" http://127.0.0.1:8020/api/equipos -H "Authorization: Bearer <token>"` → `200`
5. Audita: crea algo y consulta `GET /api/auditoria?entidad=...` con el token; debe verse la fila con `usuario_username=ramon`.

- [ ] **Step 3: Parar el backend**

`netstat -ano | findstr :8020` → `taskkill /PID <pid> /T /F`.

- [ ] **Step 4: Commit (solo si hubo ajustes)**

Si todo verde sin cambios, no hay commit.

---

## Task 9: Prompt Lovable 19 (login + historial por ficha)

**Files:**
- Create: `docs/lovable/19_auth_auditoria.md`
- Modify: `docs/lovable/README.md`

- [ ] **Step 1: Write the Lovable prompt**

Crear `docs/lovable/19_auth_auditoria.md`:

```markdown
# Prompt 19 — Login + historial de auditoría por ficha

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()`, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`). NO cambies nombres de campo.

## 1. Tipos en `src/lib/types.ts`
- `interface Usuario { id:number; username:string; nombre:string; rol:string; activo:boolean }`
- `interface AuditoriaLog { id:number; fecha_hora:string; usuario_id:number|null;
  usuario_username:string; entidad:string; entidad_id:number; accion:"alta"|"edicion"|"borrado";
  cambios:string|null }`  // `cambios` es un JSON string `{campo:[antes,despues]}`

## 2. Autenticación
- El helper `api()` debe inyectar la cabecera `Authorization: Bearer <token>` leyendo el token de
  `localStorage` (clave `token`). Si una respuesta es **401**, borra el token y redirige a `/login`.
- Página **pública** `/login` SIN el shell/menú interno: formulario usuario + contraseña →
  `POST /api/auth/login {username,password}`. Al 200 guarda `token` en localStorage y el usuario,
  redirige a la home. Muestra error en 401.
- En la cabecera de la app (zona interna): el `nombre` del usuario actual (`GET /api/auth/me`) y un
  botón **Salir** → `POST /api/auth/logout` (con el Bearer) → borra token → `/login`.
- Protege las rutas internas: si no hay token, redirige a `/login`.
- El formulario público de solicitud de soporte (`/solicitud`, si existe) **NO** debe requerir token.

## 3. Historial de cambios por ficha
- En las fichas de **equipo**, **incidencia** y **cliente**, añade una sección/acordeón "Historial de
  cambios" que llame `GET /api/auditoria?entidad=<tabla>&entidad_id=<id>` (entidad = `equipos`,
  `incidencias`, `clientes`).
- Muestra cada entrada como una línea de timeline: fecha-hora, `usuario_username`, `accion`
  (badge: alta=verde, edicion=ámbar, borrado=rojo) y, parseando `cambios` (JSON), la lista de campos
  cambiados `campo: antes → después` (en alta, "creado con …"; en borrado, "eliminado").

Usa EXACTAMENTE los nombres de campo de arriba; no inventes endpoints.
```

- [ ] **Step 2: Update README índice**

En `docs/lovable/README.md`, añade (en la sección que corresponda):
```markdown
| 19 | `19_auth_auditoria.md` | **Login + auditoría**: página pública `/login` + Bearer token en `api()` + logout/usuario en cabecera + sección "Historial de cambios" por ficha (`GET /api/auditoria`). Backend: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `GET /api/auditoria`. |
```

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/19_auth_auditoria.md docs/lovable/README.md
git commit -m "docs: prompt Lovable 19 — login + historial de auditoria"
```
(Mensaje termina con la línea Co-Authored-By habitual.)

- [ ] **Step 4: (Manual, fuera del plan)** Pegar el prompt 19 en Lovable; `git pull` del submódulo,
  `bun install`, `bun x tsc --noEmit`, smoke. Crear el primer usuario con el CLI antes de probar.

---

## Self-review (cobertura del spec)

- **`Usuario`/`Sesion`/`AuditoriaLog` con sus campos:** Tasks 2 y 5. ✅
- **Hashing stdlib (pbkdf2), verify constante, malformado→False:** Task 1. ✅
- **`auth_service` (autenticar/crear_sesion/validar_token/cerrar_sesion + excepciones):** Task 2. ✅
- **Token 7 días configurable (`AUTH_SESION_DIAS`):** Task 2 (`_dias_sesion`). ✅
- **Router auth login/logout/me + `get_current_user` que sella `db.info`:** Task 3. ✅
- **Protección de los 12 routers internos; público health/login/docs; compat 166 tests:** Task 4. ✅
- **Captura automática alta/edición/borrado con diff, usuario de `db.info`, exclusión `Sesion`/`AuditoriaLog`, redacción de sensibles, sin-usuario→"sistema":** Task 5. ✅
- **Auditoría atómica (core insert en la misma transacción):** Task 5 (`_emitir`). ✅
- **Consulta `GET /api/auditoria` con filtros + orden desc + límite:** Task 6. ✅
- **CLI bootstrap de usuarios:** Task 7. ✅
- **Frontend: login público, Bearer en api(), logout/usuario, solicitud pública sin token, historial por ficha:** Task 9 (prompt). ✅
- **Fuera de alcance (roles efectivos, UI usuarios, pantalla global, reset, rate-limit, 2FA):** no implementado. ✅
- **Nota de integración con la rama Solicitud (POST público + endpoints internos):** documentada en el header. ✅

Consistencia de tipos: `Usuario`/`Sesion`/`AuditoriaLog` (modelos), `UsuarioOut`/`LoginPayload`/`LoginOut`/
`AuditoriaLogOut` (schemas), `seguridad.hash_password`/`verify_password`, `auth_service.*` +
`CredencialesInvalidas`/`SesionInvalida`, `deps.get_current_user`, `auditoria.registrar_listeners`,
`crear_usuario.crear_usuario`/`UsuarioYaExiste` — usados igual en todas las tareas y el prompt.
```
