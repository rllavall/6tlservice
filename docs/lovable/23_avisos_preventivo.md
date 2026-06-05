# Prompt 23 — Panel de avisos (preventivo + contratos por caducar)

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()` que ya inyecta el Bearer token, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`).
NO cambies nombres de campo. No inventes endpoints ni campos fuera de los listados aquí.

El equipo interno necesita ver de un vistazo **qué necesita atención**: preventivos vencidos o que tocan
pronto, y contratos que están a punto de caducar. Todo viene calculado del backend en un solo endpoint.

## 1. Tipos en `src/lib/types.ts`
```ts
interface AvisoPreventivo {
  equipo: Equipo;            // EquipoOut completo (incl. bajo_contrato/contrato)
  contrato: ContratoResumen; // id, codigo, nivel, estado, vigente
  proxima_fecha: string;     // ISO date
  dias_restantes: number;    // negativo si vencido
  bucket: "vencido" | "proximo";
  ultima_fecha: string | null;
}
interface AvisoContrato {
  contrato: ContratoResumen;
  cliente: Cliente | null;
  fecha_fin: string;
  dias_restantes: number;
}
interface ResumenAvisos {
  preventivos_vencidos: number;
  preventivos_proximos: number;
  contratos_por_caducar: number;
}
interface AvisosOut {
  preventivos: AvisoPreventivo[];
  contratos_por_caducar: AvisoContrato[];
  resumen: ResumenAvisos;
}
```

## 2. Pantalla `/avisos` (nueva, en el menú)
- Carga `GET /api/avisos` → `AvisosOut`.
- **Sección "Preventivos"**: tabla con columnas — equipo (nº de serie + producto, enlace a su ficha),
  contrato (`codigo` + `nivel` badge), `proxima_fecha`, `dias_restantes`, y un badge de `bucket`
  (vencido=rojo, proximo=ámbar). Acciones por fila: enlace a la ficha del equipo y botón
  **"Registrar preventivo"** que reutiliza el formulario del prompt 22 (`POST /api/equipos/{id}/preventivos`).
  Filtro por bucket: **Vencidos / Próximos / Todos**. Orden: ya viene del backend (más vencido primero).
- **Sección "Contratos por caducar"**: tabla con contrato (`codigo` + `nivel`), cliente (si lo hay),
  `fecha_fin`, `dias_restantes`. Enlace a la ficha del contrato (`/contratos`).
- Si ambas listas están vacías, muestra un estado "Sin avisos pendientes" en verde.

## 3. Badge en el menú
- Junto a "Avisos" en la navegación, muestra un contador =
  `resumen.preventivos_vencidos + resumen.contratos_por_caducar` (los que requieren acción ya). Si es 0,
  no pintes badge. Refresca al entrar en la app y al volver a `/avisos`.

## 4. (Opcional) cabecera de "Resumen de servicio"
- Si existe la cabecera de KPIs del resumen de servicio, puedes añadir un contador "Preventivos vencidos"
  (= `resumen.preventivos_vencidos`) leyendo el mismo `GET /api/avisos`. No es obligatorio.

No cambies la lógica existente de equipos, contratos ni preventivo; solo consume `GET /api/avisos` y
reutiliza los componentes ya creados (selector/ficha de equipo, formulario de preventivo).
