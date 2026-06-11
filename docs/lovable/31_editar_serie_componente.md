# Prompt 31 — Editar el número de serie de un componente montado

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()`, React Query (`qc`), shadcn, paleta lila `#9e007e`,
toasts con `sonner`). Trabaja en la ficha de equipo `src/routes/equipos.$id.tsx`.

## Objetivo
En la base instalada, muchos componentes se cargan con un nº de serie provisional (`S/N pendiente (item)`).
Necesitamos poder **escribir el nº de serie real** de cada componente ya montado, sin desmontarlo.

## Backend (ya existe, no lo toques)
- **`PATCH /api/componentes/{id}`** con body parcial `{"numero_serie": "<valor>"}`. Solo actualiza los campos
  enviados (no toca `equipo_id`/`posicion`/`fecha_montaje`: el componente sigue montado).
- Devuelve el `ComponenteOut` actualizado. Si el `(producto, numero_serie)` ya existe → **409**
  (`"Ya existe un componente con ese (producto, numero_serie)"`). 404 si el id no existe.

## UI a implementar
En la tabla de componentes de la ficha, cada fila tiene un menú (`DropdownMenu`) con "Sustituir" y "Desmontar".
Añade una tercera acción **"Editar nº de serie"** (icono `Pencil`).

1. Estado nuevo: `const [editarSerieFor, setEditarSerieFor] = useState<ComponenteMontado | null>(null)`.
2. `DropdownMenuItem` "Editar nº de serie" → `onClick={() => setEditarSerieFor(c)}`.
3. Un `Dialog` (controlado por `editarSerieFor`) con:
   - Título "Editar nº de serie" y, como subtítulo, el part number + descripción del componente y su posición.
   - Un `Input` prefilled con `editarSerieFor.numero_serie`.
   - Botones "Cancelar" y "Guardar".
4. Al guardar: `useMutation` que llama
   ```ts
   api(`/api/componentes/${editarSerieFor.id}`, { method: "PATCH", body: JSON.stringify({ numero_serie: valor.trim() }) })
   ```
   - onSuccess: `qc.invalidateQueries({ queryKey: ["equipo", id] })`, `toast.success("Nº de serie actualizado")`, cierra el diálogo.
   - onError: si el status es 409, `toast.error("Ese nº de serie ya existe para este componente")`; si no, muestra el mensaje del error.
   - Deshabilita "Guardar" si el input está vacío o igual al valor actual.

## Notas
- No cambies tipos: `ComponenteMontado` ya tiene `numero_serie`.
- Los componentes de Virginia Panel y cableado están marcados `N/D (item)` a propósito (no trazan serial); el usuario
  puede editarlos igual si hiciera falta, no hay que bloquearlos.
- No toques "Sustituir" ni "Desmontar".
