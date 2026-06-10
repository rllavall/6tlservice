from app import derivaciones


def test_transicion_valida_avanza_un_paso():
    assert derivaciones.transicion_valida("pendiente", "enviada") is True
    assert derivaciones.transicion_valida("enviada", "en_proveedor") is True
    assert derivaciones.transicion_valida("en_proveedor", "recibida") is True
    assert derivaciones.transicion_valida("recibida", "cerrada") is True


def test_transicion_invalida_salta_pasos_o_retrocede():
    assert derivaciones.transicion_valida("pendiente", "cerrada") is False
    assert derivaciones.transicion_valida("enviada", "pendiente") is False
    assert derivaciones.transicion_valida("cerrada", "recibida") is False


def test_misma_etapa_es_valida_idempotente():
    assert derivaciones.transicion_valida("enviada", "enviada") is True
