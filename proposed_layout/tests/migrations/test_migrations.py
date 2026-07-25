"""Schema-migration tests.

Proves that ``initialise_auth_db`` upgrades a *previous-schema* auth database
(a users table that predates the newer columns) to the current schema without
losing data — i.e. an existing deployment can be migrated in place.
"""

import os
import sqlite3
import sys

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
)

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.schema import initialise_auth_db


# The original users table, before legacy_salt / password_changed_at /
# email_verified / line_manager_id / must_change_password were added.
_LEGACY_USERS_SQL = """
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    UNIQUE NOT NULL,
    password_hash   TEXT    NOT NULL,
    display_name    TEXT,
    email           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login      TEXT
);
"""

_NEW_COLUMNS = {
    "legacy_salt",
    "password_changed_at",
    "email_verified",
    "line_manager_id",
    "must_change_password",
}


def _make_legacy_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_LEGACY_USERS_SQL)
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, email) "
            "VALUES (?, ?, ?, ?)",
            ("legacy_user", "hashed-pw", "Legacy User", "legacy@example.com"),
        )
        conn.commit()
    finally:
        conn.close()


def test_legacy_db_is_missing_new_columns(tmp_path):
    db = str(tmp_path / "legacy.db")
    _make_legacy_db(db)
    conn = sqlite3.connect(db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    finally:
        conn.close()
    assert not (_NEW_COLUMNS & cols)  # none present yet


def test_migration_adds_new_columns(tmp_path):
    db = str(tmp_path / "legacy.db")
    _make_legacy_db(db)

    initialise_auth_db(db)  # migrate in place

    conn = connect(db)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    finally:
        conn.close()
    assert _NEW_COLUMNS <= cols  # every new column now exists


def test_migration_preserves_existing_rows(tmp_path):
    db = str(tmp_path / "legacy.db")
    _make_legacy_db(db)

    initialise_auth_db(db)

    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT username, email, display_name, must_change_password "
            "FROM users WHERE username = 'legacy_user'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["username"] == "legacy_user"
    assert row["email"] == "legacy@example.com"
    # New flag defaults to 0 for pre-existing (non-demo) accounts.
    assert row["must_change_password"] == 0


def test_migration_is_idempotent(tmp_path):
    db = str(tmp_path / "legacy.db")
    _make_legacy_db(db)
    initialise_auth_db(db)
    initialise_auth_db(db)  # second run must not error or duplicate

    conn = connect(db)
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM users WHERE username = 'legacy_user'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert cnt == 1
