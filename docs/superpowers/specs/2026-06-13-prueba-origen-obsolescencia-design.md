# Prueba de origen (cita textual + URL verificada) y "no encontrado" — Diseño

**Fecha:** 2026-06-13
**Estado:** aprobado por el usuario (verbal) — pendiente de plan

## Problema

El chequeo de obsolescencia por componente (Claude Code headless) devuelve hoy un
estado de ciclo de vida con una `url_fuente` que el modelo *afirma* y un `resumen`.
No hay garantía de que el agente haya visitado esa URL ni de que la información sea
original (no alucinada). Además, cuando no encuentra nada, la regla actual fuerza
"activo", lo que confunde "confirmado vigente" con "no hay datos".

El usuario pide: en cada búsqueda, **prueba real de que la información se encontró
en la web y es original**; y cuando no se encuentra, mensaje explícito **"No
encontrado en la web del fabricante"**.

## Idea central

La **cita textual** es la llave del hallazgo. Un resultado solo cuenta como hallazgo
válido si trae las tres cosas:

1. `estado` (ciclo de vida válido),
2. una **cita literal** copiada de la página fuente (prueba de originalidad),
3. una `url_fuente` que el agente **abrió de verdad** (`WebFetch`) durante la búsqueda
   (verificación cruzada contra el rastro real del stream).

Si falta cualquiera de las tres → `estado_consulta = "no_encontrado"`, **no se toca el
estado** del producto, y se muestra "No encontrado en la web del fabricante".

## Decisiones tomadas

- **Tipo de prueba:** cita textual + verificación cruzada de URL (no re-fetch del backend).
- **No encontrado:** no se cambia el estado del producto; se sella
  `ciclo_vida_verificado_en = hoy` para no reintentar en cada pasada (sin tocar
  estado/cita/url). `timeout` y `error` **no** sellan (se reintentan).
- **URL no verificada** (el agente cita una URL que no abrió) → se trata como
  "no encontrado" (estricto).
- `estado_consulta` pasa a `ok | no_encontrado | timeout | error` (el antiguo
  `sin_respuesta` se unifica en `no_encontrado`).

## Componentes y cambios

### 1. Contrato del agente — `backend/obsolescencia_prompt.md`
- El JSON gana `"cita"`: fragmento textual copiado tal cual de la página (no parafraseado).
- Reglas reescritas:
  - Todo `estado` exige `cita` literal + `url_fuente` reales.
  - **Se elimina el "por defecto activo".** Si no encuentra el PN en la web del
    fabricante o una fuente fiable → devuelve `estado: null, cita: null, url_fuente: null`.
  - No inventar; la cita debe ser copia literal entre comillas.

### 2. Parser + runner — `backend/run_obsolescencia.py`
- `_procesar_stream` recolecta además las URLs realmente abiertas (`WebFetch` →
  `input.url`) y devuelve `(texto, tokens, hubo, urls_visitadas)`.
- Nuevo `_url_verificada(url_fuente, urls_visitadas) -> bool`: normaliza ambas
  (minúsculas, sin esquema, sin `www.`, sin barra final; compara host+path) y exige
  coincidencia con alguna URL visitada.
- `_parsear_estado` añade `cita` al dict que extrae.
- `consultar_fabricante`: un hallazgo es válido solo si `estado` **y** `cita` no vacía
  **y** `_url_verificada(url_fuente, urls_visitadas)`. Si no → `_sin_estado(tokens,
  "no_encontrado")`. El dict de retorno gana `cita`. `timeout` / `error` sin cambios.

### 3. Lógica pura — `backend/app/obsolescencia.py`
- Sin cambios funcionales (la regla de cita se aplica en el runner). `requiere_url`
  se mantiene como red de seguridad en `registrar_hallazgo`.

### 4. Persistencia — `backend/app/models.py` + `backend/app/migrations.py`
- `Producto.ciclo_vida_cita: str | None` (TEXT).
- `NoticiaObsolescencia.cita: str | None` (TEXT).
- Migración idempotente añade ambas columnas (`_COLUMNAS_NUEVAS`).

### 5. Servicio — `backend/app/obsolescencia_service.py`
- `registrar_hallazgo` gana parámetro `cita: str | None`; guarda
  `p.ciclo_vida_cita = cita` y `NoticiaObsolescencia(cita=cita)`.
- Nuevo `marcar_revisado(db, producto_id, hoy)`: sella solo `ciclo_vida_verificado_en`
  sin tocar estado/cita/url (para el caso "no_encontrado").

### 6. Banco / jobs / schemas
- `backend/app/obsolescencia_banco.py`:
  - `informe_banco` añade `ciclo_vida_cita` a cada fila.
  - `refrescar_banco`: pasa `cita=v.get("cita")` a `registrar_hallazgo`; cuando el
    resultado es `no_encontrado` llama `marcar_revisado`; el evento `resultado`
    incluye `cita` y el `estado_consulta` real (ya no fuerza `"ok"`).
- `backend/app/obsolescencia_jobs.py`: el item de resultado propaga `cita`;
  `estado_consulta` por defecto `no_encontrado` en lugar de `sin_respuesta`.
- `backend/app/schemas.py`:
  - `ObsolescenciaBancoComponenteOut += ciclo_vida_cita: Optional[str]`.
  - `RefrescoResultadoItem += cita: Optional[str]`.

### 7. Export — `backend/app/obsolescencia_export.py`
- Añadir columna "Cita" (`ciclo_vida_cita`) al xlsx (tras "Fuente"/"Resumen").

### 8. Frontend — prompt Lovable 36
- Tipos: `RefrescoResultadoItem += cita: string | null`; `ObsolescenciaBancoComponenteOut
  += ciclo_vida_cita`; unión `estado_consulta` añade `"no_encontrado"`.
- Diálogo de refresco: en resultados `ok`, mostrar la **cita entrecomillada + enlace a
  la fuente** (la prueba). En `no_encontrado` → "No encontrado en la web del fabricante".
- Tabla del report: la cita visible (tooltip/expand) junto a la fuente.

## Estrategia de pruebas (TDD)

- `_url_verificada`: normalización (esquema, `www`, barra final, query, mayúsculas),
  coincidencia y no-coincidencia.
- `_procesar_stream`: recolecta las URLs de `WebFetch`.
- `consultar_fabricante`: `ok` exige cita + url verificada; sin cita → `no_encontrado`;
  url citada pero no visitada → `no_encontrado`; `timeout`/`error` intactos.
- `registrar_hallazgo`: persiste `cita` en producto y noticia.
- `marcar_revisado`: sella `verificado_en` sin tocar estado/cita/url.
- migración: añade `ciclo_vida_cita` y `cita`.
- banco/jobs: propagan `cita` y `estado_consulta` correcto; `no_encontrado` llama
  `marcar_revisado` y no cambia el estado.

## Fuera de alcance (YAGNI)

- Re-fetch del backend para validar la cita (descartado por frágil).
- Estado de ciclo de vida nuevo "desconocido/sin_datos" (no se toca el enum).
