# Prompt Lovable 10 — Incidencias / RMA: alta + hooks en pantallas existentes

> Requiere prompts 00, 08 y 09. Mantén la identidad 6TL (lila `#9e007e`, Open Sans/Roboto). NO toques el shell ni el cliente API. Añade la ruta `/incidencias/nueva` y modifica puntualmente las pantallas indicadas en "Hooks en pantallas existentes".

---

## Parte A — Alta de incidencia (`/incidencias/nueva`)

Implementa el formulario de **nueva incidencia** en `/incidencias/nueva`. Este formulario se abre al pulsar "+ Nueva incidencia" desde la lista (prompt 08) o al pulsar "Abrir incidencia" desde la ficha de un equipo (ver Parte B); en ese segundo caso, puede recibir query params `equipo_id` o `componente_id` para pre-rellenar el selector.

### Carga previa

Carga en paralelo antes de renderizar el formulario:
- `GET /api/equipos` → lista de equipos para el selector.
- `GET /api/componentes` → lista de componentes para el selector.

### Campos del formulario

| Campo | Tipo | Obligatoriedad | Observaciones |
|---|---|---|---|
| **Equipo / Componente** | Selector doble | Al menos uno | Selector de equipo (numero_serie + parte del part_number) Y selector de componente (numero_serie). Al menos uno de los dos debe estar relleno; pueden estarlo los dos. Si llegan query params `equipo_id` / `componente_id`, preseleccionar el correspondiente. |
| **Título** | Texto libre | Obligatorio | Descripción breve de la avería. |
| **Descripción del problema** | Textarea | Obligatorio | Detalle del síntoma observado. |
| **Prioridad** | Select | Opcional (default `media`) | baja / media / alta. Badge de color junto al select para visualización inmediata. |
| **Asignado a** | Texto libre | Opcional | Nombre del técnico responsable. |
| **En garantía** | Selector ternario | Opcional | Opciones: "Sí" (`true`) / "No" (`false`) / "—" (`null`). |
| **Fecha de apertura** | Fecha | Obligatorio | Por defecto la fecha de hoy. |

### Submit

`POST /api/incidencias` con body:
```json
{
  "equipo_id":            <id o null>,
  "componente_id":        <id o null>,
  "titulo":               "...",
  "descripcion_problema": "...",
  "prioridad":            "media",
  "asignado_a":           "..." | null,
  "en_garantia":          true | false | null,
  "fecha_apertura":       "YYYY-MM-DD"
}
```
Solo incluye `equipo_id` / `componente_id` cuando no sean null.

**Manejo de errores:**
- **422 Unprocessable Entity:** el backend lo devuelve si ningún sujeto está relleno (`equipo_id` y `componente_id` ambos null). Muestra el `detail` en un banner de error claro dentro del formulario ("Debes indicar al menos un equipo o componente").
- **404 Not Found:** FK inválida (id de equipo o componente que no existe). Muestra toast de error con el `detail` del backend.

Tras creación exitosa: navega automáticamente a `/incidencias/{id}` (ficha del expediente recién creado).

### Layout

Página centrada (max-width ~720 px), card única con título "Nueva incidencia" (Open Sans). Botones al pie: **"Cancelar"** (gris, vuelve a `/incidencias`) y **"Crear expediente"** (primario lila). El botón de submit se deshabilita mientras se envía la petición (spinner).

---

## Parte B — Hooks en pantallas existentes

### B1 — Sección "Incidencias" en la ficha de equipo (prompt 02, ruta `/equipos/$id`)

En la ficha de equipo (`GET /api/equipos/{id}` → `EquipoFicha`), añade una nueva sección al final del cuerpo:

**Card "Incidencias del equipo":**
- Carga `GET /api/incidencias?equipo_id={id}` al montar la ficha (en paralelo con la carga principal).
- Muestra una tabla compacta con columnas: Código (`codigo`), Título (`titulo`), Estado (badge), Prioridad (badge), Asignado a, Fecha apertura. Cada fila clicable → `/incidencias/{id}`.
- Si está vacío: "Sin incidencias registradas".
- Botón **"+ Abrir incidencia"** en la cabecera de la card → navega a `/incidencias/nueva?equipo_id={id}` (pre-rellena el selector de equipo).

No modifiques nada más de la ficha de equipo (ni la cabecera, ni los modales existentes, ni los historiales).

### B2 — Campo opcional `incidencia_id` en los modales de trazabilidad (prompt 02)

Los modales **Registrar movimiento**, **Montar componente**, **Desmontar componente** y **Sustituir componente** ahora pueden vincular la acción a una incidencia abierta. Añade en cada uno de estos modales:

**Campo opcional "¿Forma parte de una incidencia abierta?" (selector):**
- Carga `GET /api/incidencias?abiertas=true` al abrir el modal.
- Muestra un select con opción "— Ninguna —" (valor null) y, por cada incidencia abierta, `codigo — titulo` (p.ej. `RMA-0001 — Fuente no enciende`).
- Si el usuario selecciona una incidencia, añade `"incidencia_id": <id>` al body del POST. Si deja "— Ninguna —", no incluyas el campo.
- El campo es completamente opcional: no valides ni bloquees el submit si no se elige ninguna.

Endpoints afectados (body existente + `incidencia_id?`):
- `POST /api/equipos/{id}/movimientos`
- `POST /api/componentes/{id}/montar`
- `POST /api/componentes/{id}/desmontar`
- `POST /api/equipos/{id}/sustituir-componente`

No toques ninguna otra parte de los modales existentes (campos, validaciones, lógica post-submit).

---

## Detalle visual

- Lila como acento primario (botón "Crear expediente", foco de inputs).
- Badge de prioridad junto al select cambia de color en tiempo real al seleccionar.
- Datos (fechas, códigos) en Roboto; etiquetas en Open Sans.

No inventes endpoints ni campos. Usa únicamente los indicados.

---

> **Nota de contrato**
>
> `POST /api/incidencias` acepta: `equipo_id?`, `componente_id?`, `titulo`, `descripcion_problema`, `prioridad?` (`baja|media|alta`, default `media`), `asignado_a?`, `en_garantia?` (`true|false|null`), `fecha_apertura` (ISO date string). Devuelve `IncidenciaOut` (201) con `codigo` asignado automáticamente (`RMA-NNNN`) y `estado: "abierta"`.
>
> Campos exactos de `IncidenciaOut`: `id`, `codigo`, `equipo_id`, `componente_id`, `titulo`, `descripcion_problema`, `prioridad`, `estado`, `asignado_a`, `en_garantia`, `diagnostico`, `resolucion`, `fecha_apertura`, `fecha_diagnostico`, `fecha_inicio_reparacion`, `fecha_resolucion`, `fecha_cierre`, `notas`.
>
> Los endpoints de trazabilidad aceptan ahora `incidencia_id?` (FK opcional a una incidencia existente):
> - `POST /api/equipos/{id}/movimientos` → body: `{ ubicacion_destino_id, fecha, motivo, usuario?, notas?, incidencia_id? }`
> - `POST /api/componentes/{id}/montar` → body: `{ equipo_id, posicion?, fecha, motivo, usuario?, notas?, incidencia_id? }`
> - `POST /api/componentes/{id}/desmontar` → body: `{ fecha, motivo, usuario?, notas?, incidencia_id? }`
> - `POST /api/equipos/{id}/sustituir-componente` → body: `{ componente_saliente_id, componente_entrante_id, posicion?, fecha, motivo, usuario?, notas?, incidencia_id? }`
