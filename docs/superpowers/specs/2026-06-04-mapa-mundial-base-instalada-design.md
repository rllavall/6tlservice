# Mapa mundial de base instalada — Diseño

**Fecha:** 2026-06-04
**Estado:** Aprobado

## Objetivo
Un apartado nuevo (`/mapa`) con un mapa mundial interactivo que muestra dónde hay
producto 6TL instalado: un pin por ubicación, con el detalle de los equipos que hay allí.

## Decisiones (brainstorming)
- **Granularidad:** pines por ubicación (B). Cada `Ubicacion` se geocodifica desde su
  dirección, de modo que dos ubicaciones de la misma ciudad no se solapan; el pin muestra la ciudad.
- **Coordenadas:** geocodificar al guardar vía Nominatim (OSM, gratis) **+** campos lat/lon
  editables manualmente como override/respaldo.
- **Qué se pinta:** solo equipos con ubicación actual conocida (último movimiento) y `operativo`;
  toggle para incluir `baja`.
- **Mapa:** Leaflet + tiles OpenStreetMap (sin API key), estilo oscuro.

## Modelo de datos
- `Ubicacion`: añadir `latitud: float?`, `longitud: float?`.
- Micro-migración idempotente `app/migrations.py` (tras `create_all`): `ALTER TABLE ubicaciones
  ADD COLUMN ...` solo si la columna no existe (`PRAGMA table_info`). No se pierde la BD/seed.

## Geocodificación — `app/geocoding.py`
- `geocode(direccion, ciudad, provincia, pais) -> (lat, lon) | None` contra Nominatim, con
  `User-Agent` propio. Inyectable para tests (sin red).
- En `POST`/`PUT` de ubicación:
  - Si el payload trae `latitud`/`longitud` → se usan (override manual).
  - Si no, y hay `ciudad`+`pais` → se geocodifica y se guarda.
  - Si el geocoder falla → coords `null`, **sin romper el guardado**.
- Script throwaway `_geocode_backfill.py` ("No commitear") para rellenar coords existentes.

## Backend — endpoint
- `GET /api/mapa/ubicaciones?incluir_baja=false&cliente_id=`
- Helper `equipos_por_ubicacion(db, incluir_baja, cliente_id)` en `trazabilidad.py`: por cada
  equipo filtrado, calcula `ubicacion_actual` (último movimiento) y agrupa por ubicación.
- Devuelve solo ubicaciones **con coords** y **con ≥1 equipo**:
  ```json
  { "ubicacion_id":1, "nombre":"...", "tipo":"fabrica_cliente",
    "ciudad":"Madrid", "provincia":"...", "pais":"España",
    "latitud":40.4, "longitud":-3.7,
    "cliente": {"id":2,"nombre":"..."},
    "num_equipos": 5,
    "equipos": [{"id":9,"numero_serie":"...","producto":"PN — descr","estado":"operativo"}] }
  ```

## Frontend — Lovable (TanStack Start)
- Prompt `docs/lovable/12_mapa_mundial.md`. Ruta `src/routes/mapa.tsx` + enlace "Mapa" en nav.
- react-leaflet + Leaflet + tiles OSM. Marcador por ubicación; popup con nombre/ciudad/cliente,
  nº de equipos y enlaces a fichas. Controles: filtro cliente + toggle incluir bajas. KPIs resumen.

## Tests (TDD, backend)
- `equipos_por_ubicacion`: último movimiento gana, solo operativos, filtro cliente, incluir_baja.
- Endpoint: forma del JSON; exclusión de ubicaciones sin coords y sin equipos.
- Geocoding: geocoder mockeado, override manual, fallo→coords null no rompe el POST.
- Schema `UbicacionOut`/`UbicacionCreate` aceptan lat/lon.
- Frontend: validación de contrato + smoke visual manual.

## Fuera de alcance (YAGNI)
Clustering de marcadores, heatmap, filtro por tipo de producto, histórico temporal.
