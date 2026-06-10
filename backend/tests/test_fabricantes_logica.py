from types import SimpleNamespace

from app import fabricantes


def test_destino_activacion_usa_email_service():
    f = SimpleNamespace(email_service="svc@ni.com", email_rma=None)
    assert fabricantes.destino_activacion(f) == "svc@ni.com"


def test_destino_rma_cae_a_service_si_no_hay_email_rma():
    f = SimpleNamespace(email_service="svc@ni.com", email_rma=None)
    assert fabricantes.destino_rma(f) == "svc@ni.com"


def test_destino_rma_prefiere_email_rma():
    f = SimpleNamespace(email_service="svc@ni.com", email_rma="rma@ni.com")
    assert fabricantes.destino_rma(f) == "rma@ni.com"


def test_requiere_web():
    assert fabricantes.requiere_web(SimpleNamespace(requiere_activacion_web=True)) is True
    assert fabricantes.requiere_web(SimpleNamespace(requiere_activacion_web=False)) is False


def test_funciones_toleran_none():
    assert fabricantes.destino_activacion(None) is None
    assert fabricantes.destino_rma(None) is None
    assert fabricantes.requiere_web(None) is False
