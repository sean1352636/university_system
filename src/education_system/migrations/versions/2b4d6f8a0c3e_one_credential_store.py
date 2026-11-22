"""university: the shared auth (auth.db) is the only credential store

``user_accounts`` in student_records.db held a second copy of password
hashes (PBKDF2), salts and TOTP secrets for 17 accounts, and its ``user_id``
column had drifted: several accounts pointed at another person's
``users.id`` (three pairs sharing an id), so the legacy login joined to the
wrong profile. Sign-in, password change/reset and MFA now go through the
shared auth only (``infrastructure/auth/facade_components``).

This migration, reading the shared auth read-only:

0. repairs messages whose ``sender_id`` / ``recipient_id`` is not a
   ``users`` row. They hold central auth ids (the other id space, written
   before sessions used local ids): each is mapped auth id → username →
   local profile, and cleared (NULL) where no profile has that username.
   This runs first because ``users`` is AUTOINCREMENT at 26 and the
   profiles created in step 1 would otherwise take ids 27/28 and inherit
   other people's messages;
1. creates the missing university profile (``users`` row) for accounts that
   have a ``user_accounts`` row and a shared sign-in but no profile (the
   staff/instructor accounts adam.johnson, adlad13, ben.smith, lucy1357),
   taking role, name and e-mail from the shared auth;
2. repoints every ``user_accounts.user_id`` at the ``users`` row with the
   same username;
3. clears ``password_hash``/``salt``/``two_fa_secret`` and sets
   ``two_fa_enabled = 0`` for every account whose username has a password
   in the shared auth. An account with no shared password keeps its local
   hash, so it does not lose the ability to sign in (none at the time of
   writing).

When the shared auth cannot be read, only step 2 runs. The table itself
stays: its non-secret columns (id map, is_active, last_login,
password_reset_required) still have readers. Idempotent.

Revision ID: 2b4d6f8a0c3e
Revises: 1a3c5e7f9b2d
Create Date: 2026-10-18 10:00:00.000000
"""
import logging
import sqlite3
from datetime import datetime
from typing import Sequence, Union

from alembic import op


revision: str = '2b4d6f8a0c3e'
down_revision: Union[str, Sequence[str], None] = '1a3c5e7f9b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def _shared_accounts():
    """``username (lower) -> {has_password, display_name, email, role}`` from
    the shared auth, opened read-only; None when it can't be read."""
    try:
        from education_system import paths
        conn = sqlite3.connect(f"file:{paths.PLATFORM_AUTH_DB}?mode=ro", uri=True)
    except Exception as exc:
        logger.warning("Shared auth not readable (%s); credentials left in place", exc)
        return None
    try:
        found = {}
        for uid, username, password_hash, display, email in conn.execute(
                "SELECT id, username, password_hash, display_name, email FROM users"):
            role = conn.execute("SELECT role FROM user_systems WHERE user_id = ? AND "
                                "system_key = 'university'", (uid,)).fetchone()
            found[str(username).lower()] = {
                "has_password": bool(password_hash),
                "display_name": display,
                "email": email,
                "role": role[0] if role else None,
            }
        return found
    except Exception as exc:
        logger.warning("Shared auth not readable (%s); credentials left in place", exc)
        return None
    finally:
        conn.close()


def _shared_usernames_by_id():
    """``auth id -> username`` from the shared auth (read-only), or None."""
    try:
        from education_system import paths
        conn = sqlite3.connect(f"file:{paths.PLATFORM_AUTH_DB}?mode=ro", uri=True)
    except Exception:
        return None
    try:
        return {row[0]: row[1] for row in conn.execute("SELECT id, username FROM users")}
    except Exception:
        return None
    finally:
        conn.close()


def _repair_dangling_messages(execute) -> None:
    if not {"sender_id", "recipient_id"} <= _columns(execute, "messages"):
        return
    names = _shared_usernames_by_id() or {}
    for column in ("sender_id", "recipient_id"):
        for (bad,) in execute(
                f'SELECT DISTINCT "{column}" FROM messages WHERE "{column}" IS NOT NULL '  # nosec B608
                f'AND "{column}" NOT IN (SELECT id FROM users)').fetchall():
            username = names.get(int(bad)) if str(bad).isdigit() else None
            local = execute("SELECT id FROM users WHERE username = ?",
                            (username,)).fetchone() if username else None
            execute(f'UPDATE messages SET "{column}" = ? WHERE "{column}" = ?',  # nosec B608
                    (local[0] if local else None, bad))
            logger.info("messages.%s %s -> %s (%s)", column, bad,
                        local[0] if local else None, username or "no shared account")


def _columns(execute, table) -> set:
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def upgrade() -> None:
    execute = op.get_bind().exec_driver_sql
    if not {"username", "user_id", "password_hash"} <= _columns(execute, "user_accounts"):
        return
    # 0. Before any profile is created (see the docstring).
    _repair_dangling_messages(execute)
    shared = _shared_accounts()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Missing university profiles for accounts that sign in centrally.
    if shared is not None:
        for (username,) in execute(
                "SELECT ua.username FROM user_accounts ua WHERE NOT EXISTS "
                "(SELECT 1 FROM users u WHERE u.username = ua.username)").fetchall():
            info = shared.get(str(username).lower())
            if not info:
                continue
            parts = (info["display_name"] or username).split()
            first = parts[0].title() if parts else username
            last = " ".join(parts[1:]).title() if len(parts) > 1 else "-"
            email = info["email"] or f"{username}@university.local"
            if execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                email = f"{username}@university.local"
            execute("INSERT INTO users (username, first_name, last_name, email, role, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (username, first, last, email, info["role"] or "staff", now, now))

    # 2. Every account points at the profile with its own username.
    execute("UPDATE user_accounts SET user_id = (SELECT u.id FROM users u WHERE "
            "u.username = user_accounts.username) WHERE EXISTS (SELECT 1 FROM users u "
            "WHERE u.username = user_accounts.username) AND user_id IS NOT (SELECT u.id "
            "FROM users u WHERE u.username = user_accounts.username)")

    # 3. No second copy of a password or TOTP secret.
    if shared is None:
        return
    cols = _columns(execute, "user_accounts")
    clear = ["password_hash = ''", "salt = ''"]
    if "two_fa_secret" in cols:
        clear.append("two_fa_secret = NULL")
    if "two_fa_enabled" in cols:
        clear.append("two_fa_enabled = 0")
    for row_id, username, password_hash in execute(
            "SELECT id, username, password_hash FROM user_accounts").fetchall():
        info = shared.get(str(username).lower())
        if not info or not info["has_password"]:
            if password_hash:
                logger.warning("Account %r has no shared password; its local hash is kept",
                               username)
            continue
        execute(f"UPDATE user_accounts SET {', '.join(clear)} WHERE id = ?",  # nosec B608
                (row_id,))


def downgrade() -> None:
    # Deliberately a no-op. The cleared hashes, salts and TOTP secrets were
    # second copies of credentials kept in the shared auth (auth.db), and
    # they cannot be restored from anywhere. The created profiles and the
    # corrected user_id links are right in either direction, so they stay.
    pass
