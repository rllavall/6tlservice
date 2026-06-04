# Resumen de servicio (KPIs cabecera "EN VIVO") — Diseño

**Fecha:** 2026-06-05
**Proyecto:** 6TL Postventa ("6tlservice")
**Estado:** diseño aprobado en brainstorming, pendiente de spec review + plan

## Problema / objetivo

La cabecera "Resumen de servicio · EN VIVO / Operaciones de postventa" muestra 4 KPIs. Los actuales
tienen problemas: **"SLA en riesgo"** promete un SLA que no existe en el modelo, y el resto no cubre el
set que el negocio quiere. Se redefine el set de 4 tarjetas y se añade un cálculo nuevo de tiempo.

Set de 4 tarjetas acordado:
1. **Incidencias abiertas** — todas las asistencias abiertas, **todos los tipos** (RMA, soporte venta,
   soporte técnico, calibración) y todas las familias (ATE, YAV, …).
2. **RMA abierto** — incidencias `tipo=rma` no cerradas.
3. **En reparación** — incidencias `estado=en_reparacion` (trabajos en curso).
4. **Tiempo medio de cierre** — media de `fecha_cierre − fecha_apertura` de las cerradas en los
   últimos 30 días (sustituye al "MTTR 30D", que medía apertura→resolución).

Se **elimina** la tarjeta "SLA en riesgo".

## Decisiones (brainstorming)

- **Tiempo de cierre sustituye al MTTR de la tarjeta**, ventana **30 días** (por `fecha_cierre`).
  El endpoint de analítica completa NO se toca (su `mttr_dias` apertura→resolución sigue igual).
- **Endpoint dedicado** `GET /api/analitica/resumen` con los 4 números (+ subtítulos), en vez de
  ampliar el payload grande de `/analitica/incidencias` o calcularlo en el front. Lógica en el módulo
  puro `analitica_incidencias.py`, `hoy` inyectable para tests.
- "abiertas" = `estado != "cerrada"` (coherente con el resto de la app).

## Backend

### Módulo `app/analitica_incidencias.py`
Nueva función pura:
```python
def resumen_servicio(db: Session, hoy: date) -> ResumenServicioOut:
    ...
```
- `incidencias_abiertas` = nº incidencias con `estado != "cerrada"` (cualquier tipo).
- `incidencias_abiertas_alta` = de las abiertas, las de `prioridad == "alta"`.
- `rma_abierto` = nº con `tipo == "rma"` y `estado != "cerrada"`.
- `en_reparacion` = nº con `estado == "en_reparacion"`.
- `cerradas_30d` = nº con `fecha_cierre` no nula y `fecha_cierre >= hoy - 30 días` (`hoy` incluido).
- `tiempo_medio_cierre_dias` = media de `(fecha_cierre - fecha_apertura).days` sobre ese mismo
  conjunto de cerradas-30d; `None` si no hay ninguna. Redondeo a 1 decimal (helper `_media` existente).

### Schema (`app/schemas.py`)
```python
class ResumenServicioOut(BaseModel):
    incidencias_abiertas: int
    incidencias_abiertas_alta: int
    rma_abierto: int
    en_reparacion: int
    cerradas_30d: int
    tiempo_medio_cierre_dias: Optional[float] = None
```

### Router (`app/routers/analitica.py`)
```python
@router.get("/resumen", response_model=ResumenServicioOut)
def resumen(db: Session = Depends(get_db)) -> ResumenServicioOut:
    return ana.resumen_servicio(db, hoy=date.today())
```
(Sin filtros: es la foto "en vivo" global.)

## Frontend (Lovable, prompt 16)

- La cabecera "Resumen de servicio · EN VIVO" llama `GET /api/analitica/resumen` y pinta 4 tarjetas:
  1. **Incidencias abiertas** = `incidencias_abiertas`; subtítulo "{incidencias_abiertas_alta} de alta prioridad".
  2. **RMA abierto** = `rma_abierto`; subtítulo "sin cerrar".
  3. **En reparación** = `en_reparacion`; subtítulo "trabajos en curso".
  4. **Tiempo medio de cierre** = `tiempo_medio_cierre_dias` (días, "—" si null); subtítulo
     "{cerradas_30d} cerradas · 30d".
- **Eliminar** la tarjeta "SLA en riesgo". El enlace "Ver analítica completa →" se mantiene.
- Tipo `ResumenServicio` en `types.ts` espejo del schema.

## Testing (TDD)

- `resumen_servicio` con dataset semilla controlado (`hoy` fijo): cuenta abiertas (varios tipos),
  abiertas de alta, rma abierto (tipo+estado), en reparación; tiempo medio de cierre solo de las
  cerradas dentro de los 30 días (una cerrada hace 40 días debe quedar EXCLUIDA), media correcta;
  `cerradas_30d` correcto.
- Caso vacío: BD sin incidencias → todos 0, `tiempo_medio_cierre_dias` null.
- Endpoint `GET /api/analitica/resumen`: 200 con la forma esperada; BD vacía → ceros/null.

## Fuera de alcance (YAGNI)

- Cambiar el MTTR (apertura→resolución) de la pantalla de analítica completa.
- SLA configurable por prioridad / "% en plazo".
- Subtítulos extra (p.ej. RMA abierto en garantía), filtros por cliente en el resumen.
