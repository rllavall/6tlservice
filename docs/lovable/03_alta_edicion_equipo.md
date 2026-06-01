# Prompt Lovable 03 — Alta / edición de equipo

> Requiere prompts 00–02. Identidad 6TL (lila `#9e007e`, Open Sans/Roboto). NO toques shell/cliente API/otras pantallas. Añade rutas `/equipos/nuevo` y `/equipos/:id/editar`.

---

Implementa **alta y edición de equipo**.

## Alta — ruta `/equipos/nuevo`
Formulario en card centrada, título "Nuevo equipo" (Open Sans).

**Datos del equipo** → `POST /api/equipos`, body `EquipoCreate`:
`{ numero_serie, producto_id, cliente?, fecha_fabricacion?, fecha_entrega?, estado?, notas? }`, `estado` por defecto "operativo".
Campos:
- **Modelo (producto):** select obligatorio, poblado con `GET /api/productos?tipo=equipo` (muestra `part_number — descripcion`). Si no hay productos tipo equipo, muestra aviso con enlace a `/catalogo` ("Crea primero el modelo en el catálogo").
- **Nº de serie:** texto obligatorio (Roboto).
- **Cliente:** texto.
- **Fecha fabricación / Fecha entrega:** date.
- **Estado:** select operativo/baja (default operativo).
- **Notas:** textarea.

Al guardar con éxito (201) → navega a la ficha `/equipos/{id}` del equipo creado, toast "Equipo creado".
Errores: 409 "El producto referenciado no es de tipo 'equipo'" o "Ya existe un equipo con ese (producto, numero_serie)" → muéstralos en el formulario (el segundo, junto al campo nº de serie).

**Componentes iniciales (opcional, en la misma alta):**
Tras crear el equipo, ofrece (en la misma pantalla o paso 2) añadir sus componentes serializados de inicio. Para cada componente:
1. Crea el componente: `POST /api/componentes`, body `{ numero_serie, producto_id, notas? }` con `producto_id` de un producto `tipo=componente` (select desde `GET /api/productos?tipo=componente`). NO pongas `equipo_id` aquí.
2. Móntalo en el equipo recién creado: `POST /api/componentes/{id}/montar` con `{ equipo_id, posicion?, fecha, motivo: "entrega_inicial" }`.
Permite añadir varias filas (componente + posición). Si el usuario no añade ninguno, no pasa nada: puede hacerlo luego desde la ficha. Mantén esto simple y claro; si una fila falla, muestra su error y deja seguir con las demás.

## Edición — ruta `/equipos/:id/editar`
Carga el equipo (`GET /api/equipos/{id}` → usa `equipo`). Edita solo campos mutables → `PUT /api/equipos/{id}`, body `EquipoUpdate` (parcial): `{ cliente?, fecha_fabricacion?, fecha_entrega?, estado?, notas? }`.
**Importante:** `numero_serie` y `producto_id` NO son editables aquí (se fijan en el alta); muéstralos como solo-lectura. La gestión de componentes se hace desde la ficha (prompt 02), no aquí.
Al guardar → vuelve a la ficha, toast "Equipo actualizado".

## Detalle visual
Botón primario lila "Guardar", secundario "Cancelar" (vuelve atrás). Validación inline. Campos de datos en Roboto. Sin colores fuera de la paleta de marca.

No inventes campos ni endpoints. Respeta los nombres de campo exactos del contrato.
