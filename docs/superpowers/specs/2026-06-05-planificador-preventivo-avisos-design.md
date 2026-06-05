# Diseño — Planificador de preventivo + avisos

Fecha: 2026-06-05 · Proyecto: 6TL Postventa ("6tlservice") · Backend FastAPI :8020 + frontend Lovable.

## Contexto

Tras añadir contratos de mantenimiento y el registro de acciones de preventivo (`AccionPreventiva`, con
`proxima_fecha` sugerida por nivel), falta la cara proactiva: **saber qué toca y qué se ha pasado de fecha**.
Esta fase añade una **agenda calculada read-only** del preventivo por equipo y un **panel de avisos**
consolidado (preventivos vencidos/próximos + contratos por caducar). Sin entidad nueva, sin migración.

Es el sub-proyecto 1 de un clúster de 3 (los otros: SLA por nivel, y notificaciones email/Telegram), que se
diseñarán por separado. Este panel de avisos será la fuente de eventos que las notificaciones entregarán más
adelante.

## Decisiones (confirmadas con el usuario)
- Planificador = **agenda CALCULADA** (read-only), no entidad de visitas programadas.
- Equipos bajo contrato **nunca revisados** SÍ aparecen, calculando desde el inicio del contrato.
- Avisos incluyen **preventivo + contrato por caducar**.
- Próxima de un nunca-revisado = `contrato.fecha_inicio + cadencia_del_nivel` (no el día del alta).
- Umbrales: **preventivo 30 días**, **contrato por caducar 60 días** (constantes; configurables en fase futura).
- Un único endpoint **`GET /api/avisos`** consolidado.
- Pantalla nueva **`/avisos`** + badge; no se toca lo existente.

## Lógica de cálculo

Solo se consideran equipos con un contrato **vigente** (`equipo.bajo_contrato`). Cadencia en meses del nivel:
`contratos.NIVELES[nivel]["preventivo_meses"]` (bronze=12, silver=6, gold=6).

**Próxima fecha de preventivo de un equipo** (`proxima_fecha_equipo`):
- Si el equipo tiene ≥1 `AccionPreventiva`: tomar la **última por fecha**; `próxima = ultima.proxima_fecha`
  si está fijada; si no, `_add_months(ultima.fecha, cadencia)`.
- Si no tiene ninguna acción: `próxima = _add_months(contrato.fecha_inicio, cadencia)`.

**Clasificación** (`clasificar(proxima, hoy, umbral=30)`):
- `proxima < hoy` → `"vencido"`
- `hoy <= proxima <= hoy + umbral` → `"proximo"`
- en otro caso → `"al_dia"`

`dias_restantes = (proxima - hoy).days` (negativo si vencido).

**Contrato por caducar** (`contrato_por_caducar(contrato, hoy, umbral=60)`):
- `contrato.vigente` (estado == "vigente") **y** `fecha_fin <= hoy + umbral`.

## Componentes (backend)

### `app/avisos.py` — lógica pura (duck-typed, `hoy` inyectable; como `garantia.py`/`contratos.py`)
- `UMBRAL_PREVENTIVO_DIAS = 30`, `UMBRAL_CONTRATO_DIAS = 60`.
- `proxima_fecha_equipo(equipo, contrato, ultima_accion, hoy) -> date` — recibe la última acción (o None) y el
  contrato vigente; aplica las reglas de arriba. Reutiliza `contratos.NIVELES` + `garantia._add_months`.
- `clasificar(proxima, hoy, umbral=UMBRAL_PREVENTIVO_DIAS) -> str` (`vencido|proximo|al_dia`).
- `dias_restantes(fecha, hoy) -> int`.
- `contrato_por_caducar(contrato, hoy, umbral=UMBRAL_CONTRATO_DIAS) -> bool`.

### `app/avisos_service.py` — orquestación con BD
- `construir_avisos(db, hoy) -> dict`:
  - Consulta equipos con `contrato_id` no nulo cuyo contrato esté vigente. Para cada uno, busca su última
    `AccionPreventiva` (por `fecha` desc), calcula `proxima` y `bucket`. Descarta `al_dia`.
  - Consulta contratos vigentes que caducan dentro del umbral.
  - Devuelve el payload estructurado (ver schema). Ordena preventivos por `dias_restantes` asc.

### Endpoint
- `GET /api/avisos` (protegido con `get_current_user`). Sin parámetros (volúmenes pequeños; el frontend
  filtra por bucket). Usa `date.today()` como `hoy`.

## Schemas (Pydantic, salida)
```python
class AvisoPreventivo(BaseModel):
    equipo: EquipoOut
    contrato: ContratoResumen
    proxima_fecha: date
    dias_restantes: int
    bucket: Literal["vencido", "proximo"]
    ultima_fecha: Optional[date] = None

class AvisoContrato(BaseModel):
    contrato: ContratoResumen
    cliente: Optional[ClienteOut] = None
    fecha_fin: date
    dias_restantes: int

class ResumenAvisos(BaseModel):
    preventivos_vencidos: int
    preventivos_proximos: int
    contratos_por_caducar: int

class AvisosOut(BaseModel):
    preventivos: list[AvisoPreventivo] = []
    contratos_por_caducar: list[AvisoContrato] = []
    resumen: ResumenAvisos
```

## Frontend (Prompt Lovable 23)
- Pantalla **`/avisos`** (menú, con badge de contador = `resumen.preventivos_vencidos +
  resumen.contratos_por_caducar`): sección "Preventivos" (tabla vencido/próximo: equipo, contrato/nivel,
  próxima fecha, días, badge bucket vencido=rojo/próximo=ámbar; enlace a ficha + botón "Registrar preventivo")
  + sección "Contratos por caducar" (contrato, cliente, fecha fin, días). Filtro por bucket.
- Tipos `AvisoPreventivo`/`AvisoContrato`/`AvisosOut` en `@/lib/types`.
- No tocar lógica existente; solo consumir `GET /api/avisos`.

## Testing (TDD)
- Lógica pura (`test_avisos_logica.py`): clasificación 3 buckets con fechas absolutas; próxima desde última
  acción con `proxima_fecha` fijada; sin `proxima_fecha` → `fecha + cadencia`; nunca-revisado → `inicio +
  cadencia`; `dias_restantes` signo; `contrato_por_caducar` dentro/fuera de umbral y excluye no-vigentes.
- Servicio/API (`test_avisos_api.py`): equipo vencido aparece, equipo al-día no; equipo sin contrato vigente
  excluido; orden por `dias_restantes` asc; contadores del `resumen`; contrato por caducar listado; protegido → 401.

## Riesgos / notas
- ⚠️ Depende de `date.today()`; los tests fijan fechas absolutas o monkeypatch (precedente flaky por fecha en ATE).
- ⚠️ Parar uvicorn antes de la suite (siembra/abre `postventa.db`).
- Read-only: ningún cambio de estado, ninguna entidad ni migración nuevas.
- Umbrales fijos por ahora; si se piden configurables, va a una fase con `configuracion`.
