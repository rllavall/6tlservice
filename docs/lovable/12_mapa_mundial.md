# Prompt 12 — Mapa mundial de base instalada

> Prompt de **funcionalidad nueva** sobre la app ya generada. Requiere el shell + cliente API del
> prompt 00. Pégalo en Lovable tal cual.

## Objetivo
Añade una pantalla nueva **`/mapa`** con un **mapa mundial interactivo** que muestra **dónde hay
producto 6TL instalado**: un marcador por ubicación (en sus coordenadas), con el detalle de los
equipos que hay allí. El backend ya expone los datos agregados y geocodificados.

## Dependencias
Instala (bun/npm): `leaflet`, `react-leaflet`, y `@types/leaflet` (dev).
Importa el CSS de Leaflet **una vez** (en `mapa.tsx` o en el root): `import "leaflet/dist/leaflet.css";`.
> Usa **`CircleMarker`** (no `Marker`) para evitar el problema de las imágenes de icono por defecto de
> Leaflet con bundlers; así no hace falta configurar `L.Icon`.

## Archivos a tocar
- **Nuevo:** `src/routes/mapa.tsx` (ruta file-based; el router las genera en `routeTree.gen.ts`).
- **Navegación:** añade un enlace **"Mapa"** en el shell/nav del prompt 00, junto a Base instalada /
  Incidencias / Catálogo / Ubicaciones / Clientes. **NO toques** otras rutas ni el resto del shell.
- **`src/types.ts`:** añade los tipos `MapaUbicacion` / `MapaEquipo` (abajo).

## Contrato del backend (verifícalo tras pegar)
- `GET /api/mapa/ubicaciones?incluir_baja=false&cliente_id=<id>` → `MapaUbicacion[]`.
  - Solo devuelve ubicaciones **con coordenadas** y **con ≥1 equipo** cuya ubicación actual (último
    movimiento) es esa. Por defecto solo equipos `operativo`; `incluir_baja=true` añade los de baja.
  - `cliente_id` (opcional) filtra por el **cliente de la ubicación**.
- Shape de cada item:
  ```ts
  export type MapaEquipo = {
    id: number;
    numero_serie: string;
    producto: string;   // "PART-NUMBER — descripción"
    estado: string;     // "operativo" | "baja"
  };
  export type MapaUbicacion = {
    ubicacion_id: number;
    nombre: string;
    tipo: string;
    ciudad: string | null;
    provincia: string | null;
    pais: string | null;
    latitud: number;    // siempre presente (las sin coords no se devuelven)
    longitud: number;
    cliente: { id: number; nombre: string } | null;
    num_equipos: number;
    equipos: MapaEquipo[];
  };
  ```
- Clientes para el filtro: `GET /api/clientes` → `Cliente[]` (usa el tipo `Cliente` ya existente:
  campos `id`, `nombre`).

## Qué construir en `src/routes/mapa.tsx`
1. **Carga de datos** con el cliente API existente (TanStack Query, igual que las otras pantallas):
   - `mapaQ`: `GET /api/mapa/ubicaciones` con `queryKey` que incluya `clienteId` e `incluirBaja`, y
     que añada los query params solo cuando apliquen (`cliente_id`, `incluir_baja=true`).
   - `clientesQ`: `GET /api/clientes` para poblar el `<Select>` de cliente.
2. **Mapa** (`react-leaflet`):
   ```tsx
   <MapContainer center={[20, 0]} zoom={2} worldCopyJump style={{ height: "100%", width: "100%" }}>
     <TileLayer
       attribution='&copy; OpenStreetMap contributors'
       url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
     />
     {ubicaciones.map((u) => (
       <CircleMarker
         key={u.ubicacion_id}
         center={[u.latitud, u.longitud]}
         radius={8 + Math.sqrt(u.num_equipos) * 3}
         pathOptions={{ color: "#9e007e", fillColor: "#9e007e", fillOpacity: 0.55, weight: 1.5 }}
       >
         <Tooltip>{`${u.ciudad ?? u.nombre} (${u.num_equipos})`}</Tooltip>
         <Popup>{/* ver punto 3 */}</Popup>
       </CircleMarker>
     ))}
   </MapContainer>
   ```
   El contenedor del mapa debe ocupar la altura disponible (p. ej. `h-[calc(100vh-…)]` o un wrapper
   con altura fija ~`70vh`). El marcador usa el **lila de marca `#9e007e`**; tamaño según nº de equipos.
3. **Popup** de cada marcador: nombre de la ubicación, ciudad/país, cliente (si hay),
   `num_equipos` equipos, y una lista (máx. ~8, con "+N más") donde cada equipo enlaza a su ficha
   `/equipos/$id` (usa el `Link` del router, misma ruta que en Base instalada). Muestra
   `numero_serie` — `producto`.
4. **Filtros** (barra lateral o cabecera, estilo shadcn como el resto):
   - `<Select>` **Cliente** (opción "Todos" + cada `Cliente.nombre`).
   - `<Switch>`/checkbox **"Incluir equipos de baja"**.
5. **Resumen (KPIs)** opcional pero deseable: total de equipos en el mapa (suma de `num_equipos`),
   nº de ubicaciones y nº de países distintos (`pais`).
6. **Estados vacíos:** si no hay ubicaciones con coordenadas, muestra un aviso amable explicando que
   las ubicaciones necesitan dirección (se geocodifican al guardar) o coordenadas manuales.

## Estilo
Identidad 6TL: acento **lila `#9e007e`**, tipografías Open Sans/Roboto, mismos componentes shadcn que
el resto. El mapa puede usar el tile estándar de OpenStreetMap (claro). Marcadores en lila.

## Notas de validación (método habitual)
- Arranca el backend antes (`:8020`). Tras pegar: verifica el contrato (nombres de campo exactos:
  `ubicacion_id`, `num_equipos`, `latitud`/`longitud`, `equipos[].producto`).
- Si el mapa sale en blanco: casi siempre es que **falta importar `leaflet/dist/leaflet.css`** o que el
  contenedor no tiene altura. No te fíes de "errores CORS" engañosos (pueden ser 500 o desajuste de
  nombre de campo).
- Para ver datos: una ubicación necesita coordenadas (geocodificadas al guardar dirección con
  ciudad+país, o lat/lon manuales) y al menos un equipo movido a ella.
