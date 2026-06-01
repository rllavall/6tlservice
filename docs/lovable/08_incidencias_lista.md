# Prompt Lovable 08 — Incidencias / RMA: lista (sub-proyecto 2)

> Requiere prompts 00 y 01. Mantén la identidad 6TL (lila `#9e007e`, Open Sans/Roboto). NO modifiques el shell, el cliente API ni ninguna pantalla existente. Añade la ruta `/incidencias` a la navegación (ítem "Incidencias", icono `alert-circle`).

---

Implementa la pantalla **lista de incidencias** en `/incidencias`. Una incidencia es un expediente de avería / RMA asociado a un equipo o componente.

## Carga de datos

`GET /api/incidencias` devuelve una lista de objetos `IncidenciaOut`. Acepta los siguientes query params que el frontend debe enviar según los filtros activos:

| Param | Tipo | Descripción |
|---|---|---|
| `estado` | string | filtra por estado exacto |
| `prioridad` | string | filtra por prioridad exacta |
| `abiertas` | boolean | `true` → solo estado `abierta` (ignora `estado` si se envía) |

Para resolver el **número de serie** del equipo o componente asociado, carga en paralelo `GET /api/equipos` y `GET /api/componentes` y mapea por id.

## Layout

Título **"Incidencias"** (Open Sans) + botón primario lila **"+ Nueva incidencia"** → navega a `/incidencias/nueva`.

### Filtros (barra sobre la tabla)
- **Estado** (select): Todos / abierta / diagnostico / en_reparacion / resuelta / cerrada.
- **Prioridad** (select): Todas / baja / media / alta / critica.
- **Solo abiertas** (toggle/switch): cuando está activo envía `?abiertas=true` y deshabilita el selector de estado (son mutuamente excluyentes con `estado`).

Cuando cambia cualquier filtro, re-lanza `GET /api/incidencias` con los params correspondientes.

### Tabla

Columnas:

| Columna | Campo | Observaciones |
|---|---|---|
| Código | `codigo` | Roboto, estilo monoespaciado, destacado (p.ej. `RMA-0001`) |
| Equipo / Componente | `equipo_id` / `componente_id` | Muestra el `numero_serie` del equipo si tiene `equipo_id`; si solo tiene `componente_id`, muestra el número de serie del componente; si tiene ambos, muestra el equipo |
| Título | `titulo` | Texto libre, truncado a 1 línea |
| Prioridad | `prioridad` | Badge: `critica` → rojo `#c62828`, `alta` → ámbar `#b26a00`, `media` → azul `#1565c0`, `baja` → gris `#6b6b6e` |
| Estado | `estado` | Badge con color: `abierta` → gris, `diagnostico` → azul `#1565c0`, `en_reparacion` → ámbar `#b26a00`, `resuelta` → verde `#2e7d32`, `cerrada` → neutro/oscuro |
| Asignado a | `asignado_a` | Texto; "—" si null |
| Fecha apertura | `fecha_apertura` | Formato `dd/mm/aaaa`, Roboto |

Cada fila es clicable → navega a `/incidencias/{id}`.

Estado vacío: "Sin incidencias — crea la primera" con isotipo gris claro.

## Detalle visual

- Lila como único acento de marca (botón, hover).
- Badges de estado y prioridad discretos (texto + fondo suave del color funcional; no fondos saturados).
- Datos (código, fechas) en Roboto; etiquetas en Open Sans.
- Ancho de columna `Código` fijo y estrecho; `Título` flexible.

No inventes endpoints ni campos. Si el dato no viene en la lista, resuélvelo con los lookups indicados.

---

> **Nota de contrato — `IncidenciaOut`**
> Campos exactos del objeto devuelto por `GET /api/incidencias` (lista de `IncidenciaOut`):
> `id`, `codigo`, `equipo_id`, `componente_id`, `titulo`, `descripcion_problema`, `prioridad`, `estado`, `asignado_a`, `en_garantia`, `diagnostico`, `resolucion`, `fecha_apertura`, `fecha_diagnostico`, `fecha_inicio_reparacion`, `fecha_resolucion`, `fecha_cierre`, `notas`.
> Valores de `estado`: `abierta` · `diagnostico` · `en_reparacion` · `resuelta` · `cerrada`.
> Valores de `prioridad`: `baja` · `media` · `alta` · `critica`.
