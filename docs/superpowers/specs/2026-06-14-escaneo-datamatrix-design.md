# Captura de nº de serie por escaneo DataMatrix — Diseño

**Fecha:** 2026-06-14
**Estado:** aprobado por el usuario (verbal: "escribe plan e implementa") — pendiente de plan

## Problema

Al dar de alta un banco (p. ej. el iUTB) sus componentes se crean con números de serie
placeholder ("S/N pendiente (1.1)"). Rellenarlos a mano, uno a uno, es lento y propenso a
error. Los componentes llevan impreso un código **DataMatrix** del fabricante que codifica
el part number y el número de serie. El usuario quiere una pantalla donde, **escaneando ese
DataMatrix con un lector** (de tipo teclado-wedge: teclea la cadena decodificada + Enter),
el sistema **rellene automáticamente el nº de serie del componente correcto** del banco,
emparejándolo por el PN de fabricante.

## Decisiones tomadas

- **El SN escaneado va a `Componente.numero_serie`** (reemplaza el placeholder). No se crea
  un campo nuevo: el placeholder existe precisamente para ser sustituido por el serial real.
- **Auto-asignación solo del caso inequívoco.** Si el PN parseado casa con exactamente un
  componente "pendiente" del banco y hay SN → se escribe. Ambigüedad / sin match / parseo
  incompleto → NO se escribe; se devuelven datos para que la UI resuelva a mano.
- **Nunca se pisa un serial real.** Si el único componente que casa ya tiene un nº de serie
  no-placeholder, NO se sobreescribe: se devuelve como caso a confirmar (la UI ofrece la
  resolución manual). Solo se rellenan placeholders automáticamente.
- **Emparejamiento por PN de fabricante** (`Producto.pn_fabricante` del componente), no por
  el part_number interno.
- **Parseo por capas:** regla regex por fabricante (si está definida) → GS1 (AIs estándar)
  → crudo (la cadena entera como SN candidato, sin PN). La primera capa que dé un resultado
  utilizable gana.
- **Resolución manual reutiliza el endpoint existente** `PATCH /api/componentes/{id}`
  (ya soporta fijar `numero_serie` con 409 si duplica). No se crea endpoint nuevo para eso.

## Detección de "placeholder"

Un componente está "pendiente" (placeholder) si su `numero_serie` empieza por `"S/N pendiente"`
(prefijo que pone `alta_equipo.py`). Helper puro reutilizable: `es_serie_placeholder(s) -> bool`.

## Componentes y cambios

### 1. Modelo — `backend/app/models.py` + `backend/app/migrations.py`
- `Fabricante.regla_datamatrix: str | None` (TEXT, nullable). Regex con grupos nombrados
  `(?P<pn>...)` y opcional `(?P<sn>...)`.
- Migración idempotente: `fabricantes` += `regla_datamatrix` (TEXT).

### 2. Parser puro — `backend/app/datamatrix.py` (sin BD, sin imports de app)
- `parsear_gs1(raw: str) -> dict`: interpreta DataMatrix GS1. Quita prefijo de simbología
  `]d2`/`]C1` si está; separa por el separador de grupo (GS, `\x1d`) y por longitudes fijas
  de AIs comunes. Reconoce AI `21`→`sn`, AI `01`→`pn` (GTIN, 14 dígitos), AI `240`→`pn`
  (referencia adicional del fabricante). Devuelve `{"pn": str|None, "sn": str|None,
  "formato": "gs1"}`. Si no parece GS1 → `{"pn": None, "sn": None, "formato": "gs1"}`.
- `parsear_con_regla(raw: str, regla: str) -> dict | None`: compila `regla` (regex); si no
  compila o no casa → `None`. Si casa → `{"pn": grupo pn o None, "sn": grupo sn o None,
  "formato": "regla"}`.
- `parsear(raw, reglas: list[str]) -> dict`: prueba cada regla en orden (primer match con al
  menos `sn` o `pn` gana) → si ninguna, `parsear_gs1` → si tampoco da pn ni sn, fallback crudo
  `{"pn": None, "sn": raw.strip() or None, "formato": "crudo"}`.
- `es_serie_placeholder(s: str | None) -> bool`.

### 3. Servicio — `backend/app/escaneo_service.py`
- `resolver_escaneo(db, equipo_id, raw) -> dict`:
  1. 404 vía excepción propia / retorno si el equipo no existe (el router traduce a HTTP).
  2. Carga los componentes del banco (`equipo_id`) con su `Producto` (para `pn_fabricante`,
     `part_number`, `posicion`) y las `regla_datamatrix` de los fabricantes presentes.
  3. `cand = datamatrix.parsear(raw, reglas)`.
  4. Empareja `cand["pn"]` (si lo hay, normalizado: strip + upper) contra el `pn_fabricante`
     (mismo normalizado) de cada componente.
  5. Determina el estado y, si procede, escribe:
     - **`asignado`** — hay `sn` y **exactamente un** componente casa y ese componente está
       en placeholder → set `numero_serie = sn`; commit (409 → estado `duplicado`).
       Devuelve `{estado, formato, pn, sn, componente_id, posicion, part_number}`.
     - **`ambiguo`** — varios componentes casan por PN → no escribe; `candidatos` = lista de
       `{componente_id, posicion, part_number, pn_fabricante, numero_serie}`.
     - **`ocupado`** — un único componente casa pero ya tiene serial real (no placeholder) →
       no escribe; devuelve ese componente como candidato (la UI decide si reemplazar a mano).
     - **`sin_match`** — `pn` no casa con ningún componente (o no hay `pn`) → no escribe;
       devuelve `pn`, `sn`, y `candidatos` = todos los componentes en placeholder del banco.
     - **`sin_sn`** — se parseó pero no hay `sn` → no escribe; `pn`, `candidatos`.
     - **`duplicado`** — el `sn` ya existe para ese producto (IntegrityError) → no escribe.

### 4. API + schemas — `backend/app/routers/equipos.py` + `backend/app/schemas.py`
- Schema input `EscaneoIn { raw: str }` (no vacío; `min_length=1` tras strip).
- Schema salida `EscaneoResultado { estado: str, formato: str, pn: str|None, sn: str|None,
  componente_id: int|None, posicion: str|None, part_number: str|None,
  candidatos: list[EscaneoCandidato] }`.
- `EscaneoCandidato { componente_id: int, posicion: str|None, part_number: str,
  pn_fabricante: str|None, numero_serie: str }`.
- `POST /api/equipos/{equipo_id}/escaneo` (protegido por el `get_current_user` global del
  router): 404 si el equipo no existe; llama `resolver_escaneo`, devuelve `EscaneoResultado`.
- Fabricante schemas (`FabricanteCreate/Update/Out`) += `regla_datamatrix: Optional[str]`.

### 5. Frontend — prompt Lovable 38
- Nueva ruta `/escaneo` (o sub-pantalla): seleccionar un banco (equipo) → muestra la lista de
  sus componentes con `posicion`, `part_number`, `pn_fabricante` y `numero_serie`, resaltando
  los que están en placeholder, + progreso "X de N con serie real".
- Input de escaneo **autofocus** que captura la cadena del lector (acaba en Enter) →
  `POST /api/equipos/{id}/escaneo`:
  - `asignado` → marca el componente (toast verde con posición + SN), re-enfoca el input.
  - `ambiguo` / `ocupado` / `sin_match` / `sin_sn` → muestra `pn`/`sn` parseado (el formato
    `crudo` llega como `sin_match` con `sn` relleno) y deja **elegir componente de los
    candidatos + editar el SN** → `PATCH /api/componentes/{id}`
    `{numero_serie}` → refresca.
  - `duplicado` → toast de error ("ese nº de serie ya existe para este producto").
- Opcional: en la pantalla de Fabricantes, exponer el campo `regla_datamatrix` (textarea) en el
  formulario de edición. (No bloqueante para v1; el backend ya lo acepta.)

## Pruebas (TDD)

**Parser (`datamatrix.py`):**
- `parsear_gs1`: AI 21 → sn; AI 01 (GTIN 14d) → pn; prefijo `]d2` se ignora; separador GS
  entre campos de longitud variable; cadena no-GS1 → sn/pn None.
- `parsear_con_regla`: grupos `pn`/`sn` extraídos; regex que no casa → None; regex inválida → None.
- `parsear`: regla gana sobre GS1; sin regla usa GS1; sin pn/sn cae a crudo (sn=raw).
- `es_serie_placeholder`: "S/N pendiente (1.1)" → True; "ABC123" → False; None → False.

**Servicio (`escaneo_service.py`):**
- `asignado`: 1 componente placeholder con pn_fabricante coincidente → set numero_serie, estado=asignado.
- `ambiguo`: 2 componentes mismo pn_fabricante → estado=ambiguo, no escribe, candidatos=2.
- `ocupado`: 1 match pero ya con serial real → estado=ocupado, no escribe.
- `sin_match`: pn no casa → estado=sin_match, candidatos=placeholders del banco.
- `sin_sn`: regla da pn pero no sn → estado=sin_sn.
- `duplicado`: sn ya usado en ese producto → estado=duplicado (IntegrityError manejado), no escribe.
- equipo inexistente → el servicio lo señala (router 404).

**Migración:** `add_missing_columns` añade `regla_datamatrix` a `fabricantes`; idempotente.

**Endpoint:** `POST /api/equipos/{id}/escaneo` → 200 con EscaneoResultado; 404 equipo inexistente;
422 si `raw` vacío. Fabricante CRUD acepta y devuelve `regla_datamatrix`.

## Fuera de alcance (YAGNI)

- Decodificar imágenes del DataMatrix en servidor (el lector hace el OCR; recibimos texto).
- Historial / auditoría específica del escaneo (el cambio de serie ya se ve en el componente).
- Aprender reglas automáticamente; las `regla_datamatrix` se cargan a mano por fabricante.
- Escaneo de equipos completos (solo componentes de un banco existente).
