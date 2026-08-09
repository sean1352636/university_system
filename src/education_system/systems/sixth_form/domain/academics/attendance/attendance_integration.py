"""Attendance integration and retention for the Sixth Form System.

Sibling to :mod:`attendance`. The last module in the package, and the
one that deals with attendance data *leaving* it:

* **Webhooks** — other systems want to know when a mark changes. A
  parent portal that only refreshes overnight is a parent portal that
  tells families yesterday's news. Subscriptions are registered here,
  events are queued when things happen, and delivery is attempted with
  backoff and a dead-letter state rather than silently.
* **Payloads** — the shapes a REST layer or an MIS sync returns, defined
  once (:func:`student_payload`, :func:`register_payload`) so the API,
  the portal and any future integration cannot each invent their own
  and drift.
* **Subject access** — :func:`subject_access_export` assembles
  everything this package holds about one learner. A GDPR request has a
  statutory deadline, and "we would have to go through eleven tables by
  hand" is not a defence.
* **Retention** — :func:`purge` deletes attendance data past its
  retention period. Keeping everything forever is not caution, it is a
  breach waiting to be discovered.

**Nothing is sent automatically on import.** Webhook delivery only
happens when :func:`deliver_pending` is called, so a test database
cannot post a term's worth of events at somebody's live endpoint.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

MARK_RECORDED: str = "mark.recorded"
MARK_AMENDED: str = "mark.amended"
REGISTER_SUBMITTED: str = "register.submitted"
ABSENCE_REPORTED: str = "absence.reported"
THRESHOLD_CROSSED: str = "threshold.crossed"
SAFEGUARDING_ALERT: str = "safeguarding.alert"
EVENT_TYPES: tuple[str, ...] = (MARK_RECORDED, MARK_AMENDED,
                                REGISTER_SUBMITTED, ABSENCE_REPORTED,
                                THRESHOLD_CROSSED, SAFEGUARDING_ALERT)

PENDING: str = "Pending"
DELIVERED: str = "Delivered"
FAILED: str = "Failed"
DEAD: str = "Dead"
EVENT_STATES: tuple[str, ...] = (PENDING, DELIVERED, FAILED, DEAD)

# Attempts before an event is parked as dead rather than retried forever.
MAX_ATTEMPTS: int = 5

# Retention, in years. Attendance is education data with a real
# retention period; keeping it indefinitely is a liability.
DEFAULT_RETENTION_YEARS: int = 7

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_webhooks (
    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    url          TEXT NOT NULL,
    secret       TEXT,
    events       TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT DEFAULT (datetime('now')),
    last_success TEXT,
    last_failure TEXT,
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS attendance_webhook_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER,
    event_type   TEXT NOT NULL,
    payload      TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'Pending',
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    delivered_at TEXT,
    FOREIGN KEY (subscription_id)
        REFERENCES attendance_webhooks(subscription_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_webhook_ev_state
    ON attendance_webhook_events(state);
CREATE INDEX IF NOT EXISTS idx_att_webhook_ev_type
    ON attendance_webhook_events(event_type);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Subscription:
    """Somewhere that wants to be told."""

    subscription_id: int
    name: str
    url: str
    secret: str | None
    events: tuple[str, ...]
    active: bool
    created_at: str | None
    last_success: str | None
    last_failure: str | None

    def wants(self, event_type: str) -> bool:
        return self.active and (not self.events or event_type in self.events)

    @property
    def healthy(self) -> bool:
        if self.last_failure is None:
            return True
        if self.last_success is None:
            return False
        return self.last_success >= self.last_failure


@dataclass
class Event:
    """One queued notification."""

    event_id: int
    subscription_id: int | None
    event_type: str
    payload: dict[str, Any]
    state: str
    attempts: int
    last_error: str | None
    created_at: str | None
    delivered_at: str | None

    @property
    def deliverable(self) -> bool:
        return self.state in (PENDING, FAILED) and self.attempts < MAX_ATTEMPTS


@dataclass
class DeliveryResult:
    attempted: int = 0
    delivered: int = 0
    failed: int = 0
    dead: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.attempted} attempted, {self.delivered} delivered, "
                f"{self.failed} failed, {self.dead} dead-lettered")


@dataclass
class PurgeResult:
    cutoff: str
    records: int = 0
    daily_sessions: int = 0
    kiosk_events: int = 0
    notifications: int = 0
    dry_run: bool = False

    @property
    def total(self) -> int:
        return (self.records + self.daily_sessions + self.kiosk_events
                + self.notifications)


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
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Integration schema ready at %s", DB_PATH)
    _DB_READY = True


def _subscription_row(r: sqlite3.Row) -> Subscription:
    return Subscription(
        subscription_id=r["subscription_id"], name=r["name"], url=r["url"],
        secret=r["secret"],
        events=tuple(json.loads(r["events"] or "[]")),
        active=bool(r["active"]), created_at=r["created_at"],
        last_success=r["last_success"], last_failure=r["last_failure"])


def _event_row(r: sqlite3.Row) -> Event:
    return Event(
        event_id=r["event_id"], subscription_id=r["subscription_id"],
        event_type=r["event_type"], payload=json.loads(r["payload"]),
        state=r["state"], attempts=r["attempts"], last_error=r["last_error"],
        created_at=r["created_at"], delivered_at=r["delivered_at"])


def validate_event_type(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if s not in EVENT_TYPES:
        raise ValidationError(
            f"Event type must be one of: {', '.join(EVENT_TYPES)}")
    return s


# ── Payload shapes ──────────────────────────────────────────────────

def mark_payload(record: Any) -> dict[str, Any]:
    """One attendance mark, as anything outside this package sees it.

    Defined once. Every integration reads this shape, so a column added
    here reaches all of them and none of them invent their own name for
    it.
    """
    mark = codes.get_code(record.code)
    return {
        "record_id": record.record_id,
        "student_id": record.student_id,
        "date": record.date,
        "slot_id": record.slot_id,
        "status": record.status,
        "code": record.code,
        "code_label": mark.label if mark else None,
        "meaning": mark.meaning if mark else None,
        "counts_as_present": codes.counts_as_present(record.code),
        "minutes_late": record.minutes_late,
        "arrival_time": record.arrival_time,
        "departure_time": record.departure_time,
        "session": record.session,
        "authorised": record.is_authorised,
        "off_site": record.is_offsite,
        "off_site_location": record.offsite_location,
        "notes": record.notes,
        "source": record.data_source,
        "voided": record.voided,
        "recorded_at": record.recorded_at,
    }


def student_payload(student_id: str, *, date_from: str | None = None,
                    date_to: str | None = None) -> dict[str, Any]:
    """One learner's attendance, for a portal or an API.

    Includes the figure *and* the marks behind it: a portal that shows a
    percentage with no way to see which lessons produced it generates a
    phone call every time somebody disagrees with it.
    """
    core.init_db()
    date_to = core._validate_date(date_to or _dt.date.today().isoformat())
    date_from = core._validate_date(
        date_from or (_dt.date.fromisoformat(date_to)
                      - _dt.timedelta(days=42)).isoformat())
    summary = core.summary_for_student(student_id, date_from=date_from,
                                       date_to=date_to)
    records = core.list_records(student_id=student_id, date_from=date_from,
                                date_to=date_to)
    return {
        "student_id": student_id,
        "window": {"from": date_from, "to": date_to},
        "summary": {
            "sessions": summary.total,
            "attending": summary.attending,
            "present": summary.present,
            "late": summary.late,
            "absent": summary.absent,
            "authorised": summary.authorised,
            "percentage": summary.percentage,
        },
        "marks": [mark_payload(r) for r in records],
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }


def register_payload(slot_id: int, date: str) -> dict[str, Any]:
    """One register, for a teaching app or an MIS pull."""
    core.init_db()
    date = core._validate_date(date)
    entries = core.register_view(slot_id, date)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_register as _reg,
    )
    session = _reg.get_session(slot_id, date)
    return {
        "slot_id": slot_id,
        "date": date,
        "state": session.state if session else "Not started",
        "submitted_at": session.submitted_at if session else None,
        "submitted_by": session.submitted_by if session else None,
        "digest": _reg.register_digest(slot_id, date),
        "entries": [{
            "student_id": e.student_id,
            "full_name": e.full_name,
            "mark": mark_payload(e.record) if e.record else None,
        } for e in entries],
    }


def summary_payload(*, date_from: str, date_to: str,
                    group_id: int | None = None) -> dict[str, Any]:
    """College or group figures, for a dashboard."""
    core.init_db()
    if group_id is not None:
        summary = core.summary_for_group(group_id, date_from=date_from,
                                         date_to=date_to)
    else:
        summary = None
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_cohorts as _cohorts,
    )
    window_days = max(1, (_dt.date.fromisoformat(date_to)
                          - _dt.date.fromisoformat(date_from)).days)
    return {
        "window": {"from": date_from, "to": date_to},
        "group_id": group_id,
        "summary": ({"sessions": summary.total,
                     "attending": summary.attending,
                     "percentage": summary.percentage}
                    if summary else None),
        "cohorts": _cohorts.band_counts(window_days=window_days,
                                        date_to=date_to),
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }


# ── Webhooks ────────────────────────────────────────────────────────

def subscribe(
    name: str,
    url: str,
    *,
    events: list[str] | None = None,
    secret: str | None = None,
) -> Subscription:
    """Register somewhere that wants attendance events.

    ``secret`` signs the payload (:func:`sign`), so a receiver can tell
    a genuine delivery from anything else that has found the endpoint.
    """
    init_db()
    name = (name or "").strip()
    url = (url or "").strip()
    if not name or not url:
        raise ValidationError("A subscription needs a name and a URL")
    if not url.startswith(("http://", "https://")):
        raise ValidationError("Webhook URL must be http(s)")
    wanted = [validate_event_type(e) for e in (events or [])]

    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_webhooks (name, url, secret, events)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET
                   url = excluded.url, secret = excluded.secret,
                   events = excluded.events, active = 1""",
            (name, url, (secret or "").strip() or None,
             json.dumps(wanted)))
        conn.commit()
    out = subscription_by_name(name)
    assert out is not None
    logger.info("Webhook subscription %r registered", name)
    return out


def unsubscribe(subscription_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE attendance_webhooks SET active = 0 "
            "WHERE subscription_id = ?", (subscription_id,))
        conn.commit()
    return bool(cur.rowcount)


def subscription_by_name(name: str) -> Subscription | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_webhooks WHERE name = ?",
            ((name or "").strip(),)).fetchone()
    return _subscription_row(r) if r else None


def list_subscriptions(*, active_only: bool = True) -> list[Subscription]:
    init_db()
    where = "WHERE active = 1" if active_only else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_webhooks {where} ORDER BY name"
        ).fetchall()
    return [_subscription_row(r) for r in rows]


def sign(payload: str, secret: str) -> str:
    """HMAC-SHA256 of the payload, as a receiver should verify it."""
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def emit(event_type: str, payload: dict[str, Any]) -> int:
    """Queue an event for every subscriber that wants it.

    Queues; does not send. Delivery is :func:`deliver_pending`, which is
    what keeps a bulk import from posting ten thousand times.
    """
    init_db()
    event_type = validate_event_type(event_type)
    body = json.dumps({"event": event_type, "data": payload,
                       "emitted_at": _dt.datetime.now().isoformat(
                           timespec="seconds")}, separators=(",", ":"))
    queued = 0
    for subscription in list_subscriptions():
        if not subscription.wants(event_type):
            continue
        with _connect() as conn:
            conn.execute(
                """INSERT INTO attendance_webhook_events
                       (subscription_id, event_type, payload, state)
                   VALUES (?, ?, ?, ?)""",
                (subscription.subscription_id, event_type, body, PENDING))
            conn.commit()
        queued += 1
    return queued


def emit_mark(record: Any, *, amended: bool = False) -> int:
    """Convenience: queue an event for one mark."""
    return emit(MARK_AMENDED if amended else MARK_RECORDED,
                mark_payload(record))


def deliver_pending(*, limit: int = 100, sender=None) -> DeliveryResult:
    """Attempt delivery of queued events.

    ``sender`` takes ``(url, body, headers)``. Without one, nothing is
    posted and every event is reported as failed — deliberately, so an
    installation with no transport configured does not look like one
    that is delivering.
    """
    init_db()
    result = DeliveryResult()
    subscriptions = {s.subscription_id: s
                     for s in list_subscriptions(active_only=False)}

    for event in list_events(state=PENDING, limit=limit) + \
            list_events(state=FAILED, limit=limit):
        if not event.deliverable:
            continue
        subscription = subscriptions.get(event.subscription_id or 0)
        if subscription is None or not subscription.active:
            _mark_event(event.event_id, DEAD,
                        error="Subscription no longer active")
            result.dead += 1
            continue

        result.attempted += 1
        body = json.dumps(event.payload, separators=(",", ":"))
        headers = {"Content-Type": "application/json",
                   "X-Attendance-Event": event.event_type}
        if subscription.secret:
            headers["X-Attendance-Signature"] = sign(body,
                                                     subscription.secret)
        try:
            if sender is None:
                raise RuntimeError(
                    "No webhook sender configured — pass sender=")
            sender(subscription.url, body, headers)
        except Exception as e:
            attempts = event.attempts + 1
            state = DEAD if attempts >= MAX_ATTEMPTS else FAILED
            _mark_event(event.event_id, state, error=str(e),
                        attempts=attempts)
            _touch_subscription(subscription.subscription_id, ok=False)
            if state == DEAD:
                result.dead += 1
            else:
                result.failed += 1
            result.errors.append(f"#{event.event_id}: {e}")
            continue
        _mark_event(event.event_id, DELIVERED, attempts=event.attempts + 1)
        _touch_subscription(subscription.subscription_id, ok=True)
        result.delivered += 1

    logger.info("Webhook delivery: %s", result.summary)
    return result


def _mark_event(event_id: int, state: str, *, error: str | None = None,
                attempts: int | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_webhook_events
                  SET state = ?, last_error = COALESCE(?, last_error),
                      attempts = COALESCE(?, attempts),
                      delivered_at = CASE WHEN ? = 'Delivered'
                                          THEN datetime('now')
                                          ELSE delivered_at END
                WHERE event_id = ?""",
            (state, error, attempts, state, event_id))
        conn.commit()


def _touch_subscription(subscription_id: int | None, *, ok: bool) -> None:
    if subscription_id is None:
        return
    column = "last_success" if ok else "last_failure"
    with _connect() as conn:
        conn.execute(
            f"UPDATE attendance_webhooks SET {column} = datetime('now') "
            "WHERE subscription_id = ?", (subscription_id,))
        conn.commit()


def list_events(*, state: str | None = None, event_type: str | None = None,
                limit: int = 200) -> list[Event]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if state:
        if state not in EVENT_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(EVENT_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if event_type:
        clauses.append("event_type = ?")
        args.append(validate_event_type(event_type))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_webhook_events {where} "
            "ORDER BY event_id LIMIT ?", args).fetchall()
    return [_event_row(r) for r in rows]


def dead_letters() -> list[Event]:
    """Events that gave up. Somebody should look at these."""
    return list_events(state=DEAD, limit=500)


def retry_dead(*, event_id: int | None = None) -> int:
    """Put dead events back in the queue after fixing the endpoint."""
    init_db()
    with _connect() as conn:
        if event_id is not None:
            cur = conn.execute(
                "UPDATE attendance_webhook_events SET state = ?, attempts = 0 "
                "WHERE event_id = ? AND state = ?",
                (PENDING, event_id, DEAD))
        else:
            cur = conn.execute(
                "UPDATE attendance_webhook_events SET state = ?, attempts = 0 "
                "WHERE state = ?", (PENDING, DEAD))
        conn.commit()
    return int(cur.rowcount)


# ── Subject access ──────────────────────────────────────────────────

def subject_access_export(student_id: str) -> dict[str, Any]:
    """Everything this package holds about one learner.

    A subject-access request has a statutory deadline, and the honest
    answer to "what do you hold" has to include the awkward parts — the
    call log, the safeguarding alerts, the letters home — not just the
    percentage. Each source is optional so the export never fails
    because one module is not in use.
    """
    core.init_db()
    export: dict[str, Any] = {
        "student_id": student_id,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "attendance_marks": [mark_payload(r) for r in
                             core.list_records(student_id=student_id,
                                               include_voided=True)],
    }

    def add(key: str, fn) -> None:
        try:
            value = fn()
            if value:
                export[key] = value
        except Exception:                   # pragma: no cover - optional dep
            logger.debug("Subject access: %s unavailable", key, exc_info=True)

    base = "education_system.systems.sixth_form.domain.academics.attendance"

    def _mod(name: str):
        return __import__(f"{base}.{name}", fromlist=[name])

    add("absence_reports",
        lambda: [vars(r) for r in _mod("attendance_absence_reports")
                 .list_reports(student_id=student_id, limit=500)])
    add("leave_requests",
        lambda: [vars(r) for r in _mod("attendance_leave")
                 .list_requests(student_id=student_id, limit=500)])
    add("evidence",
        lambda: [vars(e) for e in _mod("attendance_evidence")
                 .list_evidence(student_id=student_id,
                                include_withdrawn=True)])
    add("appeals",
        lambda: [vars(a) for a in _mod("attendance_appeals")
                 .list_appeals(student_id=student_id, limit=200)])
    add("calls",
        lambda: [vars(c) for c in _mod("attendance_calling")
                 .list_calls(student_id=student_id, limit=500)])
    add("notifications",
        lambda: [vars(n) for n in _mod("attendance_notifications")
                 .list_notifications(student_id=student_id, limit=500)])
    add("letters",
        lambda: [vars(letter) for letter in _mod("attendance_letters")
                 .list_letters(student_id=student_id, limit=100)])
    add("cases",
        lambda: _mod("attendance_escalation").case_file(student_id))
    add("punctuality_triggers",
        lambda: [vars(t) for t in _mod("attendance_punctuality")
                 .list_triggers(student_id=student_id, limit=200)])
    add("safeguarding_alerts",
        lambda: [vars(a) for a in _mod("attendance_safeguarding")
                 .list_alerts(student_id=student_id, limit=200)])
    add("bursary",
        lambda: [vars(p) for p in _mod("attendance_bursary")
                 .list_payments(student_id=student_id, limit=200)])
    add("awards",
        lambda: [vars(a) for a in _mod("attendance_rewards")
                 .list_awards(student_id=student_id, limit=200)])
    return export


def subject_access_json(student_id: str) -> str:
    """The export as JSON, with dataclasses flattened."""
    return json.dumps(subject_access_export(student_id), indent=2,
                      default=str)


def erase_student(student_id: str, *, confirm: str,
                  actor: str) -> dict[str, int]:
    """Erase one learner's attendance data.

    For a right-to-erasure request that the college has decided to
    grant. Requires the student id repeated as ``confirm``, because this
    cannot be undone and a mistyped id would erase the wrong person.
    """
    init_db()
    if confirm != student_id:
        raise ValidationError(
            "Pass the student id again as `confirm` to erase their data")
    if not (actor or "").strip():
        raise ValidationError("An erasure must record who authorised it")

    tables = (
        "attendance_records", "attendance_daily_sessions",
        "attendance_absence_reports", "attendance_leave_requests",
        "attendance_evidence", "attendance_appeals", "attendance_calls",
        "attendance_notifications", "attendance_letters",
        "attendance_cases", "attendance_contracts", "attendance_meetings",
        "attendance_punctuality_triggers",
        "attendance_safeguarding_alerts", "attendance_cme_referrals",
        "attendance_bursary_awards", "attendance_bursary_payments",
        "attendance_bursary_exemptions", "attendance_awards",
        "attendance_kiosk_tokens", "attendance_kiosk_events",
        "attendance_placement_days", "attendance_exam_candidates",
    )
    removed: dict[str, int] = {}
    with _connect() as conn:
        for table in tables:
            try:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE student_id = ?",
                    (student_id,))
                if cur.rowcount:
                    removed[table] = cur.rowcount
            except sqlite3.OperationalError:
                continue        # table not present in this installation
        conn.commit()
    logger.warning("Erased attendance data for %s (%d table(s)) by %s",
                   student_id, len(removed), actor)
    return removed


# ── Retention ───────────────────────────────────────────────────────

def retention_cutoff(*, years: int = DEFAULT_RETENTION_YEARS) -> str:
    """The date before which attendance data should no longer be held."""
    today = _dt.date.today()
    try:
        return today.replace(year=today.year - max(1, years)).isoformat()
    except ValueError:                      # pragma: no cover - 29 February
        return today.replace(year=today.year - max(1, years),
                             day=28).isoformat()


def purge(*, years: int = DEFAULT_RETENTION_YEARS,
          dry_run: bool = True, actor: str | None = None) -> PurgeResult:
    """Delete attendance data past its retention period.

    Defaults to a dry run, because the first time anybody runs this the
    number is always larger than expected and it should be looked at
    before it happens.
    """
    init_db()
    cutoff = retention_cutoff(years=years)
    result = PurgeResult(cutoff=cutoff, dry_run=dry_run)

    targets = (
        ("attendance_records", "date", "records"),
        ("attendance_daily_sessions", "date", "daily_sessions"),
        ("attendance_kiosk_events", "date", "kiosk_events"),
        ("attendance_notifications", "covers_date", "notifications"),
    )
    with _connect() as conn:
        for table, column, attribute in targets:
            try:
                if dry_run:
                    r = conn.execute(
                        f"SELECT COUNT(*) AS n FROM {table} "
                        f"WHERE {column} < ?", (cutoff,)).fetchone()
                    count = int(r["n"])
                else:
                    cur = conn.execute(
                        f"DELETE FROM {table} WHERE {column} < ?", (cutoff,))
                    count = int(cur.rowcount)
                setattr(result, attribute, count)
            except sqlite3.OperationalError:
                continue
        if not dry_run:
            conn.commit()

    logger.info("Retention purge (%s) before %s: %d row(s)",
                "dry run" if dry_run else f"by {actor or '?'}", cutoff,
                result.total)
    return result


def retention_report(*, years: int = DEFAULT_RETENTION_YEARS
                     ) -> dict[str, Any]:
    """What is held beyond the retention period, without deleting it."""
    result = purge(years=years, dry_run=True)
    return {
        "retention_years": years,
        "cutoff": result.cutoff,
        "attendance_marks": result.records,
        "session_marks": result.daily_sessions,
        "kiosk_events": result.kiosk_events,
        "notifications": result.notifications,
        "total": result.total,
        "action": ("Nothing to purge" if result.total == 0
                   else "Run purge(dry_run=False) to delete"),
    }
