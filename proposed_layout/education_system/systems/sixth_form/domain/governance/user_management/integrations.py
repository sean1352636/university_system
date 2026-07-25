"""External-system integrations + saved filters + admin notes
(#44-50).

* 44. SSO mapping — bind user → external IdP subject
* 45. HRIS sync — import staff from a CSV / list, reconcile delta
* 46. MIS sync — same shape, students-from-MIS
* 47. Webhook outbox on user events
* 48. Quick search bar (used by the GUI; we just expose a search helper)
* 49. Saved filters (named queries for the users list)
* 50. Annotated user notes (timestamped admin notes)
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from education_system.systems.sixth_form.domain.governance.user_management import (
    lifecycle,
)
from education_system.systems.sixth_form.interfaces import user_accounts as _ua
from education_system.systems.sixth_form.interfaces.user_accounts import (
    UserAccountError,
)

logger = logging.getLogger(__name__)


# ── Schema ────────────────────────────────────────────────────────────

def _init(auth: Any) -> None:
    try:
        conn = lifecycle._conn(auth)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_external_identities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    provider TEXT NOT NULL,          -- 'microsoft' | 'google' | …
                    external_subject TEXT NOT NULL,
                    email TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(provider, external_subject)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_webhook_endpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    secret TEXT,
                    events TEXT NOT NULL,           -- comma-separated
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    created_by TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_webhook_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint_id INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    enqueued_at TEXT NOT NULL,
                    delivered_at TEXT,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_saved_filters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL,        -- JSON of filter state
                    created_at TEXT NOT NULL,
                    UNIQUE(owner, name)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    author TEXT,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    visible_to_user INTEGER NOT NULL DEFAULT 0
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_notes_user
                ON user_notes(user_id, created_at)
            ''')
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("integrations schema init failed")
        raise


# ── 44. SSO mapping ───────────────────────────────────────────────────

def add_sso_mapping(auth: Any, *, user_id: int, provider: str,
                     external_subject: str,
                     email: str | None = None) -> int:
    _init(auth)
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    if not provider or not external_subject:
        raise UserAccountError("provider and external_subject required.")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO user_external_identities
                (user_id, provider, external_subject, email, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, provider.lower(), external_subject,
                  (email or '').strip() or None, now))
            mid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.IntegrityError as e:
        raise UserAccountError(
            "That (provider, external_subject) is already mapped."
        ) from e
    except sqlite3.Error as e:
        logger.exception("add_sso_mapping failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "sso_map_add", user_id,
                      {"provider": provider,
                       "external_subject": external_subject})
    return mid


def remove_sso_mapping(auth: Any, mapping_id: int) -> bool:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            r = conn.execute(
                "SELECT user_id, provider FROM user_external_identities "
                "WHERE id = ?", (mapping_id,)).fetchone()
            if r is None:
                return False
            conn.execute(
                "DELETE FROM user_external_identities WHERE id = ?",
                (mapping_id,))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("remove_sso_mapping failed")
        return False
    lifecycle._audit(auth, "sso_map_remove", r["user_id"],
                      {"mapping_id": mapping_id,
                       "provider": r["provider"]})
    return True


def list_sso_mappings(auth: Any, *,
                        user_id: int | None = None) -> list[dict]:
    _init(auth)
    sql = "SELECT * FROM user_external_identities"
    args: list = []
    if user_id is not None:
        sql += " WHERE user_id = ?"
        args.append(user_id)
    sql += " ORDER BY provider, user_id"
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_sso_mappings failed")
        return []


# ── 45/46. HRIS / MIS reconciliation ──────────────────────────────────

@dataclass
class SyncRow:
    external_id: str
    username: str | None
    display_name: str | None
    email: str | None
    department: str | None
    job_title: str | None


@dataclass
class SyncReport:
    new: list[SyncRow]
    matched: list[tuple[SyncRow, int]]      # (row, internal user_id)
    missing_locally: list[SyncRow]
    missing_externally: list[str]           # usernames not in feed


def _read_feed(path: str) -> list[SyncRow]:
    p = Path(path)
    if not p.is_file():
        raise UserAccountError(f"Feed not found: {path}")
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise UserAccountError("Feed has no header row.")
        reader.fieldnames = [h.strip().lower().replace(" ", "_")
                             for h in reader.fieldnames]
        out: list[SyncRow] = []
        for r in reader:
            out.append(SyncRow(
                external_id=(r.get("external_id") or "").strip(),
                username=(r.get("username") or "").strip() or None,
                display_name=(r.get("display_name") or "").strip()
                or None,
                email=(r.get("email") or "").strip() or None,
                department=(r.get("department") or "").strip() or None,
                job_title=(r.get("job_title") or "").strip() or None,
            ))
    return out


def reconcile_sync(auth: Any, path: str, *,
                    role_for_new: str | None = None
                    ) -> SyncReport:
    """Read an HRIS/MIS feed and compare against the local users
    table. ``role_for_new`` is informational — this function does
    NOT auto-create users; the caller picks which `new` rows to
    apply via ``apply_sync_create``."""
    feed = _read_feed(path)
    by_username = {u.username: u for u in _ua.list_users(auth)}

    new: list[SyncRow] = []
    matched: list[tuple[SyncRow, int]] = []
    missing_locally: list[SyncRow] = []
    seen_usernames: set[str] = set()
    for row in feed:
        uname = row.username
        if not uname:
            continue
        seen_usernames.add(uname)
        if uname in by_username:
            matched.append((row, by_username[uname].id))
        else:
            new.append(row)
            missing_locally.append(row)
    missing_externally = sorted(set(by_username) - seen_usernames)
    return SyncReport(new=new, matched=matched,
                       missing_locally=missing_locally,
                       missing_externally=missing_externally)


def apply_sync_create(auth: Any, rows: Iterable[SyncRow], *,
                       role: str, system_key: str) -> list[int]:
    """Create users for selected feed rows. Idempotent — re-runs skip
    usernames that now exist locally."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        lifecycle as lc,
    )
    import secrets
    by_username = {u.username for u in _ua.list_users(auth)}
    created: list[int] = []
    for r in rows:
        if not r.username or r.username in by_username:
            continue
        try:
            user = lc.create_user_full(
                auth, username=r.username,
                password=secrets.token_urlsafe(18),
                display_name=r.display_name, email=r.email,
                role=role, system_key=system_key,
                department=r.department, job_title=r.job_title)
            created.append(user.id)
        except Exception:
            logger.exception("apply_sync_create row failed for %r",
                              r.username)
    lifecycle._audit(auth, "sync_apply_create", None,
                      {"created": len(created)})
    return created


# ── 47. Webhook outbox ────────────────────────────────────────────────

def add_webhook(auth: Any, *, url: str,
                 events: list[str],
                 secret: str | None = None) -> int:
    _init(auth)
    if not url:
        raise UserAccountError("url is required.")
    if not events:
        raise UserAccountError("events list is required.")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    actor = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO user_webhook_endpoints
                (url, secret, events, is_active, created_at, created_by)
                VALUES (?, ?, ?, 1, ?, ?)
            ''', (url, secret, ",".join(events), now, actor))
            eid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("add_webhook failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "webhook_add", None,
                      {"endpoint_id": eid, "url": url,
                       "events": events})
    return eid


def remove_webhook(auth: Any, endpoint_id: int) -> bool:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute(
                "UPDATE user_webhook_endpoints SET is_active=0 "
                "WHERE id = ?", (endpoint_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("remove_webhook failed")
        return False


def list_webhooks(auth: Any) -> list[dict]:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM user_webhook_endpoints "
                "WHERE is_active = 1 ORDER BY id").fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_webhooks failed")
        return []


def enqueue_event(auth: Any, event: str, payload: dict) -> int:
    """Drop a row in the outbox for every endpoint subscribed to
    ``event``. A delivery worker would later POST and flip the row to
    ``Delivered`` — we keep the outbox so missed deliveries are visible."""
    _init(auth)
    body = json.dumps(payload, default=str)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    queued = 0
    try:
        conn = lifecycle._conn(auth)
        try:
            for ep in conn.execute(
                    "SELECT id, events FROM user_webhook_endpoints "
                    "WHERE is_active = 1").fetchall():
                events = [e.strip() for e in (ep["events"] or "").split(",")]
                if event not in events and "*" not in events:
                    continue
                conn.execute('''
                    INSERT INTO user_webhook_outbox
                    (endpoint_id, event, payload, enqueued_at)
                    VALUES (?, ?, ?, ?)
                ''', (ep["id"], event, body, now))
                queued += 1
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("enqueue_event failed")
    return queued


def list_outbox(auth: Any, *, status: str | None = None,
                  limit: int = 200) -> list[dict]:
    _init(auth)
    sql = "SELECT * FROM user_webhook_outbox"
    args: list = []
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY enqueued_at DESC LIMIT ?"
    args.append(int(limit))
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_outbox failed")
        return []


# ── 48. Quick search ──────────────────────────────────────────────────

def quick_search(auth: Any, query: str, *,
                   limit: int = 50) -> list[dict]:
    """Cross-field user search by username / display_name / email
    fragment. Returns a flat list of dicts with the join fields the GUI
    needs."""
    q = (query or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute('''
                SELECT id, username, display_name, email, is_active
                FROM users
                WHERE username LIKE ? OR display_name LIKE ?
                   OR email LIKE ?
                ORDER BY username LIMIT ?
            ''', (like, like, like, int(limit))).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("quick_search failed")
        return []
    return [dict(r) for r in rows]


# ── 49. Saved filters ─────────────────────────────────────────────────

def save_filter(auth: Any, *, name: str, payload: dict) -> int:
    _init(auth)
    if not name:
        raise UserAccountError("name is required.")
    owner = lifecycle._actor_name(auth)
    now = datetime.datetime.now().isoformat(timespec='seconds')
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO user_saved_filters
                (owner, name, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(owner, name) DO UPDATE SET
                    payload=excluded.payload,
                    created_at=excluded.created_at
            ''', (owner, name, json.dumps(payload, default=str), now))
            conn.commit()
            fid = cur.lastrowid
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("save_filter failed")
        raise UserAccountError(f"DB error: {e}") from e
    return fid or 0


def delete_filter(auth: Any, *, name: str) -> bool:
    _init(auth)
    owner = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute(
                "DELETE FROM user_saved_filters "
                "WHERE owner = ? AND name = ?", (owner, name))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("delete_filter failed")
        return False


def list_filters(auth: Any) -> list[dict]:
    _init(auth)
    owner = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            rows = conn.execute(
                "SELECT * FROM user_saved_filters WHERE owner = ? "
                "ORDER BY name", (owner,)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_filters failed")
        return []
    out: list[dict] = []
    for r in rows:
        try:
            payload = json.loads(r["payload"])
        except Exception:
            payload = {}
        out.append({"id": r["id"], "name": r["name"],
                     "created_at": r["created_at"],
                     "payload": payload})
    return out


# ── 50. Admin notes ───────────────────────────────────────────────────

def add_note(auth: Any, *, user_id: int, body: str,
              visible_to_user: bool = False) -> int:
    _init(auth)
    if _ua.get_user(auth, user_id) is None:
        raise UserAccountError(f"No user #{user_id}")
    body = (body or "").strip()
    if not body:
        raise UserAccountError("body is required.")
    now = datetime.datetime.now().isoformat(timespec='seconds')
    author = lifecycle._actor_name(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            cur = conn.execute('''
                INSERT INTO user_notes
                (user_id, author, body, created_at, visible_to_user)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, author, body, now,
                  1 if visible_to_user else 0))
            nid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.exception("add_note failed")
        raise UserAccountError(f"DB error: {e}") from e
    lifecycle._audit(auth, "user_note_add", user_id,
                      {"note_id": nid,
                       "visible_to_user": visible_to_user})
    return nid


def delete_note(auth: Any, note_id: int) -> bool:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            r = conn.execute(
                "SELECT user_id FROM user_notes WHERE id = ?",
                (note_id,)).fetchone()
            if r is None:
                return False
            conn.execute("DELETE FROM user_notes WHERE id = ?",
                         (note_id,))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("delete_note failed")
        return False
    lifecycle._audit(auth, "user_note_delete", r["user_id"],
                      {"note_id": note_id})
    return True


def list_notes(auth: Any, user_id: int) -> list[dict]:
    _init(auth)
    try:
        conn = lifecycle._conn(auth)
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM user_notes WHERE user_id = ? "
                "ORDER BY created_at DESC", (user_id,)).fetchall()]
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("list_notes failed")
        return []
