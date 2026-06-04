# Bitácora de avances de incidencia — Diseño

**Fecha:** 2026-06-04
**Proyecto:** 6TL Postventa ("6tlservice")
**Estado:** diseño aprobado en brainstorming, pendiente de spec review + plan

## Problema / objetivo

Desde la lista de incidencias se debe poder abrir una incidencia y, en un **popup**, introducir
manualmente **cada avance/report** de su gestión. Hoy la incidencia solo tiene campos sueltos
(`diagnostico`, `resolucion`, `notas`) que se pisan al editar; no existe un registro cronológico
(bitácora) de avances. Se necesita una **bitácora de entradas**: N entradas por incidencia, cada una
con fecha, autor, tipo y texto, vistas como timeline y gestionables (crear/editar/borrar).

## Decisiones (brainstorming)

- **Bitácora = entidad nueva** `AvanceIncidencia` (no reusar `notas` ni un array JSON).
- **Campos por entrada:** `fecha` (editable, default hoy) + `autor` (texto libre, opcional) +
  `tipo` (`avance | report | llamada | visita | diagnostico | otro`, default `avance`) + `texto`.
- **Operaciones:** crear, **editar (PATCH)**, borrar, listar.
- **UI:** popup desde la **lista** (ver timeline + añadir/editar/borrar sin salir de la lista) **y**
  el mismo componente embebido en la **ficha** (`/incidencias/$id`). Misma fuente de datos.
- **Aditiva e independiente:** no toca `diagnostico`/`resolucion`/`notas` ni el flujo de estados;
  un avance NO dispara transiciones.

## Modelo de datos (backend)

Nueva entidad `AvanceIncidencia` (tabla `avances_incidencia`):
- `id: int` PK
- `incidencia_id: int` FK → `incidencias.id`
- `fecha: date`
- `autor: Optional[str]`
- `tipo: str` (default `"avance"`; valores `avance|report|llamada|visita|diagnostico|otro`)
- `texto: str`

`relationship` no imprescindible; se consulta por `incidencia_id`. La tabla la crea
`Base.metadata.create_all` al arrancar (es tabla NUEVA, no requiere `migrations.py`, que solo añade
columnas a tablas existentes). En la `postventa.db` viva, `create_all` la crea automáticamente.

## API (router nuevo `app/routers/avances.py`, prefix `/api/incidencias`)

Se separa en su propio router para no engordar `incidencias.py`.

- `GET /api/incidencias/{incidencia_id}/avances` → `list[AvanceOut]` ordenada **desc** por
  `fecha` y luego `id` (más reciente primero). 404 si la incidencia no existe.
- `POST /api/incidencias/{incidencia_id}/avances` body `AvanceCreate {fecha?, autor?, tipo?, texto}`
  → 201 `AvanceOut`. 404 si la incidencia no existe; `texto` obligatorio (422 si falta/vacío);
  `fecha` por defecto = hoy si no se envía.
- `PATCH /api/incidencias/{incidencia_id}/avances/{avance_id}` body `AvanceUpdate` (todos opcionales:
  `fecha?, autor?, tipo?, texto?`) → `AvanceOut`. 404 si el avance no existe o no pertenece a esa
  incidencia.
- `DELETE /api/incidencias/{incidencia_id}/avances/{avance_id}` → 204. 404 igual que PATCH.

`IncidenciaFicha` (respuesta de `GET /api/incidencias/{id}`) gana `avances: list[AvanceOut]`
(mismo orden desc), para que la ficha muestre el timeline sin una llamada extra.

### Esquemas (`app/schemas.py`)
```python
_TIPO_AVANCE = Literal["avance", "report", "llamada", "visita", "diagnostico", "otro"]

class AvanceCreate(BaseModel):
    fecha: Optional[date] = None       # router pone hoy si None
    autor: Optional[str] = None
    tipo: _TIPO_AVANCE = "avance"
    texto: str

class AvanceUpdate(BaseModel):
    fecha: Optional[date] = None
    autor: Optional[str] = None
    tipo: Optional[_TIPO_AVANCE] = None
    texto: Optional[str] = None

class AvanceOut(_ORM):
    id: int
    incidencia_id: int
    fecha: date
    autor: Optional[str] = None
    tipo: str
    texto: str
```
`texto` obligatorio en create; validar no-vacío (str con `min_length=1` o validación en router).

## Frontend (Lovable, prompt 14)

- Componente `BitacoraIncidencia` reutilizable: **timeline** de entradas (fecha · tipo badge · autor ·
  texto) + formulario "Añadir avance" (selector tipo, fecha [default hoy], autor, textarea) +
  acciones por entrada (editar / borrar).
- **Lista** (`incidencias.tsx`): el click en una fila abre un **popup/modal** con la bitácora de esa
  incidencia (carga `GET .../avances`, permite añadir/editar/borrar). Se mantiene un acceso a la ficha
  completa (botón "Abrir expediente" → `/incidencias/$id`).
- **Ficha** (`incidencias.$id.tsx`): mismo componente embebido (timeline + alta/edición/borrado).
- Tipos nuevos en `types.ts`: `AvanceTipo`, `Avance`/`AvanceOut`; `IncidenciaFicha.avances`.

## Testing (TDD)

- Modelo: crear `AvanceIncidencia` con defaults (`tipo="avance"`).
- Endpoints: POST crea (201, fecha default hoy si no se envía, 404 incidencia inexistente, 422 texto
  vacío); GET lista en orden desc; PATCH edita (y 404 si el avance es de otra incidencia); DELETE
  borra (204) + 404 tras borrar.
- Expediente: `GET /api/incidencias/{id}` incluye `avances` poblada y ordenada.

## Fuera de alcance (YAGNI)

- Adjuntar ficheros a una entrada.
- Que un avance dispare un cambio de estado.
- Notificaciones / menciones.
- Edición concurrente / control de versiones de una entrada.
