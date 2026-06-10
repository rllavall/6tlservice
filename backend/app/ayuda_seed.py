from __future__ import annotations

from sqlalchemy.orm import Session

from app import models

CATALOGO_INICIAL = [
    {"clave": "equipos.estado", "titulo": "Estado del equipo", "pantalla": "equipos",
     "texto": "Operativo = el equipo está en servicio. Baja = retirado del servicio (reversible desde la ficha)."},
    {"clave": "equipos.categoria", "titulo": "Categoría", "pantalla": "equipos",
     "texto": "Familia del equipo: ATE, YAV Module, FastATE Module, Test Fixture, Test Handler u Otro. Se hereda del producto del catálogo."},
    {"clave": "equipos.version", "titulo": "Versión", "pantalla": "equipos",
     "texto": "Revisión de hardware/firmware de esta unidad concreta."},
    {"clave": "equipos.numero_serie_cliente", "titulo": "Nº de serie del cliente", "pantalla": "equipos",
     "texto": "Número de serie con el que el cliente identifica el equipo (opcional, distinto del nuestro)."},
    {"clave": "garantia.estado", "titulo": "Estado de garantía", "pantalla": "garantia",
     "texto": "Vigente, Por vencer (≤90 días), Vencida o Sin datos. Se calcula desde la fecha de fabricación/entrega y los meses de garantía."},
    {"clave": "garantia.meses", "titulo": "Meses de garantía", "pantalla": "garantia",
     "texto": "Meses de garantía de la unidad. Si está vacío, se hereda del producto (por defecto 24)."},
    {"clave": "incidencias.tipo", "titulo": "Tipo de incidencia", "pantalla": "incidencias",
     "texto": "RMA (devolución/reparación), Soporte de venta (SV), Soporte técnico (ST) o Calibración (CAL). El código de la incidencia lleva ese prefijo."},
    {"clave": "incidencias.prioridad", "titulo": "Prioridad", "pantalla": "incidencias",
     "texto": "Baja, Media o Alta. Orienta el orden de atención."},
    {"clave": "incidencias.estado", "titulo": "Estado", "pantalla": "incidencias",
     "texto": "Flujo: Abierta → Diagnóstico → En reparación → Resuelta → Cerrada. Se puede reabrir una resuelta o cerrada."},
    {"clave": "incidencias.en_garantia", "titulo": "En garantía", "pantalla": "incidencias",
     "texto": "Indica si la incidencia está cubierta por garantía. En RMA se autodetecta del equipo al crearla (editable)."},
    {"clave": "incidencias.avances", "titulo": "Bitácora de avances", "pantalla": "incidencias",
     "texto": "Registro cronológico de la incidencia: reportes, llamadas, visitas, diagnósticos y avances."},
    {"clave": "mapa.pin", "titulo": "Pines del mapa", "pantalla": "mapa",
     "texto": "Cada pin es una ubicación con coordenadas y al menos un equipo operativo; agrupa los equipos de esa ubicación."},
    {"clave": "mapa.incluir_baja", "titulo": "Incluir bajas", "pantalla": "mapa",
     "texto": "Si se activa, también se muestran los equipos dados de baja (no solo los operativos)."},
    {"clave": "analitica.mttr", "titulo": "MTTR", "pantalla": "analitica",
     "texto": "Tiempo medio de reparación: de la apertura a la resolución de las incidencias."},
    {"clave": "resumen.tiempo_medio_cierre", "titulo": "Tiempo medio de cierre", "pantalla": "resumen",
     "texto": "Tiempo medio de cierre en los últimos 30 días: de la apertura al cierre de la incidencia."},
    {"clave": "auditoria.historial", "titulo": "Historial de cambios", "pantalla": "auditoria",
     "texto": "Quién creó, editó o borró cada dato de esta ficha y cuándo."},
    {"clave": "fabricantes.maestro", "titulo": "Maestro de fabricantes", "pantalla": "fabricantes",
     "texto": "Ficha por marca (National, Keysight…): a qué email se escribe para activar "
              "garantía y para RMA, si exige activación en su web, y su política de RMA. "
              "Es la base para automatizar avisos y derivaciones."},
    {"clave": "garantia.activar", "titulo": "Activar garantía del fabricante", "pantalla": "componentes",
     "texto": "Inicia la activación de la garantía del instrumento con el fabricante. El "
              "sistema redacta el aviso y deja la garantía 'pendiente de activación' hasta "
              "que registres el feedback (fecha real y referencia), que arranca el conteo."},
    {"clave": "garantia.confirmar", "titulo": "Confirmar activación", "pantalla": "componentes",
     "texto": "Registra la respuesta del fabricante: fecha real de inicio y referencia. A "
              "partir de esa fecha la garantía cuenta y se calcula su vencimiento."},
    {"clave": "derivaciones.crear", "titulo": "Derivar incidencia (RMA / interno)", "pantalla": "incidencias",
     "texto": "Abre una derivación desde la incidencia: externa hacia un fabricante (con tu "
              "referencia y la suya) o interna hacia un departamento. Misma mecánica para "
              "ambos; al cerrarse, resuelve la incidencia."},
]


def sembrar_ayuda(db: Session) -> int:
    """Inserta las claves del catálogo que falten (no pisa las existentes). Devuelve cuántas insertó."""
    existentes = {clave for (clave,) in db.query(models.AyudaTopico.clave).all()}
    nuevos = 0
    for item in CATALOGO_INICIAL:
        if item["clave"] in existentes:
            continue
        db.add(models.AyudaTopico(
            clave=item["clave"], titulo=item.get("titulo"),
            texto=item["texto"], pantalla=item.get("pantalla"),
        ))
        nuevos += 1
    if nuevos:
        db.commit()
    return nuevos
