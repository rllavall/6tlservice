from app import models
from app.ayuda_seed import CATALOGO_INICIAL, sembrar_ayuda


def test_sembrar_inserta_las_que_faltan(db_session):
    n = sembrar_ayuda(db_session)
    assert n == len(CATALOGO_INICIAL) and n > 0
    assert db_session.query(models.AyudaTopico).count() == n


def test_sembrar_es_idempotente(db_session):
    sembrar_ayuda(db_session)
    total = db_session.query(models.AyudaTopico).count()
    assert sembrar_ayuda(db_session) == 0           # segunda vez no inserta nada
    assert db_session.query(models.AyudaTopico).count() == total


def test_sembrar_no_pisa_texto_existente(db_session):
    clave = CATALOGO_INICIAL[0]["clave"]
    db_session.add(models.AyudaTopico(clave=clave, texto="MI TEXTO EDITADO"))
    db_session.commit()
    sembrar_ayuda(db_session)
    t = db_session.query(models.AyudaTopico).filter_by(clave=clave).first()
    assert t.texto == "MI TEXTO EDITADO"            # no se sobrescribe


def test_catalogo_sin_claves_duplicadas():
    claves = [item["clave"] for item in CATALOGO_INICIAL]
    assert len(claves) == len(set(claves))
