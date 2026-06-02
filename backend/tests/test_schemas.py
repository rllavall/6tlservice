from datetime import date

from app import models, schemas


def test_equipo_out_from_orm(db_session):
    p = models.Producto(part_number="ATE-1", tipo="equipo", descripcion="x")
    db_session.add(p)
    db_session.flush()
    eq = models.Equipo(numero_serie="S", producto_id=p.id, fecha_entrega=date(2026, 1, 1))
    db_session.add(eq)
    db_session.flush()
    out = schemas.EquipoOut.model_validate(eq)
    assert out.numero_serie == "S"
    assert out.producto_id == p.id


def test_producto_create_requires_tipo():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        schemas.ProductoCreate(part_number="x", descripcion="y")  # tipo missing
