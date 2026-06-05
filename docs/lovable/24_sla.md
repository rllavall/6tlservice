# Prompt 24 — Cumplimiento de SLA por nivel

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()` que ya inyecta el Bearer token, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`).
NO cambies nombres de campo. No inventes endpoints ni campos fuera de los listados aquí.

Cada incidencia de un equipo bajo **contrato vigente** tiene un SLA según el nivel (Bronze/Silver/Gold): un
objetivo de **respuesta** y de **resolución** en días. El backend lo calcula; aquí solo se muestra.

## 1. Tipos en `src/lib/types.ts`
```ts
type EstadoSla = "en_plazo" | "en_riesgo" | "incumplido" | "sin_sla";

interface SlaMetrica {
  objetivo_fecha: string;       // ISO date
  fecha_real: string | null;
  dias_restantes: number;       // negativo si pasado el objetivo
  estado: EstadoSla;
}
interface SlaIncidencia {
  nivel: string;                // bronze|silver|gold
  respuesta: SlaMetrica;
  resolucion: SlaMetrica;
  estado_global: EstadoSla;
}
interface SlaIncidenciaItem { incidencia: Incidencia; sla: SlaIncidencia }
interface CumplimientoSla { total: number; respuesta_pct: number | null; resolucion_pct: number | null }
interface ResumenSla { en_riesgo: number; incumplidas: number }
interface SlaOut {
  cumplimiento: CumplimientoSla;
  en_riesgo: SlaIncidenciaItem[];
  incumplidas: SlaIncidenciaItem[];
  resumen: ResumenSla;
}
```
Añade `sla: SlaIncidencia | null` a la ficha/expediente de incidencia (`IncidenciaFicha`).

Badge de estado (reutilizable): en_plazo=verde, en_riesgo=ámbar, incumplido=rojo, sin_sla=gris.

## 2. Expediente de incidencia — panel "SLA"
- Lee `ficha.sla` (`GET /api/incidencias/{id}`). Si es `null`, muestra "Sin SLA (equipo sin contrato vigente)".
- Si existe: encabezado con `nivel` (badge), y dos filas:
  - **Respuesta**: `objetivo_fecha`, `dias_restantes`, badge `respuesta.estado`.
  - **Resolución**: `objetivo_fecha`, `dias_restantes`, badge `resolucion.estado`.
  - Si hay `fecha_real`, muéstrala ("cumplido el …"); si no, "pendiente".

## 3. Pantalla SLA (`/sla`, en el menú; o sección en analítica)
- Carga `GET /api/sla`.
- **Tarjetas de cumplimiento**: `cumplimiento.respuesta_pct` %, `cumplimiento.resolucion_pct` %, `total`
  incidencias evaluadas (con SLA). Si `pct` es `null`, muestra "—".
- **Tabla "Incumplidas"** (`incumplidas[]`): por fila, incidencia (código + título, enlace a su ficha), badge
  `sla.estado_global`, nivel, días restantes de resolución (`sla.resolucion.dias_restantes`).
- **Tabla "En riesgo"** (`en_riesgo[]`): igual estructura.
- Badge en el menú junto a "SLA" = `resumen.en_riesgo + resumen.incumplidas` (0 → sin badge).

## 4. (Opcional) en la lista de incidencias
- Si resulta cómodo, una columna/badge de SLA por incidencia. No es obligatorio (la fuente es el expediente).

Consume `GET /api/sla` y `ficha.sla`. No cambies la lógica existente de incidencias; solo añade los paneles.
