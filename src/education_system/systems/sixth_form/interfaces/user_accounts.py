"""User accounts admin for the Sixth Form System.

A thin admin layer on top of the **shared** auth tables
(``users``, ``user_systems``, ``password_history``). Designed for
the local "User Accounts" menu — i.e. an admin signed into the
sixth-form system managing its users.

Doesn't own any of those tables — every read/write goes through the
shared auth DB. ``create_user`` and password strength reuse the
shared auth helpers; admin-side password reset, lock/unlock, and
active-flag toggling fill in functionality the shared facade doesn't
expose.

System key for the sixth form is ``"sixth_form"`` (matches the
launcher / role-manager nomenclature).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from education_system.platform.identity.auth.db import connect as _auth_connect
from education_system.platform.identity.auth.exceptions import AuthError
from education_system.platform.identity.auth.password_manager import (
    hash_password,
    validate_password_strength,
)
from education_system.platform.identity.auth.role_manager import ROLE_HIERARCHY

logger = logging.getLogger(__name__)

SYSTEM_KEY: str = "sixth_form"

ROLES: tuple[str, ...] = tuple(sorted(ROLE_HIERARCHY.keys(),
                                          key=lambda r: -ROLE_HIERARCHY[r]))
DEFAULT_ROLE: str = "staff"


class UserAccountError(ValueError):
    pass


@dataclass
class UserRow:
    id: int
    username: str
    display_name: str | None
    email: str | None
    is_active: bool
    locked_until: str | None
    failed_login_attempts: int
    created_at: str
    updated_at: str
    last_login: str | None
    password_changed_at: str | None
    systems: list[dict] = field(default_factory=list)

    @property
    def is_locked(self) -> bool:
        if not self.locked_until:
            return False
        try:
            return (datetime.fromisoformat(self.locked_until)
                    > datetime.utcnow())
        except ValueError:
            return False

    def role_for(self, system_key: str) -> str | None:
        for s in self.systems:
            if s.get("system_key") == system_key:
                return s.get("role")
        return None


# ── DB plumbing ────────────────────────────────────────────────────

def _db_path(auth: Any) -> str | None:
    return getattr(auth, "_db_path", None)


def _conn(auth: Any):
    return _auth_connect(_db_path(auth))


def _row_to_user(r) -> UserRow:
    locked = r["locked_until"] if "locked_until" in r.keys() else None
    return UserRow(
        id=r["id"], username=r["username"],
        display_name=r["display_name"],
        email=r["email"],
        is_active=bool(r["is_active"]),
        locked_until=locked,
        failed_login_attempts=r["failed_login_attempts"]
            if "failed_login_attempts" in r.keys() else 0,
        created_at=r["created_at"],
        updated_at=r["updated_at"] if "updated_at" in r.keys()
            else r["created_at"],
        last_login=r["last_login"] if "last_login" in r.keys()
            else None,
        password_changed_at=r["password_changed_at"]
            if "password_changed_at" in r.keys() else None,
    )


def _load_systems(auth: Any, user_id: int) -> list[dict]:
    return auth.role_manager.get_user_systems(user_id)


# ── Listing / fetching ─────────────────────────────────────────────

def list_users(
    auth: Any,
    *,
    query: str | None = None,
    system_key: str | None = None,
    role: str | None = None,
    active_only: bool = False,
    locked_only: bool = False,
) -> list[UserRow]:
    clauses: list[str] = []
    args: list[Any] = []
    if query:
        like = f"%{query.strip()}%"
        clauses.append(
            "(u.username LIKE ? OR u.display_name LIKE ? "
            "OR u.email LIKE ?)")
        args.extend([like, like, like])
    if system_key:
        if role:
            if role not in ROLE_HIERARCHY:
                raise UserAccountError(
                    f"Role must be one of: "
                    f"{', '.join(ROLE_HIERARCHY.keys())}")
            clauses.append(
                "u.id IN (SELECT user_id FROM user_systems "
                "         WHERE system_key = ? AND role = ?)")
            args.extend([system_key, role])
        else:
            clauses.append(
                "u.id IN (SELECT user_id FROM user_systems "
                "         WHERE system_key = ?)")
            args.append(system_key)
    elif role:
        if role not in ROLE_HIERARCHY:
            raise UserAccountError(
                f"Role must be one of: "
                f"{', '.join(ROLE_HIERARCHY.keys())}")
        clauses.append(
            "u.id IN (SELECT user_id FROM user_systems "
            "         WHERE role = ?)")
        args.append(role)
    if active_only:
        clauses.append("u.is_active = 1")
    if locked_only:
        clauses.append(
            "u.locked_until IS NOT NULL "
            "AND u.locked_until > datetime('now')")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT u.* FROM users u {where} "
           "ORDER BY u.username")
    conn = _conn(auth)
    try:
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    out: list[UserRow] = []
    for r in rows:
        u = _row_to_user(r)
        u.systems = _load_systems(auth, u.id)
        out.append(u)
    return out


def get_user(auth: Any, user_id: int) -> UserRow | None:
    conn = _conn(auth)
    try:
        r = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    u = _row_to_user(r)
    u.systems = _load_systems(auth, u.id)
    return u


def get_by_username(auth: Any, username: str) -> UserRow | None:
    conn = _conn(auth)
    try:
        r = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),)).fetchone()
    finally:
        conn.close()
    if r is None:
        return None
    u = _row_to_user(r)
    u.systems = _load_systems(auth, u.id)
    return u


# ── Create / update ────────────────────────────────────────────────

def create_user(
    auth: Any,
    *,
    username: str,
    password: str,
    display_name: str | None = None,
    email: str | None = None,
    system_key: str | None = SYSTEM_KEY,
    role: str | None = DEFAULT_ROLE,
) -> UserRow:
    if not (username or "").strip():
        raise UserAccountError("Username is required.")
    if not password:
        raise UserAccountError("Password is required.")
    if role is not None and role not in ROLE_HIERARCHY:
        raise UserAccountError(
            f"Role must be one of: {', '.join(ROLE_HIERARCHY.keys())}")
    systems = [(system_key, role)] if (system_key and role) else None
    try:
        uid = auth.create_user(
            username=username.strip(),
            password=password,
            display_name=(display_name or "").strip() or None,
            email=(email or "").strip() or None,
            systems=systems,
        )
    except AuthError as e:
        raise UserAccountError(str(e)) from e
    out = get_user(auth, uid)
    assert out is not None
    logger.info("Created user '%s' (id=%d)", username, uid)
    return out


def update_profile(
    auth: Any,
    user_id: int,
    *,
    display_name: str | None = None,
    email: str | None = None,
) -> UserRow:
    if get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    conn = _conn(auth)
    try:
        conn.execute(
            "UPDATE users SET display_name = ?, email = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            ((display_name or "").strip() or None,
             (email or "").strip() or None,
             user_id))
        conn.commit()
    finally:
        conn.close()
    out = get_user(auth, user_id)
    assert out is not None
    logger.info("Updated profile for user_id=%d", user_id)
    return out


def admin_reset_password(
    auth: Any, user_id: int, new_password: str,
) -> UserRow:
    """Set a new password without requiring the old one. Saves the
    existing hash to password_history (so it counts toward the
    no-reuse-of-last-5 policy) and invalidates any active sessions
    for that user."""
    if not new_password:
        raise UserAccountError("New password is required.")
    is_valid, msg = validate_password_strength(new_password)
    if not is_valid:
        raise UserAccountError(msg)
    user = get_user(auth, user_id)
    if user is None:
        raise UserAccountError(f"No user #{user_id}")

    new_hash = hash_password(new_password)
    conn = _conn(auth)
    try:
        old_hash_row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,)).fetchone()
        old_hash = old_hash_row["password_hash"] if old_hash_row else None
        if old_hash:
            conn.execute(
                "INSERT INTO password_history (user_id, password_hash) "
                "VALUES (?, ?)", (user_id, old_hash))
        conn.execute(
            "UPDATE users SET password_hash = ?, "
            "password_changed_at = datetime('now'), "
            "failed_login_attempts = 0, locked_until = NULL, "
            "updated_at = datetime('now') WHERE id = ?",
            (new_hash, user_id))
        conn.commit()
    finally:
        conn.close()
    try:
        auth.session_manager.invalidate_user_sessions(user_id)
    except Exception:
        logger.warning(
            "Failed to invalidate sessions for user_id=%d",
            user_id, exc_info=True)
    logger.info("Admin-reset password for user_id=%d", user_id)
    out = get_user(auth, user_id)
    assert out is not None
    return out


def set_active(auth: Any, user_id: int, active: bool) -> UserRow:
    if get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    conn = _conn(auth)
    try:
        conn.execute(
            "UPDATE users SET is_active = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (1 if active else 0, user_id))
        conn.commit()
    finally:
        conn.close()
    if not active:
        try:
            auth.session_manager.invalidate_user_sessions(user_id)
        except Exception:
            logger.warning(
                "Failed to invalidate sessions on deactivate "
                "for user_id=%d", user_id, exc_info=True)
    logger.info("Set is_active=%s for user_id=%d", active, user_id)
    out = get_user(auth, user_id)
    assert out is not None
    return out


def lock_user(auth: Any, user_id: int,
                minutes: int = 60) -> UserRow:
    if minutes <= 0 or minutes > 60 * 24 * 365:
        raise UserAccountError("Lock duration must be 1..525600 min")
    if get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    until = (datetime.utcnow() + timedelta(minutes=minutes)
              ).isoformat(timespec="seconds")
    conn = _conn(auth)
    try:
        conn.execute(
            "UPDATE users SET locked_until = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (until, user_id))
        conn.commit()
    finally:
        conn.close()
    try:
        auth.session_manager.invalidate_user_sessions(user_id)
    except Exception:
        logger.warning(
            "Failed to invalidate sessions on lock for user_id=%d",
            user_id, exc_info=True)
    logger.info("Locked user_id=%d until %s", user_id, until)
    out = get_user(auth, user_id)
    assert out is not None
    return out


def unlock_user(auth: Any, user_id: int) -> UserRow:
    if get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    conn = _conn(auth)
    try:
        conn.execute(
            "UPDATE users SET locked_until = NULL, "
            "failed_login_attempts = 0, "
            "updated_at = datetime('now') WHERE id = ?",
            (user_id,))
        conn.commit()
    finally:
        conn.close()
    logger.info("Unlocked user_id=%d", user_id)
    out = get_user(auth, user_id)
    assert out is not None
    return out


def delete_user(auth: Any, user_id: int) -> bool:
    user = get_user(auth, user_id)
    if user is None:
        return False
    cur = getattr(auth, "current_user", None) or {}
    if cur.get("id") == user_id:
        raise UserAccountError(
            "You can't delete the account you're signed in as.")
    conn = _conn(auth)
    try:
        conn.execute("DELETE FROM user_systems WHERE user_id = ?",
                      (user_id,))
        conn.execute("DELETE FROM sessions WHERE user_id = ?",
                      (user_id,))
        try:
            conn.execute(
                "DELETE FROM password_history WHERE user_id = ?",
                (user_id,))
        except Exception:
            pass
        try:
            conn.execute(
                "DELETE FROM mfa_secrets WHERE user_id = ?",
                (user_id,))
            conn.execute(
                "DELETE FROM mfa_recovery_codes WHERE user_id = ?",
                (user_id,))
        except Exception:
            pass
        cur2 = conn.execute("DELETE FROM users WHERE id = ?",
                              (user_id,))
        conn.commit()
        deleted = cur2.rowcount > 0
    finally:
        conn.close()
    if deleted:
        logger.info("Deleted user '%s' (id=%d)",
                    user.username, user_id)
    return deleted


# ── Role / system access ───────────────────────────────────────────

def grant_role(auth: Any, user_id: int, system_key: str,
                  role: str) -> UserRow:
    if role not in ROLE_HIERARCHY:
        raise UserAccountError(
            f"Role must be one of: "
            f"{', '.join(ROLE_HIERARCHY.keys())}")
    if get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    auth.role_manager.grant_system_access(user_id, system_key, role)
    out = get_user(auth, user_id)
    assert out is not None
    return out


def revoke_role(auth: Any, user_id: int,
                  system_key: str) -> UserRow:
    if get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    auth.role_manager.revoke_system_access(user_id, system_key)
    out = get_user(auth, user_id)
    assert out is not None
    return out


# ── Summary ────────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    active: int
    inactive: int
    locked: int
    sixth_form_users: int
    by_role_in_sixthform: dict[str, int]
    recent_logins_7d: int


def summary(auth: Any) -> Summary:
    users = list_users(auth)
    total = len(users)
    active = sum(1 for u in users if u.is_active)
    inactive = total - active
    locked = sum(1 for u in users if u.is_locked)
    sixth = [u for u in users if u.role_for(SYSTEM_KEY)]
    by_role = {r: 0 for r in ROLE_HIERARCHY}
    for u in sixth:
        r = u.role_for(SYSTEM_KEY)
        if r:
            by_role[r] = by_role.get(r, 0) + 1
    cutoff = (datetime.utcnow() - timedelta(days=7)
              ).isoformat(timespec="seconds")
    recent = sum(1 for u in users
                  if u.last_login and u.last_login >= cutoff)
    return Summary(
        total=total, active=active, inactive=inactive,
        locked=locked,
        sixth_form_users=len(sixth),
        by_role_in_sixthform=by_role,
        recent_logins_7d=recent,
    )
