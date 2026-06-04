# Prompt 13 — Analítica de incidencias + control de garantía

Contexto: app de postventa de 6TL (electronic test systems). Stack ya existente:
**TanStack Start** (rutas en `src/routes`), TypeScript, Tailwind, shadcn. API base
`VITE_API_BASE ?? http://127.0.0.1:8020`. Usa el helper `api<T>()` de `src/lib/api` y los
tipos de `@/lib/types`. Paleta de marca: lila `#9e007e`. Gráficos con **recharts** (instálalo si
no está: `recharts`). NO toques el backend ni cambies nombres de campo: usa exactamente los de abajo.

## 1. Tipos nuevos en `src/lib/types.ts`

```ts
export type IncidenciaTipo = "rma" | "soporte_venta" | "soporte_tecnico" | "calibracion";
export type EstadoGarantia = "vigente" | "por_vencer" | "vencida" | "sin_datos";

// Añade a Incidencia / IncidenciaOut:
//   tipo: IncidenciaTipo;
// Añade a Equipo / EquipoFicha["equipo"]:
//   version: string | null;
//   numero_serie_cliente: string | null;
//   meses_garantia: number | null;
//   fecha_fin_garantia: string | null;       // ISO date, solo lectura (derivado)
//   estado_garantia: EstadoGarantia | null;   // solo lectura (derivado)

export interface ConteoItem { clave: string; etiqueta: string; valor: number; }
export interface KpiTiempoItem { clave: string; etiqueta: string; dias: number | null; n: number; }
export interface KpiTiempo {
  mttr_dias: number | null;
  diagnostico_dias: number | null;
  edad_abiertas_dias: number | null;
  por_tipo: KpiTiempoItem[];
  por_producto: KpiTiempoItem[];
  por_tecnico: KpiTiempoItem[];
}
export interface PuntoTendencia { mes: string; abiertas: number; cerradas: number; backlog: number; }
export interface RankingItem { id: number | null; etiqueta: string; valor: number; }
export interface ResumenGarantia {
  equipos_por_estado: ConteoItem[];
  rma_en_garantia: number;
  rma_fuera_garantia: number;
  rma_garantia_desconocida: number;
}
export interface AnaliticaIncidencias {
  total: number;
  por_tipo: ConteoItem[];
  por_producto: ConteoItem[];
  por_tecnico: ConteoItem[];
  por_prioridad: ConteoItem[];
  por_estado: ConteoItem[];
  por_cliente: ConteoItem[];
  kpis_tiempo: KpiTiempo;
  tendencia_mensual: PuntoTendencia[];
  fiabilidad_productos: RankingItem[];
  fiabilidad_equipos: RankingItem[];
  garantia: ResumenGarantia;
}
```

## 2. Ruta nueva `src/routes/analitica.tsx`

Pantalla `/analitica`. `useQuery` a `GET /api/analitica/incidencias` con query string de los filtros
activos. Devuelve un único objeto `AnaliticaIncidencias`.

- **Cabecera con filtros globales** (al cambiar, refetch):
  - Rango de fechas `desde` / `hasta` (params `desde=YYYY-MM-DD&hasta=YYYY-MM-DD`, sobre fecha de apertura).
  - `tipo`: select con "Todos" + las 4 opciones (RMA / Soporte Venta / Soporte Técnico / Calibración),
    param `tipo=rma|soporte_venta|soporte_tecnico|calibracion`.
  - Cliente: select cargado de `GET /api/clientes`, param `cliente_id=`.
- **KPI cards** (fila superior): Total incidencias (`total`), MTTR días (`kpis_tiempo.mttr_dias`),
  Edad media abiertas días (`kpis_tiempo.edad_abiertas_dias`), % RMA en garantía
  (`garantia.rma_en_garantia / (garantia.rma_en_garantia + garantia.rma_fuera_garantia)`, 0 si denom 0).
  Muestra `—` cuando un KPI es `null`.
- **Distribuciones** (BarChart recharts, una por bloque; eje = `etiqueta`, valor = `valor`): por tipo,
  por producto (top 10), por técnico, por prioridad, por estado, por cliente. Barras en lila `#9e007e`.
- **Tendencia mensual** (LineChart): eje X `mes` (YYYY-MM); series `abiertas`, `cerradas`, `backlog`.
- **Fiabilidad** (dos tablas): `fiabilidad_productos` y `fiabilidad_equipos` (columna etiqueta + nº
  incidencias). En la tabla de equipos, enlaza cada fila a la ficha del equipo `/equipos/$id` usando `id`.
- **Garantía** (sección): tarjetas/badges con `garantia.equipos_por_estado` (Vigente/Por vencer/Vencida/
  Sin datos) y un bloque "RMA: en garantía / fuera / desconocida" con los 3 contadores.
- Estados de carga (skeleton) y vacío ("Sin datos para los filtros seleccionados").

## 3. Selector de tipo en incidencia (`incidencias.nueva.tsx` y edición en `incidencias.$id.tsx`)

- Añade un selector **Tipo** (4 opciones, default **RMA**). Envía `tipo` en el POST de alta y en el PATCH
  de edición.
- Muestra un **badge de tipo** en la lista (`incidencias.tsx`) y en la ficha.
- Para RMA con equipo: `en_garantia` ya llega autodetectado del backend al crear (según la garantía del
  equipo en la fecha de apertura), pero sigue siendo **editable** en el formulario. Para los otros tipos,
  `en_garantia` es irrelevante (puede ocultarse o dejarse opcional).

## 4. Ficha + alta/edición del equipo (`equipos.$id.tsx`, `equipos.nuevo.tsx`, `equipos.$id.editar.tsx`)

- Campos **editables**: `version`, `numero_serie_cliente`, `meses_garantia`.
- La ficha muestra, en el bloque de identidad del equipo: **PN** y **descripción** (del producto asociado),
  **SN** (`numero_serie`), **Nº serie cliente** (`numero_serie_cliente`, solo si tiene valor — "si aplica"),
  **año de fabricación** (año de `fecha_fabricacion`) y **versión** (`version`).
- **Badge de estado de garantía** (`estado_garantia`) con color: `vigente`=verde, `por_vencer`=ámbar,
  `vencida`=rojo, `sin_datos`=gris; muestra `fecha_fin_garantia` cuando exista (y los meses de garantía).

## 5. Navegación

- Añade una entrada **"Analítica"** al menú/navegación que lleve a `/analitica`.

Recuerda: usa EXACTAMENTE los nombres de campo de arriba; no inventes endpoints ni renombres campos.
