# Categoría de familia en la base instalada — Diseño

**Fecha:** 2026-06-04
**Proyecto:** 6TL Postventa ("6tlservice")
**Estado:** diseño aprobado en brainstorming, pendiente de spec review + plan

## Problema / objetivo

La base instalada debe **distinguir la familia** de cada equipo: ATE, YAV Module, fastATE Module,
Test Fixture, Test Handler. Hoy el catálogo (`Producto`) solo tiene `tipo` (`equipo`/`componente`,
estructural) y `descripcion`; no hay una categoría de familia. Se añade `categoria` al producto y se
muestra/filtra en la base instalada.

Matiz del negocio: la **configuración de un ATE puede contener YAV Modules**, etc. Esto ya está
modelado — un ATE es un `Equipo` y sus módulos son los `Componente` montados en él. Por tanto la
categoría vive en el `Producto` (aplica a equipos *y* a componentes/módulos), y cada módulo montado
en un ATE puede mostrar su familia sin entidad nueva.

## Decisiones (brainstorming)

- **`categoria` vive en el catálogo (`Producto`)**, compartida por todas las unidades del mismo part
  number. Fuente única; no se denormaliza en `Equipo`.
- **Lista cerrada + Otro** (slugs): `ate | yav_module | fastate_module | test_fixture | test_handler | otro`.
- **Alcance UI:** columna "Categoría" + filtro en la base instalada (`GET /api/equipos?categoria=`).
- `Equipo.categoria` y `Componente.categoria` = **propiedades de solo lectura** que devuelven
  `producto.categoria` (no columnas nuevas), expuestas en `EquipoOut`/`ComponenteOut`.

## Modelo de datos

### `Producto`
- `+ categoria: Optional[str]` (nullable; valores `ate|yav_module|fastate_module|test_fixture|test_handler|otro`).
  Productos existentes quedan `null` (sin categoría) hasta clasificarlos.

### `Equipo` y `Componente` (sin columnas nuevas)
- Propiedad de solo lectura `categoria` que devuelve `self.producto.categoria` (o `None` si no hay
  producto cargado). Usa la relación `producto` ya existente en `Equipo`; en `Componente` se añade/usa
  la relación al producto si hace falta para la propiedad.

### Migración
`app/migrations.py::add_missing_columns()` (idempotente): `ALTER TABLE productos ADD COLUMN categoria TEXT`.

## API

- `ProductoCreate`/`ProductoUpdate`/`ProductoOut`: `+ categoria: Optional[Literal[...slugs...]]` (Create/Update),
  `Optional[str]` en Out.
- `EquipoOut`: `+ categoria: Optional[str]` (derivado del producto vía propiedad del modelo).
- `ComponenteOut`: `+ categoria: Optional[str]` (idem).
- `GET /api/equipos` (router equipos): nuevo parámetro `categoria: Optional[str] = None`; filtra los
  equipos por la categoría de su producto (join `Equipo.producto_id == Producto.id`,
  `Producto.categoria == categoria`). Combinable con los filtros existentes (`producto_id`, `estado`,
  `numero_serie`, `part_number`); mantener `.distinct()` donde ya se usa.

## Frontend (Lovable, prompt 15)

- **Base instalada** (`src/routes/index.tsx` / tabla de equipos): columna **"Categoría"** (badge) +
  **filtro por categoría** (select junto al buscador por nº de serie). Llama `GET /api/equipos?categoria=`.
  Mapa slug→etiqueta: `ate`→"ATE", `yav_module`→"YAV Module", `fastate_module`→"fastATE Module",
  `test_fixture`→"Test Fixture", `test_handler`→"Test Handler", `otro`→"Otro".
- **Alta/edición de producto** (catálogo, `src/routes/catalogo.tsx` o el form de producto): selector de
  `categoria` (6 opciones + "Sin categoría"). Envía/lee `categoria`.
- **Ficha de equipo**: en la lista de componentes (configuración), mostrar la `categoria` de cada
  módulo (badge), de modo que un ATE muestre sus YAV Modules etiquetados.
- Tipos en `types.ts`: `CategoriaProducto` (slugs); `categoria` en `Producto`, `Equipo`/`EquipoOut`,
  `Componente`/`ComponenteOut`.

## Testing (TDD)

- `Producto`: crear con `categoria` y devolverla (Create/Out).
- Propiedad `Equipo.categoria` = la del producto asociado; `None` si el producto no tiene categoría.
- Propiedad `Componente.categoria` = la del producto asociado.
- `GET /api/equipos?categoria=ate` devuelve solo equipos cuyo producto es `ate`; combinación con otro
  filtro; categoría inexistente → lista vacía.
- Migración idempotente añade `productos.categoria`.

## Fuera de alcance (YAGNI)

- Categoría por unidad (en `Equipo`) en vez de por catálogo.
- Agrupar / contar equipos por categoría.
- Exponer la categoría en analítica (fiabilidad por familia) o en el mapa.
- Reglas que validen qué categorías pueden montarse dentro de qué (p.ej. "un ATE solo admite YAV/fastATE").
