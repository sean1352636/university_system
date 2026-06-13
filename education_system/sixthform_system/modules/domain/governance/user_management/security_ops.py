"""Security operations for User Management — covers items 13-20:

13. Force password reset (next-login flag + invalidate sessions)
14. Generate one-time login link / token
15. Reset MFA (clear stored TOTP secret + recovery codes)
16. List / revoke active sessions
17. Failed-login dashboard
18. Lock / unlock account with reason + expiry
19. Password-age report
20. Compromised-password check against a local breach list

Everything writes through the existing auth tables where they exist
(``sessions``, ``mfa_secrets``, ``security_audit_log``, etc.) and
falls back to side-tables only for state that isn't already modelled:

* ``user_password_reset_flags`` — track must-change-on-next-login per
  user (the auth flow checks this when authenticating);
* ``user_lock_history`` — reason + admin trail for each lock/unlock;
* ``user_breach_list`` — local breach corpus (full SHA-1 hex) loaded
  from a file via ``import_breach_list``.

All writes audit through ``lifecycle._audit``.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from education_system.sixthform_system.modules.domain.governance.user_management import (
    lifecycle,
)
from education_system.sixthform_system.modules.shared import user_accounts as _ua
from education_system.sixthform_system.modules.shared.user_accounts import (
    UserAccountError, UserRow,
)

logger = logging.getLogger(__name__)


# ── Schema ────────────────────────────────────────────────────────────

def _init_schema(auth: Any) -> None:
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_password_reset_flags (
                    user_id INTEGER PRIMARY KEY,
                    must_change INTEGER NOT NULL DEFAULT 1,
                    set_by TEXT, set_at TEXT,
                    cleared_at TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_lock_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,      -- 'lock' | 'unlock'
                    reason TEXT,
                    locked_until TEXT,
                    actor TEXT,
                    at TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_breach_list (
                    sha1_hex TEXT PRIMARY KEY,
                    source TEXT,
                    imported_at TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_lock_history_user
                ON user_lock_history(user_id, at)
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("security_ops schema init failed")
        raise


# ── 13. Force password reset ──────────────────────────────────────────

def force_password_reset(auth: Any, user_id: int,
                           *, invalidate_sessions: bool = True
                           ) -> None:
    """Flag the user as must-change-on-next-login, optionally
    invalidating active sessions. Does NOT pick a new password — the
    user does that themselves on next sign-in."""
    _init_schema(auth)
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                INSERT INTO user_password_reset_flags
                (user_id, must_change, set_by, set_at, cleared_at)
                VALUES (?, 1, ?, ?, NULL)
                ON CONFLICT(user_id) DO UPDATE SET
                    must_change=1, set_by=excluded.set_by,
                    set_at=excluded.set_at, cleared_at=NULL
            ''', (user_id, actor, now))
            if invalidate_sessions:
                conn.execute(
                    "UPDATE sessions SET is_active = 0 WHERE user_id = ?",
                    (user_id,))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("force_password_reset failed")
        raise UserAccountError(f"Could not flag user: {e}") from e
    lifecycle._audit(auth, "force_password_reset", user_id,
                      {"invalidate_sessions": invalidate_sessions})


def clear_password_reset_flag(auth: Any, user_id: int) -> None:
    _init_schema(auth)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute(
                "UPDATE user_password_reset_flags "
                "SET must_change=0, cleared_at=? WHERE user_id=?",
                (now, user_id))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("clear_password_reset_flag failed")


def must_change_password(auth: Any, user_id: int) -> bool:
    _init_schema(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            r = conn.execute(
                "SELECT must_change FROM user_password_reset_flags "
                "WHERE user_id = ?", (user_id,)).fetchone()
            return bool(r and r["must_change"])
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("must_change_password failed")
        return False


# ── 14. One-time login link ───────────────────────────────────────────

DEFAULT_OTL_TTL_HOURS = 4


def generate_one_time_login(auth: Any, user_id: int,
                              *, ttl_hours: int = DEFAULT_OTL_TTL_HOURS,
                              ) -> str:
    """Issue a one-time login token that can stand in for password +
    MFA for a single sign-in. Implementation reuses the existing
    ``password_reset_tokens`` table — caller hashes/verifies through
    the existing password-reset flow."""
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = (datetime.datetime.now()
                + datetime.timedelta(hours=ttl_hours)).isoformat(
        timespec='seconds')
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute(
                "INSERT INTO password_reset_tokens "
                "(user_id, token_hash, expires_at) VALUES (?, ?, ?)",
                (user_id, token_hash, expires))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("generate_one_time_login failed")
        raise UserAccountError(f"Could not issue token: {e}") from e
    lifecycle._audit(auth, "one_time_login_issued", user_id,
                      {"expires_at": expires})
    return token


# ── 15. Reset MFA ─────────────────────────────────────────────────────

def reset_mfa(auth: Any, user_id: int) -> None:
    """Wipe the stored TOTP secret + recovery codes. The user must
    re-enrol on next sign-in."""
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute("DELETE FROM mfa_secrets WHERE user_id = ?",
                         (user_id,))
            conn.execute(
                "DELETE FROM mfa_recovery_codes WHERE user_id = ?",
                (user_id,))
            # Best-effort: clear "trusted device" cookies so the user
            # is forced through MFA next time.
            try:
                conn.execute(
                    "DELETE FROM trusted_devices WHERE user_id = ?",
                    (user_id,))
            except sqlite3.Error:
                pass
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("reset_mfa failed")
        raise UserAccountError(f"Could not reset MFA: {e}") from e
    lifecycle._audit(auth, "mfa_reset", user_id, None)
    logger.info("MFA reset for user_id=%d", user_id)


# ── 16. Sessions ──────────────────────────────────────────────────────

@dataclass
class SessionRow:
    id: int
    user_id: int
    token: str
    created_at: str
    expires_at: str
    is_active: bool


def list_sessions(auth: Any, user_id: int,
                    *, active_only: bool = True) -> list[SessionRow]:
    sql = "SELECT * FROM sessions WHERE user_id = ?"
    args: list = [user_id]
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY created_at DESC"
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_sessions failed")
        return []
    return [SessionRow(
        id=r["id"], user_id=r["user_id"], token=r["token"],
        created_at=r["created_at"], expires_at=r["expires_at"],
        is_active=bool(r["is_active"])) for r in rows]


def revoke_session(auth: Any, session_id: int) -> bool:
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute(
                "UPDATE sessions SET is_active = 0 WHERE id = ?",
                (session_id,))
            conn.commit()
            ok = cur.rowcount > 0
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("revoke_session failed")
        return False
    if ok:
        lifecycle._audit(auth, "session_revoked", None,
                          {"session_id": session_id})
    return ok


def revoke_all_sessions(auth: Any, user_id: int) -> int:
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute(
                "UPDATE sessions SET is_active = 0 "
                "WHERE user_id = ? AND is_active = 1", (user_id,))
            conn.commit()
            n = cur.rowcount
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("revoke_all_sessions failed")
        return 0
    lifecycle._audit(auth, "all_sessions_revoked", user_id,
                      {"count": n})
    return n


# ── 17. Failed-login dashboard ────────────────────────────────────────

@dataclass
class FailedLogin:
    when: str
    username: str | None
    user_id: int | None
    detail: str | None
    ip_address: str | None


def list_failed_logins(auth: Any, *, hours: int = 24
                         ) -> list[FailedLogin]:
    """Pull failed-login events from ``security_audit_log``. We look
    for event types that look like login failures."""
    cutoff = (datetime.datetime.now()
              - datetime.timedelta(hours=hours)).isoformat(
        timespec='seconds')
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute('''
                SELECT created_at, username, user_id, detail, ip_address
                FROM security_audit_log
                WHERE created_at >= ?
                  AND (lower(event_type) LIKE '%fail%'
                        OR lower(event_type) LIKE '%denied%'
                        OR lower(event_type) LIKE '%lock%'
                        OR lower(event_type) LIKE '%invalid%')
                ORDER BY created_at DESC
            ''', (cutoff,)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_failed_logins failed")
        return []
    return [FailedLogin(
        when=r["created_at"], username=r["username"],
        user_id=r["user_id"], detail=r["detail"],
        ip_address=r["ip_address"]) for r in rows]


# ── 18. Lock / unlock ─────────────────────────────────────────────────

def lock_user(auth: Any, user_id: int, *,
                reason: str | None = None,
                until: str | None = None,
                duration_hours: int | None = 24) -> UserRow:
    """Lock an account. ``until`` (ISO timestamp) wins if supplied,
    otherwise ``duration_hours`` is added to "now". The shared auth
    helper handles the actual ``locked_until`` write."""
    _init_schema(auth)
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    if until:
        try:
            datetime.datetime.fromisoformat(until)
        except ValueError as e:
            raise UserAccountError(
                "until must be ISO-8601 (YYYY-MM-DDTHH:MM).") from e
        locked_until = until
    else:
        hours = max(1, int(duration_hours or 24))
        locked_until = (datetime.datetime.now()
                         + datetime.timedelta(hours=hours)
                         ).isoformat(timespec='seconds')
    try:
        out = _ua.lock_user(auth, user_id, locked_until)
    except Exception as e:
        logger.exception("lock_user failed")
        raise UserAccountError(f"Could not lock: {e}") from e

    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                INSERT INTO user_lock_history
                (user_id, action, reason, locked_until, actor, at)
                VALUES (?, 'lock', ?, ?, ?, ?)
            ''', (user_id, (reason or '').strip() or None,
                  locked_until, actor, now))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("lock history append failed")

    lifecycle._audit(auth, "user_lock", user_id,
                      {"reason": reason,
                       "locked_until": locked_until})
    return out


def unlock_user(auth: Any, user_id: int) -> UserRow:
    _init_schema(auth)
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    try:
        out = _ua.unlock_user(auth, user_id)
    except Exception as e:
        logger.exception("unlock_user failed")
        raise UserAccountError(f"Could not unlock: {e}") from e
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                INSERT INTO user_lock_history
                (user_id, action, reason, locked_until, actor, at)
                VALUES (?, 'unlock', NULL, NULL, ?, ?)
            ''', (user_id, actor, now))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("unlock history append failed")
    lifecycle._audit(auth, "user_unlock", user_id, None)
    return out


def lock_history(auth: Any, user_id: int) -> list[dict]:
    _init_schema(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM user_lock_history WHERE user_id = ? "
                "ORDER BY at DESC", (user_id,)).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("lock_history failed")
        return []


# ── 19. Password-age report ───────────────────────────────────────────

@dataclass
class PasswordAgeRow:
    user_id: int
    username: str
    display_name: str | None
    password_changed_at: str | None
    days_since_change: int | None


def password_age_report(auth: Any,
                          *, min_age_days: int = 90,
                          include_never_set: bool = True
                          ) -> list[PasswordAgeRow]:
    rows = _ua.list_users(auth)
    now = datetime.datetime.now()
    out: list[PasswordAgeRow] = []
    for u in rows:
        days: int | None
        if u.password_changed_at:
            try:
                changed = datetime.datetime.fromisoformat(
                    u.password_changed_at)
                days = (now - changed).days
            except ValueError:
                days = None
        else:
            days = None
        keep = False
        if days is None:
            keep = include_never_set
        elif days >= min_age_days:
            keep = True
        if keep:
            out.append(PasswordAgeRow(
                user_id=u.id, username=u.username,
                display_name=u.display_name,
                password_changed_at=u.password_changed_at,
                days_since_change=days,
            ))
    out.sort(key=lambda r: (r.days_since_change is not None,
                              r.days_since_change or -1),
              reverse=True)
    return out


# ── 20. Compromised-password check ────────────────────────────────────

def import_breach_list(auth: Any, source_path: str,
                        *, source_label: str | None = None
                        ) -> int:
    """Bulk-load SHA-1 hashes (one per line, hex). Empty lines and
    comments (#…) are skipped. Existing rows are kept (PK conflict
    ignored) so re-imports are safe."""
    _init_schema(auth)
    p = Path(source_path)
    if not p.is_file():
        raise UserAccountError(f"Breach list not found: {source_path}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    label = source_label or p.name
    inserted = 0
    try:
        conn = lifecycle._conn(auth)
        try:
            with p.open("r", encoding="utf-8") as f:
                batch: list[tuple] = []
                for raw in f:
                    h = raw.strip().split(":", 1)[0]   # tolerate HIBP "hash:count" rows
                    if not h or h.startswith("#"):
                        continue
                    if len(h) != 40:
                        continue
                    batch.append((h.lower(), label, now))
                    if len(batch) >= 2000:
                        cur = conn.executemany(
                            "INSERT OR IGNORE INTO user_breach_list "
                            "(sha1_hex, source, imported_at) VALUES "
                            "(?, ?, ?)", batch)
                        inserted += cur.rowcount or 0
                        batch.clear()
                if batch:
                    cur = conn.executemany(
                        "INSERT OR IGNORE INTO user_breach_list "
                        "(sha1_hex, source, imported_at) VALUES "
                        "(?, ?, ?)", batch)
                    inserted += cur.rowcount or 0
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("import_breach_list failed")
        raise UserAccountError(f"Import failed: {e}") from e
    lifecycle._audit(auth, "breach_list_imported", None,
                      {"source": label, "inserted": inserted})
    return inserted


def check_password_compromised(auth: Any, password: str) -> bool:
    """Return True if ``password`` SHA-1 is in the local breach list."""
    if not password:
        return False
    _init_schema(auth)
    sha1 = hashlib.sha1(password.encode()).hexdigest().lower()
    try:
        conn = lifecycle._conn(auth)
        try:
            r = conn.execute(
                "SELECT 1 FROM user_breach_list WHERE sha1_hex = ? LIMIT 1",
                (sha1,)).fetchone()
            return r is not None
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("check_password_compromised failed")
        return False


def breach_list_stats(auth: Any) -> dict:
    _init_schema(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM user_breach_list").fetchone()[0]
            latest = conn.execute(
                "SELECT MAX(imported_at) FROM user_breach_list"
            ).fetchone()[0]
            return {"hashes": int(n or 0),
                    "latest_import": latest}
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("breach_list_stats failed")
        return {"hashes": 0, "latest_import": None}
