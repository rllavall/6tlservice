# Prompt Lovable 02 — Ficha de equipo (pantalla central) + acciones

> Requiere prompts 00 y 01. Mantén la identidad 6TL (lila `#9e007e`, Open Sans/Roboto). NO modifiques el shell, el cliente API ni la home; añade la ruta `/equipos/:id`.

---

Implementa la **ficha de equipo** en `/equipos/:id`. Es la pantalla central de la app.

## Carga de datos
`GET /api/equipos/{id}` devuelve **toda la ficha compuesta** en una sola llamada (`EquipoFicha`):
```
{
  equipo:        { id, numero_serie, producto_id, cliente_id, fecha_fabricacion, fecha_entrega, estado, notas },
  producto:      { id, part_number, tipo, descripcion, fabricante, modelo, notas },
  cliente:       { id, nombre, cif, persona_contacto, email_contacto, telefono_contacto, notas } | null,
  ubicacion_actual: { id, nombre, tipo, cliente_id, direccion, codigo_postal, ciudad, provincia, pais, notas } | null,
  componentes:   [ { id, numero_serie, producto_id, equipo_id, posicion, fecha_montaje, notas } ],
  historial_movimientos:   [ { id, equipo_id, ubicacion_destino_id, fecha, motivo, usuario, notas } ],
  historial_configuracion: [ { id, componente_id, equipo_id, accion, posicion, fecha, motivo, usuario, notas } ]
}
```
Las listas vienen ordenadas de más reciente a más antigua. `ubicacion_actual` es `null` si el equipo aún no tiene movimientos (en ese caso muéstralo como "Sede 6TL" en gris, con matiz "sin movimientos registrados").

Para mostrar el part number/descripcion de cada **componente** (la ficha solo trae `producto_id`), carga `GET /api/productos?tipo=componente` y mapea `producto_id` → part_number + descripcion. Igual para resolver nombres de ubicaciones en el historial de movimientos: carga `GET /api/ubicaciones` y mapea `ubicacion_destino_id` → nombre.

## Layout

**Cabecera (card destacada):**
- Grande: `numero_serie` (Roboto, muy visible) y debajo el modelo (`producto.part_number` — `producto.descripcion`).
- Chips/datos: **Ubicación actual** (badge lila con icono map-pin: `ubicacion_actual.nombre`), **Estado** (badge operativo/baja), **Cliente** (`cliente.nombre` desde el objeto `cliente` de la ficha; "—" si null; opcionalmente enlazable a `/clientes`), **Fecha de entrega**, **Fabricante**.
- Acciones a la derecha: botón secundario **"Editar"** (→ `/equipos/{id}/editar`, prompt 03) y botón primario lila **"Registrar movimiento"** (abre modal, ver abajo).

**Cuerpo en dos columnas (responsive a una en móvil):**

### Columna izquierda — Configuración actual
Card "Configuración actual" con la tabla de `componentes` montados ahora:
- Columnas: Posición (`posicion`), Componente (part_number — descripcion), Nº de serie (Roboto), Fecha montaje.
- Acciones por fila: **Desmontar**, **Sustituir** (iconos + menú).
- Botón en la cabecera de la card: **"+ Montar componente"**.
- Si está vacío: "Sin componentes montados".
- Si vienes del buscador global resaltando un componente (query param), destácalo brevemente (fondo lila-50).

### Columna derecha — Historiales (dos pestañas o dos cards apiladas)
1. **Historial de ubicación** (`historial_movimientos`) como **línea de tiempo** vertical: cada hito muestra fecha, ubicación destino (nombre), motivo (badge: entrega/traslado/reparacion/devolucion) y usuario/notas. El más reciente arriba, marcado como "actual".
2. **Historial de configuración** (`historial_configuracion`) como línea de tiempo: cada evento muestra fecha, acción (badge lila "montaje" / gris "desmontaje"), el componente (part_number + serie), posición, motivo (entrega_inicial/sustitucion/upgrade/reparacion/retirada) y usuario/notas. Es la traza de cómo ha cambiado la configuración del ATE en el tiempo.

## Modales de acción (todas las acciones se hacen desde la ficha, en modal)

Tras cada acción con éxito: cierra modal, **re-fetch de la ficha**, toast de confirmación. En error, muestra el `detail` del backend en el modal (p.ej. 409 "El componente ya está montado").

**1) Registrar movimiento** — `POST /api/equipos/{id}/movimientos`
Body: `{ ubicacion_destino_id, fecha, motivo, usuario?, notas? }`, `motivo ∈ entrega|traslado|reparacion|devolucion`.
Campos: selector de ubicación destino (desde `GET /api/ubicaciones`), fecha (date), motivo (select), usuario (texto), notas (textarea).

**2) Montar componente** — `POST /api/componentes/{componente_id}/montar`
Body: `{ equipo_id, posicion?, fecha, motivo, usuario?, notas? }`, `motivo ∈ entrega_inicial|sustitucion|upgrade|reparacion|retirada`.
El `equipo_id` es el de la ficha actual. Para elegir el componente a montar, ofrece un selector de **componentes en stock** (no montados): cárgalos con `GET /api/componentes?equipo_id=` … no existe filtro "sin asignar"; en su lugar carga `GET /api/componentes`, filtra en cliente los que tienen `equipo_id === null`, y muéstralos (part_number — serie). Campos: componente (select), posición (texto, p.ej. "PXI ranura 3"), fecha, motivo, usuario, notas.

**3) Desmontar componente** — `POST /api/componentes/{componente_id}/desmontar`
Body: `{ fecha, motivo, usuario?, notas? }`. Confirmación + campos fecha/motivo/usuario/notas.

**4) Sustituir componente** — `POST /api/equipos/{id}/sustituir-componente`
Body: `{ componente_saliente_id, componente_entrante_id, posicion?, fecha, motivo, usuario?, notas? }`.
El saliente es la fila desde la que abres la acción. El entrante: selector de componentes en stock (`equipo_id === null`). Posición por defecto = la del saliente. Devuelve `{ desmontaje, montaje }`; toast "Componente sustituido".

## Detalle visual
Líneas de tiempo con el punto/hito en lila. Badges de motivos discretos. Datos numéricos (series, fechas) en Roboto. Mantén el lila como único acento de marca; verde/gris solo para estado operativo/baja.

No inventes endpoints ni campos. Si necesitas un dato que la API no da, resuélvelo con los lookups indicados (`/api/productos`, `/api/ubicaciones`, `/api/componentes`).
