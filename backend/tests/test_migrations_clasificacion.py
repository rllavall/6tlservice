from sqlalchemy import create_engine, text

from app import migrations


def _crear_db_sin_columnas(path_url):
    eng = create_engine(path_url)
    with eng.begin() as c:
        c.exec_driver_sql(
            "CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT,"
            " tipo TEXT, descripcion TEXT)")
    return eng


def test_migracion_anade_columnas_clasificacion(tmp_path):
    url = f"sqlite:///{tmp_path/'m.db'}"
    eng = _crear_db_sin_columnas(url)
    migrations.add_missing_columns(eng)
    with eng.connect() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(productos)"))}
    assert "clasificacion_origen" in cols
    assert "clasificacion_motivo" in cols


def test_migracion_es_idempotente(tmp_path):
    url = f"sqlite:///{tmp_path/'m.db'}"
    eng = _crear_db_sin_columnas(url)
    migrations.add_missing_columns(eng)
    migrations.add_missing_columns(eng)  # no debe lanzar
    with eng.connect() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(productos)"))}
    assert "clasificacion_origen" in cols
