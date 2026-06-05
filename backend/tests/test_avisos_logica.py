from datetime import date
from types import SimpleNamespace

from app import avisos


def _con(inicio=date(2020, 1, 1), fin=date(2100, 1, 1), nivel="bronze", cancelado=False):
    return SimpleNamespace(fecha_inicio=inicio, fecha_fin=fin, nivel=nivel, cancelado=cancelado)


def test_clasificar_buckets():
    hoy = date(2026, 6, 5)
    assert avisos.clasificar(date(2026, 6, 1), hoy) == "vencido"
    assert avisos.clasificar(date(2026, 6, 20), hoy) == "proximo"
    assert avisos.clasificar(date(2026, 9, 1), hoy) == "al_dia"


def test_dias_restantes_signo():
    hoy = date(2026, 6, 5)
    assert avisos.dias_restantes(date(2026, 6, 10), hoy) == 5
    assert avisos.dias_restantes(date(2026, 6, 1), hoy) == -4


def test_proxima_desde_ultima_accion_con_proxima_fecha():
    con = _con(nivel="bronze")
    ultima = SimpleNamespace(fecha=date(2025, 1, 1), proxima_fecha=date(2026, 1, 1))
    assert avisos.proxima_fecha_equipo(object(), con, ultima, date(2026, 6, 5)) == date(2026, 1, 1)


def test_proxima_desde_ultima_accion_sin_proxima_fecha_usa_cadencia():
    con = _con(nivel="gold")
    ultima = SimpleNamespace(fecha=date(2026, 1, 1), proxima_fecha=None)
    assert avisos.proxima_fecha_equipo(object(), con, ultima, date(2026, 6, 5)) == date(2026, 7, 1)


def test_proxima_nunca_revisado_desde_inicio_mas_cadencia():
    con = _con(inicio=date(2026, 1, 1), nivel="bronze")
    assert avisos.proxima_fecha_equipo(object(), con, None, date(2026, 6, 5)) == date(2027, 1, 1)


def test_contrato_por_caducar():
    hoy = date(2026, 6, 5)
    assert avisos.contrato_por_caducar(_con(fin=date(2026, 7, 1)), hoy) is True
    assert avisos.contrato_por_caducar(_con(fin=date(2027, 1, 1)), hoy) is False
    assert avisos.contrato_por_caducar(_con(fin=date(2026, 7, 1), cancelado=True), hoy) is False
