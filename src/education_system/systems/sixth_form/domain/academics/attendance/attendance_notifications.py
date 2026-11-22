"""Attendance notifications for the Sixth Form System.

Sibling to :mod:`attendance`. A college that only tells a family about
attendance when it has become a problem has already lost the argument:
the first a parent hears is a letter about a figure they had no way of
watching. What works is small, regular, unremarkable information.

Two kinds, and the difference is timing:

* **Same-day alerts** — an unexplained absence today. Sent once, per
  learner, per day. Not once per lesson: five texts about five periods
  is how a family learns to ignore the sixth.
* **Weekly statements** — the figure, the direction it moved, and the
  sessions missed, itemised. Dull by design. A statement that only
  arrives when something is wrong is a letter; one that arrives every
  Friday is information.

Everything is *queued*, not sent. This module decides what should go to
whom and holds it; :func:`dispatch_due` hands it to whatever the
platform actually sends with. That split matters: a bug in a report
should never be an incident involving four hundred text messages, and a
queue can be inspected before it goes.

Guardian preferences are respected — a contact who does not receive
communications, or who has no address for the channel, is skipped and
said to have been skipped rather than silently dropped.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_calendar as calendar,
    attendance_codes as codes,
    attendance_thresholds as thresholds,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

ABSENCE_ALERT: str = "Absence alert"
LATE_ALERT: str = "Late alert"
WEEKLY_STATEMENT: str = "Weekly statement"
THRESHOLD_WARNING: str = "Threshold warning"
KINDS: tuple[str, ...] = (ABSENCE_ALERT, LATE_ALERT, WEEKLY_STATEMENT,
                          THRESHOLD_WARNING)

SMS: str = "SMS"
EMAIL: str = "Email"
PORTAL: str = "Portal"
CHANNELS: tuple[str, ...] = (SMS, EMAIL, PORTAL)

# Who it goes to.
GUARDIAN: str = "Guardian"
STUDENT: str = "Student"
AUDIENCES: tuple[str, ...] = (GUARDIAN, STUDENT)

QUEUED: str = "Queued"
SENT: str = "Sent"
FAILED: str = "Failed"
SKIPPED: str = "Skipped"
CANCELLED: str = "Cancelled"
STATES: tuple[str, ...] = (QUEUED, SENT, FAILED, SKIPPED, CANCELLED)

# Don't send the same thing twice in this many hours.
DEDUPE_HOURS: int = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    kind         TEXT NOT NULL,
    audience     TEXT NOT NULL DEFAULT 'Guardian',
    channel      TEXT NOT NULL DEFAULT 'SMS',
    recipient    TEXT,
    recipient_name TEXT,
    subject      TEXT,
    body         TEXT NOT NULL,
    covers_date  TEXT,
    state        TEXT NOT NULL DEFAULT 'Queued',
    queued_at    TEXT DEFAULT (datetime('now')),
    sent_at      TEXT,
    detail       TEXT,
    dedupe_key   TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_notif_state
    ON attendance_notifications(state);
CREATE INDEX IF NOT EXISTS idx_att_notif_student
    ON attendance_notifications(student_id, covers_date);
CREATE INDEX IF NOT EXISTS idx_att_notif_dedupe
    ON attendance_notifications(dedupe_key);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Notification:
    """One message waiting to go, or one that went."""

    notification_id: int
    student_id: str
    kind: str
    audience: str
    channel: str
    recipient: str | None
    recipient_name: str | None
    subject: str | None
    body: str
    covers_date: str | None
    state: str
    queued_at: str | None
    sent_at: str | None
    detail: str | None
    dedupe_key: str | None

    @property
    def is_queued(self) -> bool:
        return self.state == QUEUED

    @property
    def label(self) -> str:
        return (f"{self.kind} → {self.recipient_name or self.recipient or '?'}"
                f" ({self.channel}) [{self.state}]")


@dataclass
class Recipient:
    """Somebody a message can be addressed to."""

    name: str | None
    address: str | None
    channel: str
    audience: str = GUARDIAN

    @property
    def usable(self) -> bool:
        return bool(self.address)


@dataclass
class QueueResult:
    """What a batch run queued."""

    kind: str
    queued: int = 0
    skipped: int = 0
    duplicates: int = 0
    no_recipient: list[str] = field(default_factory=list)
    notifications: list[Notification] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.kind}: {self.queued} queued, {self.skipped} skipped, "
                f"{self.duplicates} already sent, "
                f"{len(self.no_recipient)} with nobody to tell")


@dataclass
class DispatchResult:
    sent: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    codes.init_db()
    thresholds.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Notification schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Notification:
    return Notification(
        notification_id=r["notification_id"], student_id=r["student_id"],
        kind=r["kind"], audience=r["audience"], channel=r["channel"],
        recipient=r["recipient"], recipient_name=r["recipient_name"],
        subject=r["subject"], body=r["body"], covers_date=r["covers_date"],
        state=r["state"], queued_at=r["queued_at"], sent_at=r["sent_at"],
        detail=r["detail"], dedupe_key=r["dedupe_key"])


def validate_channel(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return SMS
    for channel in CHANNELS:
        if s.lower() == channel.lower():
            return channel
    raise ValidationError(f"Channel must be one of: {', '.join(CHANNELS)}")


def validate_kind(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    for kind in KINDS:
        if s.lower() == kind.lower():
            return kind
    raise ValidationError(f"Kind must be one of: {', '.join(KINDS)}")


# ── Working out who to tell ─────────────────────────────────────────

def recipients_for(student_id: str, *, audience: str = GUARDIAN,
                   channel: str = SMS) -> list[Recipient]:
    """Who should get a message about this learner, on this channel.

    Honours the guardian's own preferences: a contact flagged as not
    receiving communications is not a delivery failure, it is a decision
    somebody recorded, and overriding it would be worse than silence.
    """
    channel = validate_channel(channel)
    out: list[Recipient] = []
    if audience == STUDENT:
        try:
            from education_system.systems.sixth_form.domain.learners.students import (  # noqa: E501
                students as _students,
            )
            student = _students.get_student(student_id)
            if student is not None:
                address = (student.email if channel == EMAIL
                           else getattr(student, "phone", None))
                out.append(Recipient(name=student.full_name, address=address,
                                     channel=channel, audience=STUDENT))
        except Exception:                   # pragma: no cover - defensive
            logger.debug("Student lookup failed", exc_info=True)
        return out

    try:
        from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (  # noqa: E501
            parent_contacts as _contacts,
        )
        for contact in _contacts.contacts_for_student(student_id):
            if not contact.receives_communications:
                continue
            if channel == EMAIL:
                address = contact.email
            else:
                address = contact.primary_phone or contact.secondary_phone
            out.append(Recipient(name=contact.full_name, address=address,
                                 channel=channel, audience=GUARDIAN))
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Parent-contact lookup unavailable", exc_info=True)
    return [r for r in out if r.usable] or out


# ── Queueing ────────────────────────────────────────────────────────

def _already_sent(dedupe_key: str) -> bool:
    cutoff = (_dt.datetime.now()
              - _dt.timedelta(hours=DEDUPE_HOURS)).strftime(
                  "%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_notifications "
            "WHERE dedupe_key = ? AND state IN (?, ?) "
            "AND COALESCE(sent_at, queued_at) >= ?",
            (dedupe_key, QUEUED, SENT, cutoff)).fetchone()
    return bool(r["n"])


def queue(
    student_id: str,
    kind: str,
    body: str,
    *,
    recipient: Recipient | None = None,
    subject: str | None = None,
    covers_date: str | None = None,
    dedupe_key: str | None = None,
    channel: str = SMS,
    audience: str = GUARDIAN,
) -> Notification | None:
    """Put one message on the queue. Sends nothing.

    Returns ``None`` when the message is a duplicate of one already
    queued or sent inside the dedupe window — a family should hear about
    Tuesday once.
    """
    init_db()
    kind = validate_kind(kind)
    channel = validate_channel(channel if recipient is None
                               else recipient.channel)
    body = (body or "").strip()
    if not body:
        raise ValidationError("A notification needs a body")
    key = dedupe_key or f"{student_id}:{kind}:{covers_date or ''}:{channel}"
    if _already_sent(key):
        return None

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_notifications
                   (student_id, kind, audience, channel, recipient,
                    recipient_name, subject, body, covers_date, state,
                    dedupe_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student_id.strip(), kind,
             recipient.audience if recipient else audience, channel,
             recipient.address if recipient else None,
             recipient.name if recipient else None,
             (subject or "").strip() or None, body,
             core._validate_date(covers_date) if covers_date else None,
             QUEUED if (recipient is None or recipient.usable) else SKIPPED,
             key))
        conn.commit()
        notification_id = int(cur.lastrowid or 0)
    return get_notification(notification_id)


# ── Same-day absence alerts ─────────────────────────────────────────

def _student_name(student_id: str) -> str:
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        student = _students.get_student(student_id)
        return student.full_name if student else student_id
    except Exception:                       # pragma: no cover - defensive
        return student_id


def absence_alert_body(student_id: str, date: str, *,
                       sessions: int) -> str:
    """The text of a same-day alert. Short, factual, and asks for a reply."""
    name = _student_name(student_id).split(" ")[0]
    plural = "lesson" if sessions == 1 else "lessons"
    return (f"{name} has been marked absent from {sessions} {plural} today "
            f"({date}) and we have no explanation on file. Please reply or "
            f"call the college so we can record the reason.")


def queue_absence_alerts(
    *,
    date: str | None = None,
    channel: str = SMS,
    audience: str = GUARDIAN,
    min_sessions: int = 1,
) -> QueueResult:
    """One alert per learner with unexplained absence today.

    Per learner, not per lesson. The batching is the feature: a family
    that gets five texts about one morning stops reading them.
    """
    init_db()
    date = core._validate_date(date or _dt.date.today().isoformat())
    result = QueueResult(kind=ABSENCE_ALERT)

    counts: dict[str, int] = {}
    for record in core.list_records(date=date):
        if record.voided:
            continue
        if codes.is_unauthorised_absence(record.code):
            counts[record.student_id] = counts.get(record.student_id, 0) + 1

    for student_id, sessions in sorted(counts.items()):
        if sessions < max(1, min_sessions):
            result.skipped += 1
            continue
        if _explained(student_id, date):
            result.skipped += 1
            continue
        people = recipients_for(student_id, audience=audience,
                                channel=channel)
        usable = [p for p in people if p.usable]
        if not usable:
            result.no_recipient.append(student_id)
            continue
        body = absence_alert_body(student_id, date, sessions=sessions)
        for person in usable:
            notification = queue(
                student_id, ABSENCE_ALERT, body, recipient=person,
                subject="Absence today", covers_date=date,
                dedupe_key=f"{student_id}:{ABSENCE_ALERT}:{date}")
            if notification is None:
                result.duplicates += 1
            else:
                result.queued += 1
                result.notifications.append(notification)
    logger.info("Absence alerts for %s: %s", date, result.summary)
    return result


def _explained(student_id: str, date: str) -> bool:
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_absence_reports as _reports,
        )
        return _reports.explained(student_id, date)
    except Exception:                       # pragma: no cover - optional dep
        return False


def queue_late_alerts(*, date: str | None = None,
                      min_minutes: int = 15,
                      channel: str = SMS) -> QueueResult:
    """Alerts for significant lateness, which nobody otherwise hears about."""
    init_db()
    date = core._validate_date(date or _dt.date.today().isoformat())
    result = QueueResult(kind=LATE_ALERT)
    worst: dict[str, int] = {}
    for record in core.list_records(date=date):
        if record.voided or not record.minutes_late:
            continue
        if record.minutes_late >= max(1, min_minutes):
            worst[record.student_id] = max(worst.get(record.student_id, 0),
                                           record.minutes_late)
    for student_id, minutes in sorted(worst.items()):
        people = [p for p in recipients_for(student_id, channel=channel)
                  if p.usable]
        if not people:
            result.no_recipient.append(student_id)
            continue
        name = _student_name(student_id).split(" ")[0]
        body = (f"{name} arrived {minutes} minutes late today ({date}). "
                f"Please help us make sure they start the day on time.")
        for person in people:
            notification = queue(
                student_id, LATE_ALERT, body, recipient=person,
                subject="Late arrival", covers_date=date,
                dedupe_key=f"{student_id}:{LATE_ALERT}:{date}")
            if notification is None:
                result.duplicates += 1
            else:
                result.queued += 1
                result.notifications.append(notification)
    return result


# ── Weekly statements ───────────────────────────────────────────────

def _week_window(date: str) -> tuple[str, str]:
    target = _dt.date.fromisoformat(core._validate_date(date))
    monday = target - _dt.timedelta(days=target.weekday())
    return monday.isoformat(), (monday + _dt.timedelta(days=4)).isoformat()


def statement_body(student_id: str, *, date_from: str,
                   date_to: str) -> str:
    """The weekly statement: the figure, the direction, the detail.

    Deliberately includes the good weeks. A message that only ever
    arrives with bad news trains people to dread it and then to ignore
    it, and the whole value of a weekly statement is that it is boring.
    """
    name = _student_name(student_id).split(" ")[0]
    summary = core.summary_for_student(student_id, date_from=date_from,
                                       date_to=date_to)
    if summary.total == 0:
        return (f"{name} had no timetabled lessons recorded between "
                f"{date_from} and {date_to}.")

    previous_from = (_dt.date.fromisoformat(date_from)
                     - _dt.timedelta(days=7)).isoformat()
    previous_to = (_dt.date.fromisoformat(date_to)
                   - _dt.timedelta(days=7)).isoformat()
    previous = core.summary_for_student(student_id, date_from=previous_from,
                                        date_to=previous_to)

    lines = [f"Attendance for {name}, {date_from} to {date_to}:",
             f"  Attended {summary.attending} of {summary.total} lessons "
             f"({summary.percentage}%)."]
    if summary.late:
        lines.append(f"  Late {summary.late} time(s).")
    if summary.absent:
        lines.append(f"  Unexplained absence: {summary.absent} lesson(s).")
    if summary.authorised:
        lines.append(f"  Authorised absence: {summary.authorised} lesson(s).")

    if previous.percentage is not None and summary.percentage is not None:
        change = round(summary.percentage - previous.percentage, 1)
        if change > 0.5:
            lines.append(f"  That is up {change} points on last week — "
                         "thank you.")
        elif change < -0.5:
            lines.append(f"  That is down {abs(change)} points on last week.")
        else:
            lines.append("  About the same as last week.")

    target = thresholds.value_of(thresholds.TARGET_ATTENDANCE, default=95.0)
    if target is not None and summary.percentage is not None \
            and summary.percentage < target:
        lines.append(f"  The college asks for {target:g}%.")
    return "\n".join(lines)


def queue_weekly_statements(
    *,
    date: str | None = None,
    channel: str = EMAIL,
    audience: str = GUARDIAN,
    group_id: int | None = None,
    also_student: bool = True,
) -> QueueResult:
    """Queue the week's statements for every active learner."""
    init_db()
    date = core._validate_date(date or _dt.date.today().isoformat())
    date_from, date_to = _week_window(date)
    result = QueueResult(kind=WEEKLY_STATEMENT)

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if group_id is not None:
        from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
            class_groups as _cg,
        )
        wanted = set(_cg.list_members(group_id))
    else:
        wanted = None

    for student in _students.list_students():
        if wanted is not None and student.student_id not in wanted:
            continue
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        summary = core.summary_for_student(student.student_id,
                                           date_from=date_from,
                                           date_to=date_to)
        if summary.total == 0:
            result.skipped += 1
            continue
        body = statement_body(student.student_id, date_from=date_from,
                              date_to=date_to)
        people = [p for p in recipients_for(student.student_id,
                                            audience=audience,
                                            channel=channel) if p.usable]
        if also_student:
            people += [p for p in recipients_for(student.student_id,
                                                 audience=STUDENT,
                                                 channel=channel)
                       if p.usable]
        if not people:
            result.no_recipient.append(student.student_id)
            continue
        for person in people:
            notification = queue(
                student.student_id, WEEKLY_STATEMENT, body,
                recipient=person, subject=f"Attendance summary, week of "
                                          f"{date_from}",
                covers_date=date_from,
                dedupe_key=f"{student.student_id}:{WEEKLY_STATEMENT}:"
                           f"{date_from}:{person.audience}")
            if notification is None:
                result.duplicates += 1
            else:
                result.queued += 1
                result.notifications.append(notification)
    logger.info("Weekly statements: %s", result.summary)
    return result


# ── Dispatch ────────────────────────────────────────────────────────

def dispatch_due(*, limit: int = 200, sender=None) -> DispatchResult:
    """Hand queued messages to whatever actually sends them.

    ``sender`` is a callable taking one :class:`Notification`. Without
    one, the platform's email integration is used for email and
    everything else is marked failed with a note — a message that cannot
    be sent should look like a failure, not like a success.
    """
    init_db()
    result = DispatchResult()
    for notification in list_notifications(state=QUEUED, limit=limit):
        try:
            if sender is not None:
                sender(notification)
            elif notification.channel == EMAIL:
                _send_email(notification)
            else:
                raise RuntimeError(
                    f"No sender configured for {notification.channel}")
        except Exception as e:
            _mark(notification.notification_id, FAILED, detail=str(e))
            result.failed += 1
            result.errors.append(f"#{notification.notification_id}: {e}")
            continue
        _mark(notification.notification_id, SENT)
        result.sent += 1
    logger.info("Dispatched %d notification(s), %d failed", result.sent,
                result.failed)
    return result


def _send_email(notification: Notification) -> None:
    """Send through the platform's email integration."""
    from education_system.platform.integrations.email.email_service import (
        EmailService,
    )
    if not notification.recipient:
        raise RuntimeError("No email address on this notification")
    service = EmailService()
    # is_configured is a property; calling it raised 'bool is not callable'.
    if not service.is_configured:
        raise RuntimeError(
            "Email is not configured on this installation — pass a sender")
    service.send_email(
        to=notification.recipient,
        subject=notification.subject or "Attendance",
        body=notification.body)


def _mark(notification_id: int, state: str, *,
          detail: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_notifications
                  SET state = ?, detail = COALESCE(?, detail),
                      sent_at = CASE WHEN ? = 'Sent' THEN datetime('now')
                                     ELSE sent_at END
                WHERE notification_id = ?""",
            (state, detail, state, notification_id))
        conn.commit()


def cancel(notification_id: int, *, reason: str | None = None) -> Notification:
    """Pull a message before it goes."""
    init_db()
    notification = get_notification(notification_id)
    if notification is None:
        raise ValidationError(f"No notification with id {notification_id}")
    if notification.state == SENT:
        raise ValidationError("That message has already gone")
    _mark(notification_id, CANCELLED, detail=reason)
    out = get_notification(notification_id)
    assert out is not None
    return out


def cancel_queued(*, kind: str | None = None,
                  covers_date: str | None = None) -> int:
    """Empty the queue — the batch was built from bad data."""
    init_db()
    cancelled = 0
    for notification in list_notifications(state=QUEUED, limit=5000):
        if kind and notification.kind != kind:
            continue
        if covers_date and notification.covers_date != covers_date:
            continue
        _mark(notification.notification_id, CANCELLED,
              detail="Batch cancelled")
        cancelled += 1
    return cancelled


# ── Reads ───────────────────────────────────────────────────────────

def get_notification(notification_id: int) -> Notification | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_notifications WHERE notification_id = ?",
            (notification_id,)).fetchone()
    return _row(r) if r else None


def list_notifications(*, student_id: str | None = None,
                       kind: str | None = None, state: str | None = None,
                       channel: str | None = None,
                       covers_date: str | None = None,
                       limit: int = 200) -> list[Notification]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if kind:
        clauses.append("kind = ?")
        args.append(validate_kind(kind))
    if state:
        if state not in STATES:
            raise ValidationError(f"State must be one of: {', '.join(STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if channel:
        clauses.append("channel = ?")
        args.append(validate_channel(channel))
    if covers_date:
        clauses.append("covers_date = ?")
        args.append(core._validate_date(covers_date))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_notifications {where} "
            "ORDER BY notification_id LIMIT ?", args).fetchall()
    return [_row(r) for r in rows]


def pending_count() -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_notifications "
            "WHERE state = ?", (QUEUED,)).fetchone()
    return int(r["n"])


def history_for(student_id: str, *, limit: int = 50) -> list[Notification]:
    """What this family has already been told — read before ringing them."""
    return list_notifications(student_id=student_id, limit=limit)


def unreachable_learners() -> list[str]:
    """Learners with nobody the college can actually contact.

    A quiet failure that only shows up here: no usable number, no email,
    no guardian receiving communications. Worth fixing before the next
    thing that needs saying is urgent.
    """
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    out: list[str] = []
    for student in _students.list_students():
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        reachable = any(
            p.usable
            for channel in (SMS, EMAIL)
            for p in recipients_for(student.student_id, channel=channel))
        if not reachable:
            out.append(student.student_id)
    return out
