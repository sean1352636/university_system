"""Attendance Concerns — tracked interventions on top of raw attendance.

The raw `attendance_records` table records who was present/late/absent.
This module sits on top of it and lets staff:

* See an **automatic watchlist** of students whose recent attendance falls
  below configurable thresholds (low attendance %, too many absences,
  too many lates, unauthorised absences).
* Log and track **concerns** (one row per intervention/case), with
  action_taken, status, follow-up date, and assigned-to.

The watchlist is computed on-the-fly from attendance data and isn't
stored.

**Storage.** Concerns are attendance *cases*: they live in
``attendance_cases`` (see :mod:`attendance_escalation`), the same rows
the escalation ladder, contracts and meetings hang off, so a concern
logged here is the case the attendance team escalates. This module keeps
its vocabulary (reason / level / status / follow-up) and maps it onto
the case columns; ``concern_id`` is the case id. The original
``attendance_concerns`` table is still created and left in place; its
rows were copied across once (``legacy_concern_id``) and it is only
touched again to delete a concern that has been deleted here.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_CONCERNS_DB

# Default thresholds (overridable on each call).
DEFAULT_WINDOW_DAYS: int = 28
DEFAULT_MIN_ATTENDANCE_PCT: float = 90.0
DEFAULT_MAX_LATES: int = 5
DEFAULT_MAX_ABSENCES: int = 3
DEFAULT_MAX_UNAUTH: int = 1

CONCERN_LEVELS: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_LEVEL: str = "Medium"

STATUSES: tuple[str, ...] = (
    "Open", "Action Plan", "Letter Sent", "Parents Contacted",
    "Meeting Held", "Resolved", "Escalated", "Closed",
)
DEFAULT_STATUS: str = "Open"
OPEN_STATUSES: tuple[str, ...] = tuple(
    s for s in STATUSES if s not in ("Resolved", "Closed"))

REASONS: tuple[str, ...] = (
    "Low overall attendance", "Persistent lates",
    "Unauthorised absences", "Truancy pattern",
    "Medical / long-term illness", "Family circumstances",
    "Mental health", "Disengagement", "Other",
)
DEFAULT_REASON: str = "Low overall attendance"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_concerns (
    concern_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    raised_date    TEXT NOT NULL,
    reason         TEXT NOT NULL,
    level          TEXT NOT NULL DEFAULT 'Medium',
    status         TEXT NOT NULL DEFAULT 'Open',
    threshold_pct  REAL,
    observed_pct   REAL,
    window_days    INTEGER,
    description    TEXT,
    action_taken   TEXT,
    follow_up_date TEXT,
    assigned_to    TEXT,
    raised_by      TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_acn_student ON attendance_concerns(student_id);
CREATE INDEX IF NOT EXISTS idx_acn_status  ON attendance_concerns(status);
CREATE INDEX IF NOT EXISTS idx_acn_level   ON attendance_concerns(level);
CREATE INDEX IF NOT EXISTS idx_acn_follow  ON attendance_concerns(follow_up_date);
"""


@dataclass
class Concern:
    concern_id: int
    student_id: str
    raised_date: str
    reason: str
    level: str
    status: str
    threshold_pct: float | None
    observed_pct: float | None
    window_days: int | None
    description: str | None
    action_taken: str | None
    follow_up_date: str | None
    assigned_to: str | None
    raised_by: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES


@dataclass
class ConcernRow:
    concern: Concern
    student_name: str


@dataclass
class WatchlistEntry:
    student_id: str
    student_name: str
    total: int
    present: int
    late: int
    absent: int
    authorised: int
    percentage: float | None
    unauth_absent: int
    reasons: list[str] = field(default_factory=list)
    has_open_concern: bool = False
    severity: str = "Low"


@dataclass
class WatchlistThresholds:
    window_days: int = DEFAULT_WINDOW_DAYS
    min_pct: float = DEFAULT_MIN_ATTENDANCE_PCT
    max_lates: int = DEFAULT_MAX_LATES
    max_absences: int = DEFAULT_MAX_ABSENCES
    max_unauth: int = DEFAULT_MAX_UNAUTH


def _cases():
    from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
        attendance_escalation as _esc,
    )
    return _esc


# Ladder rung → the level a case shows in the concern log when it was
# opened on the ladder rather than here.
_STAGE_LEVEL: dict[str, str] = {
    "Tutor conversation": "Low",
    "Tutor meeting": "Medium",
    "Head of year meeting": "High",
    "Formal review": "Critical",
    "External referral": "Critical",
}


# ── DB plumbing ────────────────────────────────────────────────────

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
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    with _connect() as conn:
        # Kept so pre-unification rows stay readable; the case store
        # copies them across on its first use.
        conn.executescript(_SCHEMA)
    _cases().init_db()
    logger.debug("Attendance-concerns schema ready at %s", DB_PATH)

    _DB_READY = True


def _from_case(c: Any) -> Concern:
    """A case in the concern log's shape."""
    esc = _cases()
    status = c.concern_status if c.concern_status in STATUSES else None
    if not c.is_open:
        if status not in ("Resolved", "Closed"):
            status = "Closed"
    elif status is None or status in ("Resolved", "Closed"):
        # Opened (or re-opened) on the ladder: say where it has got to.
        status = ("Escalated" if c.stage_number >= 3
                  else "Action Plan" if c.state == esc.MONITORING
                  else "Open")
    created = c.created_at or c.opened_on
    return Concern(
        concern_id=c.case_id,
        student_id=c.student_id,
        raised_date=c.opened_on,
        reason=c.reason if c.reason in REASONS else "Other",
        level=c.level if c.level in CONCERN_LEVELS else
        _STAGE_LEVEL.get(c.stage, DEFAULT_LEVEL),
        status=status,
        threshold_pct=c.threshold_pct,
        observed_pct=(c.observed_pct if c.observed_pct is not None
                      else c.baseline_pct),
        window_days=c.window_days,
        description=c.summary,
        action_taken=c.action_taken,
        follow_up_date=c.review_on,
        assigned_to=c.owner,
        raised_by=c.opened_by,
        notes=c.notes,
        created_at=created,
        updated_at=c.updated_at or created,
    )


def _case_fields(p: dict[str, Any]) -> dict[str, Any]:
    """This module's validated payload as case columns."""
    return {
        "reason": p["reason"], "level": p["level"],
        "concern_status": p["status"], "threshold_pct": p["threshold_pct"],
        "observed_pct": p["observed_pct"], "window_days": p["window_days"],
        "summary": p["description"], "action_taken": p["action_taken"],
        "review_on": p["follow_up_date"], "owner": p["assigned_to"],
        "opened_by": p["raised_by"], "notes": p["notes"],
    }


def _row_concern(r: sqlite3.Row) -> Concern:
    return Concern(
        concern_id=r["concern_id"], student_id=r["student_id"],
        raised_date=r["raised_date"], reason=r["reason"],
        level=r["level"], status=r["status"],
        threshold_pct=r["threshold_pct"], observed_pct=r["observed_pct"],
        window_days=r["window_days"],
        description=r["description"], action_taken=r["action_taken"],
        follow_up_date=r["follow_up_date"], assigned_to=r["assigned_to"],
        raised_by=r["raised_by"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_pct(value: Any, label: str) -> float | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if not (0.0 <= f <= 100.0):
        raise ValidationError(f"{label} must be between 0 and 100")
    return f


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student ID").strip()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(data.get("student_id"))
    out["raised_date"] = _validate_date(
        data.get("raised_date"), "Raised date", required=True)

    reason = _require(data.get("reason"), "Reason").strip()
    if reason not in REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(REASONS)}")
    out["reason"] = reason

    level = (data.get("level") or DEFAULT_LEVEL).strip()
    if level not in CONCERN_LEVELS:
        raise ValidationError(
            f"Level must be one of: {', '.join(CONCERN_LEVELS)}")
    out["level"] = level

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["threshold_pct"] = _validate_pct(
        data.get("threshold_pct"), "Threshold %")
    out["observed_pct"] = _validate_pct(
        data.get("observed_pct"), "Observed %")

    wd = data.get("window_days")
    if wd in (None, ""):
        out["window_days"] = None
    else:
        try:
            w = int(wd)
        except (TypeError, ValueError):
            raise ValidationError(
                "Window days must be a whole number") from None
        if w <= 0 or w > 365:
            raise ValidationError("Window days must be 1..365")
        out["window_days"] = w

    out["follow_up_date"] = _validate_date(
        data.get("follow_up_date"), "Follow-up date")
    out["description"]  = (data.get("description") or "").strip() or None
    out["action_taken"] = (data.get("action_taken") or "").strip() or None
    out["assigned_to"]  = (data.get("assigned_to") or "").strip() or None
    out["raised_by"]    = (data.get("raised_by") or "").strip() or None
    out["notes"]        = (data.get("notes") or "").strip() or None
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_concern(data: dict[str, Any]) -> Concern:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_concern validation failed: %s", e)
        raise
    esc = _cases()
    fields = _case_fields(p)
    closed = p["status"] in esc.CONCERN_CLOSED_STATUSES
    try:
        new_id = esc.concern_insert(
            p["student_id"], p["raised_date"],
            baseline_pct=p["observed_pct"],
            state=esc.CLOSED if closed else esc.OPEN,
            closed_on=p["raised_date"] if closed else None,
            outcome=(p["action_taken"] or p["status"]) if closed else None,
            **fields)
    except esc.ValidationError as e:
        raise ValidationError(str(e)) from None
    out = get_concern(new_id)
    assert out is not None
    logger.info(
        "Created attendance concern #%d for %s "
        "(reason=%s, level=%s, observed=%s%%)",
        new_id, p["student_id"], p["reason"], p["level"],
        p["observed_pct"],
    )
    return out


def get_concern(concern_id: int) -> Concern | None:
    init_db()
    case = _cases().get_case(concern_id)
    return _from_case(case) if case is not None else None


def get_legacy_concern(old_concern_id: int) -> Concern | None:
    """A concern by its id in the pre-unification table."""
    init_db()
    case = _cases().case_by_legacy_concern(old_concern_id)
    return _from_case(case) if case is not None else None


def list_concerns(
    *,
    student_id: str | None = None,
    status: str | None = None,
    level: str | None = None,
    reason: str | None = None,
    open_only: bool = False,
    assigned_to: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Concern]:
    init_db()
    if status and status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    if level and level not in CONCERN_LEVELS:
        raise ValidationError(
            f"Level must be one of: {', '.join(CONCERN_LEVELS)}")
    if reason and reason not in REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(REASONS)}")
    date_from = _validate_date(date_from, "date_from")
    date_to = _validate_date(date_to, "date_to")
    who = (assigned_to or "").strip().lower()
    # Every case is a concern: the ladder's cases appear here too, so the
    # pastoral team and the attendance team work from one list.
    out: list[Concern] = []
    for case in _cases().list_cases(
            student_id=(student_id or "").strip() or None, limit=100000):
        c = _from_case(case)
        if status and c.status != status:
            continue
        if level and c.level != level:
            continue
        if reason and c.reason != reason:
            continue
        if open_only and c.status not in OPEN_STATUSES:
            continue
        if who and who not in (c.assigned_to or "").lower():
            continue
        if date_from and c.raised_date < date_from:
            continue
        if date_to and c.raised_date > date_to:
            continue
        out.append(c)
    # High/Critical first, then most recent.
    rank = {"Critical": 0, "High": 1, "Medium": 2}
    out.sort(key=lambda c: -c.concern_id)
    out.sort(key=lambda c: c.raised_date, reverse=True)
    out.sort(key=lambda c: rank.get(c.level, 3))
    return out


def list_concerns_with_detail(**kwargs) -> list[ConcernRow]:
    rows = list_concerns(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [ConcernRow(concern=c,
                        student_name=names.get(c.student_id, "(unknown)"))
            for c in rows]


def update_concern(concern_id: int, data: dict[str, Any]) -> Concern:
    init_db()
    existing = get_concern(concern_id)
    if existing is None:
        raise ValidationError(f"No concern with id {concern_id}")
    merged = {
        "student_id":     existing.student_id,
        "raised_date":    data.get("raised_date", existing.raised_date),
        "reason":         data.get("reason", existing.reason),
        "level":          data.get("level", existing.level),
        "status":         data.get("status", existing.status),
        "threshold_pct":  data.get("threshold_pct", existing.threshold_pct),
        "observed_pct":   data.get("observed_pct", existing.observed_pct),
        "window_days":    data.get("window_days", existing.window_days),
        "description":    data.get("description", existing.description),
        "action_taken":   data.get("action_taken", existing.action_taken),
        "follow_up_date": data.get("follow_up_date",
                                     existing.follow_up_date),
        "assigned_to":    data.get("assigned_to", existing.assigned_to),
        "raised_by":      data.get("raised_by", existing.raised_by),
        "notes":          data.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    esc = _cases()
    case = esc.get_case(concern_id)
    fields = _case_fields(p)
    fields["opened_on"] = p["raised_date"]
    closing = p["status"] in esc.CONCERN_CLOSED_STATUSES
    if case is not None and closing and case.is_open:
        import datetime as _dt
        fields.update(state=esc.CLOSED,
                      closed_on=_dt.date.today().isoformat(),
                      closed_by=p["assigned_to"],
                      outcome=p["action_taken"] or p["status"])
    elif case is not None and not closing and not case.is_open \
            and p["status"] != existing.status:
        # Moved back to an open status by a person: re-open the case.
        fields.update(state=esc.OPEN, closed_on=None, closed_by=None,
                      outcome=None)
    try:
        esc.concern_update(concern_id, **fields)
    except esc.ValidationError as e:
        raise ValidationError(str(e)) from None
    out = get_concern(concern_id)
    assert out is not None
    logger.info("Updated attendance concern #%d (status=%s, level=%s)",
                concern_id, out.status, out.level)
    return out


def set_status(concern_id: int, status: str) -> Concern:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_concern(concern_id, {"status": status})


def delete_concern(concern_id: int) -> bool:
    init_db()
    if _cases().delete_case(concern_id):
        logger.info("Deleted attendance concern #%d", concern_id)
        return True
    return False


def concerns_for_student(student_id: str) -> list[Concern]:
    return list_concerns(student_id=student_id)


# ── Watchlist ─────────────────────────────────────────────────────

def _date_window(window_days: int) -> tuple[str, str]:
    import datetime as _dt
    today = _dt.date.today()
    start = today - _dt.timedelta(days=window_days)
    return start.isoformat(), today.isoformat()


def watchlist(
    thresholds: WatchlistThresholds | None = None,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[WatchlistEntry]:
    """Build a watchlist of students who breach any threshold over
    the configured window."""
    init_db()
    t = thresholds or WatchlistThresholds()
    if date_from is None or date_to is None:
        df, dt = _date_window(t.window_days)
        date_from = date_from or df
        date_to   = date_to or dt
    # Imported unconditionally — they used to sit inside the branch
    # above, so an explicit date range raised NameError.
    from education_system.systems.sixth_form.domain.academics.attendance import attendance as _att
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _att.init_db()

    open_by_student: dict[str, bool] = {}
    for c in list_concerns(open_only=True):
        open_by_student[c.student_id] = True

    with _connect() as conn:
        rows = conn.execute(
            """SELECT student_id, status, COUNT(*) AS n
                  FROM attendance_records
                 WHERE date >= ? AND date <= ?
                 GROUP BY student_id, status""",
            (date_from, date_to),
        ).fetchall()

    # In the attendance schema, "Authorised" is its own status value
    # (authorised absence); "Absent" rows are unauthorised absences.
    agg: dict[str, dict[str, int]] = {}
    for r in rows:
        d = agg.setdefault(r["student_id"],
                            {"Present": 0, "Late": 0, "Absent": 0,
                             "Authorised": 0, "unauth": 0})
        d[r["status"]] = d.get(r["status"], 0) + r["n"]
    for sid, d in agg.items():
        d["unauth"] = d["Absent"]

    name_map = {s.student_id: s.full_name
                 for s in _students.list_students()}

    out: list[WatchlistEntry] = []
    for sid, d in agg.items():
        total = d["Present"] + d["Late"] + d["Absent"] + d["Authorised"]
        if total == 0:
            continue
        attending = d["Present"] + d["Late"]
        pct = round(100.0 * attending / total, 1)

        reasons: list[str] = []
        if pct < t.min_pct:
            reasons.append(f"Attendance {pct}% < {t.min_pct}%")
        if d["Late"] > t.max_lates:
            reasons.append(f"{d['Late']} lates (>{t.max_lates})")
        if d["Absent"] > t.max_absences:
            reasons.append(f"{d['Absent']} absences (>{t.max_absences})")
        if d["unauth"] > t.max_unauth:
            reasons.append(f"{d['unauth']} unauth (>{t.max_unauth})")

        if not reasons:
            continue

        # Severity: scale by how far below threshold.
        if pct < t.min_pct - 15 or d["unauth"] >= 3:
            severity = "Critical"
        elif pct < t.min_pct - 5 or d["unauth"] >= 2:
            severity = "High"
        elif pct < t.min_pct:
            severity = "Medium"
        else:
            severity = "Low"

        out.append(WatchlistEntry(
            student_id=sid,
            student_name=name_map.get(sid, "(unknown)"),
            total=total, present=d["Present"], late=d["Late"],
            absent=d["Absent"], authorised=d["Authorised"],
            percentage=pct, unauth_absent=d["unauth"],
            reasons=reasons,
            has_open_concern=open_by_student.get(sid, False),
            severity=severity,
        ))

    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    out.sort(key=lambda e: (sev_order[e.severity],
                              e.percentage if e.percentage is not None else 0))
    return out


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    open_count: int
    by_level: dict[str, int]
    by_status: dict[str, int]
    by_reason: dict[str, int]
    high_critical_open: int
    overdue_follow_ups: int
    upcoming_follow_ups: int
    unassigned_open: int
    watchlist_size: int
    watchlist_without_concern: int


def summary(
    *,
    upcoming_window_days: int = 14,
    thresholds: WatchlistThresholds | None = None,
) -> Summary:
    import datetime as _dt
    init_db()
    today = _dt.date.today().isoformat()
    cutoff = (_dt.date.today() + _dt.timedelta(days=upcoming_window_days)
              ).isoformat()

    rows = list_concerns()
    by_level = {lvl: 0 for lvl in CONCERN_LEVELS}
    by_status = {st: 0 for st in STATUSES}
    by_reason = {r: 0 for r in REASONS}
    open_count = 0
    high_crit = 0
    overdue = 0
    upcoming = 0
    unassigned = 0
    for c in rows:
        by_level[c.level] = by_level.get(c.level, 0) + 1
        by_status[c.status] = by_status.get(c.status, 0) + 1
        by_reason[c.reason] = by_reason.get(c.reason, 0) + 1
        if c.is_open:
            open_count += 1
            if c.level in ("High", "Critical"):
                high_crit += 1
            if not c.assigned_to:
                unassigned += 1
            if c.follow_up_date:
                if c.follow_up_date < today:
                    overdue += 1
                elif c.follow_up_date <= cutoff:
                    upcoming += 1

    wl = watchlist(thresholds)
    wl_without = sum(1 for e in wl if not e.has_open_concern)

    return Summary(
        total=len(rows),
        open_count=open_count,
        by_level=by_level,
        by_status=by_status,
        by_reason=by_reason,
        high_critical_open=high_crit,
        overdue_follow_ups=overdue,
        upcoming_follow_ups=upcoming,
        unassigned_open=unassigned,
        watchlist_size=len(wl),
        watchlist_without_concern=wl_without,
    )
