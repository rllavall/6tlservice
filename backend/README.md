# 6TL Postventa — Backend (trazabilidad + base instalada)

FastAPI + SQLAlchemy + SQLite. Sub-proyecto 1 de la plataforma postventa de 6TL.

## Setup
    python -m venv .venv
    .venv\Scripts\pip install -e ".[dev]"

## Tests
    .venv\Scripts\pytest -q

## Arrancar (puerto 8020 — evita choque con ATE/Quotify :8000 y dashboard :8010)
    .venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8020

Docs interactivas: http://127.0.0.1:8020/docs

## Modelo
6 entidades: Ubicacion, Producto (catálogo), Equipo, Componente, Movimiento (log de ubicación),
CambioConfiguracion (log de montajes/desmontajes). Ubicación actual = último movimiento; config
actual = componentes con equipo_id apuntando al equipo.

## Endpoints principales
- CRUD: `/api/ubicaciones`, `/api/productos`, `/api/equipos`, `/api/componentes`
- Ficha: `GET /api/equipos/{id}` (cabecera + config actual + ubicación actual + ambos historiales)
- Búsqueda global: `GET /api/buscar?serie=...`
- Equipos por part number: `GET /api/equipos?part_number=...`
- Equipos en una ubicación: `GET /api/ubicaciones/{id}/equipos`
- Movimientos: `POST /api/equipos/{id}/movimientos`
- Configuración: `POST /api/componentes/{id}/montar`, `/desmontar`, `POST /api/equipos/{id}/sustituir-componente`

## Limitaciones conocidas (v1)
- `GET /api/ubicaciones/{id}/equipos` calcula la ubicación actual por equipo en un scan O(n).
  Suficiente a escala de captura manual; optimizar con query windowed si la base instalada crece.
- Sin auth (uso interno 6TL). Portal de cliente y roles = fase posterior.
