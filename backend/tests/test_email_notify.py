from datetime import date
from types import SimpleNamespace

from app import email_notify


def _sol():
    return SimpleNamespace(
        codigo="SOL-0007", nombre_contacto="Ana", empresa="ACME",
        email_contacto="ana@acme.com", telefono_contacto="600",
        numero_serie_texto="SN-1", part_number_texto="PN-1",
        titulo="No arranca", descripcion_problema="Se apaga solo",
        fecha_solicitud=date(2026, 6, 5),
    )


def test_construir_mensaje_incluye_codigo_y_destino():
    cfg = {"from": "support@6tlengineering.com", "to": "support@6tlengineering.com",
           "host": "smtp.x", "port": 587, "user": None, "password": None}
    msg = email_notify.construir_mensaje(_sol(), cfg)
    assert "SOL-0007" in msg["Subject"]
    assert msg["To"] == "support@6tlengineering.com"
    assert "No arranca" in msg.get_content()


def test_sin_config_smtp_no_envia(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    enviados = []
    ok = email_notify.enviar_aviso_solicitud(_sol(), transporte=lambda m, c: enviados.append(m))
    assert ok is False and enviados == []   # sin host no intenta enviar


def test_envia_con_transporte_inyectado(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    enviados = []
    ok = email_notify.enviar_aviso_solicitud(_sol(), transporte=lambda m, c: enviados.append(m))
    assert ok is True and len(enviados) == 1


def test_fallo_de_envio_es_best_effort(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    def _boom(m, c):
        raise RuntimeError("smtp down")
    ok = email_notify.enviar_aviso_solicitud(_sol(), transporte=_boom)
    assert ok is False   # no relanza


def test_smtp_port_no_numerico_cae_a_587(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "abc")
    cfg = email_notify._config()
    assert cfg["port"] == 587
