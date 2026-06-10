# Motor de Fabricantes y RMA — Diseño

- **Fecha**: 2026-06-11
- **Proyecto**: 6TL Postventa (`6tlservice`)
- **Origen**: brainstorming a partir de la reunión "06-10 Disseny d'un Sistema de Gestió del Cicle de Vida del Producte".
- **Alcance**: automatizaciones #1 (maestro de fabricantes), #2 (bucle de activación de garantía) y #3 (RMA externo encadenado / derivación interna), tratadas como una sola pieza coherente.

## 1. Problema y motivación

La reunión describe el ciclo de vida completo del producto en servicio postventa. Buena parte ya está implementada (base instalada, incidencias, garantía a nivel equipo, preventivo, avisos, ayuda contextual, solicitudes de cliente, contratos, SLA, notificaciones). Faltan tres piezas que la reunión señala como las más diferenciadoras:

1. **Maestro de fabricantes**: cada marca (National Instruments, Keysight/Agilent, Rohde, SMH…) gestiona garantía y RMA de forma distinta. Hoy `Producto.fabricante` es solo texto libre y no hay procedimiento asociado. Resultado: garantías que no se activan ("no ho fem") y RMAs gestionados a mano en la web de cada fabricante.

2. **Activación de garantía con bucle cerrado**: para fabricantes como National, la garantía del instrumento **empieza cuando el fabricante la activa**, no en la entrega. Hoy no se traza. Se quiere: el sistema redacta el email, lo manda al responsable interno, deja el estado "pendiente del Galarzo", y al recibir feedback se registra la fecha real de inicio y arranca el conteo.

3. **RMA externo encadenado**: una incidencia de un instrumento en garantía dispara un envío al fabricante (RMA externo) con la referencia interna; se guarda el nº de RMA del fabricante; al cerrarse, cierra la incidencia. Si lo que falla es algo propio (la máquina, no el instrumento), el mismo mecanismo dispara un flujo **interno** hacia el departamento que corresponda.

## 2. Decisiones de diseño tomadas

- **Maestro de fabricantes**: nueva tabla `Fabricante` + FK `Producto.fabricante_id`. El texto libre actual se migra emparejando por nombre y se conserva como legado.
- **Garantía del fabricante a nivel Componente** (el instrumento individual), no a nivel Equipo. Es lo que se activa con la marca (el serial del DMM). Independiente de la garantía comercial que el Equipo da al cliente.
- **`GarantiaFabricante` como tabla 1:1** con `Componente` (no columnas en `Componente`), por el ciclo de estados.
- **`Derivacion` como entidad 0..N** ligada a `Incidencia`, que cubre tanto el RMA externo al fabricante como el flujo interno a un departamento con el mismo mecanismo.
- **`departamento`** en derivaciones internas: texto libre (endurecible a lista cerrada más adelante).
- **Cierre del bucle**: email best-effort (vía el SMTP existente) + confirmación manual del feedback. El humano siempre está en el lazo; nada se envía directo al fabricante sin paso interno.

## 3. Modelo de datos

### 3.1 `Fabricante` (tabla nueva `fabricantes`)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `nombre` | str único | National Instruments, Keysight… |
| `email_service` | str? | destino para activación de garantía |
| `email_rma` | str? | destino para RMA (puede coincidir con service) |
| `url_activacion_garantia` | str? | web de activación cuando aplica |
| `requiere_activacion_web` | bool | default False |
| `politica_rma` | text? | procedimiento descrito |
| `notas` | str? | |

`Producto.fabricante_id`: FK nullable → `fabricantes.id`. Se conserva `Producto.fabricante` (texto) como legado.

### 3.2 `GarantiaFabricante` (tabla nueva `garantias_fabricante`, 1:1 con Componente)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `componente_id` | FK único → componentes.id | 1:1 |
| `fabricante_id` | FK → fabricantes.id | derivable del producto, se persiste |
| `estado` | str | `no_aplica` \| `pendiente_activacion` \| `activada` \| `rechazada` |
| `fecha_solicitud` | date? | cuándo se pidió la activación |
| `fecha_activacion` | date? | inicio real de la garantía (arranca el conteo) |
| `meses_garantia` | int? | |
| `referencia_fabricante` | str? | id que devuelve el fabricante |
| `responsable` | str? | quién gestiona ("el Galarzo") |
| `notas` | str? | |

Derivados (propiedades, reutilizando lógica de `garantia.py`):
- `fecha_fin`: `fecha_activacion + meses_garantia`.
- `estado_cobertura`: `vigente` \| `por_vencer` \| `vencida` \| `sin_activar`.

`estado = pendiente_activacion` es el label "pendiente del Galarzo".

### 3.3 `Derivacion` (tabla nueva `derivaciones`, 0..N por Incidencia)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `incidencia_id` | FK → incidencias.id | |
| `tipo` | str | `externa_fabricante` \| `interna_departamento` |
| `fabricante_id` | FK? → fabricantes.id | si externa |
| `departamento` | str? | si interna (texto libre) |
| `tu_referencia` | str único | auto `RMA-NNNN` |
| `referencia_externa` | str? | nº de RMA del fabricante |
| `estado` | str | `pendiente` \| `enviada` \| `en_proveedor` \| `recibida` \| `cerrada` |
| `fecha_creacion` | date | |
| `fecha_envio` | date? | |
| `fecha_cierre` | date? | |
| `notas` | str? | |

Al pasar a `cerrada`, puede avanzar/cerrar la incidencia padre (regla en el servicio).

## 4. Lógica (módulos puros + servicios)

Sigue el patrón existente: módulo puro testeable + servicio con DB.

- **`app/fabricantes.py`** (puro): resuelve el procedimiento por marca — a quién se escribe (service/rma), si requiere web, texto base de la política.
- **`app/garantia_fabricante.py`** (puro) + servicio:
  - `activar(componente, ...)`: crea `GarantiaFabricante` en `pendiente_activacion`, fija `fecha_solicitud`, prepara el email.
  - `confirmar(garantia, fecha_activacion, referencia)`: pasa a `activada`, arranca el conteo.
  - cobertura derivada (delega en `garantia.py` para vigente/por_vencer/vencida).
- **`app/derivaciones.py`** (puro) + servicio:
  - `crear(incidencia, tipo, destino)`: genera `tu_referencia` (`RMA-NNNN`), estado `pendiente`, prepara destino/email según tipo + fabricante.
  - transiciones de estado (`enviada` → `en_proveedor` → `recibida` → `cerrada`), registro de `referencia_externa`.
  - `cerrar(derivacion)`: regla de avance de la incidencia padre.
- **Email**: reutiliza el SMTP best-effort existente (`email_notify` / `notificaciones`). Plantillas nuevas para activación y para RMA. El envío nunca bloquea; la confirmación del feedback es siempre manual.

## 5. API (routers protegidos con auth + auditoría heredada)

- CRUD `/api/fabricantes`.
- `POST /api/componentes/{id}/garantia/activar` — crea solicitud + email.
- `POST /api/componentes/{id}/garantia/confirmar` — registra feedback (fecha + referencia).
- `GET /api/componentes/{id}/garantia`.
- `GET /api/garantias/pendientes` — cola "pendiente del Galarzo" para panel.
- `POST /api/incidencias/{id}/derivaciones` — crea derivación + email.
- `PATCH /api/derivaciones/{id}` — transiciones de estado, `referencia_externa`, cierre.
- `GET /api/incidencias/{id}/derivaciones`.

## 6. Migración e infraestructura

- `app/migrations.py::ensure_schema` (idempotente, patrón existente): `ALTER TABLE productos ADD COLUMN fabricante_id`; `create_all` de `fabricantes`, `garantias_fabricante`, `derivaciones`.
- **Data-migration de siembra**: por cada valor distinto y no nulo de `Producto.fabricante`, crear un `Fabricante` (si no existe por nombre) y enlazar `fabricante_id`. Idempotente.
- Routers nuevos heredan auth (Bearer) y auditoría automática (listener ORM) ya existentes.
- **Tópicos de ayuda** (`AyudaTopico`): claves nuevas para cada botón/acción del módulo, sembradas por `ayuda_seed.py` (insert-if-missing). Es la pieza que más valoraron en la reunión.

## 7. Testing (TDD, subagent-driven)

- Módulos puros (`fabricantes`, `garantia_fabricante`, `derivaciones`): tests unitarios sin DB.
- Servicios: tests con DB en memoria (patrón existente).
- Routers: `TestClient` con auth.
- Migración: test de idempotencia (ejecutar dos veces, sin error, sin duplicar fabricantes).
- Data-migration de siembra: test que verifica emparejado por nombre y no duplicación.

## 8. Fuera de alcance (YAGNI explícito)

- **Contratos back-to-back proveedor (#4)**: diferido. El maestro `Fabricante` deja el gancho para colgar contratos de proveedor más adelante.
- **Integración API real con fabricantes**: solo email best-effort; nada de scraping de sus webs ni APIs propietarias.
- **IA de patrones de incidencias (#7)**: diferido a cuando haya volumen de datos.
- **Upsell proactivo (#6)** y **autocompletar alta desde albarán (#5)**: módulos separados, fuera de esta pieza.

## 9. Riesgos / notas operativas

- `ensure_schema` debe correr antes que cualquier consulta que toque las columnas nuevas (patrón ya establecido en el proyecto).
- El seeder de ayuda toca `postventa.db` al importar: parar uvicorn antes de correr tests (nota operativa conocida del proyecto).
- La cola `GET /api/garantias/pendientes` debe filtrar solo `pendiente_activacion` para no saturar el panel.
