"""The university-local ``users`` table, owned by a migration.

``student_records.db`` carries a small directory table also called
``users`` — who exists here and what role they hold, joined to
``students.student_id``. It is not the ``auth.db`` users table, which owns
credentials, lockout and MFA for the whole platform. The two have separate
id spaces (``admin`` is 19 there and 1 here), which is exactly why the
local one needs a stated shape rather than an accidental one.

It had 44 disagreeing definitions across 30 files. Five declared
``password_hash``; two of those would, on the fallback path where the
central auth system fails to initialise, hash a real admin password and
insert it here — a second credential store with none of the policy the
first one enforces. Those columns exist on no live database, so the writes
were failing, which is the only reason the shadow store never appeared.
This migration states the credential-free shape, and
``users_table.ensure_users_table`` never adds a credential column whatever
the caller asked for.

Revision ID: f7b3d81e4c69
Revises: e4a17c9d3b52
"""

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7b3d81e4c69"
down_revision: Union[str, Sequence[str], None] = "e4a17c9d3b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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

FOREIGN_KEY = "FOREIGN KEY (student_id) REFERENCES students (student_id)"

INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
    "CREATE INDEX IF NOT EXISTS idx_users_student_id ON users(student_id)",
)

# SQLite refuses ``ADD COLUMN ... UNIQUE``, so a column backfilled onto an
# existing table takes its uniqueness from an index instead.
UNIQUE_INDEXES: tuple[str, ...] = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)",
)

# Never to be created on this table. Listed so the check below can say
# something useful rather than just failing.
AUTH_OWNED = (
    "password_hash", "password_salt", "legacy_salt", "must_change_password",
    "failed_login_attempts", "locked_until",
)


def upgrade() -> None:
    body = ",\n    ".join(f'"{name}" {decl}' for name, decl in USER_COLUMNS)
    op.execute(
        f"CREATE TABLE IF NOT EXISTS users (\n    {body},\n    {FOREIGN_KEY}\n)")

    bind = op.get_bind()
    existing = {
        row[1] for row in bind.execute(sa.text("PRAGMA table_info(users)"))
    }
    for name, decl in USER_COLUMNS:
        if name in existing or "PRIMARY KEY" in decl.upper():
            continue
        # UNIQUE is rejected by ADD COLUMN outright, and a NOT NULL column
        # with no default cannot be added to a populated table. Strip both
        # here; uniqueness comes back as an index below, and the strict
        # shape applies to a fresh database via the CREATE above.
        addable = re.sub(r"\bUNIQUE\b", "", decl, flags=re.IGNORECASE)
        if "NOT NULL" in addable.upper() and "DEFAULT" not in addable.upper():
            addable = re.sub(r"\bNOT\s+NULL\b", "", addable, flags=re.IGNORECASE)
        addable = re.sub(r"\s+", " ", addable).strip() or "TEXT"
        op.execute(f'ALTER TABLE users ADD COLUMN "{name}" {addable}')

    for statement in INDEXES:
        op.execute(statement)
    for statement in UNIQUE_INDEXES:
        try:
            op.execute(statement)
        except Exception as exc:  # noqa: BLE001
            # An established table may already hold duplicates that the
            # declared UNIQUE would have prevented. Say so; do not fail the
            # upgrade over it.
            print(f"WARNING: could not enforce {statement}: {exc}")

    leaked = sorted(
        {row[1].lower()
         for row in bind.execute(sa.text("PRAGMA table_info(users)"))}
        & set(AUTH_OWNED)
    )
    if leaked:
        # Not dropped automatically: if a database really does hold
        # credentials here, somebody has to decide what happens to them.
        print(
            "WARNING: student_records.db users carries auth-owned columns "
            f"{leaked}. Credentials belong in auth.db; review before "
            "dropping them."
        )


def downgrade() -> None:
    # Not reversible: the previous state was "whichever of 44 definitions
    # ran first", which no migration can restore.
    pass
