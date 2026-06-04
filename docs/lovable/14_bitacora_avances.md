# Prompt 14 — Bitácora de avances de incidencia (popup desde la lista + ficha)

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()`, tipos en `@/lib/types`, paleta lila
`#9e007e`, shadcn). NO cambies nombres de campo del backend; usa exactamente los de abajo.

## 1. Tipos en `src/lib/types.ts`
```ts
export type AvanceTipo = "avance" | "report" | "llamada" | "visita" | "diagnostico" | "otro";
export interface Avance {
  id: number;
  incidencia_id: number;
  fecha: string;          // ISO date YYYY-MM-DD
  autor: string | null;
  tipo: AvanceTipo;
  texto: string;
}
// Añade a IncidenciaFicha:  avances: Avance[];
```

## 2. Componente `src/components/BitacoraIncidencia.tsx`
Props: `{ incidenciaId: number }`.
- Carga `GET /api/incidencias/{incidenciaId}/avances` (ya viene ordenado **desc** = más reciente primero).
- **Timeline**: cada entrada muestra `fecha`, un **badge** de `tipo`, `autor` (si existe) y `texto`.
  Acciones por entrada: **editar** y **borrar**.
- **Formulario "Añadir avance"**: selector `tipo` (6 opciones, default `avance`), `fecha` (input date,
  default hoy), `autor` (texto, opcional), `texto` (textarea, **obligatorio**). Submit →
  `POST /api/incidencias/{id}/avances` con `{tipo, fecha, autor, texto}`.
- **Editar**: `PATCH /api/incidencias/{id}/avances/{avanceId}` con los campos cambiados (no envíes `null`
  en fecha/tipo/texto — el backend devuelve 422; para vaciar `autor` sí se admite `null`).
- **Borrar**: `DELETE /api/incidencias/{id}/avances/{avanceId}` (204).
- Refresca la lista tras cada alta/edición/borrado. Estados de carga y vacío ("Sin avances todavía").
- Errores: si el POST/PATCH devuelve 422 (texto vacío), muestra el mensaje junto al campo.

## 3. Lista de incidencias (`src/routes/incidencias.tsx`)
- El click en una fila abre un **popup/modal** (Dialog de shadcn) con la cabecera de la incidencia
  (código, título, badge de estado y de tipo) y dentro `<BitacoraIncidencia incidenciaId={inc.id} />`.
- Dentro del modal, un botón **"Abrir expediente"** navega a `/incidencias/$id` (ficha completa).
- (Mantén accesible la ficha completa; pero el click principal de la fila abre el popup de bitácora.)

## 4. Ficha de incidencia (`src/routes/incidencias.$id.tsx`)
- Añade una sección **"Bitácora / Avances"** en el expediente que embeba
  `<BitacoraIncidencia incidenciaId={id} />`. Puedes usar `ficha.avances` para el primer pintado
  y/o recargar vía el endpoint.

Recuerda: usa EXACTAMENTE los nombres de campo de arriba; no inventes endpoints.
