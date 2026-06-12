# Report de obsolescencia por banco — Diseño

**Fecha:** 2026-06-12
**Estado:** Aprobado (brainstorming)

## Contexto

La feature de obsolescencia (ciclo de vida EOL/PCN) ya existe y trabaja sobre **todo el
catálogo**: `obsolescencia_service.productos_a_revisar`, `resumen_obsolescencia` y
`construir_informe` son globales, y el orquestador semanal `run_obsolescencia.py` recorre el
catálogo entero. No hay forma de obtener el estado de obsolescencia acotado a **un banco/equipo
concreto** ni de exportarlo.

El usuario necesita generar un **report de obsolescencia de un banco**: la foto del estado de
ciclo de vida de todos los componentes montados en ese equipo, consultable en pantalla y
exportable (Excel/PDF), con opción de re-verificar el banco antes de generarlo.

Hoy la BD viva tiene **1 banco real** (iUTB SN001, 131 componentes / 119 productos distintos;
~55 P/N propios 6TL que salen `activo` y ~64 de terceros, que son la vigilancia útil). El diseño
es genérico por `equipo_id` aunque hoy solo haya uno.

## Decisiones (brainstorming)

- **Fuente de datos:** estado **ya almacenado** en cada producto, con **opción de refrescar**
  (re-verificar el banco) antes de generar.
- **Entrega:** **API JSON + descarga**.
- **Formato descargable:** **Excel (.xlsx) + PDF**.
- **Alcance de filas:** **todos** los componentes del banco (los propios 6TL incluidos, salen
  `activo`). Orden por defecto = severidad de riesgo descendente.
- **Refresco:** **síncrono acotado** (opción A) — reutiliza el orquestador existente, limitado a
  los productos del banco, con `consultar` inyectable y un `limite` conservador.

## Arquitectura

Una sola fuente de verdad (`informe_banco`) que sirve para JSON y para las dos exportaciones.

### `app/obsolescencia_banco.py` (lectura, sin red)

- `informe_banco(db, equipo_id, hoy) -> dict` — compila el report:
  - **Cabecera:** equipo (`id`, `numero_serie`, producto `part_number`/descripción, cliente,
    `estado`, contrato + nivel si lo tiene).
  - **Filas (todos los componentes de `equipo.componentes`):** `posicion` · `part_number` (6TL) ·
    `fabricante` · `pn_fabricante` · `descripcion` · `numero_serie` · `estado_ciclo_vida` ·
    `ciclo_vida_fecha` · `ciclo_vida_url` (fuente) · `ciclo_vida_resumen` ·
    `ciclo_vida_verificado_en` · `categoria_componente`. Orden por `obsolescencia.severidad`
    descendente, luego `posicion`.
  - **Resumen:** conteos por estado (reutiliza `obsolescencia.ESTADOS`), nº en riesgo
    (severidad > 0), nº sin verificar (`estado_ciclo_vida is None`), y
    `verificado_mas_antiguo` (mín. `ciclo_vida_verificado_en`, para saber si el banco está fresco).
  - Estructura plana (dict) reutilizada tal cual por API y exportadores.
- `productos_de_equipo(db, equipo_id) -> list[Producto]` — productos **distintos** de los
  componentes del banco con `fabricante` y `pn_fabricante` no nulos (verificables), no verificados
  primero (mismo criterio de orden que `productos_a_revisar`, filtrado por banco).
- `refrescar_banco(db, equipo_id, hoy, *, limite, consultar) -> dict` — por cada producto (hasta
  `limite`) llama `consultar(producto, url)` y `obsolescencia_service.registrar_hallazgo(...)`;
  fallos de `consultar` se ignoran (best-effort). `consultar` es **inyectable** (mismo patrón que
  `run_obsolescencia.ejecutar`); el router pasa por defecto
  `run_obsolescencia.consultar_fabricante`. La `url` por producto sale de su fabricante
  (`Fabricante.url_obsolescencia`, helper equivalente a `run_obsolescencia._url_fabricante`).
  Devuelve `informe_banco(...)` ya actualizado. Como usa `registrar_hallazgo`, **alimenta también
  las noticias globales** (`NoticiaObsolescencia` si el estado empeora) — coherente con la
  vigilancia semanal.

### `app/obsolescencia_export.py` (sin BD)

- `a_xlsx(informe) -> bytes` con **openpyxl**: hoja "Componentes" (cabecera del banco + fila de
  resumen + tabla con encabezados), celda de estado coloreada por riesgo.
- `a_pdf(informe) -> bytes` con **reportlab**: cabecera del banco + `Table`/`TableStyle` con filas
  de riesgo resaltadas + pie con fecha de generación.
- Ambos consumen el dict de `informe_banco`; no tocan BD.

### Endpoints — router `app/routers/obsolescencia.py` (protegidos con `get_current_user`)

- `GET /api/equipos/{id}/obsolescencia` → JSON del report. 404 si el equipo no existe.
- `GET /api/equipos/{id}/obsolescencia/export?formato=xlsx|pdf` → descarga vía `Response`
  (`media_type` y `Content-Disposition: attachment; filename="obsolescencia_<numero_serie>_<fecha>.<ext>"`).
  `formato` inválido → 422.
- `POST /api/equipos/{id}/obsolescencia/refrescar?limite=N` → re-verifica el banco y devuelve el
  report actualizado. `limite` por defecto **10** (conservador para no eternizar la petición HTTP;
  el front avisa "puede tardar").

### Schemas (`app/schemas.py`)

`ObsolescenciaBancoOut` (cabecera + `componentes: list[...]` + `resumen`) para tipar la respuesta
JSON y el contrato con el frontend.

## Manejo de errores

- Equipo inexistente → **404**.
- `formato` no en {`xlsx`,`pdf`} → **422**.
- Banco sin componentes → report válido vacío (no es error).
- Fallo de `consultar` en refresco → ese producto se omite (best-effort), nunca rompe el endpoint.
- Sin token → **401** (dependencia de auth ya existente).

## Pruebas (TDD)

- **`obsolescencia_banco`:** orden por severidad; conteos/resumen correctos; filtro de productos
  verificables; `refrescar_banco` con `consultar` falso (registra estado, crea noticia al empeorar,
  respeta `limite`, ignora fallos).
- **Export:** `a_xlsx` devuelve bytes que empiezan por `PK\x03\x04`; `a_pdf` por `%PDF`; ambos
  contienen el nº de serie del banco.
- **Routers:** 200 JSON con shape esperado; 404 equipo inexistente; export con `Content-Type` y
  `Content-Disposition` correctos; 422 formato inválido; 401 sin token; refrescar con `consultar`
  inyectado vía dependency override (sin red).

## Dependencias nuevas

`openpyxl` y `reportlab` (añadir al entorno/requirements del backend). Justificadas por la decisión
de exportar a Excel + PDF.

## Fuera de alcance (YAGNI)

- Refresco en segundo plano / polling de progreso (opción B) — se subirá a eso solo si el refresco
  acotado se queda corto en la práctica.
- Report multi-banco / comparativa entre bancos.
- Programar el refresco por banco en Task Scheduler (la vigilancia semanal global ya cubre el
  catálogo).
- UI Lovable (prompt aparte tras el backend).
