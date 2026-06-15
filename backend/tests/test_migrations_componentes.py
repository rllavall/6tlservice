"""La micro-migración relaja numero_serie a NULLable en BDs antiguas (rebuild)."""
from sqlalchemy import create_engine, text

from app.migrations import add_missing_columns


def _crear_componentes_antiguo(engine):
    """Esquema antiguo: numero_serie NOT NULL, sin columna revision."""
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE componentes ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " numero_serie VARCHAR NOT NULL,"
            " producto_id INTEGER NOT NULL,"
            " equipo_id INTEGER,"
            " posicion VARCHAR,"
            " fecha_montaje DATE,"
            " notas VARCHAR,"
            " UNIQUE (producto_id, numero_serie))"
        )
        conn.exec_driver_sql(
            "INSERT INTO componentes (numero_serie, producto_id, posicion)"
            " VALUES ('SN-REAL', 7, 'A1')"
        )


def _numero_serie_notnull(conn) -> int:
    for r in conn.execute(text("PRAGMA table_info(componentes)")).fetchall():
        if r[1] == "numero_serie":
            return r[3]  # notnull flag
    raise AssertionError("columna numero_serie no encontrada")


def test_migracion_relaja_notnull_y_anade_revision_preservando_filas():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    _crear_componentes_antiguo(eng)

    with eng.begin() as conn:
        assert _numero_serie_notnull(conn) == 1  # antes: NOT NULL

    add_missing_columns(eng)

    with eng.begin() as conn:
        assert _numero_serie_notnull(conn) == 0  # ahora: NULLable
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(componentes)")).fetchall()}
        assert "revision" in cols
        # fila antigua preservada
        fila = conn.execute(text("SELECT numero_serie, producto_id, posicion FROM componentes")).fetchone()
        assert fila == ("SN-REAL", 7, "A1")
        # ahora se puede insertar serie NULL (no_trazado)
        conn.exec_driver_sql("INSERT INTO componentes (numero_serie, producto_id) VALUES (NULL, 9)")
        conn.exec_driver_sql("INSERT INTO componentes (numero_serie, producto_id) VALUES (NULL, 10)")
        n = conn.execute(text("SELECT COUNT(*) FROM componentes WHERE numero_serie IS NULL")).scalar()
        assert n == 2


def test_migracion_es_idempotente():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    _crear_componentes_antiguo(eng)
    add_missing_columns(eng)
    add_missing_columns(eng)  # segunda pasada no debe romper ni duplicar
    with eng.begin() as conn:
        assert _numero_serie_notnull(conn) == 0
        n = conn.execute(text("SELECT COUNT(*) FROM componentes")).scalar()
        assert n == 1
