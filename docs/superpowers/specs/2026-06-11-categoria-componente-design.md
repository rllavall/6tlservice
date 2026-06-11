# Categoría de componente — diseño

**Fecha:** 2026-06-11
**Proyecto:** 6TL Postventa ("6tlservice") — backend FastAPI + frontend Lovable
**Estado:** aprobado para implementación

## Objetivo

Clasificar cada componente de la base instalada en una de cuatro **categorías
funcionales**: **Instrumento**, **Mass Interconnect**, **Wiring** y **Accesories**.
Esto permite agrupar, filtrar y leer de un vistazo qué tipo de elemento es cada
componente del BOM de un equipo (p. ej. los ~131 componentes del iUTB-Power
0869660000002 SN 001 de Indra/Aranjuez).

Esta clasificación es un **eje nuevo e independiente** del `Producto.categoria`
existente (`ate/yav_module/fastate_module/test_fixture/test_handler/otro`), que
describe el tipo de producto 6TL, no su función dentro de un equipo de test.

## Decisiones tomadas

- **Dónde vive el dato:** en el **producto** (catálogo), no en cada componente.
  Un mismo P/N tiene siempre la misma categoría funcional, así que clasificar
  119 productos basta y el componente la **hereda**. Refleja exactamente el
  patrón del `categoria` actual.
- **Auto-clasificación con revisión:** un script siembra la categoría por reglas
  y el usuario corrige los dudosos después desde la UI.
- **Campo opcional:** vacío = sin clasificar (no se fuerza a clasificar todo).

## Modelo de datos

Nueva columna nullable en `productos`:

```
categoria_componente  TEXT  NULL
```

Valores permitidos (slug → etiqueta visible):

| slug               | etiqueta            |
|--------------------|---------------------|
| `instrumento`      | Instrumento         |
| `mass_interconnect`| Mass Interconnect   |
| `wiring`           | Wiring              |
| `accesorios`       | Accesories          |

- Migración idempotente en `app/migrations.py` (entrada en el dict `productos`,
  igual que `categoria`/`pn_fabricante`). `create_all` no añade columnas a tablas
  existentes, por eso va por `ensure_schema`/ALTER.
- `Componente.categoria_componente` como **propiedad de solo lectura** que
  devuelve `self.producto.categoria_componente` (idéntico al `categoria` heredado
  actual del modelo `Componente`).

## API

- **Validación** con `Literal["instrumento","mass_interconnect","wiring","accesorios"]`
  (constante `_CATEGORIA_COMPONENTE` en `schemas.py`, junto a `_CATEGORIA`).
- `ProductoCreate` / `ProductoUpdate`: nuevo campo opcional `categoria_componente`.
- `ProductoOut`: expone `categoria_componente`.
- `ComponenteOut`: expone `categoria_componente` (derivada del producto), igual
  que ya hace con `categoria`.
- **Filtros de lista:**
  - `GET /api/productos?categoria_componente=<slug>`
  - `GET /api/componentes?categoria_componente=<slug>` (subconsulta por
    `Producto.id` con esa categoría, igual que el filtro `categoria` en
    `routers/equipos.py`).

## Carga de datos — auto-clasificación (script throwaway)

Script `backend/_clasificar_categoria_componente.py` (gitignored por `_*.py`),
auditado como `usuario="alta manual"`, con backup previo de `postventa.db` y
flag `--commit`. Reglas, evaluadas en orden (primera que casa gana):

1. **Mass Interconnect** — fabricante/descr. contiene `Virginia Panel` o P/N
   empieza por `VP`.
2. **Wiring** — descripción contiene `lead`, `cable`, `patch`, `cord`, `wire`,
   `wiring` o `harness`.
3. **Instrumento** — fabricante en {Keysight, Agilent, National Instruments, NI,
   Pickering, Chroma, Ametek, Höcherl, Hocherl}.
4. **Accesories** — todo lo demás (6TL, Cliff, tornillería, etc.).

El script imprime el conteo por categoría y la lista de los clasificados como
`accesorios` para que el usuario revise los dudosos. **No** es la verdad final:
es un punto de partida editable en la UI.

## Frontend (prompt Lovable)

Un único prompt Lovable nuevo:

1. **Selector** "Categoría de componente" en alta/edición de producto. Relevante
   sólo cuando `tipo === "componente"` (se puede ocultar/deshabilitar si es
   equipo). Opciones = las 4 etiquetas + "(sin clasificar)".
2. **Badge** de categoría por componente en la ficha del equipo (lista de
   componentes), leyendo `componente.categoria_componente`.
3. **Filtro** por categoría de componente en el catálogo / listado.

## Construcción

- Backend con **TDD directo** (alcance pequeño: 1 columna + propiedad derivada +
  schema + 2 filtros + script de clasificación).
- Cobertura de tests:
  - migración añade la columna (idempotente).
  - `ProductoCreate` acepta slug válido y rechaza inválido.
  - `ProductoOut`/`ComponenteOut` exponen el campo; el componente lo hereda.
  - filtro `GET /api/productos?categoria_componente=` y
    `GET /api/componentes?categoria_componente=` devuelven sólo lo que toca.
- Frontend por prompt Lovable como el resto del proyecto.

## Fuera de alcance (YAGNI)

- No se añade entidad/tabla de categorías editable (las 4 son fijas por Literal).
- No se migra `Componente` para que tenga categoría propia (siempre heredada del
  producto).
- No se toca el eje `Producto.categoria` existente.
