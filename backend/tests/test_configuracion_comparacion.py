"""Comparación config real vs esperada (plantilla)."""
import pytest


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={
        "part_number": "ATE-CFG", "tipo": "equipo", "descripcion": "Banco"}).json()["id"]


@pytest.fixture
def prod_inst(client):
    return client.post("/api/productos", json={
        "part_number": "DMM-C", "tipo": "componente", "descripcion": "Multímetro",
        "categoria_componente": "instrumento"}).json()["id"]


@pytest.fixture
def prod_sw(client):
    return client.post("/api/productos", json={
        "part_number": "SW-C", "tipo": "componente", "descripcion": "Firmware",
        "categoria_componente": "software"}).json()["id"]


@pytest.fixture
def prod_cable(client):
    return client.post("/api/productos", json={
        "part_number": "CBL-C", "tipo": "componente", "descripcion": "Cable",
        "categoria_componente": "wiring", "bajo_coste": True}).json()["id"]


def _pl(client, eq, comp, **kw):
    return client.post(f"/api/productos/{eq}/plantilla", json={"producto_componente_id": comp, **kw})


def test_alta_desde_plantilla_marca_pendientes(client, prod_equipo, prod_inst, prod_sw, prod_cable):
    _pl(client, prod_equipo, prod_inst, posicion="A1")
    _pl(client, prod_equipo, prod_sw, posicion="SW")
    _pl(client, prod_equipo, prod_cable, posicion="W1", cantidad=2)

    eq_id = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-CFG-1", "producto_id": prod_equipo, "desde_plantilla": True}).json()["id"]

    cfg = client.get(f"/api/equipos/{eq_id}/configuracion").json()
    res = cfg["resumen"]
    assert res["esperados"] == 4         # 1 + 1 + 2
    assert res["presentes"] == 4
    assert res["faltantes"] == 0
    assert res["sobrantes"] == 0
    assert res["series_pendientes"] == 1     # el instrumento, placeholder
    assert res["versiones_pendientes"] == 1  # el software, sin revisión
    assert res["completo"] is False

    # capturar la serie del instrumento y poner la revisión del software -> completo
    comps = client.get(f"/api/componentes?equipo_id={eq_id}").json()
    inst = next(c for c in comps if c["producto_id"] == prod_inst)
    sw = next(c for c in comps if c["producto_id"] == prod_sw)
    client.patch(f"/api/componentes/{inst['id']}", json={"numero_serie": "REAL-DMM-1"})
    client.patch(f"/api/componentes/{sw['id']}", json={"revision": "v2.1"})

    cfg2 = client.get(f"/api/equipos/{eq_id}/configuracion").json()
    assert cfg2["resumen"]["series_pendientes"] == 0
    assert cfg2["resumen"]["versiones_pendientes"] == 0
    assert cfg2["resumen"]["completo"] is True


def test_faltantes_y_sobrantes(client, prod_equipo, prod_inst, prod_cable):
    _pl(client, prod_equipo, prod_inst, posicion="A1", cantidad=2)  # se esperan 2 instrumentos

    eq_id = client.post("/api/equipos", json={
        "numero_serie": "EQ-CFG-2", "producto_id": prod_equipo}).json()["id"]
    # monta 1 instrumento (falta 1) y 1 cable NO esperado (sobrante)
    client.post("/api/componentes", json={
        "numero_serie": "DMM-X", "producto_id": prod_inst, "equipo_id": eq_id, "posicion": "A1"})
    client.post("/api/componentes", json={
        "producto_id": prod_cable, "equipo_id": eq_id, "posicion": "Z9"})

    cfg = client.get(f"/api/equipos/{eq_id}/configuracion").json()
    linea_inst = next(l for l in cfg["lineas"] if l["producto_componente_id"] == prod_inst)
    assert linea_inst["cantidad_esperada"] == 2
    assert linea_inst["cantidad_presente"] == 1
    assert linea_inst["faltan"] == 1
    assert cfg["resumen"]["faltantes"] == 1
    assert cfg["resumen"]["sobrantes"] == 1
    assert cfg["sobrantes"][0]["part_number"] == "CBL-C"


def test_configuracion_equipo_inexistente_404(client):
    assert client.get("/api/equipos/99999/configuracion").status_code == 404
