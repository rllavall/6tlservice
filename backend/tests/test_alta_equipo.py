import pytest


@pytest.fixture
def prod_equipo(client):
    return client.post("/api/productos", json={
        "part_number": "ATE-1000", "tipo": "equipo", "descripcion": "Sistema",
        "meses_garantia_default": 24,
    }).json()["id"]


@pytest.fixture
def prod_componente(client):
    return client.post("/api/productos", json={
        "part_number": "PXI-5122", "tipo": "componente", "descripcion": "Digi",
    }).json()["id"]


@pytest.fixture
def cliente(client):
    return client.post("/api/clientes", json={"nombre": "Indra"}).json()["id"]


@pytest.fixture
def ubicacion(client, cliente):
    return client.post("/api/ubicaciones", json={
        "nombre": "Planta Aranjuez", "tipo": "fabrica_cliente", "cliente_id": cliente,
    }).json()["id"]


def test_alta_schema_defaults():
    from app.schemas import EquipoAltaCreate
    p = EquipoAltaCreate(numero_serie="EQ-1", producto_id=1)
    assert p.estado == "operativo"
    assert p.componentes == []
    assert p.ubicacion_id is None
