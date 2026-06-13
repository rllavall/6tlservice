# Pasos en vivo + tokens + timeout en el refresco de obsolescencia — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el popup de progreso del refresco de obsolescencia por banco muestre, por cada componente, una traza en vivo de lo que hace el agente (qué busca, qué web lee), el consumo de tokens (por componente + total) y un timeout corto y visible que evite cuelgues.

**Architecture:** `consultar_fabricante` (Claude Code headless) pasa a `claude -p --output-format stream-json --verbose` leído línea a línea con `Popen`; emite pasos vía callback `on_paso`, saca tokens del evento final `result`, y se autolimita con `threading.Timer(timeout, proc.kill)`. `refrescar_banco` reemite los pasos por su `on_progreso` existente como evento `{"tipo":"paso"}`; el store de jobs acumula `tokens_total` y la traza `actual.pasos`; los schemas y el frontend (prompt 35) exponen los campos nuevos.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / Pydantic v2 / pytest. Frontend TanStack Start (prompt Lovable, fuera de este plan de código).

**Formato real de los eventos `stream-json` (verificado con `claude 2.1.177` en esta máquina):**
- Líneas ruido `{"type":"system",...}` (incluye un hook SessionStart con `additionalContext` enorme) → se ignoran.
- `{"type":"assistant","message":{"content":[{"type":"tool_use","name":"WebSearch","input":{"query":"..."}}]}}` — un bloque `tool_use` por herramienta. `WebSearch`→`input.query`; `WebFetch`→`input.url`. Hay también `name:"ToolSearch"` (carga de tools) = ruido, se ignora por nombre.
- `{"type":"result","subtype":"success","result":"<texto con el {estado…}>","usage":{"input_tokens":N,"output_tokens":N,"cache_creation_input_tokens":N,"cache_read_input_tokens":N},...}` — evento final con el texto y los tokens.

**Ejecución de tests (siempre desde `backend/`):** `.venv/Scripts/python -m pytest <ruta> -v`.
⚠️ **Parar uvicorn (:8020) antes de correr tests**: el seeder de ayuda toca `postventa.db` al importar y SQLite se bloquea. (`netstat -ano | grep :8020` → `taskkill /PID <pid> /F` si hace falta; relanzar al terminar.)

---

### Task 1: `consultar_fabricante` por streaming (pasos + tokens + timeout)

**Files:**
- Modify: `backend/run_obsolescencia.py` (reemplaza `consultar_fabricante`, añade helpers)
- Test: `backend/tests/test_consultar_fabricante.py` (nuevo)

Añade `import threading` y `from urllib.parse import urlparse` arriba (junto a los imports existentes `json, os, shutil, subprocess, sys`).

- [ ] **Step 1: Escribe los tests (fallan)**

Crea `backend/tests/test_consultar_fabricante.py`:

```python
"""Tests del parser stream-json y del runner con timeout de consultar_fabricante."""
import json
from datetime import date

import run_obsolescencia as ro


class _Producto:
    fabricante = "Beta"
    pn_fabricante = "BET-1"
    descripcion = "Cable"
    fabricante_id = None


def _linea_assistant(name, inp):
    return json.dumps({"type": "assistant",
                       "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}})


def _linea_result(texto, usage):
    return json.dumps({"type": "result", "subtype": "success", "result": texto, "usage": usage})


def test_descripcion_paso_websearch_y_webfetch():
    assert ro._descripcion_paso("WebSearch", {"query": "MAX3232 EOL"}) == "🔎 Buscando: «MAX3232 EOL»"
    assert ro._descripcion_paso("WebFetch", {"url": "https://www.digikey.com/x"}) == "🌐 Leyendo www.digikey.com"
    assert ro._descripcion_paso("ToolSearch", {"query": "select:WebSearch"}) is None


def test_tokens_de_usage_suma_los_cuatro_campos():
    u = {"input_tokens": 10, "output_tokens": 5,
         "cache_creation_input_tokens": 2, "cache_read_input_tokens": 100}
    assert ro._tokens_de_usage(u) == 117
    assert ro._tokens_de_usage({}) == 0


def test_procesar_stream_emite_pasos_y_saca_tokens_y_texto():
    lineas = [
        '{"type":"system","subtype":"init"}',
        '{"type":"system","subtype":"hook_started"}',
        _linea_assistant("ToolSearch", {"query": "select:WebSearch"}),
        _linea_assistant("WebSearch", {"query": "MAX3232 lifecycle"}),
        _linea_assistant("WebFetch", {"url": "https://www.ti.com/product/MAX3232"}),
        _linea_result('Respuesta: {"estado":"obsoleto","fecha_evento":"2025-01-01","url_fuente":"http://ti","resumen":"EOL"}',
                      {"input_tokens": 4000, "output_tokens": 100,
                       "cache_creation_input_tokens": 0, "cache_read_input_tokens": 20000}),
    ]
    pasos = []
    texto, tokens, hubo = ro._procesar_stream(iter(lineas), on_paso=lambda ev: pasos.append(ev["descripcion"]))
    assert hubo is True
    assert tokens == 24100
    assert "obsoleto" in texto
    # ToolSearch ignorado; solo WebSearch + WebFetch generan pasos
    assert pasos == ["🔎 Buscando: «MAX3232 lifecycle»", "🌐 Leyendo www.ti.com"]


def test_parsear_estado_extrae_dict_o_none():
    d = ro._parsear_estado('bla {"estado":"eol_anunciado","fecha_evento":"2025-06-01"} fin')
    assert d["estado"] == "eol_anunciado"
    assert d["fecha_evento"] == date(2025, 6, 1)
    assert ro._parsear_estado("sin json aqui") is None
    assert ro._parsear_estado('{"resumen":"x"}') is None  # sin estado


class _FakeProc:
    def __init__(self, lineas):
        self.stdout = iter(lineas)
        self.killed = False
    def kill(self):
        self.killed = True
    def wait(self, timeout=None):
        return 0


class _TimerInmediato:
    """Factory de timer que dispara la función al instante (simula expiración)."""
    def __init__(self, _seg, fn):
        self._fn = fn
    def start(self):
        self._fn()
    def cancel(self):
        pass


class _TimerNulo:
    def __init__(self, _seg, fn):
        pass
    def start(self):
        pass
    def cancel(self):
        pass


def test_consultar_fabricante_ok_devuelve_estado_y_tokens():
    lineas = [
        _linea_assistant("WebSearch", {"query": "BET-1 EOL"}),
        _linea_result('{"estado":"nrnd","fecha_evento":null,"url_fuente":"http://b","resumen":"r"}',
                      {"input_tokens": 1000, "output_tokens": 50}),
    ]
    pasos = []
    v = ro.consultar_fabricante(_Producto(), "http://beta", on_paso=lambda ev: pasos.append(ev["descripcion"]),
                                _popen=lambda: _FakeProc(lineas), _timer_factory=_TimerNulo)
    assert v["estado"] == "nrnd"
    assert v["estado_consulta"] == "ok"
    assert v["tokens_total"] == 1050
    assert pasos == ["🔎 Buscando: «BET-1 EOL»"]


def test_consultar_fabricante_sin_estado_es_sin_respuesta():
    lineas = [_linea_result("no encontré nada concluyente", {"input_tokens": 500, "output_tokens": 10})]
    v = ro.consultar_fabricante(_Producto(), None, _popen=lambda: _FakeProc(lineas), _timer_factory=_TimerNulo)
    assert v["estado"] is None
    assert v["estado_consulta"] == "sin_respuesta"
    assert v["tokens_total"] == 510


def test_consultar_fabricante_timeout_marca_timeout_y_mata_proceso():
    proc = _FakeProc([])  # no llega ningún result
    v = ro.consultar_fabricante(_Producto(), None, _popen=lambda: proc, _timer_factory=_TimerInmediato)
    assert v["estado_consulta"] == "timeout"
    assert v["estado"] is None
    assert proc.killed is True
```

- [ ] **Step 2: Corre los tests, fallan**

Run: `.venv/Scripts/python -m pytest tests/test_consultar_fabricante.py -v`
Expected: FAIL (`_descripcion_paso` / `_procesar_stream` / nuevos kwargs no existen).

- [ ] **Step 3: Implementa los helpers + reescribe `consultar_fabricante`**

En `backend/run_obsolescencia.py`, añade los imports y reemplaza la función `consultar_fabricante` (líneas ~51-84) por:

```python
def _descripcion_paso(name, inp):
    """Descripción legible de un tool_use de búsqueda web; None si no es WebSearch/WebFetch."""
    if name == "WebSearch":
        q = (inp or {}).get("query")
        return f"🔎 Buscando: «{q}»" if q else None
    if name == "WebFetch":
        url = (inp or {}).get("url") or ""
        dom = urlparse(url).netloc or url
        return f"🌐 Leyendo {dom}" if dom else None
    return None


def _tokens_de_usage(usage):
    """Suma los tokens del bloque usage (input+output+cache); 0 si falta."""
    u = usage or {}
    return sum(int(u.get(k, 0) or 0) for k in (
        "input_tokens", "output_tokens",
        "cache_creation_input_tokens", "cache_read_input_tokens"))


def _procesar_stream(lineas, on_paso=None):
    """Consume líneas stream-json. Por cada tool_use de búsqueda llama on_paso.
    Devuelve (texto_result|None, tokens_total, hubo_result)."""
    texto = None
    tokens = 0
    for linea in lineas:
        linea = (linea or "").strip()
        if not linea:
            continue
        try:
            ev = json.loads(linea)
        except ValueError:
            continue
        tipo = ev.get("type")
        if tipo == "assistant":
            for b in ev.get("message", {}).get("content", []) or []:
                if b.get("type") != "tool_use":
                    continue
                desc = _descripcion_paso(b.get("name"), b.get("input"))
                if desc and on_paso is not None:
                    try:
                        on_paso({"descripcion": desc})
                    except Exception:
                        pass
        elif tipo == "result":
            texto = ev.get("result")
            tokens = _tokens_de_usage(ev.get("usage"))
    return texto, tokens, (texto is not None)


def _parsear_estado(out):
    """Extrae el dict {estado,fecha_evento,url_fuente,resumen} del texto, o None."""
    if not out:
        return None
    inicio, fin = out.find("{"), out.rfind("}")
    if inicio == -1 or fin == -1:
        return None
    try:
        data = json.loads(out[inicio:fin + 1])
    except ValueError:
        return None
    if not data.get("estado"):
        return None
    fe = data.get("fecha_evento")
    return {
        "estado": data["estado"],
        "fecha_evento": date.fromisoformat(fe) if fe else None,
        "url_fuente": data.get("url_fuente"),
        "resumen": data.get("resumen"),
    }


def _sin_estado(tokens, estado_consulta):
    return {"estado": None, "fecha_evento": None, "url_fuente": None, "resumen": None,
            "tokens_total": tokens, "estado_consulta": estado_consulta}


def consultar_fabricante(producto, url_obsolescencia, *, on_paso=None, timeout=None,
                         _popen=None, _timer_factory=threading.Timer):
    """Lanza Claude Code headless en streaming para investigar el ciclo de vida.

    Emite los pasos web vía `on_paso({"descripcion": ...})`, mide tokens y se
    autolimita con un timeout (default env OBSOLESCENCIA_TIMEOUT_SEG=90; al saltar
    mata el proceso). Devuelve SIEMPRE un dict con `estado` (str|None),
    `fecha_evento`, `url_fuente`, `resumen`, `tokens_total` y `estado_consulta`
    ∈ ok|sin_respuesta|timeout|error. `_popen`/`_timer_factory` son inyectables
    para test."""
    if timeout is None:
        timeout = int(os.environ.get("OBSOLESCENCIA_TIMEOUT_SEG", "90"))
    plantilla = (Path(__file__).with_name("obsolescencia_prompt.md")).read_text(encoding="utf-8")
    prompt = plantilla.format(
        fabricante=producto.fabricante or "",
        pn=producto.pn_fabricante or "",
        descripcion=producto.descripcion or "",
        url=url_obsolescencia or "(sin URL conocida; busca en abierto)",
    )
    cmd = [_claude_bin(), "--allowedTools", "WebSearch,WebFetch",
           "--output-format", "stream-json", "--verbose", "-p", prompt]

    def _abrir():
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")

    expirado = {"v": False}
    try:
        proc = (_popen or _abrir)()
    except Exception:
        return _sin_estado(0, "error")

    def _matar():
        expirado["v"] = True
        try:
            proc.kill()
        except Exception:
            pass

    timer = _timer_factory(timeout, _matar)
    timer.start()
    try:
        texto, tokens, _ = _procesar_stream(proc.stdout, on_paso)
    except Exception:
        timer.cancel()
        try:
            proc.kill()
        except Exception:
            pass
        return _sin_estado(0, "error")
    finally:
        timer.cancel()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    if expirado["v"]:
        return _sin_estado(tokens, "timeout")
    hallazgo = _parsear_estado(texto)
    if hallazgo:
        hallazgo["tokens_total"] = tokens
        hallazgo["estado_consulta"] = "ok"
        return hallazgo
    return _sin_estado(tokens, "sin_respuesta")
```

- [ ] **Step 4: Corre los tests, pasan**

Run: `.venv/Scripts/python -m pytest tests/test_consultar_fabricante.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/run_obsolescencia.py backend/tests/test_consultar_fabricante.py
git commit -m "feat(obsolescencia): consultar_fabricante por streaming (pasos+tokens+timeout)"
```

---

### Task 2: Adaptar el camino síncrono (pasada semanal) al nuevo contrato

`consultar_fabricante` ya no devuelve `None` en "no concluyente" sino un dict con `estado=None`. Los consumidores que hacían `if v:`/`if not v: continue` registrarían un hallazgo con `estado=None` → hay que guardar por `estado`.

**Files:**
- Modify: `backend/run_obsolescencia.py` (`ejecutar`, `main`)
- Test: `backend/tests/test_run_obsolescencia_contrato.py` (nuevo)

- [ ] **Step 1: Test (falla)**

Crea `backend/tests/test_run_obsolescencia_contrato.py`:

```python
"""ejecutar() no debe registrar hallazgo cuando consultar devuelve estado=None."""
from datetime import date

import run_obsolescencia as ro
from app import models, obsolescencia_service


def _seed(db):
    p = models.Producto(part_number="P1", tipo="componente", descripcion="x",
                        fabricante="Beta", pn_fabricante="B1", estado_ciclo_vida="activo")
    db.add(p); db.commit()
    return p.id


def test_ejecutar_ignora_dict_sin_estado(db_session, monkeypatch):
    pid = _seed(db_session)
    # consultar devuelve el dict "sin respuesta" del nuevo contrato
    def fake(p, url, **kw):
        return {"estado": None, "tokens_total": 500, "estado_consulta": "sin_respuesta"}
    monkeypatch.setattr(obsolescencia_service, "productos_a_revisar",
                        lambda db, hoy, limite=20: db.query(models.Producto).all())
    ro.ejecutar(db_session, date(2026, 6, 13), consultar=fake,
                notificar_fn=lambda *a, **k: {"enviado": False, "canales": []})
    p = db_session.get(models.Producto, pid)
    assert p.estado_ciclo_vida == "activo"  # no cambió: no se registró nada
```

- [ ] **Step 2: Corre, falla**

Run: `.venv/Scripts/python -m pytest tests/test_run_obsolescencia_contrato.py -v`
Expected: FAIL (intenta `registrar_hallazgo` con estado None → error o cambia estado).

- [ ] **Step 3: Implementa el guard**

En `backend/run_obsolescencia.py::ejecutar`, cambia:
```python
        v = consultar(p, url)
        if not v:
            continue
```
por:
```python
        v = consultar(p, url)
        if not v or not v.get("estado"):
            continue
```

En `main()` (rama `--dry-run`), cambia:
```python
                v = consultar_fabricante(p, _url_fabricante(db, p))
                if v:
```
por:
```python
                v = consultar_fabricante(p, _url_fabricante(db, p))
                if v and v.get("estado"):
```

- [ ] **Step 4: Corre, pasa**

Run: `.venv/Scripts/python -m pytest tests/test_run_obsolescencia_contrato.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/run_obsolescencia.py backend/tests/test_run_obsolescencia_contrato.py
git commit -m "fix(obsolescencia): guard por estado en la pasada semanal (nuevo contrato dict)"
```

---

### Task 3: `refrescar_banco` reemite pasos + tokens/estado_consulta en `resultado`

**Files:**
- Modify: `backend/app/obsolescencia_banco.py` (`refrescar_banco`, + helper `_reemitir_paso`)
- Modify: `backend/tests/test_obsolescencia_banco.py` (fakes aceptan `on_paso`; test nuevo)

- [ ] **Step 1: Actualiza los fakes existentes y añade el test (falla)**

En `backend/tests/test_obsolescencia_banco.py`, los fakes deben aceptar `on_paso` (ahora `refrescar_banco` siempre lo pasa). Cambia las firmas:
- `def fake_consultar(producto, url):` → `def fake_consultar(producto, url, *, on_paso=None):` (las 2 apariciones)
- `def fake(p, url):` → `def fake(p, url, *, on_paso=None):` (las 2 apariciones, en `test_refrescar_banco_emite_progreso` y donde aparezca)

Añade al final de `backend/tests/test_obsolescencia_banco.py`:

```python
def test_refrescar_banco_reemite_pasos_y_tokens(db_session):
    eq_id = _seed_banco(db_session)

    def fake(p, url, *, on_paso=None):
        if on_paso:
            on_paso({"descripcion": "🔎 Buscando: «x»"})
            on_paso({"descripcion": "🌐 Leyendo ti.com"})
        if p.part_number == "P-ACT":
            return {"estado": "obsoleto", "fecha_evento": None, "url_fuente": "http://b",
                    "resumen": "x", "tokens_total": 1234, "estado_consulta": "ok"}
        return {"estado": None, "tokens_total": 99, "estado_consulta": "sin_respuesta"}

    ev = []
    obsolescencia_banco.refrescar_banco(
        db_session, eq_id, date(2026, 6, 13), limite=10,
        consultar=fake, on_progreso=ev.append)

    pasos = [e for e in ev if e["tipo"] == "paso"]
    assert any(e["descripcion"] == "🔎 Buscando: «x»" for e in pasos)
    # cada producto emite 2 pasos
    assert len(pasos) >= 2
    # los pasos de un producto van entre su 'actual' y su 'resultado'
    res = [e for e in ev if e["tipo"] == "resultado"]
    pact = next(e for e in res if e["producto"].part_number == "P-ACT")
    assert pact["tokens"] == 1234
    assert pact["estado_consulta"] == "ok"
    pobs = next(e for e in res if e["producto"].part_number == "P-OBS")
    assert pobs["tokens"] == 99
    assert pobs["estado_consulta"] == "sin_respuesta"
```

- [ ] **Step 2: Corre, falla**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py -v`
Expected: FAIL en el test nuevo (no hay evento `paso` ni claves `tokens`/`estado_consulta`). Los demás tests del fichero deben seguir verdes tras actualizar los fakes.

- [ ] **Step 3: Implementa**

En `backend/app/obsolescencia_banco.py`, añade el helper antes de `refrescar_banco`:

```python
def _reemitir_paso(on_progreso, producto, indice, total):
    """Devuelve un on_paso que reemite cada paso como evento 'paso' del on_progreso."""
    if on_progreso is None:
        return None

    def on_paso(ev):
        on_progreso({"tipo": "paso", "indice": indice, "total": total,
                     "producto": producto, "descripcion": ev.get("descripcion")})
    return on_paso
```

Reemplaza el cuerpo del bucle `for i, p in enumerate(...)` de `refrescar_banco` por:

```python
    for i, p in enumerate(prods, start=1):
        if on_progreso is not None:
            on_progreso({"tipo": "actual", "indice": i, "total": total, "producto": p})
        anterior = p.estado_ciclo_vida
        try:
            v = consultar(p, _url_fabricante(db, p),
                          on_paso=_reemitir_paso(on_progreso, p, i, total))
        except Exception:
            v = None
        tokens = (v or {}).get("tokens_total", 0)
        estado_consulta = (v or {}).get("estado_consulta", "sin_respuesta")
        cambio = False
        if v and v.get("estado"):
            res = obsolescencia_service.registrar_hallazgo(
                db, p.id, v["estado"], hoy=hoy, fecha_evento=v.get("fecha_evento"),
                url=v.get("url_fuente"), resumen=v.get("resumen"))
            cambio = bool(res.get("cambio"))
            estado_consulta = "ok"
        if on_progreso is not None:
            on_progreso({"tipo": "resultado", "indice": i, "total": total, "producto": p,
                         "estado_anterior": anterior, "estado_nuevo": p.estado_ciclo_vida,
                         "cambio": cambio, "tokens": tokens, "estado_consulta": estado_consulta})
```

Actualiza el docstring de `refrescar_banco` para mencionar el evento `paso` y las claves `tokens`/`estado_consulta` del evento `resultado`.

> Nota: `refrescar_banco` ahora invoca SIEMPRE `consultar(p, url, on_paso=…)`. El `consultar_fabricante` real (Task 1) lo acepta; los fakes de test se actualizaron en el Step 1; cuando `on_progreso is None`, `_reemitir_paso` devuelve `None` → `on_paso=None`.

- [ ] **Step 4: Corre, pasa**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py -v`
Expected: PASS (todos, incluido el nuevo).

- [ ] **Step 5: Commit**

```bash
git add backend/app/obsolescencia_banco.py backend/tests/test_obsolescencia_banco.py
git commit -m "feat(obsolescencia): refrescar_banco reemite pasos + tokens/estado_consulta"
```

---

### Task 4: Store de jobs acumula `tokens_total` y la traza `actual.pasos`

**Files:**
- Modify: `backend/app/obsolescencia_jobs.py` (`crear_job`, `_hacer_callback`)
- Modify: `backend/tests/test_obsolescencia_jobs.py` (fakes aceptan `on_paso`; test nuevo)

- [ ] **Step 1: Actualiza fakes y añade test (falla)**

En `backend/tests/test_obsolescencia_jobs.py`:
- `def fake(p, url):` → `def fake(p, url, *, on_paso=None):` y que devuelva tokens:
  ```python
  def fake(p, url, *, on_paso=None):
      if on_paso:
          on_paso({"descripcion": "🔎 Buscando: «x»"})
      return {"estado": "obsoleto", "fecha_evento": None, "url_fuente": "http://b/eol",
              "resumen": "x", "tokens_total": 321, "estado_consulta": "ok"}
  ```
- `consultar=lambda p, u: None` → `consultar=lambda p, u, **kw: None`

Amplía las asserts de `test_ejecutar_job_termina_con_progreso_y_report` añadiendo:
```python
    assert snap["tokens_total"] == 321
    assert snap["resultados"][0]["tokens"] == 321
    assert snap["resultados"][0]["estado_consulta"] == "ok"
```

Añade un test directo del callback:
```python
def test_callback_acumula_pasos_y_tokens():
    job_id = obsolescencia_jobs.crear_job(1, 2)
    cb = obsolescencia_jobs._hacer_callback(job_id)

    class _P:
        part_number = "P1"; fabricante = "Beta"; descripcion = "Cable"

    p = _P()
    cb({"tipo": "actual", "indice": 1, "total": 2, "producto": p})
    cb({"tipo": "paso", "indice": 1, "total": 2, "producto": p, "descripcion": "🔎 a"})
    cb({"tipo": "paso", "indice": 1, "total": 2, "producto": p, "descripcion": "🌐 b"})
    snap1 = obsolescencia_jobs.snapshot(job_id)
    assert snap1["actual"]["pasos"] == ["🔎 a", "🌐 b"]

    cb({"tipo": "resultado", "indice": 1, "total": 2, "producto": p,
        "estado_anterior": "activo", "estado_nuevo": "obsoleto", "cambio": True,
        "tokens": 100, "estado_consulta": "ok"})
    # nuevo producto vacía pasos
    cb({"tipo": "actual", "indice": 2, "total": 2, "producto": p})
    snap2 = obsolescencia_jobs.snapshot(job_id)
    assert snap2["actual"]["pasos"] == []
    assert snap2["tokens_total"] == 100
    assert snap2["resultados"][0]["tokens"] == 100
```

- [ ] **Step 2: Corre, falla**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_jobs.py -v`
Expected: FAIL (no hay `tokens_total`, ni `pasos`, ni manejo de evento `paso`).

- [ ] **Step 3: Implementa**

En `backend/app/obsolescencia_jobs.py`, en `crear_job` añade `"tokens_total": 0,` al dict del job (junto a las otras claves).

Reemplaza `_hacer_callback` por:

```python
def _hacer_callback(job_id: str):
    def cb(ev: dict) -> None:
        p = ev["producto"]
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is None:
                return
            if ev["tipo"] == "actual":
                job["indice"] = ev["indice"]
                job["actual"] = {"part_number": p.part_number,
                                 "fabricante": p.fabricante,
                                 "descripcion": p.descripcion,
                                 "pasos": []}
            elif ev["tipo"] == "paso":
                if job["actual"] is not None and ev.get("descripcion"):
                    job["actual"]["pasos"].append(ev["descripcion"])
            elif ev["tipo"] == "resultado":
                job["resultados"].append({
                    "part_number": p.part_number,
                    "descripcion": p.descripcion,
                    "estado_anterior": ev["estado_anterior"],
                    "estado_nuevo": ev["estado_nuevo"],
                    "cambio": ev["cambio"],
                    "tokens": ev.get("tokens", 0),
                    "estado_consulta": ev.get("estado_consulta", "ok"),
                })
                job["tokens_total"] += ev.get("tokens", 0)
    return cb
```

En `snapshot`, copia también `pasos` como lista nueva (evita lecturas rotas):
```python
        copia["actual"] = dict(job["actual"]) if job["actual"] else None
        if copia["actual"] is not None:
            copia["actual"]["pasos"] = list(job["actual"].get("pasos", []))
```
(`tokens_total` es un int: ya se copia con `dict(job)`.)

- [ ] **Step 4: Corre, pasa**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_jobs.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/obsolescencia_jobs.py backend/tests/test_obsolescencia_jobs.py
git commit -m "feat(obsolescencia): jobs acumulan tokens_total y traza actual.pasos"
```

---

### Task 5: Schemas + test de router (exponer los campos nuevos)

El router GET devuelve `snapshot` validado por `RefrescoProgreso`; basta con ampliar los schemas y verificar que el GET expone los campos.

**Files:**
- Modify: `backend/app/schemas.py` (`RefrescoActual`, `RefrescoResultadoItem`, `RefrescoProgreso`)
- Modify: `backend/tests/test_obsolescencia_banco_router.py` (fakes aceptan `on_paso`; asserts nuevos)

- [ ] **Step 1: Amplía los schemas y el test del router (falla)**

En `backend/app/schemas.py` (líneas ~952-975):
```python
class RefrescoActual(BaseModel):
    part_number: str
    fabricante: Optional[str] = None
    descripcion: str
    pasos: list[str] = Field(default_factory=list)


class RefrescoResultadoItem(BaseModel):
    part_number: str
    descripcion: str
    estado_anterior: Optional[str] = None
    estado_nuevo: Optional[str] = None
    cambio: bool
    tokens: int = 0
    estado_consulta: str = "ok"


class RefrescoProgreso(BaseModel):
    job_id: str
    equipo_id: int
    total: int
    indice: int
    estado: str  # en_curso | terminado | error
    tokens_total: int = 0
    actual: Optional[RefrescoActual] = None
    resultados: list[RefrescoResultadoItem] = Field(default_factory=list)
    report: Optional[ObsolescenciaBancoOut] = None
    error: Optional[str] = None
```

En `backend/tests/test_obsolescencia_banco_router.py`:
- El fake de `get_consultar_fabricante` que devuelve estado debe aceptar `on_paso` y emitir un paso + tokens. Cambia (línea ~104):
  ```python
  app.dependency_overrides[get_consultar_fabricante] = lambda: (
      lambda p, url, *, on_paso=None: (
          on_paso({"descripcion": "🔎 Buscando: «x»"}) if on_paso else None,
          {"estado": "obsoleto", "fecha_evento": None, "url_fuente": "http://b",
           "resumen": "x", "tokens_total": 777, "estado_consulta": "ok"})[1])
  ```
  (o, más legible, define una función `def _fake(p, url, *, on_paso=None): ...` en el test.)
- El fake `lambda p, url: None` (línea ~128) → `lambda p, url, *, on_paso=None: {"estado": None, "tokens_total": 0, "estado_consulta": "sin_respuesta"}` (o que acepte `**kw`).

En el test del progreso (el que monkeypatchea `lanzar`→`ejecutar` inline y hace el GET), añade asserts:
```python
    assert cuerpo["tokens_total"] == 777
    assert cuerpo["resultados"][0]["tokens"] == 777
    assert cuerpo["resultados"][0]["estado_consulta"] == "ok"
    # actual.pasos presente en el schema (lista, posiblemente vacía al terminar)
    # (cuando estado == terminado, actual es None; el campo vive en RefrescoActual)
```
(Ajusta los nombres `cuerpo`/variable según el test existente.)

- [ ] **Step 2: Corre, falla**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco_router.py -v`
Expected: FAIL (asserts de `tokens_total`/`tokens` antes de ampliar schema, o fake con firma vieja).

- [ ] **Step 3: Implementa**

Aplica los cambios de schema del Step 1. (Los fakes del test ya se actualizaron en el Step 1.)

- [ ] **Step 4: Corre, pasa**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco_router.py -v`
Expected: PASS.

- [ ] **Step 5: Suite completa de obsolescencia + commit**

Run: `.venv/Scripts/python -m pytest tests/ -k obsolescencia -v`
Expected: PASS (toda la familia obsolescencia verde).

```bash
git add backend/app/schemas.py backend/tests/test_obsolescencia_banco_router.py
git commit -m "feat(obsolescencia): schemas exponen tokens_total, tokens, estado_consulta y pasos"
```

---

### Task 6: Prompt Lovable 35 (frontend) + README

**Files:**
- Create: `docs/lovable/35_pasos_tokens_obsolescencia.md`
- Modify: `docs/lovable/README.md` (fila nueva)

- [ ] **Step 1: Escribe el prompt 35**

Crea `docs/lovable/35_pasos_tokens_obsolescencia.md` con el contenido (sin código backend, solo instrucciones para Lovable):

```markdown
# Prompt 35 — Pasos en vivo + tokens en el popup de refresco de obsolescencia

Contexto: app postventa 6TL (TanStack Start, `api<T>()` en `@/lib/api` inyecta Bearer, tipos en
`@/lib/types`, shadcn, paleta lila #9e007e). El popup `RefrescoObsolescenciaProgresoDialog`
(prompt 34) sondea cada 1 s `GET /api/equipos/{id}/obsolescencia/refrescar/{job_id}`.
**NO cambies nombres de campo del backend. No inventes endpoints ni campos.**

El backend añade campos al progreso. Actualiza los tipos y la UI.

## 1. Tipos en `src/lib/types.ts`
- `RefrescoActual` += `pasos: string[]`.
- `RefrescoResultadoItem` += `tokens: number` y `estado_consulta: "ok" | "sin_respuesta" | "timeout" | "error"`.
- `RefrescoProgreso` += `tokens_total: number`.

## 2. UI en `RefrescoObsolescenciaProgresoDialog`
- **Cabecera:** junto a "Chequeando i/total", muestra **`Tokens: {tokens_total.toLocaleString()}`** (total en vivo).
- **Tarjeta del componente actual:** bajo el nombre/fabricante, una **traza** que lista `actual.pasos[]` en
  orden (cada string ya viene con su emoji: "🔎 Buscando…", "🌐 Leyendo…"). Estilo lista compacta/monoespaciada,
  el último elemento resaltado. Si `pasos` está vacío, muestra "Iniciando…".
- **Log de resultados:** en cada línea, además del badge de estado, muestra los **`tokens` del componente**
  (p.ej. chip gris "{tokens.toLocaleString()} tok"). Si `estado_consulta === "timeout"` muestra
  "⏱ sin respuesta (timeout)" en ámbar en vez del badge; si `=== "sin_respuesta"` muestra "— sin cambios"
  atenuado; si `=== "error"` muestra "⚠ error" en rojo; si `=== "ok"` el `<EstadoCicloBadge>` como hasta ahora.

## 3. Notas
- El sondeo y el resto del popup (prompt 34) no cambian; solo se añaden tokens y la traza.
- `actual` es `null` cuando el job termina; la traza solo se ve mientras hay un componente en curso.
```

- [ ] **Step 2: Añade la fila al README**

En `docs/lovable/README.md`, añade una fila para el prompt 35 (siguiendo el formato de las filas 33/34): número, fichero, descripción ("Pasos en vivo + tokens en el popup de refresco de obsolescencia").

- [ ] **Step 3: Commit**

```bash
git add docs/lovable/35_pasos_tokens_obsolescencia.md docs/lovable/README.md
git commit -m "docs(lovable): prompt 35 — pasos en vivo + tokens en el popup de obsolescencia"
```

---

## Verificación final (tras todas las tareas)

- [ ] Suite completa: `.venv/Scripts/python -m pytest tests/ -v` (toda verde; ⚠️ uvicorn parado).
- [ ] Sondeo real (opcional, consume tokens): con `ANTHROPIC_API_KEY` en `backend/.env`, arrancar backend, iniciar un refresco real de un banco pequeño y ver en el GET del job los `actual.pasos`, `tokens`/`tokens_total` y, forzando un `OBSOLESCENCIA_TIMEOUT_SEG=1`, que un componente sale `estado_consulta="timeout"`.
- [ ] Dispatch final code reviewer sobre todo el conjunto.
- [ ] superpowers:finishing-a-development-branch.
