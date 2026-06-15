# Auto-clasificación de trazabilidad (afecta_a_medida / bajo_coste)

**Fecha:** 2026-06-15
**Estado:** aprobado, en implementación
**Rama:** `feat/auto-clasificacion-trazabilidad`
**Predecesor:** `2026-06-14-criticidad-trazabilidad-design.md` (la cascada de derivación ya existe)

## Contexto y objetivo

La feature de criticidad/trazabilidad deriva `criticidad` y `nivel_trazabilidad`
automáticamente, **pero** depende de dos toggles que hoy el usuario rellena a mano por
producto: `afecta_a_medida` y `bajo_coste`. La categoría (`categoria_componente`) ya se
auto-clasifica; estos dos flags no. Objetivo: **auto-rellenar esos dos flags** para
minimizar el trabajo manual, manteniendo el override manual como escape.

Los flags solo aportan valor cuando **discrepan** de lo que ya implica la categoría
(p. ej. un cable de *sense* en "wiring" que sí afecta a la medida, o tornillería en
"accesorios" que es claramente de bajo coste). Por eso la automatización **lee la
descripción/fabricante/PN**, no solo la categoría.

No hay campo de precio/coste en `Producto`. Señales disponibles:
`categoria_componente`, `fabricante`/`fabricante_id`, `descripcion`, `part_number`,
`pn_fabricante`.

## Decisiones

- **Alcance:** solo `afecta_a_medida` y `bajo_coste`. La cascada de `app/criticidad.py`
  NO cambia. La categoría sigue clasificándose como hoy.
- **Motor híbrido:** reglas deterministas cubren la mayoría (gratis, instantáneo); un
  agente LLM headless (reusa la infra de obsolescencia) resuelve solo el residuo
  `ambiguo`, con justificación.
- **Aplicación:** auto-aplica con `origen=agente`; **nunca pisa `origen=manual`**;
  auditado y reversible.
- **Disparo:** reglas síncronas al crear/editar; LLM por lote bajo demanda.
- **`origen` a nivel del par de flags** (tocar uno a mano congela ambos) — simple, como
  `ciclo_vida_origen` de obsolescencia.

## Modelo de datos

### `Producto` (columnas nuevas)
- `clasificacion_origen: str|null` — `agente` | `manual`. Default null (= sin clasificar
  todavía; el agente puede escribir).
- `clasificacion_motivo: str|null` (texto) — razón de reglas o LLM, para transparencia
  y auditoría (estilo `ciclo_vida_cita`).
- Migración idempotente en `app/migrations.py` (`ADD COLUMN` si falta), como las previas.

No se añaden columnas para los flags: se siguen usando `afecta_a_medida`/`bajo_coste`.

## Componentes

### `app/clasificacion_trazabilidad.py` (puro, sin BD)
Motor de reglas. Estilo `criticidad.py` (funciona sobre cualquier objeto/duck-type).

```
class ResultadoClasificacion:
    afecta_a_medida: bool
    bajo_coste: bool
    ambiguo: bool        # True -> escalar al LLM
    motivo: str          # explicación corta y legible
```

`clasificar_por_reglas(categoria_componente, fabricante, descripcion, part_number) -> ResultadoClasificacion`

Reglas (se evalúan señales; las keywords son sub-cadenas case-insensitive):

- **afecta_a_medida = True** si:
  - `categoria_componente ∈ {instrumento, mass_interconnect}`, **o**
  - la descripción contiene una señal de cadena de medida:
    `_MEDIDA_KW = {sense, sonda, probe, referencia, reference, calibr, precis,
    sensor, medida, measurement, dmm, shunt, termopar, thermocouple, rtd}`.
- **bajo_coste = True** si:
  - `categoria_componente ∈ {wiring, accesorios}` **y** NO hay señal instrument-grade
    (ni keyword de medida, ni fabricante de instrumentación), **o**
  - la descripción contiene una señal de estándar barato:
    `_BARATO_KW = {tornillo, screw, etiqueta, label, brida, bracket, soporte,
    tapa, cover, patch, latiguillo, generic, generico, standard, estandar}`.
- **software / fixture_adaptador** → ambos flags `False` (la categoría ya los lleva a
  `version`; los flags no cambian el resultado).
- **ambiguo = True** (señales débiles o en conflicto) cuando:
  - categoría ∈ {accesorios, wiring} y NO casa ninguna keyword (`_MEDIDA_KW` ni
    `_BARATO_KW`), **o**
  - fabricante de instrumentación pero la descripción casa `_BARATO_KW` (posible
    accesorio barato de marca cara), **o**
  - categoría nula y sin keyword decisiva.
  En `ambiguo`, los flags propuestos por reglas son el "mejor esfuerzo conservador"
  (p. ej. accesorios sin pista → bajo_coste False, afecta False = criticidad media),
  pero se marcan para que el LLM los confirme/corrija.

Reutiliza la lista de fabricantes de instrumentación del clasificador de categoría
(`_INSTRUMENTO_SUBSTR`) — extraída a una constante compartida o duplicada con un test que
las mantenga sincronizadas.

### `consultar_clasificacion` (inyectable, LLM headless)
Firma estable, default = Claude headless (mismo plumbing que `consultar_fabricante` de
obsolescencia: binario `claude`, prompt acotado, parseo JSON robusto).

`consultar_clasificacion(part_number, descripcion, fabricante, categoria) -> dict`
→ `{afecta_a_medida: bool, bajo_coste: bool, razon: str}`.

Anti-alucinación: el prompt pide JSON estricto + razón obligatoria; si la respuesta no
parsea o no decide, el servicio descarta el resultado LLM y deja el de reglas (no
escribe basura). Inyectable para que los tests usen un fake determinista (sin red).

### `app/clasificacion_service.py`
Orquesta sobre BD. Funciones:

- `clasificar_producto(db, producto, *, usar_llm=False, consultar=consultar_clasificacion)
  -> ResultadoAplicado` — corre reglas; si `ambiguo and usar_llm`, llama al LLM y, si
  devuelve algo válido, lo usa; escribe `afecta_a_medida`, `bajo_coste`,
  `clasificacion_origen='agente'`, `clasificacion_motivo`. **No-op si
  `clasificacion_origen == 'manual'`** (devuelve estado `omitido_manual`).
- `clasificar_lote(db, *, usar_llm=True, consultar=...) -> ResumenLote` — recorre los
  `Producto.tipo == 'componente'` con `clasificacion_origen != 'manual'`; aplica reglas a
  todos y LLM a los `ambiguo`. Devuelve conteos + lista de cambios. Audita (usuario de
  `db.info`, igual que el resto).

### Trigger al vuelo (router de productos)
En el create/update de producto componente:
- Si el body trae `afecta_a_medida`, `bajo_coste` o `nivel_trazabilidad_override`
  explícitos → es edición manual → set `clasificacion_origen='manual'`, NO corre reglas.
- Si no → `clasificar_producto(db, p, usar_llm=False)` (solo reglas, síncrono, gratis).

### Endpoint + CLI por lote
- `POST /api/clasificacion-trazabilidad/lote?dry_run=<bool>` (protegido, como el resto):
  corre `clasificar_lote`; `dry_run=true` no escribe, devuelve el plan. Respuesta:
  `{procesados, por_reglas, por_llm, omitidos_manual, sin_cambios, cambios:[{producto_id,
  part_number, afecta_a_medida, bajo_coste, origen, motivo}]}`.
- CLI `backend/run_clasificacion.py` (+ `.cmd`) estilo `run_obsolescencia.py`:
  `--dry-run`, `--limite N`, `--sin-llm`. Para backfill y para Task Scheduler futuro.

### Schemas / API
- `ProductoOut`: + `clasificacion_origen` (str|null), `clasificacion_motivo` (str|null).
  `afecta_a_medida`, `bajo_coste`, `criticidad`, `nivel_trazabilidad` ya están.
- El front mostrará badge `Auto/Manual` + tooltip de motivo, y "editar a mano" que pasa a
  manual (prompt Lovable 40, follow-up; fuera del backend de este sub-proyecto).

## Flujo de datos

1. Alta/edición de componente (sin tocar flags) → reglas síncronas → flags + origen=agente.
2. Usuario lanza lote (o backfill inicial) → reglas a todos + LLM a los ambiguos → escribe
   lo que cambia, respeta manual, audita.
3. Usuario edita un flag/override a mano → origen=manual → agente no vuelve a tocarlo.

## Manejo de errores
- LLM caído / respuesta no parseable → se ignora, queda el resultado de reglas (nunca
  rompe el lote ni escribe nulos). Se cuenta como `por_reglas`.
- Producto sin descripción ni categoría → reglas devuelven `ambiguo`; sin LLM, defaults
  conservadores (media/serie).
- `dry_run` nunca escribe (verificable en test).

## Pruebas (TDD)
- `clasificacion_trazabilidad.py`: tabla de casos (cada categoría, keywords de medida,
  keywords baratas, conflictos → ambiguo), incl. duck-types.
- `clasificacion_service`: respeta `origen=manual`; escribe origen/motivo; LLM fake para
  ambiguos; LLM inválido → cae a reglas; auditoría registrada.
- Trigger al vuelo: body con flags → manual (sin reglas); body sin flags → reglas.
- Endpoint lote: dry_run no escribe; conteos correctos; protegido (401 sin token).
- Migración idempotente: corre dos veces, columnas presentes, datos preservados.

## Fuera de alcance
- Frontend (badge/tooltip/editar-a-mano) → prompt Lovable 40, follow-up.
- Tarea programada en Task Scheduler → opcional, posterior (el CLI ya lo permite).
- Baseline por unidad (conclusión 5) → sigue siendo 2º sub-proyecto de la feature previa.

## Plan de incrementos (TDD)
1. `app/clasificacion_trazabilidad.py` puro + tests (reglas + ambiguo).
2. Columnas `clasificacion_origen`/`clasificacion_motivo` + migración + schemas (`ProductoOut`).
3. `consultar_clasificacion` (LLM headless inyectable) + parseo robusto + tests con fake.
4. `app/clasificacion_service.py` (clasificar_producto + clasificar_lote) + auditoría + tests.
5. Trigger al vuelo en router de productos (manual vs agente) + tests.
6. Endpoint `POST /api/clasificacion-trazabilidad/lote` + CLI `run_clasificacion.py` + tests.
7. Backfill del catálogo vivo (lote real con backup) + verificación.
