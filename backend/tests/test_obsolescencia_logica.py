import pytest

from app import obsolescencia as ob


def test_estados_y_severidad():
    assert ob.ESTADOS == ["activo", "nrnd", "eol_anunciado", "ultima_compra", "obsoleto"]
    assert ob.severidad("activo") == 0
    assert ob.severidad("obsoleto") == 4
    assert ob.severidad(None) == 0          # sin verificar = baseline
    assert ob.severidad("desconocido") == 0


def test_estado_valido():
    assert ob.estado_valido("nrnd") is True
    assert ob.estado_valido("activo") is True
    assert ob.estado_valido("zzz") is False
    assert ob.estado_valido(None) is False


def test_requiere_url():
    assert ob.requiere_url("activo") is False
    assert ob.requiere_url("nrnd") is True
    assert ob.requiere_url("obsoleto") is True


def test_es_cambio_notable_solo_si_empeora():
    assert ob.es_cambio_notable(None, "activo") is False     # primera vez activo: no avisa
    assert ob.es_cambio_notable(None, "obsoleto") is True
    assert ob.es_cambio_notable("activo", "nrnd") is True
    assert ob.es_cambio_notable("nrnd", "nrnd") is False      # se mantiene: no duplica
    assert ob.es_cambio_notable("obsoleto", "activo") is False  # recuperación: no avisa
    assert ob.es_cambio_notable("activo", "zzz") is False     # estado inválido


def test_validar_hallazgo():
    ob.validar_hallazgo("activo", None)                 # ok sin url
    ob.validar_hallazgo("obsoleto", "https://x")        # ok con url
    with pytest.raises(ValueError):
        ob.validar_hallazgo("obsoleto", None)           # downgrade sin fuente
    with pytest.raises(ValueError):
        ob.validar_hallazgo("zzz", "https://x")         # estado inválido
