from datetime import date
from types import SimpleNamespace

from app import garantia_fabricante as gf


def _g(activacion, meses):
    return SimpleNamespace(fecha_activacion=activacion, meses_garantia=meses)


def test_fecha_fin_suma_meses():
    assert gf.fecha_fin(_g(date(2026, 1, 31), 24)) == date(2028, 1, 31)


def test_fecha_fin_none_si_sin_activar():
    assert gf.fecha_fin(_g(None, 24)) is None
    assert gf.fecha_fin(_g(date(2026, 1, 1), None)) is None


def test_estado_cobertura_sin_activar():
    assert gf.estado_cobertura(_g(None, 24), date(2026, 6, 1)) == "sin_activar"


def test_estado_cobertura_vigente_por_vencer_vencida():
    g = _g(date(2026, 1, 1), 12)  # fin = 2027-01-01
    assert gf.estado_cobertura(g, date(2026, 6, 1)) == "vigente"
    assert gf.estado_cobertura(g, date(2026, 12, 1)) == "por_vencer"  # <= 90 días
    assert gf.estado_cobertura(g, date(2027, 2, 1)) == "vencida"
