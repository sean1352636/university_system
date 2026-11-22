"""The university-local ``users`` table has one definition, and no credentials.

There are two ``users`` tables in this platform: ``auth.db`` owns identity
(passwords, lockout, MFA) and ``student_records.db`` carries a local
directory joined to ``students``. The local one had 44 disagreeing
definitions across 30 files, five of which declared ``password_hash`` — two
of those would, on a fallback path, have written a real hashed admin
password into the wrong database.

These tests pin the shape, and pin the rule that the local table never
grows a credential column.
"""

from __future__ import annotations

import ast
import re
import sqlite3
from pathlib import Path

import pytest

from education_system.systems.university.infrastructure.database.schemas.users_table import (
    AUTH_OWNED_COLUMNS,
    COLUMN_ALIASES,
    USER_COLUMN_NAMES,
    USER_COLUMNS,
    AuthOwnedColumnError,
    UnknownUserColumnError,
    create_users_sql,
    credential_columns_present,
    ensure_users_table,
    missing_columns,
    resolve_column,
)

REPO_ROOT = Path(__file__).resolve().parents[6]
UNIVERSITY_ROOT = (REPO_ROOT / "src" / "education_system" / "systems"
                   / "university")
MIGRATION = (REPO_ROOT / "src" / "education_system" / "migrations" / "versions"
             / "f7b3d81e4c69_canonical_local_users_table.py")


@pytest.fixture()
def db(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "local_users.db")
    yield conn
    conn.close()


def _migration_constant(path: Path, name: str):
    """Read a module-level constant out of a migration without importing it.

    The migrations annotate their constants (``X: tuple[...] = (...)``), so
    this has to handle ``AnnAssign`` as well as ``Assign`` — matching only
    the latter silently returns None and the comparison passes vacuously.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            if getattr(node.target, "id", None) == name and node.value:
                return ast.literal_eval(node.value)
        elif isinstance(node, ast.Assign):
            if any(getattr(t, "id", "") == name for t in node.targets):
                return ast.literal_eval(node.value)
    return None


# --------------------------------------------------------------- definition

def test_migration_and_module_agree():
    migration_columns = _migration_constant(MIGRATION, "USER_COLUMNS")
    assert migration_columns is not None, "migration lost USER_COLUMNS"
    assert tuple(migration_columns) == tuple(USER_COLUMNS)


def test_the_local_table_declares_no_credentials():
    """The whole point of the split. If this fails, somebody has started a
    second identity store in student_records.db."""
    leaked = USER_COLUMN_NAMES & AUTH_OWNED_COLUMNS
    assert not leaked, f"credential columns declared locally: {sorted(leaked)}"


def test_bootstrap_never_adds_a_credential_column(db):
    ensure_users_table(db)
    assert credential_columns_present(db) == []


def test_bootstrap_creates_every_column(db):
    ensure_users_table(db)
    assert missing_columns(db) == []


def test_bootstrap_is_idempotent(db):
    ensure_users_table(db)
    before = db.execute("SELECT sql FROM sqlite_master "
                        "WHERE name='users'").fetchone()[0]
    ensure_users_table(db)
    after = db.execute("SELECT sql FROM sqlite_master "
                       "WHERE name='users'").fetchone()[0]
    assert before == after


def test_bootstrap_widens_a_narrow_populated_table(db):
    """A NOT NULL column with no default cannot be added to a populated
    table; the bootstrap relaxes it rather than failing."""
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, "
               "username TEXT UNIQUE NOT NULL)")
    db.execute("INSERT INTO users (username) VALUES ('ada')")
    ensure_users_table(db)
    assert missing_columns(db) == []
    assert db.execute("SELECT username FROM users").fetchone() == ("ada",)


def test_create_sql_matches_the_column_list(db):
    db.executescript(create_users_sql())
    columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
    assert columns == USER_COLUMN_NAMES


# ----------------------------------------------------------------- aliases

@pytest.mark.parametrize(("given", "expected"), [
    ("user_id", "id"),
    ("created_date", "created_at"),
    ("email_address", "email"),
    ("ROLE", "role"),
])
def test_resolve_column(given, expected):
    assert resolve_column(given) == expected


@pytest.mark.parametrize("column", [
    "password_hash", "password_salt", "is_active", "last_login",
    "must_change_password", "locked_until",
])
def test_resolve_column_refuses_auth_owned_names(column):
    with pytest.raises(AuthOwnedColumnError) as excinfo:
        resolve_column(column)
    assert "auth.db" in str(excinfo.value)


def test_resolve_column_rejects_a_typo():
    with pytest.raises(UnknownUserColumnError):
        resolve_column("usrename")


# ----------------------------------------------------- no credential writes

# Legitimately writes to auth.db, reading the local table as its source.
_EXEMPT = {"infrastructure/auth/migration_to_shared.py"}

# Modules that still administer accounts against the local table. Each is a
# real defect — helpdesk-created accounts cannot log in, and password
# resets there change nothing — but fixing them means routing the flow
# through platform.identity.auth, which is a behaviour change rather than a
# schema one. The list is a ratchet: it may shrink, never grow.
_KNOWN_LOCAL_ACCOUNT_ADMIN = {
    "domains/student_support/interfaces/gui/helpdesk/user_management.py",
    "domains/student_life/interfaces/gui/student_union_gui/core/profile.py",
    "domains/student_support/interfaces/gui/student_support/reports_export.py",
    "shell/api/routes/user_routes.py",
    "shell/gui/main/admin/user_management_gui.py",
}

_SQL_NOISE = {
    "excluded", "values", "set", "where", "select", "null", "coalesce",
    "case", "when", "then", "end", "users",
}


def _user_write_columns(text: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(
            r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+users\s*\(([^)]*)\)",
            text, re.IGNORECASE | re.DOTALL):
        names |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", match.group(1)))
    for match in re.finditer(r"UPDATE\s+users\s+SET\s+(.{0,400}?)\s+WHERE",
                             text, re.IGNORECASE | re.DOTALL):
        names |= {m.group(1) for m in
                  re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", match.group(1))}
    return {n.lower() for n in names} - _SQL_NOISE


def _scan() -> dict[str, set[str]]:
    offenders: dict[str, set[str]] = {}
    for path in UNIVERSITY_ROOT.rglob("*.py"):
        rel = path.relative_to(UNIVERSITY_ROOT).as_posix()
        if rel in _EXEMPT:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "users" not in text:
            continue
        bad = _user_write_columns(text) & AUTH_OWNED_COLUMNS
        if bad:
            offenders[rel] = bad
    return offenders


def test_no_new_module_writes_credentials_to_the_local_table():
    offenders = set(_scan()) - _KNOWN_LOCAL_ACCOUNT_ADMIN
    assert not offenders, (
        "these modules write auth-owned columns into student_records.db's "
        f"users table; credentials belong in auth.db: {sorted(offenders)}"
    )


def test_the_known_offender_list_does_not_go_stale():
    """A ratchet is only useful if fixed entries get deleted."""
    fixed = _KNOWN_LOCAL_ACCOUNT_ADMIN - set(_scan())
    assert not fixed, (
        "these modules no longer write credentials locally — remove them "
        f"from _KNOWN_LOCAL_ACCOUNT_ADMIN: {sorted(fixed)}"
    )


def test_no_module_writes_an_alias_column():
    offenders: dict[str, set[str]] = {}
    for path in UNIVERSITY_ROOT.rglob("*.py"):
        rel = path.relative_to(UNIVERSITY_ROOT).as_posix()
        if rel in _EXEMPT:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "users" not in text:
            continue
        used = _user_write_columns(text)
        bad = {c for c in used - USER_COLUMN_NAMES - AUTH_OWNED_COLUMNS
               if c in COLUMN_ALIASES}
        if bad:
            offenders[rel] = bad
    assert not offenders, f"use the canonical column names: {offenders}"
