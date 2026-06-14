"""Micro-migraciones idempotentes para SQLite.

`create_all` no añade columnas a tablas ya existentes; esto rellena ese hueco
para la BD persistente sin perder datos (ALTER TABLE ADD COLUMN si falta).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# tabla -> {columna: tipo SQL}
_COLUMNAS_NUEVAS: dict[str, dict[str, str]] = {
    "ubicaciones": {"latitud": "FLOAT", "longitud": "FLOAT"},
    # FKs añadidos por el sub-proyecto Incidencias; BDs anteriores no los tienen.
    "movimientos": {"incidencia_id": "INTEGER"},
    "cambios_configuracion": {"incidencia_id": "INTEGER"},
    # Garantía + tipo de incidencia (sub-proyecto analítica).
    "productos": {"meses_garantia_default": "INTEGER DEFAULT 24", "categoria": "TEXT",
                  "pn_fabricante": "TEXT", "fabricante_id": "INTEGER",
                  "categoria_componente": "TEXT",
                  "afecta_a_medida": "BOOLEAN NOT NULL DEFAULT 0",
                  "bajo_coste": "BOOLEAN NOT NULL DEFAULT 0",
                  "nivel_trazabilidad_override": "TEXT",
                  "estado_ciclo_vida": "TEXT", "ciclo_vida_fecha": "DATE",
                  "ciclo_vida_url": "TEXT", "ciclo_vida_resumen": "TEXT",
                  "ciclo_vida_verificado_en": "DATE", "ciclo_vida_cita": "TEXT",
                  "ciclo_vida_origen": "TEXT"},
    "componentes": {"revision": "TEXT"},
    "fabricantes": {"url_obsolescencia": "TEXT", "regla_datamatrix": "TEXT"},
    "noticias_obsolescencia": {"cita": "TEXT", "origen": "TEXT"},
    "equipos": {"meses_garantia": "INTEGER", "version": "TEXT", "numero_serie_cliente": "TEXT", "contrato_id": "INTEGER"},
    "incidencias": {"tipo": "TEXT NOT NULL DEFAULT 'rma'", "creada_en": "DATETIME",
                    "respondida_en": "DATETIME", "resuelta_en": "DATETIME"},
}


def _columnas_existentes(conn, tabla: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({tabla})")).fetchall()
    return {r[1] for r in rows}


# Esquema canónico de `componentes` con numero_serie NULLable (espejo del ORM).
# SQLite no relaja NOT NULL con ALTER TABLE, así que en BDs antiguas hay que
# reconstruir la tabla. Se crea con nombre temporal (que nadie referencia) y se
# renombra al final, evitando que el rename reescriba las FKs de otras tablas.
_COMPONENTES_DDL = (
    "CREATE TABLE componentes_new ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " numero_serie VARCHAR,"
    " producto_id INTEGER NOT NULL REFERENCES productos(id),"
    " equipo_id INTEGER REFERENCES equipos(id),"
    " posicion VARCHAR,"
    " revision VARCHAR,"
    " fecha_montaje DATE,"
    " notas VARCHAR,"
    " CONSTRAINT uq_componente_serie UNIQUE (producto_id, numero_serie))"
)


def _rebuild_componentes_si_notnull(engine: Engine) -> None:
    """Si `componentes.numero_serie` es NOT NULL (BD antigua), reconstruye la tabla
    para hacerlo NULLable (y añade `revision`), preservando las filas. Idempotente."""
    with engine.begin() as conn:
        info = conn.execute(text("PRAGMA table_info(componentes)")).fetchall()
        if not info:
            return  # la tabla no existe; create_all la creará con el esquema nuevo
        ns = next((r for r in info if r[1] == "numero_serie"), None)
        if ns is None or ns[3] == 0:
            return  # ya es NULLable
        cols_old = [r[1] for r in info]
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS componentes_new")
        conn.exec_driver_sql(_COMPONENTES_DDL)
        new_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(componentes_new)")).fetchall()]
        comunes = ", ".join(c for c in cols_old if c in new_cols)
        conn.exec_driver_sql(
            f"INSERT INTO componentes_new ({comunes}) SELECT {comunes} FROM componentes")
        conn.exec_driver_sql("DROP TABLE componentes")
        conn.exec_driver_sql("ALTER TABLE componentes_new RENAME TO componentes")


def add_missing_columns(engine: Engine) -> None:
    """Añade columnas declaradas en `_COLUMNAS_NUEVAS` que falten. Idempotente."""
    _rebuild_componentes_si_notnull(engine)
    with engine.begin() as conn:
        for tabla, columnas in _COLUMNAS_NUEVAS.items():
            existentes = _columnas_existentes(conn, tabla)
            if not existentes:
                continue  # la tabla no existe todavía (create_all la creará completa)
            for col, tipo in columnas.items():
                if col not in existentes:
                    conn.exec_driver_sql(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
