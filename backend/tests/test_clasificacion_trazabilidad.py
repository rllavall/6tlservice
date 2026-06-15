from app.clasificacion_trazabilidad import clasificar_por_reglas, ResultadoClasificacion


def test_instrumento_afecta_a_medida_no_ambiguo():
    r = clasificar_por_reglas("instrumento", "Keysight", "DMM 6.5 digitos", "34461A")
    assert r.afecta_a_medida is True
    assert r.bajo_coste is False
    assert r.ambiguo is False
    assert r.motivo


def test_mass_interconnect_afecta_a_medida():
    r = clasificar_por_reglas("mass_interconnect", "Virginia Panel", "Receiver", "VP-90")
    assert r.afecta_a_medida is True
    assert r.ambiguo is False


def test_wiring_con_keyword_barata_es_bajo_coste():
    r = clasificar_por_reglas("wiring", None, "Patch cord generico 1m", "PC-1M")
    assert r.bajo_coste is True
    assert r.afecta_a_medida is False
    assert r.ambiguo is False


def test_wiring_con_keyword_de_medida_afecta_y_no_bajo_coste():
    r = clasificar_por_reglas("wiring", None, "Cable de sense Kelvin 4 hilos", "SNS-4")
    assert r.afecta_a_medida is True
    assert r.bajo_coste is False
    assert r.ambiguo is False


def test_accesorios_sin_keyword_es_ambiguo():
    r = clasificar_por_reglas("accesorios", None, "Modulo auxiliar", "AUX-1")
    assert r.ambiguo is True


def test_accesorios_tornillo_es_bajo_coste_no_ambiguo():
    r = clasificar_por_reglas("accesorios", None, "Tornillo M3 inox", "M3")
    assert r.bajo_coste is True
    assert r.ambiguo is False


def test_software_flags_false():
    r = clasificar_por_reglas("software", "6TL", "Licencia TestStand", "SW-1")
    assert r.afecta_a_medida is False
    assert r.bajo_coste is False
    assert r.ambiguo is False


def test_fixture_adaptador_flags_false():
    r = clasificar_por_reglas("fixture_adaptador", "6TL", "Fixture banco X", "FX-1")
    assert r.afecta_a_medida is False
    assert r.bajo_coste is False


def test_marca_instrumentacion_pero_descr_barata_es_ambiguo():
    r = clasificar_por_reglas("accesorios", "Keysight", "Etiqueta adhesiva", "LBL-1")
    assert r.ambiguo is True


def test_categoria_nula_sin_keyword_es_ambiguo():
    r = clasificar_por_reglas(None, None, "Pieza", "X1")
    assert r.ambiguo is True


def test_funciona_sobre_duck_type_via_kwargs():
    r = clasificar_por_reglas("instrumento", "", "", "")
    assert isinstance(r, ResultadoClasificacion)
