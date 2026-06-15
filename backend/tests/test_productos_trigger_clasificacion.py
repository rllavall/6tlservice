def _payload(**kw):
    base = dict(part_number="PN1", tipo="componente", descripcion="DMM 6.5",
                categoria_componente="instrumento")
    base.update(kw)
    return base


def test_crear_sin_flags_aplica_reglas(client):
    r = client.post("/api/productos", json=_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["afecta_a_medida"] is True
    assert body["clasificacion_origen"] == "agente"


def test_crear_con_flag_explicito_es_manual(client):
    r = client.post("/api/productos", json=_payload(afecta_a_medida=False))
    assert r.status_code == 201
    body = r.json()
    assert body["clasificacion_origen"] == "manual"
    assert body["afecta_a_medida"] is False  # respeta lo que mando el usuario


def test_actualizar_con_override_es_manual(client):
    cid = client.post("/api/productos", json=_payload()).json()["id"]
    r = client.put(f"/api/productos/{cid}",
                   json=_payload(nivel_trazabilidad_override="no_trazado"))
    assert r.status_code == 200
    assert r.json()["clasificacion_origen"] == "manual"


def test_actualizar_sin_flags_reaplica_reglas(client):
    cid = client.post("/api/productos", json=_payload()).json()["id"]
    r = client.put(f"/api/productos/{cid}",
                   json=_payload(descripcion="Patch cord generico", categoria_componente="wiring"))
    assert r.status_code == 200
    body = r.json()
    assert body["bajo_coste"] is True
    assert body["clasificacion_origen"] == "agente"


def test_put_sin_flags_no_pisa_valores_manuales(client):
    # Producto manual con bajo_coste=True fijado a mano.
    cid = client.post("/api/productos", json=_payload(
        categoria_componente="wiring", bajo_coste=True, afecta_a_medida=False)).json()["id"]
    # PUT que solo cambia la descripcion, SIN reenviar los flags.
    r = client.put(f"/api/productos/{cid}", json=dict(
        part_number="PN1", tipo="componente", descripcion="otra desc",
        categoria_componente="wiring"))
    assert r.status_code == 200
    body = r.json()
    assert body["clasificacion_origen"] == "manual"  # sigue manual
    assert body["bajo_coste"] is True  # NO se pierde el valor manual


def test_put_sin_override_no_pisa_override_manual(client):
    cid = client.post("/api/productos", json=_payload(
        nivel_trazabilidad_override="no_trazado")).json()["id"]
    r = client.put(f"/api/productos/{cid}", json=dict(
        part_number="PN1", tipo="componente", descripcion="otra",
        categoria_componente="instrumento"))
    assert r.status_code == 200
    body = r.json()
    assert body["clasificacion_origen"] == "manual"
    assert body["nivel_trazabilidad_override"] == "no_trazado"  # preservado
