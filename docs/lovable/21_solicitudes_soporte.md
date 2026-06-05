# Prompt 21 — Solicitudes de soporte (formulario público + gestión interna)

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()` que ya inyecta el Bearer token, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`).
NO cambies nombres de campo. No inventes endpoints ni campos.

Un cliente externo envía una "solicitud de soporte" desde un formulario **público** (sin login). El equipo
interno la revisa y la **aprueba** (lo que crea automáticamente una incidencia) o la **rechaza** con motivo.

## 1. Tipos en `src/lib/types.ts`
```ts
type EstadoSolicitud = "pendiente" | "aprobada" | "rechazada";
type TipoIncidencia = "rma" | "soporte_venta" | "soporte_tecnico" | "calibracion";
type Prioridad = "baja" | "media" | "alta";

interface Solicitud {
  id: number;
  codigo: string;                 // "SOL-0001"
  estado: EstadoSolicitud;
  fecha_solicitud: string;        // ISO date
  nombre_contacto: string;
  empresa: string | null;
  email_contacto: string;
  telefono_contacto: string | null;
  numero_serie_texto: string | null;
  part_number_texto: string | null;
  titulo: string;
  descripcion_problema: string;
  incidencia_id: number | null;   // set tras aprobar
  motivo_rechazo: string | null;
  fecha_resolucion: string | null;
}
```

## 2. Formulario PÚBLICO — ruta `/solicitar` (FUERA del shell autenticado)
- Página independiente, **sin** sidebar ni guard de login (no usa el Bearer). Branding 6TL ligero.
- Campos (POST a `/api/solicitudes`):
  - `nombre_contacto` *(obligatorio)*, `email_contacto` *(obligatorio, valida formato email)*,
    `titulo` *(obligatorio)*, `descripcion_problema` *(obligatorio, textarea)*.
  - Opcionales: `empresa`, `telefono_contacto`, `numero_serie_texto` (nº de serie del equipo),
    `part_number_texto` (referencia/part number).
  - **Honeypot anti-bot**: incluye un campo `website` oculto (CSS `display:none`, `tabindex=-1`,
    `autocomplete=off`). Envíalo SIEMPRE en el body; si un humano lo deja vacío todo va bien (el backend
    rechaza con 400 si llega relleno). No lo muestres al usuario.
- Al enviar: `POST /api/solicitudes` **sin** cabecera Authorization. Respuesta 201 → muestra pantalla de
  éxito con el `codigo` ("Hemos recibido tu solicitud **SOL-0001**, te contactaremos en breve"). Limpia el
  formulario. Errores de validación (422/400) → mensaje inline.

## 3. Pantalla INTERNA — ruta `/solicitudes` (dentro del shell autenticado, en el menú)
- Lista vía `GET /api/solicitudes` (protegido, usa `api<T>()`). Filtro por estado con tabs/selector:
  Pendientes (`?estado=pendiente`) / Aprobadas / Rechazadas / Todas (sin query). Default: Pendientes.
- Tabla: `codigo`, `fecha_solicitud`, `nombre_contacto` + `empresa`, `titulo`, badge de `estado`
  (pendiente=ámbar, aprobada=verde, rechazada=gris). Orden ya viene del backend (más recientes primero).
- Fila → abre panel/drawer de detalle con todos los campos, incluido `numero_serie_texto` y
  `part_number_texto` (ayudan a identificar el equipo). Si `estado!=pendiente`, muestra solo lectura
  (+ `motivo_rechazo` si rechazada, + enlace a la incidencia `incidencia_id` si aprobada).

### 3a. Aprobar (solo si `estado==pendiente`)
- Botón "Aprobar" abre diálogo. Payload a `POST /api/solicitudes/{id}/aprobar`:
  - **Sujeto (obligatorio: al menos uno)** `equipo_id` **o** `componente_id`. Reutiliza el selector de
    equipos que ya existe en la app (búsqueda por nº de serie / código); precarga la búsqueda con
    `numero_serie_texto`/`part_number_texto` de la solicitud si vienen.
  - `tipo`: `TipoIncidencia` (default `"rma"`). `prioridad`: `Prioridad` (default `"media"`).
  - `asignado_a` (opcional, técnico). `en_garantia` (opcional tri-estado: sí/no/auto): si lo dejas
    vacío y `tipo=="rma"` con equipo, el backend la calcula sola — refléjalo como "Automática".
- Respuesta 201 = la **incidencia creada** (`IncidenciaOut`, tiene `id` y `codigo`). Toast de éxito,
  refresca la lista, y ofrece "Ver incidencia" navegando a su ficha. 409 → la solicitud ya no está
  pendiente (refresca). 404 → equipo/componente no encontrado (muestra el mensaje).

### 3b. Rechazar (solo si `estado==pendiente`)
- Botón "Rechazar" abre diálogo con `motivo` *(obligatorio, textarea)*. `POST /api/solicitudes/{id}/rechazar`
  con `{ motivo }`. 200 → toast, refresca. 409 → ya no pendiente.

## 4. Badge de pendientes en el menú
- Junto a "Solicitudes" en la navegación, muestra un contador con el nº de solicitudes pendientes
  (longitud de `GET /api/solicitudes?estado=pendiente`). Refresca al entrar y tras aprobar/rechazar.

No cambies la lógica existente de incidencias ni el selector de equipos; solo consúmelos.
