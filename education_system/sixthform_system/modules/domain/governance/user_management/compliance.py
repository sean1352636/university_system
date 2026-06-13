"""Compliance / legal helpers (#39-43).

* 39. GDPR consent ledger per user
* 40. Subject Access Request (SAR) bundler
* 41. Retention-policy executor (sweeps user_archives past retention)
* 42. Safeguarding flag with restricted-view side-table
* 43. Right-to-erasure workflow (DPO sign-off → purge_user)
"""

from __future__ import annotations

import datetime
import io
import json
import logging
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

from education_system.sixthform_system.modules.domain.governance.user_management import (
    lifecycle,
)
from education_system.sixthform_system.modules.shared import user_accounts as _ua
from education_system.sixthform_system.modules.shared.user_accounts import (
    UserAccountError,
)

logger = logging.getLogger(__name__)


def _init(auth: Any) -> None:
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_safeguarding_flags (
                    user_id INTEGER PRIMARY KEY,
                    reason TEXT,
                    set_by TEXT, set_at TEXT NOT NULL,
                    cleared_by TEXT, cleared_at TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_erasure_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_user_id INTEGER NOT NULL,
                    reason TEXT,
                    requested_by TEXT, requested_at TEXT NOT NULL,
                    dpo_approved_by TEXT, dpo_approved_at TEXT,
                    executed_at TEXT,
                    status TEXT NOT NULL DEFAULT 'Pending'
                )
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("compliance schema init failed")
        raise


# ── 39. GDPR consent ledger ───────────────────────────────────────────

def list_consents(auth: Any, user_id: int) -> list[dict]:
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM consent_records WHERE user_id = ? "
                "ORDER BY updated_at DESC", (user_id,)).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_consents failed")
        return []


def record_consent(auth: Any, *, user_id: int, consent_type: str,
                    granted: bool, source: str = "manual",
                    version: str | None = None) -> int:
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO consent_records
                (user_id, consent_type, granted, granted_at,
                 withdrawn_at, source, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, consent_type, 1 if granted else 0,
                  now if granted else None,
                  None if granted else now,
                  source, version or '1.0', now, now))
            rid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("record_consent failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "consent_record", user_id,
                      {"consent_type": consent_type,
                       "granted": granted, "source": source})
    return rid


# ── 40. SAR bundler ───────────────────────────────────────────────────

# Tables on the auth side (and our side-tables) that may carry user
# data. Each entry: (table, fk_column, optional description).
SAR_TABLES = (
    ("users",                       "id",           "Core profile"),
    ("user_systems",                "user_id",      "System access"),
    ("user_profile_extras",         "user_id",      "Extended profile"),
    ("user_archives",               "user_id",      "Archives"),
    ("user_suspensions",            "user_id",      "Suspensions"),
    ("user_name_history",           "user_id",      "Renames"),
    ("user_lock_history",           "user_id",      "Locks"),
    ("user_pending_setups",         "user_id",      "Pending setup tokens"),
    ("user_audit_log",              "target_user_id", "Audit log"),
    ("user_permission_overrides",   "user_id",      "Permission overrides"),
    ("jit_access_requests",         "user_id",      "JIT requests"),
    ("consent_records",             "user_id",      "GDPR consents"),
    ("password_history",            "user_id",      "Password history (hashes)"),
    ("password_reset_tokens",       "user_id",      "Password resets"),
    ("trusted_devices",             "user_id",      "Trusted devices"),
    ("security_questions",          "user_id",      "Security questions"),
    ("security_audit_log",          "user_id",      "Security audit"),
    ("email_verification_tokens",   "user_id",      "Email verifications"),
    ("oauth_accounts",              "user_id",      "OAuth identities"),
    ("webauthn_credentials",        "user_id",      "WebAuthn credentials"),
    ("user_notes",                  "user_id",      "Admin notes"),
    ("user_safeguarding_flags",     "user_id",      "Safeguarding flag"),
)


def collect_sar(auth: Any, user_id: int) -> dict[str, list[dict]]:
    """Walk every known table that might hold rows for this user and
    collect their contents. Missing tables are skipped silently."""
    out: dict[str, list[dict]] = {}
    try:
        conn = lifecycle._conn(auth)
        try:
            for table, col, _desc in SAR_TABLES:
                try:
                    rows = conn.execute(
                        f"SELECT * FROM {table} WHERE {col} = ?",
                        (user_id,)).fetchall()
                    out[table] = [dict(r) for r in rows]
                except sqlite3.Error:
                    logger.debug("SAR: skipped %s (not present?)",
                                  table, exc_info=True)
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("collect_sar failed")
    return out


def bundle_sar(auth: Any, user_id: int, *,
                output_path: str | None = None) -> str:
    """Write a ZIP containing per-table JSON files. Returns the path."""
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    data = collect_sar(auth, user_id)
    if output_path is None:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = (f"/tmp/sar-user-{user_id}-{ts}.zip"
                        if Path("/tmp").is_dir()
                        else f"sar-user-{user_id}-{ts}.zip")
    try:
        with zipfile.ZipFile(output_path, "w",
                              compression=zipfile.ZIP_DEFLATED) as zf:
            for table, rows in data.items():
                zf.writestr(
                    f"{table}.json",
                    json.dumps(rows, indent=2, default=str))
            zf.writestr("README.txt",
                          (f"Subject Access Request bundle for user "
                           f"#{user_id}.\n"
                           f"Generated: "
                           f"{datetime.datetime.now().isoformat()}\n"))
    except OSError as e:
        logger.exception("bundle_sar zip write failed")
        raise UserAccountError(f"Could not write SAR: {e}") from e
    lifecycle._audit(auth, "sar_export", user_id,
                      {"output_path": output_path,
                       "tables": list(data.keys())})
    logger.info("SAR bundled for user_id=%d -> %s",
                user_id, output_path)
    return output_path


# ── 41. Retention-policy executor ────────────────────────────────────

def execute_retention_policy(auth: Any, *,
                               purge_expired: bool = False) -> dict:
    """Sweep ``user_archives`` rows whose ``retention_until`` is in
    the past. By default just reports them; with ``purge_expired=True``
    runs ``lifecycle.purge_user`` to actually delete.

    Returns ``{candidates: [...], purged: [...], errors: [...]}``.
    """
    lifecycle.init_lifecycle_schema(auth)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    cands: list[dict] = []
    purged: list[int] = []
    errors: list[tuple[int, str]] = []
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute('''
                SELECT archive_id, user_id, retention_until
                FROM user_archives
                WHERE status = 'Archived' AND retention_until < ?
            ''', (now,)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("execute_retention_policy fetch failed")
        return {"candidates": [], "purged": [], "errors": []}
    for r in rows:
        cands.append({"archive_id": r["archive_id"],
                       "user_id": r["user_id"],
                       "retention_until": r["retention_until"]})
        if not purge_expired:
            continue
        try:
            user = _ua.get_user(auth, r["user_id"])
            if user is None:
                continue
            ok = lifecycle.purge_user(
                auth, r["user_id"],
                reason=("Retention expired: "
                         f"{r['retention_until']}"),
                confirmation_token=user.username)
            if ok:
                purged.append(r["user_id"])
        except UserAccountError as e:
            errors.append((r["user_id"], str(e)))
        except Exception as e:
            logger.exception("retention purge failed for "
                              "user_id=%d", r["user_id"])
            errors.append((r["user_id"], str(e)))
    lifecycle._audit(auth, "retention_sweep", None,
                      {"candidates": len(cands),
                       "purged": len(purged),
                       "errors": len(errors),
                       "execute": purge_expired})
    return {"candidates": cands, "purged": purged, "errors": errors}


# ── 42. Safeguarding flag ─────────────────────────────────────────────

def set_safeguarding(auth: Any, user_id: int, *,
                      reason: str | None = None) -> None:
    _init(auth)
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                INSERT INTO user_safeguarding_flags
                (user_id, reason, set_by, set_at, cleared_by, cleared_at)
                VALUES (?, ?, ?, ?, NULL, NULL)
                ON CONFLICT(user_id) DO UPDATE SET
                    reason=excluded.reason,
                    set_by=excluded.set_by, set_at=excluded.set_at,
                    cleared_by=NULL, cleared_at=NULL
            ''', (user_id, (reason or '').strip() or None, actor, now))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("set_safeguarding failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "safeguarding_set", user_id,
                      {"reason": reason})


def clear_safeguarding(auth: Any, user_id: int) -> bool:
    _init(auth)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute(
                "UPDATE user_safeguarding_flags "
                "SET cleared_by=?, cleared_at=? WHERE user_id=? "
                "AND cleared_at IS NULL", (actor, now, user_id))
            conn.commit()
            ok = cur.rowcount > 0
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("clear_safeguarding failed")
        return False
    if ok:
        lifecycle._audit(auth, "safeguarding_clear", user_id, None)
    return ok


def is_safeguarded(auth: Any, user_id: int) -> bool:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            r = conn.execute(
                "SELECT 1 FROM user_safeguarding_flags "
                "WHERE user_id = ? AND cleared_at IS NULL LIMIT 1",
                (user_id,)).fetchone()
            return r is not None
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("is_safeguarded failed")
        return False


def list_safeguarded(auth: Any) -> list[dict]:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM user_safeguarding_flags "
                "WHERE cleared_at IS NULL ORDER BY set_at DESC"
            ).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_safeguarded failed")
        return []


# ── 43. Right-to-erasure ──────────────────────────────────────────────

def open_erasure_request(auth: Any, *, target_user_id: int,
                          reason: str | None = None) -> int:
    _init(auth)
    if _ua.get_user(auth, target_user_id) is None:
        raise UserAccountError(f"No user #{target_user_id}")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO user_erasure_requests
                (target_user_id, reason, requested_by, requested_at,
                 status) VALUES (?, ?, ?, ?, 'Pending')
            ''', (target_user_id, reason, actor, now))
            rid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("open_erasure_request failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "erasure_request", target_user_id,
                      {"request_id": rid, "reason": reason})
    return rid


def execute_erasure(auth: Any, request_id: int) -> bool:
    """DPO step: approve + run a confirmed purge. The request must
    be Pending; the actor running this call is recorded as the DPO."""
    _init(auth)
    actor = lifecycle._actor_name(auth)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        conn = lifecycle._conn(auth)
        try:
            r = conn.execute(
                "SELECT * FROM user_erasure_requests "
                "WHERE request_id = ?", (request_id,)).fetchone()
            if r is None:
                raise UserAccountError(f"No request #{request_id}")
            if r["status"] != "Pending":
                raise UserAccountError(
                    f"Request is {r['status']!r}.")
            if r["requested_by"] == actor:
                raise UserAccountError(
                    "Two-person rule: a different admin (DPO) must "
                    "execute the erasure.")
            target = r["target_user_id"]
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("execute_erasure fetch failed")
        raise UserAccountError(f"DB error: {e}") from e
    user = _ua.get_user(auth, target)
    if user is None:
        raise UserAccountError(f"Target user #{target} no longer exists.")
    ok = lifecycle.purge_user(auth, target,
                                reason="Right-to-erasure",
                                confirmation_token=user.username)
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                UPDATE user_erasure_requests
                SET dpo_approved_by=?, dpo_approved_at=?,
                    executed_at=?, status='Executed'
                WHERE request_id=?
            ''', (actor, now, now, request_id))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("execute_erasure mark failed")
    lifecycle._audit(auth, "erasure_executed", target,
                      {"request_id": request_id})
    return ok


def list_erasure_requests(auth: Any) -> list[dict]:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM user_erasure_requests "
                "ORDER BY requested_at DESC").fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_erasure_requests failed")
        return []
