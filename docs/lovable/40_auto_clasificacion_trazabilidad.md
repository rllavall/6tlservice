# Prompt Lovable 40 — Auto-clasificación de trazabilidad (badge Auto/Manual + motivo)

Contexto: el backend ahora **auto-rellena** los flags `afecta_a_medida` y `bajo_coste`
de los productos componente (motor de reglas + agente LLM para ambiguos). Cada producto
trae `clasificacion_origen` (`agente` | `manual` | null) y `clasificacion_motivo` (texto).
NO toques otras pantallas. Esto es un refinamiento de la UI del prompt 39.

## 1. Catálogo de productos (`/catalogo`) — origen de la clasificación
En la ficha/tabla de producto **componente**, junto a los badges existentes de
`criticidad` y `nivel_trazabilidad` (prompt 39), añade un badge de **origen**:
- `clasificacion_origen === "agente"` → badge gris "Auto" con icono ✨/robot.
- `clasificacion_origen === "manual"` → badge lila "Manual".
- `null` → sin badge (aún sin clasificar).
Al pasar el ratón por el badge (o un icono "i" al lado), muestra un tooltip con
`clasificacion_motivo` (p. ej. "categoria instrumento: afecta a medida" o
"LLM: es un cable de sense Kelvin").

## 2. Comportamiento de los toggles (importante)
Los toggles `afecta_a_medida` y `bajo_coste` siguen siendo editables, pero su semántica
cambia:
- Si el usuario **edita** cualquiera de los dos toggles (o el `nivel_trazabilidad_override`)
  y guarda, el backend marca automáticamente `clasificacion_origen = "manual"` y deja de
  auto-clasificar ese producto. No tienes que mandar `clasificacion_origen`; basta con
  incluir el flag en el body del `POST`/`PUT`.
- Si el usuario crea/edita el producto **sin tocar** esos toggles (no los incluyas en el
  body si no se han modificado), el backend aplica las reglas automáticas y deja
  `clasificacion_origen = "agente"`.
- **Clave de contrato:** en el `PUT` de un producto, **no reenvíes** `afecta_a_medida` /
  `bajo_coste` / `nivel_trazabilidad_override` si el usuario no los ha cambiado en el
  formulario. Si los reenvías siempre, el backend lo interpretará como edición manual.
  (El backend ya protege los valores manuales previos si no los mandas.)

Opcional: muestra un texto de ayuda bajo los toggles: "Se rellenan automáticamente;
edítalos solo para forzar un valor (pasará a Manual)."

## 3. Acción "volver a automático" (opcional, recomendado)
En productos con `clasificacion_origen === "manual"`, ofrece un botón pequeño
"Volver a automático". Implementación simple desde el front: no hay endpoint dedicado;
basta con hacer un `PUT /api/productos/{id}` reenviando el producto **sin** los tres
campos manuales (`afecta_a_medida`, `bajo_coste`, `nivel_trazabilidad_override`) — el
backend re-aplicará las reglas y volverá a `origen = "agente"`.

## Campos / contrato
- `ProductoOut`: `clasificacion_origen` (string|null: `agente`|`manual`),
  `clasificacion_motivo` (string|null). `afecta_a_medida`/`bajo_coste`/`criticidad`/
  `nivel_trazabilidad`/`nivel_trazabilidad_override` ya existen (prompt 39).
- `ProductoCreate` (usado por POST y PUT): los flags son opcionales con default `false`/
  `null`. Inclúyelos en el body SOLO cuando el usuario los edite.

## Notas
- No cambies la cascada de criticidad ni el resto del formulario.
- El badge de origen es de solo lectura; lo único editable son los toggles del punto 2.
