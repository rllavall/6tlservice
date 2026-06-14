# Criticidad → nivel de trazabilidad (apartado componentes)

**Fecha:** 2026-06-14
**Estado:** aprobado, en implementación
**Rama:** `feat/criticidad-trazabilidad`

## Contexto y objetivo

Adaptar la app (sobre todo el apartado de componentes) a las conclusiones sobre
trazabilidad en entornos ATE:

1. No trazar individualmente cables estándar ni elementos de bajo coste.
2. Trazar siempre los elementos que afectan al resultado de medida.
3. Controlar fixtures, adaptadores y software por versión/revisión.
4. Implementar una clasificación de criticidad que determine **automáticamente**
   el nivel de trazabilidad.
5. Dar máxima importancia a la gestión de configuración (baseline) e histórico de
   cambios. **(Fuera de alcance de este sub-proyecto; segundo sub-proyecto.)**

Además, dos requisitos del usuario:
- La configuración del ATE es "qué componentes (con su serie/versión) están
  integrados en este equipo (nº de serie)".
- Minimizar el trabajo manual del operario al introducir series y configuración.

## Decisiones

- **Criticidad** legible: `ALTA` · `MEDIA` · `BAJA` (derivada, no se guarda).
- **Nivel de trazabilidad** (derivado): `serie` · `version` · `no_trazado`.
- La criticidad y el nivel se **derivan automáticamente** de señales del producto,
  con override manual por producto.
- 3 niveles (no "por lote": YAGNI, no aparece en las conclusiones).

## Modelo de datos

### `Producto` (nuevas columnas)
- `afecta_a_medida: bool` (default `false`) — conclusión 2.
- `bajo_coste: bool` (default `false`) — conclusión 1.
- `nivel_trazabilidad_override: str|null` — gana sobre la derivación.
- `categoria_componente`: añadir `software` y `fixture_adaptador` a las 4 actuales
  (`instrumento`, `mass_interconnect`, `wiring`, `accesorios`).
- Propiedades derivadas (modelo, estilo `Equipo.estado_garantia`):
  `criticidad`, `nivel_trazabilidad` → delegan en `app/criticidad.py`.

### `Componente` (cambios)
- `numero_serie` pasa a **opcional** (null en `no_trazado`; placeholder
  `"S/N pendiente …"` en `serie` sin escanear). El unique `(producto_id,
  numero_serie)` tolera múltiples NULL en SQLite.
- `revision: str|null` — versión/revisión de la unidad montada (conclusión 3).
- Propiedad derivada `nivel_trazabilidad` (del producto).

### `PlantillaComponente` (entidad nueva) — configuración esperada por producto-equipo
- `producto_equipo_id` (FK productos, tipo equipo)
- `producto_componente_id` (FK productos, tipo componente)
- `posicion: str|null`
- `cantidad: int` (default 1)

## Derivación (`app/criticidad.py`, puro)

Cascada en orden (primera que casa gana):

| Condición | Criticidad | Nivel |
|---|---|---|
| `nivel_trazabilidad_override` presente | derivada de criticidad base | = override |
| `afecta_a_medida` | ALTA | `serie` |
| categoría `software` o `fixture_adaptador` | ALTA | `version` |
| categoría `instrumento` o `mass_interconnect` | ALTA | `serie` |
| `bajo_coste` (típico `wiring`/`accesorios`) | BAJA | `no_trazado` |
| resto | MEDIA | `serie` |

`criticidad` se infiere también cuando hay override (la criticidad no es override,
solo el nivel lo es): se usa la misma cascada ignorando el override para criticidad.

## Flujo / endpoints

- `criticidad` y `nivel_trazabilidad` expuestos en `ProductoOut`; `nivel_trazabilidad`
  en `ComponenteOut`; `revision` en `ComponenteOut`/`ComponenteUpdate`.
- CRUD de `PlantillaComponente` por producto-equipo:
  `GET/POST/DELETE /api/productos/{id}/plantilla` (+ PATCH cantidad/posición).
- Alta de equipo desde plantilla: `EquipoAltaCreate.desde_plantilla: bool`.
  Construye las líneas según nivel:
  - `serie` → placeholder de serie (escaneable),
  - `version` → sin serie (revisión pendiente),
  - `no_trazado` → sin serie, presente.
- Comparación config real vs esperada:
  `GET /api/equipos/{id}/configuracion` → `{esperados, presentes, faltantes,
  sobrantes, series_pendientes, versiones_pendientes}`.
- Escaneo DataMatrix: sin cambios de fondo; las líneas `no_trazado` no requieren escaneo.

## Fuera de alcance
- Baseline por unidad + diff contra baseline (conclusión 5) → 2º sub-proyecto.
- Importar BOM desde el sistema ATE (`6TL_Escandalls`) → futuro.

## Plan de incrementos (TDD)
1. `app/criticidad.py` puro + tests.
2. Columnas `Producto`/`Componente` + migración + propiedades + schemas (categorías nuevas).
3. `PlantillaComponente` + servicio + router CRUD + tests.
4. Alta desde plantilla + tests.
5. Comparación config real vs esperada + endpoint + tests.
