# Diseño — Wizard de alta de equipo (rediseño)

**Fecha:** 2026-06-09
**Estado:** aprobado (pendiente de plan de implementación)

## Objetivo

Rediseñar la pantalla de alta de equipo (`/equipos/nuevo`) para que sea más
moderna, más fácil para el operario y, sobre todo, que **no se deje ninguna dato
por el camino**. Hoy es un formulario plano de 2 pasos en una sola página, con
mezcla de idiomas (castellano + inglés), sin captura de ubicación, sin valores
por defecto inteligentes y sin paso de revisión.

## Decisiones tomadas (brainstorming)

- **Idioma:** el wizard queda **íntegramente en inglés** y coherente. (Unificar
  TODA la app a inglés es un trabajo mayor → queda como follow-up separado; aquí
  se toca solo el wizard.)
- **"Que no se deje ningún dato":** se atacan las 4 vías a la vez — paso de
  revisión, valores por defecto inteligentes, captura de ubicación y campos
  obligatorios guiados.
- **Alcance:** wizard por pasos completo (no poliment incremental).
- **Estrategia de guardado:** **endpoint atómico en el backend** (todo-o-nada),
  no orquestación cliente. Garantiza que un alta nunca quede a medias.

## Estructura del wizard (4 pasos)

Ruta `/equipos/nuevo`. Un solo paso visible cada vez, con **barra de progreso**
arriba (pasos numerados; el completado con ✓, el actual resaltado). Todo el
estado vive en local; **no se guarda nada hasta el "Create unit" final**.
Botones Back/Next; **Next bloqueado** hasta que estén los obligatorios del paso.

```
 ①Unit ───── ②Customer & location ───── ③Components ───── ④Review
```

### Paso 1 · Unit (puerta obligatoria: model + serial)
- **Model*** — producto `tipo=equipo`, muestra `part_number — descripción`.
- **Serial number*** — obligatorio.
- **Customer serial no.** — opcional.
- **Version** — opcional.
- Al elegir Model: se precarga el campo de garantía del paso 2 desde
  `producto.meses_garantia_default` (mostrando "from model: 24", editable).

### Paso 2 · Customer & location
Dos subsecciones dentro del mismo paso (menos clics para el operario):
- **Customer & location:**
  - **Customer** — opcional (select).
  - **Location** — opcional, **filtrado por el cliente elegido**. Elegir
    ubicación crea el **movimiento inicial "entrega"**. Sin ubicación → se omite.
  - **Manufacture date** — opcional.
  - **Delivery date** — opcional, **valor por defecto = hoy**.
- **Warranty & status:**
  - **Warranty months** — **precargado** desde el modelo (24 por defecto del
    producto), editable. Elimina el `sin_datos` silencioso de la analítica.
  - **Status** — `operativo|baja`, por defecto `operativo`.
  - **Notes** — opcional.

### Paso 3 · Initial components (opcional)
Editor de filas (el actual, pulido): por fila Model (producto `tipo=componente`)
+ Serial number + Position + Notes. Serial obligatorio por fila. Añadir/quitar
filas. Se puede saltar sin componentes.

### Paso 4 · Review & confirm
Resumen read-only agrupado por secciones; cada sección con enlace **"Edit"** que
salta a su paso. Muestra exactamente qué se va a crear: la unidad, su movimiento
de ubicación (o "No location"), y N componentes. **Avisos** discretos para
huecos notables: "No customer", "No location → won't show on the map", "Warranty
not set". Botón **Create unit** (confirmación = única llamada al backend).

## "Que no se deje ningún dato" — cómo se cubre

- **Valores por defecto:** delivery date = hoy · warranty months = default del
  modelo · status = operativo.
- **Obligatorios guiados:** `*` claro, "(optional)" en el resto, Next bloqueado
  hasta tener los clave del paso, mensajes inline.
- **Ubicación:** capturada como movimiento "entrega" → el equipo aparece en el
  mapa desde el minuto uno.
- **Revisión:** el paso 4 obliga a pasar por delante de todo antes de confirmar.

## Backend — endpoint atómico nuevo `POST /api/equipos/alta`

- **Payload `EquipoAltaCreate`:** todos los campos de `EquipoCreate`
  (`numero_serie`, `producto_id`, `cliente_id?`, `fecha_fabricacion?`,
  `fecha_entrega?`, `estado`, `notas?`, `meses_garantia?`, `version?`,
  `numero_serie_cliente?`) **+** `ubicacion_id?` (+ `movimiento_fecha?`,
  `movimiento_notas?`) **+** `componentes: list[{producto_id, numero_serie,
  posicion?, notas?}]?`.
- **Comportamiento (una transacción):**
  1. **Validar primero** (antes de insertar): serials únicos del equipo Y de
     todos los componentes (sin colisión con BD ni entre sí), `producto_id` del
     equipo es `tipo=equipo`, cada componente es `tipo=componente`, y —solo si
     hay `ubicacion_id` Y `cliente_id`— que la ubicación pertenezca a ese cliente
     (si la ubicación no tiene cliente, p. ej. un almacén, se acepta).
  2. Crear el equipo.
  3. Si `ubicacion_id`: crear movimiento `motivo="entrega"`, fecha =
     `movimiento_fecha` o `fecha_entrega` o hoy.
  4. Por cada componente: crear `Componente` + montar (`motivo="entrega_inicial"`).
- **Atomicidad:** cualquier fallo → **rollback de todo**; no quedan filas
  parciales.
- **Errores estructurados:** `{detail: {step: "unit"|"location"|"component",
  index?: n, message}}` para que el wizard salte al paso correcto (p. ej. serial
  duplicado → 409 y vuelve al paso 1; serial de componente duplicado → 409 con
  `index`).
- **Respuesta:** `EquipoOut` (o `EquipoFicha`) del equipo creado.
- **Auditoría:** se audita como una operación coherente (un solo flush dentro de
  la transacción; el listener ORM existente registra los inserts).

## Tests (backend, TDD)

- Happy path completo (equipo + ubicación + N componentes) crea todo y devuelve
  el equipo con su movimiento y componentes montados.
- Cada opcional omitido (sin ubicación / sin componentes / sin cliente).
- Serial de equipo duplicado → 409 y **nada creado** (assert: no equipo, no
  movimiento, no componentes).
- Serial de componente duplicado (con BD o entre filas) → **rollback total**.
- Ubicación que pertenece a otro cliente → error, nada creado.
- `producto_id` de equipo que es `tipo=componente` (y viceversa en componentes)
  → 409, nada creado.
- Atomicidad: forzar fallo en el último componente y verificar que no queda
  ninguna fila parcial.
- Garantía: el backend autorrellena `meses_garantia` desde
  `producto.meses_garantia_default` cuando llega `None` (mismo comportamiento que
  `POST /api/equipos`), de modo que nunca queda sin dato silenciosamente. Si el
  cliente envía un valor explícito, se respeta. El wizard además lo precarga en
  la UI al elegir el modelo (doble red de seguridad).

## Frontend (prompt Lovable)

- Reescribir `/equipos/nuevo` como wizard de 4 pasos con barra de progreso,
  estado local único, validación por paso y paso de revisión.
- Una sola llamada `POST /api/equipos/alta` al confirmar; manejar el error
  estructurado saltando al paso indicado.
- Location select filtrado por cliente; prefill de garantía al elegir modelo;
  delivery date = hoy por defecto.
- **Todo el texto en inglés.**

## Fuera de alcance (follow-up)

- Unificación de idioma del resto de la app (hoy bilingüe).
- Comprobación asíncrona de serial duplicado "al vuelo" (de momento se valida en
  el confirm con error claro que vuelve al paso 1).
- Alta de cliente/ubicación/modelo nuevos desde dentro del wizard (se asume que
  ya existen en el catálogo; el wizard enlaza a crearlos si faltan, como hoy).
