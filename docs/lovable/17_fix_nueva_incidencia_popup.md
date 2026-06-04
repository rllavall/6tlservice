# Prompt 17 — FIX: "Nueva incidencia" no funciona + convertirla en popup

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()`, tipos en `@/lib/types`, shadcn,
paleta lila `#9e007e`).

## El bug (causa raíz)
`src/routes/incidencias.tsx` es la **ruta padre** de `incidencias.$id.tsx` y `incidencias.nueva.tsx`
(rutas hijas anidadas), pero su componente NO renderiza `<Outlet />`. Por eso navegar a
`/incidencias/nueva` o `/incidencias/$id` cambia la URL pero **sigue mostrando la lista** (la pantalla
no cambia → "no hace nada"). Hay que arreglar el `Outlet` y, de paso, convertir "Nueva incidencia" en
un popup como pidió el usuario.

## 1. Arreglar el routing (Outlet) — OBLIGATORIO
Reestructura la ruta `/incidencias` en layout + index:

- **`src/routes/incidencias.tsx`** → conviértela en un **layout** cuyo componente renderice SOLO
  `<Outlet />` (de `@tanstack/react-router`). Quita de aquí la lista, los filtros y los diálogos
  (se mueven al index). Mantén `createFileRoute("/incidencias")`.
- **`src/routes/incidencias.index.tsx`** (NUEVO) → mueve aquí TODO el contenido actual de la lista
  (tabla, filtros, el popup de Bitácora, etc.). `createFileRoute("/incidencias/")`. Es lo que se ve en
  `/incidencias`.

Con esto, `/incidencias/$id` (Abrir expediente) y `/incidencias/nueva` vuelven a renderizar.

## 2. "Nueva incidencia" como POPUP en la lista
En `incidencias.index.tsx`:
- El botón **"Nueva incidencia"** ya NO navega (`<Link to="/incidencias/nueva">`). En su lugar abre un
  **Dialog** (popup, shadcn) con el formulario de alta de incidencia.
- Extrae el formulario a un componente reutilizable **`src/components/NuevaIncidenciaForm.tsx`** con la
  lógica/campos que hoy están en `incidencias.nueva.tsx`: selector de **equipo** o **componente**
  (al menos uno — el backend devuelve 422 si faltan ambos), **título**, **descripción**, **tipo**
  (rma/soporte_venta/soporte_tecnico/calibracion, default rma), **prioridad** (baja/media/alta),
  **asignado_a**, **en_garantia** (para RMA), **fecha_apertura** (default hoy). Props sugeridas:
  `{ equipoIdInicial?: string, onCreated: (inc) => void, onCancel: () => void }`.
- Al guardar: `POST /api/incidencias` con `{equipo_id?|componente_id?, titulo, descripcion_problema,
  tipo, prioridad, asignado_a, en_garantia, fecha_apertura}`. Tras 201: cierra el popup, refresca la
  lista (invalida la query de incidencias) y muestra toast con el `codigo` devuelto. Si 422 por sujeto,
  muestra el error junto al selector.

## 3. Reusar el formulario en la ficha de equipo y en la página
- **`src/routes/equipos.$id.tsx`** (línea ~1395 hay un `to: "/incidencias/nueva"`): cambia ese botón
  "crear incidencia" para que abra el MISMO popup `NuevaIncidenciaForm` con `equipoIdInicial` = el id
  del equipo (en vez de navegar).
- **`src/routes/incidencias.nueva.tsx`**: déjala como página fina que simplemente renderiza
  `<NuevaIncidenciaForm>` (para deep-links `/incidencias/nueva?equipo_id=`), o elimínala si prefieres
  popup-only — pero entonces quita también cualquier `<Link>`/`navigate` que apunte a ella.

## Verificación
- Tras aplicar: `/incidencias/$id` (Abrir expediente) debe renderizar la ficha; "Nueva incidencia"
  (en la lista y en la ficha de equipo) debe abrir el popup, crear la incidencia y refrescar la lista.

No toques el backend ni los nombres de campo.
