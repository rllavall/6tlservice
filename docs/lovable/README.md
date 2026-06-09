# Prompts Lovable — Frontend 6TL Postventa

Backend FastAPI en `http://127.0.0.1:8020`. Pega los prompts **en orden** en Lovable.

## Sub-proyecto 1 — Trazabilidad + base instalada

Frontend (React/Vite/TS/Tailwind/shadcn).

| # | Prompt | Pantalla / contenido |
|---|--------|----------------------|
| 00 | `00_design_system.md` | **Pegar primero.** Identidad corporativa 6TL (lila `#9e007e`, Open Sans/Roboto, isotipo) + shell con navegación + cliente API a :8020 |
| 01 | `01_base_instalada.md` | Home: tabla de base instalada + buscador global por nº de serie + filtros |
| 02 | `02_ficha_equipo.md` | Ficha de equipo (central): config actual + ubicación actual + historiales + modales montar/desmontar/sustituir/mover |
| 03 | `03_alta_edicion_equipo.md` | Alta y edición de equipo (+ componentes iniciales) |
| 04 | `04_catalogo.md` | Catálogo de productos (part numbers) |
| 05 | `05_ubicaciones.md` | Ubicaciones (plantas/sedes) con dirección + cliente |
| 06 | `06_clientes.md` | Clientes (entidad maestra: dueño de equipos y plantas) |
| 07 | `07_update_cliente_entidad.md` | **Prompt de ACTUALIZACIÓN** para una app ya generada con el contrato viejo: introduce Cliente como entidad y reconcilia ubicaciones/equipo |

> **Nota de contrato (sub-proyecto 1):** "Cliente" es una **entidad propia** (`/api/clientes`). Un cliente tiene N ubicaciones y N equipos. `Ubicacion.cliente_id` (solo para `tipo=fabrica_cliente`) y `Equipo.cliente_id` son FKs a Cliente. Si ya pegaste una versión anterior de los prompts (con `cliente` de texto / `empresa_cliente`), pega el **prompt 07** para ponerla al día.

## Sub-proyecto 2 — Incidencias / RMA

Pega estos prompts después de los del sub-proyecto 1 (requieren el shell y el cliente API de 00). El contrato central es `IncidenciaOut` / `IncidenciaFicha` (ver nota abajo). Los endpoints de trazabilidad del sub-proyecto 1 aceptan ahora un campo opcional `incidencia_id` en el body (introducido por el prompt 10).

| # | Prompt | Pantalla / contenido |
|---|--------|----------------------|
| 08 | `08_incidencias_lista.md` | Lista de incidencias (`/incidencias`): tabla con filtros de estado/prioridad y toggle "solo abiertas" |
| 09 | `09_incidencias_ficha.md` | Ficha de incidencia / expediente (`/incidencias/$id`): timeline de fases, bloques equipo/componente/cliente, acciones de transición de estado |
| 10 | `10_incidencias_alta.md` | Alta de incidencia (`/incidencias/nueva`) + hooks: sección "Incidencias" en ficha de equipo (02) + campo `incidencia_id` en modales de trazabilidad |

> **Nota de contrato (sub-proyecto 2):**
> - `IncidenciaOut` (campos): `id`, `codigo` (RMA-NNNN), `equipo_id`, `componente_id`, `titulo`, `descripcion_problema`, `prioridad` (`baja|media|alta`), `estado` (`abierta|diagnostico|en_reparacion|resuelta|cerrada`), `asignado_a`, `en_garantia`, `diagnostico`, `resolucion`, `fecha_apertura`, `fecha_diagnostico`, `fecha_inicio_reparacion`, `fecha_resolucion`, `fecha_cierre`, `notas`.
> - `IncidenciaFicha` (shape de `GET /api/incidencias/{id}`): `{ incidencia: IncidenciaOut, equipo, componente, cliente, cambios_configuracion[], movimientos[] }`.
> - Los endpoints de trazabilidad aceptan `incidencia_id?` opcional: `POST /api/equipos/{id}/movimientos`, `POST /api/componentes/{id}/montar`, `POST /api/componentes/{id}/desmontar`, `POST /api/equipos/{id}/sustituir-componente`.

## Mejoras sueltas

| # | Prompt | Pantalla / contenido |
|---|--------|----------------------|
| 11 | `11_filtro_serie_base_instalada.md` | **Actualización** de la Base instalada (01): buscador por nº de serie en la tabla. Backend `GET /api/equipos?numero_serie=` (parcial, insensible a mayúsculas, incluye serie de componentes). |
| 12 | `12_mapa_mundial.md` | **Nueva pantalla** `/mapa`: mapa mundial interactivo (Leaflet + OSM) de base instalada. Backend `GET /api/mapa/ubicaciones` (un marcador por ubicación con coords y ≥1 equipo; filtros cliente + incluir bajas). Geocodificación al guardar ubicación (Nominatim) + lat/lon manual. |
| 13 | `13_analitica_garantia.md` | **Nueva pantalla** `/analitica`: estadísticas de incidencias (por tipo/producto/técnico/prioridad/estado/cliente), KPIs de tiempo (MTTR/diagnóstico/edad), tendencia mensual y fiabilidad. Backend `GET /api/analitica/incidencias` (filtros desde/hasta/tipo/cliente_id). Incluye **tipo de incidencia** (RMA/Soporte Venta/Soporte Técnico/Calibración) y **control de garantía**: campos `version`, `numero_serie_cliente`, `meses_garantia` en equipo + badge de estado de garantía (vigente/por_vencer/vencida/sin_datos) y RMA en/fuera de garantía. |

> **Nota de contrato (analítica + garantía, prompt 13):**
> - `IncidenciaOut`/`IncidenciaCreate`/`IncidenciaUpdate` ganan `tipo` (`rma|soporte_venta|soporte_tecnico|calibracion`, default `rma`). El listado acepta `?tipo=`. El código es `RMA-/SV-/ST-/CAL-NNNN` según el tipo. En RMA, `en_garantia` se autodetecta del equipo al crear (editable).
> - `EquipoOut`/`EquipoCreate`/`EquipoUpdate` ganan `version`, `numero_serie_cliente`, `meses_garantia`; `EquipoOut` además expone derivados de solo lectura `fecha_fin_garantia` y `estado_garantia`. `ProductoCreate/Out` ganan `meses_garantia_default` (default 24, heredado por el equipo al alta).
> - `GET /api/analitica/incidencias?desde=&hasta=&tipo=&cliente_id=` → `AnaliticaIncidencias` (ver el prompt 13 para el shape completo).

| # | Prompt | Pantalla / contenido |
|---|--------|----------------------|
| 14 | `14_bitacora_avances.md` | **Bitácora de avances** por incidencia. Popup desde la lista (`/incidencias`) + sección en la ficha. Backend `GET/POST/PATCH/DELETE /api/incidencias/{id}/avances` y `avances[]` en el expediente. Entrada = `fecha` + `autor` + `tipo` (avance/report/llamada/visita/diagnostico/otro) + `texto`. |

> **Nota de contrato (bitácora, prompt 14):**
> - `Avance` = `{id, incidencia_id, fecha (ISO), autor|null, tipo (avance|report|llamada|visita|diagnostico|otro), texto}`. `IncidenciaFicha` gana `avances: Avance[]`.
> - `GET /api/incidencias/{id}/avances` (orden desc), `POST` (201, `texto` obligatorio→422 si vacío, `fecha` default hoy), `PATCH .../{avance_id}` (no enviar `null` en fecha/tipo/texto), `DELETE .../{avance_id}` (204).

| # | Prompt | Pantalla / contenido |
|---|--------|----------------------|
| 15 | `15_categoria_base_instalada.md` | **Categoría de familia** en la base instalada: columna + filtro por categoría (ATE/YAV Module/fastATE Module/Test Fixture/Test Handler/Otro). Backend `Producto.categoria`, `categoria` en `EquipoOut`/`ComponenteOut`, filtro `GET /api/equipos?categoria=`. Selector en el alta/edición de producto + badge por componente en la ficha. |

> **Nota de contrato (categoría, prompt 15):**
> - `categoria` (slug `ate|yav_module|fastate_module|test_fixture|test_handler|otro`, nullable) en `Producto` (catálogo). `EquipoOut` y `ComponenteOut` la exponen (derivada del producto, solo lectura).
> - `ProductoCreate`/PUT aceptan `categoria`. `GET /api/equipos?categoria=<slug>` filtra la base instalada (combinable con `numero_serie`/`part_number`/`estado`/`producto_id`).

| # | Prompt | Pantalla / contenido |
|---|--------|----------------------|
| 16 | `16_resumen_servicio.md` | **Cabecera "Resumen de servicio · EN VIVO"**: 4 KPIs (Incidencias abiertas · RMA abierto · En reparación · Tiempo medio de cierre 30d), elimina "SLA en riesgo". Backend `GET /api/analitica/resumen` → `ResumenServicioOut` (`incidencias_abiertas`/`_alta`, `rma_abierto`, `en_reparacion`, `cerradas_30d`, `tiempo_medio_cierre_dias`). |
| 17 | `17_fix_nueva_incidencia_popup.md` | **FIX (solo frontend):** "Nueva incidencia" no funcionaba — `incidencias.tsx` (ruta padre) no renderizaba `<Outlet/>`, así que las rutas hijas `/incidencias/nueva` y `/incidencias/$id` no se pintaban. Arregla el routing (layout + `incidencias.index.tsx`) y convierte "Nueva incidencia" en un **popup** reutilizable (`NuevaIncidenciaForm`), también usado desde la ficha de equipo. Sin cambios de backend. |
| 19 | `19_auth_auditoria.md` | **Login + auditoría**: página pública `/login` + Bearer token en `api()` + logout/usuario en cabecera + sección "Historial de cambios" por ficha (`GET /api/auditoria`). Backend: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `GET /api/auditoria`. |
| 20 | `20_ayuda_contextual.md` | **Ayuda contextual**: componente `<HelpTip clave=...>` (tooltip "?") que carga el catálogo `GET /api/ayuda` y muestra el texto por clave, colocado junto a campos/secciones clave. Backend: `GET/PUT/DELETE /api/ayuda` (catálogo editable, sembrado). |
| 27 | `27_wizard_alta_equipo.md` | **Rediseño** de `/equipos/nuevo` como wizard de 4 pasos (inglés) con barra de progreso, valores por defecto inteligentes y paso de revisión final. Una sola llamada al backend al confirmar: `POST /api/equipos/alta`. |

## Identidad corporativa (de `6TL_Línies bàsiques imatge corporativa.pdf`)
- **Lila** `#9e007e` (Pantone 2415C) — color de marca / acento primario
- **Gris** `#3d3d3f` · **Negro** `#000000` · **Blanco** `#ffffff`
- Tipografías: **Open Sans** (principal) · **Roboto** (secundaria/datos)
- Isotipo: círculo lila con "6TL" en blanco (SVG oficial pendiente — el prompt 00 crea uno fiel sustituible)

## Notas de validación (método habitual)
- Tras pegar cada prompt: verificar contrato (nombres de campo exactos), no fiarse de "errores CORS" engañosos (pueden ser 500 silenciosos o desajuste de nombre de campo).
- Arrancar backend antes: `.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8020` desde `backend/`.
