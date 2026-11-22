"""Writing an export into another organisation's database (Batch
Operations, administrators): SQLite, or PostgreSQL / MySQL when their
driver is installed. The target table is created with one TEXT column per
exported field if it is not there. Nothing about the connection is kept."""

from __future__ import annotations

import re

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _connect(config):
    kind = str(config.get("type") or "sqlite").lower()
    if kind == "sqlite":
        import sqlite3
        if not config.get("path"):
            raise ValueError("Give the SQLite file")
        return sqlite3.connect(config["path"]), "?"
    if kind == "postgresql":
        try:
            import psycopg2
        except ImportError:
            raise ValueError("PostgreSQL needs the psycopg2 package installed") from None
        return psycopg2.connect(host=config["host"], port=int(config.get("port") or 5432),
                                dbname=config["database"], user=config["user"],
                                password=config.get("password", "")), "%s"
    if kind == "mysql":
        try:
            import mysql.connector
        except ImportError:
            raise ValueError("MySQL needs the mysql-connector-python package installed") from None
        return mysql.connector.connect(host=config["host"], port=int(config.get("port") or 3306),
                                       database=config["database"], user=config["user"],
                                       password=config.get("password", "")), "%s"
    raise ValueError("Database type must be sqlite, postgresql or mysql")


def write_rows(config, table, columns, rows, replace=False) -> int:
    """Insert ``rows`` (dicts) into ``table``; returns how many."""
    if not _IDENT.match(table or "") or not all(_IDENT.match(c) for c in columns):
        raise ValueError("Table and column names may use letters, digits and _ only")
    target, mark = _connect(config)
    try:
        cur = target.cursor()
        cur.execute(f"CREATE TABLE IF NOT EXISTS {table} "  # nosec B608 - checked names
                    f"({', '.join(f'{c} TEXT' for c in columns)})")
        if replace:
            cur.execute(f"DELETE FROM {table}")  # nosec B608 - checked name
        marks = ", ".join(mark for _ in columns)
        cur.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({marks})",  # nosec B608
                        [tuple(None if r.get(c) is None else str(r.get(c)) for c in columns)
                         for r in rows])
        target.commit()
    finally:
        target.close()
    return len(rows)


def test_connection(config) -> str:
    """Connect and run ``SELECT 1``; nothing is written. A SQLite file that
    does not exist yet is reported, not created."""
    import os
    if str(config.get("type") or "sqlite").lower() == "sqlite":
        path = config.get("path")
        if not path:
            raise ValueError("Give the SQLite file")
        if not os.path.exists(path):
            return f"{path} does not exist yet; Send will create it"
    target, _mark = _connect(config)
    try:
        cur = target.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
    finally:
        target.close()
    return "connected"
