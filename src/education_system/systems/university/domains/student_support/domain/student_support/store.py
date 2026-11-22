"""Connections to the support database.

Every support module opens the database through :func:`connect`, so the
path is read at call time from ``config.SUPPORT_DB`` (tests and scratch runs
repoint it there) and every connection is the managed one from the
university ``db`` module (foreign keys on, closed by ``with``).
"""

from __future__ import annotations

from contextlib import contextmanager

from education_system.systems.university.infrastructure.database.db import sqlite3


def connect(row_factory: bool = True, timeout: float = 30):
    """A new connection to the support database (``with`` commits and closes)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        config,
    )
    conn = sqlite3.connect(config.SUPPORT_DB, timeout=timeout)
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def reading():
    """A read connection that is always closed."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def writing():
    """One write transaction: committed on success, rolled back on error,
    always closed. Nothing slow (files, e-mail, other connections) belongs
    inside it."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
