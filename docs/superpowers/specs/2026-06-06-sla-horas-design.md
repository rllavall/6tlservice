# Diseño — SLA en horas (marcas de tiempo de evento)

Fecha: 2026-06-06 · Proyecto: 6TL Postventa ("6tlservice").

## Contexto

El SLA actual (`app/sla.py`) mide en **días** porque las fechas de incidencia son `Date`. El usuario necesita
precisión de **horas**. Enfoque elegido (aprobado): **añadir marcas de tiempo de evento** puestas por el
servidor (no migrar los `fecha_*` existentes). Las `fecha_*` (editables, usadas por analítica) se quedan; el
SLA gana precisión horaria con timestamps reales y, para datos antiguos, cae a la fecha a medianoche.

## Objetivos de SLA (horas, confirmados con el usuario)

| nivel  | respuesta_horas | resolucion_horas |
|--------|-----------------|------------------|
| gold   | 2               | 24               |
| silver | 4               | 48               |
| bronze | 8               | 168 (1 semana)   |

## Marcas de tiempo (modelo + transiciones)

`Incidencia` gana 3 columnas `DateTime` nullable:
- `creada_en` — `mapped_column(DateTime, default=datetime.now, nullable=True)`. Se rellena sola en CUALQUIER
  alta (default ORM), sin tocar endpoints de creación. Filas históricas = NULL.
- `respondida_en` — se fija en `incidencias_service.transicionar` la **primera** vez que la incidencia pasa a
  `diagnostico` o `en_reparacion` (si está vacía). No se borra al reabrir.
- `resuelta_en` — se fija al pasar a `resuelta`; se **borra** al reabrir (igual que `fecha_resolucion`).

Migración: añadir las 3 columnas a `incidencias` en `migrations.py` (tipo SQL `DATETIME`).

## Cálculo del SLA (horas)

**Anclaje día+hora** (`_combinar(dia, preciso)` en `app/sla.py`): devuelve `datetime.combine(dia,
preciso.time())` si `preciso` no es None, si no `datetime.combine(dia, time.min)` (medianoche). Es decir: **el
DÍA siempre sale de la fecha autoritativa** (`fecha_*`), y la **hora** se toma de la marca de evento cuando
existe. Así una incidencia con `fecha_apertura` retroactiva sigue contando desde ese día (no desde `creada_en`),
y los tests con fechas absolutas siguen siendo válidos.

`evaluar(incidencia, nivel, ahora: datetime)`:
- `inicio = _combinar(fecha_apertura, creada_en)`.
- `resp_real = _combinar(_primera(fecha_diagnostico, fecha_inicio_reparacion, fecha_resolucion), respondida_en)`
  o None si no hay ninguna de esas fechas.
- `reso_real = _combinar(_primera(fecha_resolucion, fecha_cierre), resuelta_en)` o None.
- `respuesta = estado_metrica(inicio, resp_real, respuesta_horas, ahora)`;
  `resolucion = estado_metrica(inicio, reso_real, resolucion_horas, ahora)`.
- `estado_global = peor(respuesta.estado, resolucion.estado)`.

`estado_metrica(inicio, real, objetivo_horas, ahora) -> dict`:
- `objetivo = inicio + timedelta(hours=objetivo_horas)`.
- Cumplida (`real` no None): `en_plazo` si `real <= objetivo`, si no `incumplido`.
- Pendiente: `incumplido` si `ahora > objetivo`; `en_riesgo` si `horas_restantes <= max(1,
  ceil(objetivo_horas * 0.25))`; si no `en_plazo`.
- `horas_restantes = None` si cumplida; si no `int((objetivo - ahora).total_seconds() // 3600)` (negativo si
  pasado).
- Devuelve `{objetivo (datetime), real (datetime|None), horas_restantes, estado}`.

## Schemas (cambios)
- `SlaMetrica`: `objetivo: datetime`, `real: Optional[datetime]`, `horas_restantes: Optional[int]`,
  `estado: _ESTADO_SLA`. (Sustituye a `objetivo_fecha`/`fecha_real`/`dias_restantes`.)
- `SlaIncidencia`, `SlaIncidenciaItem`, `SlaOut` igual (estructura). El sort de `construir_sla` pasa a
  `resolucion.horas_restantes`.
- `IncidenciaOut` gana `creada_en/respondida_en/resuelta_en: Optional[datetime] = None` (visibilidad).

## Servicio
- `sla_service`: pasa `ahora = datetime.now()`; `sla_de_incidencia`/`construir_sla` sin cambios de forma salvo
  el campo de orden (`horas_restantes`). `cumplimiento` igual (% en_plazo).

## Frontend (Prompt Lovable 24 — actualizar)
- El panel SLA muestra `objetivo` (fecha+hora), `horas_restantes` y el badge. Las tarjetas de cumplimiento
  igual. Texto: plazos en horas.

## Testing (TDD, reescribir SLA)
- `test_sla_logica.py`: `SLA_NIVELES` en horas; `_combinar` (con/sin preciso); `estado_metrica` en horas
  (cumplida en plazo/tarde, pendiente en riesgo/incumplido/en plazo) con `datetime` absolutos; `evaluar` toma
  el día de `fecha_apertura` y la hora de `creada_en`.
- `test_sla_service.py`: incidencia con apertura muy pasada → incumplida; sin contrato → sin_sla; cumplimiento.
- `test_sla_api.py`: `IncidenciaFicha.sla` con `objetivo`/`horas_restantes`; endpoint incumplida; 401.
- `test_incidencias` (nuevo o ampliado): `creada_en` se rellena sola; `respondida_en` al pasar a diagnóstico;
  `resuelta_en` al resolver y se borra al reabrir.
- Migración: columnas nuevas en `incidencias`.

## Riesgos / notas
- ⚠️ `datetime.now()` no determinista → tests pasan `ahora` explícito o usan marcas absolutas.
- El DÍA del SLA siempre viene de `fecha_*` (autoritativo); la marca de evento solo aporta la hora → respeta
  fechas retroactivas y no rompe tests de fechas absolutas.
- Históricos (sin marcas) = precisión de día (medianoche). Nuevos = precisión de hora.
- Sin cambios en el contrato de creación/transición de la API (los `fecha_*` siguen siendo `date`).
