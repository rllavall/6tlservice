# Prompt 22 — Contratos de mantenimiento + preventivo + P/N de fabricante

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()` que ya inyecta el Bearer token, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`).
NO cambies nombres de campo. No inventes endpoints ni campos fuera de los listados aquí.

Un equipo puede estar bajo un **contrato de mantenimiento** (niveles Bronze/Silver/Gold). El equipo interno
gestiona los contratos, asigna equipos cubiertos y registra **acciones de preventivo** (que pueden generar
una incidencia correctiva). Además, el maestro de productos gana un **P/N de fabricante**.

## 1. Tipos en `src/lib/types.ts`
```ts
type NivelContrato = "bronze" | "silver" | "gold";
type EstadoContrato = "pendiente" | "vigente" | "vencido" | "cancelado";
type TipoPreventivo = "on_site" | "remoto";
type VeredictoPreventivo = "ok" | "con_observaciones" | "requiere_accion";

interface NivelDetalle { preventivo: string; soporte: string; respuesta: string; preventivo_meses: number }

interface ContratoResumen { id:number; codigo:string; nivel:NivelContrato; estado:EstadoContrato; vigente:boolean }

interface Contrato {
  id:number; codigo:string; cliente_id:number|null; nivel:NivelContrato;
  fecha_inicio:string; fecha_fin:string; cancelado:boolean; notas:string|null;
  estado:EstadoContrato; vigente:boolean; nivel_detalle:NivelDetalle|null;
}
interface ContratoDetalle { contrato:Contrato; cliente:Cliente|null; equipos:Equipo[] }

interface AccionPreventiva {
  id:number; equipo_id:number; contrato_id:number|null; fecha:string;
  tecnico:string|null; tipo:TipoPreventivo; veredicto:VeredictoPreventivo;
  informe:string|null; proxima_fecha:string|null; incidencia_id:number|null;
}
```
Añade `pn_fabricante:string|null` a `Producto`, y `bajo_contrato:boolean` + `contrato:ContratoResumen|null` a `Equipo`.

## 2. P/N de fabricante (catálogo + configuración)
- En el alta/edición de **producto** (catálogo) añade el campo `pn_fabricante` (texto, opcional).
- En la **"Configuración actual"** de la ficha de equipo, muestra el `pn_fabricante` del producto de cada
  componente junto al `part_number` interno 6TL (p.ej. "PN 6TL: X · P/N fab.: Y"). No cambies la lógica de montaje.

## 3. Pantalla **Contratos** `/contratos` (nueva, en el menú)
- Lista vía `GET /api/contratos?estado=&cliente_id=`. Filtro por estado (Vigentes/Pendientes/Vencidos/
  Cancelados/Todas). Tabla: `codigo`, cliente, `nivel` (badge: bronze=marrón, silver=gris, gold=dorado),
  vigencia (`fecha_inicio`→`fecha_fin`), badge de `estado` (vigente=verde, pendiente=ámbar, vencido=rojo,
  cancelado=gris).
- Alta/edición: `POST /api/contratos` (body `{cliente_id?, nivel, fecha_inicio, fecha_fin, notas?}`),
  `PUT /api/contratos/{id}` (parcial; **cancelar** = `PUT` con `{cancelado:true}`).
- Ficha `GET /api/contratos/{id}` → `ContratoDetalle`: muestra datos + **`nivel_detalle`** (preventivo /
  soporte / respuesta) como info del nivel + tabla de **equipos cubiertos**.
  - Asignar equipo: `POST /api/contratos/{id}/equipos` body `{equipo_id}` (reutiliza el selector de equipos
    existente). Si responde **409**, muestra el mensaje (el equipo es de otro cliente).
  - Desasignar: `DELETE /api/contratos/{id}/equipos/{equipo_id}`.
- Borrar contrato: `DELETE /api/contratos/{id}`. Si responde **409** (tiene equipos/acciones), muestra aviso
  de "cancélalo en su lugar" y ofrece el botón de cancelar.

## 4. Base instalada / ficha de equipo
- Badge **"Bajo contrato"** (verde) cuando `equipo.bajo_contrato`; si hay `equipo.contrato`, muestra su
  `codigo` + `nivel`. Filtro nuevo en base instalada: `GET /api/equipos?bajo_contrato=true|false`.
- Sección **Preventivo** en la ficha de equipo:
  - Historial: `GET /api/equipos/{id}/preventivos` (lista de `AccionPreventiva`, ya ordenada por fecha desc).
    Columnas: fecha, tipo, técnico, `veredicto` (badge: ok=verde, con_observaciones=ámbar, requiere_accion=rojo),
    próxima fecha, y enlace a la incidencia si `incidencia_id`.
  - Botón **"Registrar preventivo"** → formulario `POST /api/equipos/{id}/preventivos` body
    `{fecha, tipo, veredicto, tecnico?, informe?, proxima_fecha?}`. Si dejas `proxima_fecha` vacía, el backend
    la autocompleta según el nivel del contrato vigente (anual/semestral) — indícalo como placeholder.
  - En una acción con `veredicto !== "ok"`, botón **"Generar incidencia"** →
    `POST /api/preventivos/{accion_id}/generar-incidencia` body `{tipo, prioridad, asignado_a?}` (tipo por
    defecto `soporte_tecnico`, prioridad `media`). Respuesta 201 = la incidencia creada → navega a su ficha.
    409 = ya tiene incidencia (refresca).

## 5. Incidencias — cobertura informativa
- En el expediente de incidencia, junto al indicador de garantía, muestra la cobertura de contrato leyendo
  `expediente.equipo.bajo_contrato` y `expediente.equipo.contrato` (ya viene en la respuesta de
  `GET /api/incidencias/{id}` — NO hay endpoint nuevo). Solo informativo, no factura.

No cambies la lógica existente de incidencias, garantía ni el selector de equipos; solo consúmelos.
