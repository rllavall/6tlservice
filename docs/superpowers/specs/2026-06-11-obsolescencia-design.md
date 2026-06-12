# Gestión de obsolescencia — Diseño

**Fecha:** 2026-06-11
**Estado:** aprobado

## Objetivo

Vigilar semanalmente el estado de ciclo de vida de los productos del catálogo (EOL/PCN/obsolescencia)
consultando la web de cada fabricante con un agente, persistir el estado en el producto y notificar
los cambios por los canales ya existentes (Telegram/email).

## Decisiones (cerradas en brainstorming)

- **Alcance:** todos los productos del catálogo con `fabricante` + `pn_fabricante` (hoy: 119 de 120).
- **Resultado:** persistir el estado de ciclo de vida en el producto **y** notificar el cambio.
- **Motor del agente:** Claude Code headless semanal (`claude -p`, sin API key). El research web usa
  sus herramientas WebSearch/WebFetch.
- **Estados (taxonomía estándar industria):** `activo` · `nrnd` · `eol_anunciado` · `ultima_compra` ·
  `obsoleto`. `NULL` = aún sin verificar.
- **Fuente web:** URL PCN/EOL opcional por fabricante + búsqueda web abierta como fallback.

## Modelo de datos

### `Producto` (columnas nuevas, vía migración ALTER idempotente)
- `estado_ciclo_vida` TEXT — uno de los 5 estados; `NULL` = sin verificar.
- `ciclo_vida_fecha` DATE — fecha del evento (anuncio EOL o *last-time-buy*), si se conoce.
- `ciclo_vida_url` TEXT — enlace a la fuente del último hallazgo.
- `ciclo_vida_resumen` TEXT — nota corta del hallazgo.
- `ciclo_vida_verificado_en` DATE — última fecha en que el agente revisó este producto.

### `Fabricante` (columna nueva)
- `url_obsolescencia` TEXT — página de Product Change Notifications / EOL del fabricante (opcional).

### Tabla nueva `noticias_obsolescencia` (historial; 1 fila por cambio detectado)
- `id` PK
- `producto_id` FK → productos.id
- `fecha_deteccion` DATE
- `estado_anterior` TEXT (nullable)
- `estado_nuevo` TEXT
- `fecha_evento` DATE (nullable)
- `url_fuente` TEXT (nullable)
- `resumen` TEXT (nullable)
- `notificado` BOOL default False

Migración: columnas vía `migrations.add_missing_columns`; tabla nueva vía `create_all`.

## Lógica pura — `app/obsolescencia.py`

- `ESTADOS = ["activo", "nrnd", "eol_anunciado", "ultima_compra", "obsoleto"]`
- `SEVERIDAD`: mapa estado → 0..4 (activo=0 … obsoleto=4).
- `estado_valido(estado) -> bool`
- `es_transicion(anterior, nuevo) -> bool` — `nuevo` válido y distinto de `anterior`.
- `requiere_url(estado) -> bool` — True para cualquier estado distinto de `activo`.
- `validar_hallazgo(estado, url) -> None` — lanza `ValueError` si el estado no es válido o si
  `requiere_url(estado)` y no hay `url` (**regla anti-alucinación: no se degrada sin fuente**).

## Servicio — `app/obsolescencia_service.py`

- `productos_a_revisar(db, hoy, *, dias=7, limite=None)` — productos con `fabricante` y
  `pn_fabricante` cuyo `ciclo_vida_verificado_en` es `NULL` o `<= hoy - dias`; orden: no verificados
  primero; `limite` opcional (auto-throttle del catálogo entre semanas).
- `registrar_hallazgo(db, producto_id, estado, *, hoy, fecha_evento=None, url=None, resumen=None)`:
  - Valida con `obsolescencia.validar_hallazgo`. Si falla la regla de URL → no registra, devuelve
    `{"registrado": False, "motivo": "sin_url"}` (no rompe el lote).
  - Siempre actualiza `ciclo_vida_verificado_en = hoy` y `estado_ciclo_vida = estado` (último
    veredicto), junto con `ciclo_vida_fecha/url/resumen`.
  - Crea `NoticiaObsolescencia` (con `estado_anterior`/`estado_nuevo`) **solo si es un cambio
    notable**: el estado empeora respecto al anterior (mayor severidad). Así `sin verificar → activo`
    no genera noticia (evita inundar en la primera pasada) y un estado que se mantiene no duplica.
    Devuelve `cambio=True` si creó noticia, `False` si no.
- `resumen_obsolescencia(db)` — conteos por estado + últimas noticias (para la UI).
- `enviar_informe(db, hoy, *, notificar_fn=notificaciones.notificar)` — junta las
  `NoticiaObsolescencia` con `notificado=False`, construye asunto/cuerpo, **envía solo si hay
  alguna** (si no, `enviado=False` y no molesta), marca `notificado=True`.

## API — `app/routers/obsolescencia.py` (protegido con Bearer)

- `GET /api/obsolescencia` — resumen + listado de noticias recientes.
- `GET /api/obsolescencia/productos-a-revisar?dias=&limite=` — lista de trabajo del agente
  (id, fabricante, pn_fabricante, descripcion, url_obsolescencia, estado actual).
- `POST /api/obsolescencia/hallazgos` — alta en lote de veredictos (lista de
  `{producto_id, estado, fecha_evento?, url?, resumen?}`), por si se alimenta vía API.
- `ProductoOut` expone los campos nuevos; el form de `Fabricante` permite editar `url_obsolescencia`.

## Orquestador semanal — `backend/run_obsolescencia.py`

Entrypoint pensado para Task Scheduler (como `run_digest.py`). Escribe directo a BD vía servicio
(sin auth). Flujo:
1. `productos_a_revisar(db, hoy, limite=N)`.
2. Por cada producto, `consultar_fabricante(producto)` → `{estado, fecha_evento?, url_fuente, resumen}`.
   - Implementación por defecto: shell a `claude -p` headless con un prompt que prioriza
     `url_obsolescencia` y, si no, busca en abierto `"<fabricante> <pn> EOL/PCN/discontinued"`.
   - `consultar_fabricante` es **inyectable** para poder testear el orquestador con un stub.
3. `registrar_hallazgo(...)` por cada veredicto.
4. `enviar_informe(db, hoy)` — un informe semanal con todos los cambios.

Glue (no testeado, documentado): `run_obsolescencia.cmd` + `obsolescencia_prompt.md` + alta de la
tarea en el Programador de Windows (semanal). Tope por ejecución para repartir el catálogo.

## Manejo de errores

- Veredicto no concluyente → no se crea noticia; el estado del producto no cambia; `verificado_en` se
  actualiza igual (sí se intentó).
- Estado distinto de `activo` sin `url_fuente` → se descarta ese veredicto (regla anti-alucinación).
- Fallo de red por producto → se salta; se reintenta la semana siguiente.
- Idempotencia: una segunda pasada la misma semana no duplica noticias (solo se registra cuando el
  estado realmente cambia).

## Frontend (prompt Lovable, follow-up — no bloquea el backend)

- Badge de estado de ciclo de vida (verde `activo` / ámbar `nrnd` / naranja `eol_anunciado`,
  `ultima_compra` / rojo `obsoleto`) en ficha de equipo y catálogo.
- Ruta `/obsolescencia` con los cambios recientes y conteos.
- Campo `url_obsolescencia` editable en el formulario de fabricante.

## Tests

Cobertura puro / servicio / router / migración:
- Pura: estado válido, `es_transicion`, `requiere_url`, `validar_hallazgo` (incl. regla URL), severidad.
- Servicio: filtro de `productos_a_revisar` (solo con fabricante+pn, respeta `dias`/`limite`),
  `registrar_hallazgo` (crea noticia solo si cambia, actualiza `verificado_en` siempre, descarta sin
  URL), `resumen_obsolescencia`, `enviar_informe` (envía solo no-notificadas y las marca, no-envío si
  vacío).
- Router: forma de la lista de trabajo, POST en lote, GET resumen, 401 en protegidos, URL de fabricante
  editable.
- Migración: columnas nuevas en `productos`/`fabricantes` y tabla `noticias_obsolescencia` presentes.
- Orquestador: con `consultar_fabricante` stub, recorre la lista, registra y dispara el informe.
