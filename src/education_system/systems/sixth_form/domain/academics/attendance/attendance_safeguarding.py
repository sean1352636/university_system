"""Attendance safeguarding bridge for the Sixth Form System.

Sibling to :mod:`attendance`. Most absence is a cold, a bus, a late
night. A small amount of it is the only outward sign that something is
badly wrong, and the difference between the two is usually just *how
long it has gone on without anybody being able to reach the family*.

That pattern is detectable, and this module detects it:

* **Consecutive unexplained days.** Not a percentage — a run. A learner
  at 94% who has not been seen since Tuesday is a more urgent question
  than one at 78% who is in three days a week, and a percentage cannot
  tell them apart.
* **Nobody reachable.** Unexplained absence plus failed contact
  attempts is the combination that matters. Either alone is ordinary.
* **Children missing education.** Past a longer run with no contact, the
  college has a duty to refer, and :func:`raise_cme_referral` records
  that as a formal act with a date and a name on it.

**This module alerts; it does not decide.** Every output is a flag for
the designated safeguarding lead to look at. It deliberately does not
close its own alerts, does not judge whether an explanation is
plausible, and does not integrate with the pastoral safeguarding record
beyond raising a concern — those are human judgements, and a system that
quietly resolved them would be worse than one that never raised them.
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

CONSECUTIVE_ABSENCE: str = "Consecutive unexplained absence"
NO_CONTACT: str = "Family not contactable"
SEVERE_ABSENCE: str = "Severe absence"
SUDDEN_DROP: str = "Sudden drop in attendance"
CME_RISK: str = "Possible child missing education"
TRIGGERS: tuple[str, ...] = (CONSECUTIVE_ABSENCE, NO_CONTACT, SEVERE_ABSENCE,
                             SUDDEN_DROP, CME_RISK)

# Alert lifecycle. Only a person moves an alert out of Open.
OPEN: str = "Open"
ACKNOWLEDGED: str = "Acknowledged"
ACTIONED: str = "Actioned"
CLOSED: str = "Closed"
ALERT_STATES: tuple[str, ...] = (OPEN, ACKNOWLEDGED, ACTIONED, CLOSED)

LOW: str = "Low"
MEDIUM: str = "Medium"
HIGH: str = "High"
LEVELS: tuple[str, ...] = (HIGH, MEDIUM, LOW)
_LEVEL_RANK: dict[str, int] = {level: i for i, level in enumerate(LEVELS)}

# CME referral lifecycle.
DRAFT: str = "Draft"
SUBMITTED: str = "Submitted"
ACKNOWLEDGED_LA: str = "Acknowledged by LA"
RESOLVED: str = "Resolved"
REFERRAL_STATES: tuple[str, ...] = (DRAFT, SUBMITTED, ACKNOWLEDGED_LA,
                                    RESOLVED)

# A drop of this many percentage points against the previous period is
# worth a look on its own, whatever the absolute figure.
SUDDEN_DROP_POINTS: float = 15.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_safeguarding_alerts (
    alert_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    trigger      TEXT NOT NULL,
    level        TEXT NOT NULL DEFAULT 'Medium',
    state        TEXT NOT NULL DEFAULT 'Open',
    detail       TEXT,
    first_date   TEXT,
    last_date    TEXT,
    days         INTEGER NOT NULL DEFAULT 0,
    raised_on    TEXT NOT NULL,
    raised_by    TEXT,
    assigned_to  TEXT,
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    closed_at    TEXT,
    closed_by    TEXT,
    outcome      TEXT,
    concern_ref  TEXT,
    UNIQUE(student_id, trigger, first_date),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_cme_referrals (
    referral_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    alert_id     INTEGER,
    last_seen    TEXT,
    days_missing INTEGER NOT NULL DEFAULT 0,
    contact_attempts INTEGER NOT NULL DEFAULT 0,
    state        TEXT NOT NULL DEFAULT 'Draft',
    local_authority TEXT,
    reference    TEXT,
    raised_on    TEXT NOT NULL,
    raised_by    TEXT,
    submitted_on TEXT,
    resolved_on  TEXT,
    outcome      TEXT,
    narrative    TEXT,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_sg_alert_state
    ON attendance_safeguarding_alerts(state);
CREATE INDEX IF NOT EXISTS idx_att_sg_alert_student
    ON attendance_safeguarding_alerts(student_id);
CREATE INDEX IF NOT EXISTS idx_att_cme_state
    ON attendance_cme_referrals(state);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Alert:
    """One thing a safeguarding lead should look at."""

    alert_id: int
    student_id: str
    trigger: str
    level: str
    state: str
    detail: str | None
    first_date: str | None
    last_date: str | None
    days: int
    raised_on: str
    raised_by: str | None
    assigned_to: str | None
    acknowledged_at: str | None
    acknowledged_by: str | None
    closed_at: str | None
    closed_by: str | None
    outcome: str | None
    concern_ref: str | None
    student_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.state in (OPEN, ACKNOWLEDGED, ACTIONED)

    @property
    def rank(self) -> int:
        return _LEVEL_RANK.get(self.level, len(LEVELS))

    @property
    def age_days(self) -> int:
        return (_dt.date.today()
                - _dt.date.fromisoformat(self.raised_on)).days

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        return f"[{self.level}] {who} — {self.trigger} ({self.days} day(s))"


@dataclass
class CMEReferral:
    """A formal children-missing-education referral."""

    referral_id: int
    student_id: str
    alert_id: int | None
    last_seen: str | None
    days_missing: int
    contact_attempts: int
    state: str
    local_authority: str | None
    reference: str | None
    raised_on: str
    raised_by: str | None
    submitted_on: str | None
    resolved_on: str | None
    outcome: str | None
    narrative: str | None

    @property
    def is_open(self) -> bool:
        return self.state != RESOLVED


@dataclass
class AbsenceRun:
    """A run of consecutive unexplained absence."""

    student_id: str
    first_date: str
    last_date: str
    days: int
    contact_attempts: int = 0
    contact_made: bool = False
    student_name: str | None = None

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        return (f"{who}: {self.days} day(s) unexplained since "
                f"{self.first_date}"
                + ("" if self.contact_made else ", no contact made"))


@dataclass
class SweepResult:
    checked: int = 0
    raised: int = 0
    existing: int = 0
    alerts: list[Alert] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.checked} learner(s) checked, {self.raised} alert(s) "
                f"raised, {self.existing} already open")


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
    thresholds.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Attendance safeguarding schema ready at %s", DB_PATH)
    _DB_READY = True


def _alert_row(r: sqlite3.Row) -> Alert:
    return Alert(
        alert_id=r["alert_id"], student_id=r["student_id"],
        trigger=r["trigger"], level=r["level"], state=r["state"],
        detail=r["detail"], first_date=r["first_date"],
        last_date=r["last_date"], days=r["days"], raised_on=r["raised_on"],
        raised_by=r["raised_by"], assigned_to=r["assigned_to"],
        acknowledged_at=r["acknowledged_at"],
        acknowledged_by=r["acknowledged_by"], closed_at=r["closed_at"],
        closed_by=r["closed_by"], outcome=r["outcome"],
        concern_ref=r["concern_ref"])


def _referral_row(r: sqlite3.Row) -> CMEReferral:
    return CMEReferral(
        referral_id=r["referral_id"], student_id=r["student_id"],
        alert_id=r["alert_id"], last_seen=r["last_seen"],
        days_missing=r["days_missing"],
        contact_attempts=r["contact_attempts"], state=r["state"],
        local_authority=r["local_authority"], reference=r["reference"],
        raised_on=r["raised_on"], raised_by=r["raised_by"],
        submitted_on=r["submitted_on"], resolved_on=r["resolved_on"],
        outcome=r["outcome"], narrative=r["narrative"])


def validate_trigger(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    for trigger in TRIGGERS:
        if s.lower() == trigger.lower():
            return trigger
    raise ValidationError(f"Trigger must be one of: {', '.join(TRIGGERS)}")


# ── Detection ───────────────────────────────────────────────────────

def _contact_history(student_id: str, *, since: str) -> tuple[int, bool]:
    """Attempts made and whether anybody was actually reached."""
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_calling as _calling,
        )
        calls = _calling.list_calls(student_id=student_id, date_from=since)
        attempts = sum(c.attempts for c in calls)
        made = any(c.outcome in _calling.CONTACT_MADE for c in calls)
        return attempts, made
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Calling lookup unavailable", exc_info=True)
        return 0, False


def absence_run(student_id: str, *, on: str | None = None,
                max_lookback_days: int = 60) -> AbsenceRun | None:
    """The current run of consecutive unexplained absence, if any.

    Counted in teaching days: a Friday absence checked on Monday is one
    day, not three, and a run that spans half term is not a fortnight of
    a learner going missing.
    """
    init_db()
    today = core._validate_date(on or _dt.date.today().isoformat())
    start = (_dt.date.fromisoformat(today)
             - _dt.timedelta(days=max(1, max_lookback_days))).isoformat()
    days = calendar.teaching_days(start, today)
    if not days:
        return None

    marked: dict[str, bool] = {}
    for record in core.list_records(student_id=student_id, date_from=start,
                                    date_to=today):
        if record.voided:
            continue
        unexplained = codes.is_unauthorised_absence(record.code)
        # A single attending mark in a day breaks the run.
        marked[record.date] = marked.get(record.date, True) and unexplained

    run_days: list[str] = []
    for date in reversed(days):
        state = marked.get(date)
        if state is True:
            run_days.append(date)
            continue
        if state is False:
            break
        # No mark at all: not evidence of absence, so it does not extend
        # a run, but it does not break one either — the register was
        # simply never taken.
        if run_days:
            continue
        break

    if not run_days:
        return None
    run_days.sort()
    attempts, made = _contact_history(student_id, since=run_days[0])
    return AbsenceRun(student_id=student_id, first_date=run_days[0],
                      last_date=run_days[-1], days=len(run_days),
                      contact_attempts=attempts, contact_made=made)


def _level_for(days: int, *, contact_made: bool) -> str:
    cme_days = thresholds.value_of(thresholds.CME_REFERRAL_DAYS, default=10.0)
    alert_days = thresholds.value_of(thresholds.UNEXPLAINED_DAYS_ALERT,
                                     default=3.0)
    if cme_days is not None and days >= cme_days and not contact_made:
        return HIGH
    if not contact_made and alert_days is not None and days >= alert_days * 2:
        return HIGH
    if not contact_made:
        return MEDIUM
    return LOW


def sweep(*, on: str | None = None, group_id: int | None = None,
          dry_run: bool = False, raised_by: str | None = None) -> SweepResult:
    """Look for the patterns worth a safeguarding lead's attention.

    Run daily. Raises an alert once per run of absence — a learner who
    has been missing for six days generates one alert that gets more
    serious, not six alerts.
    """
    init_db()
    today = core._validate_date(on or _dt.date.today().isoformat())
    result = SweepResult()

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    wanted: set[str] | None = None
    if group_id is not None:
        from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
            class_groups as _cg,
        )
        wanted = set(_cg.list_members(group_id))

    alert_days = thresholds.value_of(thresholds.UNEXPLAINED_DAYS_ALERT,
                                     default=3.0) or 3.0
    for student in _students.list_students():
        if wanted is not None and student.student_id not in wanted:
            continue
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        result.checked += 1

        run = absence_run(student.student_id, on=today)
        if run is None or run.days < alert_days:
            continue
        level = _level_for(run.days, contact_made=run.contact_made)
        trigger = (CME_RISK if level == HIGH and not run.contact_made
                   else CONSECUTIVE_ABSENCE)
        detail = (f"{run.days} consecutive teaching day(s) unexplained since "
                  f"{run.first_date}; {run.contact_attempts} contact "
                  f"attempt(s), "
                  + ("contact made" if run.contact_made
                     else "nobody reached"))

        existing = _find_alert(student.student_id, trigger, run.first_date)
        if existing is not None:
            if not dry_run:
                _update_alert(existing.alert_id, level=level, days=run.days,
                              last_date=run.last_date, detail=detail)
            result.existing += 1
            continue
        if dry_run:
            result.raised += 1
            continue
        alert = raise_alert(
            student.student_id, trigger, level=level, detail=detail,
            first_date=run.first_date, last_date=run.last_date,
            days=run.days, raised_by=raised_by)
        result.raised += 1
        result.alerts.append(alert)

    logger.warning("Safeguarding sweep: %s", result.summary)
    return result


def _find_alert(student_id: str, trigger: str,
                first_date: str) -> Alert | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_safeguarding_alerts "
            "WHERE student_id = ? AND trigger = ? AND first_date = ?",
            (student_id, trigger, first_date)).fetchone()
    return _alert_row(r) if r else None


def _update_alert(alert_id: int, *, level: str, days: int, last_date: str,
                  detail: str) -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_safeguarding_alerts
                  SET level = ?, days = ?, last_date = ?, detail = ?
                WHERE alert_id = ? AND state != ?""",
            (level, days, last_date, detail, alert_id, CLOSED))
        conn.commit()


# ── Alerts ──────────────────────────────────────────────────────────

def raise_alert(
    student_id: str,
    trigger: str,
    *,
    level: str = MEDIUM,
    detail: str | None = None,
    first_date: str | None = None,
    last_date: str | None = None,
    days: int = 0,
    raised_by: str | None = None,
    assigned_to: str | None = None,
) -> Alert:
    """Raise an alert. Also files a pastoral concern where one can be."""
    init_db()
    trigger = validate_trigger(trigger)
    if level not in LEVELS:
        raise ValidationError(f"Level must be one of: {', '.join(LEVELS)}")
    today = _dt.date.today().isoformat()

    concern_ref = _file_concern(student_id, trigger, detail, level)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_safeguarding_alerts
                   (student_id, trigger, level, state, detail, first_date,
                    last_date, days, raised_on, raised_by, assigned_to,
                    concern_ref)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, trigger, first_date) DO UPDATE SET
                   level = excluded.level, days = excluded.days,
                   last_date = excluded.last_date, detail = excluded.detail""",
            (student_id.strip(), trigger, level, OPEN,
             (detail or "").strip() or None, first_date, last_date, days,
             today, (raised_by or "").strip() or None,
             (assigned_to or "").strip() or _designated_lead(), concern_ref))
        conn.commit()
    out = _find_alert(student_id.strip(), trigger, first_date or "")
    if out is None:
        out = list_alerts(student_id=student_id, limit=1)[0]
    logger.warning("Safeguarding alert: %s", out.label)
    return out


def _designated_lead() -> str | None:
    """Whoever the staff directory says is a DSL."""
    try:
        from education_system.systems.sixth_form.domain.staff import staff as _staff
        for member in _staff.list_staff():
            if getattr(member, "is_dsl", False) and member.is_active:
                return member.full_name
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("DSL lookup unavailable", exc_info=True)
    return None


def _file_concern(student_id: str, trigger: str, detail: str | None,
                  level: str) -> str | None:
    """Mirror the alert into the pastoral safeguarding record.

    Best effort, and deliberately one-way: this module raises, the
    safeguarding team decides. A failure to file is logged rather than
    raised — an attendance sweep must not stop because a pastoral module
    changed shape.
    """
    try:
        from education_system.systems.sixth_form.domain.safeguarding import (
            safeguarding as _safeguarding,
        )
        record = _safeguarding.create_concern({
            "student_id": student_id,
            "category": "Attendance",
            "summary": trigger,
            "details": detail,
            "risk_level": level,
        })
        return str(getattr(record, "concern_id", "") or "") or None
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Could not file a pastoral concern for %s", student_id,
                     exc_info=True)
        return None


def acknowledge(alert_id: int, *, by: str) -> Alert:
    """A safeguarding lead has seen it. Not the same as acting on it."""
    init_db()
    if get_alert(alert_id) is None:
        raise ValidationError(f"No alert with id {alert_id}")
    who = (by or "").strip()
    if not who:
        raise ValidationError("An acknowledgement needs a name")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_safeguarding_alerts
                  SET state = ?, acknowledged_at = datetime('now'),
                      acknowledged_by = ?
                WHERE alert_id = ? AND state = ?""",
            (ACKNOWLEDGED, who, alert_id, OPEN))
        conn.commit()
    out = get_alert(alert_id)
    assert out is not None
    return out


def mark_actioned(alert_id: int, *, by: str, note: str) -> Alert:
    """Something has been done — a visit, a referral, a conversation."""
    init_db()
    if get_alert(alert_id) is None:
        raise ValidationError(f"No alert with id {alert_id}")
    detail = (note or "").strip()
    if not detail:
        raise ValidationError("Say what was done")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_safeguarding_alerts
                  SET state = ?, outcome = ?, acknowledged_by =
                      COALESCE(acknowledged_by, ?)
                WHERE alert_id = ?""",
            (ACTIONED, detail, (by or "").strip() or None, alert_id))
        conn.commit()
    out = get_alert(alert_id)
    assert out is not None
    return out


def close_alert(alert_id: int, *, outcome: str, by: str) -> Alert:
    """Close an alert. Always a person, never the sweep."""
    init_db()
    if get_alert(alert_id) is None:
        raise ValidationError(f"No alert with id {alert_id}")
    note = (outcome or "").strip()
    if not note:
        raise ValidationError("A safeguarding alert needs a stated outcome")
    if not (by or "").strip():
        raise ValidationError("A safeguarding alert must be closed by a named "
                              "person")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_safeguarding_alerts
                  SET state = ?, closed_at = datetime('now'), closed_by = ?,
                      outcome = ?
                WHERE alert_id = ?""",
            (CLOSED, by.strip(), note, alert_id))
        conn.commit()
    out = get_alert(alert_id)
    assert out is not None
    return out


def get_alert(alert_id: int) -> Alert | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_safeguarding_alerts WHERE alert_id = ?",
            (alert_id,)).fetchone()
    return _alert_row(r) if r else None


def list_alerts(*, student_id: str | None = None, state: str | None = None,
                trigger: str | None = None, level: str | None = None,
                open_only: bool = False, limit: int = 200) -> list[Alert]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if open_only:
        clauses.append("state != ?")
        args.append(CLOSED)
    elif state:
        if state not in ALERT_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(ALERT_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if trigger:
        clauses.append("trigger = ?")
        args.append(validate_trigger(trigger))
    if level:
        clauses.append("level = ?")
        args.append(level)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_safeguarding_alerts {where} "
            "ORDER BY alert_id DESC LIMIT ?", args).fetchall()
    return [_alert_row(r) for r in rows]


def open_alerts(*, with_names: bool = True) -> list[Alert]:
    """The list a DSL looks at, most serious first."""
    out = list_alerts(open_only=True, limit=500)
    if with_names and out:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for alert in out:
            alert.student_name = index.get(alert.student_id)
    out.sort(key=lambda a: (a.rank, -a.days))
    return out


def is_flagged(student_id: str) -> bool:
    """Whether this learner has an open safeguarding alert.

    Read by :mod:`attendance_calling` to push them up the call list.
    """
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_safeguarding_alerts "
            "WHERE student_id = ? AND state != ?",
            (student_id.strip(), CLOSED)).fetchone()
    return bool(r["n"])


def unacknowledged(*, hours: int = 24) -> list[Alert]:
    """Alerts nobody has looked at. The list that must never be long."""
    return [a for a in list_alerts(state=OPEN, limit=500)
            if a.age_days * 24 >= hours]


# ── CME referrals ───────────────────────────────────────────────────

def raise_cme_referral(
    student_id: str,
    *,
    alert_id: int | None = None,
    raised_by: str,
    local_authority: str | None = None,
    narrative: str | None = None,
    on: str | None = None,
) -> CMEReferral:
    """Record a children-missing-education referral.

    A formal act with a duty behind it, so it is recorded as a document
    with a date, an author and a narrative — not as a status change on
    an alert.
    """
    init_db()
    if not (raised_by or "").strip():
        raise ValidationError("A CME referral must name who raised it")
    today = core._validate_date(on or _dt.date.today().isoformat())
    run = absence_run(student_id, on=today)
    last_seen = None
    for record in core.list_records(student_id=student_id, date_to=today):
        if codes.counts_as_present(record.code):
            last_seen = record.date
            break

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_cme_referrals
                   (student_id, alert_id, last_seen, days_missing,
                    contact_attempts, state, local_authority, raised_on,
                    raised_by, narrative)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student_id.strip(), alert_id, last_seen,
             run.days if run else 0, run.contact_attempts if run else 0,
             DRAFT, (local_authority or "").strip() or None, today,
             raised_by.strip(), (narrative or "").strip() or None))
        conn.commit()
        referral_id = int(cur.lastrowid or 0)
    logger.warning("CME referral #%d raised for %s", referral_id, student_id)
    out = get_referral(referral_id)
    assert out is not None
    return out


def submit_referral(referral_id: int, *, reference: str | None = None,
                    on: str | None = None) -> CMEReferral:
    """Mark a referral as sent to the local authority."""
    init_db()
    if get_referral(referral_id) is None:
        raise ValidationError(f"No referral with id {referral_id}")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_cme_referrals
                  SET state = ?, submitted_on = ?, reference = COALESCE(?,
                      reference)
                WHERE referral_id = ?""",
            (SUBMITTED, core._validate_date(on or
                                            _dt.date.today().isoformat()),
             (reference or "").strip() or None, referral_id))
        conn.commit()
    out = get_referral(referral_id)
    assert out is not None
    return out


def resolve_referral(referral_id: int, *, outcome: str) -> CMEReferral:
    """Close a referral with what actually happened."""
    init_db()
    if get_referral(referral_id) is None:
        raise ValidationError(f"No referral with id {referral_id}")
    note = (outcome or "").strip()
    if not note:
        raise ValidationError("A referral needs a stated outcome")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_cme_referrals
                  SET state = ?, resolved_on = ?, outcome = ?
                WHERE referral_id = ?""",
            (RESOLVED, _dt.date.today().isoformat(), note, referral_id))
        conn.commit()
    out = get_referral(referral_id)
    assert out is not None
    return out


def get_referral(referral_id: int) -> CMEReferral | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_cme_referrals WHERE referral_id = ?",
            (referral_id,)).fetchone()
    return _referral_row(r) if r else None


def list_referrals(*, state: str | None = None,
                   student_id: str | None = None,
                   limit: int = 100) -> list[CMEReferral]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if state:
        if state not in REFERRAL_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(REFERRAL_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_cme_referrals {where} "
            "ORDER BY referral_id DESC LIMIT ?", args).fetchall()
    return [_referral_row(r) for r in rows]


def referral_candidates(*, on: str | None = None) -> list[AbsenceRun]:
    """Learners whose absence run has reached the referral threshold.

    Presented as a list for a person to work through, never acted on
    automatically. A CME referral is a serious step and the decision
    belongs to somebody who has looked at the case.
    """
    init_db()
    today = core._validate_date(on or _dt.date.today().isoformat())
    cme_days = thresholds.value_of(thresholds.CME_REFERRAL_DAYS,
                                   default=10.0) or 10.0
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    out: list[AbsenceRun] = []
    existing = {r.student_id for r in list_referrals(limit=500)
                if r.is_open}
    for student in _students.list_students():
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        if student.student_id in existing:
            continue
        run = absence_run(student.student_id, on=today)
        if run is None or run.days < cme_days or run.contact_made:
            continue
        run.student_name = student.full_name
        out.append(run)
    out.sort(key=lambda r: -r.days)
    return out
