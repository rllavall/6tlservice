# Diseño — Contratos de mantenimiento, P/N de fabricante y acciones de preventivo

Fecha: 2026-06-05 · Proyecto: 6TL Postventa ("6tlservice") · Backend FastAPI :8020 + frontend Lovable.

## Contexto y motivación

Tres cambios pedidos por el usuario, en el mismo módulo de postventa:

1. **Configuración** — añadir el **P/N del fabricante** a los componentes (hoy solo existe el `part_number`
   interno 6TL). Sin campo cantidad: dos componentes iguales se registran como dos líneas (dos `Componente`).
2. **Contratos de mantenimiento** — concepto inexistente hoy. Un equipo puede estar o no bajo contrato; hay
   que distinguirlo y gestionar los contratos. Basado en la propuesta de servicio iUTB INDRA: niveles de
   servicio **Bronze / Silver / Gold**.
3. **Acciones e informes de preventivo** — registrar las intervenciones preventivas (ejecución + reporte de
   salud del banco) por equipo, con posibilidad de generar una incidencia correctiva si procede.

NO incluye (YAGNI / fases futuras): planificador/calendario de preventivo, facturación/económico del
contrato, gestión de repuestos, campañas de calibración. El preventivo de esta fase es **registro de
acciones realizadas + próxima fecha como dato**, no un scheduler.

## Modelo de datos

### 1. `Producto.pn_fabricante` (nuevo campo)
- Columna `pn_fabricante: str | None` en `productos`. Atributo del maestro (todos los componentes de ese
  part_number comparten el P/N de fabricante). Se rellena en el catálogo.
- Migración: `migrations.py` añade la columna a la tabla existente (idempotente, add-column si falta).

### 2. `ContratoMantenimiento` (tabla nueva `contratos`)
Campos:
- `id` PK
- `codigo` str único — formato `CTR-NNNN` (autogenerado, helper análogo a `solicitudes_service.generar_codigo`)
- `cliente_id` FK → `clientes` (titular del contrato)
- `nivel` str — `Literal["bronze","silver","gold"]`
- `fecha_inicio` date
- `fecha_fin` date
- `cancelado` bool (default False)
- `notas` str | None

**Estado derivado** (property, NO columna), calculado con la fecha de hoy — análogo a `garantia.estado_garantia`:
- `cancelado` → `"cancelado"`
- hoy < `fecha_inicio` → `"pendiente"`
- `fecha_inicio` ≤ hoy ≤ `fecha_fin` → `"vigente"`
- hoy > `fecha_fin` → `"vencido"`
- `vigente: bool` property = `estado == "vigente"`

**Atributos del nivel** — NO se guardan; se derivan de `nivel` con una tabla en código (módulo
`app/contratos_niveles.py` o constante en el servicio):

| nivel  | preventivo  | soporte          | respuesta   |
|--------|-------------|------------------|-------------|
| bronze | anual       | horario laborable| estándar    |
| silver | semestral   | horario laborable| mejorada    |
| gold   | semestral   | 24/7             | prioritaria |

Se exponen en el schema de salida para mostrarlos en la ficha (campo `nivel_detalle` o equivalente).

### 3. `Equipo.contrato_id` (nuevo campo) + derivación
- Columna `contrato_id: int | None` FK → `contratos`. Relación **1 contrato → N equipos** (el contrato es
  el "actual"; sin histórico de contratos por equipo — YAGNI).
- Property derivada `bajo_contrato: bool` = `contrato_id` no nulo **y** el contrato vinculado está `vigente`.
- Migración: add-column en `migrations.py`.

### 4. `AccionPreventiva` (tabla nueva `acciones_preventivo`)
Campos:
- `id` PK
- `equipo_id` FK → `equipos` (obligatorio)
- `contrato_id` FK → `contratos` | None — se auto-rellena con el contrato vigente del equipo en el momento
  de crear la acción (snapshot de bajo qué contrato se hizo); editable/anulable.
- `fecha` date (de la intervención)
- `tecnico` str | None
- `tipo` str — `Literal["on_site","remoto"]`
- `veredicto` str — `Literal["ok","con_observaciones","requiere_accion"]` (estado de salud del banco)
- `informe` str | None (texto del reporte / observaciones)
- `proxima_fecha` date | None — sugerida al crear a partir del nivel del contrato (anual = +12 meses,
  semestral = +6 meses) sobre `fecha`; editable. Si no hay contrato/nivel, queda vacía y la pone el usuario.
- `incidencia_id` FK → `incidencias` | None (si la acción generó una incidencia correctiva)

Tabla nueva → `create_all` la crea; no necesita migración de columnas.

## Servicios / lógica

- `app/contratos_service.py`: `generar_codigo(db)` (`CTR-NNNN`), helpers de asignación de equipos con
  validación de cliente.
- Validación al **vincular un equipo a un contrato**: si `equipo.cliente_id` está fijado y difiere de
  `contrato.cliente_id` → error de negocio → HTTP 409. Si el equipo no tiene cliente, se permite (no se
  fuerza). Desvincular siempre permitido.
- `app/preventivo_service.py`: crear acción (auto-asocia contrato vigente, sugiere `proxima_fecha` del
  nivel), y `generar_incidencia(db, accion, payload)` que crea una `Incidencia` correctiva enlazada
  (reutiliza `incidencias_service.generar_codigo`, tipo por defecto `soporte_tecnico`/correctivo, estado
  `abierta`, equipo = el de la acción) y fija `accion.incidencia_id`. Mismo patrón que `solicitudes_service.aprobar`.
- Cobertura de contrato en incidencias: **calculada en vivo** (no snapshot). El schema de salida del
  expediente/ficha de incidencia incluye `bajo_contrato: bool` y un resumen del contrato (código, nivel,
  estado) leído del equipo asociado en el momento de la consulta. Solo informativo.

## API (todos los endpoints protegidos salvo indicación)

Contratos:
- `GET /api/contratos?estado=&cliente_id=` — lista (estado = filtro por estado derivado, en memoria o SQL
  por fechas).
- `POST /api/contratos` — alta.
- `GET /api/contratos/{id}` — detalle + equipos cubiertos + `nivel_detalle` + estado.
- `PUT /api/contratos/{id}` — edición (incluye `cancelado`).
- `DELETE /api/contratos/{id}` — borrado **duro solo si no tiene equipos vinculados ni acciones de
  preventivo**. Si los tiene → HTTP 409 con mensaje que indica cancelar en su lugar (`PUT` con
  `cancelado=true`). Así el historial nunca queda huérfano.
- `POST /api/contratos/{id}/equipos` body `{equipo_id}` — vincular equipo (valida cliente → 409).
- `DELETE /api/contratos/{id}/equipos/{equipo_id}` — desvincular.

Equipos / base instalada:
- `GET /api/equipos?bajo_contrato=true|false` — filtro nuevo (derivado). Compone con los filtros existentes.
- Ficha de equipo: expone `contrato` (resumen) y `bajo_contrato`.

Preventivo:
- `GET /api/equipos/{id}/preventivos` — historial preventivo del equipo (orden desc por fecha).
- `POST /api/equipos/{id}/preventivos` — crear acción (auto-asocia contrato, sugiere `proxima_fecha`).
- `POST /api/preventivos/{accion_id}/generar-incidencia` body `{tipo?, prioridad?, asignado_a?}` — crea
  incidencia correctiva enlazada (201, devuelve `IncidenciaOut`). 409 si ya tiene `incidencia_id`.

Incidencias:
- El expediente/ficha (`GET /api/incidencias/{id}` o el `Out` existente) añade `bajo_contrato` + resumen de
  contrato del equipo (en vivo).

## Frontend (Prompt Lovable 22)
- Catálogo: campo P/N de fabricante en alta/edición de producto; mostrarlo en la "Configuración actual" del
  equipo junto al part_number 6TL.
- Pantalla **Contratos** (`/contratos`): lista con código, cliente, nivel (badge), vigencia/estado;
  ficha con datos + `nivel_detalle` + tabla de equipos cubiertos (asignar/desasignar).
- Base instalada / ficha de equipo: badge "bajo contrato" (verde si vigente) + historial de preventivo +
  botón "Registrar preventivo" (formulario) y desde una acción con veredicto distinto de OK, botón
  "Generar incidencia".
- Incidencias: indicador de cobertura de contrato (informativo) junto al de garantía.

## Auditoría
- Las tablas nuevas y columnas quedan cubiertas automáticamente por el listener ORM de auditoría existente
  (registra cualquier flush de modelos). No requiere código extra.

## Testing (TDD, estilo del proyecto)
- `contratos`: generar_codigo secuencial; estado derivado en los 4 casos (pendiente/vigente/vencido/
  cancelado) con fechas monkeypatch/explícitas; `nivel_detalle` por nivel; vincular equipo OK / 409 por
  cliente distinto; desvincular; DELETE con dependencias → 409.
- `equipo.bajo_contrato`: true solo con contrato vigente; false si vencido/cancelado/sin contrato; filtro
  `?bajo_contrato=`.
- `preventivo`: crear acción auto-asocia contrato vigente; sugiere `proxima_fecha` por nivel (anual/semestral);
  generar-incidencia crea y enlaza, 409 si repetido; historial por equipo ordenado.
- `incidencia`: expone `bajo_contrato` en vivo (cambia si el contrato vence).
- Endpoints protegidos → 401 sin token.

## Riesgos / notas
- ⚠️ El estado derivado depende de "hoy"; los tests que fijan vigencia deben usar fechas absolutas o
  monkeypatch de la fecha (precedente: tests flaky por fecha en ATE).
- ⚠️ Parar uvicorn antes de la suite (el arranque siembra/abre `postventa.db`).
- `proxima_fecha` por nivel usa aritmética de meses simple (+6/+12); sin librería de calendario.
- Reutilizar el patrón solicitud→incidencia para preventivo→incidencia (no duplicar lógica de creación).
