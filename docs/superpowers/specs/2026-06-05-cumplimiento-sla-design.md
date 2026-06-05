# Diseño — Cumplimiento de SLA por nivel de contrato

Fecha: 2026-06-05 · Proyecto: 6TL Postventa ("6tlservice") · Backend FastAPI :8020 + frontend Lovable.

> **Nota:** diseñado e implementado de forma autónoma (usuario ausente, autorización explícita "no hace falta
> mi aprobación"). Las decisiones de diseño tomadas por defecto están marcadas y son fácilmente ajustables
> (objetivos de SLA en una sola tabla de constantes).

## Contexto

Los contratos tienen nivel Bronze/Silver/Gold; la propuesta iUTB INDRA promete distinto **tiempo de respuesta
y de resolución** por nivel. Esta fase mide cada incidencia (de un equipo bajo contrato vigente) contra el SLA
de su nivel y marca `en_plazo / en_riesgo / incumplido`. Es el sub-proyecto **3 de 3** del clúster de servicio
(tras #1 preventivo+avisos; queda #2 notificaciones, que entregará estos eventos).

## Decisiones de diseño (por defecto, ajustables)

- **Granularidad = días.** Las fechas de incidencia son `Date` (no datetime), así que el SLA se mide en días
  naturales. Esto elimina la complejidad de "horas hábiles vs 24/7"; si se requiere granularidad horaria habría
  que migrar las fechas a datetime (fase futura).
- **Objetivos por nivel** (`SLA_NIVELES`, constantes en código, editables en fase futura vía `configuracion`):
  | nivel  | respuesta_dias | resolucion_dias |
  |--------|----------------|-----------------|
  | gold   | 1              | 5               |
  | silver | 2              | 10              |
  | bronze | 3              | 15              |
- **Mapeo de hitos:**
  - *Respuesta:* `fecha_apertura` → primera de (`fecha_diagnostico`, `fecha_inicio_reparacion`,
    `fecha_resolucion`) que esté fijada (= primera intervención registrada).
  - *Resolución:* `fecha_apertura` → primera de (`fecha_resolucion`, `fecha_cierre`).
- **Sólo incidencias de equipos con contrato vigente.** El nivel sale del contrato del equipo. Sin contrato
  vigente (o incidencia sin equipo) → `sin_sla` (no se mide).

## Lógica de evaluación (por métrica: respuesta y resolución)

Dado `objetivo = fecha_apertura + objetivo_dias` y `hoy`:
- **Cumplida** (hay fecha real): `en_plazo` si `fecha_real <= objetivo`, si no `incumplido`.
- **Pendiente** (sin fecha real): `incumplido` si `hoy > objetivo`; `en_riesgo` si
  `dias_restantes <= max(1, ceil(objetivo_dias * 0.25))`; si no `en_plazo`.
- `dias_restantes = (objetivo - hoy).days`.

**Estado global de la incidencia** = el peor de respuesta y resolución (orden:
`incumplido > en_riesgo > en_plazo`). Si no hay SLA → `sin_sla`.

## Componentes (backend)

### `app/sla.py` — lógica pura (duck-typed, `hoy` inyectable)
- `SLA_NIVELES: dict[nivel, {"respuesta_dias", "resolucion_dias"}]`.
- `_primera(*fechas) -> Optional[date]` (primera no-None).
- `estado_metrica(apertura, fecha_real, objetivo_dias, hoy) -> dict`:
  `{objetivo_fecha, fecha_real, dias_restantes, estado}`.
- `evaluar(incidencia, nivel, hoy) -> dict`: usa los hitos mapeados; devuelve
  `{nivel, respuesta:{...}, resolucion:{...}, global: estado}`. Reutiliza `garantia._add_months`? No: aquí se
  suma en días (`apertura + timedelta(days=objetivo_dias)`).
- `peor(*estados) -> str`.

### `app/sla_service.py` — orquestación con BD
- `sla_de_incidencia(db, incidencia, hoy) -> Optional[dict]`: localiza el equipo de la incidencia y su contrato
  vigente; si no hay → None (`sin_sla`). Si hay, `sla.evaluar(...)`.
- `construir_sla(db, hoy) -> dict`: recorre incidencias **abiertas** (estado != cerrada/resuelta) de equipos con
  contrato vigente; clasifica; devuelve `{cumplimiento:{respuesta_pct, resolucion_pct, total}, en_riesgo:[...],
  incumplidas:[...], resumen:{en_riesgo, incumplidas}}`. `cumplimiento` se calcula sobre **todas** las
  incidencias con SLA (abiertas + cerradas) del histórico: % cuya métrica quedó `en_plazo`.

### Endpoints
- `GET /api/sla` (protegido) → resumen de cumplimiento + listas de incidencias en riesgo / incumplidas
  (cada item: incidencia resumida + su `SlaIncidencia`). Ordenadas por gravedad/dias_restantes.
- **Expediente de incidencia**: `IncidenciaFicha` gana `sla: Optional[SlaIncidencia]` (calculado en vivo en el
  builder de la ficha, `incidencias.py`).

## Schemas (Pydantic, salida)
```python
_ESTADO_SLA = Literal["en_plazo", "en_riesgo", "incumplido", "sin_sla"]

class SlaMetrica(BaseModel):
    objetivo_fecha: date
    fecha_real: Optional[date] = None
    dias_restantes: int
    estado: _ESTADO_SLA

class SlaIncidencia(BaseModel):
    nivel: str
    respuesta: SlaMetrica
    resolucion: SlaMetrica
    estado_global: _ESTADO_SLA

class SlaIncidenciaItem(_ORM):
    incidencia: IncidenciaOut
    sla: SlaIncidencia

class CumplimientoSla(BaseModel):
    total: int
    respuesta_pct: Optional[float] = None
    resolucion_pct: Optional[float] = None

class SlaOut(BaseModel):
    cumplimiento: CumplimientoSla
    en_riesgo: list[SlaIncidenciaItem] = []
    incumplidas: list[SlaIncidenciaItem] = []
    resumen: dict   # {"en_riesgo": int, "incumplidas": int}
```
(En `IncidenciaFicha` se añade `sla: Optional[SlaIncidencia] = None`.)

## Frontend (Prompt Lovable 24)
- En el **expediente de incidencia**: panel "SLA" con nivel, respuesta y resolución (objetivo, días restantes,
  badge de estado: en_plazo=verde, en_riesgo=ámbar, incumplido=rojo, sin_sla=gris).
- En la **lista de incidencias**: columna/badge de `estado_global` de SLA (si se expone ahí; opcional).
- Pantalla o sección **SLA** (`/sla` o dentro de analítica): tarjetas de cumplimiento (% respuesta / %
  resolución / total) + tablas de "en riesgo" e "incumplidas" con enlace a la incidencia.
- Tipos `SlaMetrica/SlaIncidencia/SlaOut` en `@/lib/types`.

## Testing (TDD)
- Pura (`test_sla_logica.py`): objetivos por nivel; `estado_metrica` en los 3 estados (cumplida en plazo / tarde
  / pendiente en riesgo / pendiente incumplido); `peor`; mapeo de hitos (primera fecha no-None).
- Servicio/API (`test_sla_service.py`, `test_sla_api.py`): incidencia de equipo bajo contrato con respuesta
  tardía → incumplido; incidencia sin contrato → sin_sla (no entra en listas); cumplimiento % sobre histórico;
  `IncidenciaFicha.sla` en vivo; protegido → 401.

## Riesgos / notas
- ⚠️ Depende de `date.today()`; tests con fechas absolutas.
- Granularidad en días: una incidencia abierta y resuelta el mismo día = 0 días (en plazo).
- Objetivos por defecto inventados (no venían numéricos en el PDF); el usuario los ajustará. Una sola tabla.
- No se modifica el endpoint de avisos en esta fase (SLA tiene su propio `GET /api/sla`); la consolidación SLA→
  avisos, si se quiere, es un follow-up trivial.
