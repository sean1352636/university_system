"""Account lifecycle helpers for Sixth Form User Management.

Implements the create / edit / archive / restore / purge flows on top
of the shared auth DB:

* extended profile fields (phone, department, job_title, line_manager)
  are stored in a side-table ``user_profile_extras`` so the auth
  ``users`` table itself stays untouched and remains shareable across
  systems;
* soft-delete writes a tombstone row in ``user_archives`` capturing the
  whole user record + reason + retention date, then sets the user
  inactive. ``restore_user`` undoes that while the retention window is
  still open;
* permanent delete calls ``user_accounts.delete_user`` and appends an
  immutable row to ``user_audit_log``.

All three tables are created lazily on first use (idempotent
``CREATE TABLE IF NOT EXISTS``), so callers don't need a migration
step. Every write goes through ``logger.info`` and an audit row so
governance reviews can trace any of these actions.
"""

from __future__ import annotations

import datetime
import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.interfaces import user_accounts as _ua
from education_system.systems.sixth_form.interfaces.user_accounts import (
    DEFAULT_ROLE, SYSTEM_KEY, UserAccountError, UserRow,
)

logger = logging.getLogger(__name__)


# ── DB plumbing ────────────────────────────────────────────────────────

def _conn(auth: Any) -> sqlite3.Connection:
    """Open the shared auth DB the same way user_accounts does."""
    return _ua._conn(auth)


def init_lifecycle_schema(auth: Any) -> None:
    """Idempotently create the lifecycle tables."""
    try:
        conn = _conn(auth)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_suspensions (
                    suspension_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    reason TEXT,
                    started_at TEXT NOT NULL,
                    started_by TEXT,
                    resume_at TEXT,
                    status TEXT NOT NULL DEFAULT 'Active',
                    ended_at TEXT,
                    ended_by TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_suspensions_user
                ON user_suspensions(user_id, status)
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_profile_extras (
                    user_id INTEGER PRIMARY KEY,
                    phone TEXT,
                    department TEXT,
                    job_title TEXT,
                    line_manager_id INTEGER,
                    notes TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_archives (
                    archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    archived_at TEXT NOT NULL,
                    archived_by TEXT,
                    reason TEXT,
                    retention_until TEXT,
                    status TEXT NOT NULL DEFAULT 'Archived',
                    snapshot TEXT NOT NULL,            -- JSON
                    restored_at TEXT,
                    restored_by TEXT,
                    purged_at TEXT,
                    purged_by TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_archives_user
                ON user_archives(user_id, status)
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_audit_log (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    actor TEXT,
                    action TEXT NOT NULL,
                    target_user_id INTEGER,
                    details TEXT
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_audit_target
                ON user_audit_log(target_user_id, ts)
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Failed to init lifecycle schemas")
        raise


def _audit(auth: Any, action: str, target_user_id: int | None,
            details: dict | str | None) -> None:
    """Append an immutable row to ``user_audit_log``. Never raises —
    audit failure should not block the parent action; surfaced via
    logger.exception so it's still visible."""
    try:
        init_lifecycle_schema(auth)
        actor = _actor_name(auth)
        ts = datetime.datetime.now().isoformat(timespec='seconds')
        detail_text = (json.dumps(details, default=str)
                        if isinstance(details, dict) else (details or ''))
        conn = _conn(auth)
        try:
            conn.execute(
                "INSERT INTO user_audit_log "
                "(ts, actor, action, target_user_id, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, actor, action, target_user_id, detail_text))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("user_audit_log write failed (action=%s, "
                          "target=%s)", action, target_user_id)


def _actor_name(auth: Any) -> str:
    """Best-effort current-user string for audit rows."""
    try:
        cu = getattr(auth, 'current_user', None) or {}
        return cu.get('username') or cu.get('display_name') or 'system'
    except Exception:
        return 'system'


# ── Extended profile ──────────────────────────────────────────────────

@dataclass
class ProfileExtras:
    user_id: int
    phone: str | None = None
    department: str | None = None
    job_title: str | None = None
    line_manager_id: int | None = None
    notes: str | None = None
    updated_at: str | None = None


def get_extras(auth: Any, user_id: int) -> ProfileExtras:
    """Return extras for ``user_id``; an all-None row if none stored."""
    init_lifecycle_schema(auth)
    try:
        conn = _conn(auth)
        try:
            r = conn.execute(
                "SELECT * FROM user_profile_extras WHERE user_id = ?",
                (user_id,)).fetchone()
            if r is None:
                return ProfileExtras(user_id=user_id)
            return ProfileExtras(
                user_id=r["user_id"], phone=r["phone"],
                department=r["department"], job_title=r["job_title"],
                line_manager_id=r["line_manager_id"], notes=r["notes"],
                updated_at=r["updated_at"])
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("get_extras failed for user_id=%d", user_id)
        return ProfileExtras(user_id=user_id)


def set_extras(auth: Any, user_id: int, *,
                phone: str | None = None,
                department: str | None = None,
                job_title: str | None = None,
                line_manager_id: int | None = None,
                notes: str | None = None) -> ProfileExtras:
    """Upsert extras. Empty strings become NULL so the row stays tidy."""
    init_lifecycle_schema(auth)
    now = datetime.datetime.now().isoformat(timespec='seconds')

    def _clean(v):
        return (v or "").strip() or None if isinstance(v, str) else v
    phone = _clean(phone)
    department = _clean(department)
    job_title = _clean(job_title)
    notes = _clean(notes)

    try:
        conn = _conn(auth)
        try:
            conn.execute('''
                INSERT INTO user_profile_extras
                (user_id, phone, department, job_title, line_manager_id,
                 notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    phone=excluded.phone,
                    department=excluded.department,
                    job_title=excluded.job_title,
                    line_manager_id=excluded.line_manager_id,
                    notes=excluded.notes,
                    updated_at=excluded.updated_at
            ''', (user_id, phone, department, job_title, line_manager_id,
                  notes, now))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("set_extras failed for user_id=%d", user_id)
        raise UserAccountError(f"Could not save extras: {e}") from e

    _audit(auth, "profile_extras_update", user_id, {
        "phone": phone, "department": department,
        "job_title": job_title, "line_manager_id": line_manager_id,
    })
    logger.info("Updated profile extras for user_id=%d", user_id)
    return get_extras(auth, user_id)


# ── Create user (full) ────────────────────────────────────────────────

def create_user_full(
    auth: Any, *,
    username: str, password: str,
    display_name: str | None = None,
    email: str | None = None,
    role: str | None = DEFAULT_ROLE,
    system_key: str | None = SYSTEM_KEY,
    phone: str | None = None,
    department: str | None = None,
    job_title: str | None = None,
    line_manager_id: int | None = None,
    notes: str | None = None,
) -> UserRow:
    """Create user via the shared helper, then attach extras. Errors at
    either step raise ``UserAccountError`` and audit the failed attempt."""
    init_lifecycle_schema(auth)
    try:
        user = _ua.create_user(
            auth,
            username=username, password=password,
            display_name=display_name, email=email,
            system_key=system_key, role=role,
        )
    except Exception as e:
        _audit(auth, "user_create_failed", None,
                {"username": username, "error": str(e)})
        raise
    try:
        set_extras(auth, user.id, phone=phone, department=department,
                    job_title=job_title, line_manager_id=line_manager_id,
                    notes=notes)
    except Exception:
        # Don't unwind the user creation — surface and log.
        logger.exception("Created user but extras attach failed "
                          "(user_id=%d)", user.id)
    _audit(auth, "user_create", user.id, {
        "username": username, "role": role, "system_key": system_key,
    })
    return user


# ── Edit user (full) ──────────────────────────────────────────────────

def update_user_full(
    auth: Any, user_id: int, *,
    display_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    department: str | None = None,
    job_title: str | None = None,
    line_manager_id: int | None = None,
    notes: str | None = None,
) -> UserRow:
    """Update both the core profile (display_name/email) and the
    extras side-table. Either side can fail without rolling the other
    back — both failures audit."""
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    init_lifecycle_schema(auth)
    try:
        _ua.update_profile(auth, user_id,
                            display_name=display_name, email=email)
    except Exception as e:
        _audit(auth, "user_update_core_failed", user_id, {"error": str(e)})
        raise
    try:
        set_extras(auth, user_id, phone=phone, department=department,
                    job_title=job_title, line_manager_id=line_manager_id,
                    notes=notes)
    except Exception:
        logger.exception("Core updated but extras failed "
                          "(user_id=%d)", user_id)
    _audit(auth, "user_update", user_id, {
        "display_name": display_name, "email": email,
        "phone": phone, "department": department,
        "job_title": job_title, "line_manager_id": line_manager_id,
    })
    return _ua.get_user(auth, user_id)


# ── Archive / soft-delete ─────────────────────────────────────────────

DEFAULT_RETENTION_DAYS = 90


@dataclass
class ArchiveRow:
    archive_id: int
    user_id: int
    archived_at: str
    archived_by: str | None
    reason: str | None
    retention_until: str | None
    status: str                  # 'Archived' | 'Restored' | 'Purged'
    snapshot: dict


def _snapshot_user(auth: Any, user: UserRow) -> dict:
    extras = get_extras(auth, user.id)
    return {
        "id": user.id, "username": user.username,
        "display_name": user.display_name, "email": user.email,
        "is_active": user.is_active,
        "locked_until": user.locked_until,
        "last_login": user.last_login,
        "password_changed_at": user.password_changed_at,
        "systems": user.systems,
        "extras": {
            "phone": extras.phone,
            "department": extras.department,
            "job_title": extras.job_title,
            "line_manager_id": extras.line_manager_id,
            "notes": extras.notes,
        },
    }


def archive_user(auth: Any, user_id: int, *,
                  reason: str | None = None,
                  retention_days: int = DEFAULT_RETENTION_DAYS) -> ArchiveRow:
    """Snapshot the user record, mark archived, deactivate the login.

    Raises ``UserAccountError`` if the user is already archived in an
    open (non-purged) row.
    """
    init_lifecycle_schema(auth)
    user = _ua.get_user(auth, user_id)
    if user is None:
        raise UserAccountError(f"No user #{user_id}")
    try:
        retention_days = int(retention_days)
    except (TypeError, ValueError):
        retention_days = DEFAULT_RETENTION_DAYS
    retention_days = max(1, min(retention_days, 3650))    # 1 day – 10 years

    now = datetime.datetime.now()
    archived_at = now.isoformat(timespec='seconds')
    retention_until = (now + datetime.timedelta(days=retention_days)) \
        .isoformat(timespec='seconds')
    actor = _actor_name(auth)
    snapshot = _snapshot_user(auth, user)

    try:
        conn = _conn(auth)
        try:
            existing = conn.execute(
                "SELECT archive_id FROM user_archives "
                "WHERE user_id = ? AND status = 'Archived'",
                (user_id,)).fetchone()
            if existing:
                raise UserAccountError(
                    f"User #{user_id} already has an open archive row "
                    f"(#{existing['archive_id']}). Restore or purge it first.")
            cur = conn.execute('''
                INSERT INTO user_archives
                (user_id, archived_at, archived_by, reason,
                 retention_until, status, snapshot)
                VALUES (?, ?, ?, ?, ?, 'Archived', ?)
            ''', (user_id, archived_at, actor, (reason or '').strip() or None,
                  retention_until, json.dumps(snapshot)))
            archive_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("archive_user DB failure")
        raise UserAccountError(f"Could not archive: {e}") from e

    # Disable login last — if it fails the archive row is already in
    # place and audit will show the discrepancy.
    try:
        _ua.set_active(auth, user_id, False)
    except Exception as e:
        logger.exception("Archive recorded but deactivate failed "
                          "(user_id=%d)", user_id)
        _audit(auth, "user_archive_partial", user_id,
                {"archive_id": archive_id, "error": str(e)})
    _audit(auth, "user_archive", user_id, {
        "archive_id": archive_id, "reason": reason,
        "retention_until": retention_until,
    })
    logger.info("Archived user_id=%d as archive_id=%d "
                "(retention_until=%s)", user_id, archive_id, retention_until)

    return ArchiveRow(
        archive_id=archive_id, user_id=user_id,
        archived_at=archived_at, archived_by=actor, reason=reason,
        retention_until=retention_until, status='Archived',
        snapshot=snapshot,
    )


def restore_user(auth: Any, archive_id: int) -> UserRow:
    """Re-activate an archived user, but only while the retention
    window is still open. Past retention you can no longer restore —
    the row stays for audit but the action is blocked."""
    init_lifecycle_schema(auth)
    try:
        conn = _conn(auth)
        try:
            r = conn.execute(
                "SELECT * FROM user_archives WHERE archive_id = ?",
                (archive_id,)).fetchone()
            if r is None:
                raise UserAccountError(f"No archive #{archive_id}")
            if r["status"] != 'Archived':
                raise UserAccountError(
                    f"Archive #{archive_id} status is {r['status']!r} — "
                    "cannot restore.")
            retention = r["retention_until"]
            if retention:
                try:
                    until = datetime.datetime.fromisoformat(retention)
                    if datetime.datetime.now() > until:
                        raise UserAccountError(
                            f"Retention window closed on {retention} — "
                            "cannot restore. Permanent delete only.")
                except ValueError:
                    pass
            user_id = r["user_id"]
            actor = _actor_name(auth)
            now = datetime.datetime.now().isoformat(timespec='seconds')
            conn.execute(
                "UPDATE user_archives SET status='Restored', "
                "restored_at=?, restored_by=? WHERE archive_id=?",
                (now, actor, archive_id))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("restore_user DB failure")
        raise UserAccountError(f"Could not restore: {e}") from e

    try:
        _ua.set_active(auth, user_id, True)
    except Exception as e:
        logger.exception("Archive flipped but reactivate failed "
                          "(user_id=%d)", user_id)
        _audit(auth, "user_restore_partial", user_id,
                {"archive_id": archive_id, "error": str(e)})
        raise UserAccountError(f"Restored archive row but could not "
                                f"reactivate user: {e}") from e

    _audit(auth, "user_restore", user_id, {"archive_id": archive_id})
    logger.info("Restored archive_id=%d (user_id=%d)", archive_id, user_id)
    out = _ua.get_user(auth, user_id)
    assert out is not None
    return out


# ── Permanent delete ──────────────────────────────────────────────────

def purge_user(auth: Any, user_id: int, *,
                reason: str | None = None,
                confirmation_token: str | None = None) -> bool:
    """Permanently delete the user. Requires ``confirmation_token`` to
    equal the user's username — a cheap second-factor that protects
    against muscle-memory deletes. Always writes an audit row first,
    so even a failed delete leaves a trace."""
    user = _ua.get_user(auth, user_id)
    if user is None:
        raise UserAccountError(f"No user #{user_id}")
    if (confirmation_token or '').strip() != user.username:
        raise UserAccountError(
            "Confirmation token must match the user's exact username.")

    init_lifecycle_schema(auth)
    snap = _snapshot_user(auth, user)
    _audit(auth, "user_purge_attempt", user_id, {
        "reason": reason, "snapshot": snap,
    })

    try:
        ok = _ua.delete_user(auth, user_id)
    except Exception as e:
        logger.exception("purge_user delete failed (user_id=%d)", user_id)
        _audit(auth, "user_purge_failed", user_id, {"error": str(e)})
        raise UserAccountError(f"Delete failed: {e}") from e
    if not ok:
        _audit(auth, "user_purge_failed", user_id,
                {"error": "delete_user returned False"})
        return False

    # Flip any open archives to Purged so the lifecycle is closed out.
    try:
        now = datetime.datetime.now().isoformat(timespec='seconds')
        actor = _actor_name(auth)
        conn = _conn(auth)
        try:
            conn.execute(
                "UPDATE user_archives "
                "SET status='Purged', purged_at=?, purged_by=? "
                "WHERE user_id=? AND status='Archived'",
                (now, actor, user_id))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not close out archive rows for "
                          "purged user_id=%d", user_id)

    _audit(auth, "user_purge", user_id, {"reason": reason})
    logger.info("Permanently deleted user_id=%d (username=%s)",
                user_id, user.username)
    return True


# ── Listings ──────────────────────────────────────────────────────────

def list_archived(auth: Any, *,
                    include_purged: bool = False,
                    include_restored: bool = False) -> list[ArchiveRow]:
    init_lifecycle_schema(auth)
    states = ['Archived']
    if include_restored:
        states.append('Restored')
    if include_purged:
        states.append('Purged')
    qmarks = ",".join("?" * len(states))
    try:
        conn = _conn(auth)
        try:
            rows = conn.execute(
                f"SELECT * FROM user_archives WHERE status IN ({qmarks}) "
                "ORDER BY archived_at DESC", states).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_archived failed")
        return []
    out: list[ArchiveRow] = []
    for r in rows:
        try:
            snap = json.loads(r["snapshot"])
        except Exception:
            snap = {}
        out.append(ArchiveRow(
            archive_id=r["archive_id"], user_id=r["user_id"],
            archived_at=r["archived_at"], archived_by=r["archived_by"],
            reason=r["reason"], retention_until=r["retention_until"],
            status=r["status"], snapshot=snap,
        ))
    return out


# ── Suspend / unsuspend ───────────────────────────────────────────────

@dataclass
class SuspensionRow:
    suspension_id: int
    user_id: int
    reason: str | None
    started_at: str
    started_by: str | None
    resume_at: str | None
    status: str                  # 'Active' | 'Resumed' | 'Cancelled'


def suspend_user(auth: Any, user_id: int, *,
                  reason: str | None = None,
                  resume_at: str | None = None) -> SuspensionRow:
    """Disable login + record a suspension row. ``resume_at`` is
    informational (cron jobs / dashboards can scan this); the user
    stays inactive until ``unsuspend_user`` is called.

    Raises ``UserAccountError`` if there's already an active suspension
    for this user."""
    init_lifecycle_schema(auth)
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    if resume_at:
        try:
            datetime.datetime.fromisoformat(resume_at)
        except ValueError as e:
            raise UserAccountError(
                "resume_at must be ISO-8601 (YYYY-MM-DD or "
                "YYYY-MM-DDTHH:MM).") from e
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = _actor_name(auth)
    try:
        conn = _conn(auth)
        try:
            existing = conn.execute(
                "SELECT suspension_id FROM user_suspensions "
                "WHERE user_id = ? AND status = 'Active'",
                (user_id,)).fetchone()
            if existing:
                raise UserAccountError(
                    f"User #{user_id} is already suspended "
                    f"(#{existing['suspension_id']}).")
            cur = conn.execute('''
                INSERT INTO user_suspensions
                (user_id, reason, started_at, started_by, resume_at,
                 status)
                VALUES (?, ?, ?, ?, ?, 'Active')
            ''', (user_id, (reason or '').strip() or None,
                  now, actor, resume_at))
            sid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("suspend_user DB failure")
        raise UserAccountError(f"Could not suspend: {e}") from e

    try:
        _ua.set_active(auth, user_id, False)
    except Exception as e:
        logger.exception("Suspension recorded but deactivate failed "
                          "(user_id=%d)", user_id)
        _audit(auth, "user_suspend_partial", user_id,
                {"suspension_id": sid, "error": str(e)})
    _audit(auth, "user_suspend", user_id, {
        "suspension_id": sid, "reason": reason, "resume_at": resume_at,
    })
    logger.info("Suspended user_id=%d (suspension_id=%d, resume_at=%s)",
                user_id, sid, resume_at)
    return SuspensionRow(
        suspension_id=sid, user_id=user_id, reason=reason,
        started_at=now, started_by=actor, resume_at=resume_at,
        status='Active')


def unsuspend_user(auth: Any, user_id: int, *,
                    cancel: bool = False) -> UserRow:
    """Close the active suspension (status flips to ``Resumed`` or
    ``Cancelled``) and reactivate the user."""
    init_lifecycle_schema(auth)
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = _actor_name(auth)
    new_status = 'Cancelled' if cancel else 'Resumed'
    try:
        conn = _conn(auth)
        try:
            cur = conn.execute('''
                UPDATE user_suspensions
                   SET status = ?, ended_at = ?, ended_by = ?
                 WHERE user_id = ? AND status = 'Active'
            ''', (new_status, now, actor, user_id))
            changed = cur.rowcount
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("unsuspend_user DB failure")
        raise UserAccountError(f"Could not unsuspend: {e}") from e
    if changed == 0:
        raise UserAccountError(
            f"User #{user_id} has no active suspension.")
    try:
        _ua.set_active(auth, user_id, True)
    except Exception as e:
        logger.exception("Suspension closed but reactivate failed "
                          "(user_id=%d)", user_id)
        _audit(auth, "user_unsuspend_partial", user_id,
                {"error": str(e)})
        raise UserAccountError(f"Closed suspension row but could not "
                                f"reactivate user: {e}") from e
    _audit(auth, "user_unsuspend", user_id,
            {"new_status": new_status})
    logger.info("Unsuspended user_id=%d (status=%s)",
                user_id, new_status)
    out = _ua.get_user(auth, user_id)
    assert out is not None
    return out


def list_suspensions(auth: Any, *, active_only: bool = True
                       ) -> list[SuspensionRow]:
    init_lifecycle_schema(auth)
    sql = "SELECT * FROM user_suspensions"
    args: list = []
    if active_only:
        sql += " WHERE status='Active'"
    sql += " ORDER BY started_at DESC"
    try:
        conn = _conn(auth)
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_suspensions failed")
        return []
    return [SuspensionRow(
        suspension_id=r["suspension_id"], user_id=r["user_id"],
        reason=r["reason"], started_at=r["started_at"],
        started_by=r["started_by"], resume_at=r["resume_at"],
        status=r["status"]) for r in rows]


# ── Offboarding (atomic) ──────────────────────────────────────────────

import secrets as _secrets


@dataclass
class OffboardResult:
    archive_id: int
    sessions_invalidated: bool
    reassignment_summary: dict


def offboard_user(auth: Any, user_id: int, *,
                   reason: str | None = None,
                   retention_days: int = DEFAULT_RETENTION_DAYS,
                   reassign_to_user_id: int | None = None,
                   ) -> OffboardResult:
    """Disable login, rotate the password (invalidates sessions per
    ``admin_reset_password``), record a *reassignment plan* for owned
    records, and archive the user. One audit row per step so the
    whole sequence is traceable.

    Cross-domain record reassignment is recorded but **not** executed
    here — every domain (housing, finance, gradebook, etc.) owns its
    own foreign-key cleanup. The summary surfaces what *would* need
    moving; an admin re-runs the per-domain re-owner tools.
    """
    init_lifecycle_schema(auth)
    user = _ua.get_user(auth, user_id)
    if user is None:
        raise UserAccountError(f"No user #{user_id}")

    # Step 1: rotate password to a random value to invalidate sessions.
    sessions_invalidated = False
    try:
        random_pw = _secrets.token_urlsafe(24) + "Aa1!"
        _ua.admin_reset_password(auth, user_id, random_pw)
        sessions_invalidated = True
    except Exception as e:
        logger.exception("Offboard: password rotate failed "
                          "(user_id=%d)", user_id)
        _audit(auth, "user_offboard_step_failed", user_id,
                {"step": "rotate_password", "error": str(e)})

    # Step 2: reassignment placeholder. Real implementation would call
    # into every domain module's "reassign owned records" helper. We
    # at least capture the user's systems for the audit trail.
    summary = {
        "from_user_id": user_id,
        "to_user_id": reassign_to_user_id,
        "systems": user.systems,
    }
    _audit(auth, "user_offboard_reassign_plan", user_id, summary)

    # Step 3: archive (deactivates + tombstone).
    try:
        arch = archive_user(auth, user_id,
                             reason=reason or "Offboarding",
                             retention_days=retention_days)
    except UserAccountError:
        # Already-archived case → re-raise after recording.
        _audit(auth, "user_offboard_failed", user_id,
                {"step": "archive"})
        raise

    _audit(auth, "user_offboard", user_id, {
        "archive_id": arch.archive_id,
        "sessions_invalidated": sessions_invalidated,
        "reassign_to_user_id": reassign_to_user_id,
    })
    logger.info("Offboarded user_id=%d (archive_id=%d, "
                "sessions_invalidated=%s)",
                user_id, arch.archive_id, sessions_invalidated)
    return OffboardResult(
        archive_id=arch.archive_id,
        sessions_invalidated=sessions_invalidated,
        reassignment_summary=summary,
    )


def is_archived(auth: Any, user_id: int) -> bool:
    init_lifecycle_schema(auth)
    try:
        conn = _conn(auth)
        try:
            r = conn.execute(
                "SELECT 1 FROM user_archives "
                "WHERE user_id=? AND status='Archived' LIMIT 1",
                (user_id,)).fetchone()
            return r is not None
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("is_archived failed for user_id=%d", user_id)
        return False
