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
}


def _columnas_existentes(conn, tabla: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({tabla})")).fetchall()
    return {r[1] for r in rows}


def add_missing_columns(engine: Engine) -> None:
    """Añade columnas declaradas en `_COLUMNAS_NUEVAS` que falten. Idempotente."""
    with engine.begin() as conn:
        for tabla, columnas in _COLUMNAS_NUEVAS.items():
            existentes = _columnas_existentes(conn, tabla)
            if not existentes:
                continue  # la tabla no existe todavía (create_all la creará completa)
            for col, tipo in columnas.items():
                if col not in existentes:
                    conn.exec_driver_sql(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
