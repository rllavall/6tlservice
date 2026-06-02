# 6TL Postventa — Sub-proyecto 2: Incidencias / RMA — Diseño

> Segundo sub-proyecto de la plataforma de postventa de 6TL. Cuelga de la columna vertebral
> (trazabilidad + base instalada) construida en el sub-proyecto 1. **Este documento cubre
> únicamente el sub-proyecto 2.** Cada sub-proyecto tiene su ciclo spec → plan → implementación.

## Contexto y objetivo

La base instalada ya permite saber qué equipos hay, de qué componentes serializados se componen,
dónde están y cómo ha cambiado su configuración en el tiempo. El sub-proyecto 2 añade el **núcleo
de postventa**: registrar averías/incidencias contra un equipo o componente y seguir su flujo de
reparación, enlazando las acciones de trazabilidad que ya existen (sustituciones de componentes,
movimientos) para que cada reparación quede como un **expediente** consultable.

Es la capacidad que más valor de postventa aporta y la que genera los datos sobre los que se apoyarán
fases posteriores (fiabilidad/MTBF, garantías formales, KPIs).

## Decisiones de alcance

- **Flujo de reparación completo** (no ligero, no configurable): cinco estados fijos
  `abierta → diagnostico → en_reparacion → resuelta → cerrada`, con técnico asignado y fecha por fase.
- **Integración "expediente que enlaza"** (no orquesta, no independiente): la incidencia referencia
  el equipo/componente y *enlaza* eventos de trazabilidad ya existentes; **no** automatiza movimientos
  ni dispara efectos secundarios. Una sola fuente de verdad (los `CambioConfiguracion`/`Movimiento`
  existentes), etiquetados con la incidencia en el momento real de la acción.
- **Sujeto: equipo o componente** — una incidencia se abre contra un equipo, contra un componente
  serializado, o ambos; regla: **al menos uno**.
- **Usuarios:** solo equipo interno de 6TL (igual que sub-proyecto 1). Técnico asignado = texto libre,
  consistente con el campo `usuario` de los eventos existentes. Sin entidad Técnico, sin portal externo.
- **Garantías:** fuera de alcance como motor. Solo un flag manual `en_garantia` (nullable) en la
  incidencia para anotación; la lógica de garantías es un sub-proyecto posterior.

### Fuera de alcance (fases posteriores)

Lógica de garantías (periodos, cálculo dentro/fuera), análisis de fiabilidad/MTBF, costes/facturación
de reparaciones, SLA, notificaciones/alertas, portal de cliente, adjuntos/documentos, integraciones.

## Arquitectura

Misma arquitectura que el sub-proyecto 1: backend FastAPI + SQLAlchemy + SQLite (`:8020`), frontend
Lovable (TanStack Start) como submódulo. Se añade una entidad, un router y un servicio de transiciones;
se tocan de forma **aditiva y retrocompatible** dos tablas y cuatro endpoints existentes.

### 1. Entidad `Incidencia` (tabla `incidencias`)

Sigue el estilo existente (PK int autoincrement, columnas `String`/`Date`, sin timestamps automáticos,
enums como listas a nivel de módulo).

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `codigo` | str **unique** | RMA legible autogenerado: `RMA-0001`, `RMA-0002`… (n = max actual + 1) |
| `equipo_id` | FK→equipos, nullable | |
| `componente_id` | FK→componentes, nullable | regla: al menos uno de equipo/componente |
| `titulo` | str | resumen corto |
| `descripcion_problema` | str | lo reportado por el cliente |
| `prioridad` | str | `baja`/`media`/`alta`, default `media` |
| `estado` | str | `abierta`/`diagnostico`/`en_reparacion`/`resuelta`/`cerrada`, default `abierta` |
| `asignado_a` | str, nullable | técnico (texto libre) |
| `en_garantia` | bool, nullable | flag manual; `null` = sin determinar |
| `diagnostico` | str, nullable | se rellena en fase diagnóstico |
| `resolucion` | str, nullable | se rellena al resolver |
| `fecha_apertura` | date | obligatoria |
| `fecha_diagnostico` | date, nullable | sellada al entrar en `diagnostico` |
| `fecha_inicio_reparacion` | date, nullable | sellada al entrar en `en_reparacion` |
| `fecha_resolucion` | date, nullable | sellada al entrar en `resuelta` |
| `fecha_cierre` | date, nullable | sellada al entrar en `cerrada` |
| `notas` | str, nullable | |

Nuevas constantes de módulo:
- `ESTADOS_INCIDENCIA = ["abierta", "diagnostico", "en_reparacion", "resuelta", "cerrada"]`
- `PRIORIDADES_INCIDENCIA = ["baja", "media", "alta"]`

El `cliente` **no** se almacena en la incidencia: se deriva del equipo al componer la ficha (o queda
vacío si el sujeto es un componente en stock sin equipo).

### 2. Enlace con la trazabilidad existente (enfoque A)

Se añade una FK **opcional** `incidencia_id` (nullable, default `NULL`) a dos tablas existentes:

- `CambioConfiguracion.incidencia_id` → `incidencias.id`
- `Movimiento.incidencia_id` → `incidencias.id`

Ambas por defecto `NULL` ⇒ totalmente retrocompatible. Cuando un técnico ejecuta una acción de
trazabilidad *en el contexto de una reparación*, pasa el `incidencia_id` y el evento queda etiquetado
y visible en el expediente. Sin `incidencia_id`, comportamiento idéntico al actual.

## API

Router nuevo `incidencias.py` montado en `/api/incidencias`:

| Método | Ruta | Comportamiento |
|---|---|---|
| `GET` | `/api/incidencias` | Lista. Filtros opcionales: `estado`, `prioridad`, `equipo_id`, `componente_id`, `asignado_a`, `abiertas` (bool; excluye `cerrada`). → `IncidenciaOut[]` |
| `POST` | `/api/incidencias` | Crea. Valida ≥1 sujeto (→422) y existencia de FKs (→404). Genera `codigo`, fija `estado=abierta` + `fecha_apertura`. → 201 `IncidenciaOut` |
| `GET` | `/api/incidencias/{id}` | **Expediente**: incidencia + snapshot equipo/componente/cliente + `cambios_configuracion` enlazados + `movimientos` enlazados. → `IncidenciaFicha` |
| `PATCH` | `/api/incidencias/{id}` | Edita campos libres (titulo, descripcion_problema, prioridad, asignado_a, en_garantia, diagnostico, resolucion, notas). **No** cambia estado. |
| `POST` | `/api/incidencias/{id}/transicion` | Avanza estado con guardas + sella fecha. Body `{nuevo_estado, fecha?}`. → `IncidenciaOut` |
| `DELETE` | `/api/incidencias/{id}` | Solo si `estado=abierta` y sin eventos enlazados → 204; si no → 409. |

### Cambios retrocompatibles en endpoints existentes

Aceptan un `incidencia_id` **opcional** en el body; si se da, se propaga al evento creado:

- `POST /api/equipos/{id}/sustituir-componente`
- `POST /api/componentes/{id}/montar`
- `POST /api/componentes/{id}/desmontar`
- `POST /api/movimientos`

### Enriquecer la ficha de equipo

`GET /api/equipos/{id}` (`EquipoFicha`) añade un campo aditivo `incidencias: IncidenciaOut[]` con las
incidencias de ese equipo, para enlazar desde la pantalla central.

## Reglas de negocio / máquina de estados

Transiciones permitidas (lineales hacia delante):

```
abierta ──▶ diagnostico ──▶ en_reparacion ──▶ resuelta ──▶ cerrada
```

- Cada transición **sella su fecha** correspondiente; si el body no trae `fecha`, se usa hoy.
- **Saltos prohibidos** (p. ej. `abierta`→`resuelta`) → **409**.
- **Retroceso prohibido**, con **una excepción: reabrir** `resuelta`/`cerrada` → `en_reparacion`
  (vuelve a fallar); al reabrir se limpian `fecha_resolucion`/`fecha_cierre` y se conserva la
  `fecha_inicio_reparacion` original.
- **Guarda de contenido:** para pasar a `resuelta` se exige `resolucion` no vacía (→409 si falta).
  El `diagnostico` se recomienda pero no se obliga.

Validaciones al crear:
- Al menos uno de `equipo_id`/`componente_id` (→422 si ninguno).
- FKs deben existir (→404).
- Si se da `componente_id` de un componente montado, su equipo se conoce (informativo en el
  expediente); no se obliga a dar también `equipo_id`.

Generación de `codigo`: secuencial `RMA-{n:04d}` calculado al crear (n = max actual + 1). App interna
monousuario, mismo supuesto de concurrencia que el resto del sistema.

## Frontend (Lovable)

Reutiliza el design system instalado (prompt 00, identidad 6TL lila). Prompts nuevos `08+` en
`docs/lovable/`:

| # | Pantalla | Contenido |
|---|---|---|
| 08 | Lista de incidencias | Tabla (`codigo`, equipo/componente, título, prioridad, estado, asignado_a, fecha). Filtros estado/prioridad + toggle "solo abiertas". Badges de estado con color. Botón "Nueva incidencia". |
| 09 | Ficha de incidencia (expediente) | Cabecera `codigo` + badge estado + **timeline** de las 5 fases con fechas. Datos equipo/componente/cliente (enlazados). Secciones: componentes sustituidos en la reparación (config events enlazados) y movimientos enlazados. Acciones: avanzar estado (con el campo que exija la guarda), asignar, editar, reabrir. |
| 10 | Alta de incidencia | Selector equipo **o** componente (≥1), título, descripción, prioridad, asignado_a, en_garantia. Accesible desde la lista y desde la ficha de equipo. |

Enganches en pantallas existentes:
- Ficha de equipo (prompt 02): sección "Incidencias" (de `EquipoFicha.incidencias`) + botón "Abrir
  incidencia" precargando el equipo.
- Modales sustituir/montar/desmontar/mover: selector opcional "¿Forma parte de una incidencia abierta?"
  que pasa `incidencia_id`.

Validación de contrato tras pegar cada prompt (método habitual: nombres de campo exactos; no fiarse de
"errores CORS" engañosos).

## Testing

TDD por archivo, patrón existente (`pytest`, DB en memoria por test, fixtures en `conftest.py`):

| Archivo | Cubre |
|---|---|
| `test_incidencias.py` | CRUD: crear (genera `codigo` secuencial), guarda ≥1 sujeto (→422), FKs inexistentes (→404), listar con cada filtro, PATCH de campos libres, borrado guardado (abierta sin enlaces→204; con enlaces o no-abierta→409) |
| `test_incidencia_transiciones.py` | Cadena lineal válida + sellado de fechas, salto prohibido (→409), retroceso prohibido (→409), reabrir resuelta/cerrada→en_reparacion limpia fechas, `resolucion` obligatoria al pasar a `resuelta` (→409) |
| `test_incidencia_enlace.py` | sustituir/montar/desmontar/mover **con** `incidencia_id` etiquetan el evento y aparecen en el expediente; **sin** `incidencia_id` funcionan igual (retrocompat); `EquipoFicha.incidencias` lista las del equipo |
| Tests existentes | Los 50 actuales siguen verdes con el `incidencia_id` opcional añadido |

**Criterio de cierre:** suite completa verde (50 actuales + nuevos), expediente compuesto
correctamente, retrocompatibilidad demostrada. Smoke en vivo con `_seed_demo.py` ampliado (una
incidencia de ejemplo).
