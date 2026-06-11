# Prompt 28 — Motor de fabricantes + activación de garantía + derivaciones (RMA / interno)

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()` que ya inyecta el Bearer token, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`,
componente `<HelpTip clave=...>` del prompt 20). **NO cambies nombres de campo. No inventes endpoints ni
campos fuera de los listados aquí.** Todas estas rutas van protegidas (el `api()` ya manda el token).

Tres piezas que se apoyan en un nuevo **maestro de fabricantes**:
1. **Fabricantes**: ficha por marca (National Instruments, Keysight…) con sus emails y política de RMA.
2. **Garantía del fabricante a nivel COMPONENTE** (el instrumento individual): se solicita su activación,
   queda *"pendiente de activación"*, y al registrar el feedback del fabricante arranca el conteo.
3. **Derivaciones** desde una incidencia: **externa** hacia un fabricante (RMA, con tu referencia y la suya)
   o **interna** hacia un departamento. Misma mecánica; al cerrarse, resuelve la incidencia.

## 1. Tipos en `src/lib/types.ts`
```ts
type EstadoGarantiaFab = "no_aplica" | "pendiente_activacion" | "activada" | "rechazada";
type CoberturaGarantiaFab = "sin_activar" | "vigente" | "por_vencer" | "vencida";
type TipoDerivacion = "externa_fabricante" | "interna_departamento";
type EstadoDerivacion = "pendiente" | "enviada" | "en_proveedor" | "recibida" | "cerrada";

interface Fabricante {
  id: number; nombre: string;
  email_service: string | null; email_rma: string | null;
  url_activacion_garantia: string | null; requiere_activacion_web: boolean;
  politica_rma: string | null; notas: string | null;
}

interface GarantiaFabricante {
  id: number; componente_id: number; fabricante_id: number | null;
  estado: EstadoGarantiaFab;
  fecha_solicitud: string | null; fecha_activacion: string | null;
  meses_garantia: number | null; referencia_fabricante: string | null;
  responsable: string | null;
  fecha_fin: string | null; estado_cobertura: CoberturaGarantiaFab;
}

interface Derivacion {
  id: number; incidencia_id: number; tipo: TipoDerivacion;
  fabricante_id: number | null; departamento: string | null;
  tu_referencia: string;            // "RMA-NNNN" (la nuestra)
  referencia_externa: string | null; // la del fabricante
  estado: EstadoDerivacion;
  fecha_creacion: string; fecha_envio: string | null; fecha_cierre: string | null;
  notas: string | null;
}
```
Añade `fabricante_id: number | null` a `Producto` (ya lo expone el backend en `ProductoOut`).

## 2. Pantalla **Fabricantes** `/fabricantes` (nueva, en el menú)
- Lista vía `GET /api/fabricantes` (ordenada por nombre). Tabla: `nombre`, `email_service`, `email_rma`,
  badge "Activación web" si `requiere_activacion_web`, y un recorte de `politica_rma`.
- Alta/edición (modal o página):
  - Crear: `POST /api/fabricantes` body `{nombre, email_service?, email_rma?, url_activacion_garantia?,
    requiere_activacion_web?, politica_rma?, notas?}`. Solo `nombre` es obligatorio. **409** = nombre duplicado.
  - Editar: `PUT /api/fabricantes/{id}` (parcial, mismos campos opcionales). **409** = nombre duplicado.
  - Detalle: `GET /api/fabricantes/{id}`.
  - Borrar: `DELETE /api/fabricantes/{id}` (204).
- `email_rma` es opcional: indica en el formulario que, si se deja vacío, para RMA se usará `email_service`.
- Pon un `<HelpTip clave="fabricantes.maestro">` junto al título de la pantalla.

## 3. Producto del catálogo enlazado al fabricante
- En el alta/edición de **producto** (catálogo), añade un selector **"Fabricante"** que carga `GET /api/fabricantes`
  y envía `fabricante_id` (number | null) en `POST/PUT /api/productos`. Conserva el campo de texto libre
  `fabricante` existente (es el legado); el selector `fabricante_id` es el enlace al maestro.

## 4. Garantía del fabricante en la ficha de equipo (a nivel componente)
La garantía del fabricante es **por componente** (el instrumento). En la ficha de equipo
(`equipos.$id.tsx`), dentro de la sección **"Configuración actual"**, en cada componente montado:
- Carga su garantía con `GET /api/componentes/{componente_id}/garantia`.
  - **404** = el componente aún no tiene garantía de fabricante iniciada → muestra botón **"Activar garantía"**.
  - **200** = muestra un badge de `estado` (pendiente_activacion=ámbar "Pendiente de activación",
    activada=verde, rechazada=gris, no_aplica=neutro) y, si `estado === "activada"`, el `estado_cobertura`
    (vigente=verde, por_vencer=ámbar, vencida=rojo) + `fecha_fin`.
- **Activar** (botón "Activar garantía"): `POST /api/componentes/{componente_id}/garantia/activar` body
  `{meses_garantia?, responsable?}` (si dejas `meses_garantia` vacío, el backend usa el del producto). Respuesta
  201 = garantía en `pendiente_activacion`. Junto al botón, `<HelpTip clave="garantia.activar">`.
- **Confirmar** (visible solo cuando `estado === "pendiente_activacion"`): formulario
  `POST /api/componentes/{componente_id}/garantia/confirmar` body `{fecha_activacion, referencia?}`
  (`fecha_activacion` ISO obligatoria = inicio real de la garantía; `referencia` = id que devuelve el fabricante).
  Respuesta 200 → la garantía pasa a `activada` y `fecha_fin`/`estado_cobertura` quedan calculados.
  **404** si la garantía no estaba iniciada, **409** si no estaba pendiente. `<HelpTip clave="garantia.confirmar">`.

## 5. Pantalla **Garantías pendientes** `/garantias-pendientes` (nueva, en el menú) — la cola "pendiente del Galarzo"
- Lista vía `GET /api/garantias/pendientes` → `GarantiaFabricante[]` (solo `estado === "pendiente_activacion"`,
  ordenadas por `fecha_solicitud`). Para cada fila muestra: `componente_id`, el fabricante (resuelve el nombre
  cruzando `fabricante_id` con la lista de `GET /api/fabricantes`), `fecha_solicitud`, `responsable`,
  `meses_garantia`.
- Acción por fila **"Confirmar activación"** → mismo formulario del punto 4 contra
  `POST /api/componentes/{componente_id}/garantia/confirmar`. Al confirmar, la fila desaparece de la cola
  (refresca la lista). Badge de recuento de pendientes en el menú.

## 6. Derivaciones (RMA / interno) en el expediente de incidencia
En la ficha de incidencia (`incidencias.$id.tsx`), añade una sección **"Derivaciones · RMA / Interno"**:
- Lista vía `GET /api/incidencias/{incidencia_id}/derivaciones` → `Derivacion[]` (orden desc por id). Columnas:
  `tu_referencia`, tipo (badge: externa_fabricante="Fabricante", interna_departamento="Interno"), destino
  (nombre del fabricante vía `fabricante_id`, o `departamento`), `referencia_externa`, badge de `estado`,
  fechas (`fecha_creacion`/`fecha_envio`/`fecha_cierre`).
- **Crear** (botón "Derivar"): `POST /api/incidencias/{incidencia_id}/derivaciones` body
  `{tipo, fabricante_id?, departamento?, notas?}`.
  - Si `tipo === "externa_fabricante"`: selector de fabricante (`GET /api/fabricantes`) → envía `fabricante_id`.
  - Si `tipo === "interna_departamento"`: campo de texto `departamento` (obligatorio para este tipo).
  - **409** = error de negocio (externa sin fabricante, interna sin departamento) → muestra el mensaje del backend.
  - Respuesta 201 = la derivación creada (estado `pendiente`). Junto al botón, `<HelpTip clave="derivaciones.crear">`.
- **Avanzar estado** (máquina de estados, solo avanza un paso o se mantiene; el orden es
  `pendiente → enviada → en_proveedor → recibida → cerrada`): `PATCH /api/derivaciones/{id}` body
  `{estado?, referencia_externa?, notas?}`.
  - Ofrece un botón "Avanzar a «siguiente estado»" según el estado actual, y un campo para registrar
    `referencia_externa` (el nº de RMA que da el fabricante).
  - **409** = transición inválida (salto/retroceso) → muestra el aviso.
  - Al pasar a `cerrada`, el backend **resuelve la incidencia padre** (estado `resuelta`) → tras la respuesta,
    **refresca el expediente** para que se vea el nuevo estado de la incidencia.

## 7. Notas
- No cambies la lógica existente de incidencias, garantía (comercial a nivel equipo), montaje de componentes
  ni el selector de equipos; solo añade lo de arriba consumiendo estos endpoints.
- La garantía del **fabricante** (componente, esta entrega) es independiente de la garantía **comercial** del
  equipo que ya existe en la ficha (prompt 13). Son dos indicadores distintos: no los mezcles.
- Emails: el backend manda los avisos de activación y de RMA en *best-effort*; el frontend no gestiona correo,
  solo dispara las acciones y registra el feedback manualmente.
