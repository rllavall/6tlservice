import pytest


@pytest.fixture
def prod_componente(client):
    return client.post("/api/productos", json={"part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digi"}).json()["id"]


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={"part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema"}).json()["id"]


def test_componente_create_unassigned(client, prod_componente):
    r = client.post("/api/componentes", json={"numero_serie": "C-1", "producto_id": prod_componente})
    assert r.status_code == 201, r.text
    assert r.json()["equipo_id"] is None


def test_componente_rejects_equipo_producto(client, prod_equipo):
    r = client.post("/api/componentes", json={"numero_serie": "C", "producto_id": prod_equipo})
    assert r.status_code == 409
    assert "componente" in r.json()["detail"].lower()


def test_componente_list_and_update(client, prod_componente):
    cid = client.post("/api/componentes", json={"numero_serie": "C-2", "producto_id": prod_componente}).json()["id"]
    r = client.get("/api/componentes")
    assert any(c["id"] == cid for c in r.json())
    r = client.put(f"/api/componentes/{cid}", json={"numero_serie": "C-2", "producto_id": prod_componente, "notas": "ok"})
    assert r.json()["notas"] == "ok"


def test_patch_componente_actualiza_serie_sin_desmontar(client, prod_componente, prod_equipo):
    eq = client.post("/api/equipos", json={"numero_serie": "SN-P", "producto_id": prod_equipo}).json()
    comp = client.post("/api/componentes", json={
        "numero_serie": "S/N pendiente (10)", "producto_id": prod_componente,
        "equipo_id": eq["id"], "posicion": "10", "fecha_montaje": "2026-06-01",
    }).json()
    r = client.patch(f"/api/componentes/{comp['id']}", json={"numero_serie": "REAL-12345"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["numero_serie"] == "REAL-12345"
    # sigue montado y conserva el resto de datos (no se desmonta)
    assert body["equipo_id"] == eq["id"]
    assert body["posicion"] == "10"
    assert body["fecha_montaje"] == "2026-06-01"


def test_patch_componente_serie_duplicada_409(client, prod_componente):
    client.post("/api/componentes", json={"numero_serie": "A", "producto_id": prod_componente})
    c2 = client.post("/api/componentes", json={"numero_serie": "B", "producto_id": prod_componente}).json()
    r = client.patch(f"/api/componentes/{c2['id']}", json={"numero_serie": "A"})
    assert r.status_code == 409


def test_patch_componente_404(client):
    r = client.patch("/api/componentes/99999", json={"numero_serie": "X"})
    assert r.status_code == 404


def test_componente_expone_categoria_del_producto(client):
    p = client.post("/api/productos", json={
        "part_number": "PN-YAV", "tipo": "componente", "descripcion": "Modulo YAV", "categoria": "yav_module",
    }).json()
    r = client.post("/api/componentes", json={"numero_serie": "YAV-1", "producto_id": p["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["categoria"] == "yav_module"


def test_modelo_componente_categoria_componente_property(db_session):
    from app import models
    p = models.Producto(part_number="P-MOD", tipo="componente", descripcion="x",
                        categoria_componente="wiring")
    db_session.add(p)
    db_session.flush()
    c = models.Componente(numero_serie="S-MOD", producto_id=p.id)
    db_session.add(c)
    db_session.flush()
    db_session.refresh(c)
    assert c.categoria_componente == "wiring"


def test_componente_hereda_categoria_componente_del_producto(client):
    prod = client.post("/api/productos", json={
        "part_number": "VP-510104206", "tipo": "componente", "descripcion": "Receiver module",
        "categoria_componente": "mass_interconnect",
    }).json()
    eq_prod = client.post("/api/productos", json={
        "part_number": "EQ-CC", "tipo": "equipo", "descripcion": "Equipo",
    }).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-CC", "producto_id": eq_prod["id"]}).json()
    comp = client.post("/api/componentes", json={
        "numero_serie": "C-1", "producto_id": prod["id"], "equipo_id": eq["id"],
    }).json()
    assert comp["categoria_componente"] == "mass_interconnect"


def test_componentes_filtra_por_categoria_componente(client):
    eq_prod = client.post("/api/productos", json={
        "part_number": "EQ-F", "tipo": "equipo", "descripcion": "Equipo",
    }).json()
    eq = client.post("/api/equipos", json={"numero_serie": "SN-F", "producto_id": eq_prod["id"]}).json()
    p_ins = client.post("/api/productos", json={
        "part_number": "INS-F", "tipo": "componente", "descripcion": "DMM",
        "categoria_componente": "instrumento",
    }).json()
    p_wir = client.post("/api/productos", json={
        "part_number": "WIR-F", "tipo": "componente", "descripcion": "Cable",
        "categoria_componente": "wiring",
    }).json()
    client.post("/api/componentes", json={"numero_serie": "CI", "producto_id": p_ins["id"], "equipo_id": eq["id"]})
    client.post("/api/componentes", json={"numero_serie": "CW", "producto_id": p_wir["id"], "equipo_id": eq["id"]})

    r = client.get("/api/componentes?categoria_componente=instrumento")
    assert r.status_code == 200
    series = {c["numero_serie"] for c in r.json()}
    assert series == {"CI"}
