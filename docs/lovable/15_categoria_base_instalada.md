# Prompt 15 — Categoría de familia en la base instalada

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()`, tipos en `@/lib/types`, paleta lila
`#9e007e`, shadcn). NO cambies nombres de campo del backend; usa exactamente los slugs de abajo.

## 1. Tipos en `src/lib/types.ts`
```ts
export type CategoriaProducto =
  | "ate" | "yav_module" | "fastate_module" | "test_fixture" | "test_handler" | "otro";

export const CATEGORIA_LABEL: Record<CategoriaProducto, string> = {
  ate: "ATE",
  yav_module: "YAV Module",
  fastate_module: "fastATE Module",
  test_fixture: "Test Fixture",
  test_handler: "Test Handler",
  otro: "Otro",
};
// Añade `categoria: CategoriaProducto | null` a: Producto, Equipo/EquipoOut, Componente/ComponenteOut.
```

## 2. Base instalada (`src/routes/index.tsx` / tabla de equipos)
- Nueva **columna "Categoría"**: badge con `CATEGORIA_LABEL[equipo.categoria]` (o "—" si es `null`).
- Nuevo **filtro por categoría**: select ("Todas" + las 6 etiquetas) junto al buscador por nº de serie.
  Llama `GET /api/equipos?categoria=<slug>` (combinable con el filtro de serie ya existente).

## 3. Alta/edición de producto (catálogo, `src/routes/catalogo.tsx` o el form de producto)
- Selector `categoria` ("Sin categoría" + las 6 etiquetas). Envía/lee `categoria` (slug) en el POST/PUT
  de producto. (El backend acepta `categoria` en `ProductoCreate`, y el PUT reusa ese mismo schema.)

## 4. Ficha de equipo (`src/routes/equipos.$id.tsx`)
- En la lista de componentes (configuración), muestra un **badge** con la `categoria` de cada componente
  (`CATEGORIA_LABEL[componente.categoria]`), de modo que un ATE muestre sus YAV Modules etiquetados.

Usa EXACTAMENTE los slugs de arriba; no inventes endpoints.
