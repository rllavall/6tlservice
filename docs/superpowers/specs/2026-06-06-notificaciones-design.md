# Diseño — Notificaciones (email / Telegram)

Fecha: 2026-06-06 · Proyecto: 6TL Postventa ("6tlservice") · Backend FastAPI :8020.

> Diseñado e implementado de forma autónoma (usuario ausente, autorización explícita). Decisiones por defecto
> marcadas; todo es best-effort y desactivable (canales no configurados = no-op).

## Contexto

Sub-proyecto **2 de 3** (último) del clúster de servicio, tras #1 (preventivo+avisos) y #3 (SLA). Entrega los
eventos que ya producen #1 y #3 (preventivos vencidos, contratos por caducar, SLA en riesgo/incumplido) y los
cambios de estado de incidencia, por **email** y/o **Telegram**.

## Decisiones de diseño

- **Sin dependencias nuevas:** email vía `smtplib` (ya usado por `app/email_notify.py`), Telegram vía
  `urllib.request` (stdlib) a la Bot API. Reutiliza `email_notify._config()` / `_enviar_smtp`.
- **Best-effort siempre:** ningún envío relanza ni rompe el flujo. Canal sin configurar (faltan variables de
  entorno) → se omite (`None`), no error.
- **Configuración por entorno:** `NOTIF_EMAIL_TO` (lista separada por comas; por defecto `SOPORTE_EMAIL_TO`),
  SMTP_* (ya existentes), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- **Inyectable para tests:** los `*_fn`/transportes se pueden sustituir; los tests NO hacen red.
- **Dos disparadores:**
  1. **Digest (escaneo):** `POST /api/notificaciones/digest` — compone y envía un resumen del estado actual
     (avisos #1 + SLA #3). Pensado para un **disparo programado** (Windows Task Scheduler / cron) diario. No
     hay scheduler dentro de la app (sync FastAPI); el disparo es externo. Soporta `?dry_run=true` (preview
     sin enviar).
  2. **Evento de incidencia (inline):** al **transicionar** una incidencia, se envía un aviso best-effort
     (hook en el endpoint de transición, envuelto en try/except — nunca rompe la transición).
- **Sin persistencia de notificaciones** (YAGNI): no hay tabla/historial; el endpoint devuelve qué se intentó.
  (Un log de envíos sería una fase futura.)
- **NO se notifica creación de incidencia** en esta fase (solo cambios de estado); se puede añadir luego.

## Componentes (backend)

### `app/notificaciones.py` — canales (best-effort, inyectable)
- `enviar_email(asunto, cuerpo, *, transporte=None) -> Optional[bool]`: `None` si SMTP/destinatarios sin
  configurar; `True/False` según envío. Reutiliza `email_notify._config()` + `_enviar_smtp`.
- `enviar_telegram(texto, *, http_post=None) -> Optional[bool]`: `None` si falta token/chat_id; usa
  `_http_post_telegram(token, chat_id, texto)` (POST JSON a `api.telegram.org/bot{token}/sendMessage`).
- `notificar(asunto, cuerpo, *, email_fn=enviar_email, telegram_fn=enviar_telegram) -> dict`: dispara ambos
  canales; devuelve `{"email": True|False|None, "telegram": True|False|None}`.

### `app/notificaciones_service.py` — composición
- `construir_digest(db, hoy) -> {asunto, cuerpo, resumen, total}`: junta
  `avisos_service.construir_avisos` + `sla_service.construir_sla`; `resumen` = contadores
  (preventivos_vencidos/proximos, contratos_por_caducar, sla_en_riesgo, sla_incumplidas); `cuerpo` = texto
  legible con los contadores y un detalle breve (códigos de las incidencias SLA incumplidas y de los
  preventivos vencidos top). `total` = suma de contadores.
- `enviar_digest(db, hoy, *, notificar_fn=notificaciones.notificar) -> {asunto, resumen, total, canales}`.
- `mensaje_incidencia(inc, evento) -> (asunto, cuerpo)`.
- `notificar_incidencia(inc, evento, *, notificar_fn=notificaciones.notificar) -> dict`.

### Endpoint + hook
- `POST /api/notificaciones/digest?dry_run=false` (protegido) → `DigestOut`. `dry_run=true` compone y
  devuelve el cuerpo SIN enviar (`enviado=false`, `canales=null`).
- Hook en `app/routers/incidencias.py` (endpoint `transicion`): tras transicionar con éxito, llamar
  `notificaciones_service.notificar_incidencia(inc, nuevo_estado)` dentro de `try/except` (best-effort). Con
  canales sin configurar es no-op → no afecta a los tests existentes ni hace red.

## Schemas
```python
class DigestOut(BaseModel):
    asunto: str
    cuerpo: str
    resumen: dict
    total: int
    enviado: bool
    canales: Optional[dict] = None
```

## Frontend (Prompt Lovable 25)
- Pequeña pantalla/sección **Notificaciones** (admin): botón "Previsualizar resumen" (`POST
  /api/notificaciones/digest?dry_run=true` → muestra `cuerpo` + `resumen`) y botón "Enviar ahora"
  (`dry_run=false` → muestra `canales`). Nota de que el envío programado se configura fuera (Task Scheduler).
- Tipo `DigestOut` en `@/lib/types`.

## Testing (TDD)
- `test_notificaciones.py` (canales): `enviar_email` → `None` sin SMTP; `True` con `transporte` inyectado y
  env SMTP_HOST+NOTIF_EMAIL_TO (monkeypatch); `enviar_telegram` → `None` sin token; `True` con `http_post`
  inyectado y env token/chat; `notificar` devuelve dict con ambas claves; un transporte que lanza → `False`.
- `test_notificaciones_service.py`: `construir_digest` compone contadores desde datos (preventivo vencido +
  SLA incumplida); `notificar_incidencia` invoca `notificar_fn` con asunto/cuerpo que contienen el código;
  `enviar_digest` invoca `notificar_fn`.
- `test_notificaciones_api.py`: `dry_run=true` devuelve `cuerpo`/`resumen`, `enviado=false`, no envía;
  `dry_run=false` sin canales → `canales={email:None,telegram:None}`, `enviado=true` (no red); protegido → 401.
- Verificar que los tests de transición de incidencia existentes siguen verdes (hook best-effort no rompe).

## Riesgos / notas
- ⚠️ `urllib`/`smtplib` con canales configurados harían red real; los tests NUNCA configuran canales reales o
  inyectan transportes — sin red en CI.
- El digest es **pull** (disparo externo). Documentar en el prompt/README que el envío periódico se programa
  con Task Scheduler llamando al endpoint (con auth).
- Best-effort: si un canal falla, el otro sigue; la transición de incidencia nunca se rompe.
