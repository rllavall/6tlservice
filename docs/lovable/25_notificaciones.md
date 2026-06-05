# Prompt 25 — Notificaciones (digest de avisos)

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()` que ya inyecta el Bearer token, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`).
NO cambies nombres de campo. No inventes endpoints ni campos fuera de los listados aquí.

El sistema puede enviar un **resumen** (digest) de los avisos pendientes (preventivos vencidos/próximos,
contratos por caducar, SLA en riesgo/incumplido) por email y/o Telegram. El envío periódico se programa FUERA
de la app; esta pantalla permite **previsualizar** y **enviar ahora** manualmente.

## 1. Tipo en `src/lib/types.ts`
```ts
interface DigestOut {
  asunto: string;
  cuerpo: string;                              // texto plano (multilínea)
  resumen: Record<string, number>;            // {preventivos_vencidos, preventivos_proximos, contratos_por_caducar, sla_en_riesgo, sla_incumplidas}
  total: number;
  enviado: boolean;
  canales: Record<string, boolean | null> | null;  // {email: true|false|null, telegram: true|false|null}
}
```

## 2. Pantalla `/notificaciones` (admin, en el menú)
- **Botón "Previsualizar resumen"** → `POST /api/notificaciones/digest?dry_run=true`. Muestra:
  - Tarjetas con cada contador de `resumen` (etiquetas legibles: "Preventivos vencidos", "Preventivos
    próximos", "Contratos por caducar", "SLA en riesgo", "SLA incumplidas") y el `total`.
  - El `cuerpo` en un bloque `<pre>` (es el texto que se enviaría).
- **Botón "Enviar ahora"** → `POST /api/notificaciones/digest` (sin `dry_run`). Tras responder, muestra el
  resultado de `canales`: por cada canal (email, telegram) un badge:
    - `true` → "Enviado" (verde)
    - `false` → "Fallo" (rojo)
    - `null` → "No configurado" (gris)
  Si `canales` es `{email:null, telegram:null}`, muestra un aviso: "Ningún canal configurado".
- **Nota informativa** (texto fijo): "El envío periódico se programa fuera de la app (p.ej. Windows Task
  Scheduler o cron llamando a `POST /api/notificaciones/digest` con autenticación). Los canales se configuran
  por variables de entorno en el servidor: `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD`/`NOTIF_EMAIL_TO` para
  email y `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` para Telegram."

## 3. (Opcional)
- Reutiliza, si te resulta cómodo, los badges/contadores de la pantalla de avisos. No es obligatorio.

Consume solo `POST /api/notificaciones/digest`. No cambies otra lógica.
