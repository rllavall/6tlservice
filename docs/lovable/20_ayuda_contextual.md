# Prompt 20 — Ayuda contextual (tooltips "?")

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()` que ya inyecta el Bearer token, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`).
NO cambies nombres de campo.

## 1. Tipo en `src/lib/types.ts`
- `interface AyudaTopico { clave:string; titulo:string|null; texto:string; pantalla:string|null }`

## 2. Carga del catálogo (una vez)
- Al entrar en la app autenticada, llama `GET /api/ayuda` y guarda un mapa `clave → AyudaTopico`
  en un contexto/store (p.ej. `AyudaProvider` con React Context, o un hook `useAyuda()`).
  Con recargar la página basta; no hace falta invalidación fina.

## 3. Componente `<HelpTip clave="...">`
- Pinta un icono **"?"** pequeño (botón con `aria-label`, icono `HelpCircle` de lucide) junto a una
  etiqueta. Al hover/click muestra un Tooltip/Popover de shadcn con el `titulo` (en negrita, si existe)
  y el `texto` del tópico cuya `clave` coincide.
- Si la `clave` no está en el catálogo, **no pinta nada** (y `console.warn` en desarrollo).

## 4. Colocación (usa EXACTAMENTE estas claves, ya sembradas en el backend)
- Base instalada / ficha de equipo: `equipos.estado`, `equipos.categoria`, `equipos.version`,
  `equipos.numero_serie_cliente`, `garantia.estado`, `garantia.meses`.
- Incidencias (lista/ficha/alta): `incidencias.tipo`, `incidencias.prioridad`, `incidencias.estado`,
  `incidencias.en_garantia`, `incidencias.avances`.
- Mapa: `mapa.pin`, `mapa.incluir_baja`.
- Analítica / cabecera KPIs: `analitica.mttr`, `resumen.tiempo_medio_cierre`.
- Sección de historial de cambios (auditoría) de la ficha: `auditoria.historial`.

Coloca el `<HelpTip clave="...">` junto a la etiqueta del campo/sección correspondiente. No cambies la
lógica existente; solo añade el icono de ayuda. No inventes claves ni endpoints.
