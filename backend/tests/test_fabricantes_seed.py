# tests/test_fabricantes_seed.py
from app import fabricantes_seed, models


def test_siembra_crea_fabricantes_y_enlaza(db_session):
    db_session.add_all([
        models.Producto(part_number="P1", tipo="componente", descripcion="DMM", fabricante="National"),
        models.Producto(part_number="P2", tipo="componente", descripcion="Fuente", fabricante="National"),
        models.Producto(part_number="P3", tipo="componente", descripcion="Osc", fabricante="Keysight"),
        models.Producto(part_number="P4", tipo="equipo", descripcion="Banco", fabricante=None),
    ])
    db_session.commit()

    creados = fabricantes_seed.sembrar_fabricantes_desde_texto(db_session)
    db_session.commit()

    assert creados == 2  # National, Keysight
    nombres = {f.nombre for f in db_session.query(models.Fabricante).all()}
    assert nombres == {"National", "Keysight"}
    p1 = db_session.query(models.Producto).filter_by(part_number="P1").one()
    assert p1.fabricante_id is not None


def test_siembra_es_idempotente(db_session):
    db_session.add(models.Producto(part_number="P1", tipo="componente",
                                   descripcion="DMM", fabricante="National"))
    db_session.commit()
    assert fabricantes_seed.sembrar_fabricantes_desde_texto(db_session) == 1
    db_session.commit()
    assert fabricantes_seed.sembrar_fabricantes_desde_texto(db_session) == 0
    db_session.commit()
    assert db_session.query(models.Fabricante).count() == 1
