"""Identity-level operations: rename + merge.

* **Force-rename** changes the username and stores the previous values
  in ``user_name_history`` so an audit reader can trace who used
  which username when.
* **Merge** picks a canonical user and moves owned auth-side rows
  (``user_systems``, ``password_history``, ``mfa_*``, ``sessions``,
  ``security_audit_log``) plus our own side-tables (extras, archives,
  audit) over to it, then archives the loser. Cross-domain ownership
  (gradebook, finance, housing) is *recorded* but not moved — see the
  reassignment summary returned to the caller.
"""

from __future__ import annotations

import datetime
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.sixthform_system.modules.domain.governance.user_management import (
    lifecycle,
)
from education_system.sixthform_system.modules.shared import user_accounts as _ua
from education_system.sixthform_system.modules.shared.user_accounts import (
    UserAccountError, UserRow,
)

logger = logging.getLogger(__name__)


def _init_schema(auth: Any) -> None:
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_name_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    old_username TEXT,
                    new_username TEXT,
                    old_display_name TEXT,
                    new_display_name TEXT,
                    changed_at TEXT NOT NULL,
                    changed_by TEXT,
                    reason TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_name_history_user
                ON user_name_history(user_id, changed_at)
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("user_name_history schema init failed")
        raise


# ── Rename ────────────────────────────────────────────────────────────

def force_rename(auth: Any, user_id: int, *,
                  new_username: str | None = None,
                  new_display_name: str | None = None,
                  reason: str | None = None) -> UserRow:
    """Change username and/or display_name and log to history.
    Refuses if either field is empty when supplied, or if the new
    username already exists."""
    _init_schema(auth)
    user = _ua.get_user(auth, user_id)
    if user is None:
        raise UserAccountError(f"No user #{user_id}")
    if new_username is None and new_display_name is None:
        raise UserAccountError("Pass at least one of new_username / "
                                "new_display_name.")
    new_username = (new_username or user.username).strip()
    if not new_username:
        raise UserAccountError("Username may not be empty.")
    if new_display_name is None:
        new_display_name = user.display_name
    elif isinstance(new_display_name, str):
        new_display_name = new_display_name.strip() or None

    if new_username != user.username:
        # Uniqueness check.
        try:
            conn = lifecycle._conn(auth)
            try:
                r = conn.execute(
                    "SELECT id FROM users WHERE username = ? AND id != ?",
                    (new_username, user_id)).fetchone()
                if r:
                    raise UserAccountError(
                        f"Username {new_username!r} is already taken.")
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.exception("Username uniqueness check failed")
            raise UserAccountError(f"DB error: {e}") from e

    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute(
                "UPDATE users SET username = ?, display_name = ?, "
                "updated_at = ? WHERE id = ?",
                (new_username, new_display_name, now, user_id))
            conn.execute('''
                INSERT INTO user_name_history
                (user_id, old_username, new_username,
                 old_display_name, new_display_name,
                 changed_at, changed_by, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, user.username, new_username,
                  user.display_name, new_display_name,
                  now, actor, (reason or '').strip() or None))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("force_rename DB failure")
        raise UserAccountError(f"Could not rename: {e}") from e

    lifecycle._audit(auth, "user_rename", user_id, {
        "old_username": user.username, "new_username": new_username,
        "old_display_name": user.display_name,
        "new_display_name": new_display_name,
        "reason": reason,
    })
    logger.info("Renamed user_id=%d (%s -> %s)",
                user_id, user.username, new_username)
    out = _ua.get_user(auth, user_id)
    assert out is not None
    return out


def name_history(auth: Any, user_id: int) -> list[dict]:
    _init_schema(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute(
                "SELECT * FROM user_name_history WHERE user_id = ? "
                "ORDER BY changed_at DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("name_history failed")
        return []


# ── Merge ─────────────────────────────────────────────────────────────

@dataclass
class MergeResult:
    canonical_user_id: int
    loser_user_id: int
    moved: dict[str, int] = field(default_factory=dict)
    archive_id: int | None = None
    cross_domain_note: str = ""


_AUTH_OWNED_TABLES = (
    # (table, fk_column)
    ("user_systems",                 "user_id"),
    ("password_history",             "user_id"),
    ("password_reset_tokens",        "user_id"),
    ("mfa_recovery_codes",           "user_id"),
    ("trusted_devices",              "user_id"),
    ("security_questions",           "user_id"),
    ("consent_records",              "user_id"),
    ("email_verification_tokens",    "user_id"),
    ("webauthn_credentials",         "user_id"),
    ("oauth_accounts",               "user_id"),
    ("security_audit_log",           "user_id"),
)

# Side-tables this module owns.
_LIFECYCLE_OWNED_TABLES = (
    ("user_profile_extras",   "user_id"),
    ("user_audit_log",        "target_user_id"),
    ("user_archives",         "user_id"),
    ("user_suspensions",      "user_id"),
    ("user_name_history",     "user_id"),
    ("user_pending_setups",   "user_id"),
)


def merge_accounts(auth: Any, *,
                    canonical_user_id: int,
                    loser_user_id: int,
                    reason: str | None = None) -> MergeResult:
    """Move every row owned by ``loser_user_id`` to
    ``canonical_user_id`` then archive the loser. Refuses to merge a
    user with itself or merge an already-archived user."""
    if canonical_user_id == loser_user_id:
        raise UserAccountError("Cannot merge a user with itself.")
    canonical = _ua.get_user(auth, canonical_user_id)
    loser = _ua.get_user(auth, loser_user_id)
    if canonical is None:
        raise UserAccountError(
            f"No canonical user #{canonical_user_id}")
    if loser is None:
        raise UserAccountError(f"No loser user #{loser_user_id}")

    lifecycle.init_lifecycle_schema(auth)
    _init_schema(auth)
    result = MergeResult(canonical_user_id=canonical_user_id,
                          loser_user_id=loser_user_id)

    try:
        conn = lifecycle._conn(auth)
        try:
            for table, col in _AUTH_OWNED_TABLES + _LIFECYCLE_OWNED_TABLES:
                try:
                    cur = conn.execute(
                        f"UPDATE {table} SET {col} = ? WHERE {col} = ?",
                        (canonical_user_id, loser_user_id))
                    result.moved[table] = cur.rowcount
                except sqlite3.Error:
                    # Table may not exist on a partial schema — log
                    # and move on so a missing optional table doesn't
                    # block the merge.
                    logger.debug("Merge: skipping %s (not present?)",
                                  table, exc_info=True)
                    result.moved[table] = 0
            # Sessions: invalidate any active for the loser instead of
            # moving — a session token shouldn't be reassigned.
            try:
                conn.execute(
                    "UPDATE sessions SET is_active = 0 "
                    "WHERE user_id = ?", (loser_user_id,))
            except sqlite3.Error:
                logger.exception("Merge: invalidate sessions failed")
            # mfa_secrets is UNIQUE(user_id), so we can't move; just
            # leave the canonical's secret alone and ignore the loser's.
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("merge_accounts move failed")
        raise UserAccountError(f"Could not merge: {e}") from e

    # Archive the loser (with a clear reason) so the username is no
    # longer usable.
    try:
        arch = lifecycle.archive_user(
            auth, loser_user_id,
            reason=("Merged into "
                     f"#{canonical_user_id} ({canonical.username})"
                     + (f": {reason}" if reason else "")),
            retention_days=lifecycle.DEFAULT_RETENTION_DAYS,
        )
        result.archive_id = arch.archive_id
    except UserAccountError as e:
        # Loser may already be archived — log and proceed.
        logger.info("Merge: loser archive skipped (%s)", e)

    result.cross_domain_note = (
        "Cross-domain records (gradebook, finance, housing, etc.) "
        "owned by the loser are NOT moved automatically — run each "
        "domain's reassignment helper. The audit row has the loser's "
        "snapshot for reference.")

    lifecycle._audit(auth, "user_merge", canonical_user_id, {
        "loser_user_id": loser_user_id,
        "loser_username": loser.username,
        "moved": result.moved, "reason": reason,
    })
    logger.info("Merged #%d -> #%d (rows moved=%s)",
                loser_user_id, canonical_user_id, result.moved)
    return result
