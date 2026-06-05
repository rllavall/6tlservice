import pytest
from sqlalchemy.exc import IntegrityError

from app import models


def test_crea_topico(db_session):
    t = models.AyudaTopico(clave="equipos.estado", titulo="Estado", texto="Operativo o baja.", pantalla="equipos")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    assert t.id is not None and t.clave == "equipos.estado"


def test_titulo_y_pantalla_opcionales(db_session):
    t = models.AyudaTopico(clave="x.y", texto="solo texto")
    db_session.add(t)
    db_session.commit()
    assert t.titulo is None and t.pantalla is None


def test_clave_unica(db_session):
    db_session.add(models.AyudaTopico(clave="dup", texto="a"))
    db_session.commit()
    db_session.add(models.AyudaTopico(clave="dup", texto="b"))
    with pytest.raises(IntegrityError):
        db_session.commit()
