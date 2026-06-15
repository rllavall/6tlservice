from app.clasificacion_llm import _parsear_respuesta


def test_parsea_json_estricto():
    out = '{"afecta_a_medida": true, "bajo_coste": false, "razon": "es un DMM"}'
    r = _parsear_respuesta(out)
    assert r == {"afecta_a_medida": True, "bajo_coste": False, "razon": "es un DMM"}


def test_parsea_json_envuelto_en_texto():
    out = 'Claro:\n{"afecta_a_medida": false, "bajo_coste": true, "razon": "cable"}\nFin.'
    r = _parsear_respuesta(out)
    assert r["bajo_coste"] is True


def test_respuesta_invalida_devuelve_none():
    assert _parsear_respuesta("no soy json") is None


def test_respuesta_sin_razon_devuelve_none():
    out = '{"afecta_a_medida": true, "bajo_coste": false}'
    assert _parsear_respuesta(out) is None


def test_respuesta_tipos_incorrectos_devuelve_none():
    out = '{"afecta_a_medida": "si", "bajo_coste": false, "razon": "x"}'
    assert _parsear_respuesta(out) is None


def test_medida_y_bajo_coste_incoherente_corrige_bajo_coste():
    out = '{"afecta_a_medida": true, "bajo_coste": true, "razon": "x"}'
    r = _parsear_respuesta(out)
    assert r["afecta_a_medida"] is True
    assert r["bajo_coste"] is False
