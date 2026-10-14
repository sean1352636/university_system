"""The one definition of the university-local ``users`` table.

There are two ``users`` tables in this platform and they are not the same
table:

* ``auth.db`` — the platform identity store. Credentials, lockout state,
  MFA, password policy. 4,878 rows. Owned by ``platform/identity/auth``.
* ``student_records.db`` — this one. A university-local directory of who
  exists and what role they hold, joined to ``students.student_id``. 25
  rows. **No credentials, deliberately.**

Two id spaces follow from that (``admin`` is 19 in auth.db and 1 here), so
never carry an id across the boundary — resolve by username.

Before this module, the local table was created by 44 disagreeing
``CREATE TABLE`` statements across 30 files. Five of them declared
``password_hash`` and two went further: on the path where the central auth
system fails to initialise, they PBKDF2-hashed a real admin password and
inserted it *here*, creating a second credential store that bypasses
bcrypt, MFA, lockout and the password policy. Those columns exist on no
live database, so the writes have been failing — which is the only reason
the shadow store never materialised.

:func:`resolve_column` therefore refuses credential names outright rather
than mapping them anywhere. Credentials belong in ``auth.db``; a caller
that wants them should go through ``platform.identity.auth``.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Iterable

logger = logging.getLogger(__name__)


# The canonical shape, matching the established table exactly. The NOT NULL
# columns carry no defaults, as on the live table: an insert must supply
# username, first_name, last_name, email, role, created_at and updated_at.
USER_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("username", "TEXT UNIQUE NOT NULL"),
    ("first_name", "TEXT NOT NULL"),
    ("last_name", "TEXT NOT NULL"),
    ("email", "TEXT UNIQUE NOT NULL"),
    ("role", "TEXT NOT NULL"),
    ("student_id", "TEXT"),
    ("created_at", "TEXT NOT NULL"),
    ("updated_at", "TEXT NOT NULL"),
    ("service_account", "INTEGER DEFAULT 0"),
)

USER_COLUMN_NAMES: frozenset[str] = frozenset(name for name, _d in USER_COLUMNS)

_FOREIGN_KEY = (
    "FOREIGN KEY (student_id) REFERENCES students (student_id)"
)

# Names older code writes, mapped onto the real ones.
COLUMN_ALIASES: dict[str, str] = {
    "user_id": "id",
    "created_date": "created_at",
    "modified_at": "updated_at",
    "email_address": "email",
}

# Names that belong to the auth.db users table, not this one. Asking for
# them here is always a mistake, and a silent one — SQLite would happily
# accept a column this table has never had if somebody added it.
AUTH_OWNED_COLUMNS: frozenset[str] = frozenset({
    "password_hash", "password_salt", "legacy_salt", "password_changed_at",
    "must_change_password", "is_active", "active", "last_login",
    "failed_login_attempts", "locked_until", "email_verified",
    "display_name", "line_manager_id",
})

_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
    "CREATE INDEX IF NOT EXISTS idx_users_student_id ON users(student_id)",
)

# SQLite cannot ``ADD COLUMN`` with UNIQUE, so a column backfilled onto an
# existing table gets its uniqueness from an index instead. Declared here
# rather than inline so the two routes to the same table agree.
_UNIQUE_INDEXES: tuple[str, ...] = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)",
)


def _addable(decl: str) -> str:
    """Strip the constraints SQLite refuses on ``ALTER TABLE ADD COLUMN``.

    A NOT NULL column needs a default to be added to a populated table, and
    UNIQUE is rejected outright — that one is restored as a unique index.
    """
    cleaned = decl
    if "UNIQUE" in cleaned.upper():
        cleaned = re.sub(r"\bUNIQUE\b", "", cleaned, flags=re.IGNORECASE)
    if "NOT NULL" in cleaned.upper() and "DEFAULT" not in cleaned.upper():
        cleaned = re.sub(r"\bNOT\s+NULL\b", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip() or "TEXT"


class UnknownUserColumnError(KeyError):
    """A caller used a column name the local ``users`` table does not have."""


class AuthOwnedColumnError(UnknownUserColumnError):
    """A caller tried to read or write a credential column on the local table.

    Credentials live in ``auth.db``. Storing them here would create a second
    identity store with none of the policy the first one enforces.
    """


def create_users_sql() -> str:
    """The canonical ``CREATE TABLE`` statement."""
    body = ",\n    ".join(f'"{name}" {decl}' for name, decl in USER_COLUMNS)
    return f"CREATE TABLE IF NOT EXISTS users (\n    {body},\n    {_FOREIGN_KEY}\n)"


def resolve_column(name: str) -> str:
    """Map a caller's column name onto the canonical one.

    Raises :class:`AuthOwnedColumnError` for anything that belongs to the
    auth database, and :class:`UnknownUserColumnError` for a typo.
    """
    key = name.strip().strip('"`[]').lower()
    if key in USER_COLUMN_NAMES:
        return key
    if key in AUTH_OWNED_COLUMNS:
        raise AuthOwnedColumnError(
            f"{name!r} belongs to the auth.db users table, not the "
            f"university-local one. Go through "
            f"education_system.platform.identity.auth instead of writing "
            f"credentials or account state into student_records.db."
        )
    if key in COLUMN_ALIASES:
        return COLUMN_ALIASES[key]
    raise UnknownUserColumnError(
        f"the local users table has no column {name!r}; known aliases: "
        f"{', '.join(sorted(COLUMN_ALIASES))}"
    )


def resolve_columns(names: Iterable[str]) -> list[str]:
    return [resolve_column(n) for n in names]


def ensure_users_table(conn: sqlite3.Connection) -> None:
    """Create the local ``users`` table if absent and backfill any missing
    column. Idempotent; safe on every entry point.

    Deliberately never adds a credential column, whatever the caller's own
    definition used to declare.
    """
    try:
        conn.execute(create_users_sql())
        existing = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        for name, decl in USER_COLUMNS:
            if name in existing:
                continue
            if "PRIMARY KEY" in decl.upper():
                logger.error("users table exists without its id column; "
                             "refusing to patch it")
                continue
            try:
                conn.execute(
                    f'ALTER TABLE users ADD COLUMN "{name}" {_addable(decl)}')
                logger.info("Added users.%s", name)
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    logger.warning("Could not add users.%s: %s", name, exc)
        for statement in _INDEXES:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError:
                logger.debug("users index skipped: %s", statement)
        for statement in _UNIQUE_INDEXES:
            # A pre-existing table may hold duplicates that the declared
            # UNIQUE would have prevented; log rather than fail the caller.
            try:
                conn.execute(statement)
            except sqlite3.OperationalError as exc:
                logger.warning("users uniqueness not enforced (%s): %s",
                               statement.split(" ON ")[-1], exc)
    except sqlite3.Error:
        logger.exception("users table bootstrap failed")


def ensure_users_table_at(db_path: str | None = None) -> None:
    """Path-taking wrapper for callers with no connection to hand."""
    if db_path is None:
        from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
        db_path = str(UNIVERSITY_DEFAULT_DB_PATH)
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_users_table(conn)
        conn.commit()
    finally:
        conn.close()


def missing_columns(conn: sqlite3.Connection) -> list[str]:
    """Canonical columns absent from this database. Empty means healthy."""
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    except sqlite3.Error:
        return sorted(USER_COLUMN_NAMES)
    if not existing:
        return sorted(USER_COLUMN_NAMES)
    return sorted(USER_COLUMN_NAMES - existing)


def credential_columns_present(conn: sqlite3.Connection) -> list[str]:
    """Auth-owned columns that have leaked onto the local table.

    Should always be empty. If it is not, something created a shadow
    credential store in ``student_records.db``.
    """
    try:
        existing = {row[1].lower()
                    for row in conn.execute("PRAGMA table_info(users)")}
    except sqlite3.Error:
        return []
    return sorted(existing & AUTH_OWNED_COLUMNS)


__all__ = [
    "USER_COLUMNS",
    "USER_COLUMN_NAMES",
    "COLUMN_ALIASES",
    "AUTH_OWNED_COLUMNS",
    "UnknownUserColumnError",
    "AuthOwnedColumnError",
    "create_users_sql",
    "resolve_column",
    "resolve_columns",
    "ensure_users_table",
    "ensure_users_table_at",
    "missing_columns",
    "credential_columns_present",
]
