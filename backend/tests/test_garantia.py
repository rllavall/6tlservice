from datetime import date
from types import SimpleNamespace

from app import garantia


def _eq(fecha_entrega=None, meses_garantia=None):
    return SimpleNamespace(fecha_entrega=fecha_entrega, meses_garantia=meses_garantia)


def test_add_months_simple():
    assert garantia._add_months(date(2024, 1, 15), 24) == date(2026, 1, 15)


def test_add_months_clamp_fin_de_mes():
    # 31 ene + 1 mes -> 28/29 feb (no existe 31 feb)
    assert garantia._add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)


def test_fecha_fin_garantia():
    assert garantia.fecha_fin_garantia(_eq(date(2024, 1, 1), 24)) == date(2026, 1, 1)


def test_fecha_fin_garantia_sin_datos():
    assert garantia.fecha_fin_garantia(_eq(None, 24)) is None
    assert garantia.fecha_fin_garantia(_eq(date(2024, 1, 1), None)) is None


def test_estado_vigente():
    eq = _eq(date(2024, 1, 1), 24)  # fin 2026-01-01
    assert garantia.estado_garantia(eq, date(2025, 1, 1)) == "vigente"


def test_estado_por_vencer():
    eq = _eq(date(2024, 1, 1), 24)  # fin 2026-01-01
    assert garantia.estado_garantia(eq, date(2025, 12, 1)) == "por_vencer"  # 31 dias


def test_estado_vencida():
    eq = _eq(date(2024, 1, 1), 24)  # fin 2026-01-01
    assert garantia.estado_garantia(eq, date(2026, 6, 1)) == "vencida"


def test_estado_sin_datos():
    assert garantia.estado_garantia(_eq(None, None), date(2026, 1, 1)) == "sin_datos"


def test_equipo_en_garantia():
    eq = _eq(date(2024, 1, 1), 24)  # fin 2026-01-01
    assert garantia.equipo_en_garantia(eq, date(2025, 6, 1)) is True
    assert garantia.equipo_en_garantia(eq, date(2026, 6, 1)) is False
    assert garantia.equipo_en_garantia(_eq(None, None), date(2026, 1, 1)) is None
