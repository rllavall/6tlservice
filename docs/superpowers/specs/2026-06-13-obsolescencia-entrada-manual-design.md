# Entrada manual del estado de ciclo de vida — Diseño

**Fecha:** 2026-06-13
**Estado:** aprobado por el usuario (verbal) — pendiente de plan

## Problema

El agente de obsolescencia no puede determinar el estado de ciclo de vida de productos
cuyo fabricante bloquea bots (p. ej. Keysight: su portal de product-lifecycle devuelve
403 al fetcher). Esos ítems se quedan permanentemente en `no_encontrado`. El usuario
quiere poder **fijar el estado a mano** desde el popup del report del banco, para esos
casos (o cualquier ítem irresoluble), sin esperar al agente.

## Decisiones tomadas

- **Precedencia: "agente gana".** Un hallazgo automático fiable (`ok`, con cita + url
  verificada) llama a `registrar_hallazgo` y **sobreescribe** el valor manual. Como
  `no_encontrado` NO toca el estado, el valor manual **sobrevive** en los bot-blocked
  (Keysight) → encaja sin lógica especial.
- **Ubicación UI:** edición **por fila en el popup del report del banco** (lápiz por
  componente). Donde se ve el "No encontrado", se arregla.
- **La nota manual se guarda en `ciclo_vida_cita`** (se reutiliza el campo de evidencia;
  el badge "Manual" deja claro que es del usuario, no una cita web).
- **Una entrada manual notable crea `NoticiaObsolescencia`** (entra en el digest y en el
  histórico), igual que un hallazgo del agente.

## Componentes y cambios

### 1. Modelo — `backend/app/models.py` + `backend/app/migrations.py`
- `Producto.ciclo_vida_origen: str | None` (TEXT, `'agente' | 'manual'`; null = histórico).
- `NoticiaObsolescencia.origen: str | None` (TEXT), por consistencia/auditoría.
- Migración idempotente para ambas.

### 2. Servicio — `backend/app/obsolescencia_service.py`
- `registrar_hallazgo` (agente): setea `p.ciclo_vida_origen = "agente"` y `origen="agente"`
  en la `NoticiaObsolescencia`. Resto igual. (Precedencia "agente gana" = ya sobreescribe.)
- Nuevo `registrar_manual(db, producto_id, estado, *, hoy, fecha_evento=None, url=None,
  nota=None) -> dict`:
  - Valida `estado` (uno de los 5; requerido). **NO** exige url (relaja `requiere_url`,
    porque en bot-blocked el usuario no tiene una url limpia).
  - Setea estado/fecha/url; `ciclo_vida_cita = nota`; `ciclo_vida_verificado_en = hoy`;
    `ciclo_vida_origen = "manual"`.
  - Si el cambio es notable (`es_cambio_notable`) → crea `NoticiaObsolescencia` con
    `cita=nota`, `origen="manual"`.

### 3. API — `backend/app/routers/productos.py` + `backend/app/schemas.py`
- Schema input `CicloVidaManualIn { estado: _ESTADO_CICLO, fecha_evento?: date,
  url?: str, nota?: str }`.
- `PATCH /api/productos/{producto_id}/ciclo-vida` (protegido por el `get_current_user`
  global del router): 404 si no existe; el `Literal` da 422 si `estado` inválido; llama
  `registrar_manual`, devuelve `ProductoOut`.
- `ProductoOut += ciclo_vida_cita`, `ciclo_vida_origen`.

### 4. Banco / schemas
- `informe_banco` añade `ciclo_vida_origen` a cada fila.
- `ObsolescenciaBancoComponenteOut += ciclo_vida_origen: Optional[str]`.

### 5. Frontend — prompt Lovable 37
- En cada fila del report, un **lápiz** → mini-diálogo: `estado` (select de los 5),
  `fecha`, `url` (opcional), `nota` (textarea = justificación). Guardar →
  `PATCH /api/productos/{id}/ciclo-vida` → refresca la tabla.
- Badge **"✋ Manual"** junto al estado cuando `ciclo_vida_origen === "manual"`. La nota
  se ve en el botón "i" de cita ya existente (prompt 36).

## Pruebas (TDD)
- `registrar_manual`: setea estado/fecha/url/cita(nota)/verificado_en/origen='manual';
  NO exige url (un `obsoleto` sin url se guarda); crea noticia si notable.
- Precedencia: `registrar_hallazgo` sobre un producto con origen='manual' lo deja en
  'agente' (sobreescribe); `marcar_revisado`/`no_encontrado` NO pisa el manual.
- Migración añade `ciclo_vida_origen` (productos) y `origen` (noticias).
- Endpoint PATCH: 200 + producto actualizado; 404 inexistente; 422 estado inválido.
- `informe_banco` expone `ciclo_vida_origen`.

## Fuera de alcance (YAGNI)
- "Borrar"/volver a sin-verificar a mano.
- Editar el ciclo de vida fuera del popup del banco (pantalla Productos/Obsolescencia).
