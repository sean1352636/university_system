"""Staff self-service ("My area") for the Sixth Form System.

Everything about the signed-in member of staff, and only them, gathered
from the modules that own it:

* timetable — the class groups they teach (:mod:`academics.timetable`,
  matched the same way ``access.taught_student_ids`` matches a teacher:
  staff id, name or login);
* absences (:mod:`..staff_absence`);
* appraisals and objectives (:mod:`..appraisals`) — they can add their
  own comments, mark their self-review done and sign the appraisal off;
* CPD records (:mod:`..cpd`) and mandatory-training status
  (:mod:`..mandatory_training`);
* DBS status (:mod:`..dbs_checks`, the latest current check);
* helpdesk tickets they raised or hold (:mod:`operations.helpdesk`);
* directed time, *if* a directed-time module is installed — see
  :func:`my_directed_time`.

The staff record is the one ``access.resolve`` found at sign-in
(``Principal.staff_id``: login → ``staff.username``, then e-mail, then
staff id). A login with no staff record gets a clear message, never
somebody else's data. No function here takes a staff id: there is no way
to ask for another person.

Appraisal sign-off lives in ``appraisal_signoffs`` (the appraisals table
has no sign-off column): who signed, when, their response, and a copy of
their comments at that moment. Once signed, comments are locked.
"""

from __future__ import annotations

import datetime as _dt
import importlib
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

AGREE = "Agree"
AGREE_WITH_COMMENTS = "Agree with comments"
DISAGREE = "Disagree"
SIGNOFF_RESPONSES: tuple[str, ...] = (AGREE, AGREE_WITH_COMMENTS, DISAGREE)

#: Appraisal statuses at which the appraisee can sign off.
SIGNABLE_STATUSES = ("End Year Review", "Completed", "Closed")

#: Where a directed-time module may appear, and the function it exports.
#: The first that imports and has one of the functions is used.
DIRECTED_TIME_MODULES: tuple[str, ...] = (
    "education_system.systems.sixth_form.domain.staff.directed_time."
    "directed_time",
)
DIRECTED_TIME_FUNCTIONS: tuple[str, ...] = ("balance",)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS appraisal_signoffs (
    signoff_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    appraisal_id  INTEGER NOT NULL UNIQUE,
    staff_id      TEXT NOT NULL,
    cycle         TEXT,
    response      TEXT NOT NULL,
    comments      TEXT,
    signed_by     TEXT NOT NULL,
    signed_at     TEXT NOT NULL
);
"""


class ValidationError(ValueError):
    pass


@dataclass
class TimetableEntry:
    day: int
    day_name: str
    period: int
    start_time: str | None
    end_time: str | None
    group_id: int
    group_name: str
    course: str | None
    room: str | None


@dataclass
class SignOff:
    signoff_id: int
    appraisal_id: int
    staff_id: str
    cycle: str | None
    response: str
    comments: str | None
    signed_by: str
    signed_at: str


@dataclass
class DirectedTime:
    available: bool
    message: str
    rows: list[dict[str, Any]]


# ── Plumbing ────────────────────────────────────────────────────────

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
    _DB_READY = True


def me() -> access.Principal:
    """The signed-in principal, refusing logins with no staff record."""
    p = access.current()
    if not p.is_staff:
        raise access.AccessDenied("My area is for staff logins.")
    if not p.staff_id:
        raise ValidationError(
            "Your login is not linked to a staff record, so there is "
            "nothing to show. Ask HR or an administrator to link your "
            "login in the Staff Directory.")
    return p


def my_staff_record() -> Any:
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    s = _staff.get_staff(me().staff_id)
    if s is None:
        raise ValidationError("Your staff record could not be found")
    return s


# ── Timetable ───────────────────────────────────────────────────────

def my_timetable() -> list[TimetableEntry]:
    """Weekly lessons for the groups this person teaches."""
    p = me()
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _crs,
    )
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    seen: dict[int, Any] = {}
    for value in dict.fromkeys(v for v in (p.staff_id, p.staff_name,
                                           p.username) if v):
        for slot in _tt.list_slots(teacher=value):
            seen[slot.slot_id] = slot
    groups: dict[int, Any] = {}
    courses: dict[int, Any] = {}
    out = []
    for slot in sorted(seen.values(), key=lambda s: (s.day, s.period)):
        g = groups.get(slot.group_id) or _cg.get_group(slot.group_id)
        groups[slot.group_id] = g
        c = None
        if g is not None:
            c = courses.get(g.course_id) or _crs.get_course(g.course_id)
            courses[g.course_id] = c
        default = _tt.DEFAULT_PERIOD_TIMES.get(slot.period, (None, None))
        out.append(TimetableEntry(
            slot.day, _tt.day_name(slot.day), slot.period,
            slot.start_time or default[0], slot.end_time or default[1],
            slot.group_id, g.group_name if g else f"Group #{slot.group_id}",
            f"{c.course_code} {c.title}" if c else None,
            slot.room or (g.room if g else None) or (c.room if c else None)))
    return out


# ── Absences, CPD, DBS, tickets ─────────────────────────────────────

def my_absences() -> list[Any]:
    from education_system.systems.sixth_form.domain.staff.staff_absence import (
        staff_absence as _abs,
    )
    return _abs.list_absences(staff_id=me().staff_id)


def my_cpd() -> list[Any]:
    from education_system.systems.sixth_form.domain.staff.cpd import cpd
    return cpd.list_records(staff_id=me().staff_id)


def my_cpd_hours(academic_year_start: str | None = None) -> float:
    """CPD hours completed since 1 September (or the date given)."""
    if academic_year_start is None:
        today = _dt.date.today()
        y = today.year if today.month >= 9 else today.year - 1
        academic_year_start = f"{y}-09-01"
    total = 0.0
    for r in my_cpd():
        when = r.attended_on or r.booked_on
        if r.status in ("Attended", "Completed") and when and \
                when >= academic_year_start:
            total += r.hours_completed or 0
    return round(total, 1)


def my_training() -> list[Any]:
    me()
    from education_system.systems.sixth_form.domain.staff.mandatory_training import (
        mandatory_training as _mt,
    )
    return _mt.my_status()


def my_dbs() -> Any | None:
    from education_system.systems.sixth_form.domain.staff.dbs_checks import (
        dbs_checks as _dbs,
    )
    return _dbs.latest_for_staff(me().staff_id)


def dbs_state(check: Any | None) -> str:
    if check is None:
        return "No DBS check on record — speak to HR"
    if check.is_expired:
        return f"Expired {check.expires_on} — speak to HR"
    if check.update_check_overdue:
        return "Update Service check overdue (HR will run it)"
    if check.expiring_soon:
        return f"Expires {check.expires_on}"
    return check.status


def my_tickets(*, open_only: bool = False) -> list[Any]:
    me()
    from education_system.systems.sixth_form.domains.operations.domain.helpdesk import (
        helpdesk as _hd,
    )
    return _hd.list_tickets(mine=True, open_only=open_only)


# ── Appraisals ──────────────────────────────────────────────────────

def _appraisals():
    from education_system.systems.sixth_form.domain.staff.appraisals import (
        appraisals as _ap,
    )
    return _ap


def my_appraisals() -> list[Any]:
    return _appraisals().list_appraisals(staff_id=me().staff_id)


def _my_appraisal(appraisal_id: int) -> Any:
    p = me()
    a = _appraisals().get_appraisal(int(appraisal_id))
    if a is None or a.staff_id != p.staff_id:
        # Same answer for "not yours" and "does not exist".
        raise ValidationError(f"No appraisal #{appraisal_id} of yours")
    return a


def my_objectives(appraisal_id: int) -> list[Any]:
    a = _my_appraisal(appraisal_id)
    return _appraisals().list_objectives(a.appraisal_id)


def signoff_for(appraisal_id: int) -> SignOff | None:
    _my_appraisal(appraisal_id)
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM appraisal_signoffs WHERE "
                         "appraisal_id=?", (int(appraisal_id),)).fetchone()
    return SignOff(**{k: r[k] for k in SignOff.__dataclass_fields__}) \
        if r else None


def _write_appraisal(a: Any, **changes: Any) -> Any:
    ap = _appraisals()
    data = ap._to_appraisal_dict(a)
    data.update(changes)
    return ap.update_appraisal(a.appraisal_id, data)


def add_my_comments(appraisal_id: int, comments: str) -> Any:
    """Set the appraisee comments on one's own appraisal (until signed)."""
    a = _my_appraisal(appraisal_id)
    text = (comments or "").strip()
    if not text:
        raise ValidationError("Write your comments first")
    if len(text) > 4000:
        raise ValidationError("Comments must be 4000 characters or fewer")
    if signoff_for(a.appraisal_id):
        raise ValidationError("You have signed this appraisal off; ask your "
                              "appraiser to reopen it to change comments")
    if a.status == "Archived":
        raise ValidationError("This appraisal is archived")
    return _write_appraisal(a, appraisee_comments=text)


def mark_self_review_done(appraisal_id: int, done: bool = True) -> Any:
    a = _my_appraisal(appraisal_id)
    if signoff_for(a.appraisal_id):
        raise ValidationError("This appraisal is already signed off")
    return _write_appraisal(a, self_review_completed=bool(done))


def sign_off(appraisal_id: int, response: str,
             comments: str | None = None) -> SignOff:
    """Sign one's own appraisal off once the end-year review is done."""
    p = me()
    a = _my_appraisal(appraisal_id)
    if a.status not in SIGNABLE_STATUSES and not a.end_year_review_on:
        raise ValidationError("You can sign off once the end-of-year review "
                              "has been held")
    resp = next((r for r in SIGNOFF_RESPONSES
                 if r.lower() == (response or "").strip().lower()), None)
    if resp is None:
        raise ValidationError("Response must be one of: "
                              + ", ".join(SIGNOFF_RESPONSES))
    text = (comments or "").strip() or None
    if resp != AGREE and not (text or a.appraisee_comments):
        raise ValidationError("Add your comments when you do not simply "
                              "agree")
    if text:
        a = add_my_comments(a.appraisal_id, text)
    init_db()
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO appraisal_signoffs (appraisal_id, staff_id, "
                "cycle, response, comments, signed_by, signed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (a.appraisal_id, p.staff_id, a.cycle, resp,
                 a.appraisee_comments, p.username or p.staff_id,
                 _dt.datetime.now().isoformat(timespec="seconds")))
        except _sql.IntegrityError:
            raise ValidationError("You have already signed this appraisal "
                                  "off") from None
    logger.info("Appraisal #%d signed off by %s (%s)", a.appraisal_id,
                p.staff_id, resp)
    out = signoff_for(a.appraisal_id)
    assert out is not None
    return out


# ── Directed time (optional) ────────────────────────────────────────

def my_directed_time() -> DirectedTime:
    """Directed-time figures from a directed-time module.

    Looks for a directed-time module at the paths
    in :data:`DIRECTED_TIME_MODULES` exporting a function named in
    :data:`DIRECTED_TIME_FUNCTIONS` that takes a staff id and returns a
    dict or a list of dicts/dataclasses.
    """
    p = me()
    for mod_name in DIRECTED_TIME_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for fn_name in DIRECTED_TIME_FUNCTIONS:
            fn = getattr(mod, fn_name, None)
            if not callable(fn):
                continue
            result = fn(p.staff_id)
            rows = result if isinstance(result, list) else [result]
            return DirectedTime(True, f"From {mod_name}.{fn_name}",
                                [_as_dict(r) for r in rows if r is not None])
    return DirectedTime(False, "Directed time is not available yet — no "
                        "directed-time module is installed.", [])


def _as_dict(r: Any) -> dict[str, Any]:
    if isinstance(r, dict):
        return dict(r)
    if hasattr(r, "__dataclass_fields__"):
        d = {k: getattr(r, k) for k in r.__dataclass_fields__}
        # Computed totals (e.g. a directed-time balance's used/remaining).
        for k in ("used", "remaining", "percent_used"):
            if k not in d and hasattr(type(r), k):
                d[k] = getattr(r, k)
        return d
    return {"value": r}


# ── One-page overview ───────────────────────────────────────────────

def overview() -> dict[str, Any]:
    """Headline figures for the My area front page. Each part is read
    independently so one failing module does not blank the page."""
    s = my_staff_record()
    out: dict[str, Any] = {"staff_id": s.staff_id, "name": s.full_name,
                           "role": s.role, "department": s.department,
                           "line_manager": s.line_manager}

    def part(key: str, fn) -> None:
        try:
            out[key] = fn()
        except Exception as exc:  # noqa: BLE001 - shown, not raised
            logger.warning("My area: %s unavailable: %s", key, exc)
            out[key] = f"unavailable ({exc})"

    part("lessons_per_week", lambda: len(my_timetable()))
    part("absence_days_this_year", _absence_days_this_year)
    part("cpd_hours_this_year", my_cpd_hours)
    part("training", _training_counts)
    part("dbs", lambda: dbs_state(my_dbs()))
    part("open_tickets", lambda: len(my_tickets(open_only=True)))
    part("appraisal", _current_appraisal_line)
    return out


def _absence_days_this_year() -> float:
    today = _dt.date.today()
    start = f"{today.year if today.month >= 9 else today.year - 1}-09-01"
    total = 0.0
    for a in my_absences():
        if a.absence_date >= start and a.status != "Cancelled":
            total += a.days_lost or 0
    return round(total, 1)


def _training_counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for c in my_training():
        if c.required:
            out[c.state] = out.get(c.state, 0) + 1
    return out


def _current_appraisal_line() -> str:
    rows = my_appraisals()
    if not rows:
        return "No appraisal on record"
    a = rows[0]
    so = signoff_for(a.appraisal_id)
    return (f"{a.cycle}: {a.status}"
            + (f" — signed off {so.signed_at[:10]}" if so else ""))
