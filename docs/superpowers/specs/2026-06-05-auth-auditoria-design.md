# Autenticación + auditoría interna — Design

**Fecha:** 2026-06-05
**Estado:** aprobado, pendiente de plan de implementación.

## Objetivo

Dar a la app postventa (6TL Postventa / "6tlservice") un **login simple** para usuarios internos y una
**trazabilidad interna completa**: un log de auditoría que registre quién da de alta, edita o borra cada
dato, con el detalle de qué cambió. Se deja el hueco para **permisos por rol en el futuro** sin
implementarlos todavía.

Alcance elegido en brainstorming:
- **Auth:** login simple (usuario/contraseña + token de sesión en cabecera `Bearer`). Sin roles efectivos.
- **Auditoría:** log completo (tabla aparte) con **acción + diff de campos**, capturado automáticamente.
- **Bootstrap:** comando CLI para crear usuarios.
- **Visualización:** API + historial embebido por ficha (sin pantalla global todavía).

## No objetivos (YAGNI — anotados para el futuro)

Roles/permisos efectivos (solo se reserva la columna `rol`), UI de gestión de usuarios, pantalla global
`/auditoria`, reset de contraseña, rate-limiting/bloqueo por intentos fallidos, 2FA, refresco/expiración
deslizante del token.

## Contexto del código (estado actual)

- Backend FastAPI + SQLAlchemy 2 (`Mapped`) + SQLite, corre en **:8020**. `app/db.py` define `Base`,
  `engine`, `SessionLocal` y la dependencia `get_db`. `app/main.py` hace `create_all` + `add_missing_columns`
  (migraciones idempotentes de columnas) y registra ~13 routers; CORS `allow_origins=["*"]`,
  `allow_credentials=False` (encaja con token en cabecera, no cookies).
- Ninguna entidad tiene hoy autoría. Existen campos de **texto libre** sueltos (`Movimiento.usuario`,
  `CambioConfiguracion.usuario`, `AvanceIncidencia.autor`, `Incidencia.asignado_a`) que **no se tocan** en
  esta entrega (siguen siendo texto libre; no se vinculan a `Usuario` por ahora).
- Tests en `backend/tests/` con fixtures `db_session`/`client` (motor SQLite en memoria; `client`
  sobreescribe `get_db`). Hay **177 tests** verdes que llaman a los endpoints **sin autenticación**.
- Filosofía del proyecto: **mínimas dependencias** (p.ej. se validó email con regex en vez de instalar
  `email-validator`). Auth y hashing se hacen con la **librería estándar** (`hashlib`, `secrets`), sin
  `passlib`/`jwt`.

---

## Arquitectura

Tres piezas nuevas, todas aditivas (tablas nuevas creadas por `create_all`; **no** se añaden columnas a
tablas existentes, así que `migrations.py` no cambia):

1. **Auth** — modelo `Usuario` + `Sesion`, módulo `seguridad.py` (hash/verify), router `auth.py`
   (login/logout/me) y dependencia `get_current_user`.
2. **Auditoría** — modelo `AuditoriaLog`, módulo `auditoria.py` (listener de sesión SQLAlchemy que captura
   alta/edición/borrado con diff), router `auditoria.py` (consulta).
3. **Bootstrap** — comando `python -m app.crear_usuario`.

### 1. Modelos

**`Usuario`** (tabla `usuarios`):

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | int PK | |
| `username` | str **único** | identificador de login |
| `nombre` | str | nombre para mostrar |
| `password_hash` | str | formato `pbkdf2_sha256$iter$salt$hash` |
| `activo` | bool, def. `True` | login bloqueado si `False` |
| `rol` | str, def. `"admin"` | **reservado**, sin efecto en esta entrega |
| `fecha_alta` | date | |

**`Sesion`** (tabla `sesiones`):

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | int PK | |
| `token` | str **único, indexado** | opaco, `secrets.token_urlsafe(32)` |
| `usuario_id` | int FK → `usuarios.id` | |
| `fecha_creacion` | datetime | |
| `fecha_expiracion` | datetime | fija; `creacion + AUTH_SESION_DIAS` (def. 7) |

**`AuditoriaLog`** (tabla `auditoria`):

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | int PK | |
| `fecha_hora` | datetime | momento del cambio |
| `usuario_id` | int FK, **nullable** | null si lo hizo el sistema/público |
| `usuario_username` | str | **desnormalizado** (sobrevive al borrado del usuario); `"sistema"`/`"público"` si no hay usuario |
| `entidad` | str | nombre de tabla, p.ej. `"equipos"` |
| `entidad_id` | int | PK de la fila afectada |
| `accion` | str | `"alta"` / `"edicion"` / `"borrado"` |
| `cambios` | str (TEXT, JSON) | `{"campo": [antes, después], ...}`; en alta = todos los campos a su valor; en borrado = snapshot |

### 2. `seguridad.py` (hashing sin dependencias)

- `hash_password(pw: str) -> str`: genera salt aleatorio (`secrets`), deriva con
  `hashlib.pbkdf2_hmac("sha256", pw, salt, ITERACIONES)`, devuelve el string autocontenido
  `pbkdf2_sha256$<iter>$<salt_hex>$<hash_hex>`.
- `verify_password(pw: str, almacenado: str) -> bool`: parsea el string, recalcula y compara en tiempo
  constante (`hmac.compare_digest`). Devuelve `False` ante formato inválido (no lanza).
- `ITERACIONES` constante (p.ej. 200_000), parametrizada en el string para poder subirla en el futuro.

### 3. Auth: router + dependencia

- `app/auth_service.py` (lógica pura, testeable sin HTTP): `autenticar(db, username, password) -> Usuario`
  (lanza `CredencialesInvalidas` si no existe / password mal / inactivo), `crear_sesion(db, usuario) -> Sesion`,
  `validar_token(db, token) -> Usuario` (lanza `SesionInvalida` si no existe / expiró / usuario inactivo),
  `cerrar_sesion(db, token)`.
- `app/routers/auth.py` (`prefix="/api/auth"`):
  - `POST /login` `{username, password}` → `200 {token, usuario:{id,username,nombre,rol}}`; `401` si credenciales
    inválidas o usuario inactivo.
  - `POST /logout` (requiere token) → `204`; borra la sesión.
  - `GET /me` (requiere token) → el usuario actual.
- **Dependencia `get_current_user`** (en `app/deps.py`):
  - Lee la cabecera `Authorization: Bearer <token>` (falta/!"Bearer" → `401`), llama `validar_token`,
    y **sella el usuario en la sesión de BD**: `db.info["usuario_id"]` y `db.info["usuario_username"]`
    (para que el listener de auditoría lo lea). Devuelve el `Usuario`. La sesión de BD es la **misma**
    que usará el endpoint (FastAPI cachea `Depends(get_db)` dentro de una petición).

### 4. Protección de endpoints

- Los **12 routers internos** se registran con `app.include_router(x.router, dependencies=[Depends(get_current_user)])`.
- **Públicos (sin auth):** `POST /api/solicitudes` (formulario del cliente), `GET /api/health`,
  `POST /api/auth/login`, y `/docs` + `/openapi.json`. El router `solicitudes` es **mixto**: el `POST` queda
  público; sus endpoints internos (`GET` lista, `GET /{id}`, y los futuros `aprobar`/`rechazar`) llevan
  `Depends(get_current_user)` por-endpoint.
- **Compatibilidad de tests:** el fixture `client` de `conftest.py` añade
  `app.dependency_overrides[get_current_user]` devolviendo un **usuario de prueba** y sellando `db.info`,
  de modo que los **177 tests existentes pasan sin cambios**. Los tests de auth nuevos usan un cliente
  **sin** ese override (flujo real de login/token).

### 5. Auditoría: captura automática

- `app/auditoria.py` registra un listener `before_flush` (+ `after_flush` para los PK de las altas) sobre
  `SessionLocal`/`Session`:
  - Recorre `session.new` (→ `alta`), `session.dirty` con cambios reales (→ `edicion`,
    vía `inspect(obj).attrs[...].history.has_changes()`), `session.deleted` (→ `borrado`).
  - Calcula `cambios` desde el historial de atributos del ORM (antes→después).
  - Lee el usuario de `session.info` (si falta → `usuario_id=None`, `usuario_username="sistema"`; en el alta
    pública de solicitud → `"público"`).
  - Escribe las filas `AuditoriaLog` **en la misma transacción**.
  - **Exclusiones:** no audita `AuditoriaLog` (anti-recursión) ni `Sesion` (ruido de login/logout).
    **Redacta** valores de campos sensibles (`password_hash`, `token`) en el diff (se registra que cambiaron,
    no el valor).
- El listener se engancha una vez al importar el módulo (cableado en `main.py` y en el motor de tests).

### 6. Auditoría: consulta

- `app/routers/auditoria.py`: `GET /api/auditoria?entidad=&entidad_id=&usuario_id=&desde=&hasta=&limit=`
  (interno, requiere auth) → lista de `AuditoriaLogOut`, **más reciente primero**, `limit` por defecto
  razonable (p.ej. 200). Pensado para el historial por ficha: `?entidad=equipos&entidad_id=7`.

### 7. Bootstrap CLI

- `python -m app.crear_usuario <username> [--nombre N] [--rol admin]`: pide la contraseña por consola
  (oculta, `getpass`), la hashea con `seguridad.hash_password`, crea el `Usuario` en la BD real
  (`postventa.db`). Sirve para el primer admin y para usuarios posteriores mientras no haya UI de gestión.
  Falla limpio si el `username` ya existe.

### 8. Frontend (prompt Lovable — fuera del backend)

- **Login** en página pública sin shell; guarda el token en `localStorage`; el helper `api()` inyecta
  `Authorization: Bearer`; un `401` limpia el token y redirige a login; cabecera muestra el usuario actual
  + botón **logout** (`POST /api/auth/logout`).
- El formulario público `/solicitud` **no** requiere token (no manda cabecera o tolera su ausencia).
- **Historial de cambios por ficha:** sección que llama `GET /api/auditoria?entidad=...&entidad_id=...`
  en las fichas de equipo, incidencia y cliente, mostrando acción + usuario + fecha + campos cambiados.

---

## Flujo de datos

1. Usuario hace `POST /api/auth/login` → recibe `token`. El front lo guarda y lo manda en cada petición.
2. En cada petición interna, `get_current_user` valida el token y sella el usuario en `db.info`.
3. El endpoint hace su trabajo (alta/edición/borrado de entidades) sobre **la misma** sesión de BD.
4. Al hacer flush/commit, el listener de auditoría lee `db.info`, calcula el diff y escribe filas
   `AuditoriaLog` en la misma transacción.
5. El front pinta el historial de una ficha consultando `GET /api/auditoria`.

## Manejo de errores

- Login: credenciales inválidas / usuario inactivo → `401` (mensaje genérico, sin revelar cuál falló).
- Token ausente/!Bearer/expirado/inválido en endpoint protegido → `401`.
- `verify_password` ante hash malformado → `False` (no lanza).
- La auditoría es **atómica con el cambio**: la fila `AuditoriaLog` se escribe en la **misma transacción**
  que la operación de negocio, a propósito (no debe existir un cambio sin su rastro). El "tolerar la
  ausencia de usuario" solo aplica a **determinar quién** lo hizo: si `db.info` no trae usuario, se registra
  `"sistema"`/`"público"` en vez de fallar. Un error real del propio listener es un bug que debe propagarse
  (y por tanto hace rollback del conjunto), no silenciarse.

## Pruebas (qué cubrir)

- `seguridad`: hash distinto por salt; verify ok/ko; hash malformado → `False`.
- `auth_service`/router: login ok devuelve token + usuario; password mala → 401; usuario inactivo → 401;
  `me` con token ok / sin token 401; logout invalida el token; token expirado → 401.
- Protección: un endpoint interno (p.ej. `GET /api/equipos`) **sin** token → 401; **con** token → 200;
  `POST /api/solicitudes` **sin** token sigue → 201 (público).
- Auditoría: un alta/edición/borrado de una entidad crea fila(s) `AuditoriaLog` con `entidad`/`entidad_id`/
  `accion` correctos, `usuario_username` del usuario logueado, y `cambios` con el diff esperado; edición
  sin cambios reales no genera fila; `password_hash`/`token` redactados; `Sesion`/`AuditoriaLog` excluidas;
  contexto sin usuario → `"sistema"`/`"público"`.
- Consulta `GET /api/auditoria`: filtros por entidad/entidad_id/usuario/fechas; orden desc; límite.
- CLI `crear_usuario`: crea el usuario; username duplicado falla limpio.
- **Regresión:** los 177 tests previos siguen verdes gracias al override de `get_current_user` en `conftest`.

## Migración / despliegue

- Tablas nuevas (`usuarios`, `sesiones`, `auditoria`) creadas por `create_all` al arrancar. Sin cambios en
  `migrations.py`.
- Al activar la auth, el backend exige token en los endpoints internos → el frontend Lovable debe llevar
  ya el login (coordinación de despliegue). El formulario público y `/api/health` siguen accesibles.
- Crear el primer usuario con el CLI antes de usar la app.
