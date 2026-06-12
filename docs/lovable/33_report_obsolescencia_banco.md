# Prompt 33 — Report de obsolescencia por banco (ficha de equipo)

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, API base
`VITE_API_BASE ?? http://127.0.0.1:8020`, helper `api<T>()` en `@/lib/api` que ya inyecta el Bearer
token, `API_BASE` también exportado desde ahí, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`,
componentes `<HelpTip clave=...>` (prompt 20) y `<EstadoCicloBadge estado url />` (prompt 32)).
**NO cambies nombres de campo del backend. No inventes endpoints ni campos fuera de los listados aquí.**
Todas estas rutas van protegidas (el `api()` ya manda el token).

Un banco (equipo) está compuesto por muchos componentes, cada uno con un estado de ciclo de vida
(obsolescencia) que mantiene el agente semanal. Este prompt añade, **en la ficha del equipo**, un
**Report de obsolescencia del banco**: ver el estado de todos sus componentes, exportarlo a Excel/PDF
y, opcionalmente, forzar una re-verificación. Es **solo lectura** salvo el botón de refrescar.

## 1. Tipos en `src/lib/types.ts`
(Reutiliza `EstadoCicloVida`/`ESTADO_CICLO_LABEL`/`ESTADO_CICLO_COLOR` del prompt 32.)
```ts
export interface ObsolescenciaBancoCabecera {
  equipo_id: number;
  numero_serie: string;
  producto: string;                 // part_number del equipo
  descripcion: string | null;
  cliente: string | null;
  estado: string;                   // estado del equipo (operativo/baja/...)
  contrato_nivel: string | null;    // bronze/silver/gold o null
}

export interface ObsolescenciaBancoComponente {
  componente_id: number;
  posicion: string | null;
  part_number: string;              // P/N 6TL del componente
  fabricante: string | null;
  pn_fabricante: string | null;
  descripcion: string;
  numero_serie: string;
  categoria_componente: string | null;
  estado_ciclo_vida: EstadoCicloVida | null;
  severidad: number;                // 0=activo/sin verificar ... 4=obsoleto
  ciclo_vida_fecha: string | null;
  ciclo_vida_url: string | null;
  ciclo_vida_resumen: string | null;
  ciclo_vida_verificado_en: string | null;
}

export interface ObsolescenciaBancoResumen {
  conteos: Record<string, number>;          // por estado
  en_riesgo: number;                         // componentes con severidad > 0
  sin_verificar: number;
  total: number;
  verificado_mas_antiguo: string | null;     // ISO date o null
}

export interface ObsolescenciaBancoReport {
  banco: ObsolescenciaBancoCabecera;
  componentes: ObsolescenciaBancoComponente[];   // YA vienen ordenados por riesgo desc
  resumen: ObsolescenciaBancoResumen;
}
```

## 2. Helper de descarga con auth en `src/lib/api.ts`
Las exportaciones devuelven un **fichero binario** con el token en cabecera, así que NO sirve un
`<a href>` directo. Añade este helper (usa `API_BASE` y el token de `localStorage["token"]`, igual que `api()`):
```ts
export async function descargarBlob(path: string, nombrePorDefecto: string): Promise<void> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("token") : null;
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(`Error ${res.status} al descargar`, res.status);
  // intenta respetar el filename del Content-Disposition
  const cd = res.headers.get("content-disposition") ?? "";
  const m = cd.match(/filename="?([^"]+)"?/);
  const nombre = m?.[1] ?? nombrePorDefecto;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

## 3. Componente `ReportObsolescenciaDialog`
Un dialog (shadcn `Dialog`) que recibe `equipoId: number` y `open`/`onOpenChange`. Al abrirse carga
`GET /api/equipos/{equipoId}/obsolescencia` → `ObsolescenciaBancoReport` (con `api<ObsolescenciaBancoReport>()`).

Contenido:
- **Título**: `Report de obsolescencia — {banco.numero_serie}` + `<HelpTip clave="obsolescencia.general" />`.
  Subtítulo con `banco.producto`, `banco.cliente ?? "—"`, y `banco.contrato_nivel` si existe.
- **Resumen (chips/tarjetas)**: `resumen.en_riesgo` (resáltalo en rojo si > 0), `resumen.sin_verificar`,
  `resumen.total`, y si `resumen.verificado_mas_antiguo` existe muéstralo como "Verificado desde {fecha}".
- **Tabla de componentes** (`resumen` arriba, luego la tabla). Una fila por `componentes[]` (ya ordenados
  por riesgo desc — respeta ese orden, NO reordenes). Columnas:
  `posicion`, `part_number`, `fabricante`, `pn_fabricante`, `numero_serie`,
  estado (`<EstadoCicloBadge estado={c.estado_ciclo_vida} url={c.ciclo_vida_url} />`),
  `ciclo_vida_fecha`, `ciclo_vida_verificado_en`. Si `c.ciclo_vida_resumen` existe, ponlo como `title`/tooltip
  de la fila o del badge. Resalta sutilmente las filas con `severidad > 0` (p.ej. fondo rojo muy tenue).
- **Barra de acciones** (pie del dialog):
  - **Exportar Excel**: `descargarBlob('/api/equipos/{equipoId}/obsolescencia/export?formato=xlsx', 'obsolescencia.xlsx')`.
  - **Exportar PDF**: `descargarBlob('/api/equipos/{equipoId}/obsolescencia/export?formato=pdf', 'obsolescencia.pdf')`.
  - **Refrescar estado**: ver punto 4.

Estados: spinner mientras carga; si `componentes` está vacío, "Este banco no tiene componentes".

## 4. Botón "Refrescar estado" (re-verificación)
- Llama `POST /api/equipos/{equipoId}/obsolescencia/refrescar?limite=10` (sin body) con `api<ObsolescenciaBancoReport>()`.
  La respuesta es el report **ya actualizado** → reemplaza el estado del dialog con ella.
- ⚠️ **Es lento**: cada componente se consulta contra la web del fabricante con un agente; puede tardar
  bastantes segundos. Muestra un aviso/confirm antes ("Re-verifica el ciclo de vida de los componentes del
  banco consultando a los fabricantes. Puede tardar un minuto.") y un spinner con texto "Verificando…"
  mientras dura. Deshabilita el botón durante la llamada. Maneja el error con un toast (no rompas el dialog).
- `limite` está acotado en backend a `1..50` (default 10); no hace falta exponerlo en la UI, deja 10 fijo.

## 5. Punto de entrada en la ficha del equipo (`src/routes/equipos.$id.tsx`)
- Añade un botón **"Report de obsolescencia"** en la cabecera de acciones de la ficha (junto a Editar / dar de
  baja, donde tengas los botones del equipo). Al pulsarlo abre `ReportObsolescenciaDialog` con el `id` del equipo.
- **NO** conviertas esto en una ruta hija nueva (evita el patrón Outlet que rompió incidencias en el prompt 17):
  es un dialog controlado por estado local de la ficha.
- No toques el resto de la ficha (componentes, incidencias, garantía, contrato…). Solo añades el botón + el dialog.

## 6. Notas
- Slugs de estado y orden de severidad: `activo < nrnd < eol_anunciado < ultima_compra < obsoleto`
  (igual que el prompt 32). El badge y los colores se reutilizan de ahí.
- El backend ya ordena los componentes por severidad descendente y calcula el resumen — el front solo pinta.
- La única escritura que añade este prompt es el botón **Refrescar** (que dispara la re-verificación por backend);
  el resto es lectura + descarga. No añadas edición de estados aquí.
- No inventes endpoints: solo `GET /api/equipos/{id}/obsolescencia`,
  `GET /api/equipos/{id}/obsolescencia/export?formato=xlsx|pdf` y `POST /api/equipos/{id}/obsolescencia/refrescar`.
