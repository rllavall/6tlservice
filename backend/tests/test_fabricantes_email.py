from types import SimpleNamespace

from app import fabricantes_email as fe


def test_construir_email_activacion_incluye_serie_y_destino():
    cfg = {"from": "support@6tlengineering.com", "to": "interno@6tl.com"}
    componente = SimpleNamespace(numero_serie="SN-123")
    fabricante = SimpleNamespace(nombre="National", email_service="svc@ni.com", email_rma=None)
    msg = fe.construir_email_activacion(componente, fabricante, cfg)
    assert "SN-123" in msg.get_content()
    assert "National" in msg.get_content()
    assert msg["To"] == "interno@6tl.com"


def test_construir_email_rma_incluye_referencias():
    cfg = {"from": "support@6tlengineering.com", "to": "interno@6tl.com"}
    derivacion = SimpleNamespace(tu_referencia="RMA-0007", referencia_externa=None)
    fabricante = SimpleNamespace(nombre="Keysight", email_service=None, email_rma="rma@key.com")
    msg = fe.construir_email_rma(derivacion, fabricante, cfg)
    assert "RMA-0007" in msg.get_content()
    assert "Keysight" in msg.get_content()


def test_enviar_es_best_effort_y_usa_transporte_inyectado():
    enviados = []
    componente = SimpleNamespace(numero_serie="SN-9")
    fabricante = SimpleNamespace(nombre="NI", email_service="svc@ni.com", email_rma=None)
    ok = fe.enviar_activacion(componente, fabricante, transporte=lambda m, c: enviados.append(m))
    assert ok is True
    assert len(enviados) == 1


def test_enviar_devuelve_false_si_transporte_lanza():
    def _boom(m, c):
        raise RuntimeError("smtp caído")
    componente = SimpleNamespace(numero_serie="SN-9")
    fabricante = SimpleNamespace(nombre="NI", email_service="svc@ni.com", email_rma=None)
    assert fe.enviar_activacion(componente, fabricante, transporte=_boom) is False
