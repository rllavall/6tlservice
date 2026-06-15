# Prompt Lovable 39 — Criticidad y trazabilidad de componentes (apartado componentes)

Contexto: el backend ya expone criticidad y nivel de trazabilidad derivados, la
plantilla de configuración esperada por producto-equipo, el alta desde plantilla y
la comparación config real vs esperada. NO toques otras pantallas.

## 1. Catálogo de productos (`/catalogo`) — clasificación de trazabilidad
En el formulario de producto de tipo **componente**, añade:
- Toggle `afecta_a_medida` ("Afecta al resultado de medida").
- Toggle `bajo_coste` ("Bajo coste / estándar").
- Categoría de componente: añade las opciones `software` ("Software") y
  `fixture_adaptador` ("Fixture / Adaptador") a las existentes.
- Select opcional `nivel_trazabilidad_override` (valores: `serie`, `version`,
  `no_trazado`, o vacío="automático").
En la tabla/ficha del producto, muestra dos badges de solo lectura que vienen del
backend: `criticidad` (alta=rojo, media=ámbar, baja=verde) y `nivel_trazabilidad`
(serie / versión / no trazado). Estos NO se editan; se derivan.
Campos en `ProductoOut`/`ProductoCreate`: `afecta_a_medida` (bool), `bajo_coste`
(bool), `nivel_trazabilidad_override` (string|null), `criticidad` (string, ro),
`nivel_trazabilidad` (string, ro).

## 2. Editor de plantilla (configuración esperada) por producto-equipo
En la ficha de un producto de tipo **equipo**, sección "Configuración esperada":
- `GET /api/productos/{id}/plantilla` → lista de líneas
  `{id, producto_componente_id, posicion, cantidad, part_number, descripcion,
   categoria_componente, criticidad, nivel_trazabilidad}`.
- Añadir línea: `POST /api/productos/{id}/plantilla` body
  `{producto_componente_id, posicion?, cantidad?=1}` (selector de producto
  componente). 409 si la línea (producto+posición) ya existe.
- Editar: `PATCH /api/plantilla/{linea_id}` body `{posicion?, cantidad?}`.
- Borrar: `DELETE /api/plantilla/{linea_id}` (204).
Muestra por línea el badge de nivel de trazabilidad.

## 3. Alta de equipo desde plantilla
En el wizard de alta (`/equipos/nuevo`), si el producto-equipo tiene plantilla,
ofrece un toggle "Pre-rellenar desde plantilla". Si se activa, manda
`POST /api/equipos/alta` con `desde_plantilla: true` (y NO mandes `componentes`).
El backend crea las líneas: nivel serie → placeholder de serie (a escanear),
version/no_trazado → sin serie. Tras el alta, lleva a la pantalla de configuración
del equipo (punto 4) para capturar series/revisiones.

## 4. Configuración del equipo: real vs esperada (en ficha de equipo)
`GET /api/equipos/{id}/configuracion` →
```
{ equipo_id, producto_equipo_id,
  lineas: [{producto_componente_id, part_number, descripcion, nivel_trazabilidad,
            cantidad_esperada, cantidad_presente, faltan}],
  sobrantes: [{componente_id, producto_id, part_number, numero_serie, posicion}],
  series_pendientes: [{componente_id, producto_id, part_number, posicion}],
  versiones_pendientes: [{componente_id, producto_id, part_number, posicion}],
  resumen: {esperados, presentes, faltantes, sobrantes, series_pendientes,
            versiones_pendientes, completo} }
```
Panel con:
- Barra/resumen "Configuración completa" cuando `resumen.completo` es true; si no,
  contadores de faltantes / sobrantes / series pendientes / versiones pendientes.
- Tabla de `lineas` (esperado vs presente, resaltando faltan>0).
- Lista de `series_pendientes` con botón que abre el escaneo DataMatrix existente
  (`/escaneo` o el modal de escaneo del equipo) para esa serie.
- Lista de `versiones_pendientes` con input de revisión que hace
  `PATCH /api/componentes/{id}` body `{revision: "..."}`.
- `sobrantes` como aviso (componentes montados no previstos en la plantilla).

## Notas
- `numero_serie` de componente ahora puede ser null (no_trazado / versión).
- `ComponenteOut` trae `revision` (string|null) y `nivel_trazabilidad` (string).
- No cambies el flujo de escaneo de fondo; solo enlázalo desde series_pendientes.
