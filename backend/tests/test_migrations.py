from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.migrations import add_missing_columns


def _legacy_engine():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with eng.begin() as c:
        c.exec_driver_sql(
            "CREATE TABLE ubicaciones (id INTEGER PRIMARY KEY, nombre TEXT, ciudad TEXT)"
        )
    return eng


def _columnas(eng, tabla):
    with eng.connect() as c:
        rows = c.execute(text(f"PRAGMA table_info({tabla})")).fetchall()
    return {r[1] for r in rows}


def test_agrega_columnas_lat_lon_a_tabla_legacy():
    eng = _legacy_engine()
    add_missing_columns(eng)
    cols = _columnas(eng, "ubicaciones")
    assert "latitud" in cols
    assert "longitud" in cols


def test_es_idempotente():
    eng = _legacy_engine()
    add_missing_columns(eng)
    add_missing_columns(eng)  # no debe lanzar al re-ejecutar
    cols = _columnas(eng, "ubicaciones")
    assert "latitud" in cols and "longitud" in cols


def test_agrega_incidencia_id_a_tablas_legacy():
    # BD anterior al sub-proyecto Incidencias: faltan los FK incidencia_id.
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with eng.begin() as c:
        c.exec_driver_sql("CREATE TABLE movimientos (id INTEGER PRIMARY KEY, equipo_id INTEGER)")
        c.exec_driver_sql(
            "CREATE TABLE cambios_configuracion (id INTEGER PRIMARY KEY, equipo_id INTEGER)"
        )
    add_missing_columns(eng)
    assert "incidencia_id" in _columnas(eng, "movimientos")
    assert "incidencia_id" in _columnas(eng, "cambios_configuracion")


def test_agrega_columnas_garantia_y_tipo():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with eng.begin() as c:
        c.exec_driver_sql("CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT)")
        c.exec_driver_sql("CREATE TABLE equipos (id INTEGER PRIMARY KEY, numero_serie TEXT)")
        c.exec_driver_sql("CREATE TABLE incidencias (id INTEGER PRIMARY KEY, codigo TEXT)")
        c.exec_driver_sql("INSERT INTO incidencias (id, codigo) VALUES (1, 'RMA-0001')")
    add_missing_columns(eng)
    assert "meses_garantia_default" in _columnas(eng, "productos")
    assert "meses_garantia" in _columnas(eng, "equipos")
    assert "version" in _columnas(eng, "equipos")
    assert "numero_serie_cliente" in _columnas(eng, "equipos")
    assert "tipo" in _columnas(eng, "incidencias")
    with eng.connect() as c:
        fila = c.execute(text("SELECT tipo FROM incidencias WHERE id=1")).fetchone()
    assert fila[0] == "rma"


def test_agrega_columna_categoria_a_productos():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with eng.begin() as c:
        c.exec_driver_sql("CREATE TABLE productos (id INTEGER PRIMARY KEY, part_number TEXT)")
    add_missing_columns(eng)
    assert "categoria" in _columnas(eng, "productos")
