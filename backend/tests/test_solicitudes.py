from datetime import date

from app import models
from app import solicitudes_service as svc


def test_modelo_solicitud_defaults(db_session):
    s = models.SolicitudSoporte(
        codigo="SOL-0001", nombre_contacto="Ana", email_contacto="ana@x.com",
        titulo="t", descripcion_problema="d", fecha_solicitud=date(2026, 6, 5),
    )
    db_session.add(s); db_session.flush()
    assert s.estado == "pendiente"
    assert s.empresa is None and s.incidencia_id is None


def test_generar_codigo_solicitud(db_session):
    assert svc.generar_codigo(db_session) == "SOL-0001"
    db_session.add(models.SolicitudSoporte(
        codigo="SOL-0001", nombre_contacto="a", email_contacto="a@x.com",
        titulo="t", descripcion_problema="d", fecha_solicitud=date(2026, 6, 5),
    ))
    db_session.flush()
    assert svc.generar_codigo(db_session) == "SOL-0002"
