# Prompt Lovable 41 — Modal de edición de producto: 2 columnas + footer fijo

**Problema:** en `src/routes/catalogo.tsx`, el modal de crear/editar producto
(`<Dialog open={modalOpen}>` → `<DialogContent className="sm:max-w-lg">`, sobre la
línea 436) es demasiado alto para un componente (~12 campos). No limita la altura ni
tiene scroll, así que el `<DialogFooter>` con el botón **Guardar** se sale por debajo
de la pantalla y no se puede pulsar.

**Objetivo:** modal más ancho con los campos en **2 columnas**, cuerpo con scroll y el
footer (Cancelar / Guardar) **siempre visible** abajo.

## Cambios (SOLO maquetación — NO toques lógica)

Este cambio es puramente de layout/CSS/markup en ese `<Dialog>`. **NO** modifiques:
- el estado (`form`, `touched`, `editing`, `modalOpen`, `partNumberError`),
- los handlers (`onChange`, `onValueChange`, `submit`, `saveMut`),
- la validación ni el contrato de `body` del POST/PUT,
- la lógica condicional de campos (categoría solo si `tipo==="equipo"`,
  `categoria_componente` + los 3 toggles de trazabilidad solo si `tipo==="componente"`).

Solo cambian clases de CSS y el envoltorio (grid) alrededor de los campos.

### 1. `DialogContent`: más ancho + altura máxima + columna flex
Cambia:
```
<DialogContent className="sm:max-w-lg">
```
por:
```
<DialogContent className="sm:max-w-2xl max-h-[90vh] flex flex-col">
```

### 2. El `<form>`: que ocupe el alto disponible en columna
Cambia:
```
<form onSubmit={submit} className="space-y-4">
```
por:
```
<form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
```

### 3. Envuelve TODOS los campos (no el footer) en un grid de 2 columnas con scroll
Justo dentro del `<form>`, envuelve todos los bloques de campos (desde "Part number"
hasta "Notas", **sin incluir** el `<DialogFooter>`) en este contenedor:
```
<div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto px-1 pb-2 sm:grid-cols-2">
  ... (todos los <div className="space-y-1.5"> de los campos) ...
</div>
```
- En pantallas pequeñas es 1 columna (`grid-cols-1`); en ≥sm pasa a 2 (`sm:grid-cols-2`).
- Cada bloque de campo sigue siendo su `<div className="space-y-1.5">` (no los toques);
  el grid los coloca en 2 columnas automáticamente.

### 4. Campos que deben ocupar las 2 columnas (ancho completo)
Añade `className="... sm:col-span-2"` al `<div>` contenedor de estos campos:
- **Descripción** (textarea)
- **Notas** (textarea)
- El **bloque de los 3 toggles de trazabilidad** (Afecta al resultado de medida /
  Bajo coste / nivel_trazabilidad_override) — que el grupo entero ocupe toda la fila.
- El mensaje de error de part number sigue bajo su campo (no cambia).

(Part number, Tipo, Categoría/Categoría componente, Fabricante, Fabricante (select del
maestro), Modelo, P/N fabricante quedan en media columna cada uno.)

### 5. `DialogFooter`: fuera del scroll, fijo abajo
El `<DialogFooter>` debe quedar FUERA del `<div>` con scroll del punto 3 (hermano de él,
dentro del `<form>`). Dale separación superior:
```
<DialogFooter className="shrink-0 border-t pt-4">
```
Mantén los dos botones tal cual (Cancelar + Guardar/Crear con `saveMut.isPending`).

## Resultado esperado
- El modal de editar un componente cabe en pantalla; los campos van en 2 columnas.
- Si aún así hay muchos campos, el cuerpo hace scroll y **Cancelar/Guardar siguen
  visibles** abajo (no se salen).
- En móvil/estrecho vuelve a 1 columna.
- Aplica igual a "Nuevo producto" y a "Editar producto" (es el mismo `<Dialog>`).
