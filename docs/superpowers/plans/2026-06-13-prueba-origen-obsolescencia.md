# Prueba de origen (cita textual + URL verificada) y "no encontrado" — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que cada chequeo de obsolescencia aporte prueba real y original (cita textual copiada de la página + URL que el agente abrió de verdad), y que cuando no se encuentra muestre "No encontrado en la web del fabricante" sin tocar el estado del producto.

**Architecture:** El agente (Claude Code headless, streaming) devuelve ahora una `cita` literal. Un hallazgo solo cuenta si trae `estado` + `cita` no vacía + `url_fuente` verificada contra las URLs `WebFetch` realmente abiertas durante el stream. Si falta algo → `estado_consulta="no_encontrado"`, no se cambia el estado, y se sella `verificado_en` para no reintentar cada pasada. La cita se persiste en `Producto.ciclo_vida_cita` y `NoticiaObsolescencia.cita` y fluye hasta el report y el diálogo de refresco.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, Pydantic v2, SQLite, pytest. Frontend TanStack Start (prompt Lovable). Tests se ejecutan desde `backend/` con `.venv/Scripts/python -m pytest`.

**Repo root:** `C:\Users\rllavall\6TL Postventa` (el repo git está en la raíz, NO en `backend/`). Código en `backend/`. Rama de trabajo: `feat/prueba-origen-obsolescencia` (ya creada).

**⚠️ Aviso de entorno:** el seeder de ayuda toca `postventa.db` al importar la app; **parar uvicorn antes de correr tests**. Ejecutar siempre los comandos `pytest`/scripts desde el directorio `backend/`.

---

### Task 1: Columnas `ciclo_vida_cita` (productos) y `cita` (noticias)

**Files:**
- Modify: `backend/app/models.py:72` (Producto), `backend/app/models.py:391` (NoticiaObsolescencia)
- Modify: `backend/app/migrations.py:18-23` (productos), `backend/app/migrations.py:12` (añadir entrada noticias)
- Test: `backend/tests/test_migrations.py`, `backend/tests/test_obsolescencia_modelo.py`

- [ ] **Step 1: Write the failing migration test**

Añadir al final de `backend/tests/test_migrations.py`:

```python
def test_migracion_anade_cita_obsolescencia(tmp_path):
    from sqlalchemy import create_engine, text
    from app.migrations import add_missing_columns

    db = tmp_path / "old2.db"
    eng = create_engine(f"sqlite+pysqlite:///{db}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT)")
        conn.exec_driver_sql(
            "CREATE TABLE noticias_obsolescencia (id INTEGER PRIMARY KEY, producto_id INTEGER)")
    add_missing_columns(eng)
    with eng.connect() as conn:
        prod_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(productos)"))}
        not_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(noticias_obsolescencia)"))}
    assert "ciclo_vida_cita" in prod_cols
    assert "cita" in not_cols
    eng.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_migrations.py::test_migracion_anade_cita_obsolescencia -v`
Expected: FAIL — `assert "ciclo_vida_cita" in prod_cols` (la columna no existe aún).

- [ ] **Step 3: Add columns to migrations**

En `backend/app/migrations.py`, dentro de `_COLUMNAS_NUEVAS`, añadir `ciclo_vida_cita` a `productos` y una entrada nueva `noticias_obsolescencia`. El bloque `productos` pasa a terminar así:

```python
    "productos": {"meses_garantia_default": "INTEGER DEFAULT 24", "categoria": "TEXT",
                  "pn_fabricante": "TEXT", "fabricante_id": "INTEGER",
                  "categoria_componente": "TEXT",
                  "estado_ciclo_vida": "TEXT", "ciclo_vida_fecha": "DATE",
                  "ciclo_vida_url": "TEXT", "ciclo_vida_resumen": "TEXT",
                  "ciclo_vida_verificado_en": "DATE", "ciclo_vida_cita": "TEXT"},
    "fabricantes": {"url_obsolescencia": "TEXT"},
    "noticias_obsolescencia": {"cita": "TEXT"},
```

- [ ] **Step 4: Add columns to models**

En `backend/app/models.py`, tras la línea 72 (`ciclo_vida_verificado_en`) dentro de `class Producto`:

```python
    ciclo_vida_cita: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

En `class NoticiaObsolescencia`, tras `resumen` (línea 391):

```python
    cita: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- [ ] **Step 5: Write model persistence test**

Añadir a `backend/tests/test_obsolescencia_modelo.py`:

```python
def test_producto_y_noticia_persisten_cita(db_session):
    p = models.Producto(part_number="X-CITA", tipo="componente", descripcion="Demo",
                         fabricante="Acme", pn_fabricante="ACM-1")
    p.ciclo_vida_cita = "Status: Obsolete (Last Time Buy 2025-12-31)"
    db_session.add(p); db_session.commit(); db_session.refresh(p)
    assert p.ciclo_vida_cita.startswith("Status: Obsolete")
    n = models.NoticiaObsolescencia(
        producto_id=p.id, fecha_deteccion=date(2026, 6, 13),
        estado_anterior="activo", estado_nuevo="obsoleto",
        cita="Discontinued per PCN-001", notificado=False)
    db_session.add(n); db_session.commit(); db_session.refresh(n)
    assert n.cita == "Discontinued per PCN-001"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_migrations.py tests/test_obsolescencia_modelo.py -v`
Expected: PASS (incluidos los nuevos).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/migrations.py backend/tests/test_migrations.py backend/tests/test_obsolescencia_modelo.py
git commit -m "feat(obsolescencia): columnas ciclo_vida_cita y noticia.cita + migracion"
```

---

### Task 2: `_url_verificada` — verificación cruzada de URL

**Files:**
- Modify: `backend/run_obsolescencia.py` (añadir helpers tras `_descripcion_paso`, ~línea 62)
- Test: `backend/tests/test_consultar_fabricante.py`

- [ ] **Step 1: Write failing tests**

Añadir a `backend/tests/test_consultar_fabricante.py`:

```python
def test_normalizar_url_quita_esquema_www_barra_y_query():
    assert ro._normalizar_url("https://www.TI.com/product/MAX3232/") == "ti.com/product/max3232"
    assert ro._normalizar_url("http://ti.com/product/MAX3232?x=1") == "ti.com/product/max3232"
    assert ro._normalizar_url(None) == ""


def test_url_verificada_compara_contra_visitadas():
    visitadas = ["https://www.ti.com/product/MAX3232", "https://digikey.com/x"]
    assert ro._url_verificada("http://ti.com/product/max3232/", visitadas) is True
    assert ro._url_verificada("https://mouser.com/otra", visitadas) is False
    assert ro._url_verificada(None, visitadas) is False
    assert ro._url_verificada("https://ti.com/x", []) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_consultar_fabricante.py::test_url_verificada_compara_contra_visitadas -v`
Expected: FAIL — `AttributeError: module 'run_obsolescencia' has no attribute '_url_verificada'`.

- [ ] **Step 3: Implement the helpers**

En `backend/run_obsolescencia.py`, tras `_descripcion_paso` (antes de `_tokens_de_usage`):

```python
def _normalizar_url(u):
    """host+path en minúsculas, sin esquema, sin 'www.', sin barra final ni query."""
    if not u:
        return ""
    p = urlparse(u if "//" in u else "//" + u)
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (p.path or "").rstrip("/").lower()
    return host + path


def _url_verificada(url_fuente, urls_visitadas):
    """True si url_fuente coincide (host+path normalizado) con alguna URL que el
    agente abrió de verdad (WebFetch). Prueba de que la fuente no es inventada."""
    objetivo = _normalizar_url(url_fuente)
    if not objetivo:
        return False
    return any(_normalizar_url(u) == objetivo for u in urls_visitadas)
```

(`urlparse` ya está importado en la cabecera del módulo.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_consultar_fabricante.py -k "url" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/run_obsolescencia.py backend/tests/test_consultar_fabricante.py
git commit -m "feat(obsolescencia): helper _url_verificada (cruce con URLs WebFetch)"
```

---

### Task 3: `_procesar_stream` recolecta las URLs abiertas (WebFetch)

**Files:**
- Modify: `backend/run_obsolescencia.py:73-100` (`_procesar_stream`), `backend/run_obsolescencia.py:172` (unpack en `consultar_fabricante`)
- Test: `backend/tests/test_consultar_fabricante.py:38-54`

- [ ] **Step 1: Update the existing stream test to expect the 4-tuple + URLs**

Reemplazar la función `test_procesar_stream_emite_pasos_y_saca_tokens_y_texto` en `backend/tests/test_consultar_fabricante.py` por:

```python
def test_procesar_stream_emite_pasos_saca_tokens_texto_y_urls():
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
    texto, tokens, hubo, urls = ro._procesar_stream(iter(lineas), on_paso=lambda ev: pasos.append(ev["descripcion"]))
    assert hubo is True
    assert tokens == 4100  # input+output (4000+100); excluye cache_read (20000)
    assert "obsoleto" in texto
    assert pasos == ["🔎 Buscando: «MAX3232 lifecycle»", "🌐 Leyendo www.ti.com"]
    assert urls == ["https://www.ti.com/product/MAX3232"]  # solo WebFetch, no WebSearch
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_consultar_fabricante.py::test_procesar_stream_emite_pasos_saca_tokens_texto_y_urls -v`
Expected: FAIL — `ValueError: not enough values to unpack (expected 4, got 3)`.

- [ ] **Step 3: Implement — collect WebFetch URLs, return 4-tuple**

Reemplazar `_procesar_stream` en `backend/run_obsolescencia.py` por:

```python
def _procesar_stream(lineas, on_paso=None):
    """Consume líneas stream-json. Por cada tool_use de búsqueda llama on_paso y
    recolecta las URLs realmente abiertas (WebFetch). Devuelve
    (texto_result|None, tokens_total, hubo_result, urls_visitadas)."""
    texto = None
    tokens = 0
    urls = []
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
                if b.get("name") == "WebFetch":
                    u = (b.get("input") or {}).get("url")
                    if u:
                        urls.append(u)
                desc = _descripcion_paso(b.get("name"), b.get("input"))
                if desc and on_paso is not None:
                    try:
                        on_paso({"descripcion": desc})
                    except Exception:
                        pass
        elif tipo == "result":
            texto = ev.get("result")
            tokens = _tokens_de_usage(ev.get("usage"))
    return texto, tokens, (texto is not None), urls
```

- [ ] **Step 4: Update the unpack site in `consultar_fabricante`**

En `backend/run_obsolescencia.py`, dentro del `try` de `consultar_fabricante` (línea ~172), cambiar:

```python
        texto, tokens, _ = _procesar_stream(proc.stdout, on_paso)
```

por:

```python
        texto, tokens, _, urls_visitadas = _procesar_stream(proc.stdout, on_paso)
```

(El uso de `urls_visitadas` se cablea en la Task 4; de momento queda asignada.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_consultar_fabricante.py -v`
Expected: PASS de los tests de stream/url. (Los de `consultar_fabricante` OK porque siguen ignorando `urls_visitadas`; se endurecen en Task 4.)

- [ ] **Step 6: Commit**

```bash
git add backend/run_obsolescencia.py backend/tests/test_consultar_fabricante.py
git commit -m "feat(obsolescencia): _procesar_stream recolecta URLs WebFetch"
```

---

### Task 4: `cita` en el contrato del runner + gate (cita + url verificada → ok, si no → no_encontrado)

**Files:**
- Modify: `backend/run_obsolescencia.py` (`_parsear_estado` ~103-122, `_sin_estado` ~125-127, `consultar_fabricante` ~187-194)
- Test: `backend/tests/test_consultar_fabricante.py`

- [ ] **Step 1: Update existing consultar tests + add gate tests**

En `backend/tests/test_consultar_fabricante.py`:

(a) Reemplazar `test_consultar_fabricante_ok_devuelve_estado_y_tokens` por (ahora exige cita + WebFetch de la url citada):

```python
def test_consultar_fabricante_ok_exige_cita_y_url_verificada():
    lineas = [
        _linea_assistant("WebFetch", {"url": "http://beta/eol"}),
        _linea_result('{"estado":"nrnd","fecha_evento":null,"url_fuente":"http://beta/eol",'
                      '"resumen":"r","cita":"NRND as of 2025"}',
                      {"input_tokens": 1000, "output_tokens": 50}),
    ]
    pasos = []
    v = ro.consultar_fabricante(_Producto(), "http://beta", on_paso=lambda ev: pasos.append(ev["descripcion"]),
                                _popen=lambda: _FakeProc(lineas), _timer_factory=_TimerNulo)
    assert v["estado"] == "nrnd"
    assert v["estado_consulta"] == "ok"
    assert v["cita"] == "NRND as of 2025"
    assert v["tokens_total"] == 1050
    assert pasos == ["🌐 Leyendo beta"]
```

(b) Reemplazar `test_consultar_fabricante_sin_estado_es_sin_respuesta` por:

```python
def test_consultar_fabricante_sin_estado_es_no_encontrado():
    lineas = [_linea_result("no encontré nada concluyente", {"input_tokens": 500, "output_tokens": 10})]
    v = ro.consultar_fabricante(_Producto(), None, _popen=lambda: _FakeProc(lineas), _timer_factory=_TimerNulo)
    assert v["estado"] is None
    assert v["estado_consulta"] == "no_encontrado"
    assert v["cita"] is None
    assert v["tokens_total"] == 510
```

(c) Añadir dos tests nuevos del gate:

```python
def test_consultar_fabricante_estado_sin_cita_es_no_encontrado():
    lineas = [
        _linea_assistant("WebFetch", {"url": "http://beta/eol"}),
        _linea_result('{"estado":"obsoleto","url_fuente":"http://beta/eol","cita":null}',
                      {"input_tokens": 200, "output_tokens": 5}),
    ]
    v = ro.consultar_fabricante(_Producto(), None, _popen=lambda: _FakeProc(lineas), _timer_factory=_TimerNulo)
    assert v["estado"] is None
    assert v["estado_consulta"] == "no_encontrado"


def test_consultar_fabricante_url_no_visitada_es_no_encontrado():
    # cita presente y estado presente, pero la url_fuente NO fue abierta (WebFetch) -> sospechosa
    lineas = [
        _linea_assistant("WebSearch", {"query": "BET-1 EOL"}),
        _linea_result('{"estado":"obsoleto","url_fuente":"http://inventada/eol","cita":"EOL 2025"}',
                      {"input_tokens": 200, "output_tokens": 5}),
    ]
    v = ro.consultar_fabricante(_Producto(), None, _popen=lambda: _FakeProc(lineas), _timer_factory=_TimerNulo)
    assert v["estado"] is None
    assert v["estado_consulta"] == "no_encontrado"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_consultar_fabricante.py -v`
Expected: FAIL — `KeyError: 'cita'` y/o `estado_consulta == "sin_respuesta"` (el gate aún no existe).

- [ ] **Step 3: Implement — cita en parser/sin_estado + gate en consultar_fabricante**

(a) En `_parsear_estado`, el `return` final pasa a incluir `cita`:

```python
    return {
        "estado": data["estado"],
        "fecha_evento": date.fromisoformat(fe) if fe else None,
        "url_fuente": data.get("url_fuente"),
        "resumen": data.get("resumen"),
        "cita": data.get("cita"),
    }
```

(b) `_sin_estado` añade la clave `cita`:

```python
def _sin_estado(tokens, estado_consulta):
    return {"estado": None, "fecha_evento": None, "url_fuente": None, "resumen": None,
            "cita": None, "tokens_total": tokens, "estado_consulta": estado_consulta}
```

(c) En `consultar_fabricante`, reemplazar el bloque final (desde `if expirado["v"]:` hasta el `return` final) por:

```python
    if expirado["v"]:
        return _sin_estado(tokens, "timeout")
    hallazgo = _parsear_estado(texto)
    if (hallazgo and hallazgo.get("cita")
            and _url_verificada(hallazgo.get("url_fuente"), urls_visitadas)):
        hallazgo["tokens_total"] = tokens
        hallazgo["estado_consulta"] = "ok"
        return hallazgo
    return _sin_estado(tokens, "no_encontrado")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_consultar_fabricante.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add backend/run_obsolescencia.py backend/tests/test_consultar_fabricante.py
git commit -m "feat(obsolescencia): hallazgo exige cita + url verificada; si no -> no_encontrado"
```

---

### Task 5: `registrar_hallazgo` guarda `cita` + `marcar_revisado`

**Files:**
- Modify: `backend/app/obsolescencia_service.py:31-57` (`registrar_hallazgo`), añadir `marcar_revisado`
- Test: `backend/tests/test_obsolescencia_service.py`

- [ ] **Step 1: Write failing tests**

Añadir a `backend/tests/test_obsolescencia_service.py`:

```python
def test_registrar_hallazgo_guarda_cita_en_producto_y_noticia(db_session):
    p = _prod(db_session, "A")
    svc.registrar_hallazgo(db_session, p.id, "obsoleto", hoy=date(2026, 6, 13),
                           url="https://x", resumen="EOL", cita="Status: Obsolete")
    db_session.refresh(p)
    assert p.ciclo_vida_cita == "Status: Obsolete"
    n = db_session.query(models.NoticiaObsolescencia).filter_by(producto_id=p.id).one()
    assert n.cita == "Status: Obsolete"


def test_marcar_revisado_sella_fecha_sin_tocar_estado(db_session):
    p = _prod(db_session, "A", estado_ciclo_vida="nrnd",
              ciclo_vida_url="https://prev", ciclo_vida_cita="cita previa")
    ok = svc.marcar_revisado(db_session, p.id, date(2026, 6, 13))
    assert ok is True
    db_session.refresh(p)
    assert p.ciclo_vida_verificado_en == date(2026, 6, 13)
    assert p.estado_ciclo_vida == "nrnd"          # intacto
    assert p.ciclo_vida_url == "https://prev"     # intacto
    assert p.ciclo_vida_cita == "cita previa"     # intacta
    assert svc.marcar_revisado(db_session, 9999, date(2026, 6, 13)) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_service.py -k "cita or marcar_revisado" -v`
Expected: FAIL — `TypeError: registrar_hallazgo() got an unexpected keyword argument 'cita'` y `AttributeError: ... 'marcar_revisado'`.

- [ ] **Step 3: Implement**

En `backend/app/obsolescencia_service.py`, cambiar la firma y el cuerpo de `registrar_hallazgo`:

```python
def registrar_hallazgo(db: Session, producto_id: int, estado: str, *, hoy: date,
                       fecha_evento: date | None = None, url: str | None = None,
                       resumen: str | None = None, cita: str | None = None) -> dict:
    p = db.get(models.Producto, producto_id)
    if p is None:
        return {"registrado": False, "motivo": "no_existe", "cambio": False}
    if not obsolescencia.estado_valido(estado):
        return {"registrado": False, "motivo": "estado_invalido", "cambio": False}
    if obsolescencia.requiere_url(estado) and not url:
        return {"registrado": False, "motivo": "sin_url", "cambio": False}

    anterior = p.estado_ciclo_vida
    notable = obsolescencia.es_cambio_notable(anterior, estado)

    p.estado_ciclo_vida = estado
    p.ciclo_vida_fecha = fecha_evento
    p.ciclo_vida_url = url
    p.ciclo_vida_resumen = resumen
    p.ciclo_vida_cita = cita
    p.ciclo_vida_verificado_en = hoy

    if notable:
        db.add(models.NoticiaObsolescencia(
            producto_id=p.id, fecha_deteccion=hoy, estado_anterior=anterior,
            estado_nuevo=estado, fecha_evento=fecha_evento, url_fuente=url,
            resumen=resumen, cita=cita, notificado=False))
    db.commit()
    return {"registrado": True, "cambio": notable, "motivo": None}


def marcar_revisado(db: Session, producto_id: int, hoy: date) -> bool:
    """Sella que el producto se revisó hoy SIN hallazgo (no encontrado en la web),
    sin tocar estado/cita/url. Evita reintentarlo en cada pasada."""
    p = db.get(models.Producto, producto_id)
    if p is None:
        return False
    p.ciclo_vida_verificado_en = hoy
    db.commit()
    return True
```

- [ ] **Step 4: Cablear el run semanal (`ejecutar`/`main`) para pasar cita + sellar no_encontrado**

En `backend/run_obsolescencia.py`, reemplazar el cuerpo del bucle de `ejecutar` por:

```python
    prods = obsolescencia_service.productos_a_revisar(db, hoy, limite=limite)
    for p in prods:
        url = _url_fabricante(db, p)
        v = consultar(p, url)
        if v and v.get("estado"):
            obsolescencia_service.registrar_hallazgo(
                db, p.id, v["estado"], hoy=hoy, fecha_evento=v.get("fecha_evento"),
                url=v.get("url_fuente"), resumen=v.get("resumen"), cita=v.get("cita"))
        elif (v or {}).get("estado_consulta") == "no_encontrado":
            obsolescencia_service.marcar_revisado(db, p.id, hoy)
    return obsolescencia_service.enviar_informe(db, hoy, notificar_fn=notificar_fn)
```

Y en `main`, en la rama `--dry-run`, pasar también `cita=v.get("cita")` a `registrar_hallazgo`:

```python
                if v and v.get("estado"):
                    obsolescencia_service.registrar_hallazgo(
                        db, p.id, v["estado"], hoy=date.today(),
                        fecha_evento=v.get("fecha_evento"), url=v.get("url_fuente"),
                        resumen=v.get("resumen"), cita=v.get("cita"))
```

- [ ] **Step 5: Actualizar el test de contrato al nuevo valor canónico + spy de marcar_revisado**

En `backend/tests/test_run_obsolescencia_contrato.py`, en `test_ejecutar_no_registra_cuando_consultar_no_da_estado`:
- cambiar el `estado_consulta` del fake de `"sin_respuesta"` a `"no_encontrado"`,
- monkeypatchear `marcar_revisado` con un spy y asertar que SÍ se llama una vez:

```python
    def fake(p, url, **kw):
        return {"estado": None, "tokens_total": 500, "estado_consulta": "no_encontrado"}

    llamadas = []
    revisados = []
    monkeypatch.setattr(obsolescencia_service, "registrar_hallazgo",
                        lambda *a, **k: llamadas.append(a) or {"cambio": False})
    monkeypatch.setattr(obsolescencia_service, "marcar_revisado",
                        lambda *a, **k: revisados.append(a) or True)
    monkeypatch.setattr(obsolescencia_service, "productos_a_revisar",
                        lambda db, hoy, limite=20: db.query(models.Producto).all())
    monkeypatch.setattr(obsolescencia_service, "enviar_informe",
                        lambda *a, **k: {"enviado": False, "total": 0, "canales": []})

    ro.ejecutar(db_session, date(2026, 6, 13), consultar=fake,
                notificar_fn=lambda *a, **k: {"enviado": False, "canales": []})

    assert llamadas == []        # con estado=None el guard evita registrar_hallazgo
    assert len(revisados) == 1   # pero sí se sella verificado_en (no_encontrado)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_service.py tests/test_run_obsolescencia.py tests/test_run_obsolescencia_contrato.py -v`
Expected: PASS (todos, incluidos los previos).

- [ ] **Step 7: Commit**

```bash
git add backend/app/obsolescencia_service.py backend/run_obsolescencia.py backend/tests/test_obsolescencia_service.py backend/tests/test_run_obsolescencia_contrato.py
git commit -m "feat(obsolescencia): registrar_hallazgo persiste cita + marcar_revisado (banco y run semanal)"
```

---

### Task 6: Reescribir el prompt del agente (`cita` obligatoria, sin "activo por defecto")

**Files:**
- Modify: `backend/obsolescencia_prompt.md` (completo)
- Test: ninguno automático (es texto de prompt); verificación = relectura + smoke posterior

- [ ] **Step 1: Reescribir el prompt**

Reemplazar el contenido completo de `backend/obsolescencia_prompt.md` por:

```markdown
Eres un analista de obsolescencia de componentes electrónicos. Investiga el estado
de ciclo de vida del siguiente producto consultando la web del fabricante.

Fabricante: {fabricante}
Part number del fabricante: {pn}
Descripción: {descripcion}
Página PCN/EOL conocida: {url}

Pasos:
1. Si hay una URL conocida, ÁBRELA con WebFetch primero. Si no, busca en abierto
   "{fabricante} {pn} end of life / PCN / discontinued / obsolete" y ABRE (WebFetch)
   la página más fiable que encuentres.
2. Determina el estado de ciclo de vida actual del part number a partir de la página
   que has abierto.

Responde ÚNICAMENTE con un objeto JSON (sin texto alrededor) con esta forma:
{{"estado": "<activo|nrnd|eol_anunciado|ultima_compra|obsoleto o null>",
  "fecha_evento": "<YYYY-MM-DD o null>",
  "url_fuente": "<url EXACTA de la página que abriste con WebFetch, o null>",
  "cita": "<fragmento de texto COPIADO LITERALMENTE de esa página que respalda el
           estado, o null>",
  "resumen": "<una frase>"}}

Reglas (prueba de origen obligatoria):
- Para dar CUALQUIER estado debes incluir las dos cosas: "url_fuente" (una página que
  realmente abriste con WebFetch) y "cita" (texto copiado LITERAL de esa página, no
  parafraseado, tal cual aparece).
- La "url_fuente" debe ser una de las URLs que abriste con WebFetch. No cites una URL
  que solo viste en resultados de búsqueda sin abrirla.
- Si NO encuentras el part number en la web del fabricante o una fuente fiable, o no
  puedes copiar una cita literal, responde:
  {{"estado": null, "fecha_evento": null, "url_fuente": null, "cita": null,
    "resumen": "no encontrado en la web del fabricante"}}
- NO uses "activo" como valor por defecto cuando no encuentres datos. Sin cita = null.
- No inventes nada.
```

- [ ] **Step 2: Verify the template still formats (no stray braces)**

Run:
```bash
.venv/Scripts/python -c "from pathlib import Path; t=Path('obsolescencia_prompt.md').read_text(encoding='utf-8'); print(t.format(fabricante='TI', pn='MAX3232', descripcion='Cable', url='http://x')[:200])"
```
Expected: imprime el prompt con los valores sustituidos y SIN lanzar `KeyError`/`IndexError` (las llaves del JSON están escapadas como `{{`/`}}`).

- [ ] **Step 3: Commit**

```bash
git add backend/obsolescencia_prompt.md
git commit -m "feat(obsolescencia): prompt exige cita literal + url WebFetch, sin activo por defecto"
```

---

### Task 7: Cablear banco (`informe_banco` cita + `refrescar_banco` cita/marcar_revisado/estado_consulta) + schema componente

**Files:**
- Modify: `backend/app/obsolescencia_banco.py:47-62` (fila de `informe_banco`), `backend/app/obsolescencia_banco.py:139-151` (`refrescar_banco`)
- Modify: `backend/app/schemas.py:915-929` (`ObsolescenciaBancoComponenteOut`)
- Test: `backend/tests/test_obsolescencia_banco.py`

- [ ] **Step 1: Update existing test + add no_encontrado/cita test**

(a) En `backend/tests/test_obsolescencia_banco.py`, en `test_refrescar_banco_reemite_pasos_y_tokens`, cambiar el return del `fake` para P-OBS de `"sin_respuesta"` a `"no_encontrado"`, y la última aserción acorde:

```python
        return {"estado": None, "tokens_total": 99, "estado_consulta": "no_encontrado"}
```
y al final:
```python
    assert pobs["estado_consulta"] == "no_encontrado"
```

(b) Añadir test nuevo (cita propagada + marcar_revisado sella sin tocar estado):

```python
def test_refrescar_banco_propaga_cita_y_marca_revisado_si_no_encontrado(db_session):
    eq_id = _seed_banco(db_session)

    def fake(p, url, *, on_paso=None):
        if p.part_number == "P-ACT":
            return {"estado": "obsoleto", "fecha_evento": None, "url_fuente": "http://b/eol",
                    "resumen": "x", "cita": "EOL confirmado", "tokens_total": 10,
                    "estado_consulta": "ok"}
        # P-OBS: no encontrado -> no debe cambiar su estado, pero sí sellar verificado_en
        return {"estado": None, "cita": None, "tokens_total": 5,
                "estado_consulta": "no_encontrado"}

    ev = []
    obsolescencia_banco.refrescar_banco(
        db_session, eq_id, date(2026, 6, 14), limite=10, consultar=fake, on_progreso=ev.append)

    p_act = db_session.query(models.Producto).filter_by(part_number="P-ACT").one()
    assert p_act.ciclo_vida_cita == "EOL confirmado"
    p_obs = db_session.query(models.Producto).filter_by(part_number="P-OBS").one()
    assert p_obs.estado_ciclo_vida == "obsoleto"             # intacto (no se tocó)
    assert p_obs.ciclo_vida_verificado_en == date(2026, 6, 14)  # sellado
    r_act = next(e for e in ev if e["tipo"] == "resultado" and e["producto"].part_number == "P-ACT")
    assert r_act["cita"] == "EOL confirmado"
    r_obs = next(e for e in ev if e["tipo"] == "resultado" and e["producto"].part_number == "P-OBS")
    assert r_obs["estado_consulta"] == "no_encontrado"
    assert r_obs["cita"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py -v`
Expected: FAIL — el nuevo test falla (`KeyError: 'cita'` en el evento resultado, y `verificado_en` no sellado).

- [ ] **Step 3: Implement — fila con cita + wiring del refresco**

(a) En `informe_banco`, dentro del `filas.append({...})` (tras `"ciclo_vida_resumen": p.ciclo_vida_resumen,`):

```python
            "ciclo_vida_cita": p.ciclo_vida_cita,
```

(b) Reemplazar el cuerpo del bucle de `refrescar_banco` (desde `anterior = p.estado_ciclo_vida` hasta el `on_progreso(...)` del resultado) por:

```python
        anterior = p.estado_ciclo_vida
        try:
            v = consultar(p, _url_fabricante(db, p),
                          on_paso=_reemitir_paso(on_progreso, p, i, total))
        except Exception:
            v = None
        tokens = (v or {}).get("tokens_total", 0)
        estado_consulta = (v or {}).get("estado_consulta", "error")
        cita = (v or {}).get("cita")
        cambio = False
        if v and v.get("estado"):
            res = obsolescencia_service.registrar_hallazgo(
                db, p.id, v["estado"], hoy=hoy, fecha_evento=v.get("fecha_evento"),
                url=v.get("url_fuente"), resumen=v.get("resumen"), cita=cita)
            cambio = bool(res.get("cambio"))
            estado_consulta = "ok"
        elif estado_consulta == "no_encontrado":
            obsolescencia_service.marcar_revisado(db, p.id, hoy)
        if on_progreso is not None:
            on_progreso({"tipo": "resultado", "indice": i, "total": total, "producto": p,
                         "estado_anterior": anterior, "estado_nuevo": p.estado_ciclo_vida,
                         "cambio": cambio, "tokens": tokens, "cita": cita,
                         "estado_consulta": estado_consulta})
```

(c) En `backend/app/schemas.py`, `ObsolescenciaBancoComponenteOut`, tras `ciclo_vida_resumen` (línea 928):

```python
    ciclo_vida_cita: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_banco.py tests/test_obsolescencia_banco_router.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/obsolescencia_banco.py backend/app/schemas.py backend/tests/test_obsolescencia_banco.py
git commit -m "feat(obsolescencia): banco propaga cita y marca_revisado en no_encontrado"
```

---

### Task 8: Jobs propagan `cita` al item de resultado

**Files:**
- Modify: `backend/app/obsolescencia_jobs.py:64-74` (`_hacer_callback`, rama `resultado`)
- Test: `backend/tests/test_obsolescencia_jobs.py`

- [ ] **Step 1: Update the callback test to assert cita**

En `backend/tests/test_obsolescencia_jobs.py`, en `test_callback_acumula_pasos_y_tokens`, añadir `"cita": "EOL doc"` al evento `resultado` y asertar que se propaga:

```python
    cb({"tipo": "resultado", "indice": 1, "total": 2, "producto": p,
        "estado_anterior": "activo", "estado_nuevo": "obsoleto", "cambio": True,
        "tokens": 100, "estado_consulta": "ok", "cita": "EOL doc"})
    cb({"tipo": "actual", "indice": 2, "total": 2, "producto": p})
    snap2 = obsolescencia_jobs.snapshot(job_id)
    assert snap2["actual"]["pasos"] == []
    assert snap2["tokens_total"] == 100
    assert snap2["resultados"][0]["tokens"] == 100
    assert snap2["resultados"][0]["cita"] == "EOL doc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_jobs.py::test_callback_acumula_pasos_y_tokens -v`
Expected: FAIL — `KeyError: 'cita'`.

- [ ] **Step 3: Implement — add cita to the result item**

En `backend/app/obsolescencia_jobs.py`, en la rama `elif ev["tipo"] == "resultado":`, el `append` pasa a:

```python
                job["resultados"].append({
                    "part_number": p.part_number,
                    "descripcion": p.descripcion,
                    "estado_anterior": ev["estado_anterior"],
                    "estado_nuevo": ev["estado_nuevo"],
                    "cambio": ev["cambio"],
                    "tokens": ev.get("tokens", 0),
                    "cita": ev.get("cita"),
                    "estado_consulta": ev.get("estado_consulta", "ok"),
                })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_jobs.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/obsolescencia_jobs.py backend/tests/test_obsolescencia_jobs.py
git commit -m "feat(obsolescencia): job propaga cita al item de resultado"
```

---

### Task 9: `RefrescoResultadoItem.cita` (schema) + columna "Cita" en export

**Files:**
- Modify: `backend/app/schemas.py:959-966` (`RefrescoResultadoItem`)
- Modify: `backend/app/obsolescencia_export.py:8-20` (`_COLUMNAS`), `backend/app/obsolescencia_export.py:52` (usar `.get`)
- Test: `backend/tests/test_obsolescencia_schemas.py`, `backend/tests/test_obsolescencia_export.py`

- [ ] **Step 1: Write failing tests**

(a) En `backend/tests/test_obsolescencia_export.py`, añadir `"ciclo_vida_cita"` a ambos componentes del fixture `_informe()` (p.ej. `"ciclo_vida_cita": "Obsolete per PCN"` en P-OBS y `"ciclo_vida_cita": None` en P-ACT) y añadir un test:

```python
def test_a_xlsx_incluye_cita():
    inf = _informe()
    inf["componentes"][0]["ciclo_vida_cita"] = "Obsolete per PCN-001"
    inf["componentes"][1]["ciclo_vida_cita"] = None
    data = obsolescencia_export.a_xlsx(inf)
    sheet = zipfile.ZipFile(io.BytesIO(data)).read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Cita" in sheet                       # encabezado
    assert "Obsolete per PCN-001" in sheet       # valor
```

(b) En `backend/tests/test_obsolescencia_schemas.py`, comprobar el campo nuevo. Añadir:

```python
def test_refresco_resultado_item_acepta_cita():
    from app.schemas import RefrescoResultadoItem
    it = RefrescoResultadoItem(part_number="P", descripcion="d", cambio=False,
                               cita="EOL literal", estado_consulta="ok")
    assert it.cita == "EOL literal"
    it2 = RefrescoResultadoItem(part_number="P", descripcion="d", cambio=False)
    assert it2.cita is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_export.py tests/test_obsolescencia_schemas.py -v`
Expected: FAIL — `Cita` no está en el sheet y `RefrescoResultadoItem` no acepta `cita`.

- [ ] **Step 3: Implement**

(a) En `backend/app/schemas.py`, `RefrescoResultadoItem`, tras `tokens: int = 0`:

```python
    cita: Optional[str] = None
```

(b) En `backend/app/obsolescencia_export.py`, añadir la columna a `_COLUMNAS` tras `("ciclo_vida_resumen", "Resumen")`:

```python
    ("ciclo_vida_resumen", "Resumen"),
    ("ciclo_vida_cita", "Cita"),
```

(c) En `a_xlsx`, hacer el acceso tolerante a filas sin la clave: cambiar
`ws.append([_txt(fila[clave]) for clave, _ in _COLUMNAS])` por
`ws.append([_txt(fila.get(clave)) for clave, _ in _COLUMNAS])`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_obsolescencia_export.py tests/test_obsolescencia_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/app/obsolescencia_export.py backend/tests/test_obsolescencia_export.py backend/tests/test_obsolescencia_schemas.py
git commit -m "feat(obsolescencia): cita en RefrescoResultadoItem y columna Cita en export"
```

---

### Task 10: Full suite + prompt Lovable 36 (frontend)

**Files:**
- Create: `docs/lovable/36_cita_origen_obsolescencia.md`
- Modify: `docs/lovable/README.md` (añadir fila 36)
- Test: suite completa del backend

- [ ] **Step 1: Run the full backend suite (regresión)**

Run (parar uvicorn antes): `.venv/Scripts/python -m pytest -q`
Expected: PASS de toda la suite (los ~427 previos + los nuevos de Tasks 1-9). Si algo falla por defaults `estado_consulta` antiguos en otros tests, ajustarlo al nuevo contrato `no_encontrado`.

- [ ] **Step 2: Write the Lovable prompt 36**

Crear `docs/lovable/36_cita_origen_obsolescencia.md`:

```markdown
# Prompt 36 — Prueba de origen (cita textual) + "No encontrado" en obsolescencia

Contexto: app postventa 6TL (TanStack Start, rutas en `src/routes`, helper `api<T>()` en
`@/lib/api` (inyecta Bearer), tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`,
componentes `<EstadoCicloBadge estado url />` (prompt 32) y
`RefrescoObsolescenciaProgresoDialog` (prompts 34/35)). **NO cambies nombres de campo del
backend. No inventes endpoints ni campos fuera de los listados.** Todo va protegido.

El backend ahora aporta una **prueba de origen** por componente: una **cita textual**
copiada de la página del fabricante (`cita`) junto a la `url_fuente`. Un hallazgo solo se
registra si trae cita + URL verificada; si no, marca el componente como **no encontrado**.

## 1. Tipos en `src/lib/types.ts`
- `RefrescoResultadoItem` += `cita: string | null`.
- `ObsolescenciaBancoComponenteOut` (la fila de la tabla del report) += `ciclo_vida_cita: string | null`.
- La unión `estado_consulta` pasa a `"ok" | "no_encontrado" | "timeout" | "error"`
  (sustituye el antiguo `"sin_respuesta"`).

## 2. UI en `RefrescoObsolescenciaProgresoDialog` (log de resultados)
Por cada línea de resultado, según `estado_consulta`:
- `"ok"`: además del `<EstadoCicloBadge estado={r.estado_nuevo} />` y el chip de tokens,
  mostrar la **prueba**: la `cita` entre comillas en bloque citado (`blockquote`/borde
  izquierdo lila, texto pequeño) y, si hay `url_fuente` disponible en la fila del report,
  un enlace "Ver fuente" (`target="_blank"`). Si no hay cita, no romper.
- `"no_encontrado"`: en vez del badge, texto atenuado **"No encontrado en la web del
  fabricante"**.
- `"timeout"`: "⏱ sin respuesta (timeout)" en ámbar (como prompt 35).
- `"error"`: "⚠ error" en rojo.

## 3. Tabla del report por banco
En la columna/celda de estado de cada componente, cuando `ciclo_vida_cita` no es null,
mostrar un icono/tooltip (o fila expandible) con la **cita textual** + enlace a
`ciclo_vida_url`. Es la evidencia de que el estado es real, no inventado.

## 4. Notas
- El sondeo y el resto del popup (prompts 34/35) no cambian; solo se añade la cita y el
  nuevo valor `no_encontrado`.
- Endpoints sin cambios: `POST /api/equipos/{id}/obsolescencia/refrescar/iniciar?limite=10`,
  `GET /api/equipos/{id}/obsolescencia/refrescar/{job_id}` → `RefrescoProgreso`,
  `GET /api/equipos/{id}/obsolescencia` → report (componentes con `ciclo_vida_cita`).
```

- [ ] **Step 3: Add README row**

En `docs/lovable/README.md`, añadir una fila para el prompt 36 siguiendo el formato de la fila 35 (número, fichero, una línea de descripción: "Prueba de origen: cita textual + 'No encontrado en la web del fabricante'").

- [ ] **Step 4: Commit**

```bash
git add docs/lovable/36_cita_origen_obsolescencia.md docs/lovable/README.md
git commit -m "docs(lovable): prompt 36 cita de origen + no encontrado"
```

---

## Notas finales para el ejecutor

- Tras todas las tasks, dispatch de un **revisor holístico** (Opus) sobre el diff completo de la rama: foco en el gate de `consultar_fabricante` (orden cita/url/timeout), que `marcar_revisado` solo se llame en `no_encontrado` (no en `timeout`/`error`), y que ningún consumidor rompa por el cambio `sin_respuesta`→`no_encontrado`.
- Luego usar **superpowers:finishing-a-development-branch** (merge a master local + push, según pida el usuario).
- El prompt Lovable 36 NO se pega aquí; queda escrito para que el usuario lo pegue cuando quiera.
- Smoke real (opcional, requiere `ANTHROPIC_API_KEY`/Claude bin): refrescar el banco iUTB (equipo id 1) y verificar que aparecen citas en los resultados o "No encontrado".
```
