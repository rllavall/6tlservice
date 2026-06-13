# Prompt 35 — Pasos en vivo + tokens en el popup de refresco de obsolescencia

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, helper `api<T>()` en `@/lib/api`
(inyecta Bearer), tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`, componentes `<EstadoCicloBadge
estado url />` (prompt 32) y `RefrescoObsolescenciaProgresoDialog` (prompt 34)). **NO cambies nombres de
campo del backend. No inventes endpoints ni campos fuera de los listados.** Todo va protegido (el `api()`
manda token).

El popup `RefrescoObsolescenciaProgresoDialog` (prompt 34) sondea cada 1 s
`GET /api/equipos/{id}/obsolescencia/refrescar/{job_id}`. Hoy muestra barra X/N + componente actual + log
de resultados. El backend ahora añade, por cada componente, una **traza en vivo de lo que hace el agente**
(qué busca, qué web lee), el **consumo de tokens** (por componente + total), y marca los componentes que no
respondieron a tiempo (**timeout**). Este prompt actualiza los tipos y la UI.

## 1. Tipos en `src/lib/types.ts`
- `RefrescoActual` += `pasos: string[]`.
- `RefrescoResultadoItem` += `tokens: number` y `estado_consulta: "ok" | "sin_respuesta" | "timeout" | "error"`.
- `RefrescoProgreso` += `tokens_total: number`.

```ts
export interface RefrescoActual {
  part_number: string;
  fabricante: string | null;
  descripcion: string;
  pasos: string[];              // traza del componente en curso (cada string ya trae su emoji)
}

export interface RefrescoResultadoItem {
  part_number: string;
  descripcion: string;
  estado_anterior: EstadoCicloVida | null;
  estado_nuevo: EstadoCicloVida | null;
  cambio: boolean;
  tokens: number;
  estado_consulta: "ok" | "sin_respuesta" | "timeout" | "error";
}

export interface RefrescoProgreso {
  // ...campos del prompt 34...
  tokens_total: number;
  // ...
}
```

## 2. UI en `RefrescoObsolescenciaProgresoDialog`
- **Cabecera:** junto a "Chequeando {indice}/{total}", muestra **`Tokens: {tokens_total.toLocaleString()}`**
  (total acumulado en vivo).
- **Tarjeta del componente actual** (cuando `actual` no es null): bajo el nombre/fabricante, una **traza**
  que lista `actual.pasos[]` en orden (cada string ya viene con su emoji: "🔎 Buscando…", "🌐 Leyendo…").
  Estilo lista compacta / monoespaciada, el último elemento resaltado. Si `actual.pasos` está vacío,
  muestra "Iniciando…". Es normal que pasen segundos entre pasos (el agente consulta la web).
- **Log de resultados:** en cada línea, además de lo que ya muestra, añade los **`tokens` del componente**
  (p.ej. un chip gris "{tokens.toLocaleString()} tok"). Y según `estado_consulta`:
  - `"ok"` → `<EstadoCicloBadge estado={r.estado_nuevo} />` como hasta ahora.
  - `"timeout"` → en vez del badge, "⏱ sin respuesta (timeout)" en ámbar.
  - `"sin_respuesta"` → "— sin cambios" atenuado.
  - `"error"` → "⚠ error" en rojo.

## 3. Notas
- El sondeo y el resto del popup (prompt 34) no cambian; solo se añaden tokens y la traza de pasos.
- `actual` es `null` cuando el job termina; la traza solo se ve mientras hay un componente en curso.
- El timeout por componente es de 90 s por defecto en el backend (un componente colgado no bloquea el banco).
- Endpoints (sin cambios respecto al 34): `POST /api/equipos/{id}/obsolescencia/refrescar/iniciar?limite=10`,
  `GET /api/equipos/{id}/obsolescencia/refrescar/{job_id}` → `RefrescoProgreso` (ahora con los campos nuevos).
