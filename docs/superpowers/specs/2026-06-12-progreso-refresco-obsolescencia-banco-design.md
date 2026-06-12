# Progreso en vivo del refresco de obsolescencia por banco — Diseño

**Fecha:** 2026-06-12
**Estado:** Aprobado (brainstorming)

## Contexto

El report de obsolescencia por banco (feature mergeada en `ea9f894`) tiene un botón **"Refrescar
estado"** que llama a `POST /api/equipos/{id}/obsolescencia/refrescar`. Ese endpoint es **síncrono**:
recorre los componentes verificables del banco llamando a `consultar_fabricante` (Claude Code headless)
uno a uno —cada llamada tarda segundos o más— y solo devuelve el report actualizado al final. La UI
muestra un **spinner ciego** durante todo ese tiempo, sin saber qué componente se está chequeando ni
cuánto queda.

El usuario quiere un **popup propio que muestre el avance en tiempo real**: una barra de progreso
(X de N), el componente que se está consultando ahora, y un log que va creciendo con cada componente
ya chequeado y su estado encontrado.

Alcance acordado: **solo el refresco por banco** (el botón del dialog). La vigilancia global semanal
(`run_obsolescencia.py`) queda fuera.

## Decisiones (brainstorming)

- **Superficie:** el botón "Refrescar estado" del dialog de report de un equipo → abre un popup de progreso.
- **Contenido del popup:** barra (X de N) + componente actual destacado + log en vivo de resultados.
- **Transporte (opción A):** **job en segundo plano + sondeo**. No SSE (la latencia por componente domina,
  sondear a 1 s se ve en tiempo real; SSE añade parsing de stream y fricción con el Bearer para nada).

## Arquitectura

### Backend

**`app/obsolescencia_jobs.py` — store de progreso en memoria** (proceso único uvicorn on-prem):
- `_JOBS: dict[str, dict]` protegido por un `threading.Lock`. Forma de un job:
  ```
  {job_id, equipo_id, total, indice, estado: "en_curso"|"terminado"|"error",
   actual: {part_number, fabricante, descripcion} | None,
   resultados: [{part_number, descripcion, estado_anterior, estado_nuevo, cambio}],
   report: dict | None, error: str | None}
  ```
- `crear_job(equipo_id, total) -> job_id` (`secrets.token_hex(8)`), `snapshot(job_id) -> dict | None`
  (copia profunda para el GET), helpers `_actualizar`/`_append_resultado` con lock.
- `ejecutar(job_id, equipo_id, *, limite, consultar, db_factory=SessionLocal)`: abre una sesión propia,
  llama a `obsolescencia_banco.refrescar_banco(...)` con un callback `on_progreso` que escribe en el store,
  y al acabar marca `estado="terminado"` + `report=informe_banco(...)`. Si algo lanza → `estado="error"`,
  `error=str(exc)`. Cierra la sesión en `finally`.
- `lanzar(job_id, equipo_id, *, limite, consultar)`: arranca `ejecutar` en un **hilo daemon**
  (`threading.Thread(..., daemon=True).start()`). **Inyectable** para tests: el router usa `lanzar`
  (hilo real); los tests llaman a `ejecutar` directo (inline, determinista).

**`app/obsolescencia_banco.py::refrescar_banco` gana `on_progreso=None`:**
- Antes de consultar cada producto: `on_progreso({"tipo":"actual","indice":i,"total":n,"producto":p})`.
- Tras `registrar_hallazgo`: `on_progreso({"tipo":"resultado","producto":p,"estado_anterior":...,
  "estado_nuevo":..., "cambio":...})`.
- Sin callback (`None`) el comportamiento es **idéntico al actual** → el endpoint síncrono y sus tests
  no cambian. Una sola función de refresco (DRY). `productos_de_equipo` y `_url_fabricante` se reutilizan.

**Endpoints nuevos** en `app/routers/obsolescencia_banco.py` (protegidos, prefix `/api/equipos`):
- `POST /{equipo_id}/obsolescencia/refrescar/iniciar?limite=N` (`limite` `Query(default=10, ge=1, le=50)`):
  valida equipo (404), calcula `total = len(productos_de_equipo(db, equipo_id)[:limite])`, crea el job,
  llama a `lanzar(...)` y devuelve `{job_id, total}`. `consultar` vía `Depends(get_consultar_fabricante)`.
- `GET /{equipo_id}/obsolescencia/refrescar/{job_id}`: devuelve `snapshot(job_id)` (404 si no existe).
  Incluye `report` embebido cuando `estado=="terminado"` (el popup refresca la tabla sin otra llamada).

El **`POST .../refrescar` síncrono actual se mantiene** (scripts/tests). Schemas nuevos en `schemas.py`:
`RefrescoIniciado {job_id, total}`, `RefrescoResultadoItem {...}`, `RefrescoProgreso {job_id, equipo_id,
total, indice, estado, actual|null, resultados[], report|null, error|null}`.

### Frontend

**`RefrescoObsolescenciaProgresoDialog`** (componente nuevo), abierto al pulsar "Refrescar estado":
- Al abrir: `POST .../refrescar/iniciar?limite=10` → `{job_id, total}`.
- **Sondeo** `GET .../refrescar/{job_id}` cada **1 s** (`setInterval`, limpiado al cerrar/terminar/error).
- Render: barra `indice/total` + texto "Chequeando i/total"; tarjeta del `actual` con spinner; lista que
  crece con `resultados[]` (P/N + descripción + `EstadoCicloBadge` del `estado_nuevo`, realce si `cambio`).
- `estado==="terminado"`: para el sondeo, "Completado · N cambios", botón **Cerrar** que cierra el popup
  y refresca la tabla del report padre con el `report` embebido (o re-`GET .../obsolescencia`).
- `estado==="error"`: muestra `error` + cerrar; no rompe el dialog padre.

**Wiring:** en `ReportObsolescenciaDialog`, "Refrescar estado" abre este popup (estado local) en vez del
refresco síncrono. El resto del dialog no cambia. Tipos `RefrescoIniciado`/`RefrescoProgreso` en `types.ts`.

## Manejo de errores

- Equipo inexistente → 404 en `iniciar`; `job_id` desconocido → 404 en el GET (el popup corta el sondeo y avisa).
- `consultar` que falla en un componente → ese ítem se omite (best-effort, ya es así); el job continúa.
- Excepción inesperada en el hilo → job `estado="error"` con el mensaje; el popup lo muestra.
- Popup cerrado a mitad → el hilo sigue hasta terminar en el backend (estado ya persistido por
  `registrar_hallazgo`); el cliente solo deja de sondear. No hay cancelación (YAGNI).

## Pruebas (TDD)

- **`refrescar_banco` con `on_progreso`**: fake `consultar` + callback acumulador → por cada producto se
  emite `actual` (antes) y `resultado` (después) con `cambio` correcto; sin callback, comportamiento idéntico.
- **`obsolescencia_jobs`**: `crear_job`/`snapshot`; `ejecutar` con `consultar` falso y `db_factory` de test
  → `estado="terminado"`, `indice==total`, `resultados` completos, `report` presente; `consultar` que lanza
  → `estado="error"` con mensaje.
- **Router**: `iniciar` → 200 `{job_id,total}` y crea el job; `GET` del job refleja progreso/terminado;
  404 equipo, 404 job, 401 sin token; `consultar` inyectado por override (sin red). Para evitar carreras,
  los tests del router inyectan un **lanzador inline** (override de `lanzar` que ejecuta `ejecutar` de forma
  síncrona) → el job está `terminado` antes del primer GET, sin depender de timing.

## Fuera de alcance (YAGNI)

- Progreso de la vigilancia global semanal (`run_obsolescencia.py`).
- Cancelar un refresco en curso.
- Persistir los jobs (sobreviven solo en memoria; un reinicio del backend los pierde — aceptable).
- Multi-worker / store distribuido (el despliegue on-prem es proceso único).
- SSE / WebSocket.
