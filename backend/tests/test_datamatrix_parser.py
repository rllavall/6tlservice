from app import datamatrix


def test_placeholder_detecta_prefijo():
    assert datamatrix.es_serie_placeholder("S/N pendiente (1.1)") is True

def test_placeholder_falso_para_serial_real():
    assert datamatrix.es_serie_placeholder("ABC123") is False

def test_placeholder_none():
    assert datamatrix.es_serie_placeholder(None) is False


def test_gs1_ai21_es_sn():
    r = datamatrix.parsear_gs1("21SN12345")
    assert r["sn"] == "SN12345"
    assert r["formato"] == "gs1"

def test_gs1_ai01_es_pn_gtin():
    r = datamatrix.parsear_gs1("0107612345678903")
    assert r["pn"] == "07612345678903"

def test_gs1_ignora_prefijo_simbologia():
    # ]d2 (simbologia) + AI01 GTIN(14) "07612345678903" + AI21 "SN999"
    r = datamatrix.parsear_gs1("]d2010761234567890321SN999")
    assert r["pn"] == "07612345678903"
    assert r["sn"] == "SN999"

def test_gs1_ai01_seguido_de_ai21_sin_prefijo():
    # Formato real más común en electrónica: 01<GTIN14>21<serial>, sin simbología.
    r = datamatrix.parsear_gs1("010761234567890321SER-ABC123")
    assert r["pn"] == "07612345678903"
    assert r["sn"] == "SER-ABC123"

def test_gs1_separador_gs_para_campo_variable():
    raw = "21LOTE-7\x1d240PN-ABC"
    r = datamatrix.parsear_gs1(raw)
    assert r["sn"] == "LOTE-7"
    assert r["pn"] == "PN-ABC"

def test_gs1_no_gs1_devuelve_none():
    r = datamatrix.parsear_gs1("CADENA-LIBRE-SIN-AI")
    assert r["pn"] is None and r["sn"] is None


def test_regla_extrae_pn_y_sn():
    regla = r"^(?P<pn>[A-Z0-9]+)-(?P<sn>\d+)$"
    r = datamatrix.parsear_con_regla("ABC123-456", regla)
    assert r == {"pn": "ABC123", "sn": "456", "formato": "regla"}

def test_regla_no_casa_devuelve_none():
    assert datamatrix.parsear_con_regla("xxx", r"^\d+$") is None

def test_regla_invalida_devuelve_none():
    assert datamatrix.parsear_con_regla("abc", r"(?P<sn>[") is None


def test_parsear_regla_gana_sobre_gs1():
    regla = r"^(?P<pn>[A-Z]+)(?P<sn>\d+)$"
    r = datamatrix.parsear("ABC123", [regla])
    assert r["formato"] == "regla" and r["pn"] == "ABC" and r["sn"] == "123"

def test_parsear_sin_regla_usa_gs1():
    r = datamatrix.parsear("21SN42", [])
    assert r["formato"] == "gs1" and r["sn"] == "SN42"

def test_parsear_cae_a_crudo():
    r = datamatrix.parsear("CADENA-LIBRE", [])
    assert r["formato"] == "crudo" and r["sn"] == "CADENA-LIBRE" and r["pn"] is None

def test_parsear_ignora_regla_invalida_y_sigue():
    r = datamatrix.parsear("21SN42", [r"(?P<sn>["])
    assert r["formato"] == "gs1" and r["sn"] == "SN42"
