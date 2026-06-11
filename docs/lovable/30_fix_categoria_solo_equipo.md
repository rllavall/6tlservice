# Prompt 30 — Fix: `categoria` es SOLO del equipo; el componente usa SOLO `categoria_componente`

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, tipos en `@/lib/types`). Corrige el
solapamiento entre los dos ejes de clasificación introducido por los prompts 15 y 29.

**Regla de negocio:**
- `categoria` (ate / yav_module / fastate_module / test_fixture / test_handler / otro) → aplica **solo a productos de tipo `equipo`**.
- `categoria_componente` (instrumento / mass_interconnect / wiring / accesorios) → aplica **solo a productos de tipo `componente`**.
- Un componente **no** tiene `categoria`; un equipo **no** tiene `categoria_componente`.

## 1. Catálogo — formulario de producto (`src/routes/catalogo.tsx`)
- El selector **"Categoría"** debe mostrarse **solo cuando `form.tipo === "equipo"`** (envuélvelo en `{form.tipo === "equipo" && ( … )}`),
  igual que "Categoría de componente" ya se muestra solo para `componente`.
- En el `body` del POST/PUT, manda `categoria: null` cuando el tipo no es equipo (simétrico a `categoria_componente`):
  ```ts
  categoria: form.tipo !== "equipo" || form.categoria === "" ? null : form.categoria,
  categoria_componente: form.tipo !== "componente" || form.categoria_componente === "" ? null : form.categoria_componente,
  ```

## 2. Ficha de equipo — lista de componentes (`src/routes/equipos.$id.tsx`)
- En cada fila de componente, **elimina el badge de `categoria`** (`CATEGORIA_LABEL[c.categoria]`). Deja **solo** el badge de
  `categoria_componente` (`CATEGORIA_COMPONENTE_LABEL[c.categoria_componente]`).
- Quita el import de `CATEGORIA_LABEL` si queda sin usar en ese archivo.

No toques el backend (ambos campos siguen siendo nullable en cualquier producto; es solo regla de presentación).
No inventes endpoints ni cambies slugs.
