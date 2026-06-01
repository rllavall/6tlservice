# Prompt Lovable 01 — Base instalada (home) + buscador global

> Requiere el prompt 00 (sistema de diseño + shell). Mantén la identidad corporativa 6TL (lila `#9e007e`, Open Sans/Roboto, isotipo). NO toques el sistema de diseño ni el cliente API; reutilízalos.

---

Implementa la pantalla principal **Base instalada** en la ruta `/` y el **buscador global** del header.

## Buscador global (en el header del shell, prompt 00)
Un input prominente con icono de lupa, placeholder "Buscar por nº de serie…". Al enviar (Enter):
- `GET /api/buscar?serie=<valor>` → devuelve `{ tipo, equipo, componente, equipo_del_componente }` donde `tipo ∈ "equipo" | "componente" | "ninguno"`.
- Si `tipo === "equipo"`: navega a `/equipos/{equipo.id}`.
- Si `tipo === "componente"`: si `equipo_del_componente` no es null, navega a `/equipos/{equipo_del_componente.id}` (y resalta el componente); si es null, muestra un toast "Componente {componente.numero_serie} en stock (no montado)".
- Si `tipo === "ninguno"`: toast "Sin resultados para ese número de serie".
Es la acción estrella de postventa: que sea rápida y siempre accesible.

## Tabla de base instalada (ruta `/`)
Carga `GET /api/equipos` → array de `Equipo`:
`{ id, numero_serie, producto_id, cliente, fecha_fabricacion, fecha_entrega, estado, notas }`
(`estado ∈ "operativo" | "baja"`).

Para mostrar el modelo y la ubicación necesitas dos lookups auxiliares:
- `GET /api/productos` → para mapear `producto_id` → `part_number` + `descripcion` (modelo del equipo).
- Para la **ubicación actual** de cada equipo, NO hay campo en `/api/equipos`. Hay dos opciones; usa la (a):
  - (a) Para la columna "Ubicación" en el listado, deja que el usuario filtre por ubicación con el selector (ver filtros); la ubicación actual exacta se ve en la ficha. En el listado, muestra ubicación solo cuando filtras por una (resaltas que esos equipos están ahí). Es suficiente para v1.
  - (Nota: existe `GET /api/ubicaciones/{id}/equipos` que lista los equipos cuya ubicación actual es esa; lo usamos para el filtro por ubicación.)

**Columnas:** Nº de serie (Roboto, destacado, clicable → ficha), Modelo (part_number — descripción), Cliente, Fecha entrega, Estado (badge). Fila entera clicable → `/equipos/{id}`.

**Badge de estado:** `operativo` = badge verde funcional discreto; `baja` = badge gris. (Recuerda: el color de marca es el lila; el verde/gris aquí es solo semáforo de estado.)

**Filtros** (barra sobre la tabla):
- **Estado:** Todos / Operativo / Baja → re-fetch con `GET /api/equipos?estado=operativo|baja`.
- **Modelo (producto):** selector poblado desde `GET /api/productos?tipo=equipo` → `GET /api/equipos?producto_id={id}`.
- **Ubicación:** selector poblado desde `GET /api/ubicaciones`; al elegir una, lista vía `GET /api/ubicaciones/{id}/equipos` (devuelve `Equipo[]`) y muestra esos.
- **Lleva el part number (componente):** input de texto → `GET /api/equipos?part_number=<pn>` (devuelve los equipos que **contienen un componente** con ese part number — trazabilidad por despiece; útil para "¿qué equipos llevan la tarjeta X?").
Los filtros se combinan de forma sensata; si la combinación es difícil, prioriza aplicarlos en servidor uno a uno y deja claro cuál está activo con chips removibles en lila.

**Cabecera de la pantalla:** título "Base instalada" (Open Sans), contador de equipos, y botón primario lila **"+ Nuevo equipo"** → navega a `/equipos/nuevo` (lo implementa el prompt 03).

**Estados vacíos / carga:** skeleton al cargar; estado vacío con isotipo en gris claro y texto "No hay equipos que coincidan".

Maneja errores del cliente API mostrando el `detail` en toast. No inventes campos que la API no devuelve.
