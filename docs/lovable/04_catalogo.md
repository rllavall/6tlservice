# Prompt Lovable 04 — Catálogo (part numbers / productos)

> Requiere prompts 00–01. Identidad 6TL (lila `#9e007e`, Open Sans/Roboto). NO toques shell/cliente API/otras pantallas. Ruta `/catalogo`.

---

Implementa el **Catálogo** en `/catalogo`. Es el maestro de *modelos* (part numbers): tanto modelos de equipo como de componente. Cada equipo/componente serializado apunta a una entrada de aquí.

## Datos — `Producto`
`{ id, part_number, tipo, descripcion, fabricante, modelo, notas }`, `tipo ∈ "equipo" | "componente"`.

- Listado: `GET /api/productos` (todo) o `GET /api/productos?tipo=equipo|componente`.
- Crear: `POST /api/productos`, body `{ part_number, tipo, descripcion, fabricante?, modelo?, notas? }`.
- Editar: `PUT /api/productos/{id}` (mismo body que crear).
- Borrar: `DELETE /api/productos/{id}` (204). Puede devolver **409 "Producto en uso; no se puede borrar"** si hay equipos/componentes que lo referencian — captura ese error y muéstralo en un toast claro.

## UI
- Título "Catálogo" (Open Sans) + botón primario lila **"+ Nuevo producto"**.
- **Pestañas o filtro** Tipo: Todos / Equipos / Componentes (re-fetch con `?tipo=`). Un badge lila distingue "equipo" y un badge gris "componente" en la tabla.
- **Tabla:** Part number (Roboto, destacado), Tipo (badge), Descripción, Fabricante, Modelo. Acciones por fila: Editar, Borrar (con confirmación).
- Buscador local por part number/descripcion (filtra en cliente la lista cargada).
- **Crear/Editar en modal** con: part_number (obligatorio), tipo (select equipo/componente, obligatorio), descripcion (obligatorio), fabricante, modelo, notas.
  - Error **409 "part_number ya existe"** → muéstralo junto al campo part_number.
- Estado vacío con isotipo gris claro: "Catálogo vacío — crea el primer modelo".

## Detalle visual
Coherente con el resto: lila como acento, datos en Roboto, badges discretos. Confirmación de borrado en diálogo (no borrar sin preguntar).

Respeta nombres de campo exactos. No inventes endpoints.
