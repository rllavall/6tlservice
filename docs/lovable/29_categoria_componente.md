# Prompt 29 — Categoría de componente (Instrumento / Mass Interconnect / Wiring / Accesories)

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()`, tipos en `@/lib/types`, paleta lila
`#9e007e`, shadcn). NO cambies nombres de campo del backend; usa exactamente los slugs de abajo.
Este es un **eje nuevo e independiente** del `categoria` existente (prompt 15) — NO lo toques ni lo mezcles.

## 1. Tipos en `src/lib/types.ts`
```ts
export type CategoriaComponente =
  | "instrumento" | "mass_interconnect" | "wiring" | "accesorios";

export const CATEGORIA_COMPONENTE_LABEL: Record<CategoriaComponente, string> = {
  instrumento: "Instrumento",
  mass_interconnect: "Mass Interconnect",
  wiring: "Wiring",
  accesorios: "Accesories",
};
// Añade `categoria_componente: CategoriaComponente | null` a: Producto/ProductoOut y Componente/ComponenteOut.
```

## 2. Alta/edición de producto (catálogo, `src/routes/catalogo.tsx` o el form de producto)
- Nuevo selector **"Categoría de componente"** ("Sin clasificar" + las 4 etiquetas). Envía/lee
  `categoria_componente` (slug) en el POST/PUT de producto. (El backend acepta `categoria_componente`
  en `ProductoCreate`, y el PUT reusa ese mismo schema.)
- Es relevante sólo cuando el producto es de tipo `componente`: deshabilítalo/ocúltalo si `tipo === "equipo"`.

## 3. Ficha de equipo (`src/routes/equipos.$id.tsx`)
- En la lista de componentes (configuración), muestra un **badge** con la `categoria_componente`
  de cada componente (`CATEGORIA_COMPONENTE_LABEL[componente.categoria_componente]`), o nada si es `null`.
  Usa un color distinto al badge de `categoria` para que se distingan ambos ejes.

## 4. Filtro por categoría de componente (catálogo / listado)
- Nuevo **select** ("Todas" + las 4 etiquetas) en el catálogo de productos.
  Llama `GET /api/productos?categoria_componente=<slug>`.
- (Opcional, si hay un listado de componentes) el mismo filtro vale para
  `GET /api/componentes?categoria_componente=<slug>`.

Usa EXACTAMENTE los slugs de arriba; no inventes endpoints. La etiqueta visible de `accesorios` es
"Accesories" (tal cual). No modifiques el eje `categoria` del prompt 15.
