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

## Identidad corporativa (de `6TL_Línies bàsiques imatge corporativa.pdf`)
- **Lila** `#9e007e` (Pantone 2415C) — color de marca / acento primario
- **Gris** `#3d3d3f` · **Negro** `#000000` · **Blanco** `#ffffff`
- Tipografías: **Open Sans** (principal) · **Roboto** (secundaria/datos)
- Isotipo: círculo lila con "6TL" en blanco (SVG oficial pendiente — el prompt 00 crea uno fiel sustituible)

## Notas de validación (método habitual)
- Tras pegar cada prompt: verificar contrato (nombres de campo exactos), no fiarse de "errores CORS" engañosos (pueden ser 500 silenciosos o desajuste de nombre de campo).
- Arrancar backend antes: `.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8020` desde `backend/`.
