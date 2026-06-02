# Prompt Lovable 05 — Ubicaciones (plantas / sedes) con dirección y cliente

> Requiere prompts 00–01 y 06 (Clientes). Identidad 6TL (lila `#9e007e`, Open Sans/Roboto). NO toques shell/cliente API/otras pantallas. Ruta `/ubicaciones`.

---

Implementa **Ubicaciones** en `/ubicaciones`. Una ubicación es un **sitio físico** donde puede estar un equipo: una planta de un cliente (con su dirección completa), una sede de 6TL, el taller de reparación o tránsito. Las ubicaciones de tipo `fabrica_cliente` **pertenecen a un Cliente** (entidad gestionada en el prompt 06).

## Datos — `Ubicacion`
`{ id, nombre, tipo, cliente_id, direccion, codigo_postal, ciudad, provincia, pais, notas }`
- `tipo ∈ "fabrica_cliente" | "sede_6tl" | "en_reparacion" | "en_transito"`.
- `cliente_id` → FK a Cliente, **opcional/null**. Solo tiene sentido para `tipo=fabrica_cliente`. Para sede_6tl/en_reparacion/en_transito va vacío.

Endpoints:
- Listar: `GET /api/ubicaciones`.
- Crear: `POST /api/ubicaciones`, body `{ nombre, tipo, cliente_id?, direccion?, codigo_postal?, ciudad?, provincia?, pais?, notas? }`.
- Editar: `PUT /api/ubicaciones/{id}` (mismo body).
- Borrar: `DELETE /api/ubicaciones/{id}` (204). Puede dar **409 "Ubicación en uso por movimientos; no se puede borrar"** — captúralo en toast.
- Equipos en una ubicación: `GET /api/ubicaciones/{id}/equipos` → `Equipo[]` cuya ubicación actual es esa.
- Para resolver `cliente_id` → nombre y poblar el selector de cliente: `GET /api/clientes`.

## UI
- Título "Ubicaciones" (Open Sans) + botón primario lila **"+ Nueva ubicación"**.
- **Tabla:** Nombre (destacado), Tipo (badge legible), **Cliente** (nombre resuelto desde `cliente_id`, "—" si null), Ciudad, País. Acciones: Editar, Borrar (confirmación).
- Filtro por tipo (chips lila) y, opcionalmente, por cliente.
- **Crear/Editar en modal:**
  - **nombre** (obligatorio) — p.ej. "Indra – Planta Aranjuez".
  - **tipo** (select con las 4 opciones, etiquetas legibles, obligatorio).
  - **cliente** (select desde `GET /api/clientes`, envías `cliente_id`) — **visible/activo solo cuando tipo = "fabrica_cliente"**; ocúltalo o deshabilítalo para los otros tipos (y manda `cliente_id` null). Error 404 "Cliente no encontrado" si el id no existe.
  - **dirección** (texto), **código postal**, **ciudad**, **provincia**, **país**, **notas**.
- **Detalle / expandible:** al pulsar una ubicación, muestra su dirección completa, el cliente (si lo tiene, enlazable a `/clientes`) y cuántos equipos hay ahí ahora (`GET /api/ubicaciones/{id}/equipos`) con enlace a cada ficha. Útil para "¿qué tengo desplegado en la planta X del cliente Y?".
- Estado vacío con isotipo gris claro: "Sin ubicaciones — crea la primera".

## Etiquetas legibles de `tipo`
`fabrica_cliente → "Fábrica cliente"`, `sede_6tl → "Sede 6TL"`, `en_reparacion → "En reparación"`, `en_transito → "En tránsito"`. Guarda/envía siempre el valor sin acentos del enum; muestra la etiqueta bonita.

## Detalle visual
Lila como acento, datos en Roboto, badges discretos por tipo. Confirmación antes de borrar.

Respeta nombres de campo exactos. No inventes endpoints.
