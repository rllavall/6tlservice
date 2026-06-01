import pytest


@pytest.fixture
def setup(client):
    pe = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "x"}).json()["id"]
    pc = client.post("/api/productos", json={"part_number": "PXI", "tipo": "componente", "descripcion": "y"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "EQ", "producto_id": pe}).json()["id"]
    comp = client.post("/api/componentes", json={"numero_serie": "C", "producto_id": pc}).json()["id"]
    return {"equipo": eq, "componente": comp}


def test_montar_sets_state_and_logs(client, setup):
    r = client.post(f"/api/componentes/{setup['componente']}/montar",
                    json={"equipo_id": setup["equipo"], "posicion": "ranura 3", "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    assert r.status_code == 201, r.text
    assert r.json()["accion"] == "montaje"

    comp = client.get(f"/api/componentes/{setup['componente']}").json()
    assert comp["equipo_id"] == setup["equipo"]
    assert comp["posicion"] == "ranura 3"

    listed = client.get(f"/api/componentes?equipo_id={setup['equipo']}").json()
    assert len(listed) == 1


def test_montar_already_mounted_409(client, setup):
    body = {"equipo_id": setup["equipo"], "fecha": "2026-01-01", "motivo": "entrega_inicial"}
    client.post(f"/api/componentes/{setup['componente']}/montar", json=body)
    r = client.post(f"/api/componentes/{setup['componente']}/montar", json=body)
    assert r.status_code == 409


def test_desmontar_clears_state(client, setup):
    client.post(f"/api/componentes/{setup['componente']}/montar",
                json={"equipo_id": setup["equipo"], "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    r = client.post(f"/api/componentes/{setup['componente']}/desmontar", json={"fecha": "2026-02-01", "motivo": "retirada"})
    assert r.status_code == 201, r.text
    assert r.json()["accion"] == "desmontaje"
    comp = client.get(f"/api/componentes/{setup['componente']}").json()
    assert comp["equipo_id"] is None


def test_desmontar_when_not_mounted_409(client, setup):
    r = client.post(f"/api/componentes/{setup['componente']}/desmontar", json={"fecha": "2026-02-01", "motivo": "retirada"})
    assert r.status_code == 409
