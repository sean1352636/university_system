"""Sixth-form alumni — Communications log (via the messages module), bounces, channel preferences and email sending.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    Alumnus,
    ChannelPrefs,
    HARD_BOUNCE_THRESHOLD,
    _log_action,
    logger,
)
from .db import (
    ValidationError,
    _connect,
    _validate_date,
    init_db,
)


# ── Communications log (delegates to the messages module) ────────

def _messages_module():
    """Lazy import of the shared sixth-form messaging module."""
    from education_system.systems.sixth_form.domains.communications.domain.messages \
        import messages as _msg
    return _msg


# Re-export the messages module's channels/statuses so callers (CLI,
# views) have one source of truth.
def _comm_channels() -> tuple[str, ...]:
    return _messages_module().CHANNELS


def _comm_statuses() -> tuple[str, ...]:
    return _messages_module().STATUSES


# Backward-compat exports — these were previously defined here.
COMM_CHANNELS = _messages_module().CHANNELS
COMM_STATUSES = _messages_module().STATUSES


def add_communication(alumni_id: int,
                       payload: dict[str, Any]):
    """Record a communication against an alumnus by writing into the
    shared messages log. ``payload`` accepts our previous shape
    (``date`` / ``channel`` / ``staff_id`` / ``subject`` / ``summary``
    / ``status``); legacy channels we used to expose ("Phone",
    "Post", "In Person", "Event") are mapped to the messages
    module's vocabulary."""
    msg = _messages_module()
    init_db()
    raw_channel = (payload.get("channel") or "Email").strip()
    channel_map = {
        "Phone":      "Phone Call",
        "Post":       "Letter",
        "In Person":  "In-Person Meeting",
        "Event":      "In-Person Meeting",
    }
    channel = channel_map.get(raw_channel, raw_channel)
    if channel not in msg.CHANNELS:
        channel = "Other"
    raw_status = (payload.get("status") or "Sent").strip()
    status_map = {
        "Bounced":  "Failed",
        "No Reply": "Sent",
        "Note":     "Received",
    }
    status = status_map.get(raw_status, raw_status)
    if status not in msg.STATUSES:
        status = "Sent"

    alumnus = get_alumnus(alumni_id)
    if alumnus is None:
        raise ValidationError(f"No alumnus #{alumni_id}")

    day = _validate_date(payload.get("date")
                            or _dt.date.today().isoformat(),
                          "Date", required=True)
    # messages.sent_at accepts "YYYY-MM-DD" or "YYYY-MM-DD HH:MM[:SS]"
    sent_at = day if status in msg.SENT_STATUSES else None
    return msg.create_message({
        "direction":  ("Incoming" if status == "Received"
                         else "Outgoing"),
        "channel":    channel,
        "status":     status,
        "subject":    (payload.get("subject")
                        or f"Contact ({raw_channel})"),
        "body":       payload.get("summary") or "",
        "alumni_id":  alumni_id,
        "to_name":    alumnus.full_name,
        "to_address": (alumnus.email
                         if channel in ("Email", "Portal") else None),
        "staff_id":   (payload.get("staff_id") or "").strip().upper()
                         or None,
        "sent_at":    sent_at,
        "tags":       payload.get("tags"),
        "notes":      payload.get("notes"),
    })


def list_communications(alumni_id: int) -> list:
    """Return the messages-module rows logged against this alumnus,
    newest first."""
    return _messages_module().list_messages(alumni_id=alumni_id)


def delete_communication(comm_id: int) -> bool:
    return _messages_module().delete_message(comm_id)


# ── Bounces ──────────────────────────────────────────────────────

def record_bounce(alumni_id: int, *, hard: bool = True,
                   reason: str | None = None) -> Alumnus:
    """Record a delivery bounce. Hard bounces increment ``bounce_count``
    and auto-flip ``status`` to 'Lost Contact' at the threshold.
    The bounce is also written to the messages log as a Failed
    Outgoing message tagged ``bounce-hard`` / ``bounce-soft``."""
    init_db()
    a0 = get_alumnus(alumni_id)
    if a0 is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    if hard:
        with _connect() as conn:
            conn.execute(
                "UPDATE alumni SET bounce_count = bounce_count + 1, "
                "updated_at = datetime('now') WHERE alumni_id = ?",
                (alumni_id,))
            conn.commit()
    try:
        _messages_module().create_message({
            "direction":  "Outgoing",
            "channel":    "Email",
            "status":     "Failed",
            "subject":    "Hard bounce" if hard else "Soft bounce",
            "body":       reason or ("Hard bounce recorded"
                                       if hard
                                       else "Soft bounce recorded"),
            "alumni_id":  alumni_id,
            "to_name":    a0.full_name,
            "to_address": a0.email,
            "tags":       "bounce-hard" if hard else "bounce-soft",
        })
    except Exception:
        logger.exception(
            "Could not log bounce to messages for alumnus #%d",
            alumni_id)
    a = get_alumnus(alumni_id)
    assert a is not None
    _log_action("alumnus.bounce", alumni_id=alumni_id,
                  hard=hard, bounce_count=a.bounce_count)
    if hard and a.bounce_count >= HARD_BOUNCE_THRESHOLD \
            and a.status == "Active":
        a = set_status(alumni_id, "Lost Contact")
        _log_action("alumnus.auto_status_change",
                      alumni_id=alumni_id, status="Lost Contact",
                      reason="hard_bounce_threshold",
                      bounces=a.bounce_count,
                      level=logging.WARNING)
    return a


def clear_bounces(alumni_id: int) -> Alumnus:
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            "UPDATE alumni SET bounce_count = 0, "
            "updated_at = datetime('now') WHERE alumni_id = ?",
            (alumni_id,))
        conn.commit()
    a = get_alumnus(alumni_id)
    assert a is not None
    return a


# ── Channel preferences ───────────────────────────────────────────

def _row_prefs(r: db.Row) -> ChannelPrefs:
    return ChannelPrefs(
        alumni_id=r["alumni_id"],
        opt_in_email=bool(r["opt_in_email"]),
        opt_in_post=bool(r["opt_in_post"]),
        opt_in_phone=bool(r["opt_in_phone"]),
        opt_in_sms=bool(r["opt_in_sms"]),
        updated_at=r["updated_at"],
    )


def get_channel_prefs(alumni_id: int) -> ChannelPrefs:
    """Return prefs, creating defaults seeded from ``opt_in_contact``
    if no row exists yet."""
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        r = conn.execute(
            "SELECT * FROM alumni_channel_prefs WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        if r is None:
            seed = conn.execute(
                "SELECT opt_in_contact FROM alumni WHERE alumni_id = ?",
                (alumni_id,)).fetchone()
            default = 1 if seed and seed["opt_in_contact"] else 0
            conn.execute(
                """INSERT INTO alumni_channel_prefs
                       (alumni_id, opt_in_email, opt_in_post,
                        opt_in_phone, opt_in_sms)
                   VALUES (?, ?, ?, ?, ?)""",
                (alumni_id, default, default, default, default))
            conn.commit()
            r = conn.execute(
                "SELECT * FROM alumni_channel_prefs WHERE alumni_id = ?",
                (alumni_id,)).fetchone()
    return _row_prefs(r)


def update_channel_prefs(alumni_id: int, *,
                          opt_in_email: bool | None = None,
                          opt_in_post:  bool | None = None,
                          opt_in_phone: bool | None = None,
                          opt_in_sms:   bool | None = None
                          ) -> ChannelPrefs:
    cur = get_channel_prefs(alumni_id)
    new = ChannelPrefs(
        alumni_id=alumni_id,
        opt_in_email=cur.opt_in_email if opt_in_email is None
                       else bool(opt_in_email),
        opt_in_post=cur.opt_in_post   if opt_in_post  is None
                       else bool(opt_in_post),
        opt_in_phone=cur.opt_in_phone if opt_in_phone is None
                       else bool(opt_in_phone),
        opt_in_sms=cur.opt_in_sms     if opt_in_sms   is None
                       else bool(opt_in_sms),
        updated_at="",
    )
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni_channel_prefs
                   SET opt_in_email = ?, opt_in_post = ?,
                       opt_in_phone = ?, opt_in_sms = ?,
                       updated_at = datetime('now')
                   WHERE alumni_id = ?""",
            (1 if new.opt_in_email else 0,
             1 if new.opt_in_post  else 0,
             1 if new.opt_in_phone else 0,
             1 if new.opt_in_sms   else 0,
             alumni_id))
        # Keep the legacy alumni.opt_in_contact in sync: 1 if any channel
        # is enabled, else 0.
        any_on = (new.opt_in_email or new.opt_in_post
                   or new.opt_in_phone or new.opt_in_sms)
        conn.execute(
            "UPDATE alumni SET opt_in_contact = ?, "
            "updated_at = datetime('now') WHERE alumni_id = ?",
            (1 if any_on else 0, alumni_id))
        conn.commit()
    return get_channel_prefs(alumni_id)


# ── Email sending (via the messages module) ───────────────────────

def _render(template: str, context: dict[str, Any]) -> str:
    """Tiny placeholder renderer: {first_name}, {last_name} etc."""
    out = template
    for k, v in context.items():
        out = out.replace("{" + k + "}", str(v) if v is not None else "")
    return out


def _alumnus_context(a: Alumnus) -> dict[str, Any]:
    return {
        "first_name":     a.first_name,
        "last_name":      a.last_name,
        "preferred_name": a.preferred_name or a.first_name,
        "leaving_year":   a.leaving_year or "",
    }


def _queue_and_send(payload: dict[str, Any]):
    """Log an outgoing e-mail as Queued and hand it to the sixth form
    outbox. The returned message reads ``Sent`` only when a provider
    accepted it; ``Queued`` while the delivery mode holds it or a retry
    is pending; ``Failed`` once retries ran out."""
    msg = _messages_module()
    out = msg.create_message({**payload, "status": "Queued",
                              "sent_at": None})
    return msg.send_message(out.message_id)


def delivery_note(message) -> str:
    """One line saying what happened to an alumni e-mail."""
    msg = _messages_module()
    d = msg.delivery_status(message.message_id)
    if message.status in msg.SENT_STATUSES:
        return "Sent — accepted by the mail server"
    if message.status == "Failed":
        return "Failed — " + ((d.last_error if d else None) or "not delivered")
    return "Queued in the outbox — " + ((d.detail if d else None)
                                         or "waiting to be sent")


def send_email_to_alumnus(alumni_id: int, subject: str, body: str,
                            *, staff_id: str | None = None,
                            respect_optin: bool = True,
                            category: str = "General"):
    """Compose an outgoing e-mail, log it in the shared messages module
    and hand it to the outbox. Returns the :class:`messages.Message`;
    its ``status`` says whether it was really sent (see
    :func:`delivery_note`)."""
    init_db()
    a = get_alumnus(alumni_id)
    if a is None:
        raise ValidationError(f"No alumnus #{alumni_id}")
    if not a.email:
        raise ValidationError("Alumnus has no primary email")
    if respect_optin:
        prefs = get_channel_prefs(alumni_id)
        if not prefs.opt_in_email:
            raise ValidationError(
                "Alumnus has opted out of email contact")
    ctx = _alumnus_context(a)
    out = _queue_and_send({
        "direction":  "Outgoing",
        "channel":    "Email",
        "category":   category,
        "subject":    _render(subject, ctx),
        "body":       _render(body, ctx),
        "alumni_id":  alumni_id,
        "to_name":    a.full_name,
        "to_address": a.email,
        "staff_id":   (staff_id or "").strip().upper() or None,
    })
    _log_action("alumnus.send_email", actor=staff_id,
                  alumni_id=alumni_id, message_id=out.message_id,
                  subject=out.subject, status=out.status)
    return out


def send_email_bulk(filters: dict[str, Any], subject: str, body: str,
                     *, staff_id: str | None = None,
                     category: str = "General"):
    """Mail-merge to every alumnus matching ``filters`` (same kwargs
    as :func:`list_alumni`) who has an email, is Active and has
    ``opt_in_email`` set. One messages row per recipient, each handed to
    the outbox. Returns ``(handed_over, skipped)``: ``handed_over``
    counts e-mails the outbox accepted (sent, or held/queued by the
    delivery mode); one that failed outright counts as skipped."""
    init_db()
    rows = list_alumni(**filters)
    recipients: list[tuple[int, str, str]] = []
    skipped = 0
    for a in rows:
        if not a.email or a.status != "Active":
            skipped += 1
            continue
        try:
            prefs = get_channel_prefs(a.alumni_id)
        except ValidationError:
            skipped += 1
            continue
        if not prefs.opt_in_email:
            skipped += 1
            continue
        ctx = _alumnus_context(a)
        # Per-recipient merge: create one outgoing message per
        # alumnus so placeholders render against their record.
        try:
            out = _queue_and_send({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   category,
                "subject":    _render(subject, ctx),
                "body":       _render(body, ctx),
                "alumni_id":  a.alumni_id,
                "to_name":    a.full_name,
                "to_address": a.email,
                "staff_id":   (staff_id or "").strip().upper() or None,
            })
            if out.status == "Failed":
                skipped += 1
                continue
            recipients.append((a.alumni_id, a.full_name, a.email))
        except Exception:
            logger.exception(
                "Bulk send failed for alumnus #%d", a.alumni_id)
            skipped += 1
    _log_action("alumnus.send_email_bulk", actor=staff_id,
                  sent=len(recipients), skipped=skipped,
                  filters=str(filters))
    return len(recipients), skipped


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .records import (  # noqa: E402,F401
    get_alumnus,
    list_alumni,
    set_status,
)
from .profile import (  # noqa: E402,F401
    _require_alumnus,
)
