"""School e-mail: compose, address, store and deliver.

Every message is saved first, with one row per recipient, and only then
delivered, so nothing is ever reported as sent that wasn't. Delivery follows
the platform-wide delivery mode (``platform/integrations/email/delivery_mode``):

* ``inbox_only`` - nothing leaves the building; recipients are marked
  ``stored``. This is the default until an administrator switches it.
* ``sandbox`` - each e-mail is written as an ``.eml`` file to
  ``paths.SECONDARY_EMAIL_SANDBOX_DIR`` instead of being sent.
* ``live`` - sent through the shared SMTP settings. Failures are recorded
  per recipient with the reason, and can be retried (up to
  :data:`MAX_ATTEMPTS` tries).

Addressing: a message goes to the contacts of chosen pupils, a form group, a
year group or the whole school, plus any extra addresses typed in. Only
contacts with an address who accept school e-mail are included; pupils with
nobody to e-mail are reported back so staff can follow them up another way.
E-mailing a whole form, year or the school needs a role in
:data:`access.BULK_EMAIL_SENDERS`.

Personalisation: the body and subject may use :data:`PLACEHOLDERS`, filled
in per recipient. An unknown ``{placeholder}`` is refused before anything is
saved, so a typo can't reach parents.

Privacy: staff see the messages they sent; administrators see all. The
activity log records counts and message numbers, never addresses or text.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import threading
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any

from education_system import paths
from education_system.systems.secondary.core.permissions import access
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
MAX_SUBJECT = 200
MAX_BODY = 20000
MAX_RECIPIENTS = 2000

AUDIENCE_KINDS = ("pupils", "form", "year", "school", "none")

#: Placeholders allowed in subject and body, and what fills them.
PLACEHOLDERS: dict[str, str] = {
    "contact_name": "The contact's name ('Parent/Carer' for typed-in addresses)",
    "pupil_first_name": "The pupil's preferred or first name",
    "pupil_name": "The pupil's preferred first name and surname",
    "year_group": "The pupil's year group number",
    "form_group": "The pupil's form group",
}
#: Placeholders that need a pupil (not available for typed-in addresses).
PUPIL_PLACEHOLDERS = frozenset(PLACEHOLDERS) - {"contact_name"}

RECIPIENT_STATUSES = ("queued", "stored", "sandbox", "sent", "failed")
STATUS_LABELS = {
    "queued": "Waiting to send",
    "stored": "Saved, not sent (inbox only)",
    "sandbox": "Written to sandbox",
    "sent": "Sent",
    "failed": "Failed",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS email_messages (
    message_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    audience_kind   TEXT NOT NULL,
    audience_label  TEXT NOT NULL,
    sender_username TEXT NOT NULL,
    sender_role     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_email_messages_sender ON email_messages (sender_username, created_at);

-- No foreign keys to pupils/contacts: the record of who was e-mailed must
-- survive a pupil or contact being removed later.
CREATE TABLE IF NOT EXISTS email_recipients (
    recipient_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id     INTEGER NOT NULL REFERENCES email_messages(message_id) ON DELETE CASCADE,
    address        TEXT NOT NULL,
    display_name   TEXT,
    pupil_id       INTEGER,
    admission_no   TEXT,
    contact_id     INTEGER,
    subject        TEXT NOT NULL,
    body           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'queued'
                   CHECK (status IN ('queued', 'stored', 'sandbox', 'sent', 'failed')),
    attempts       INTEGER NOT NULL DEFAULT 0,
    last_error     TEXT,
    delivered_at   TEXT,
    UNIQUE (message_id, address)
);
CREATE INDEX IF NOT EXISTS ix_email_recipients_status ON email_recipients (status, message_id);
"""

database.register_schema("email_outbox", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

_deliver_lock = threading.Lock()


# ── Addressing ───────────────────────────────────────────────────────

@dataclass
class Audience:
    """Who a message is for. ``kind`` picks the pupils; extra addresses are
    added whatever the kind."""

    kind: str = "none"
    pupil_ids: list[int] = field(default_factory=list)
    form_group: str | None = None
    year_group: int | None = None
    extra_addresses: list[str] = field(default_factory=list)

    @property
    def is_bulk(self) -> bool:
        return self.kind in {"form", "year", "school"}

    def label(self) -> str:
        parts = []
        if self.kind == "pupils":
            n = len(self.pupil_ids)
            parts.append(f"Contacts of {n} pupil{'s' if n != 1 else ''}")
        elif self.kind == "form":
            parts.append(f"Contacts of form {self.form_group}")
        elif self.kind == "year":
            parts.append(f"Contacts of Year {self.year_group}")
        elif self.kind == "school":
            parts.append("Contacts of all pupils on roll")
        if self.extra_addresses:
            n = len(self.extra_addresses)
            parts.append(f"{n} other address{'es' if n != 1 else ''}")
        return " + ".join(parts) or "Nobody"


@dataclass(frozen=True)
class Recipient:
    address: str
    display_name: str
    pupil: P.Pupil | None = None
    contact_id: int | None = None


@dataclass
class Resolved:
    """The result of addressing a message, before anything is saved."""

    recipients: list[Recipient]
    pupils: int
    pupils_without_email: list[P.Pupil]
    invalid_addresses: list[str]


def _audience_pupils(audience: Audience) -> list[P.Pupil]:
    if audience.kind == "pupils":
        found = [P.get_pupil(pid) for pid in dict.fromkeys(audience.pupil_ids)]
        return [p for p in found if p is not None]
    if audience.kind == "form":
        return P.list_pupils(form_group=audience.form_group)
    if audience.kind == "year":
        return P.list_pupils(year_group=audience.year_group)
    if audience.kind == "school":
        return P.list_pupils()
    return []


def resolve(audience: Audience) -> Resolved:
    """Work out exactly who would receive a message (no side effects).

    Screens call this to show "this will go to N people" before sending.
    """
    if audience.kind not in AUDIENCE_KINDS:
        raise ValidationError([f"Unknown audience '{audience.kind}'"])
    pupils = _audience_pupils(audience)
    by_pupil = C.emailable_for_pupils([p.pupil_id for p in pupils])
    seen: set[str] = set()
    recipients: list[Recipient] = []
    without: list[P.Pupil] = []
    for pupil in pupils:
        found = by_pupil.get(pupil.pupil_id, [])
        if not found:
            without.append(pupil)
        for contact in found:
            address = (contact.email or "").lower()
            if address in seen:
                continue  # one e-mail per address, even for siblings
            seen.add(address)
            recipients.append(Recipient(address, contact.full_name, pupil, contact.contact_id))
    invalid = []
    for raw in audience.extra_addresses:
        address = raw.strip().lower()
        if not address:
            continue
        if not C.valid_email(address):
            invalid.append(raw.strip())
            continue
        if address not in seen:
            seen.add(address)
            recipients.append(Recipient(address, "Parent/Carer"))
    return Resolved(recipients, len(pupils), without, invalid)


def parse_addresses(text: str) -> list[str]:
    """Split typed addresses on commas, semicolons, spaces or new lines."""
    return [a for a in re.split(r"[,;\s]+", text or "") if a]


# ── Personalisation ──────────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_]+)\}")


def unknown_placeholders(text: str) -> list[str]:
    return sorted({m for m in _PLACEHOLDER_RE.findall(text or "") if m not in PLACEHOLDERS})


def personalise(text: str, recipient: Recipient) -> str:
    pupil = recipient.pupil
    values = {
        "contact_name": recipient.display_name or "Parent/Carer",
        "pupil_first_name": (pupil.preferred_name or pupil.legal_first_name) if pupil else "",
        "pupil_name": pupil.display_name if pupil else "",
        "year_group": str(pupil.year_group) if pupil else "",
        "form_group": (pupil.form_group or "") if pupil else "",
    }
    return _PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), text)


# ── Sending ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SendResult:
    message_id: int
    recipients: int
    pupils_without_email: list[P.Pupil]


def _validate_message(subject: str, body: str, audience: Audience,
                      actor: Principal) -> tuple[str, str, Resolved]:
    problems: list[str] = []
    subject = " ".join((subject or "").split())  # no line breaks: no header injection
    body = (body or "").replace("\r\n", "\n").strip()
    if not subject:
        problems.append("A subject is required")
    elif len(subject) > MAX_SUBJECT:
        problems.append(f"The subject is too long (over {MAX_SUBJECT} characters)")
    if not body:
        problems.append("The message is empty")
    elif len(body) > MAX_BODY:
        problems.append(f"The message is too long (over {MAX_BODY} characters)")
    bad = unknown_placeholders(subject + "\n" + body)
    if bad:
        problems.append("Unknown placeholder(s): " + ", ".join("{" + b + "}" for b in bad)
                        + ". Allowed: " + ", ".join("{" + k + "}" for k in PLACEHOLDERS))
    if audience.is_bulk and not actor.can_email_bulk:
        raise PermissionDenied(
            "Your account can e-mail chosen pupils' contacts, but not a whole "
            "form, year group or the school.")
    if audience.kind == "form" and not audience.form_group:
        problems.append("Choose a form group")
    if audience.kind == "year" and audience.year_group not in P.YEAR_GROUPS:
        problems.append("Choose a year group")
    resolved = resolve(audience)
    used = set(_PLACEHOLDER_RE.findall(subject + "\n" + body)) & PUPIL_PLACEHOLDERS
    if used and any(r.pupil is None for r in resolved.recipients):
        problems.append("Pupil placeholders (" + ", ".join("{" + u + "}" for u in sorted(used))
                        + ") can't be filled in for typed-in addresses - remove them or "
                        "remove the other addresses")
    if resolved.invalid_addresses:
        problems.append("These addresses don't look right: "
                        + ", ".join(resolved.invalid_addresses))
    if not resolved.recipients and not problems:
        problems.append("Nobody to send to - none of the chosen pupils has a contact "
                        "who accepts e-mail, and no other addresses were given")
    if len(resolved.recipients) > MAX_RECIPIENTS:
        problems.append(f"Too many recipients ({len(resolved.recipients)}; "
                        f"the limit is {MAX_RECIPIENTS})")
    if problems:
        raise ValidationError(problems)
    return subject, body, resolved


def send_message(subject: str, body: str, audience: Audience, *,
                 actor: Principal) -> SendResult:
    """Validate, address and save a message, ready for :func:`deliver`.

    Nothing is delivered here; callers run :func:`deliver` next (the GUI in
    a background thread) so a slow mail server never freezes a screen.
    """
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can send e-mail.")
    try:
        subject, body, resolved = _validate_message(subject, body, audience, actor)
    except PermissionDenied:
        activity_log.record("email.send", outcome="denied", principal=actor,
                            audience=audience.kind)
        raise
    except ValidationError as e:
        activity_log.record("email.send", outcome="invalid", principal=actor,
                            audience=audience.kind, problems=len(e.problems))
        raise
    with database.connect() as conn:
        cur = conn.execute(
            "INSERT INTO email_messages (subject, body, audience_kind, audience_label, "
            "sender_username, sender_role) VALUES (?, ?, ?, ?, ?, ?)",
            (subject, body, audience.kind, audience.label(), actor.username, actor.role))
        message_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO email_recipients (message_id, address, display_name, pupil_id, "
            "admission_no, contact_id, subject, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(message_id, r.address, r.display_name,
              r.pupil.pupil_id if r.pupil else None,
              r.pupil.admission_no if r.pupil else None, r.contact_id,
              personalise(subject, r), personalise(body, r)) for r in resolved.recipients])
    activity_log.record("email.send", target=f"message:{message_id}", principal=actor,
                        audience=audience.kind, recipients=len(resolved.recipients),
                        pupils=resolved.pupils,
                        pupils_without_email=len(resolved.pupils_without_email) or None)
    return SendResult(message_id, len(resolved.recipients), resolved.pupils_without_email)


def send_to_address(address: str, display_name: str, subject: str, body: str, *,
                    actor: Principal, kind: str, label: str,
                    pupil: P.Pupil | None = None) -> int:
    """Save an already-written e-mail to one address (e.g. from a template) and
    return its message id; run :func:`deliver` next, as with :func:`send_message`.

    *kind* names what sent it (``"pupil_welcome"``) and is logged.
    """
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can send e-mail.")
    address = (address or "").strip().lower()
    subject = " ".join((subject or "").split())
    body = (body or "").replace("\r\n", "\n").strip()
    problems = []
    if not C.valid_email(address):
        problems.append("The e-mail address doesn't look right")
    if not subject or len(subject) > MAX_SUBJECT:
        problems.append("The subject is missing or too long")
    if not body or len(body) > MAX_BODY:
        problems.append("The message is missing or too long")
    if problems:
        activity_log.record("email.send", outcome="invalid", principal=actor, audience=kind,
                            problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        message_id = conn.execute(
            "INSERT INTO email_messages (subject, body, audience_kind, audience_label, "
            "sender_username, sender_role) VALUES (?, ?, ?, ?, ?, ?)",
            (subject, body, kind, label, actor.username, actor.role)).lastrowid
        conn.execute(
            "INSERT INTO email_recipients (message_id, address, display_name, pupil_id, "
            "admission_no, subject, body) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (message_id, address, display_name, pupil.pupil_id if pupil else None,
             pupil.admission_no if pupil else None, subject, body))
    activity_log.record("email.send", target=f"message:{message_id}", principal=actor,
                        audience=kind, recipients=1,
                        pupil=pupil.admission_no if pupil else None)
    return int(message_id)


def save_prepared(kind: str, label: str, subject: str, body: str,
                  recipients: list[tuple[str, str, str, str]], *, actor: Principal) -> int:
    """Save a message whose recipients were addressed and personalised by the
    caller (e.g. alumni mailings): ``(address, display_name, subject, body)``
    each. Returns the message id; run :func:`deliver` next."""
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can send e-mail.")
    if not recipients:
        raise ValidationError(["Nobody to send to"])
    if len(recipients) > MAX_RECIPIENTS:
        raise ValidationError([f"Too many recipients ({len(recipients)}; "
                               f"the limit is {MAX_RECIPIENTS})"])
    with database.connect() as conn:
        message_id = conn.execute(
            "INSERT INTO email_messages (subject, body, audience_kind, audience_label, "
            "sender_username, sender_role) VALUES (?, ?, ?, ?, ?, ?)",
            (subject, body, kind, label, actor.username, actor.role)).lastrowid
        conn.executemany(
            "INSERT OR IGNORE INTO email_recipients (message_id, address, display_name, "
            "subject, body) VALUES (?, ?, ?, ?, ?)",
            [(message_id, a.strip().lower(), n, s, b) for a, n, s, b in recipients])
    activity_log.record("email.send", target=f"message:{message_id}", principal=actor,
                        audience=kind, recipients=len(recipients))
    return int(message_id)


# ── Delivery ─────────────────────────────────────────────────────────

def delivery_mode() -> str:
    from education_system.platform.integrations.email.delivery_mode import (
        delivery_mode as _mode,
    )
    try:
        return _mode()
    except Exception:
        return "inbox_only"


MODE_DESCRIPTIONS = {
    "inbox_only": "Inbox only - messages are saved here but not sent to anyone.",
    "sandbox": "Sandbox - messages are written to files for checking, not sent.",
    "live": "Live - messages are sent to recipients by e-mail.",
}


def _write_sandbox(row) -> None:
    msg = EmailMessage()
    msg["To"] = row["address"]
    msg["From"] = "school@localhost"
    msg["Subject"] = row["subject"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(row["body"])
    folder = paths.SECONDARY_EMAIL_SANDBOX_DIR
    folder.mkdir(parents=True, exist_ok=True)
    name = f"msg{row['message_id']:06d}_r{row['recipient_id']:07d}.eml"
    (folder / name).write_text(msg.as_string(), encoding="utf-8")


@dataclass(frozen=True)
class DeliveryReport:
    mode: str
    counts: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def deliver(message_id: int | None = None, *, principal: Principal | None = None,
            sender=None) -> DeliveryReport:
    """Deliver queued recipients (of one message, or all) by the current mode.

    Safe to call from a background thread and to call twice: a lock stops two
    deliveries overlapping, and each row is marked as soon as it is handled.
    *sender* is for tests: an object with ``send_email(to, subject, body)``
    returning ``{"success": bool, "error": str}``.
    """
    mode = delivery_mode()
    counts: dict[str, int] = {}
    with _deliver_lock:
        sql = "SELECT * FROM email_recipients WHERE status = 'queued'"
        params: list[Any] = []
        if message_id is not None:
            sql += " AND message_id = ?"
            params.append(int(message_id))
        with database.connect() as conn:
            rows = conn.execute(sql + " ORDER BY recipient_id", params).fetchall()
        reply_to = None
        if mode == "live" and rows and sender is None:
            from education_system.platform.integrations.email.email_service import EmailService
            name, reply_to = _sender_settings()
            sender = EmailService(from_name=name)
        for row in rows:
            status, error = _deliver_one(row, mode, sender, reply_to)
            counts[status] = counts.get(status, 0) + 1
            with database.connect() as conn:
                conn.execute(
                    "UPDATE email_recipients SET status = ?, attempts = attempts + ?, "
                    "last_error = ?, delivered_at = CASE WHEN ? IN ('sent', 'sandbox') "
                    "THEN datetime('now') ELSE delivered_at END WHERE recipient_id = ?",
                    (status, 1 if mode != "inbox_only" else 0, error, status,
                     row["recipient_id"]))
    if counts:
        activity_log.record("email.deliver", principal=principal,
                            target=f"message:{message_id}" if message_id else "all_queued",
                            mode=mode, **{k: v for k, v in sorted(counts.items())})
    return DeliveryReport(mode, counts)


def _sender_settings() -> tuple[str | None, str | None]:
    """(sender name, reply-to) from School Settings: the sender name falls
    back to the school name, reply-to to the school office e-mail. None
    leaves the e-mail service's own configuration in place."""
    try:
        from education_system.systems.secondary.modules.administration.domain import settings as ST
        v = ST.school_values()
        return (v.get("email_sender_name") or None,
                ST.get_setting("email_reply_to") or v.get("school_email") or None)
    except Exception:  # noqa: BLE001 - settings unreadable: keep the service defaults
        logger.exception("School settings for e-mail sender could not be read")
        return None, None


def _deliver_one(row, mode: str, sender, reply_to: str | None = None
                 ) -> tuple[str, str | None]:
    if mode == "inbox_only":
        return "stored", None
    if mode == "sandbox":
        try:
            _write_sandbox(row)
            return "sandbox", None
        except OSError as e:
            return "failed", f"Could not write sandbox file: {e}"
    try:
        result = sender.send_email(row["address"], row["subject"], row["body"],
                                   **({"reply_to": reply_to} if reply_to else {}))
    except Exception as e:  # noqa: BLE001 - a bad recipient must not stop the rest
        return "failed", f"{type(e).__name__}: {e}"[:300]
    if result.get("success"):
        return "sent", None
    return "failed", str(result.get("error") or "Unknown error")[:300]


def retry_failed(message_id: int, *, actor: Principal) -> int:
    """Queue a message's failed recipients again (those under MAX_ATTEMPTS).
    Returns how many were queued; run :func:`deliver` afterwards."""
    _message_for(message_id, actor)
    with database.connect() as conn:
        cur = conn.execute(
            "UPDATE email_recipients SET status = 'queued' WHERE message_id = ? "
            "AND status = 'failed' AND attempts < ?", (int(message_id), MAX_ATTEMPTS))
        n = cur.rowcount
    activity_log.record("email.retry", target=f"message:{message_id}", principal=actor,
                        requeued=n)
    return n


def queued_count() -> int:
    with database.connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM email_recipients WHERE status = 'queued'").fetchone()[0]


# ── Reading ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MessageSummary:
    message_id: int
    subject: str
    body: str
    audience_label: str
    sender_username: str
    created_at: str
    counts: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def status_text(self) -> str:
        order = ("sent", "sandbox", "stored", "queued", "failed")
        return ", ".join(f"{self.counts[k]} {STATUS_LABELS[k].lower()}"
                         for k in order if self.counts.get(k))


def _can_see_all(actor: Principal) -> bool:
    return actor.role in access.EMAIL_ADMINS


def _summaries(where: str, params: list[Any], limit: int | None = None) -> list[MessageSummary]:
    sql = f"SELECT * FROM email_messages {where} ORDER BY message_id DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params = [*params, int(limit)]
    with database.connect() as conn:
        msgs = conn.execute(sql, params).fetchall()
        counts: dict[int, dict[str, int]] = {}
        if msgs:
            ids = [m["message_id"] for m in msgs]
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                for r in conn.execute(
                        "SELECT message_id, status, COUNT(*) AS n FROM email_recipients "
                        f"WHERE message_id IN ({', '.join('?' for _ in chunk)}) "
                        "GROUP BY message_id, status", chunk):
                    counts.setdefault(r["message_id"], {})[r["status"]] = r["n"]
    return [MessageSummary(m["message_id"], m["subject"], m["body"], m["audience_label"],
                           m["sender_username"], m["created_at"],
                           counts.get(m["message_id"], {})) for m in msgs]


def list_messages(*, actor: Principal, limit: int = 500) -> list[MessageSummary]:
    """Messages this person may see, newest first."""
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can see school e-mail.")
    if _can_see_all(actor):
        return _summaries("", [], limit)
    return _summaries("WHERE sender_username = ?", [actor.username], limit)


def _message_for(message_id: int, actor: Principal) -> MessageSummary:
    found = _summaries("WHERE message_id = ?", [int(message_id)])
    if not found:
        raise NotFound(f"No message {message_id}")
    message = found[0]
    if not _can_see_all(actor) and message.sender_username != actor.username:
        activity_log.record("email.view", target=f"message:{message_id}", outcome="denied",
                            principal=actor)
        raise PermissionDenied("You can only open messages you sent.")
    return message


def get_message(message_id: int, *, actor: Principal) -> tuple[MessageSummary, list[dict]]:
    """A message and its recipients, if *actor* may see it."""
    message = _message_for(message_id, actor)
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT recipient_id, address, display_name, admission_no, status, attempts, "
            "last_error, delivered_at FROM email_recipients WHERE message_id = ? "
            "ORDER BY admission_no, address", (int(message_id),)).fetchall()
    activity_log.record("email.view", target=f"message:{message_id}", principal=actor)
    return message, [dict(r) for r in rows]


def today_counts() -> dict[str, int]:
    """Recipient counts for messages created today (dashboard use)."""
    today = _dt.date.today().isoformat()
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT r.status, COUNT(*) FROM email_recipients r JOIN email_messages m "
            "USING (message_id) WHERE m.created_at >= ? GROUP BY r.status",
            (today,)).fetchall()
    return {r[0]: r[1] for r in rows}
