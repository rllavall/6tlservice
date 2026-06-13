# Prompt 37 — Entrada manual del estado de ciclo de vida en el report del banco

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, helper `api<T>()` en
`@/lib/api` (inyecta Bearer), tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`,
componentes `<EstadoCicloBadge estado url resumen />` y `ReportObsolescenciaDialog`
(prompts 32/34/35/36)). **NO cambies nombres de campo del backend. No inventes endpoints
ni campos fuera de los listados.** Todo va protegido (el `api()` manda token).

Para fabricantes cuya web bloquea bots (p. ej. Keysight) el agente no puede determinar el
estado y el componente se queda en "No encontrado". El usuario debe poder **fijar el
estado a mano** desde la tabla del report del banco.

## 1. Tipos en `src/lib/types.ts`
- `ObsolescenciaBancoComponente` += `producto_id: number` y
  `ciclo_vida_origen: string | null` ("agente" | "manual").

## 2. Endpoint (ya existe en backend)
`PATCH /api/productos/{producto_id}/ciclo-vida` con body:
`{ "estado": "activo"|"nrnd"|"eol_anunciado"|"ultima_compra"|"obsoleto", "fecha_evento"?: "YYYY-MM-DD"|null, "url"?: string|null, "nota"?: string|null }`
Devuelve el producto actualizado. Usa `c.producto_id` de la fila del report (ahora
disponible) como `{producto_id}`.

## 3. UI en `ReportObsolescenciaDialog` (tabla de componentes)
- En cada fila, junto al estado, un **botón lápiz** (icono `Pencil`, ghost, pequeño) que
  abre un diálogo "Fijar estado a mano":
  - `estado`: select con los 5 valores (etiquetas legibles: Activo / NRND / EOL anunciado /
    Última compra / Obsoleto).
  - `fecha_evento`: input date (opcional).
  - `url`: input (opcional).
  - `nota`: textarea (opcional) — "justificación / fuente". Se mostrará como la cita.
  - Botón Guardar → `api(PATCH /api/productos/{producto_id}/ciclo-vida, body)` → al éxito,
    `toast.success`, cerrar el diálogo y **refrescar el report** (re-fetch del
    `GET /api/equipos/{id}/obsolescencia`). Manejar error con `toast.error`.
- Badge **"✋ Manual"** (pequeño, gris/lila) junto al `<EstadoCicloBadge>` cuando
  `ciclo_vida_origen === "manual"`. No mostrar nada extra cuando es "agente"/null.

## 4. Notas
- El resto del popup (prompts 34/35/36) no cambia.
- Tras guardar manual, el badge "Manual" debe aparecer y la cita (nota) verse en el botón
  "i" de prueba de origen (prompt 36).
