# Prompt 16 — Cabecera "Resumen de servicio · EN VIVO" (KPIs)

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()`, tipos en `@/lib/types`, paleta lila `#9e007e`, shadcn). NO cambies nombres de campo.

## 1. Tipo en `src/lib/types.ts`
```ts
export interface ResumenServicio {
  incidencias_abiertas: number;
  incidencias_abiertas_alta: number;
  rma_abierto: number;
  en_reparacion: number;
  cerradas_30d: number;
  tiempo_medio_cierre_dias: number | null;
}
```

## 2. Cabecera "Resumen de servicio · EN VIVO / Operaciones de postventa"
Llama `GET /api/analitica/resumen` (`useQuery`) y pinta **4 tarjetas** (sustituyendo las actuales,
y ELIMINANDO la tarjeta "SLA en riesgo"):

1. **Incidencias abiertas** = `incidencias_abiertas`; subtítulo "{incidencias_abiertas_alta} de alta prioridad".
   (Cuenta TODAS las asistencias abiertas: RMA, soporte venta, soporte técnico, calibración — todas las familias.)
2. **RMA abierto** = `rma_abierto`; subtítulo "sin cerrar".
3. **En reparación** = `en_reparacion`; subtítulo "trabajos en curso".
4. **Tiempo medio de cierre** = `tiempo_medio_cierre_dias` (formatea como "{n} d", o "—" si es `null`);
   subtítulo "{cerradas_30d} cerradas · 30d".

Mantén el enlace "Ver analítica completa →" hacia `/analitica`. Conserva el estilo y layout actuales
(mismas tarjetas con su icono; solo cambian etiquetas, valores y la fuente de datos).
