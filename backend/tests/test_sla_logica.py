from datetime import date, datetime
from types import SimpleNamespace

from app import sla


def _inc(apertura, creada_en=None, diag=None, ini_rep=None, reso=None, cierre=None,
         respondida_en=None, resuelta_en=None):
    return SimpleNamespace(
        fecha_apertura=apertura, creada_en=creada_en, fecha_diagnostico=diag,
        fecha_inicio_reparacion=ini_rep, fecha_resolucion=reso, fecha_cierre=cierre,
        respondida_en=respondida_en, resuelta_en=resuelta_en)


def test_sla_niveles_horas():
    assert sla.SLA_NIVELES["gold"]["respuesta_horas"] == 2
    assert sla.SLA_NIVELES["gold"]["resolucion_horas"] == 24
    assert sla.SLA_NIVELES["bronze"]["resolucion_horas"] == 168


def test_combinar_usa_dia_y_hora():
    d = date(2026, 6, 1)
    ts = datetime(2025, 1, 1, 14, 30)
    assert sla._combinar(d, ts) == datetime(2026, 6, 1, 14, 30)
    assert sla._combinar(d, None) == datetime(2026, 6, 1, 0, 0)
    assert sla._combinar(None, ts) is None


def test_metrica_cumplida_en_plazo():
    inicio = datetime(2026, 6, 1, 0, 0)
    m = sla.estado_metrica(inicio, datetime(2026, 6, 1, 1, 0), 2, datetime(2026, 6, 2))
    assert m["estado"] == "en_plazo"
    assert m["horas_restantes"] is None
    assert m["objetivo"] == datetime(2026, 6, 1, 2, 0)


def test_metrica_cumplida_tarde():
    inicio = datetime(2026, 6, 1, 0, 0)
    m = sla.estado_metrica(inicio, datetime(2026, 6, 1, 5, 0), 2, datetime(2026, 6, 2))
    assert m["estado"] == "incumplido"


def test_metrica_pendiente_en_riesgo():
    inicio = datetime(2026, 6, 1, 0, 0)
    m = sla.estado_metrica(inicio, None, 24, datetime(2026, 6, 1, 20, 0))
    assert m["estado"] == "en_riesgo"
    assert m["horas_restantes"] == 4


def test_metrica_pendiente_incumplido():
    inicio = datetime(2026, 6, 1, 0, 0)
    m = sla.estado_metrica(inicio, None, 2, datetime(2026, 6, 1, 10, 0))
    assert m["estado"] == "incumplido"
    assert m["horas_restantes"] < 0


def test_metrica_pendiente_en_plazo():
    inicio = datetime(2026, 6, 1, 0, 0)
    m = sla.estado_metrica(inicio, None, 168, datetime(2026, 6, 1, 1, 0))
    assert m["estado"] == "en_plazo"


def test_peor():
    assert sla.peor("en_plazo", "incumplido") == "incumplido"
    assert sla.peor("en_plazo", "en_riesgo") == "en_riesgo"
    assert sla.peor("en_plazo", "en_plazo") == "en_plazo"


def test_evaluar_dia_de_apertura_hora_de_creada():
    inc = _inc(date(2026, 6, 1), creada_en=datetime(2026, 6, 1, 10, 0),
               diag=date(2026, 6, 1), respondida_en=datetime(2026, 6, 1, 11, 0))
    ev = sla.evaluar(inc, "gold", datetime(2026, 6, 10))
    assert ev["nivel"] == "gold"
    assert ev["respuesta"]["real"] == datetime(2026, 6, 1, 11, 0)
    assert ev["respuesta"]["estado"] == "en_plazo"
