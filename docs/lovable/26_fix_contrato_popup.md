# Prompt 26 — FIX: ficha de contrato como popup (modal)

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()` que ya inyecta el Bearer token, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`).

## Problema a corregir
En la pantalla **Contratos** (`src/routes/contratos.tsx`), al hacer clic en una fila se navega a la ruta
`/contratos/$id` (`src/routes/contratos.$id.tsx`), **pero no se ve nada**: `contratos.$id` está anidado bajo
`contratos.tsx` y esa pantalla NO renderiza un `<Outlet/>`, así que el detalle nunca aparece.

**Solución pedida:** mostrar el detalle del contrato en un **modal (Dialog popup)** que se abre al hacer clic
en la fila, en vez de navegar a otra ruta. No uses una ruta hija para el detalle.

## Qué hacer
1. En `contratos.tsx`, **deja de navegar** a `/contratos/$id` en el `onClick` de la fila. En su lugar, guarda
   en estado el `id` del contrato seleccionado (`const [detalleId, setDetalleId] = useState<number|null>(null)`)
   y ábre el modal: `onClick={() => setDetalleId(c.id)}`.
2. Crea un **`<ContratoDetalleDialog>`** (en el mismo archivo o componente nuevo) que recibe `contratoId` y
   `onClose`, y se renderiza con shadcn `Dialog`. Cuando hay `contratoId`, hace
   `useQuery(["contrato", contratoId], () => api<ContratoDetalle>(\`/api/contratos/${contratoId}\`))` y muestra:
   - Cabecera: `codigo` (mono), `NivelBadge`, `EstadoContratoBadge`, cliente, vigencia
     (`fecha_inicio → fecha_fin`), `notas`.
   - **`nivel_detalle`** (si existe): Preventivo / Soporte / Respuesta.
   - **Tabla "Equipos cubiertos"** (`equipos[]`): nº de serie (enlace a `/equipos/$id`), producto, y botón de
     **desasignar** (`DELETE /api/contratos/{id}/equipos/{equipoId}`). Botón **"Asignar equipo"**
     (`POST /api/contratos/{id}/equipos` body `{equipo_id}`, 409 si el equipo es de otro cliente).
   - Acciones: **Editar** (reusa `ContratoFormDialog`), **Cancelar contrato** (`PUT {cancelado:true}`),
     **Borrar** (`DELETE`; si 409 → aviso "tiene equipos/acciones, cancélalo").
   - Tras cualquier mutación, invalida `["contrato", contratoId]` y `["contratos"]`.
3. **Reutiliza la lógica que ya está escrita** en `src/routes/contratos.$id.tsx` (las mutaciones de cancelar/
   borrar/asignar/desasignar y el sub-diálogo `AsignarEquipoDialog` ya existen ahí): muévela al
   `<ContratoDetalleDialog>`. Mantén exportados `NivelBadge`, `EstadoContratoBadge`, `ContratoFormDialog`.
4. **Elimina o vacía** la ruta `src/routes/contratos.$id.tsx` (ya no se usa). Si la borras, asegúrate de que
   el route tree se regenere (déjalo sin `createFileRoute` o bórralo del todo). Comprueba que `tsc` queda limpio.
5. El modal debe ser ancho (p.ej. `sm:max-w-2xl`) y con scroll interno si la tabla de equipos es larga.

No cambies la lógica de creación de contratos ni el resto de pantallas. Solo convierte el detalle en popup.
