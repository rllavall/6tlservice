# Prompt Lovable 09 — Incidencias / RMA: ficha (expediente)

> Requiere prompts 00 y 08. Mantén la identidad 6TL (lila `#9e007e`, Open Sans/Roboto). NO toques el shell, el cliente API ni ninguna pantalla existente. Añade la ruta `/incidencias/$id`.

---

Implementa la **ficha de incidencia (expediente)** en `/incidencias/$id`.

## Carga de datos

`GET /api/incidencias/{id}` devuelve un objeto `IncidenciaFicha`:
```
{
  incidencia:           IncidenciaOut,
  equipo:               { id, numero_serie, producto_id, cliente_id, fecha_fabricacion, fecha_entrega, estado, notas } | null,
  componente:           { id, numero_serie, producto_id, equipo_id, posicion, fecha_montaje, notas } | null,
  cliente:              { id, nombre, cif, persona_contacto, email_contacto, telefono_contacto, notas } | null,
  cambios_configuracion: [ { id, componente_id, equipo_id, accion, posicion, fecha, motivo, usuario, notas } ],
  movimientos:          [ { id, equipo_id, ubicacion_destino_id, fecha, motivo, usuario, notas } ]
}
```

Para resolver nombres de ubicaciones en `movimientos`, carga `GET /api/ubicaciones` y mapea `ubicacion_destino_id → nombre`.
Para resolver part_number/descripcion de componentes en `cambios_configuracion`, carga `GET /api/productos` y mapea `producto_id → part_number + descripcion` (si tienes el componente desde `GET /api/componentes/{id}`).

Tras cada acción con éxito: re-fetch de toda la ficha y toast de confirmación. En error, muestra el `detail` del backend.

## Layout

### Cabecera (card destacada)

- **Código** grande (`incidencia.codigo`, Roboto monospace, muy visible, p.ej. `RMA-0001`) y, junto a él, el badge de **estado** (mismos colores que en la lista: gris/azul/ámbar/verde/neutro).
- Datos secundarios en chips: **Prioridad** (badge de color), **Asignado a**, **En garantía** (Sí/No/—), **Equipo** (enlace a `/equipos/{id}` si `equipo_id` existe), **Cliente** (enlace a `/clientes/{id}` si `cliente_id` existe).
- Acciones a la derecha (ver sección Acciones).

### Línea de tiempo de fases

Card "Fases del expediente" con **5 hitos** en línea de tiempo horizontal (o vertical en móvil). Cada hito tiene:
- Nombre de la fase: **Apertura** · **Diagnóstico** · **En reparación** · **Resuelta** · **Cerrada**
- Fecha correspondiente: `fecha_apertura` · `fecha_diagnostico` · `fecha_inicio_reparacion` · `fecha_resolucion` · `fecha_cierre`
- Punto lila si la fecha está rellena (fase alcanzada); punto gris si es null (fase pendiente).
- La fase activa (la más reciente alcanzada) se resalta con punto lila grande.

### Cuerpo (dos columnas, responsive)

**Columna izquierda:**

Card **"Problema"**: `titulo` (Open Sans, semibold) + `descripcion_problema` (Roboto).

Card **"Diagnóstico / Resolución"**: muestra `diagnostico` y `resolucion` (cada uno con su etiqueta). Si están vacíos, texto gris "Sin registrar". Botón editar pequeño en la cabecera de la card abre el modal de edición (ver Acciones).

Card **"Notas"**: `notas` libre. Mismo botón editar.

**Columna derecha:**

Card **"Equipo / Componente / Cliente"**: datos de `equipo` (numero_serie, enlace a ficha de equipo), `componente` (numero_serie, posicion), `cliente` (nombre, persona de contacto, email), con enlace a las pantallas correspondientes. Muestra solo los bloques que no sean null.

Card **"Componentes sustituidos en esta reparación"** (`cambios_configuracion`): tabla con fecha, acción (badge lila "montaje" / gris "desmontaje"), componente (part_number — serie), posición, motivo, usuario. Si está vacío: "Sin cambios de configuración registrados".

Card **"Movimientos de este expediente"** (`movimientos`): lista de hitos con fecha, ubicación destino (nombre resuelto), motivo (badge), usuario. Si está vacío: "Sin movimientos registrados".

## Acciones

Todas las acciones se ejecutan desde la ficha, en modal o inline. Agrupa los botones de acción en un menú desplegable o botonera discreta en la cabecera.

**1) Avanzar estado** — `POST /api/incidencias/{id}/transicion`
Body: `{ nuevo_estado, fecha? }`.
Muestra solo la transición válida desde el estado actual:
- `abierta` → botón **"Iniciar diagnóstico"** (nuevo_estado: `diagnostico`)
- `diagnostico` → botón **"Iniciar reparación"** (nuevo_estado: `en_reparacion`)
- `en_reparacion` → botón **"Marcar como resuelta"** (nuevo_estado: `resuelta`); ANTES de enviar la transición, comprueba que `incidencia.resolucion` no sea null/vacío. Si lo está, abre primero el modal de edición enfocado en el campo `resolucion` y no envíes la transición hasta que se guarde.
- `resuelta` → botón **"Cerrar expediente"** (nuevo_estado: `cerrada`)

Incluye un campo `fecha` (date, opcional, por defecto hoy) en el modal de confirmación de cada transición.

**2) Reabrir** — `POST /api/incidencias/{id}/transicion`
Body: `{ nuevo_estado: "en_reparacion" }`.
Botón **"Reabrir"** visible solo cuando `estado ∈ {resuelta, cerrada}`.

**3) Editar** — `PATCH /api/incidencias/{id}`
Body libre (campos opcionales): `titulo`, `descripcion_problema`, `prioridad`, `asignado_a`, `en_garantia`, `diagnostico`, `resolucion`, `notas`.
Modal con todos los campos editables. Solo envía los campos que el usuario modifique (partial update).

**4) Borrar** — `DELETE /api/incidencias/{id}`
Botón visible **solo si `estado === "abierta"`**. Requiere confirmación explícita ("Borrar expediente — esta acción es irreversible"). Tras borrar con éxito, navega a `/incidencias`.

## Detalle visual

- Punto/hito de la línea de tiempo en lila. Fases alcanzadas: línea continua lila entre puntos. Fases pendientes: línea punteada gris.
- Badges de motivo (entrega/traslado/reparacion/devolucion) discretos.
- Datos (código, fechas, series) en Roboto; etiquetas y títulos en Open Sans.
- Mantén el lila como único acento de marca; verde/ámbar/rojo solo para estados funcionales.

No inventes endpoints ni campos. Si el dato no lo da la API, resuélvelo con los lookups indicados.

---

> **Nota de contrato — `IncidenciaFicha`**
> La llamada `GET /api/incidencias/{id}` devuelve: `incidencia` (objeto `IncidenciaOut`), `equipo`, `componente`, `cliente`, `cambios_configuracion[]`, `movimientos[]`.
>
> Campos exactos de `IncidenciaOut`: `id`, `codigo`, `equipo_id`, `componente_id`, `titulo`, `descripcion_problema`, `prioridad`, `estado`, `asignado_a`, `en_garantia`, `diagnostico`, `resolucion`, `fecha_apertura`, `fecha_diagnostico`, `fecha_inicio_reparacion`, `fecha_resolucion`, `fecha_cierre`, `notas`.
>
> Transiciones válidas: `abierta→diagnostico`, `diagnostico→en_reparacion`, `en_reparacion→resuelta` (requiere `resolucion`), `resuelta→cerrada`. Reabrir: `resuelta|cerrada→en_reparacion`. El backend rechaza transiciones inválidas con 409.
