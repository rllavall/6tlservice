"""La API expone criticidad/nivel_trazabilidad derivados y persiste los campos nuevos."""


def _crear_producto(client, **kw):
    base = {"part_number": kw.pop("pn"), "tipo": "componente", "descripcion": "x"}
    base.update(kw)
    r = client.post("/api/productos", json=base)
    assert r.status_code == 201, r.text
    return r.json()


def test_producto_instrumento_es_alta_serie(client):
    p = _crear_producto(client, pn="INST-1", categoria_componente="instrumento")
    assert p["criticidad"] == "alta"
    assert p["nivel_trazabilidad"] == "serie"


def test_producto_software_es_version(client):
    p = _crear_producto(client, pn="SW-1", categoria_componente="software")
    assert p["criticidad"] == "alta"
    assert p["nivel_trazabilidad"] == "version"


def test_producto_bajo_coste_es_no_trazado(client):
    p = _crear_producto(client, pn="CAB-1", categoria_componente="wiring", bajo_coste=True)
    assert p["criticidad"] == "baja"
    assert p["nivel_trazabilidad"] == "no_trazado"


def test_override_persiste_y_gana(client):
    p = _crear_producto(client, pn="INST-2", categoria_componente="instrumento",
                        nivel_trazabilidad_override="no_trazado")
    assert p["nivel_trazabilidad_override"] == "no_trazado"
    assert p["nivel_trazabilidad"] == "no_trazado"  # override gana
    assert p["criticidad"] == "alta"                # criticidad no la cambia


def test_componente_expone_nivel_y_persiste_revision_y_serie_nula(client):
    p = _crear_producto(client, pn="FIX-1", categoria_componente="fixture_adaptador")
    r = client.post("/api/componentes", json={
        "producto_id": p["id"], "numero_serie": None, "revision": "Rev C"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["numero_serie"] is None
    assert body["revision"] == "Rev C"
    assert body["nivel_trazabilidad"] == "version"
