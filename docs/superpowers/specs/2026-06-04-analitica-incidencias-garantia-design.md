# Analítica de incidencias + control de garantía — Diseño

**Fecha:** 2026-06-04
**Proyecto:** 6TL Postventa ("6tlservice") — electronic test systems
**Estado:** diseño aprobado en brainstorming, pendiente de spec review + plan

## Problema / objetivo

El postventa necesita una **pantalla de analítica de incidencias** (estadística por tipo,
por producto, por técnico, etc.) y un **control de garantía** real de la base instalada.

Hoy faltan dos datos en el modelo:

1. **Tipo de incidencia.** La entidad `Incidencia` se modeló solo como RMA (`codigo = RMA-NNNN`,
   sin campo de tipo). El negocio distingue cuatro tipos de intervención:
   `rma | soporte_venta | soporte_tecnico | calibracion`.
2. **Garantía calculable.** El `Equipo` tiene `fecha_entrega` pero ninguna duración ni fecha de
   fin de garantía, así que no se puede saber si un equipo está en garantía. El flag
   `Incidencia.en_garantia` es manual y no se apoya en ningún dato del equipo.

Requisito explícito del usuario: **el RMA se desglosa en garantía vs no garantía** y **tiene que
haber un control de garantía** (no solo el flag manual).

## Decisiones de diseño (tomadas en brainstorming)

- **Tipo de incidencia:** nuevo campo `Incidencia.tipo`, enum `rma | soporte_venta |
  soporte_tecnico | calibracion`, default `rma`. Las 58 incidencias existentes quedan como `rma`.
- **Código por tipo:** `generar_codigo` usa prefijo según el tipo, con secuencia propia por prefijo:
  `RMA-NNNN`, `SV-NNNN` (soporte venta), `ST-NNNN` (soporte técnico), `CAL-NNNN` (calibración).
- **Garantía:** `meses_garantia` vive en el **equipo** (editable), con default heredado del
  **producto** (`Producto.meses_garantia_default`, default 24) al dar de alta el equipo; override por
  unidad para garantías extendidas. `fecha_fin_garantia = fecha_entrega + meses_garantia`.
- **Alcance control de garantía:** analítica **+ operativo en la ficha del equipo**. En la ficha:
  badge de estado de garantía. Al crear un **RMA**, `en_garantia` se autodetecta desde la garantía
  del equipo en `fecha_apertura`, pero queda **editable** (override manual).
- **Arquitectura analítica:** un único endpoint de agregación server-side
  (`GET /api/analitica/incidencias`) que devuelve todos los grupos de métricas calculados en un
  módulo puro testeable (patrón TDD del proyecto). El frontend solo pinta.
- **Entrega:** backend TDD + endpoint + **prompt Lovable 13** para la pantalla `/analitica`, el
  selector de `tipo` en el alta/edición de incidencia y el badge de garantía en la ficha del equipo.

## Modelo de datos (cambios)

### `Producto`
- `+ meses_garantia_default: Optional[int]` (default 24 a nivel de aplicación; nullable en BD).

### `Equipo`
- `+ meses_garantia: Optional[int]` (nullable). Al crear el equipo, si no se indica, se hereda de
  `producto.meses_garantia_default`.
- `+ version: Optional[str]` (nullable). Revisión HW/FW de **esa unidad** (p.ej. "Rev C", "FW 2.1").
  Distinta del PN/descripción, que viven en el catálogo (`Producto`). El año de fabricación se sigue
  guardando como `fecha_fabricacion` (fecha completa; en UI se muestra solo el año donde convenga).
- **Datos del equipo y de dónde vienen:** SN = `numero_serie`; **PN** y **descripción** = del
  `Producto` asociado (no se duplican en el equipo); año fabricación = `fecha_fabricacion`;
  **versión** = `version` (nuevo).
- **Derivados (no columnas):**
  - `fecha_fin_garantia = fecha_entrega + relativedelta(months=meses_garantia)` (None si falta
    `fecha_entrega` o `meses_garantia`).
  - `estado_garantia(hoy)` → `vigente | por_vencer | vencida | sin_datos`.
    `por_vencer` = vigente y vence en ≤ `UMBRAL_POR_VENCER_DIAS` (default 90).

### `Incidencia`
- `+ tipo: str` (default `"rma"`, enum `rma | soporte_venta | soporte_tecnico | calibracion`).
- `en_garantia` se mantiene como está (Optional[bool]); en RMA se autorrellena al crear.

### Migración
`app/migrations.py::add_missing_columns()` (idempotente, patrón ya existente): ADD COLUMN
`productos.meses_garantia_default`, `equipos.meses_garantia`, `equipos.version`, `incidencias.tipo`
(con default `'rma'` para las filas existentes). Sin destruir datos.

## Lógica de garantía (`app/garantia.py`, módulo puro)

- `fecha_fin_garantia(equipo) -> Optional[date]`
- `estado_garantia(equipo, hoy) -> str` (`vigente|por_vencer|vencida|sin_datos`)
- `equipo_en_garantia(equipo, fecha) -> Optional[bool]` (None si `sin_datos`) — usado para
  autodetectar `en_garantia` al crear un RMA.
- Todo con `hoy`/`fecha` inyectables (tests sin depender del reloj).

## Servicio de incidencias (cambios)

- `generar_codigo(db, tipo)`: mapa `{rma:"RMA", soporte_venta:"SV", soporte_tecnico:"ST",
  calibracion:"CAL"}`; escanea los códigos con ese prefijo y devuelve `PREFIJO-NNNN` (max+1).
  Retrocompatible: los RMA existentes siguen su secuencia.
- POST incidencia: si `tipo == "rma"`, `equipo_id` presente y el cliente no envió `en_garantia`
  explícito → `en_garantia = equipo_en_garantia(equipo, fecha_apertura)`. Si lo envió, se respeta.

## Backend analítica (`app/analitica_incidencias.py` + router `app/routers/analitica.py`)

### Endpoint
`GET /api/analitica/incidencias?desde=&hasta=&tipo=&cliente_id=`
- Filtros (todos opcionales): `desde`/`hasta` sobre `fecha_apertura`; `tipo`; `cliente_id`
  (cliente del equipo de la incidencia).
- Devuelve un único objeto `AnaliticaIncidenciasOut` con todos los grupos.

### Grupos de métricas (todos en el payload)
1. **Distribuciones (conteos):** por `tipo`, por producto/familia (producto del equipo o
   componente), por técnico (`asignado_a`), por `prioridad`, por `estado`, por cliente,
   en/fuera de garantía (solo RMA).
2. **KPIs de tiempo** (días):
   - MTTR = media de `fecha_resolucion - fecha_apertura` (solo resueltas/cerradas).
   - Tiempo medio de diagnóstico = media de `fecha_diagnostico - fecha_apertura`.
   - Edad media de las abiertas = media de `hoy - fecha_apertura` (estado ≠ cerrada).
   - Agregado y desglosado por `tipo`, por producto, por técnico.
   - *(Se omite "% en plazo": no hay campo SLA. Se añadirá si se define un objetivo.)*
3. **Tendencia mensual:** por mes (`YYYY-MM`): nº abiertas (por `fecha_apertura`), nº cerradas
   (por `fecha_cierre`), backlog acumulado (abiertas−cerradas hasta ese mes).
4. **Fiabilidad:** ranking de productos y de equipos por nº de incidencias (top N), tasa de RMA
   por familia de producto.
5. **Garantía (control):** equipos por `estado_garantia` (vigente/por_vencer/vencida/sin_datos);
   RMA en vs fuera de garantía; (lista de "por vencer" se deja para una iteración posterior — el
   alcance elegido es analítica + ficha, sin pantalla de alertas dedicada).

### Esquemas de salida
`AnaliticaIncidenciasOut` compuesto por sub-modelos: `ConteoItem{clave,etiqueta,valor}`,
`KpiTiempo{global, por_tipo[], por_producto[], por_tecnico[]}`, `PuntoTendencia{mes, abiertas,
cerradas, backlog}`, `RankingItem{id?, etiqueta, valor}`, `ResumenGarantia{...}`.

## Frontend Lovable (prompt 13)

1. **Ruta nueva `/analitica`:**
   - Cabecera con filtros globales: rango de fechas, `tipo`, cliente.
   - KPI cards arriba (total incidencias, MTTR, abiertas, % en garantía).
   - Gráficos de barras para distribuciones (recharts/shadcn, paleta lila `#9e007e`).
   - Gráfico de línea para tendencia mensual.
   - Tablas para rankings de fiabilidad y resumen de garantía.
2. **Alta/edición de incidencia:** selector **tipo** (4 opciones); para RMA, `en_garantia`
   precargado desde la garantía del equipo (editable). Badge de tipo en lista y ficha.
3. **Ficha + alta/edición del equipo:** campos `meses_garantia` y `version` (editables) +
   **badge de estado de garantía** (vigente/por vencer/vencida/sin datos) con `fecha_fin_garantia`.
   La ficha muestra PN/descripción (del producto), SN, año de fabricación y versión.
4. Entrada de navegación a `/analitica`.

## Contrato (campos nuevos en API)

- `ProductoOut/Create/Update`: `+ meses_garantia_default`.
- `EquipoOut/Create/Update/Ficha`: `+ meses_garantia`, `+ version`, `+ fecha_fin_garantia` (derivado,
  solo Out/Ficha), `+ estado_garantia` (derivado, solo Out/Ficha).
- `IncidenciaOut/Create/Update`: `+ tipo`. Filtro `tipo` en el listado.

## Testing (TDD)

- `garantia.py`: fin de garantía, estados (vigente/por_vencer/vencida/sin_datos), `equipo_en_garantia`
  con fechas inyectadas; bordes (sin fecha_entrega, sin meses, justo en el límite).
- `generar_codigo`: prefijo y secuencia por tipo; coexistencia con RMA existentes.
- POST incidencia RMA: autodetección de `en_garantia` + respeto del override.
- migración idempotente: añade columnas, default `tipo='rma'`, no rompe BD poblada.
- `analitica_incidencias`: cada grupo de métricas con dataset semilla controlado; filtros
  (desde/hasta/tipo/cliente); casos vacíos (sin incidencias → ceros, sin divisiones por cero en MTTR).
- endpoint `/api/analitica/incidencias`: forma del payload + filtros + 200 con BD vacía.

## Fuera de alcance (YAGNI)

- Pantalla/alerta dedicada de equipos por vencer (solo el bucket en analítica).
- SLA y "% resueltas en plazo" (no hay objetivo definido).
- Coste económico de los RMA (no hay datos de coste en el modelo).
- Exportación a Excel/PDF de la analítica.
