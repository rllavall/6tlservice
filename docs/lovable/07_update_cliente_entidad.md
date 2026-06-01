# Prompt Lovable 07 — ACTUALIZACIÓN: Cliente como entidad (pegar sobre la app ya generada)

> Pega esto en tu app de Lovable existente. Aplica un cambio de modelo del backend: ahora **Cliente es una entidad propia**. Mantén la identidad corporativa 6TL (lila `#9e007e`, Open Sans/Roboto, isotipo) y NO rompas las pantallas que ya funcionan; solo aplica estos cambios.

---

El backend ha cambiado: **"Cliente" pasa a ser una entidad gestionable** (antes era texto suelto / un campo en la ubicación). Aplica estos cambios respetando los nombres de campo EXACTOS.

## 1. Nueva pantalla "Clientes" + navegación
Añade un item de navegación **"Clientes"** (`/clientes`, icono `building-2`) en la barra lateral, entre "Base instalada" y "Catálogo", con el mismo estilo (activo en lila).

Crea la pantalla `/clientes` para la entidad `Cliente` = `{ id, nombre, cif, persona_contacto, email_contacto, telefono_contacto, notas }`:
- Listar `GET /api/clientes`; crear `POST /api/clientes` (solo `nombre` obligatorio); editar `PUT /api/clientes/{id}`; borrar `DELETE /api/clientes/{id}` (puede dar **409 "Cliente en uso; no se puede borrar"** → toast).
- Tabla: Nombre, CIF, Persona de contacto, Email (`mailto:`), Teléfono. Acciones Editar/Borrar (con confirmación). Buscador local por nombre/CIF.
- Crear/Editar en modal con esos campos (valida email en cliente).
- Detalle del cliente: sus **ubicaciones** (`GET /api/ubicaciones` filtrado en cliente por `cliente_id`) y sus **equipos** (`GET /api/equipos` filtrado por `cliente_id`, enlace a cada ficha).

## 2. Ubicaciones — nuevos campos (dirección + cliente)
El modelo `Ubicacion` cambia a: `{ id, nombre, tipo, cliente_id, direccion, codigo_postal, ciudad, provincia, pais, notas }`.
- **ELIMINA** el antiguo campo `empresa_cliente` de la UI (ya no existe en el backend).
- En el formulario de ubicación añade: **cliente** (select desde `GET /api/clientes`, envía `cliente_id`) **visible solo cuando `tipo = "fabrica_cliente"`** (para los demás tipos, manda `cliente_id` null), **dirección**, **código postal**, **provincia** (ciudad y país ya estaban).
- En la tabla de ubicaciones, sustituye la columna antigua de empresa por **Cliente** (nombre resuelto desde `cliente_id` vía `GET /api/clientes`; "—" si null).
- Body de crear/editar: `{ nombre, tipo, cliente_id?, direccion?, codigo_postal?, ciudad?, provincia?, pais?, notas? }`.

## 3. Equipo — cliente pasa de texto a select (cliente_id)
El campo `cliente` (texto) del equipo se sustituye por `cliente_id` (FK).
- En **alta/edición de equipo**: cambia el input de texto "Cliente" por un **select** poblado con `GET /api/clientes` que envía `cliente_id`. Es opcional. Body alta: `{ numero_serie, producto_id, cliente_id?, ... }`; body edición (`PUT`): `{ cliente_id?, fecha_fabricacion?, fecha_entrega?, estado?, notas? }`.
- Si el id no existe el backend responde 404 "Cliente no encontrado".

## 4. Mostrar el cliente (resuelto) donde antes había texto
- **Base instalada (`/`):** la columna "Cliente" ahora resuelve `equipo.cliente_id` → `nombre` con `GET /api/clientes` ("—" si null). Añade (opcional) un filtro por cliente.
- **Ficha de equipo (`/equipos/:id`):** `GET /api/equipos/{id}` ahora incluye un objeto `cliente` en la respuesta (`{ id, nombre, cif, persona_contacto, email_contacto, telefono_contacto, notas }` o null). Muestra `cliente.nombre` en la cabecera (chip), enlazable a `/clientes`. El `equipo` ya NO trae `cliente` de texto; usa `equipo.cliente_id` / el objeto `cliente`.
- La `ubicacion_actual` de la ficha ahora trae los nuevos campos (`direccion, codigo_postal, provincia` además de ciudad/país); puedes mostrar la dirección completa en el tooltip/detalle de ubicación.

## Importante
- Nombres de campo EXACTOS: `cliente_id` (no `cliente`), `persona_contacto`, `email_contacto`, `telefono_contacto`, `codigo_postal`, `direccion`, `provincia`.
- No toques las pantallas de catálogo ni la lógica de componentes/montajes/movimientos: ese contrato no ha cambiado.
- Mantén la identidad corporativa 6TL en todo lo nuevo (lila, Open Sans/Roboto, isotipo, badges discretos).
