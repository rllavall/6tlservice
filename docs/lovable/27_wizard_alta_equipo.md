# Prompt 27 — Rediseño del wizard de alta de equipo

**Archivo:** `src/routes/equipos.nuevo.tsx` (reescribir por completo).
**NO toques** ningún otro archivo de rutas ni los tipos no relacionados.

## Objetivo
Convertir el alta de equipo en un **wizard moderno de 4 pasos** con barra de
progreso, **todo el texto en inglés**, valores por defecto inteligentes, captura
de ubicación y un paso de revisión final. Una sola llamada al backend al
confirmar.

## Pasos
Barra de progreso arriba (1 Unit · 2 Customer & location · 3 Components · 4
Review), paso completado con ✓, actual resaltado. Botones **Back / Next**; Next
deshabilitado hasta que los obligatorios del paso estén. Todo el estado vive en
local; NADA se guarda hasta "Create unit".

1. **Unit** (obligatorios: Model + Serial number)
   - Model* — `GET /api/productos?tipo=equipo`, muestra `part_number — descripcion`.
   - Serial number*.
   - Customer serial no. (optional).
   - Version (optional).
   - Al elegir Model, precargar Warranty months (paso 2) con
     `producto.meses_garantia_default`.
2. **Customer & location** (dos subtarjetas)
   - Customer (optional) — `GET /api/clientes`.
   - Location (optional) — `GET /api/ubicaciones`, **filtrado por el Customer
     elegido** (si hay) más las ubicaciones sin cliente. Hint: "Sets where the
     unit is installed (creates the initial delivery movement)".
   - Manufacture date (optional).
   - Delivery date (optional) — **por defecto = hoy**.
   - Warranty months (precargado del modelo, editable).
   - Status — Active/Inactive (operativo/baja), por defecto Active.
   - Notes (optional).
3. **Initial components** (optional)
   - Editor de filas: Model (`tipo=componente`) + Serial number + Position +
     Notes. Añadir/quitar filas. Se puede saltar.
4. **Review & confirm**
   - Resumen read-only por secciones, cada una con enlace **Edit** que vuelve a
     su paso. Mostrar lo que se creará: la unidad, su ubicación (o "No
     location"), y la lista de componentes.
   - Avisos discretos: "No customer", "No location → won't show on the map",
     "Warranty not set".
   - Botón **Create unit**.

## Guardado (una sola llamada)
Al confirmar: `POST /api/equipos/alta` con el body:
```json
{
  "numero_serie": "...", "producto_id": 0, "cliente_id": null,
  "fecha_fabricacion": null, "fecha_entrega": "2026-06-09",
  "estado": "operativo", "notas": null, "meses_garantia": 24,
  "version": null, "numero_serie_cliente": null,
  "ubicacion_id": null, "movimiento_notas": null,
  "componentes": [
    {"producto_id": 0, "numero_serie": "...", "posicion": null, "notas": null}
  ]
}
```
Campos vacíos → enviar `null`/omitir; `componentes` → `[]` si no hay.
Respuesta 201 = el equipo creado → navegar a `/equipos/$id`.

## Manejo de errores
Si la respuesta NO es 201, el body es
`{ "detail": { "step": "unit"|"location"|"component", "index": number|null, "message": string } }`.
Mostrar `message` (toast) y **saltar al paso indicado** por `step` (para
`component`, además resaltar la fila `index`). Quedarse en el wizard sin perder
lo introducido.

## Estilo
Coherente con el resto de la app (lila `#9e007e`, componentes shadcn ya
presentes: Button, Input, Label, Select, Textarea). Wizard centrado, `max-w-3xl`.
Enlace "← Installed base" arriba.
