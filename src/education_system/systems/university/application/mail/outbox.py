"""The university's one e-mail outbox.

Every message, from every part of the university, goes through
:func:`submit`. Delivery is done after commit by
``infrastructure/email/outbox_delivery``, which claims due messages with
:func:`claim_due` and reports each attempt with :func:`record_result`.

Delivery modes (read from the e-mail config, shown on the status screens):

* ``inbox_only`` – nothing leaves the system; the message is kept as
  ``stored`` and the recipient sees the in-app inbox copy only.
* ``sandbox`` – messages are written as ``.eml`` files instead of sent.
* ``live`` – messages are sent over SMTP.

Who gets what:

* An address with a hard bounce, complaint or manual block gets nothing.
* An unsubscribe (address-level, from the link in bulk mail) or a user's
  own preference blocks bulk and marketing mail in that category, never
  transactional mail (password resets, decisions, receipts…).

Retries: a temporary failure is tried again after 1, 5, 30, 120 and 720
minutes, up to ``max_attempts``; then the message is ``failed``. A
permanent failure (5xx recipient refusal) marks it ``bounced`` and
suppresses the address.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.schemas import (
    email_outbox_schema,
)

ADMIN_ROLES = ("admin", "administrator", "superadmin")
KINDS = ("transactional", "bulk", "marketing")
MODES = ("inbox_only", "sandbox", "live")
FINAL = ("sent", "bounced", "suppressed", "stored", "cancelled", "failed")
BACKOFF_MINUTES = (1, 5, 30, 120, 720)
OUTCOMES = ("sent", "temporary", "permanent", "rejected")
STALE_SENDING_MINUTES = 15
UNSUBSCRIBE_PATH = "/api/v1/university/email/unsubscribe/"

SETTINGS = {
    "max_attempts": "5",
    "retention_days": "365",
    "public_base_url": "",
    # 1: plain-text e-mail also goes out in the branded HTML design
    # (infrastructure/email/html_layout); 0: plain text only.
    "html_layout": "1",
}

_ADDRESS = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def ensure(conn) -> None:
    email_outbox_schema.apply_to_connection(conn)


def now(at=None) -> str:
    return (at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def _dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _one(conn, sql, params=()) -> dict | None:
    found = _dicts(conn.execute(sql, params))
    return found[0] if found else None


def is_admin(role) -> bool:
    return str(role or "").lower() in ADMIN_ROLES


def require(allowed, message) -> None:
    if not allowed:
        raise PermissionError(message)


def valid_address(address) -> str:
    address = str(address or "").strip()
    if "\r" in address or "\n" in address or not _ADDRESS.match(address):
        raise ValueError(f"Not a valid e-mail address: {address!r}")
    return address


def audit(conn, actor, entity, entity_id, action, detail=None) -> None:
    conn.execute("INSERT INTO email_audit (entity, entity_id, action, actor, detail, at) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (entity, None if entity_id is None else str(entity_id), action, actor,
                  json.dumps(detail, default=str) if detail else None, now()))


# ── settings ────────────────────────────────────────────────────────────


def setting(conn, key) -> str:
    ensure(conn)
    row = conn.execute("SELECT value FROM email_settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else SETTINGS[key]


def int_setting(conn, key) -> int:
    try:
        return int(setting(conn, key))
    except ValueError:
        return int(SETTINGS[key])


def set_setting(conn, actor, actor_role, key, value) -> None:
    require(is_admin(actor_role) or holds(conn, actor, "email_admin"),
            "Only an e-mail administrator can change e-mail settings")
    if key not in SETTINGS:
        raise ValueError(f"Unknown setting {key!r}")
    value = str(value).strip()
    if key in ("max_attempts", "retention_days") and (not value.isdigit() or int(value) < 1):
        raise ValueError(f"{key} must be a whole number above zero")
    if key == "public_base_url" and value and not value.startswith("https://"):
        raise ValueError("The public address must start with https://")
    if key == "html_layout" and value not in ("0", "1"):
        raise ValueError("html_layout must be 1 (branded design) or 0 (plain text)")
    conn.execute("INSERT INTO email_settings (key, value, updated_by, updated_at) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                 "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                 (key, value, actor, now()))
    audit(conn, actor, "setting", key, "changed", {"value": value})


# ── roles ───────────────────────────────────────────────────────────────


def holds(conn, username, role, user_role="") -> bool:
    if is_admin(user_role):
        return True
    ensure(conn)
    return conn.execute("SELECT 1 FROM email_roles WHERE username = ? AND role = ?",
                        (username, role)).fetchone() is not None


def grant(conn, actor, actor_role, username, role) -> None:
    require(is_admin(actor_role), "Only an administrator can grant e-mail roles")
    if role not in ("bulk_sender", "email_admin"):
        raise ValueError("Role must be bulk_sender or email_admin")
    ensure(conn)
    found = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    if not found or str(found[0]).lower() == "student":
        raise ValueError(f"No member of staff with username {username!r}")
    conn.execute("INSERT OR IGNORE INTO email_roles (username, role, granted_by, granted_at) "
                 "VALUES (?, ?, ?, ?)", (username, role, actor, now()))
    audit(conn, actor, "role", username, "granted", {"role": role})


def revoke(conn, actor, actor_role, username, role) -> None:
    require(is_admin(actor_role), "Only an administrator can revoke e-mail roles")
    ensure(conn)
    conn.execute("DELETE FROM email_roles WHERE username = ? AND role = ?", (username, role))
    audit(conn, actor, "role", username, "revoked", {"role": role})


def roles(conn) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT * FROM email_roles ORDER BY username, role"))


# ── who may be sent what ────────────────────────────────────────────────


def blocked_reason(conn, address, kind="transactional", category="general",
                   to_ref=None) -> str | None:
    """Why ``address`` must not be sent this message, or ``None``."""
    ensure(conn)
    hard = conn.execute("SELECT reason FROM email_suppressions WHERE address = ? "
                        "AND reason IN ('bounce', 'complaint', 'manual') LIMIT 1",
                        (address,)).fetchone()
    if hard:
        return f"address suppressed ({hard[0]})"
    if kind == "transactional":
        return None
    unsub = conn.execute("SELECT category FROM email_suppressions WHERE address = ? "
                         "AND reason = 'unsubscribe' AND category IN ('*', ?) LIMIT 1",
                         (address, category)).fetchone()
    if unsub:
        return "unsubscribed" + ("" if unsub[0] == "*" else f" from {category}")
    if to_ref:
        pref = conn.execute("SELECT enabled FROM email_preferences WHERE user_id = ? "
                            "AND event_kind IN (?, 'all_bulk') AND enabled = 0 LIMIT 1",
                            (str(to_ref), category)).fetchone()
        if pref:
            return "recipient opted out"
    return None


def suppress(conn, actor, address, reason, *, category="*", detail=None) -> None:
    ensure(conn)
    address = valid_address(address)
    conn.execute("INSERT INTO email_suppressions (address, category, reason, detail, added_by, "
                 "added_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(address, category) DO UPDATE "
                 "SET reason = excluded.reason, detail = excluded.detail, "
                 "added_by = excluded.added_by, added_at = excluded.added_at",
                 (address, category, reason, detail, actor, now()))
    audit(conn, actor, "suppression", address, "added", {"reason": reason, "category": category})


def add_suppression(conn, actor, actor_role, address, detail="") -> None:
    require(is_admin(actor_role) or holds(conn, actor, "email_admin"),
            "Only an e-mail administrator can block an address")
    suppress(conn, actor, address, "manual", detail=detail or None)


def remove_suppression(conn, actor, actor_role, address, category="*") -> None:
    require(is_admin(actor_role) or holds(conn, actor, "email_admin"),
            "Only an e-mail administrator can unblock an address")
    ensure(conn)
    conn.execute("DELETE FROM email_suppressions WHERE address = ? AND category = ?",
                 (address, category))
    audit(conn, actor, "suppression", address, "removed", {"category": category})


def suppressions(conn) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT * FROM email_suppressions ORDER BY added_at DESC"))


# ── preferences and unsubscribe ─────────────────────────────────────────


def preferences(conn, user_id) -> dict[str, bool]:
    ensure(conn)
    return {kind: bool(on) for kind, on in conn.execute(
        "SELECT event_kind, enabled FROM email_preferences WHERE user_id = ?", (str(user_id),))}


def set_preference(conn, user_id, category, enabled) -> None:
    ensure(conn)
    conn.execute("INSERT INTO email_preferences (user_id, event_kind, enabled, updated_at) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT(user_id, event_kind) DO UPDATE SET "
                 "enabled = excluded.enabled, updated_at = excluded.updated_at",
                 (str(user_id), str(category), 1 if enabled else 0, now()))


def unsubscribe_token(conn, address, category) -> str:
    ensure(conn)
    token = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO email_unsubscribe_tokens (token, address, category, created_at) "
                 "VALUES (?, ?, ?, ?)", (token, address, category, now()))
    return token


def unsubscribe_footer(conn, address, category) -> str:
    token = unsubscribe_token(conn, address, category)
    base = setting(conn, "public_base_url").rstrip("/")
    if base:
        how = f"unsubscribe here: {base}{UNSUBSCRIBE_PATH}{token}"
    else:
        how = (f"turn them off under E-mail preferences in the University app "
               f"(unsubscribe code {token})")
    return ("\n\n--\nYou are receiving this because you are on a university mailing list "
            f"({category}). To stop these e-mails, {how}.")


def unsubscribe(conn, token, *, everything=False) -> dict:
    """Use a token from a bulk e-mail. Returns the address and category."""
    ensure(conn)
    row = _one(conn, "SELECT * FROM email_unsubscribe_tokens WHERE token = ?", (str(token),))
    if not row:
        raise ValueError("This unsubscribe link is not valid")
    category = "*" if everything else row["category"]
    already = conn.execute("SELECT 1 FROM email_suppressions WHERE address = ? AND category = ? "
                           "AND reason = 'unsubscribe'", (row["address"], category)).fetchone()
    if not already:
        suppress(conn, "unsubscribe-link", row["address"], "unsubscribe", category=category)
    conn.execute("UPDATE email_unsubscribe_tokens SET used_at = COALESCE(used_at, ?) "
                 "WHERE token = ?", (now(), token))
    return {"address": row["address"], "category": category}


# ── submit ──────────────────────────────────────────────────────────────


def _join(value) -> str | None:
    if not value:
        return None
    return ", ".join(value) if isinstance(value, (list, tuple)) else str(value)


def submit(conn, to_address, subject, body, *, mode, kind="transactional",
           category="general", to_ref=None, cc=None, bcc=None, attachments=None,
           created_by=None, bulk_id=None, stored_email_id=None, reply_to=None) -> dict:
    """Put one message in the outbox. Returns ``{"message_id", "status"}``.
    ``reply_to`` (an address) becomes the message's Reply-To header.

    Does not commit; delivery happens after the caller commits."""
    ensure(conn)
    to_address = valid_address(to_address)
    if not str(subject or "").strip():
        raise ValueError("A subject is required")
    if "\r" in subject or "\n" in subject:
        raise ValueError("The subject cannot contain line breaks")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}")
    body = "" if body is None else str(body)
    reply_to = valid_address(reply_to) if reply_to else None
    reason = blocked_reason(conn, to_address, kind, category, to_ref)
    if reason:
        status = "suppressed"
    elif mode == "inbox_only":
        status = "stored"
    else:
        status = "queued"
    if kind != "transactional" and status != "suppressed":
        body += unsubscribe_footer(conn, to_address, category)
    stamp = now()
    cur = conn.execute(
        "INSERT INTO email_outbox (to_address, to_ref, subject, body, cc, bcc, reply_to, "
        "attachments, kind, category, status, mode, next_attempt_at, last_error, bulk_id, "
        "stored_email_id, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (to_address, None if to_ref is None else str(to_ref), subject, body, _join(cc),
         _join(bcc), reply_to, _join(attachments), kind, category, status, mode,
         stamp if status == "queued" else None, reason, bulk_id, stored_email_id, created_by,
         stamp, stamp))
    return {"message_id": cur.lastrowid, "status": status, "reason": reason}


# ── delivery bookkeeping ────────────────────────────────────────────────


def claim_due(conn, limit=20, at=None) -> list[dict]:
    """Mark up to ``limit`` due messages as ``sending`` and return them.
    Messages stuck in ``sending`` (a crashed worker) become due again."""
    ensure(conn)
    stamp = now(at)
    stale = now((at or datetime.now()) - timedelta(minutes=STALE_SENDING_MINUTES))
    conn.execute("UPDATE email_outbox SET status = 'queued' WHERE status = 'sending' "
                 "AND updated_at < ?", (stale,))
    due = _dicts(conn.execute(
        "SELECT * FROM email_outbox WHERE status = 'queued' AND "
        "(next_attempt_at IS NULL OR next_attempt_at <= ?) ORDER BY message_id LIMIT ?",
        (stamp, int(limit))))
    for row in due:
        conn.execute("UPDATE email_outbox SET status = 'sending', updated_at = ? "
                     "WHERE message_id = ? AND status = 'queued'", (stamp, row["message_id"]))
    return due


def _retry_at(attempts, at=None) -> str:
    minutes = BACKOFF_MINUTES[min(attempts, len(BACKOFF_MINUTES)) - 1]
    return now((at or datetime.now()) + timedelta(minutes=minutes))


def record_result(conn, message_id, mode, outcome, detail=None, at=None) -> str:
    """Record one delivery attempt; returns the message's new status.

    ``outcome`` is ``sent``, ``temporary`` (try again later),
    ``permanent`` (the recipient's server refused the address) or
    ``rejected`` (the message itself cannot be sent, e.g. a missing
    attachment; the address is not blamed)."""
    ensure(conn)
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {', '.join(OUTCOMES)}")
    msg = _one(conn, "SELECT * FROM email_outbox WHERE message_id = ?", (message_id,))
    if not msg:
        raise ValueError(f"No message {message_id}")
    stamp = now(at)
    attempts = int(msg["attempts"] or 0) + 1
    conn.execute("INSERT INTO email_attempts (message_id, mode, outcome, detail, at) "
                 "VALUES (?, ?, ?, ?, ?)", (message_id, mode, outcome, detail, stamp))
    if outcome == "sent":
        status, next_at, error, sent_at = "sent", None, None, stamp
    elif outcome == "permanent":
        status, next_at, error, sent_at = "bounced", None, detail, None
        suppress(conn, "delivery", msg["to_address"], "bounce", detail=detail)
    elif outcome == "rejected" or attempts >= int_setting(conn, "max_attempts"):
        status, next_at, error, sent_at = "failed", None, detail, None
    else:
        status, next_at, error, sent_at = "queued", _retry_at(attempts, at), detail, None
    conn.execute("UPDATE email_outbox SET status = ?, attempts = ?, next_attempt_at = ?, "
                 "last_error = ?, sent_at = COALESCE(?, sent_at), mode = ?, updated_at = ? "
                 "WHERE message_id = ?",
                 (status, attempts, next_at, error, sent_at, mode, stamp, message_id))
    return status


def record_bounce(conn, actor, actor_role, message_id, detail, *, hard=True) -> None:
    """A bounce reported after the message left (a returned e-mail)."""
    require(is_admin(actor_role) or holds(conn, actor, "email_admin"),
            "Only an e-mail administrator can record a bounce")
    msg = _one(conn, "SELECT * FROM email_outbox WHERE message_id = ?", (message_id,))
    if not msg:
        raise ValueError(f"No message {message_id}")
    conn.execute("UPDATE email_outbox SET status = 'bounced', last_error = ?, updated_at = ? "
                 "WHERE message_id = ?", (detail, now(), message_id))
    if hard:
        suppress(conn, actor, msg["to_address"], "bounce", detail=detail)
    audit(conn, actor, "message", message_id, "bounce recorded", {"hard": hard})


def retry(conn, actor, actor_role, message_id) -> None:
    require(is_admin(actor_role) or holds(conn, actor, "email_admin"),
            "Only an e-mail administrator can retry a message")
    msg = _one(conn, "SELECT status, to_address FROM email_outbox WHERE message_id = ?",
               (message_id,))
    if not msg:
        raise ValueError(f"No message {message_id}")
    if msg["status"] not in ("failed", "bounced", "cancelled"):
        raise ValueError(f"A {msg['status']} message cannot be retried")
    if blocked_reason(conn, msg["to_address"]):
        raise ValueError("The address is suppressed; unblock it first")
    conn.execute("UPDATE email_outbox SET status = 'queued', attempts = 0, next_attempt_at = ?, "
                 "updated_at = ? WHERE message_id = ?", (now(), now(), message_id))
    audit(conn, actor, "message", message_id, "retried")


def cancel(conn, actor, actor_role, message_id) -> None:
    require(is_admin(actor_role) or holds(conn, actor, "email_admin"),
            "Only an e-mail administrator can cancel a message")
    cur = conn.execute("UPDATE email_outbox SET status = 'cancelled', updated_at = ? "
                       "WHERE message_id = ? AND status = 'queued'", (now(), message_id))
    if not cur.rowcount:
        raise ValueError("Only a queued message can be cancelled")
    audit(conn, actor, "message", message_id, "cancelled")


# ── reading ─────────────────────────────────────────────────────────────


def messages(conn, *, status=None, search=None, bulk_id=None, limit=200) -> list[dict]:
    ensure(conn)
    sql = ("SELECT message_id, to_address, to_ref, subject, kind, category, status, mode, "
           "attempts, next_attempt_at, last_error, bulk_id, created_by, created_at, sent_at "
           "FROM email_outbox WHERE 1 = 1")
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if bulk_id:
        sql += " AND bulk_id = ?"
        params.append(bulk_id)
    if search:
        sql += " AND (to_address LIKE ? OR subject LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY message_id DESC LIMIT ?"
    params.append(int(limit))
    return _dicts(conn.execute(sql, params))


def message(conn, message_id) -> dict | None:
    ensure(conn)
    msg = _one(conn, "SELECT * FROM email_outbox WHERE message_id = ?", (message_id,))
    if msg:
        msg["attempt_log"] = _dicts(conn.execute(
            "SELECT * FROM email_attempts WHERE message_id = ? ORDER BY attempt_id",
            (message_id,)))
    return msg


def status_counts(conn) -> dict[str, int]:
    ensure(conn)
    return {s: n for s, n in conn.execute(
        "SELECT status, COUNT(*) FROM email_outbox GROUP BY status")}


def recent_audit(conn, limit=200) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT * FROM email_audit ORDER BY audit_id DESC LIMIT ?",
                               (int(limit),)))
