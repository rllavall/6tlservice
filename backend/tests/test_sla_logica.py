from datetime import date
from types import SimpleNamespace

from app import sla


def _inc(apertura, diag=None, ini_rep=None, reso=None, cierre=None):
    return SimpleNamespace(
        fecha_apertura=apertura, fecha_diagnostico=diag, fecha_inicio_reparacion=ini_rep,
        fecha_resolucion=reso, fecha_cierre=cierre)


def test_sla_niveles():
    assert sla.SLA_NIVELES["gold"]["respuesta_dias"] == 1
    assert sla.SLA_NIVELES["bronze"]["resolucion_dias"] == 15


def test_metrica_cumplida_en_plazo():
    m = sla.estado_metrica(date(2026, 6, 1), date(2026, 6, 2), 3, date(2026, 6, 10))
    assert m["estado"] == "en_plazo"
    assert m["objetivo_fecha"] == date(2026, 6, 4)


def test_metrica_cumplida_tarde_incumplido():
    m = sla.estado_metrica(date(2026, 6, 1), date(2026, 6, 9), 3, date(2026, 6, 10))
    assert m["estado"] == "incumplido"


def test_metrica_pendiente_en_riesgo():
    m = sla.estado_metrica(date(2026, 6, 1), None, 5, date(2026, 6, 5))  # objetivo 06-06, quedan 1 día
    assert m["estado"] == "en_riesgo"


def test_metrica_pendiente_incumplido():
    m = sla.estado_metrica(date(2026, 6, 1), None, 3, date(2026, 6, 10))  # objetivo 06-04 < hoy
    assert m["estado"] == "incumplido"


def test_metrica_pendiente_en_plazo():
    m = sla.estado_metrica(date(2026, 6, 1), None, 15, date(2026, 6, 2))  # objetivo 06-16, lejos
    assert m["estado"] == "en_plazo"


def test_peor():
    assert sla.peor("en_plazo", "incumplido") == "incumplido"
    assert sla.peor("en_plazo", "en_riesgo") == "en_riesgo"
    assert sla.peor("en_plazo", "en_plazo") == "en_plazo"


def test_evaluar_usa_primera_fecha_respuesta():
    inc = _inc(date(2026, 6, 1), diag=None, ini_rep=date(2026, 6, 2))
    ev = sla.evaluar(inc, "gold", date(2026, 6, 10))
    assert ev["nivel"] == "gold"
    assert ev["respuesta"]["estado"] == "en_plazo"
    assert ev["respuesta"]["fecha_real"] == date(2026, 6, 2)
    assert ev["estado_global"] in {"en_plazo", "en_riesgo", "incumplido"}
