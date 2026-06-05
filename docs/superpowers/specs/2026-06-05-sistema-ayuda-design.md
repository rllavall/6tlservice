# Sistema de ayuda contextual — Design

**Fecha:** 2026-06-05
**Estado:** aprobado, pendiente de plan de implementación.

## Objetivo

Dar a la app postventa (6TL Postventa / "6tlservice") un **sistema de ayuda contextual**: tooltips /
iconos "?" junto a campos, botones y secciones, que explican qué es cada cosa sin salir de la pantalla.
El contenido vive en un **catálogo editable en el backend** (clave → texto) para poder cambiarlo sin
re-desplegar el frontend.

Decisiones de brainstorming:
- **Forma:** ayuda **contextual** (tooltips/iconos "?"), no panel por pantalla ni tour guiado.
- **Contenido:** **backend editable** (tabla `ayuda`, clave → texto), no estático en el front.
- **Gestión:** **API CRUD + catálogo inicial sembrado**; SIN pantalla de edición todavía (más adelante).

## No objetivos (YAGNI — anotados para el futuro)

Pantalla de edición `/ayuda`, permisos por rol para editar (cualquier usuario logueado puede),
versionado/historial de textos (más allá de lo que ya registra la auditoría), i18n/multi-idioma,
ayuda enriquecida (imágenes/vídeo), panel de ayuda por pantalla y tour de onboarding.

## Contexto del código (estado actual)

- Backend FastAPI + SQLAlchemy 2 (`Mapped`) + SQLite, en **:8020**. `app/db.py` (`Base`, `engine`,
  `SessionLocal`, `get_db`). `app/main.py` hace `create_all` → `add_missing_columns` →
  `registrar_listeners` (auditoría) y registra los routers internos con
  `dependencies=[Depends(get_current_user)]` (auth ya mergeada). Hay un patrón de **seed idempotente al
  arrancar** ya usado por las migraciones.
- `app/schemas.py`: `class _ORM(BaseModel): model_config = ConfigDict(from_attributes=True)`; Pydantic v2.
- Auditoría automática: un listener de `Session` registra toda alta/edición/borrado ORM con diff de campos
  (entidad = nombre de tabla). **Las escrituras de ayuda quedarán auditadas gratis** (`entidad="ayuda"`).
- `app/deps.py::get_current_user` protege los routers internos; el catálogo de ayuda se sirve **protegido**
  (se consume dentro de la app autenticada).
- Filosofía del proyecto: mínimas dependencias; tablas nuevas creadas por `create_all`.

---

## Arquitectura

Dos piezas, ambas aditivas (tabla nueva creada por `create_all`; sin cambios en `migrations.py`):

1. **Catálogo de ayuda** — modelo `AyudaTopico`, schemas, router CRUD `ayuda.py`, y un seeder
   `ayuda_seed.py` cableado al arranque.
2. **Frontend (Lovable, prompt 20)** — componente `<HelpTip clave=...>` que carga el catálogo una vez y
   pinta el icono "?" con el texto; colocado junto a los campos/secciones clave.

### 1. Modelo

**`AyudaTopico`** (tabla `ayuda`):

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | int PK | |
| `clave` | str **único, indexado** | llave natural que referencia el front, p.ej. `equipos.estado` |
| `titulo` | str, nullable | cabecera corta del tooltip |
| `texto` | str | el texto de ayuda |
| `pantalla` | str, nullable | agrupación, p.ej. `equipos`/`incidencias`/`mapa` |

La **clave** es la llave natural (lo que conoce el front); los ids numéricos no se exponen al uso normal.

### 2. Schemas (`app/schemas.py`)

```python
class AyudaOut(_ORM):
    clave: str
    titulo: Optional[str] = None
    texto: str
    pantalla: Optional[str] = None


class AyudaUpsert(BaseModel):
    titulo: Optional[str] = None
    texto: str = Field(min_length=1)
    pantalla: Optional[str] = None
```

(`AyudaOut` no expone `id`: el front trabaja por `clave`.)

### 3. Router `app/routers/ayuda.py` (protegido)

- `GET /api/ayuda?pantalla=` → `list[AyudaOut]` (filtro opcional por `pantalla`), ordenado por `clave`.
  El front lo carga **una sola vez** al entrar y cachea `clave → tópico`.
- `GET /api/ayuda/{clave}` → `AyudaOut` (404 si no existe).
- `PUT /api/ayuda/{clave}` → **upsert** con cuerpo `AyudaUpsert`: si la `clave` existe la actualiza, si no
  la crea; devuelve `AyudaOut`. Idempotente (es la vía de edición). La `clave` viene de la URL, no del cuerpo.
- `DELETE /api/ayuda/{clave}` → `204` (404 si no existe).

Se registra en `main.py` con `dependencies=[Depends(get_current_user)]`, junto a los otros routers internos.

### 4. Seeder `app/ayuda_seed.py`

- `CATALOGO_INICIAL`: lista/dict de `{clave, titulo, texto, pantalla}` con los textos de arranque, cubriendo
  los campos/estados clave de las pantallas existentes. Conjunto inicial sugerido (ampliable):
  - **equipos / base instalada:** `equipos.estado` (operativo vs baja), `equipos.categoria`,
    `equipos.numero_serie_cliente`, `equipos.version`, `garantia.estado` (vigente/por_vencer/vencida/sin_datos),
    `garantia.meses` (de dónde sale la garantía).
  - **incidencias:** `incidencias.tipo` (rma/soporte_venta/soporte_tecnico/calibracion y sus prefijos
    RMA/SV/ST/CAL), `incidencias.prioridad` (baja/media/alta), `incidencias.estado` (flujo de 5 estados),
    `incidencias.en_garantia`, `incidencias.avances` (la bitácora).
  - **mapa:** `mapa.pin` (un pin = una ubicación con coords y ≥1 equipo operativo), `mapa.incluir_baja`.
  - **analítica / resumen:** `analitica.mttr`, `resumen.tiempo_medio_cierre`.
  - **auditoría:** `auditoria.historial` (qué es el historial de cambios de la ficha).
- `sembrar_ayuda(db)`: **inserta solo las claves que falten** (no sobrescribe textos ya editados por un
  admin). Idempotente. Cableado en `main.py` tras `create_all`/`add_missing_columns`. Se ejecuta en cada
  arranque, de modo que las claves nuevas añadidas en código se siembran solas.

### 5. Frontend (prompt Lovable 20 — fuera del backend)

- **Carga única del catálogo:** al entrar en la app autenticada, `GET /api/ayuda` → mapa `clave → {titulo,
  texto, pantalla}` en un contexto/store. (Se recarga al refrescar; no hace falta invalidación fina.)
- **Componente `<HelpTip clave="equipos.estado"/>`:** pinta un icono **"?"** (Tooltip/Popover de shadcn,
  paleta lila `#9e007e`) que muestra `titulo` (si hay) + `texto`. Si la `clave` no está en el catálogo →
  **no pinta nada** (y `console.warn` en desarrollo). Accesible (botón con `aria-label`).
- **Colocación:** se inserta junto a las etiquetas de los campos/secciones clave de las pantallas (base
  instalada, ficha de equipo, alta/edición, incidencias, mapa, analítica), usando exactamente las claves
  sembradas. No cambia la lógica existente; solo añade el icono.
- **Tipos en `types.ts`:** `interface AyudaTopico { clave:string; titulo:string|null; texto:string;
  pantalla:string|null }`.

---

## Flujo de datos

1. Al arrancar el backend, `sembrar_ayuda(db)` inserta las claves del catálogo inicial que falten.
2. El usuario entra → el front hace `GET /api/ayuda` (con su Bearer) y cachea `clave → tópico`.
3. Cada `<HelpTip clave>` busca su texto en la caché y lo muestra al pulsar/hover.
4. (Edición) Un usuario logueado puede `PUT /api/ayuda/{clave}` para crear/editar un texto; la edición
   queda **auditada** (`entidad="ayuda"`). El cambio se ve tras recargar el catálogo.

## Manejo de errores

- `GET /{clave}` / `DELETE /{clave}` sobre clave inexistente → `404`.
- `PUT` con `texto` vacío → `422` (validación Pydantic `min_length=1`).
- `clave` no encontrada en el front → el `HelpTip` no se pinta (degradación silenciosa); aviso en dev.
- Endpoints protegidos: sin token → `401` (igual que el resto de routers internos).

## Pruebas (qué cubrir)

- Modelo `AyudaTopico` (clave única).
- `GET /api/ayuda` lista + filtro por `pantalla`, orden por clave.
- `GET /api/ayuda/{clave}`: existente → 200; inexistente → 404.
- `PUT /api/ayuda/{clave}`: crea (no existía) → devuelve el tópico; actualiza (existía) → cambia texto;
  `texto` vacío → 422.
- `DELETE /api/ayuda/{clave}`: existente → 204 y desaparece; inexistente → 404.
- Seeder `sembrar_ayuda`: inserta las claves que faltan; **no** sobrescribe una clave ya existente
  (idempotente); ejecutarlo dos veces no duplica.
- Protección: `GET /api/ayuda` sin token → 401 (vía `client_sin_auth`).
- Regresión: la suite previa sigue verde.

## Migración / despliegue

- Tabla nueva `ayuda` creada por `create_all` al arrancar. Sin cambios en `migrations.py`.
- `sembrar_ayuda` corre en cada arranque (insert-if-missing), así que el catálogo se mantiene al día con el
  código sin pisar ediciones.
- El frontend (prompt 20) se pega en Lovable después; el backend funciona y es testeable por su cuenta.
