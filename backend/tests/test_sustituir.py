import pytest


@pytest.fixture
def setup(client):
    pe = client.post("/api/productos", json={"part_number": "ATE", "tipo": "equipo", "descripcion": "x"}).json()["id"]
    pc = client.post("/api/productos", json={"part_number": "PXI", "tipo": "componente", "descripcion": "y"}).json()["id"]
    eq = client.post("/api/equipos", json={"numero_serie": "EQ", "producto_id": pe}).json()["id"]
    saliente = client.post("/api/componentes", json={"numero_serie": "OLD", "producto_id": pc}).json()["id"]
    entrante = client.post("/api/componentes", json={"numero_serie": "NEW", "producto_id": pc}).json()["id"]
    client.post(f"/api/componentes/{saliente}/montar", json={"equipo_id": eq, "posicion": "r3", "fecha": "2026-01-01", "motivo": "entrega_inicial"})
    return {"equipo": eq, "saliente": saliente, "entrante": entrante}


def test_sustituir_swaps_and_logs_both(client, setup):
    r = client.post(f"/api/equipos/{setup['equipo']}/sustituir-componente", json={
        "componente_saliente_id": setup["saliente"],
        "componente_entrante_id": setup["entrante"],
        "posicion": "r3", "fecha": "2026-05-01", "motivo": "sustitucion",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["desmontaje"]["accion"] == "desmontaje"
    assert body["montaje"]["accion"] == "montaje"

    old = client.get(f"/api/componentes/{setup['saliente']}").json()
    new = client.get(f"/api/componentes/{setup['entrante']}").json()
    assert old["equipo_id"] is None
    assert new["equipo_id"] == setup["equipo"]
    assert new["posicion"] == "r3"


def test_sustituir_entrante_already_mounted_is_atomic_409(client, setup):
    # Mount entrante on same equipo first to force a conflict on the montaje half.
    client.post(f"/api/componentes/{setup['entrante']}/montar", json={"equipo_id": setup["equipo"], "fecha": "2026-02-01", "motivo": "upgrade"})
    r = client.post(f"/api/equipos/{setup['equipo']}/sustituir-componente", json={
        "componente_saliente_id": setup["saliente"],
        "componente_entrante_id": setup["entrante"],
        "fecha": "2026-05-01", "motivo": "sustitucion",
    })
    assert r.status_code == 409
    # Atomicity: saliente must remain mounted (rollback of the desmontaje).
    old = client.get(f"/api/componentes/{setup['saliente']}").json()
    assert old["equipo_id"] == setup["equipo"]
