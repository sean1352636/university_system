"""Reminders, RSVP messages, change notices and digests for the
Sixth Form Calendar.

Sibling to :mod:`calendar`. Until now the calendar told nobody
anything: :func:`calendar.cancel_event` flipped a status and everyone
turned up anyway. The 27 email templates next door cover library
fines and missing homework, and not one of them mentions an event.

Everything goes through a queue, the same shape as
:mod:`attendance_notifications`: a message is *queued* by whichever
rule produced it, sits inspectable in the table, and goes out when
:func:`send_queued` drains it. The queue is the audit trail and the
safety valve — a bad sweep queues nonsense, and nonsense in a queue
is deletable in a way nonsense in inboxes is not.

The producers:

* :func:`sweep_reminders` — events N days out get a reminder, N per
  type from :data:`REMINDER_LEAD_DAYS`. Idempotent by dedupe key.
* :func:`notify_change` / :func:`notify_cancellation` — the diff, in
  sentences, to the people affected. Wired into the views' save
  path rather than the core module, so imports stay one-way.
* :func:`queue_rsvp_request` / :func:`queue_rsvp_confirmation` —
  what ``rsvp_required`` has been waiting for.
* :func:`queue_week_ahead` — one digest per audience, Monday's
  briefing note.

Recipients are free text. A row addressed to a real address
(``x@y``) is sent by :func:`send_queued`; a row addressed to an
audience (``audience:Students``) is a broadcast whose fan-out
belongs to whatever front end knows the mailing lists — it stays
queued until something claims it.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable

from education_system import paths
from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_CALENDAR_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

REMINDER: str = "Reminder"
RSVP_REQUEST: str = "RSVP Request"
RSVP_CONFIRMATION: str = "RSVP Confirmation"
CHANGE_NOTICE: str = "Change Notice"
CANCELLATION: str = "Cancellation"
DIGEST: str = "Week Ahead"
KINDS: tuple[str, ...] = (
    REMINDER, RSVP_REQUEST, RSVP_CONFIRMATION, CHANGE_NOTICE,
    CANCELLATION, DIGEST,
)

QUEUED: str = "Queued"
SENT: str = "Sent"
FAILED: str = "Failed"
CANCELLED: str = "Cancelled"
STATES: tuple[str, ...] = (QUEUED, SENT, FAILED, CANCELLED)

# How many days before each type of event its reminder goes out.
# Types not listed remind the day before.
REMINDER_LEAD_DAYS: dict[str, int] = {
    "Trip": 7,
    "Parents' Evening": 3,
    "Open Day": 3,
    "Exam": 3,
    "Mock Exam": 3,
    "Deadline": 2,
}
DEFAULT_REMINDER_LEAD: int = 1

# Event fields whose change is worth telling people about. A tweaked
# internal note is not.
NOTIFIABLE_FIELDS: tuple[str, ...] = (
    "start_date", "end_date", "start_time", "end_time", "location",
    "status",
)

_FIELD_LABELS: dict[str, str] = {
    "start_date": "date", "end_date": "end date",
    "start_time": "start time", "end_time": "end time",
    "location": "location", "status": "status",
}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     INTEGER,
    kind         TEXT NOT NULL,
    recipient    TEXT NOT NULL,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'Queued',
    dedupe_key   TEXT,
    queued_at    TEXT DEFAULT (datetime('now')),
    sent_at      TEXT,
    detail       TEXT
);

CREATE INDEX IF NOT EXISTS idx_cal_notif_state
    ON calendar_notifications(state);
CREATE INDEX IF NOT EXISTS idx_cal_notif_event
    ON calendar_notifications(event_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cal_notif_dedupe
    ON calendar_notifications(dedupe_key)
    WHERE dedupe_key IS NOT NULL;
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Notification:
    notification_id: int
    event_id: int | None
    kind: str
    recipient: str
    subject: str
    body: str
    state: str
    dedupe_key: str | None
    queued_at: str | None
    sent_at: str | None
    detail: str | None

    @property
    def is_broadcast(self) -> bool:
        return self.recipient.startswith("audience:")

    @property
    def label(self) -> str:
        return f"[{self.kind}] → {self.recipient}: {self.subject}"


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Calendar notification schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Notification:
    return Notification(
        notification_id=r["notification_id"], event_id=r["event_id"],
        kind=r["kind"], recipient=r["recipient"],
        subject=r["subject"], body=r["body"], state=r["state"],
        dedupe_key=r["dedupe_key"], queued_at=r["queued_at"],
        sent_at=r["sent_at"], detail=r["detail"])


# ── Queueing primitives ─────────────────────────────────────────────

def _when_line(event: core.Event) -> str:
    when = (event.start_date if not event.is_multiday
            else f"{event.start_date} → {event.end_date}")
    return f"{when}, {event.time_label}"


def queue(event_id: int | None, kind: str, recipient: str,
          subject: str, body: str, *,
          dedupe_key: str | None = None) -> Notification | None:
    """Put one message on the queue. A duplicate dedupe key is a
    quiet no-op — that is the whole point of the key."""
    if kind not in KINDS:
        raise ValidationError(f"Kind must be one of: {', '.join(KINDS)}")
    who = (recipient or "").strip()
    if not who:
        raise ValidationError("Recipient is required")
    init_db()
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO calendar_notifications
                       (event_id, kind, recipient, subject, body,
                        dedupe_key)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_id, kind, who, subject.strip(), body,
                 dedupe_key))
            conn.commit()
        except sqlite3.IntegrityError:
            return None
        new_id = cur.lastrowid
    out = get_notification(new_id)
    assert out is not None
    return out


# ── Reminders ───────────────────────────────────────────────────────

def sweep_reminders(*, today: str | None = None) -> int:
    """Queue a reminder for every scheduled event whose lead day is
    today or has slipped past unqueued. Safe daily; idempotent by
    (event, kind) dedupe key."""
    init_db()
    now = (core._validate_date(today, "today") if today
           else _dt.date.today().isoformat())
    horizon = (_dt.date.fromisoformat(now)
               + _dt.timedelta(days=max(
                   REMINDER_LEAD_DAYS.values()) + 1)).isoformat()
    queued = 0
    for event in core.list_events(status="Scheduled", date_from=now,
                                  date_to=horizon,
                                  overlapping=False):
        lead = REMINDER_LEAD_DAYS.get(event.event_type,
                                      DEFAULT_REMINDER_LEAD)
        send_on = (_dt.date.fromisoformat(event.start_date)
                   - _dt.timedelta(days=lead)).isoformat()
        if send_on > now:
            continue
        recipient = f"audience:{event.audience}"
        subject = f"Reminder: {event.title} — {event.start_date}"
        lines = [
            f"{event.title}",
            f"When:  {_when_line(event)}",
        ]
        if event.location:
            lines.append(f"Where: {event.location}")
        if event.organiser:
            lines.append(f"Organiser: {event.organiser}")
        if event.rsvp_required:
            lines.append("")
            lines.append("This event needs an RSVP — please book "
                         "your place if you have not already.")
        got = queue(event.event_id, REMINDER, recipient, subject,
                    "\n".join(lines),
                    dedupe_key=f"reminder:{event.event_id}")
        if got is not None:
            queued += 1
    if queued:
        logger.info("Reminder sweep queued %d message(s)", queued)
    return queued


# ── Change and cancellation ─────────────────────────────────────────

def notify_change(before: core.Event, after: core.Event, *,
                  reason: str | None = None) -> Notification | None:
    """Tell the audience what actually moved. Nothing notifiable
    moved → nothing queued."""
    changes = []
    for field in NOTIFIABLE_FIELDS:
        old, new = getattr(before, field), getattr(after, field)
        if old != new:
            changes.append(
                f"  {_FIELD_LABELS[field].capitalize()}: "
                f"{old or '—'} → {new or '—'}")
    if not changes:
        return None
    if after.status == "Cancelled" and before.status != "Cancelled":
        return notify_cancellation(after, reason=reason)
    lines = [f"{after.title} has changed:", "", *changes, "",
             f"It now runs: {_when_line(after)}"]
    if reason:
        lines.append(f"Reason: {reason}")
    return queue(
        after.event_id, CHANGE_NOTICE, f"audience:{after.audience}",
        f"Changed: {after.title}", "\n".join(lines))


def notify_cancellation(event: core.Event, *,
                        reason: str | None = None) -> Notification | None:
    lines = [f"{event.title} on {event.start_date} has been "
             "cancelled."]
    if reason:
        lines.append(f"Reason: {reason}")
    lines.append("")
    lines.append("Please pass this on to anyone you know was "
                 "planning to attend.")
    return queue(
        event.event_id, CANCELLATION, f"audience:{event.audience}",
        f"Cancelled: {event.title} ({event.start_date})",
        "\n".join(lines),
        dedupe_key=f"cancel:{event.event_id}")


# ── RSVP ────────────────────────────────────────────────────────────

def queue_rsvp_request(event_id: int) -> Notification | None:
    """Ask the audience to book. Only meaningful for events that
    said they wanted RSVPs."""
    event = core.get_event(event_id)
    if event is None or event.is_deleted:
        raise ValidationError(f"No event #{event_id}")
    if not event.rsvp_required:
        raise ValidationError(
            f"Event #{event_id} does not take RSVPs")
    cap = (f"Places are limited to {event.capacity}."
           if event.capacity else "")
    body = "\n".join(filter(None, [
        f"You are invited to: {event.title}",
        f"When:  {_when_line(event)}",
        f"Where: {event.location}" if event.location else None,
        "",
        "Please book your place. " + cap,
    ]))
    return queue(event_id, RSVP_REQUEST,
                 f"audience:{event.audience}",
                 f"RSVP: {event.title}", body,
                 dedupe_key=f"rsvp-request:{event_id}")


def queue_rsvp_confirmation(event_id: int, recipient: str, *,
                            waitlisted: bool = False) -> Notification | None:
    """One person's booking confirmed (or queued). Called by the
    booking flow with wherever the reply should go."""
    event = core.get_event(event_id)
    if event is None:
        raise ValidationError(f"No event #{event_id}")
    if waitlisted:
        subject = f"Waitlisted: {event.title}"
        body = (f"The event is currently full, so you are on the "
                f"waiting list for {event.title} "
                f"({_when_line(event)}).\n\nIf a place opens up it "
                "is yours automatically and we will tell you.")
    else:
        subject = f"Booked: {event.title}"
        body = (f"Your place is confirmed for {event.title}.\n"
                f"When:  {_when_line(event)}"
                + (f"\nWhere: {event.location}" if event.location
                   else ""))
    return queue(event_id, RSVP_CONFIRMATION, recipient, subject,
                 body)


# ── Week ahead ──────────────────────────────────────────────────────

def queue_week_ahead(*, monday: str | None = None) -> int:
    """One digest per audience with anything on: the week's events,
    day by day. Idempotent per (audience, week)."""
    init_db()
    if monday:
        anchor = _dt.date.fromisoformat(
            core._validate_date(monday, "monday"))
        anchor -= _dt.timedelta(days=anchor.weekday())
    else:
        today = _dt.date.today()
        anchor = today - _dt.timedelta(days=today.weekday())
    week_from = anchor.isoformat()
    week_to = (anchor + _dt.timedelta(days=6)).isoformat()

    by_audience: dict[str, list[core.Event]] = {}
    for event in core.list_events(date_from=week_from,
                                  date_to=week_to,
                                  status="Scheduled"):
        by_audience.setdefault(event.audience, []).append(event)

    queued = 0
    for audience, events in sorted(by_audience.items()):
        lines = [f"Week beginning {week_from} — "
                 f"{len(events)} event(s):", ""]
        day = None
        for e in sorted(events,
                        key=lambda x: (x.start_date,
                                       x.start_time or "99")):
            if e.start_date != day:
                day = e.start_date
                weekday = _dt.date.fromisoformat(day).strftime("%A")
                lines.append(f"{weekday} {day}")
            where = f" @ {e.location}" if e.location else ""
            lines.append(f"  {e.time_label:<12} {e.title}{where}")
        got = queue(
            None, DIGEST, f"audience:{audience}",
            f"Week ahead ({week_from}) — {audience}",
            "\n".join(lines),
            dedupe_key=f"digest:{audience}:{week_from}")
        if got is not None:
            queued += 1
    return queued


# ── The queue itself ────────────────────────────────────────────────

def get_notification(notification_id: int) -> Notification | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM calendar_notifications "
            "WHERE notification_id = ?", (notification_id,)).fetchone()
    return _row(r) if r else None


def list_notifications(*, state: str | None = None,
                       kind: str | None = None,
                       event_id: int | None = None,
                       limit: int = 500) -> list[Notification]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if state:
        if state not in STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if kind:
        if kind not in KINDS:
            raise ValidationError(
                f"Kind must be one of: {', '.join(KINDS)}")
        clauses.append("kind = ?")
        args.append(kind)
    if event_id is not None:
        clauses.append("event_id = ?")
        args.append(event_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM calendar_notifications {where} "
            "ORDER BY queued_at DESC, notification_id DESC LIMIT ?",
            args).fetchall()
    return [_row(r) for r in rows]


def cancel_notification(notification_id: int) -> bool:
    """Pull a queued message before it goes."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE calendar_notifications SET state = ? "
            "WHERE notification_id = ? AND state = ?",
            (CANCELLED, notification_id, QUEUED))
        conn.commit()
    return bool(cur.rowcount)


def _send_email(address: str, subject: str, body: str) -> None:
    from education_system.platform.integrations.email.email_service import (
        EmailService,
    )
    service = EmailService()
    if not service.is_configured():
        raise RuntimeError("Email is not configured on this "
                           "installation")
    service.send_email(to=address, subject=subject, body=body)


def send_queued(*, sender: Callable[[str, str, str], None] | None = None,
                limit: int = 200) -> tuple[int, int]:
    """Drain the queue. Returns (sent, failed).

    Only rows addressed to an actual address go out; broadcast rows
    (``audience:…``) stay queued for whichever surface owns the
    fan-out. ``sender`` is ``(email, subject, body)``; without one
    the college's email service is used, and an unconfigured service
    fails the rows rather than pretending.
    """
    init_db()
    sent = failed = 0
    for n in list_notifications(state=QUEUED, limit=limit):
        if n.is_broadcast:
            continue
        try:
            if sender is not None:
                sender(n.recipient, n.subject, n.body)
            else:
                _send_email(n.recipient, n.subject, n.body)
        except Exception as e:
            failed += 1
            with _connect() as conn:
                conn.execute(
                    "UPDATE calendar_notifications SET state = ?, "
                    "detail = ? WHERE notification_id = ?",
                    (FAILED, str(e)[:300], n.notification_id))
                conn.commit()
            continue
        sent += 1
        with _connect() as conn:
            conn.execute(
                "UPDATE calendar_notifications SET state = ?, "
                "sent_at = datetime('now') WHERE notification_id = ?",
                (SENT, n.notification_id))
            conn.commit()
    if sent or failed:
        logger.info("Notification drain: %d sent, %d failed", sent,
                    failed)
    return sent, failed
