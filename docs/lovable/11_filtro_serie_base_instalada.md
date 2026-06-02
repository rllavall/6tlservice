# Prompt 11 — Filtro por nº de serie en la Base instalada

> **Prompt de ACTUALIZACIÓN** sobre la app ya generada. Pertenece al sub-proyecto 1 (base instalada),
> pero usa una mejora de backend ya disponible. Pégalo en Lovable tal cual.

## Objetivo
En la pantalla **Base instalada** (Home) añade un buscador por **número de serie** que filtre la tabla.
El backend ya soporta el filtro: `GET /api/equipos?numero_serie=<texto>` hace **match parcial e
insensible a mayúsculas**, y además **incluye equipos cuyo componente serializado** contenga ese texto.

## Archivo a tocar
`src/routes/index.tsx` (componente `BaseInstaladaPage`). **NO toques** ningún otro archivo, ni los
demás filtros (estado, producto, ubicación, cliente, part_number), ni la tabla, ni el resto de rutas.

## Qué hacer — replica EXACTAMENTE el patrón del filtro `part_number` que ya existe
El filtro `part_number` usa un input de texto con estado "aplicado" (`partNumber` / `partNumberApplied`)
y una función `applyPartNumber`. Crea su gemelo para la serie:

1. **Estado:** junto a `const [partNumber, setPartNumber] = useState("")` y
   `const [partNumberApplied, setPartNumberApplied] = useState("")`, añade:
   ```tsx
   const [numeroSerie, setNumeroSerie] = useState<string>("");
   const [numeroSerieApplied, setNumeroSerieApplied] = useState<string>("");
   ```

2. **Query:** en `equiposQ`, añade `numeroSerie: numeroSerieApplied` al `queryKey` (junto a
   `partNumber: partNumberApplied`) y, dentro del `queryFn`, en la rama que construye `params`
   (la que NO usa el endpoint de ubicación), añade:
   ```tsx
   if (numeroSerieApplied) params.set("numero_serie", numeroSerieApplied);
   ```

3. **Combinación client-side cuando hay filtro de ubicación:** en el `useMemo` de `rows` (el bloque
   `if (ubicacionId !== "all") { ... }`), añade un filtro coherente con el backend (parcial,
   insensible a mayúsculas, por serie del equipo):
   ```tsx
   if (numeroSerieApplied)
     data = data.filter((e) =>
       e.numero_serie.toLowerCase().includes(numeroSerieApplied.toLowerCase())
     );
   ```
   (En la rama de ubicación no filtramos por serie de componente; basta con la del equipo.)

4. **Aplicar:** añade `function applyNumeroSerie() { setNumeroSerieApplied(numeroSerie.trim()); }`
   y, como en part_number, dispara `applyNumeroSerie` al pulsar Enter en el input y/o con un botón
   "Buscar" al lado. Pon un input de texto con `placeholder="Buscar por nº de serie…"` en la zona de
   filtros, con el mismo estilo (shadcn `Input` + `Button`) que el de part_number.

5. **clearAll:** dentro de `clearAll()` añade `setNumeroSerie(""); setNumeroSerieApplied("");`.

6. **hasAnyFilter:** añade `|| !!numeroSerieApplied` a la condición `hasAnyFilter`.

7. **Chip de filtro activo:** donde se renderizan los `<FilterChip>`, añade uno para la serie cuando
   `numeroSerieApplied` no esté vacío:
   ```tsx
   {numeroSerieApplied && (
     <FilterChip
       label={`Serie: ${numeroSerieApplied}`}
       onRemove={() => { setNumeroSerie(""); setNumeroSerieApplied(""); }}
     />
   )}
   ```

## Contrato (verifícalo tras pegar)
- Endpoint: `GET /api/equipos?numero_serie=<texto>` → `Equipo[]`. Es **parcial + insensible a
  mayúsculas** y matchea también por serie de componente montado. Combinable con el resto de filtros.
- Campo del modelo usado en cliente: `Equipo.numero_serie` (string). No hay campos nuevos.
- Método de validación habitual: nombres de campo exactos; no fiarse de "errores CORS" engañosos.
