# Pasos en vivo + tokens + timeout en el refresco de obsolescencia por banco — Diseño

**Fecha:** 2026-06-13
**Estado:** Aprobado (brainstorming)

## Contexto

El popup de progreso del refresco de obsolescencia por banco (`RefrescoObsolescenciaProgresoDialog`,
features mergeadas en `ea9f894` + `93e13f1`) ya muestra una barra X/N, el componente actual y un log de
resultados. Pero la consulta de cada componente —`consultar_fabricante` en `run_obsolescencia.py`, que
lanza Claude Code headless (`claude -p`)— es una **caja negra**: corre segundos/minutos y solo se ve el
resultado al final. Además:

- **No se ve qué hace el agente** mientras consulta un componente (qué busca, qué web lee).
- **No se mide el consumo de tokens** de cada búsqueda.
- El `timeout=300` actual por producto es **invisible** (al saltar, el `except` traga y devuelve `None`,
  el producto se omite en silencio) y demasiado largo: un producto colgado bloquea el banco 5 minutos
  sin que el usuario lo sepa.

El usuario quiere, dentro del popup: (1) una **traza en vivo de los pasos** del agente por componente
("🔎 Buscando…", "🌐 Leyendo…"), (2) el **consumo de tokens por componente + total acumulado**, y
(3) un **timeout corto y visible** por componente que evite cuelgues.

## Decisiones (brainstorming)

- **Límite anti-cuelgue:** timeout **por producto, visible**. Default 90 s (editable por env
  `OBSOLESCENCIA_TIMEOUT_SEG`). Al saltar → el componente se marca "sin respuesta (timeout)" en el log y
  el job sigue con el siguiente. Nunca cuelga el banco entero.
- **Tokens:** **por producto + total acumulado** en la cabecera del popup.
- **Coste monetario:** fuera de alcance (solo tokens).
- **Pasos en vivo:** mostrar los pasos de herramienta web del agente (búsquedas y fetches), no su texto
  de razonamiento.

## Enfoque: streaming del headless

Hoy se usa `claude -p` con salida de texto y se parsea el `{estado…}` que el modelo escribe. Para ver los
pasos intermedios **en vivo** hay que streamear: se pasa a
**`claude -p --output-format stream-json --verbose`** leído **línea a línea con `subprocess.Popen`**.
Ese stream emite un evento JSON por paso del agente:

- `tool_use` `WebSearch` → `input.query` → descripción **"🔎 Buscando: «{query}»"**.
- `tool_use` `WebFetch` → `input.url` → descripción **"🌐 Leyendo {dominio}"**.
- evento final `type:"result"` → trae **`usage`** (input/output tokens) y el texto (`result`) con el
  `{estado…}`.

Un solo mecanismo (stream-json + Popen) resuelve las tres cosas: pasos en vivo, tokens y timeout.

**Alternativas descartadas:** `--output-format json` (un bloque al final) no permite pasos en vivo;
estimar tokens por nº de caracteres es impreciso; mostrar el texto de razonamiento del agente es ruidoso
(YAGNI); tope de tokens global y cancelación a mitad quedan fuera (YAGNI).

## Arquitectura

### Backend

**`run_obsolescencia.py::consultar_fabricante(producto, url_obsolescencia, *, on_paso=None, timeout=None)`:**
- `Popen([claude, "--allowedTools", "WebSearch,WebFetch", "--output-format", "stream-json",
  "--verbose", "-p", prompt], stdout=PIPE, text=True, stdin=DEVNULL)`.
- Lee `stdout` línea a línea; cada línea es un JSON. Por cada `tool_use` de `WebSearch`/`WebFetch`
  construye una descripción legible y, si `on_paso` no es `None`, llama `on_paso({"descripcion": …})`.
- Del evento `type:"result"` extrae `usage` → `tokens_total = input_tokens + output_tokens`
  (+ cache si están presentes) y el texto `result`, del que saca el `{estado…}` como hoy
  (`find("{")`/`rfind("}")` + `json.loads`).
- **Timeout:** `threading.Timer(timeout, proc.kill)` arrancado antes del bucle de lectura; al saltar,
  el proceso muere, el lector ve EOF y se marca `estado_consulta="timeout"`. `timeout` por defecto =
  `int(os.environ.get("OBSOLESCENCIA_TIMEOUT_SEG", "90"))`. El Timer se cancela en `finally`.
- **Devuelve SIEMPRE un dict** (contrato aditivo; ya no `None` a secas):
  ```
  {estado: str|None, fecha_evento: date|None, url_fuente: str|None, resumen: str|None,
   tokens_total: int, estado_consulta: "ok"|"sin_respuesta"|"timeout"|"error"}
  ```
  - `estado` presente y parseado → `estado_consulta="ok"`.
  - `result` sin `{estado…}` o sin `estado` → `estado=None`, `estado_consulta="sin_respuesta"`.
  - Timer disparado → `estado=None`, `estado_consulta="timeout"`, `tokens_total=0`.
  - Cualquier otra excepción / stream ilegible → `estado=None`, `estado_consulta="error"`, `tokens_total=0`.

**`app/obsolescencia_banco.py::refrescar_banco`:** deja de hacer `if not v` (que asumía `None`). Ahora:
```python
v = consultar(p, _url_fabricante(db, p), on_paso=_reemitir_paso(on_progreso, p))
tokens = (v or {}).get("tokens_total", 0)
estado_consulta = (v or {}).get("estado_consulta", "sin_respuesta")
cambio = False
if v and v.get("estado"):
    res = obsolescencia_service.registrar_hallazgo(...)
    cambio = bool(res.get("cambio"))
    estado_consulta = "ok"
on_progreso({"tipo": "resultado", ..., "tokens": tokens, "estado_consulta": estado_consulta, "cambio": cambio})
```
- `refrescar_banco` invoca **siempre** `consultar(p, url, on_paso=…)` con el keyword. El
  `consultar_fabricante` real lo acepta; los **fakes de test** existentes se actualizan para aceptar
  `on_paso=None` (o `**kwargs`) — más limpio que un try/except por `TypeError`. El modo síncrono
  (`on_progreso is None`) pasa `on_paso=None`.
- Si `on_progreso is None` (modo síncrono / endpoint viejo), `on_paso` también es `None` → sin pasos,
  comportamiento idéntico al actual salvo el contrato de retorno.

**`run_obsolescencia.py::ejecutar` y `main()` (--dry-run):** cambian `if not v: continue` /
`if v:` por `if v and v.get("estado")` (porque `consultar_fabricante` ya no devuelve `None` en
"no concluyente"). Sin pasos ni tokens (no aplican a la pasada semanal).

**`app/obsolescencia_jobs.py`:**
- Job dict gana `tokens_total: 0`.
- `actual` gana `pasos: []`: en el callback, evento `"actual"` reinicia `actual` con `pasos: []`
  (nuevo producto); evento `"paso"` hace `actual["pasos"].append(ev["descripcion"])`; evento
  `"resultado"` añade `tokens`/`estado_consulta` al item y suma `job["tokens_total"] += ev["tokens"]`.
- `snapshot` ya copia `actual` (dict) y `resultados` (list); copiar también `actual["pasos"]` como lista
  nueva y exponer `tokens_total` (int, copia directa).

**`app/schemas.py`:**
- `RefrescoActual` += `pasos: list[str] = []`.
- `RefrescoResultadoItem` += `tokens: int`, `estado_consulta: str`.
- `RefrescoProgreso` += `tokens_total: int`.

### Frontend (prompt Lovable 35)

`RefrescoObsolescenciaProgresoDialog`:
- **Cabecera:** total de tokens en vivo (`tokens_total`, formateado con separador de miles).
- **Tarjeta del producto actual:** bajo el nombre, un **mini-trace** que lista `actual.pasos[]` en orden
  ("🔎 Buscando…", "🌐 Leyendo…"); crece con cada sondeo.
- **Log de resultados:** cada línea muestra los `tokens` del componente y, si `estado_consulta` es
  `timeout` o `sin_respuesta`, una marca distinta (icono/color) en vez del badge de estado.
- Sondeo se mantiene en 1 s (muestra siempre la traza/tokens más recientes del snapshot).
- Tipos `RefrescoActual`/`RefrescoResultadoItem`/`RefrescoProgreso` actualizados en `types.ts`.

## Manejo de errores

- Timeout de un componente → `estado_consulta="timeout"`, línea "sin respuesta (timeout)" en el log,
  tokens 0; el job continúa. Nunca cuelga el banco.
- Stream `stream-json` ilegible / sin `usage` → `tokens_total=0`, `estado_consulta="error"`,
  el job no se rompe (ese componente se omite del registro).
- `on_paso` que falla → se ignora (best-effort); no debe tumbar la consulta.
- Popup cerrado a mitad → el hilo sigue en backend hasta terminar; el cliente deja de sondear (igual que hoy).

## Pruebas (TDD)

- **`consultar_fabricante`** con un `Popen` fake que emite líneas `stream-json` (un `WebSearch`, un
  `WebFetch`, un `result` con `usage` y `{estado…}`): `on_paso` recibe una descripción por cada tool_use;
  el retorno trae `estado` + `tokens_total` correctos + `estado_consulta="ok"`. Variante sin `{estado…}`
  → `sin_respuesta`. Timer mockeado que dispara `proc.kill` → `estado_consulta="timeout"`, tokens 0.
- **`refrescar_banco`** con fake `consultar` que invoca `on_paso` y devuelve tokens → el `on_progreso`
  recibe eventos `paso` (con descripción) y un `resultado` con `tokens`/`estado_consulta`; un dict con
  `estado=None` no registra hallazgo pero sí emite `resultado`. Fake sin `on_paso` no rompe.
- **`obsolescencia_jobs`:** evento `paso` acumula en `actual.pasos`; `actual` (nuevo producto) vacía
  `pasos`; `tokens_total` se acumula; `snapshot` refleja `pasos`, `tokens`, `tokens_total`.
- **Router:** GET del job expone `actual.pasos`, `tokens_total` y `tokens`/`estado_consulta` por
  resultado (con el lanzador inline determinista ya usado en los tests del router).

## Fuera de alcance (YAGNI)

- Coste monetario (USD/€).
- Tope de tokens global / presupuesto.
- Texto de razonamiento del agente (solo pasos de herramienta web WebSearch/WebFetch).
- Cancelar un refresco en curso.
- Pasos en vivo en la pasada semanal `run_obsolescencia.py` (solo el refresco por banco del popup).
- Persistir jobs / multi-worker (sigue en memoria, proceso único on-prem).
