"""Staff exit interviews for the Sixth Form System.

Beside the HR record (:mod:`.staff_hr`): when a member of staff leaves,
HR records why they are going, where to, how they rated working here and
what they would change. One table, ``staff_exit_interviews``:

* who (staff id with a snapshot of name, job role and department — the
  staff record may be removed later, the interview must still read) and
  their leaving date;
* status Scheduled / Completed / Declined (declining is an answer too);
* the primary reason and any secondary reasons, the destination;
* a 1-5 rating for each feedback area (workload, leadership, line
  management, CPD, pay, work-life balance, culture, resources, student
  behaviour, communication), plus what went well / what to change;
* would they recommend us / come back; interviewer, date and method.

:func:`leavers_without_interview` lists staff who have left (or are
working notice) according to the staff directory or the HR record and
have no interview yet. The reports count reasons and destinations and
average the area ratings, by academic year or department.

Access: ``HR`` only — exit interviews are confidential HR records. They
are never deleted.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

SCHEDULED = "Scheduled"
COMPLETED = "Completed"
DECLINED = "Declined"
STATUSES: tuple[str, ...] = (SCHEDULED, COMPLETED, DECLINED)

REASONS: tuple[str, ...] = (
    "Workload", "Promotion / career progression", "Pay and benefits",
    "Relocation", "Leadership / management", "Work-life balance",
    "Retirement", "End of fixed-term contract", "Health",
    "Family / caring responsibilities", "Student behaviour",
    "Leaving teaching / education", "Redundancy / restructure",
    "Dismissal", "Further study", "Other")

DESTINATIONS: tuple[str, ...] = (
    "Another sixth form / college", "Another school", "Further education",
    "Higher education", "Multi-academy trust / central role",
    "Local authority", "Outside education — private sector",
    "Outside education — public sector", "Self-employed", "Retirement",
    "Career break", "Further study", "Not working", "Unknown", "Other")

FEEDBACK_AREAS: tuple[str, ...] = (
    "Workload", "Leadership & senior team", "Line management",
    "Professional development", "Pay & benefits", "Work-life balance",
    "Culture & colleagues", "Facilities & resources", "Student behaviour",
    "Communication")
RATING_LABELS = {1: "Very poor", 2: "Poor", 3: "Fair", 4: "Good",
                 5: "Very good"}

METHODS: tuple[str, ...] = ("Face to face", "Video call", "Phone",
                            "Written questionnaire")
ANSWERS: tuple[str, ...] = ("Yes", "No", "Unsure")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff_exit_interviews (
    interview_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id          TEXT NOT NULL,
    staff_name        TEXT NOT NULL,
    job_role          TEXT,
    department        TEXT,
    start_date        TEXT,
    leaving_date      TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'Scheduled',
    primary_reason    TEXT,
    other_reasons     TEXT,
    destination       TEXT,
    destination_detail TEXT,
    ratings           TEXT NOT NULL DEFAULT '{}',
    went_well         TEXT,
    could_improve     TEXT,
    would_recommend   TEXT,
    would_return      TEXT,
    interviewer_id    TEXT,
    interviewer_name  TEXT,
    interview_date    TEXT,
    method            TEXT,
    notes             TEXT,
    recorded_by       TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    UNIQUE (staff_id, leaving_date)
);
CREATE INDEX IF NOT EXISTS idx_exit_leaving
    ON staff_exit_interviews(leaving_date);
"""


class ValidationError(ValueError):
    pass


@dataclass
class ExitInterview:
    interview_id: int
    staff_id: str
    staff_name: str
    job_role: str | None
    department: str | None
    start_date: str | None
    leaving_date: str
    status: str
    primary_reason: str | None
    other_reasons: list[str]
    destination: str | None
    destination_detail: str | None
    ratings: dict[str, int]
    went_well: str | None
    could_improve: str | None
    would_recommend: str | None
    would_return: str | None
    interviewer_id: str | None
    interviewer_name: str | None
    interview_date: str | None
    method: str | None
    notes: str | None
    recorded_by: str | None
    created_at: str
    updated_at: str

    @property
    def length_of_service_years(self) -> float | None:
        if not self.start_date:
            return None
        try:
            a = _dt.date.fromisoformat(self.start_date)
            b = _dt.date.fromisoformat(self.leaving_date)
        except ValueError:
            return None
        return round((b - a).days / 365.25, 1)

    @property
    def average_rating(self) -> float | None:
        vals = list(self.ratings.values())
        return round(sum(vals) / len(vals), 1) if vals else None


@dataclass
class Leaver:
    staff_id: str
    staff_name: str
    job_role: str | None
    department: str | None
    leaving_date: str | None
    source: str


@dataclass
class ExitReport:
    interviews: int = 0
    completed: int = 0
    declined: int = 0
    reasons: dict[str, int] = field(default_factory=dict)
    primary_reasons: dict[str, int] = field(default_factory=dict)
    destinations: dict[str, int] = field(default_factory=dict)
    area_averages: dict[str, float] = field(default_factory=dict)
    by_department: dict[str, int] = field(default_factory=dict)
    would_recommend: dict[str, int] = field(default_factory=dict)
    would_return: dict[str, int] = field(default_factory=dict)
    average_service_years: float | None = None


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Exit interview schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: _sql.Row) -> ExitInterview:
    d = {k: r[k] for k in ExitInterview.__dataclass_fields__}
    d["other_reasons"] = [x for x in (r["other_reasons"] or "").split("|")
                          if x]
    try:
        d["ratings"] = {k: int(v) for k, v in
                        json.loads(r["ratings"] or "{}").items()}
    except (ValueError, TypeError, AttributeError):
        d["ratings"] = {}
    return ExitInterview(**d)


# ── Helpers ─────────────────────────────────────────────────────────

def _hr() -> access.Principal:
    p = access.current()
    p.require(access.HR, "staff exit interviews")
    return p


def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _date(v: Any, label: str, *, required: bool = False) -> str | None:
    s = _text(v)
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _opt_choice(v: Any, options: tuple[str, ...], label: str) -> str | None:
    s = _text(v)
    if not s:
        return None
    for o in options:
        if s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def _ratings(v: Any) -> dict[str, int]:
    if not v:
        return {}
    if not isinstance(v, dict):
        raise ValidationError("Ratings must be area → 1-5")
    out: dict[str, int] = {}
    for area, val in v.items():
        if val in (None, ""):
            continue
        name = _opt_choice(area, FEEDBACK_AREAS, "Feedback area")
        try:
            n = int(str(val).strip())
        except ValueError:
            raise ValidationError(f"{area}: rating must be 1-5") from None
        if n not in RATING_LABELS:
            raise ValidationError(f"{area}: rating must be 1-5")
        out[name] = n
    return out


def _staff(staff_id: str):
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff_mod,
    )
    return _staff_mod.get_staff(staff_id)


def _payload(payload: dict[str, Any],
             existing: ExitInterview | None) -> dict[str, Any]:
    def get(k: str) -> Any:
        return payload.get(k, getattr(existing, k) if existing else None)
    status = _opt_choice(get("status"), STATUSES, "Status") or SCHEDULED
    reasons = get("other_reasons") or []
    if isinstance(reasons, str):
        reasons = [x.strip() for x in reasons.split(",")]
    others = []
    for x in reasons:
        r = _opt_choice(x, REASONS, "Other reason")
        if r and r not in others:
            others.append(r)
    primary = _opt_choice(get("primary_reason"), REASONS, "Primary reason")
    if primary in others:
        others.remove(primary)
    ratings = _ratings(get("ratings"))
    interview_date = _date(get("interview_date"), "Interview date")
    if status == COMPLETED:
        if not primary:
            raise ValidationError("A completed interview needs the primary "
                                  "reason for leaving")
        if not interview_date:
            raise ValidationError("A completed interview needs the date it "
                                  "took place")
        if interview_date > _dt.date.today().isoformat():
            raise ValidationError("Interview date cannot be in the future")
    iv_id = _text(get("interviewer_id"))
    iv_name = _text(get("interviewer_name"))
    if iv_id:
        s = _staff(iv_id)
        if s is None:
            raise ValidationError(f"No staff member with id {iv_id} "
                                  "(interviewer)")
        iv_name = s.full_name
    return {
        "leaving_date": _date(get("leaving_date"), "Leaving date",
                              required=True),
        "status": status, "primary_reason": primary,
        "other_reasons": "|".join(others),
        "destination": _opt_choice(get("destination"), DESTINATIONS,
                                   "Destination"),
        "destination_detail": _text(get("destination_detail")),
        "ratings": json.dumps(ratings, sort_keys=True),
        "went_well": _text(get("went_well")),
        "could_improve": _text(get("could_improve")),
        "would_recommend": _opt_choice(get("would_recommend"), ANSWERS,
                                       "Would recommend"),
        "would_return": _opt_choice(get("would_return"), ANSWERS,
                                    "Would return"),
        "interviewer_id": iv_id, "interviewer_name": iv_name,
        "interview_date": interview_date,
        "method": _opt_choice(get("method"), METHODS, "Method"),
        "notes": _text(get("notes")),
    }


_FIELDS = ("leaving_date", "status", "primary_reason", "other_reasons",
           "destination", "destination_detail", "ratings", "went_well",
           "could_improve", "would_recommend", "would_return",
           "interviewer_id", "interviewer_name", "interview_date", "method",
           "notes")


# ── CRUD ────────────────────────────────────────────────────────────

def create_interview(payload: dict[str, Any]) -> ExitInterview:
    """Schedule or record an exit interview for a member of staff."""
    p = _hr()
    init_db()
    sid = _text(payload.get("staff_id"))
    if not sid:
        raise ValidationError("Staff member is required")
    s = _staff(sid)
    if s is None:
        raise ValidationError(f"No staff member with id {sid}")
    if not payload.get("leaving_date") and s.end_date:
        payload = {**payload, "leaving_date": s.end_date}
    d = _payload(payload, None)
    if s.start_date and d["leaving_date"] < s.start_date:
        raise ValidationError("Leaving date is before their start date")
    with _connect() as conn:
        try:
            cur = conn.execute(
                f"INSERT INTO staff_exit_interviews (staff_id, staff_name, "  # DBW001: literal column list
                f"job_role, department, start_date, recorded_by, "
                f"{', '.join(_FIELDS)}) VALUES (?, ?, ?, ?, ?, ?, "
                f"{', '.join('?' * len(_FIELDS))})",
                (s.staff_id, s.full_name, s.role, s.department, s.start_date,
                 p.staff_name or p.username, *[d[k] for k in _FIELDS]))
        except _sql.IntegrityError:
            raise ValidationError(
                f"{s.full_name} already has an exit interview for leaving "
                f"on {d['leaving_date']}") from None
        new_id = cur.lastrowid
    logger.info("Exit interview #%d for %s (%s)", new_id, s.staff_id,
                d["status"])
    return get_interview(new_id)


def update_interview(interview_id: int,
                     payload: dict[str, Any]) -> ExitInterview:
    _hr()
    existing = get_interview(interview_id)
    d = _payload(payload, existing)
    with _connect() as conn:
        try:
            conn.execute(
                "UPDATE staff_exit_interviews SET "
                + ", ".join(f"{k}=?" for k in _FIELDS)  # DBW001: literal column list
                + ", updated_at=datetime('now') WHERE interview_id=?",
                (*[d[k] for k in _FIELDS], existing.interview_id))
        except _sql.IntegrityError:
            raise ValidationError("Another interview already exists for "
                                  "that leaving date") from None
    return get_interview(existing.interview_id)


def get_interview(interview_id: int) -> ExitInterview:
    _hr()
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM staff_exit_interviews WHERE "
                         "interview_id=?", (int(interview_id),)).fetchone()
    if r is None:
        raise ValidationError(f"No exit interview #{interview_id}")
    return _row(r)


def academic_year_bounds(year: str) -> tuple[str, str]:
    """``2025/26`` → (2025-09-01, 2026-08-31)."""
    m = re.match(r"^(\d{4})/(\d{2})$", (year or "").strip())
    if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
        raise ValidationError("Academic year must look like 2025/26")
    start = int(m.group(1))
    return f"{start}-09-01", f"{start + 1}-08-31"


def academic_year_of(d: str) -> str:
    day = _dt.date.fromisoformat(d)
    start = day.year if day.month >= 9 else day.year - 1
    return f"{start}/{(start + 1) % 100:02d}"


def list_interviews(*, status: str | None = None,
                    academic_year: str | None = None,
                    department: str | None = None,
                    reason: str | None = None,
                    staff_id: str | None = None) -> list[ExitInterview]:
    _hr()
    init_db()
    clauses, args = [], []
    if status:
        clauses.append("status = ?")
        args.append(_opt_choice(status, STATUSES, "Status"))
    if academic_year:
        a, b = academic_year_bounds(academic_year)
        clauses.append("leaving_date BETWEEN ? AND ?")
        args += [a, b]
    if department:
        clauses.append("department = ?")
        args.append(department)
    if staff_id:
        clauses.append("staff_id = ?")
        args.append(staff_id.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = [_row(r) for r in conn.execute(
            f"SELECT * FROM staff_exit_interviews{where} "  # DBW001: literal clauses
            "ORDER BY leaving_date DESC, interview_id DESC", args).fetchall()]
    if reason:
        rows = [r for r in rows
                if reason in ([r.primary_reason] + r.other_reasons)]
    return rows


# ── Leavers and reports ─────────────────────────────────────────────

def leavers(*, since: str | None = None) -> list[Leaver]:
    """Staff who have left or are working notice, from the staff directory
    (status Left) and the HR record (Left / Notice)."""
    _hr()
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff_mod,
    )
    from education_system.systems.sixth_form.domain.staff.staff_hr import (
        staff_hr as _hrmod,
    )
    out: dict[str, Leaver] = {}
    for s in _staff_mod.list_staff(employment_status="Left"):
        out[s.staff_id] = Leaver(s.staff_id, s.full_name, s.role,
                                 s.department, s.end_date, "Staff directory")
    for status in ("Left", "Notice"):
        for r in _hrmod.list_records(employment_status=status):
            if r.staff_id in out and out[r.staff_id].leaving_date:
                continue
            s = _staff_mod.get_staff(r.staff_id)
            out[r.staff_id] = Leaver(
                r.staff_id, s.full_name if s else r.staff_id,
                s.role if s else None, s.department if s else None,
                r.end_date or r.contract_end,
                "HR record" + (" (working notice)" if status == "Notice"
                               else ""))
    rows = list(out.values())
    if since:
        cut = _date(since, "Since")
        rows = [r for r in rows if (r.leaving_date or "9999") >= cut]
    return sorted(rows, key=lambda r: r.leaving_date or "", reverse=True)


def leavers_without_interview(*, since: str | None = None) -> list[Leaver]:
    done = {i.staff_id for i in list_interviews()}
    return [lv for lv in leavers(since=since) if lv.staff_id not in done]


def report(*, academic_year: str | None = None,
           department: str | None = None) -> ExitReport:
    rows = list_interviews(academic_year=academic_year,
                           department=department)
    out = ExitReport(interviews=len(rows))
    totals: dict[str, list[int]] = {}
    service = []
    for r in rows:
        out.by_department[r.department or "—"] = (
            out.by_department.get(r.department or "—", 0) + 1)
        if r.status == DECLINED:
            out.declined += 1
            continue
        if r.status != COMPLETED:
            continue
        out.completed += 1
        if r.primary_reason:
            out.primary_reasons[r.primary_reason] = (
                out.primary_reasons.get(r.primary_reason, 0) + 1)
        for reason in [r.primary_reason] + r.other_reasons:
            if reason:
                out.reasons[reason] = out.reasons.get(reason, 0) + 1
        if r.destination:
            out.destinations[r.destination] = (
                out.destinations.get(r.destination, 0) + 1)
        for area, n in r.ratings.items():
            totals.setdefault(area, []).append(n)
        for attr, bucket in (("would_recommend", out.would_recommend),
                             ("would_return", out.would_return)):
            v = getattr(r, attr)
            if v:
                bucket[v] = bucket.get(v, 0) + 1
        if r.length_of_service_years is not None:
            service.append(r.length_of_service_years)
    out.area_averages = {a: round(sum(v) / len(v), 2)
                         for a, v in totals.items()}
    if service:
        out.average_service_years = round(sum(service) / len(service), 1)
    for d in ("reasons", "primary_reasons", "destinations"):
        setattr(out, d, dict(sorted(getattr(out, d).items(),
                                    key=lambda kv: -kv[1])))
    return out
