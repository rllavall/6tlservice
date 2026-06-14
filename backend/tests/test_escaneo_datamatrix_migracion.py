from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.migrations import add_missing_columns


def _cols(engine, tabla):
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({tabla})")).fetchall()
    return {r[1] for r in rows}


def test_migracion_anhade_regla_datamatrix_a_fabricantes():
    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE fabricantes (id INTEGER PRIMARY KEY, nombre TEXT)")
    add_missing_columns(eng)
    assert "regla_datamatrix" in _cols(eng, "fabricantes")


def test_migracion_es_idempotente_regla_datamatrix():
    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE fabricantes (id INTEGER PRIMARY KEY, nombre TEXT)")
    add_missing_columns(eng)
    add_missing_columns(eng)
    assert "regla_datamatrix" in _cols(eng, "fabricantes")
