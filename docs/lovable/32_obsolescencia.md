# Prompt 32 — Obsolescencia (ciclo de vida de productos)

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()` que ya inyecta el Bearer token, tipos en
`@/lib/types`, shadcn, paleta lila `#9e007e`, componente `<HelpTip clave=...>` del prompt 20).
**NO cambies nombres de campo del backend. No inventes endpoints ni campos fuera de los listados aquí.**
Todas estas rutas van protegidas (el `api()` ya manda el token).

Un agente revisa semanalmente la web de cada fabricante y marca el **estado de ciclo de vida** de cada
producto del catálogo (EOL/PCN/obsolescencia). El frontend solo MUESTRA ese estado y deja editar la URL
de obsolescencia del fabricante; **no** clasifica a mano (lo hace el agente).

## 1. Tipos en `src/lib/types.ts`
```ts
export type EstadoCicloVida =
  | "activo" | "nrnd" | "eol_anunciado" | "ultima_compra" | "obsoleto";

export const ESTADO_CICLO_LABEL: Record<EstadoCicloVida, string> = {
  activo: "Activo",
  nrnd: "No recomendado (NRND)",
  eol_anunciado: "EOL anunciado",
  ultima_compra: "Última compra",
  obsoleto: "Obsoleto",
};

// Color del badge por estado (Tailwind). `null` = sin verificar -> gris/neutro.
export const ESTADO_CICLO_COLOR: Record<EstadoCicloVida, string> = {
  activo: "bg-green-100 text-green-800",
  nrnd: "bg-amber-100 text-amber-800",
  eol_anunciado: "bg-orange-100 text-orange-800",
  ultima_compra: "bg-orange-200 text-orange-900",
  obsoleto: "bg-red-100 text-red-800",
};

export interface NoticiaObsolescencia {
  id: number;
  producto_id: number;
  fecha_deteccion: string;            // ISO date
  estado_anterior: string | null;
  estado_nuevo: string;
  fecha_evento: string | null;
  url_fuente: string | null;
  resumen: string | null;
  notificado: boolean;
}

export interface ObsolescenciaResumen {
  conteos: Record<string, number>;    // p.ej. {activo: 90, nrnd: 3, obsoleto: 1, ...}
  sin_verificar: number;
  noticias: NoticiaObsolescencia[];   // últimas detectadas, recientes primero
}
```
Añade a `Producto`/`ProductoOut` (ya los expone el backend en `ProductoOut`):
```ts
  estado_ciclo_vida: EstadoCicloVida | null;
  ciclo_vida_fecha: string | null;
  ciclo_vida_url: string | null;
  ciclo_vida_resumen: string | null;
  ciclo_vida_verificado_en: string | null;
```
Añade a `Fabricante` (prompt 28): `url_obsolescencia: string | null;`

## 2. Componente reutilizable `EstadoCicloBadge`
Un pequeño badge que recibe `estado: EstadoCicloVida | null` y opcionalmente `url: string | null`:
- Si `estado` es `null` → badge neutro gris "Sin verificar".
- Si no → badge con `ESTADO_CICLO_LABEL[estado]` y clase `ESTADO_CICLO_COLOR[estado]`.
- Si hay `url`, el badge enlaza a esa URL (`target="_blank" rel="noreferrer"`) con un iconito de enlace.

## 3. Badge en el catálogo (`src/routes/catalogo.tsx` o el listado de productos)
- En la fila/tarjeta de cada producto muestra `<EstadoCicloBadge estado={p.estado_ciclo_vida} url={p.ciclo_vida_url} />`.
  Los datos ya vienen en `GET /api/productos` (campos del punto 1). Es **solo lectura** (no añadas selector de estado).
- Si `p.ciclo_vida_resumen` existe, muéstralo como `title`/tooltip del badge.

## 4. Pantalla **Obsolescencia** `/obsolescencia` (nueva, en el menú)
Vista general del estado del catálogo. Carga `GET /api/obsolescencia` → `ObsolescenciaResumen`.
- **Cabecera de KPIs**: una tarjeta por estado con su `conteos[estado]` (usa `ESTADO_CICLO_LABEL` y el color),
  más una tarjeta "Sin verificar" con `sin_verificar`. Resalta visualmente `obsoleto`, `ultima_compra` y
  `eol_anunciado` (son los que requieren acción).
- **Tabla "Cambios recientes"** con `noticias`: columnas `fecha_deteccion`, producto (muestra `producto_id`;
  si tienes a mano el catálogo en memoria, resuelve el `part_number`), transición
  `estado_anterior ?? "sin verificar" → estado_nuevo` (usa el badge), `resumen`, y un enlace "fuente"
  si `url_fuente`. Orden tal cual llega (recientes primero).
- Pon un `<HelpTip clave="obsolescencia.general">` junto al título.
- Estado vacío: si `noticias` está vacío, muestra "Sin cambios de obsolescencia detectados".

## 5. URL de obsolescencia editable en el fabricante (`/fabricantes`, prompt 28)
- En el formulario de alta/edición de fabricante añade un campo de texto **"URL de obsolescencia (PCN/EOL)"**
  que lee/escribe `url_obsolescencia`. Va en el body de `POST /api/fabricantes` y `PUT /api/fabricantes/{id}`
  (ambos ya aceptan `url_obsolescencia`, opcional). Es la página que el agente consulta para esa marca.
- En la tabla de fabricantes, si `url_obsolescencia` existe, muestra un pequeño enlace "PCN".

## 6. Notas
- Usa EXACTAMENTE los slugs de estado de arriba; el orden de severidad es
  `activo < nrnd < eol_anunciado < ultima_compra < obsoleto`.
- El frontend NO clasifica ni cambia el estado de los productos: eso lo hace el agente semanal por backend.
  La única escritura que añade este prompt es la `url_obsolescencia` del fabricante.
- No toques los ejes `categoria` (prompt 15) ni `categoria_componente` (prompt 29); este es un indicador aparte.
