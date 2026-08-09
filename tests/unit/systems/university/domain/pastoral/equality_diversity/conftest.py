"""Shared fixtures for the Equality & Diversity service-layer tests.

The whole E&D package reaches the database through a single choke point:
``schema.get_connection()``, which opens ``sqlite3.connect(str(DEFAULT_DB_PATH))``
using the module-global ``schema.DEFAULT_DB_PATH``. Every other module
(``access``, ``integrations``, ``reports_engine``) imports that same
``get_connection`` function, so patching ``schema.DEFAULT_DB_PATH`` to a temp
file redirects the entire package at once — no per-module patching needed and
never a touch on the real ``student_records.db``.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.university.domain.pastoral.equality_diversity import (
    schema,
)


@pytest.fixture(autouse=True)
def ed_db(tmp_path, monkeypatch):
    """Point the whole E&D package at a fresh temp DB and migrate the schema."""
    db_path = str(tmp_path / "ed.db")
    monkeypatch.setattr(schema, "DEFAULT_DB_PATH", db_path)
    schema.migrate()
    return db_path


@pytest.fixture()
def raw(ed_db):
    """Return a factory opening a plain connection to the temp DB (for
    seeding parent tables and asserting on rows out-of-band)."""

    def _connect():
        conn = sqlite3.connect(ed_db)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    return _connect


# --- helpers to stand up the "central" university tables the integrations /
#     reports layers LEFT JOIN against. They live in the same DB file. -------

@pytest.fixture()
def mk_students(raw):
    def _mk(rows):
        conn = raw()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS students ("
            "student_id TEXT, first_name TEXT, last_name TEXT, "
            "email_address TEXT, gender TEXT, dob TEXT, course TEXT, "
            "year_of_study INTEGER, status TEXT)"
        )
        conn.executemany(
            "INSERT INTO students (student_id, first_name, last_name, "
            "email_address, gender, dob, course, year_of_study, status) "
            "VALUES (:student_id, :first_name, :last_name, :email_address, "
            ":gender, :dob, :course, :year_of_study, :status)",
            rows,
        )
        conn.commit()
        conn.close()

    return _mk


@pytest.fixture()
def mk_staff(raw):
    def _mk(rows, full=True):
        conn = raw()
        if full:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS staff ("
                "id INTEGER, username TEXT, name TEXT, email TEXT, role TEXT, "
                "department TEXT, status TEXT)"
            )
            conn.executemany(
                "INSERT INTO staff (id, username, name, email, role, "
                "department, status) VALUES (:id, :username, :name, :email, "
                ":role, :department, :status)",
                rows,
            )
        else:
            # bare install: no department/status columns → forces the
            # OperationalError fallback path in sync_from_staff
            conn.execute(
                "CREATE TABLE IF NOT EXISTS staff ("
                "id INTEGER, username TEXT, name TEXT, email TEXT, role TEXT)"
            )
            conn.executemany(
                "INSERT INTO staff (id, username, name, email, role) "
                "VALUES (:id, :username, :name, :email, :role)",
                rows,
            )
        conn.commit()
        conn.close()

    return _mk


@pytest.fixture()
def mk_table(raw):
    """Generic create-and-fill for the small cross-domain join tables."""

    def _mk(ddl, insert_sql, rows):
        conn = raw()
        conn.execute(ddl)
        if rows:
            conn.executemany(insert_sql, rows)
        conn.commit()
        conn.close()

    return _mk
