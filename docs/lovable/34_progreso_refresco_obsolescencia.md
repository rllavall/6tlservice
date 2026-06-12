# Prompt 34 — Popup de progreso del refresco de obsolescencia por banco

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, helper `api<T>()` en `@/lib/api`
(inyecta Bearer), tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`, componentes `<EstadoCicloBadge
estado url />` (prompt 32) y `ReportObsolescenciaDialog` (prompt 33)). **NO cambies nombres de campo del
backend. No inventes endpoints ni campos fuera de los listados.** Todo va protegido (el `api()` manda token).

Hoy el botón **"Refrescar estado"** del `ReportObsolescenciaDialog` llama a un refresco síncrono y muestra
un spinner ciego. Este prompt lo cambia: el refresco corre en segundo plano en el backend y un **popup
muestra el avance en vivo** (barra X/N + componente actual + log de resultados), sondeando cada 1 s.

## 1. Tipos en `src/lib/types.ts`
```ts
export interface RefrescoIniciado {
  job_id: string;
  total: number;
}

export interface RefrescoActual {
  part_number: string;
  fabricante: string | null;
  descripcion: string;
}

export interface RefrescoResultadoItem {
  part_number: string;
  descripcion: string;
  estado_anterior: EstadoCicloVida | null;
  estado_nuevo: EstadoCicloVida | null;
  cambio: boolean;
}

export interface RefrescoProgreso {
  job_id: string;
  equipo_id: number;
  total: number;
  indice: number;
  estado: "en_curso" | "terminado" | "error";
  actual: RefrescoActual | null;
  resultados: RefrescoResultadoItem[];
  report: ObsolescenciaBancoReport | null;  // presente cuando estado==="terminado"
  error: string | null;
}
```

## 2. Componente `RefrescoObsolescenciaProgresoDialog`
Props: `{ equipoId: number; open: boolean; onOpenChange: (v:boolean)=>void; onTerminado: (report: ObsolescenciaBancoReport)=>void }`.

Comportamiento:
- Al abrir (`open` pasa a true): `POST /api/equipos/{equipoId}/obsolescencia/refrescar/iniciar?limite=10`
  con `api<RefrescoIniciado>(..., { method: "POST" })` → guarda `{ job_id, total }`.
- **Sondeo**: cada **1000 ms** (`setInterval`) `api<RefrescoProgreso>('/api/equipos/{equipoId}/obsolescencia/refrescar/{job_id}')`.
  Guarda la respuesta en estado. **Limpia el interval** al desmontar, al cerrar, y cuando `estado` deja de ser `"en_curso"`.
- Render mientras `en_curso`:
  - **Barra de progreso** con `indice / total` (shadcn `Progress`, value = `total ? indice/total*100 : 0`) + texto `Chequeando {indice}/{total}`.
  - **Tarjeta "actual"** (si `actual`): `actual.part_number` + `actual.fabricante ?? "—"` + `actual.descripcion`, con un spinner pequeño.
  - **Log en vivo**: lista (orden de llegada) de `resultados[]`: `part_number` + `descripcion` + `<EstadoCicloBadge estado={r.estado_nuevo} />`; si `r.cambio`, marca la fila (icono/realce, p.ej. punto lila) indicando que cambió.
- `estado === "terminado"`: para el sondeo; muestra "Completado · {nº de resultados con cambio} cambios"; botón **Cerrar** que llama `onTerminado(prog.report)` (si `report`) y `onOpenChange(false)`.
- `estado === "error"`: muestra `error` + botón Cerrar. No rompe el dialog padre.
- Errores de red en el sondeo (p.ej. 404 del job): corta el interval y muestra un aviso + Cerrar.

## 3. Wiring en `ReportObsolescenciaDialog` (prompt 33)
- El botón **"Refrescar estado"** ya NO llama al refresco síncrono: ahora abre `RefrescoObsolescenciaProgresoDialog`
  (estado local `openRefresco`).
- `onTerminado={(report) => { /* refresca la tabla del report con el report recibido, o vuelve a hacer
  GET /api/equipos/{id}/obsolescencia */ }}`.
- El resto del `ReportObsolescenciaDialog` no se toca.

## 4. Notas
- Endpoints (solo estos): `POST /api/equipos/{id}/obsolescencia/refrescar/iniciar?limite=10` → `RefrescoIniciado`;
  `GET /api/equipos/{id}/obsolescencia/refrescar/{job_id}` → `RefrescoProgreso`.
- El refresco es lento (consulta a fabricantes con un agente): es normal que pasen segundos entre resultados.
- Si el usuario cierra el popup a mitad, el backend sigue hasta terminar; no hay cancelación.
- Reutiliza `EstadoCicloVida`/`EstadoCicloBadge` del prompt 32 y `ObsolescenciaBancoReport` del prompt 33.
