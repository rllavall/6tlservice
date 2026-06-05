def _equipo_vencido(client):
    prod = client.post("/api/productos", json={
        "part_number": "6TL-AVA", "tipo": "equipo", "descripcion": "Banco"}).json()
    con = client.post("/api/contratos", json={
        "nivel": "bronze", "fecha_inicio": "2020-01-01", "fecha_fin": "2100-01-01"}).json()
    eq = client.post("/api/equipos", json={
        "numero_serie": "AV1", "producto_id": prod["id"]}).json()
    client.post(f"/api/contratos/{con['id']}/equipos", json={"equipo_id": eq["id"]})
    return eq["id"], con


def test_avisos_lista_preventivo_vencido(client):
    eid, _ = _equipo_vencido(client)
    out = client.get("/api/avisos").json()
    ids = [a["equipo"]["id"] for a in out["preventivos"]]
    assert eid in ids
    aviso = next(a for a in out["preventivos"] if a["equipo"]["id"] == eid)
    assert aviso["bucket"] == "vencido"
    assert aviso["contrato"]["nivel"] == "bronze"
    assert out["resumen"]["preventivos_vencidos"] >= 1


def test_avisos_shape(client):
    out = client.get("/api/avisos").json()
    assert "contratos_por_caducar" in out and isinstance(out["contratos_por_caducar"], list)
    assert set(out["resumen"].keys()) == {"preventivos_vencidos", "preventivos_proximos", "contratos_por_caducar"}


def test_avisos_protegido_401(client_sin_auth):
    assert client_sin_auth.get("/api/avisos").status_code == 401
