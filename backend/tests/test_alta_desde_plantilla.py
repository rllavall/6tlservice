"""Alta de equipo desde la plantilla: pre-rellena componentes según nivel."""
import pytest


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={
        "part_number": "ATE-PL", "tipo": "equipo", "descripcion": "Banco"}).json()["id"]


@pytest.fixture
def prod_inst(client):
    return client.post("/api/productos", json={
        "part_number": "DMM-9", "tipo": "componente", "descripcion": "Multímetro",
        "categoria_componente": "instrumento"}).json()["id"]


@pytest.fixture
def prod_sw(client):
    return client.post("/api/productos", json={
        "part_number": "SW-9", "tipo": "componente", "descripcion": "Firmware",
        "categoria_componente": "software"}).json()["id"]


@pytest.fixture
def prod_cable(client):
    return client.post("/api/productos", json={
        "part_number": "CBL-9", "tipo": "componente", "descripcion": "Cable",
        "categoria_componente": "wiring", "bajo_coste": True}).json()["id"]


def _plantilla(client, eq, comp, **kw):
    body = {"producto_componente_id": comp}
    body.update(kw)
    return client.post(f"/api/productos/{eq}/plantilla", json=body)


def test_alta_desde_plantilla_prellena_segun_nivel(client, prod_equipo, prod_inst, prod_sw, prod_cable):
    _plantilla(client, prod_equipo, prod_inst, posicion="A1")
    _plantilla(client, prod_equipo, prod_sw, posicion="SW")
    _plantilla(client, prod_equipo, prod_cable, posicion="W1", cantidad=3)

    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-PL-1", "producto_id": prod_equipo, "desde_plantilla": True})
    assert r.status_code == 201, r.text
    eq_id = r.json()["id"]

    comps = client.get(f"/api/componentes?equipo_id={eq_id}").json()
    assert len(comps) == 5  # 1 instrumento + 1 software + 3 cables

    inst = next(c for c in comps if c["producto_id"] == prod_inst)
    assert inst["nivel_trazabilidad"] == "serie"
    assert inst["numero_serie"].startswith("S/N pendiente")  # placeholder escaneable

    sw = next(c for c in comps if c["producto_id"] == prod_sw)
    assert sw["nivel_trazabilidad"] == "version"
    assert sw["numero_serie"] is None  # versión pendiente, sin serie

    cables = [c for c in comps if c["producto_id"] == prod_cable]
    assert len(cables) == 3
    assert all(c["numero_serie"] is None for c in cables)  # no trazado, sin serie


def test_alta_desde_plantilla_vacia_no_falla(client, prod_equipo):
    r = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-PL-VACIA", "producto_id": prod_equipo, "desde_plantilla": True})
    assert r.status_code == 201, r.text
    assert client.get(f"/api/componentes?equipo_id={r.json()['id']}").json() == []


def test_dos_altas_misma_plantilla_no_colisionan_series_nulas(client, prod_equipo, prod_cable):
    _plantilla(client, prod_equipo, prod_cable, posicion="W1", cantidad=2)
    r1 = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-A", "producto_id": prod_equipo, "desde_plantilla": True})
    r2 = client.post("/api/equipos/alta", json={
        "numero_serie": "EQ-B", "producto_id": prod_equipo, "desde_plantilla": True})
    assert r1.status_code == 201 and r2.status_code == 201, (r1.text, r2.text)
