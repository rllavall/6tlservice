# Prompt Lovable 05 — Ubicaciones (fábricas / sedes)

> Requiere prompts 00–01. Identidad 6TL (lila `#9e007e`, Open Sans/Roboto). NO toques shell/cliente API/otras pantallas. Ruta `/ubicaciones`.

---

Implementa **Ubicaciones** en `/ubicaciones`. Son los sitios donde puede estar un equipo: fábricas de clientes por el mundo, sedes de 6TL, taller de reparación, tránsito.

## Datos — `Ubicacion`
`{ id, nombre, tipo, empresa_cliente, pais, ciudad, notas }`
`tipo ∈ "fabrica_cliente" | "sede_6tl" | "en_reparacion" | "en_transito"`.

- Listar: `GET /api/ubicaciones`.
- Crear: `POST /api/ubicaciones`, body `{ nombre, tipo, empresa_cliente?, pais?, ciudad?, notas? }`.
- Editar: `PUT /api/ubicaciones/{id}` (mismo body).
- Borrar: `DELETE /api/ubicaciones/{id}` (204). Puede devolver **409 "Ubicación en uso por movimientos; no se puede borrar"** — captúralo y muéstralo en toast.
- Equipos en una ubicación: `GET /api/ubicaciones/{id}/equipos` → `Equipo[]` cuya ubicación actual es esa (úsalo en el detalle, ver abajo).

## UI
- Título "Ubicaciones" (Open Sans) + botón primario lila **"+ Nueva ubicación"**.
- **Tabla / tarjetas:** Nombre (destacado), Tipo (badge con etiqueta legible: "Fábrica cliente", "Sede 6TL", "En reparación", "En tránsito"), Empresa cliente, Ciudad, País. Acciones: Editar, Borrar (confirmación).
- Filtro por tipo (chips lila).
- **Crear/Editar en modal:** nombre (obligatorio), tipo (select con las 4 opciones y etiquetas legibles), empresa_cliente, pais, ciudad, notas.
- **Detalle / expandible:** al pulsar una ubicación, muestra cuántos equipos hay ahí ahora (`GET /api/ubicaciones/{id}/equipos`) con enlace a cada ficha. Útil para "¿qué tengo desplegado en la fábrica X?".
- Estado vacío con isotipo gris claro: "Sin ubicaciones — crea la primera".

## Etiquetas legibles de `tipo`
Mapea valor → etiqueta UI: `fabrica_cliente → "Fábrica cliente"`, `sede_6tl → "Sede 6TL"`, `en_reparacion → "En reparación"`, `en_transito → "En tránsito"`. Guarda/envía siempre el valor sin acentos del enum; muestra la etiqueta bonita.

## Detalle visual
Lila como acento, datos en Roboto, badges discretos por tipo. Confirmación antes de borrar.

Respeta nombres de campo exactos. No inventes endpoints.
