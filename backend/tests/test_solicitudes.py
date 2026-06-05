from datetime import date

from app import email_notify, models
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


def test_crear_solicitud_publica(client, monkeypatch):
    enviados = []
    monkeypatch.setattr(email_notify, "enviar_aviso_solicitud", lambda s: enviados.append(s.codigo) or True)
    r = client.post("/api/solicitudes", json={
        "nombre_contacto": "Ana", "email_contacto": "ana@acme.com",
        "titulo": "No arranca", "descripcion_problema": "Se apaga solo",
        "numero_serie_texto": "SN-9",
    })
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["codigo"].startswith("SOL-") and b["estado"] == "pendiente"
    assert "website" not in b
    assert enviados == [b["codigo"]]   # se disparó el aviso


def test_crear_solicitud_honeypot_400(client, monkeypatch):
    monkeypatch.setattr(email_notify, "enviar_aviso_solicitud", lambda s: True)
    r = client.post("/api/solicitudes", json={
        "nombre_contacto": "Bot", "email_contacto": "bot@x.com",
        "titulo": "x", "descripcion_problema": "y", "website": "http://spam",
    })
    assert r.status_code == 400


def test_crear_solicitud_email_invalido_422(client):
    r = client.post("/api/solicitudes", json={
        "nombre_contacto": "Ana", "email_contacto": "no-es-email",
        "titulo": "x", "descripcion_problema": "y",
    })
    assert r.status_code == 422


def test_email_falla_no_rompe_alta(client, monkeypatch):
    def _boom(s):
        raise RuntimeError("smtp down")
    monkeypatch.setattr(email_notify, "enviar_aviso_solicitud", _boom)
    r = client.post("/api/solicitudes", json={
        "nombre_contacto": "Ana", "email_contacto": "ana@acme.com",
        "titulo": "x", "descripcion_problema": "y",
    })
    assert r.status_code == 201, r.text
