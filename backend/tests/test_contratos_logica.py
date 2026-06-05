from datetime import date
from types import SimpleNamespace

from app import contratos


def _c(inicio, fin, cancelado=False, nivel="bronze"):
    return SimpleNamespace(fecha_inicio=inicio, fecha_fin=fin, cancelado=cancelado, nivel=nivel)


def test_estado_vigente():
    c = _c(date(2026, 1, 1), date(2026, 12, 31))
    assert contratos.estado_contrato(c, date(2026, 6, 5)) == "vigente"
    assert contratos.esta_vigente(c, date(2026, 6, 5)) is True


def test_estado_pendiente():
    c = _c(date(2026, 7, 1), date(2026, 12, 31))
    assert contratos.estado_contrato(c, date(2026, 6, 5)) == "pendiente"


def test_estado_vencido():
    c = _c(date(2025, 1, 1), date(2025, 12, 31))
    assert contratos.estado_contrato(c, date(2026, 6, 5)) == "vencido"


def test_estado_cancelado_tiene_prioridad():
    c = _c(date(2026, 1, 1), date(2026, 12, 31), cancelado=True)
    assert contratos.estado_contrato(c, date(2026, 6, 5)) == "cancelado"
    assert contratos.esta_vigente(c, date(2026, 6, 5)) is False


def test_nivel_detalle():
    assert contratos.NIVELES["bronze"]["preventivo"] == "anual"
    assert contratos.NIVELES["gold"]["soporte"] == "24/7"
    assert contratos.NIVELES["silver"]["preventivo_meses"] == 6


def test_sugerir_proxima_fecha_por_nivel():
    assert contratos.sugerir_proxima_fecha(date(2026, 6, 5), "bronze") == date(2027, 6, 5)
    assert contratos.sugerir_proxima_fecha(date(2026, 6, 5), "gold") == date(2026, 12, 5)
    assert contratos.sugerir_proxima_fecha(date(2026, 6, 5), None) is None
