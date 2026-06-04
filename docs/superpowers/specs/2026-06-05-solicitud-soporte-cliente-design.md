# Solicitud de soporte del cliente (formulario público) — Diseño

**Fecha:** 2026-06-05
**Proyecto:** 6TL Postventa ("6tlservice")
**Estado:** diseño aprobado en brainstorming, pendiente de spec review + plan

## Problema / objetivo

Permitir que un **cliente** genere directamente una **solicitud de soporte** desde un formulario
público (accesible por link, sin login, no incrustado en la app interna). La solicitud NO es todavía
una incidencia: un **técnico la revisa y la aprueba** (→ se crea la incidencia) o la rechaza. Al entrar
una solicitud, se envía un **aviso por correo a support@6tlengineering.com**.

## Decisiones (brainstorming)

- **Campos del cliente** (no se expone la base instalada interna): datos de contacto + identificación
  del equipo por **texto** + problema. El **técnico** fija tipo/prioridad/equipo real al aprobar.
- **Correo:** SMTP propio de 6tlengineering, credenciales en variables de entorno; envío **best-effort**
  (si falla, NO bloquea la creación de la solicitud); transporte **inyectable** para tests. From=To=
  `support@6tlengineering.com` (configurable por env, default support@).
- **Aprobar:** el técnico mapea la solicitud a un Equipo real, fija tipo/prioridad/asignado y se **crea
  la Incidencia** (reusa `generar_codigo`); la solicitud queda `aprobada` enlazada a la incidencia.
  Rechazar guarda `motivo`.
- **Formulario público:** página independiente **sin la navegación interna**. URL provisional
  `/solicitud` (el usuario decide la ruta definitiva al pegar el prompt).

## Modelo de datos

Nueva entidad `SolicitudSoporte` (tabla `solicitudes_soporte`, la crea `Base.metadata.create_all` —
es tabla nueva, no requiere migración de columnas):
- `id: int` PK
- `codigo: str` (`SOL-NNNN`, secuencial)
- `estado: str` (`pendiente | aprobada | rechazada`, default `pendiente`)
- `fecha_solicitud: date`
- `nombre_contacto: str`, `empresa: Optional[str]`, `email_contacto: str`, `telefono_contacto: Optional[str]`
- `numero_serie_texto: Optional[str]`, `part_number_texto: Optional[str]` (lo que el cliente escribe)
- `titulo: str`, `descripcion_problema: str`
- `incidencia_id: Optional[int]` FK → `incidencias.id` (se rellena al aprobar)
- `motivo_rechazo: Optional[str]`
- `fecha_resolucion: Optional[date]` (fecha de aprobación o rechazo)

## API

### Público (sin auth)
- `POST /api/solicitudes` body `SolicitudCreate`:
  - Campos: `nombre_contacto`, `empresa?`, `email_contacto`, `telefono_contacto?`,
    `numero_serie_texto?`, `part_number_texto?`, `titulo`, `descripcion_problema`, `website?` (honeypot).
  - Validación: `email_contacto` formato email; `titulo`/`descripcion_problema`/`nombre_contacto`
    no vacíos; **honeypot** `website` debe venir vacío (si trae valor → 400, descarta como bot).
  - Crea la solicitud (estado `pendiente`, `codigo` `SOL-NNNN`, `fecha_solicitud` = hoy) y **dispara el
    aviso por correo** (best-effort). Responde 201 `SolicitudOut` (incluye `codigo`).

### Interno
- `GET /api/solicitudes?estado=` → `list[SolicitudOut]` (orden desc por id). `GET /api/solicitudes/{id}`.
- `POST /api/solicitudes/{id}/aprobar` body `{equipo_id?, componente_id?, tipo, prioridad,
  asignado_a?, en_garantia?}`:
  - 409 si la solicitud no está `pendiente`. Requiere `equipo_id` o `componente_id` (≥1) — valida que
    existan (404). Crea la `Incidencia` (`generar_codigo(db, tipo)`, estado `abierta`, copia `titulo`
    y `descripcion_problema` de la solicitud, `fecha_apertura` = hoy, en RMA autodetecta `en_garantia`
    como el alta normal salvo override). Marca la solicitud `aprobada`, `incidencia_id`, `fecha_resolucion`.
    Devuelve la `IncidenciaOut` creada.
- `POST /api/solicitudes/{id}/rechazar` body `{motivo}` → estado `rechazada`, `motivo_rechazo`,
  `fecha_resolucion`. 409 si no está `pendiente`.

### Schemas (`app/schemas.py`)
`SolicitudCreate` (campos públicos + honeypot), `SolicitudOut` (todos menos honeypot),
`AprobarSolicitudPayload {equipo_id?, componente_id?, tipo, prioridad, asignado_a?, en_garantia?}`
(reusa los mismos Literales de tipo `rma|soporte_venta|soporte_tecnico|calibracion` y prioridad
`baja|media|alta` que `IncidenciaCreate`), `RechazarSolicitudPayload {motivo: str}`.

## Módulo de correo (`app/email_notify.py`)

- Config desde entorno: `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`,
  `SMTP_FROM` (default `support@6tlengineering.com`), `SOPORTE_EMAIL_TO` (default `support@6tlengineering.com`).
- `enviar_aviso_solicitud(solicitud, transporte=None) -> bool`: construye asunto
  (`Nueva solicitud de soporte {codigo}`) y cuerpo (contacto + equipo texto + título + descripción),
  y envía. `transporte` inyectable (un callable que recibe el mensaje); por defecto usa `smtplib.SMTP`.
  **Best-effort:** captura cualquier excepción, la loguea y devuelve `False` (no relanza). Si falta
  configuración SMTP, no intenta enviar y devuelve `False` (la solicitud se crea igual).
- El router `POST /api/solicitudes` llama a esta función tras `commit`; ignora el resultado para la
  respuesta (el alta no depende del correo).

## Frontend (Lovable, prompt 18)

- **Página pública** (URL provisional `/solicitud`) renderizada **sin la navegación interna** (no
  muestra el shell/menú de la app): formulario con contacto (nombre, empresa, email, teléfono),
  equipo por texto (nº de serie, PN), título, descripción, + campo honeypot oculto `website`. Envía
  `POST /api/solicitudes`. Tras 201 → pantalla de agradecimiento con el `codigo`. Maneja 400 (validación).
- **Pantalla interna** `/solicitudes`: lista con filtro por `estado` (badge pendiente/aprobada/rechazada),
  detalle con los datos del cliente; **Aprobar** abre un modal donde el técnico mapea el Equipo real
  (selector de la base instalada) + tipo + prioridad + asignado → `POST .../aprobar` (crea la incidencia,
  navega/enlaza a ella); **Rechazar** pide motivo → `POST .../rechazar`. Entrada en el menú interno.
- Tipos en `types.ts`: `SolicitudSoporte`, `SolicitudEstado`.

## Testing (TDD)

- `POST /api/solicitudes`: crea (201, código `SOL-NNNN`, estado pendiente); honeypot con valor → 400;
  email inválido / campos vacíos → 422/400.
- **Correo:** con transporte inyectable, `enviar_aviso_solicitud` produce el mensaje esperado; un fallo
  del transporte NO rompe el `POST /api/solicitudes` (la solicitud se crea igual). Sin config SMTP →
  no envía, devuelve False, alta OK.
- `GET /api/solicitudes` + filtro estado. `aprobar`: crea incidencia (código por tipo), enlaza
  `incidencia_id`, estado→aprobada; 409 si ya no está pendiente; 404 equipo inexistente; requiere sujeto.
  `rechazar`: estado→rechazada + motivo; 409 si no pendiente.

## Fuera de alcance (YAGNI)

- Auth / rate-limiting del endpoint público (más allá del honeypot).
- Email de confirmación al cliente; captcha; adjuntar ficheros.
- Decidir la URL pública definitiva (se ajusta al pegar el prompt).
