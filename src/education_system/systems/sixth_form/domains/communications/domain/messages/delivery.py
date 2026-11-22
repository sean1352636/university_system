"""Message delivery — the outbox behind the messages log.

The messages log records what the college says to whom. This module is
what actually tries to get it there:

* **Email** goes through the platform e-mail integration and obeys the
  platform delivery mode (``inbox_only`` / ``sandbox`` / ``live``, set in
  the shared e-mail config — see
  :mod:`education_system.platform.integrations.email.delivery_mode`).
  Nothing leaves the building unless that mode is ``live``; in
  ``sandbox`` an .eml file is written; in ``inbox_only`` the delivery is
  *held* so it can be released later.
* **SMS** goes through an SMS channel with a provider setting. With no
  provider configured the delivery stays
  ``"Queued (no SMS provider configured)"`` — an honest status, never
  "Sent".

One ``message_deliveries`` row per attempt-able delivery (one per
message). Failures are retried with back-off up to ``max_attempts``; the
row keeps the attempt count, last error and next retry time so the
messaging window can show exactly what happened.

The message's own ``status`` follows the delivery: ``Sent`` only when a
provider accepted it, ``Failed`` once retries are exhausted, ``Queued``
for everything still waiting (held, sandboxed, no provider, retrying).
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass
from typing import Any, Callable

from education_system import paths

logger = logging.getLogger(__name__)

# ── Vocabularies ────────────────────────────────────────────────────

#: Channels this outbox actually delivers. Letters, calls and meetings
#: are things a person does; the log records them as before.
DELIVERED_CHANNELS: tuple[str, ...] = ("Email", "SMS")

QUEUED = "Queued"
RETRYING = "Retrying"
SENT = "Sent"
FAILED = "Failed"
HELD = "Held"
SANDBOX = "Sandbox"
NO_SMS_PROVIDER = "Queued (no SMS provider configured)"
CANCELLED = "Cancelled"

STATES: tuple[str, ...] = (QUEUED, RETRYING, SENT, FAILED, HELD, SANDBOX,
                           NO_SMS_PROVIDER, CANCELLED)
#: States the outbox processor picks up.
DUE_STATES: tuple[str, ...] = (QUEUED, RETRYING)
#: States still waiting for something outside this module (mode change,
#: a provider being configured) — "Release held" re-queues them.
WAITING_STATES: tuple[str, ...] = (HELD, SANDBOX, NO_SMS_PROVIDER)

DEFAULT_MAX_ATTEMPTS = 3
#: First retry after this many minutes; doubles each time.
RETRY_BASE_MINUTES = 5

SMS_PROVIDERS: tuple[str, ...] = ("", "twilio")
SMS_MAX_LEN = 459   # three concatenated SMS segments

_PHONE_RE = re.compile(r"^\+?\d{7,15}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS message_deliveries (
    delivery_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      INTEGER NOT NULL,
    channel         TEXT NOT NULL,
    recipient       TEXT,
    provider        TEXT,
    state           TEXT NOT NULL DEFAULT 'Queued',
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 3,
    last_error      TEXT,
    detail          TEXT,
    next_attempt_at TEXT,
    last_attempt_at TEXT,
    sent_at         TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (message_id) REFERENCES messages(message_id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_msgdel_message
    ON message_deliveries(message_id);
CREATE INDEX IF NOT EXISTS idx_msgdel_state
    ON message_deliveries(state);

CREATE TABLE IF NOT EXISTS messaging_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


@dataclass
class Delivery:
    delivery_id: int
    message_id: int
    channel: str
    recipient: str | None
    provider: str | None
    state: str
    attempts: int
    max_attempts: int
    last_error: str | None
    detail: str | None
    next_attempt_at: str | None
    last_attempt_at: str | None
    sent_at: str | None
    created_at: str
    updated_at: str

    @property
    def is_final(self) -> bool:
        return self.state in (SENT, FAILED, CANCELLED)

    @property
    def can_retry(self) -> bool:
        return self.state in (FAILED, RETRYING, QUEUED) + WAITING_STATES


@dataclass
class ProcessResult:
    attempted: int = 0
    sent: int = 0
    failed: int = 0
    waiting: int = 0
    errors: list[str] | None = None


class DeliveryError(RuntimeError):
    """A delivery attempt failed (the message is retried)."""


# ── DB plumbing ─────────────────────────────────────────────────────

def _db_path():
    # Follow the messages module so a redirected messages DB (tests)
    # carries the outbox with it.
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _messages,
    )
    return _messages.DB_PATH


def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(_db_path()))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_READY_FOR: str | None = None


def init_db() -> None:
    global _READY_FOR
    key = str(_db_path())
    if _READY_FOR == key:
        return
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _messages,
    )
    _messages.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY_FOR = key


def _row(r: _sql.Row) -> Delivery:
    return Delivery(**{k: r[k] for k in r.keys()})


def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Settings ────────────────────────────────────────────────────────

def get_setting(key: str, default: str | None = None) -> str | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT value FROM messaging_settings WHERE key = ?",
                         (key,)).fetchone()
    return r["value"] if r and r["value"] is not None else default


def set_setting(key: str, value: str | None) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO messaging_settings (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                   updated_at = datetime('now')""", (key, value))
        conn.commit()


def sms_provider() -> str:
    """The configured SMS provider name, ``""`` when none."""
    name = (get_setting("sms_provider", "") or "").strip().lower()
    return name if name in SMS_PROVIDERS else ""


def set_sms_provider(name: str | None) -> str:
    name = (name or "").strip().lower()
    if name not in SMS_PROVIDERS:
        from education_system.systems.sixth_form.domains.communications.domain.messages.messages import (
            ValidationError,
        )
        raise ValidationError(
            "SMS provider must be one of: none, "
            + ", ".join(p for p in SMS_PROVIDERS if p))
    set_setting("sms_provider", name)
    logger.info("SMS provider set to %s", name or "none")
    return name


def max_attempts() -> int:
    try:
        n = int(get_setting("max_attempts", str(DEFAULT_MAX_ATTEMPTS)) or 0)
    except ValueError:
        n = DEFAULT_MAX_ATTEMPTS
    return max(1, min(n, 10))


def email_mode() -> str:
    """The platform e-mail delivery mode (read, never changed here)."""
    from education_system.platform.integrations.email.delivery_mode import (
        delivery_mode,
    )
    return delivery_mode()


@dataclass
class ChannelStatus:
    email_mode: str
    email_configured: bool
    sms_provider: str
    sms_configured: bool

    def lines(self) -> list[str]:
        sms = self.sms_provider or "none"
        return [
            f"E-mail delivery mode: {self.email_mode}"
            + ("" if self.email_mode != "live" else
               (" (SMTP configured)" if self.email_configured
                else " (SMTP NOT configured)")),
            f"SMS provider: {sms}"
            + ("" if not self.sms_provider else
               (" (credentials present)" if self.sms_configured
                else " (credentials missing)")),
        ]


def channel_status() -> ChannelStatus:
    try:
        from education_system.platform.integrations.email.email_service import (
            EmailService,
        )
        email_ok = bool(EmailService().is_configured)
    except Exception:
        logger.debug("EmailService unavailable", exc_info=True)
        email_ok = False
    provider = sms_provider()
    return ChannelStatus(email_mode=email_mode(), email_configured=email_ok,
                         sms_provider=provider,
                         sms_configured=bool(provider)
                         and _twilio_credentials() is not None)


# ── SMS channel ─────────────────────────────────────────────────────

def normalise_phone(value: str | None) -> str | None:
    """Strip spaces/dashes/brackets; UK ``07…`` becomes ``+447…``."""
    s = re.sub(r"[\s\-().]", "", value or "")
    if not s:
        return None
    if s.startswith("00"):
        s = "+" + s[2:]
    elif s.startswith("07") and len(s) == 11:
        s = "+44" + s[1:]
    return s if _PHONE_RE.match(s) else None


def _twilio_credentials() -> tuple[str, str, str] | None:
    cfg: dict[str, Any] = {}
    try:
        cfg = json.loads(paths.PLATFORM_SMS_CONFIG_PATH.read_text(
            encoding="utf-8")).get("twilio", {}) or {}
    except (OSError, ValueError):
        cfg = {}
    sid = os.environ.get("TWILIO_ACCOUNT_SID") or cfg.get("account_sid") or ""
    tok = os.environ.get("TWILIO_AUTH_TOKEN") or cfg.get("auth_token") or ""
    num = os.environ.get("TWILIO_FROM_NUMBER") or cfg.get("from_number") or ""
    return (sid, tok, num) if sid and tok and num else None


def _send_sms_twilio(to: str, body: str) -> str:
    creds = _twilio_credentials()
    if creds is None:
        raise DeliveryError(
            "Twilio credentials missing (platform SMS config / TWILIO_* env)")
    try:
        from twilio.rest import Client  # type: ignore[import-not-found]
    except ImportError:
        raise DeliveryError(
            "twilio package not installed (pip install twilio)") from None
    sid, tok, num = creds
    msg = Client(sid, tok).messages.create(body=body, from_=num, to=to)
    return f"twilio sid {getattr(msg, 'sid', '?')}"


#: name -> callable(to, body) returning a provider reference. A test or
#: an installation can register its own gateway here.
_SMS_SENDERS: dict[str, Callable[[str, str], str]] = {
    "twilio": _send_sms_twilio,
}


def register_sms_sender(name: str, sender: Callable[[str, str], str]) -> None:
    """Make an SMS gateway available under ``name``."""
    name = name.strip().lower()
    _SMS_SENDERS[name] = sender
    if name not in SMS_PROVIDERS:
        globals()["SMS_PROVIDERS"] = SMS_PROVIDERS + (name,)


# ── Queueing ────────────────────────────────────────────────────────

def get_delivery(delivery_id: int) -> Delivery | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM message_deliveries "
                         "WHERE delivery_id = ?", (delivery_id,)).fetchone()
    return _row(r) if r else None


def delivery_for(message_id: int) -> Delivery | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM message_deliveries "
                         "WHERE message_id = ?", (message_id,)).fetchone()
    return _row(r) if r else None


def deliveries_by_message(message_ids: list[int] | None = None
                          ) -> dict[int, Delivery]:
    """Map message_id -> delivery in one query (for list screens)."""
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM message_deliveries").fetchall()
    out = {r["message_id"]: _row(r) for r in rows}
    if message_ids is not None:
        wanted = set(message_ids)
        out = {k: v for k, v in out.items() if k in wanted}
    return out


def list_deliveries(*, state: str | None = None,
                    channel: str | None = None,
                    problems_only: bool = False,
                    limit: int | None = None) -> list[Delivery]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if state:
        clauses.append("state = ?")
        args.append(state)
    if channel:
        clauses.append("channel = ?")
        args.append(channel)
    if problems_only:
        ph = ",".join("?" * 3)
        clauses.append(f"(state IN ({ph}) OR last_error IS NOT NULL) "
                       "AND state != 'Sent'")
        args.extend([FAILED, RETRYING, NO_SMS_PROVIDER])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM message_deliveries {where} "
           "ORDER BY updated_at DESC, delivery_id DESC")
    if limit:
        sql += f" LIMIT {int(limit)}"
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def enqueue(message_id: int) -> Delivery:
    """Create (or reset) the delivery row for a message."""
    init_db()
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _messages,
    )
    msg = _messages.get_message(message_id)
    if msg is None:
        raise _messages.ValidationError(f"No message with id {message_id}")
    if msg.channel not in DELIVERED_CHANNELS:
        raise _messages.ValidationError(
            f"{msg.channel} messages are recorded, not delivered")
    provider = "email" if msg.channel == "Email" else (sms_provider() or None)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO message_deliveries
                   (message_id, channel, recipient, provider, state,
                    attempts, max_attempts, next_attempt_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, NULL)
               ON CONFLICT(message_id) DO UPDATE SET
                   channel = excluded.channel,
                   recipient = excluded.recipient,
                   provider = excluded.provider,
                   state = excluded.state,
                   attempts = 0,
                   max_attempts = excluded.max_attempts,
                   next_attempt_at = NULL,
                   last_error = NULL,
                   updated_at = datetime('now')""",
            (message_id, msg.channel, msg.to_address, provider, QUEUED,
             max_attempts()))
        conn.commit()
    out = delivery_for(message_id)
    assert out is not None
    return out


def _update(delivery_id: int, **fields: Any) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        conn.execute(
            f"UPDATE message_deliveries SET {sets}, "
            "updated_at = datetime('now') WHERE delivery_id = ?",
            (*fields.values(), delivery_id))
        conn.commit()


def _set_message_status(message_id: int, status: str, *,
                        sent: bool = False) -> None:
    """Write the message status directly — the messages module's
    ``update_message`` re-validates the whole row, which is not this
    module's business."""
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _messages,
    )
    with _sql.connect(str(_messages.DB_PATH)) as conn:
        conn.execute(
            "UPDATE messages SET status = ?, "
            "sent_at = CASE WHEN ? THEN COALESCE(sent_at, ?) ELSE sent_at END,"
            " updated_at = datetime('now') WHERE message_id = ?",
            (status, 1 if sent else 0, _now(), message_id))
        conn.commit()


# ── Attempting ──────────────────────────────────────────────────────

def _attempt_email(msg: Any) -> tuple[str, str]:
    """Returns (state, detail). Raises DeliveryError on failure."""
    from education_system.platform.integrations.email import delivery_mode as _dm
    if not msg.to_address:
        raise DeliveryError("No e-mail address on this message")
    mode = _dm.delivery_mode()
    if mode == "inbox_only":
        return HELD, ("Held: e-mail delivery mode is inbox_only — kept in "
                      "the messages log, nothing sent")
    if mode == "sandbox":
        _dm.deliver(msg.to_address, msg.subject, msg.body, lambda: False)
        return SANDBOX, "Written to the e-mail sandbox folder (not sent)"

    from education_system.platform.integrations.email.email_service import (
        EmailService,
    )
    service = EmailService()
    if not service.is_configured:
        raise DeliveryError("SMTP is not configured on this installation")
    cc = [a.strip() for a in (msg.cc_address or "").split(",") if a.strip()]
    result = service.send_email(to=msg.to_address, subject=msg.subject,
                                body=msg.body, cc=cc or None,
                                reply_to=msg.from_address or None)
    if not result.get("success"):
        raise DeliveryError(result.get("error") or "SMTP send failed")
    return SENT, "Accepted by the SMTP server"


def _attempt_sms(msg: Any) -> tuple[str, str]:
    to = normalise_phone(msg.to_address)
    if not to:
        raise DeliveryError(
            f"Not a valid mobile number: {msg.to_address or '(blank)'}")
    provider = sms_provider()
    if not provider:
        return NO_SMS_PROVIDER, ("No SMS provider configured — the text "
                                 "is waiting in the outbox")
    mode = email_mode()
    if mode != "live":
        # The platform delivery mode governs every outbound channel.
        return HELD, f"Held: delivery mode is {mode} — SMS not sent"
    sender = _SMS_SENDERS.get(provider)
    if sender is None:
        raise DeliveryError(f"SMS provider '{provider}' is not available")
    body = msg.body if len(msg.body) <= SMS_MAX_LEN else \
        msg.body[:SMS_MAX_LEN - 1] + "…"
    ref = sender(to, body)
    return SENT, f"Accepted by {provider}" + (f" ({ref})" if ref else "")


def attempt(delivery_id: int) -> Delivery:
    """Try one delivery now and record the outcome. Never raises for a
    failed send — the failure is the recorded outcome."""
    init_db()
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _messages,
    )
    d = get_delivery(delivery_id)
    if d is None:
        raise _messages.ValidationError(f"No delivery with id {delivery_id}")
    if d.state in (SENT, CANCELLED):
        return d
    msg = _messages.get_message(d.message_id)
    if msg is None:
        _update(delivery_id, state=CANCELLED, detail="Message deleted")
        return get_delivery(delivery_id)  # type: ignore[return-value]

    attempts = d.attempts + 1
    now = _now()
    try:
        if msg.channel == "Email":
            state, detail = _attempt_email(msg)
        else:
            state, detail = _attempt_sms(msg)
    except Exception as e:  # noqa: BLE001 - every failure is recorded
        error = str(e) or e.__class__.__name__
        if attempts >= d.max_attempts:
            _update(delivery_id, state=FAILED, attempts=attempts,
                    last_error=error, last_attempt_at=now,
                    next_attempt_at=None,
                    detail=f"Gave up after {attempts} attempt(s)")
            _set_message_status(d.message_id, "Failed")
        else:
            wait = RETRY_BASE_MINUTES * (2 ** (attempts - 1))
            nxt = (_dt.datetime.now() + _dt.timedelta(minutes=wait)
                   ).strftime("%Y-%m-%d %H:%M:%S")
            _update(delivery_id, state=RETRYING, attempts=attempts,
                    last_error=error, last_attempt_at=now,
                    next_attempt_at=nxt,
                    detail=f"Attempt {attempts} failed; retry at {nxt}")
            _set_message_status(d.message_id, "Queued")
        logger.warning("Delivery #%d (message #%d) failed: %s",
                       delivery_id, d.message_id, error)
        return get_delivery(delivery_id)  # type: ignore[return-value]

    if state == SENT:
        _update(delivery_id, state=SENT, attempts=attempts,
                last_attempt_at=now, sent_at=now, next_attempt_at=None,
                detail=detail, last_error=None,
                recipient=msg.to_address)
        _set_message_status(d.message_id, "Sent", sent=True)
    else:
        # Waiting on configuration — not an attempt that failed.
        _update(delivery_id, state=state, last_attempt_at=now,
                next_attempt_at=None, detail=detail,
                recipient=msg.to_address)
        _set_message_status(d.message_id, "Queued")
    logger.info("Delivery #%d (message #%d): %s", delivery_id,
                d.message_id, state)
    return get_delivery(delivery_id)  # type: ignore[return-value]


def deliver_message(message_id: int) -> Delivery:
    """Queue a message and try it straight away."""
    d = enqueue(message_id)
    return attempt(d.delivery_id)


def process_outbox(*, limit: int = 200) -> ProcessResult:
    """Attempt every delivery that is due (queued, or retrying and past
    its retry time)."""
    init_db()
    ph = ",".join("?" * len(DUE_STATES))
    with _connect() as conn:
        ids = [r[0] for r in conn.execute(
            f"SELECT delivery_id FROM message_deliveries "
            f"WHERE state IN ({ph}) AND (next_attempt_at IS NULL "
            f"OR next_attempt_at <= ?) ORDER BY delivery_id LIMIT ?",
            (*DUE_STATES, _now(), int(limit))).fetchall()]
    result = ProcessResult(errors=[])
    for did in ids:
        d = attempt(did)
        result.attempted += 1
        if d.state == SENT:
            result.sent += 1
        elif d.state in (FAILED, RETRYING):
            result.failed += 1
            result.errors.append(f"#{d.message_id}: {d.last_error}")
        else:
            result.waiting += 1
    logger.info("Outbox processed: %d attempted, %d sent, %d failed",
                result.attempted, result.sent, result.failed)
    return result


def retry(delivery_id: int) -> Delivery:
    """Manual retry: reset the attempt count and try now."""
    d = get_delivery(delivery_id)
    if d is None:
        from education_system.systems.sixth_form.domains.communications.domain.messages.messages import (
            ValidationError,
        )
        raise ValidationError(f"No delivery with id {delivery_id}")
    if d.state == SENT:
        return d
    _update(delivery_id, state=QUEUED, attempts=0, next_attempt_at=None,
            max_attempts=max_attempts())
    _set_message_status(d.message_id, "Queued")
    return attempt(delivery_id)


def release_waiting() -> ProcessResult:
    """Re-try deliveries that were held / sandboxed / waiting for an SMS
    provider — use after the delivery mode or provider changes."""
    init_db()
    ph = ",".join("?" * len(WAITING_STATES))
    with _connect() as conn:
        conn.execute(
            f"UPDATE message_deliveries SET state = ?, attempts = 0, "
            f"next_attempt_at = NULL, updated_at = datetime('now') "
            f"WHERE state IN ({ph})", (QUEUED, *WAITING_STATES))
        conn.commit()
    return process_outbox()


def cancel(delivery_id: int) -> Delivery:
    d = get_delivery(delivery_id)
    if d is None:
        from education_system.systems.sixth_form.domains.communications.domain.messages.messages import (
            ValidationError,
        )
        raise ValidationError(f"No delivery with id {delivery_id}")
    if d.state == SENT:
        return d
    _update(delivery_id, state=CANCELLED, next_attempt_at=None,
            detail="Cancelled by staff")
    _set_message_status(d.message_id, "Draft")
    return get_delivery(delivery_id)  # type: ignore[return-value]


def summary() -> dict[str, int]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT state, COUNT(*) AS n FROM "
                            "message_deliveries GROUP BY state").fetchall()
    out = {s: 0 for s in STATES}
    for r in rows:
        out[r["state"]] = r["n"]
    return out
