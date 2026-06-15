def _comp(client, pn, cat, descripcion="x"):
    # crea con flag explicito para NO disparar reglas y poder probar el lote
    return client.post("/api/productos", json=dict(
        part_number=pn, tipo="componente", descripcion=descripcion,
        categoria_componente=cat, afecta_a_medida=False)).json()


def test_lote_protegido_sin_token_401(client_sin_auth):
    r = client_sin_auth.post("/api/clasificacion-trazabilidad/lote")
    assert r.status_code == 401


def test_lote_dry_run_no_escribe(client):
    _comp(client, "I1", "instrumento", "DMM")
    r = client.post("/api/clasificacion-trazabilidad/lote?dry_run=true")
    assert r.status_code == 200
    # como se creo manual, el lote lo omite
    assert r.json()["omitidos_manual"] >= 1


def test_lote_clasifica_componentes_agente(client):
    # producto agente (sin flags) ya quedo clasificado por el trigger; el lote
    # re-evalua y reporta sin_cambios o cambios
    client.post("/api/productos", json=dict(
        part_number="W1", tipo="componente", descripcion="Patch generico",
        categoria_componente="wiring"))
    r = client.post("/api/clasificacion-trazabilidad/lote")
    assert r.status_code == 200
    body = r.json()
    assert "procesados" in body and "cambios" in body
