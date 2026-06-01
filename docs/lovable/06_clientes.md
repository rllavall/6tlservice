# Prompt Lovable 06 — Clientes (entidad maestra)

> Requiere prompt 00. Identidad 6TL (lila `#9e007e`, Open Sans/Roboto). NO toques shell/cliente API/otras pantallas. Ruta `/clientes`. Debe estar en la navegación (item "Clientes", icono `building-2`).

---

Implementa **Clientes** en `/clientes`. Un Cliente es el **cliente final / dueño** de los sistemas entregados. Un cliente puede tener varias **ubicaciones/plantas** (gestionadas en el prompt 05) y varios **equipos** (sistemas entregados). Es una entidad maestra de la que dependen ubicaciones y equipos.

## Datos — `Cliente`
`{ id, nombre, cif, persona_contacto, email_contacto, telefono_contacto, notas }`

Endpoints:
- Listar: `GET /api/clientes` (ordenados por nombre).
- Obtener: `GET /api/clientes/{id}`.
- Crear: `POST /api/clientes`, body `{ nombre, cif?, persona_contacto?, email_contacto?, telefono_contacto?, notas? }` (solo `nombre` obligatorio).
- Editar: `PUT /api/clientes/{id}` (mismo body).
- Borrar: `DELETE /api/clientes/{id}` (204). Puede dar **409 "Cliente en uso; no se puede borrar"** si tiene ubicaciones o equipos asociados — captúralo en toast claro.

Cruces útiles (lookups, no hay endpoint dedicado):
- Ubicaciones del cliente: `GET /api/ubicaciones` y filtra en cliente por `cliente_id`.
- Equipos del cliente: `GET /api/equipos` y filtra en cliente por `cliente_id`.

## UI
- Título "Clientes" (Open Sans) + botón primario lila **"+ Nuevo cliente"**.
- **Tabla:** Nombre (destacado), CIF, Persona de contacto, Email, Teléfono. Acciones: Editar, Borrar (confirmación).
- Buscador local por nombre/CIF (filtra la lista cargada).
- **Crear/Editar en modal:** nombre (obligatorio), CIF, persona de contacto, email (valida formato email en cliente), teléfono, notas.
- **Detalle / ficha de cliente** (al pulsar una fila, panel o `/clientes/:id`):
  - Datos de contacto.
  - **Plantas/ubicaciones del cliente:** lista filtrada de `GET /api/ubicaciones` por `cliente_id`, con dirección y enlace a `/ubicaciones`.
  - **Equipos del cliente:** lista filtrada de `GET /api/equipos` por `cliente_id`, con nº de serie + modelo y enlace a cada ficha `/equipos/{id}`. Es la vista "todo lo que tiene este cliente".
- Estado vacío con isotipo gris claro: "Sin clientes — crea el primero".

## Detalle visual
Lila como acento, datos (CIF, teléfono) en Roboto, badges discretos. Email como enlace `mailto:`. Confirmación antes de borrar.

Respeta nombres de campo exactos. No inventes endpoints.
