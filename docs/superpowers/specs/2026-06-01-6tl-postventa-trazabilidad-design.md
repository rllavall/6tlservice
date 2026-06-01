# 6TL Postventa — Sub-proyecto 1: Trazabilidad + Base instalada

**Fecha:** 2026-06-01
**Estado:** Diseño aprobado
**Empresa:** 6TL — fabricación y comercialización de sistemas de test para electrónica (ATE)

## Contexto y objetivo global

6TL necesita una plataforma para **gestionar y controlar la postventa** de los sistemas de test que
suministra. La visión completa abarca seis subsistemas que se apoyan en una columna vertebral común:

- **Trazabilidad** de componentes en los sistemas suministrados, a nivel part number + número de serie.
- **Localización** del equipo (puede estar en distintas fábricas del mundo).
- **RMA** (devoluciones / reparaciones).
- **Garantías**.
- **Historial de incidencias**.
- **Soporte técnico**.

Más capacidades identificadas en brainstorming para fases futuras: calibración y mantenimiento
preventivo (muy relevante en ATE), versiones de firmware/SW, análisis de fiabilidad por componente
(detección de lote defectuoso, MTBF), repuestos/spare parts, contratos de servicio/SLA, field service,
costes y facturación de reparaciones fuera de garantía, base de conocimiento, portal de cliente,
dashboard de KPIs, gestión documental, notificaciones/alertas, e integración con ERP/Quotify/6TL
Production System.

### Decomposición

La plataforma se construye por sub-proyectos, cada uno con su ciclo spec → plan → implementación. La
columna vertebral (trazabilidad + localización) es el **sub-proyecto 1** y la base sobre la que cuelgan
los demás. **Este documento cubre únicamente el sub-proyecto 1.**

### Decisiones de alcance (MVP, sub-proyecto 1)

- **Origen del dato:** lo introduce 6TL a mano. La app es la fuente de verdad. Cero integraciones en v1.
- **Granularidad:** solo se serializan componentes/módulos clave (instrumentos, tarjetas, PC, fuentes…).
  El equipo tiene serie propia; cuelgan de él los componentes clave serializados. Modelo de dos niveles.
- **Usuarios:** solo equipo interno de 6TL (postventa, soporte, producción). Login simple, sin portal externo.
- **Alcance v1:** solo la columna vertebral — equipos + componentes serializados + ubicación (base instalada).
  RMA, garantías, incidencias y soporte son fases posteriores.
- **Específico ATE:** la configuración de instrumentos de un equipo **cambia con el tiempo** (sustituciones,
  upgrades, retiradas) y debe trazarse con historial.

## Arquitectura

- **Backend:** FastAPI + SQLAlchemy + SQLite (patrón ATE/Quotify). Modelos, esquemas Pydantic, routers por
  entidad, y una capa de **servicio** para la lógica de los dos logs (ubicación y configuración).
- **Frontend:** Lovable / React (Vite + TS + Tailwind + shadcn).
- **Puerto backend:** **:8020** (evita choque con :8000 ATE/Quotify y :8010 dashboard).

## Modelo de datos

El principio de diseño: las consultas transversales son el valor de la trazabilidad ("¿dónde está la serie
X?", "¿qué equipos llevan el part number Y?", "¿por dónde ha pasado este equipo?", "¿qué llevaba en la
fecha Z?"). El modelo se elige para que esas consultas sean naturales. Se eligió el enfoque
**catálogo + instancias + logs de eventos** frente a un modelo plano (pierde historial y consistencia) o
un documento JSON anidado (mata las consultas transversales).

### 1. `Ubicacion`
Dónde puede estar un equipo.
```
id, nombre, tipo (fabrica_cliente | sede_6tl | en_reparacion | en_transito),
empresa_cliente, pais, ciudad, notas
```

### 2. `Producto` (catálogo / part number)
Define cada *modelo* una sola vez. Evita part numbers sueltos mal escritos.
```
id, part_number (único), tipo (equipo | componente),
descripcion, fabricante, modelo, notas
```
`tipo` distingue si el part number es un equipo entregable o un componente serializable.

### 3. `Equipo` (instancia entregada)
Un sistema físico con su número de serie.
```
id, numero_serie, producto_id → Producto(tipo=equipo),
cliente, fecha_fabricacion, fecha_entrega, estado (operativo | baja), notas
```
La **ubicación actual NO se guarda como campo**: se deriva del último `Movimiento`.

### 4. `Componente` (instancia serializada)
Módulo clave. Los campos `equipo_id`/`posicion` representan el **estado actual** (cacheado), mantenido por
los eventos de configuración.
```
id, numero_serie, producto_id → Producto(tipo=componente),
equipo_id → Equipo (nullable: suelto/repuesto), posicion (texto libre, p.ej. "PXI ranura 3"),
fecha_montaje, notas
```

### 5. `Movimiento` (evento de ubicación)
Historial de localización a nivel de equipo.
```
id, equipo_id → Equipo, ubicacion_destino_id → Ubicacion,
fecha, motivo (entrega | traslado | reparacion | devolucion), usuario, notas
```
**Ubicación actual del equipo = movimiento más reciente.** El origen es implícito (ubicación del movimiento
anterior).

### 6. `CambioConfiguracion` (evento de configuración)
Historial de montajes/desmontajes de componentes — específico de ATE.
```
id, componente_id → Componente, equipo_id → Equipo,
accion (montaje | desmontaje), posicion,
fecha, motivo (entrega_inicial | sustitucion | upgrade | reparacion | retirada), usuario, notas
```

### Reglas del modelo
- **Ubicación a nivel de equipo.** Los componentes heredan la ubicación del equipo donde están montados.
  Un componente suelto (sin `equipo_id`) se considera en sede 6TL.
- **Unicidad de serie = `(producto_id, numero_serie)`** juntos (dos fabricantes pueden repetir serie; el
  part number desambigua).
- **Dos logs simétricos:** `Movimiento` (dónde está) y `CambioConfiguracion` (qué lleva).
- **Estado actual cacheado** en `Equipo` (vía último movimiento, derivado) y `Componente` (`equipo_id`/
  `posicion`); los logs son la fuente del historial. El servicio actualiza estado y log en la misma operación.

### Comportamiento de los logs
- **Montar** componente en equipo → evento `montaje` + fija `Componente.equipo_id`/`posicion`.
- **Desmontar** → evento `desmontaje` + `Componente.equipo_id = null`.
- **Sustituir** una tarjeta = `desmontaje` del saliente + `montaje` del entrante, **atómico**.
- **Configuración actual** de un equipo = componentes con `equipo_id` apuntando a él.
- **Historial de configuración** = `CambioConfiguracion` del equipo ordenados por fecha; reconstruye
  "qué llevaba el equipo en la fecha X".

## API (FastAPI)

### CRUD básico
- `…/ubicaciones` — GET, POST, PUT, DELETE
- `…/productos` — GET (filtro `?tipo=equipo|componente`), POST, PUT, DELETE
- `…/equipos` — GET (lista base instalada con filtros), POST, PUT
- `…/componentes` — GET, POST, PUT

### Ficha y consultas transversales
- `GET /api/equipos/{id}` — ficha completa: cabecera + componentes actuales + ubicación actual +
  historial de movimientos + historial de configuración.
- `GET /api/buscar?serie=XXXX` — búsqueda global por nº de serie → devuelve el equipo o el componente
  (y en qué equipo está montado). La consulta estrella.
- `GET /api/equipos?producto_id=…` / `?part_number=…` — qué equipos llevan un part number (vía componentes).
- `GET /api/ubicaciones/{id}/equipos` — qué equipos hay ahora en una ubicación.

### Acciones (capa de servicio, lógica de los dos logs)
- `POST /api/equipos/{id}/movimientos` — registra traslado (crea `Movimiento`).
- `POST /api/componentes/{id}/montar` — `{equipo_id, posicion, fecha, motivo}` → `montaje` + estado.
- `POST /api/componentes/{id}/desmontar` — `{fecha, motivo}` → `desmontaje` + libera.
- `POST /api/equipos/{id}/sustituir-componente` —
  `{componente_saliente_id, componente_entrante_id, posicion, fecha, motivo}` → desmontaje + montaje atómicos.

### Validaciones
- Unicidad `(producto_id, numero_serie)`.
- Un `Producto` tipo=equipo no puede montarse como componente y viceversa.
- No montar un componente ya montado sin desmontarlo antes.
- No borrar un `Producto`/`Ubicacion` en uso (referenciado).

## Frontend (Lovable / React)

Navegación lateral sencilla (app interna). Cinco pantallas:

1. **Base instalada (home)** — tabla de equipos; buscador global por nº de serie/part number prominente
   arriba; filtros (ubicación, modelo, estado). Fila → ficha.
2. **Ficha de equipo** — pantalla central:
   - Cabecera: nº serie, modelo, cliente, ubicación actual (badge), estado.
   - Configuración actual: tabla de componentes montados (serie, part number, posición). Acciones
     *Montar* / *Desmontar* / *Sustituir* (en modales).
   - Historial de ubicación: línea de tiempo + botón *Registrar movimiento* (modal).
   - Historial de configuración: línea de tiempo de montajes/desmontajes.
3. **Alta/edición de equipo** — datos + modelo del catálogo + componentes serializados iniciales.
4. **Catálogo (part numbers)** — CRUD de productos, filtrable por tipo.
5. **Ubicaciones** — CRUD de fábricas/sedes.

UX: las acciones de montar/desmontar/sustituir/mover van en **modales** desde la ficha (siempre en el
contexto de un equipo). El buscador global por serie es lo más prominente.

## Testing y calidad

**Backend (pytest, TDD):**
- Validaciones: unicidad `(producto_id, numero_serie)`; tipo equipo≠componente; no montar ya montado;
  no borrar producto/ubicación en uso.
- Lógica de los dos logs:
  - Ubicación actual = último `Movimiento`; cero movimientos → sede 6TL por defecto.
  - Montar → componente en config actual + evento en historial.
  - Desmontar → fuera de config actual, evento permanece.
  - Sustituir → saliente desmontado + entrante montado, ambos eventos, atómico (rollback si falla uno).
  - Historial de configuración reconstruye "qué llevaba el equipo en fecha X".
- Consultas transversales: buscar por serie (equipo o componente + su equipo); equipos por part number;
  equipos por ubicación.

**Frontend (Lovable):** validación visual + verificación del contrato API (nombres de campos); cuidado con
falsos errores CORS, 500 silenciosos, desajustes de nombre de campo, re-import duplicado.

## Fuera de alcance (fases posteriores)
RMA, garantías, incidencias, soporte técnico, calibración/mantenimiento preventivo, firmware/versiones,
análisis de fiabilidad/MTBF, repuestos, SLA, field service, costes/facturación, base de conocimiento,
portal de cliente, dashboard KPIs, gestión documental, notificaciones, integraciones (ERP/Quotify/6TL PS).
