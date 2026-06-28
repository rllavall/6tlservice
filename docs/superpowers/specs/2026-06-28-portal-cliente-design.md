# Portal de Cliente — Diseño

**Fecha:** 2026-06-28
**Estado:** Aprobado (brainstorming). Pendiente de plan de implementación.
**Autor:** Ramón + Claude (brainstorming).

## Objetivo

Dar a los clientes de 6TL un portal web autenticado para **consultar** su base
instalada, el estado de sus incidencias/RMA y sus contratos, y para **interactuar**
de forma muy acotada (abrir solicitudes de soporte, comentar incidencias, descargar
PDFs). La **seguridad y el aislamiento de datos entre clientes es el requisito
rector**: un cliente jamás puede ver ni tocar datos de otro, y la superficie pública
nunca da acceso a la app interna de 6TL.

## Decisiones de brainstorming (cerradas)

1. **Identidad:** usuario por **persona de contacto** (no por empresa), con **magic
   link en el primer acceso** y contraseña propia a partir de ahí.
2. **Alcance MVP:** (1) ver equipos, (2) ver incidencias/RMA, (3) ver contratos+SLA,
   (6) abrir solicitud de soporte autenticada, (7) comentar incidencia abierta,
   (8) descargar PDFs **generados al vuelo**. Adjuntos subidos = fase 2.
3. **Arquitectura:** opción B — **mismo backend/despliegue, sub-app `/portal` con
   identidad y endpoints dedicados**, que solo llaman a consultas *scoped-by-cliente*;
   nunca tocan los routers internos ni `get_current_user`.
4. **Hosting:** **on-prem 6TL** (Docker Compose + reverse proxy TLS + Postgres). El
   equipo interno accede a la app interna **solo desde oficina/VPN**; el reverse proxy
   solo expone a Internet `/portal` y `/api/portal`. Lo interno queda bloqueado desde fuera.
5. **Provisión:** **invite-only**. Un usuario interno otorga el acceso a contactos
   concretos de un cliente; nadie se auto-registra.
6. **Documentos MVP:** PDF generados al vuelo (expediente de incidencia, certificado de
   garantía). Adjuntos reales subidos = fase 2.
7. **2FA:** fuera del MVP; **TOTP en fase 2**. El MVP lleva cookie HttpOnly + rate-limit
   + invite-only + tokens hasheados de un solo uso.

## Principio de seguridad rector

El portal es una **superficie completamente separada** de la app interna: identidad
propia (`UsuarioCliente`, no `Usuario`), dependencia de auth propia (`get_cliente_actual`,
no `get_current_user`), y una capa de consultas que **exige `cliente_id` como argumento**.
El `cliente_id` **siempre** se deriva del usuario autenticado; **nunca** se acepta desde
el request. Un recurso que no pertenece al cliente → **404** (no confirmamos existencia).

## Modelo de datos (3 entidades nuevas)

```
UsuarioCliente
  id, cliente_id (FK Cliente, NOT NULL)        ← frontera dura de aislamiento
  email (único), nombre, cargo (opcional)
  password_hash (nullable hasta 1er acceso)
  activo (bool), fecha_alta, ultimo_acceso (nullable)
  invitado_por (FK Usuario interno, opcional), fecha_invitacion

TokenAccesoCliente                              ← magic link (alta y reset)
  id, usuario_cliente_id (FK)
  token_hash (NO el token en claro)
  proposito (alta | reset)
  fecha_expiracion (corta: 60 min), usado_en (nullable)

SesionCliente                                   ← sesión activa del portal
  id, usuario_cliente_id (FK)
  token_hash
  fecha_creacion, fecha_expiracion (~12 h + idle)
  ip_creacion, user_agent
```

Notas de diseño:
- **Tokens hasheados en BD** (sesión y magic link): si se lee la BD no hay tokens
  usables. El token en claro vive solo en el email/cookie del cliente. Reutiliza el
  patrón pbkdf2 de `app/seguridad.py` (o hash dedicado para tokens de alta entropía).
- **Identidades separadas** (`UsuarioCliente` ≠ `Usuario`): no comparten tabla, tokens
  ni dependencia. Un fallo en el portal no puede escalar a la app interna.
- **`SesionCliente` guarda IP/UA** para auditoría y detección de uso anómalo.
- Las invitaciones se **pre-rellenan** desde los contactos ya cargados de Salesforce
  (`Cliente.persona_contacto` / `email_contacto`).

## Autenticación y onboarding

### Alta (invite-only + magic link)
1. Usuario interno → ficha de Cliente → "Invitar al portal" (elige contacto prellenado
   o introduce email+nombre).
2. Backend crea `UsuarioCliente` (sin password) + `TokenAccesoCliente(proposito=alta,
   exp 60 min)`; envía email con `https://portal.../activar?token=<claro>` (en BD solo
   `token_hash`).
3. Cliente abre el enlace → si token válido y no usado → formulario "crea tu contraseña"
   → guarda `password_hash`, marca token `usado_en`.
4. En adelante: login email + contraseña.

### Login y sesión
- `POST /api/portal/auth/login` → valida → crea `SesionCliente` → fija cookie.
- **Token de sesión en cookie `HttpOnly` + `Secure` + `SameSite=Strict`** (no
  localStorage): un XSS no puede robar la sesión. (La app interna usa Bearer; el portal
  usa cookie por ser superficie pública.)
- Caducidad ~12 h + idle timeout (más corta que la interna). `POST /logout` borra sesión.
- `GET /api/portal/auth/me` → datos de usuario+cliente para la cabecera.

### Reset de contraseña
- `POST /api/portal/auth/reset` con email → **siempre 200** ("si existe, te enviamos un
  enlace"), nunca confirma existencia (anti-enumeración). Si existe → emite
  `TokenAccesoCliente(proposito=reset)`; mismo flujo de enlace.

### Endurecimiento (MVP)
| Riesgo | Mitigación |
|---|---|
| Fuerza bruta login | Rate-limit por IP y por cuenta + backoff; bloqueo temporal tras N intentos |
| Fuerza bruta magic link | `secrets.token_urlsafe(32)`, un solo uso, exp 60 min, hasheado |
| Enumeración de cuentas | Respuestas genéricas en login y reset |
| Robo de sesión | Cookie HttpOnly/Secure/SameSite=Strict; sesión corta; IP/UA registrados |
| Acceso de ex-empleado del cliente | Usuario interno revoca (`activo=false`) → invalida sesiones al instante |
| Abuso del endpoint público | Reverse proxy limita a `/portal` + `/api/portal`; rate-limit a nivel app |

(2FA TOTP: fase 2.)

## Endpoints del portal y aislamiento de datos

### Dependencia guardiana
`app/portal/deps.py::get_cliente_actual` → lee cookie de sesión, valida `SesionCliente`,
devuelve `UsuarioCliente`, y sella `db.info["portal_cliente_id"]` + un actor
`cliente:<email>` para auditoría. Todos los routers del portal se registran con
`dependencies=[Depends(get_cliente_actual)]`. **Ningún endpoint recibe `cliente_id` por
parámetro.**

### Capa de consultas scoped (módulo puro, testeable)
`app/portal/consultas.py` — toda función **obliga** a pasar `cliente_id`:
```
equipos_de(db, cliente_id) -> list[Equipo]
equipo_de(db, cliente_id, equipo_id) -> Equipo | None        # None si no es suyo → 404
incidencias_de(db, cliente_id, ...) -> list[Incidencia]
incidencia_de(db, cliente_id, incidencia_id) -> Incidencia | None
contratos_de(db, cliente_id) -> list[Contrato]
```
Una incidencia es "del cliente" si su equipo/componente pertenece a ese `cliente_id`.

### Endpoints (prefijo `/api/portal`, todos scoped)
| Método | Ruta | Devuelve (filtrado al cliente) |
|---|---|---|
| GET | `/equipos` | Base instalada: serie, modelo, ubicación, estado, garantía |
| GET | `/equipos/{id}` | Ficha (404 si no es suyo) |
| GET | `/incidencias` | RMA/incidencias con estado en vivo |
| GET | `/incidencias/{id}` | Expediente recortado: estado, fechas, bitácora filtrada |
| POST | `/incidencias/{id}/comentarios` | (P7) entrada de bitácora `tipo='cliente'` |
| GET | `/contratos` | Contratos + nivel + SLA |
| POST | `/solicitudes` | (P6) solicitud autenticada, prellenada con sus equipos |
| GET | `/documentos/incidencia/{id}.pdf` | (P8) PDF del expediente al vuelo (404 si ajeno) |
| GET | `/documentos/garantia/{equipo_id}.pdf` | (P8) certificado de garantía generado |

### Decisiones de exposición de datos
1. **Vistas recortadas, no los `*Out` internos.** Schemas propios (`EquipoPortalOut`,
   `IncidenciaPortalOut`, …) con **lista blanca explícita** de campos. Se **omiten**
   campos internos: coste, márgenes, notas internas, diagnóstico técnico crudo,
   asignación de técnico, etc. No se reutiliza `EquipoOut`/`IncidenciaFicha` para no
   filtrar campos por accidente.
2. **Bitácora filtrada por visibilidad.** Nueva columna
   `AvanceIncidencia.visible_cliente` (bool, default `False`): el técnico decide qué
   avance se comparte. El portal solo sirve `visible_cliente=True`. Los comentarios que
   escribe el cliente (P7) entran como `tipo='cliente'`, `visible_cliente=True`, y los
   ve el técnico en la app interna.

### Límites del comentario de cliente (P7)
Solo si la incidencia está **abierta/en curso** (no cerrada). El cliente puede comentar
pero **no** cambiar estado, prioridad ni ningún otro campo. Es una entrada de bitácora,
nada más.

## Frontend

- **App/entrada separada** servida bajo `portal.6tl...`, **sin ninguna ruta ni
  componente de la app interna** (ni por error de routing un cliente cae en pantallas
  internas). Mismo stack (TanStack Start / Lovable) y reutiliza el design system.
- Rutas: `/login`, `/activar?token=`, `/reset`, y shell autenticado: `/` (mis equipos),
  `/equipos/$id`, `/incidencias`, `/incidencias/$id` (comentar + descargar PDF),
  `/contratos`, `/solicitar`.
- Sesión vía **cookie HttpOnly** → el front no manipula el token; llamadas con
  `credentials: 'include'`. 401 → redirige a `/login`.
- Solo recibe los `*PortalOut` recortados; ningún campo interno viaja al navegador.

## Auditoría

- **Reutiliza el listener ORM existente** (`app/auditoria.py`). `get_cliente_actual`
  sella `db.info` con actor `cliente:<email>` → las escrituras del portal (comentarios,
  solicitudes) quedan auditadas y distinguibles de las internas.
- **Log de acceso del portal**: logins (ok/fallido), uso de magic link y resets, con
  IP/UA, para responder "¿quién accedió a los datos de este cliente y cuándo?".

## Estrategia de testing (TDD)

La seguridad se prueba, no se asume. Tests prioritarios:
1. **Aislamiento (críticos):** cliente A no ve equipo/incidencia/contrato/PDF de B → 404
   (un test por endpoint con id ajeno).
2. **Sin `cliente_id` inyectable:** ningún endpoint acepta `cliente_id` por
   parámetro/body (se ignora si se manda).
3. **Auth:** magic link de un solo uso; token caducado rechazado; login malo → genérico;
   reset no enumera; sesión revocada (`activo=false`) → 401 inmediato.
4. **Rate-limit:** N logins fallidos → bloqueo temporal.
5. **Vistas recortadas:** los `*PortalOut` no contienen campos internos (test de contrato
   sobre las claves del JSON).
6. **Bitácora:** solo `visible_cliente=True` se sirve; comentario de cliente entra con
   `tipo='cliente'` y lo ve el técnico en la app interna.
7. **Separación de identidades:** un token de `Sesion` interna no vale en `/api/portal`
   y viceversa.
8. **Protección de superficie:** cada endpoint del portal sin sesión → 401.

## Aprovechamiento de lo existente

Reutiliza: `app/seguridad.py` (hashing), patrón `auth_service`/`deps`, listener de
auditoría, modelos `Cliente`/`Equipo`/`Incidencia`/`Contrato`, datos Salesforce para
prellenar invitaciones. **Nuevo:** paquete `app/portal/` (deps, consultas scoped,
routers, schemas), 3 entidades, columna `AvanceIncidencia.visible_cliente`, generación
de PDF, app frontend separada.

## Fuera de alcance (fase 2+)

- Adjuntos subidos reales (certificados firmados, fotos, informes escaneados).
- TOTP / 2FA.
- Notificaciones al cliente por cambio de estado de sus RMA (encaja con el módulo de
  notificaciones ya existente; valorar en su momento).
- Avisos de obsolescencia/EOL en el portal (punto 5 del brainstorm, descartado del MVP).

## Dependencias / prerequisitos de infraestructura

- Migración a **PostgreSQL + Alembic** (hoy SQLite sin migraciones reales) y despliegue
  on-prem con reverse proxy TLS antes de exponer el portal a Internet. Ligado al audit
  de arquitectura previo (roles efectivos, `DATABASE_URL` por entorno, arranque en
  `lifespan`). El portal **no** debe salir a producción sobre la config de dev actual.
