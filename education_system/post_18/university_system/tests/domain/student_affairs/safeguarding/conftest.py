"""Shared fixtures for the safeguarding service-layer tests.

The whole safeguarding package reaches the database through a single choke
point: ``safeguarding.db._connect`` does a *local* ``from ...infrastructure
.database.db import get_connection`` on every call. Patching that one
``get_connection`` attribute therefore redirects every service module
(cases / risk / analytics / submissions / …) at once, with no per-module
patching required.

Each test gets a throwaway SQLite file with the safeguarding schema already
migrated in via ``init_db``. ``synchronous=OFF`` is safe here — the DB is
disposable — and avoids the per-commit fsync cost that dominates a suite
where every service call opens its own short-lived connection.
"""

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3

_SAFEGUARDING = (
    "education_system.post_18.university_system.modules.domain."
    "student_affairs.safeguarding"
)


@pytest.fixture(autouse=True)
def sg_db(tmp_path, monkeypatch):
    """Point the whole safeguarding package at a fresh temp DB and migrate it."""
    db_path = str(tmp_path / "safeguarding.db")

    def _fake_get_connection(*args, **kwargs):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=OFF")
        return conn

    # Patch at the source module — _connect re-imports get_connection on every
    # call, so this catches all callers regardless of import style.
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.get_connection",
        _fake_get_connection,
    )

    from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding import (
        db as sg_db_mod,
    )

    sg_db_mod.init_db()
    return db_path


@pytest.fixture()
def make_case():
    """Factory that persists a submission and returns its new case id.

    Defaults to a non-CRITICAL severity so the CRITICAL-only escalation /
    email path is not exercised (that path is covered separately with the
    email sender mocked).
    """
    from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.services.submissions import (
        save_submission,
    )

    def _make(
        username="s.student",
        full_name="Sam Student",
        content="general concern text that is long enough to be meaningful",
        severity="MEDIUM",
        categories=None,
        **kwargs,
    ):
        user = {"username": username, "full_name": full_name, "role": "student"}
        return save_submission(
            user,
            content,
            severity,
            categories if categories is not None else {},
            **kwargs,
        )

    return _make
