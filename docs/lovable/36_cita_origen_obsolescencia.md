# Prompt 36 — Prueba de origen (cita textual) + "No encontrado" en obsolescencia

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, helper `api<T>()` en
`@/lib/api` (inyecta Bearer), tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`,
componentes `<EstadoCicloBadge estado url />` (prompt 32) y
`RefrescoObsolescenciaProgresoDialog` (prompts 34/35)). **NO cambies nombres de campo del
backend. No inventes endpoints ni campos fuera de los listados.** Todo va protegido.

El backend ahora aporta una **prueba de origen** por componente: una **cita textual**
copiada de la página del fabricante (`cita`) junto a la `url_fuente`. Un hallazgo solo se
registra si trae cita + URL verificada; si no, marca el componente como **no encontrado**.

## 1. Tipos en `src/lib/types.ts`
- `RefrescoResultadoItem` += `cita: string | null`.
- `ObsolescenciaBancoComponenteOut` (la fila de la tabla del report) += `ciclo_vida_cita: string | null`.
- La unión `estado_consulta` pasa a `"ok" | "no_encontrado" | "timeout" | "error"`
  (sustituye el antiguo `"sin_respuesta"`).

## 2. UI en `RefrescoObsolescenciaProgresoDialog` (log de resultados)
Por cada línea de resultado, según `estado_consulta`:
- `"ok"`: además del `<EstadoCicloBadge estado={r.estado_nuevo} />` y el chip de tokens,
  mostrar la **prueba**: la `cita` entre comillas en bloque citado (`blockquote`/borde
  izquierdo lila, texto pequeño) y, si hay `url_fuente` disponible en la fila del report,
  un enlace "Ver fuente" (`target="_blank"`). Si no hay cita, no romper.
- `"no_encontrado"`: en vez del badge, texto atenuado **"No encontrado en la web del
  fabricante"**.
- `"timeout"`: "⏱ sin respuesta (timeout)" en ámbar (como prompt 35).
- `"error"`: "⚠ error" en rojo.

## 3. Tabla del report por banco
En la columna/celda de estado de cada componente, cuando `ciclo_vida_cita` no es null,
mostrar un icono/tooltip (o fila expandible) con la **cita textual** + enlace a
`ciclo_vida_url`. Es la evidencia de que el estado es real, no inventado.

## 4. Notas
- El sondeo y el resto del popup (prompts 34/35) no cambian; solo se añade la cita y el
  nuevo valor `no_encontrado`.
- Endpoints sin cambios: `POST /api/equipos/{id}/obsolescencia/refrescar/iniciar?limite=10`,
  `GET /api/equipos/{id}/obsolescencia/refrescar/{job_id}` → `RefrescoProgreso`,
  `GET /api/equipos/{id}/obsolescencia` → report (componentes con `ciclo_vida_cita`).
