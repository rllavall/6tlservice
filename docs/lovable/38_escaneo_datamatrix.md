# Prompt 38 — Pantalla de escaneo DataMatrix para capturar nº de serie de componentes

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, helper `api<T>()` en
`@/lib/api` (inyecta Bearer), tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`).
**NO cambies nombres de campo del backend. No inventes endpoints ni campos fuera de los
listados.** Todo va protegido (el `api()` manda token).

Objetivo: al dar de alta un banco (p. ej. el iUTB), sus componentes nacen con nº de serie
placeholder `"S/N pendiente (1.1)"`. Esta pantalla permite, **escaneando con un lector
DataMatrix** (tipo teclado-wedge: teclea la cadena decodificada y un Enter), rellenar
automáticamente el nº de serie del componente correcto del banco, emparejando por PN de
fabricante.

## 1. Tipos en `src/lib/types.ts`
```ts
export type EstadoEscaneo =
  | "asignado" | "ambiguo" | "ocupado" | "sin_match" | "sin_sn" | "duplicado" | "equipo_no_existe";

export interface EscaneoCandidato {
  componente_id: number;
  posicion: string | null;
  part_number: string;
  pn_fabricante: string | null;
  numero_serie: string;
}

export interface EscaneoResultado {
  estado: EstadoEscaneo;
  formato: string | null;       // "regla" | "gs1" | "crudo" | null
  pn: string | null;
  sn: string | null;
  componente_id: number | null;
  posicion: string | null;
  part_number: string | null;
  candidatos: EscaneoCandidato[];
}
```

## 2. Endpoints (ya existen en backend)
- `GET /api/equipos` → lista de equipos (bancos). Campos usados: `id`, `numero_serie`,
  `producto` (descripción), `cliente`. Para elegir el banco.
- `GET /api/componentes?equipo_id={id}` → lista de componentes del banco. Campos usados:
  `id`, `numero_serie`, `posicion`, `part_number` (si no viene, usa lo que exponga `ComponenteOut`:
  `producto_id`; el `part_number` se puede tomar del propio resultado de escaneo). Resaltar los
  que empiezan por `"S/N pendiente"`.
- `POST /api/equipos/{equipo_id}/escaneo` body `{ "raw": string }` → `EscaneoResultado`.
  404 si el equipo no existe; 422 si `raw` vacío.
- `PATCH /api/componentes/{componente_id}` body `{ "numero_serie": string }` → componente
  actualizado. 409 si el nº de serie ya existe para ese producto. (Para la resolución manual.)

## 3. Ruta nueva `/escaneo` (`src/routes/escaneo.tsx`)
- **Selector de banco**: combo/lista con `GET /api/equipos`. Al elegir uno, cargar sus
  componentes con `GET /api/componentes?equipo_id={id}` y mostrarlos en una tabla:
  `posicion`, `part_number`, `numero_serie` (resaltar en lila los placeholders).
- **Cabecera de progreso**: "X de N con nº de serie real" (N = total componentes; X = los que
  NO empiezan por `"S/N pendiente"`). Barra o texto.
- **Input de escaneo (autofocus)**: un `<input>` siempre enfocado. En `onKeyDown` con `Enter`
  (o detectando el fin de cadena del lector), enviar `POST /api/equipos/{id}/escaneo` con
  `{ raw: valorDelInput }`, **vaciar el input y re-enfocarlo**. (El lector escribe la cadena y
  pulsa Enter solo.) Mostrar un hint: "Escanea el DataMatrix del componente…".

## 4. Manejo del resultado (`EscaneoResultado.estado`)
- **`asignado`** → `toast.success` ("Posición {posicion}: {sn}"), refrescar la lista de
  componentes (re-fetch), re-enfocar el input. La fila correspondiente deja de estar en
  placeholder.
- **`ambiguo` / `ocupado` / `sin_match` / `sin_sn`** → abrir un **panel/diálogo de resolución
  manual**: mostrar `pn` y `sn` parseados (si los hay) y la lista `candidatos`
  (`posicion`, `part_number`, `numero_serie`). El usuario elige un candidato y edita el SN
  (precargar con `sn` si existe) → `PATCH /api/componentes/{componente_id}` con
  `{ numero_serie }`. 409 → `toast.error` ("Ese nº de serie ya existe para el producto").
  Al éxito: `toast.success`, cerrar, refrescar, re-enfocar el input.
  - Texto de ayuda según estado: `ambiguo` = "varios componentes con ese PN, elige uno";
    `ocupado` = "ese componente ya tiene nº de serie, confírmalo si quieres reemplazarlo";
    `sin_match` = "no se reconoció el PN, asigna a mano"; `sin_sn` = "no se detectó nº de serie".
- **`duplicado`** → `toast.error` ("Ese nº de serie ya existe para este producto").
- **`equipo_no_existe`** no debería ocurrir (el banco se elige de la lista); si llega, `toast.error`.

## 5. (Opcional, no bloqueante) regla de fabricante
En el formulario de Fabricantes (si existe pantalla de edición), añadir un textarea
`regla_datamatrix` — regex con grupos nombrados `(?P<pn>...)` y `(?P<sn>...)` — enviado en
`POST/PUT /api/fabricantes` (el backend ya lo acepta y lo devuelve en `FabricanteOut`).
Ayuda: "Regla de parseo del DataMatrix de este fabricante (regex). Déjalo vacío para usar GS1."

## 6. Instrucciones Lovable
- Crear SOLO `src/routes/escaneo.tsx` (+ tipos en `src/lib/types.ts`). **No toques** otras rutas
  ni `ReportObsolescenciaDialog`.
- Añadir un enlace a `/escaneo` en la navegación principal (donde estén las demás rutas).
- Verificar contrato: nombres de campo EXACTOS de los tipos de arriba. Un "error CORS" suele ser
  un desajuste de nombre o un 500 silencioso.
- El input de escaneo debe recuperar el foco tras cada escaneo para encadenar lecturas sin ratón.
