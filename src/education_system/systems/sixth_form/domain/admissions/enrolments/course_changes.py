"""Course changes (subject swaps) after enrolment.

A learner may swap a subject during the change window — by default the
first 42 days after their enrolment's start date, which is also the
16-19 funding qualifying period. After the cut-off a change needs an
``override_reason`` (kept with the change).

:func:`change_course` changes the learning aim through
:func:`learning_aims.change_aim` (old aim Transferred, new aim opened,
both in ``learning_aim_changes``) and then moves the learner's class
groups: out of the old subject's groups, into the emptiest group for the
new subject that has space — or it reports that none is available.

Settings live in ``enrolment_settings`` (key/value, who changed it and
when) and are shared with the enrolment checks. Changing them needs
``admissions`` or ``students.manage``.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as _enrolments,
)

logger = logging.getLogger(__name__)

ValidationError = _enrolments.ValidationError

#: Setting keys and their defaults.
CHANGE_CUTOFF_DAYS = "course_change_cutoff_days"
TUTOR_GROUP_LIMIT = "tutor_group_size_limit"
VISA_WARNING_DAYS = "visa_warning_days"
DEFAULTS: dict[str, int] = {
    CHANGE_CUTOFF_DAYS: 42,
    TUTOR_GROUP_LIMIT: 25,
    VISA_WARNING_DAYS: 60,
}
_LIMITS: dict[str, tuple[int, int]] = {
    CHANGE_CUTOFF_DAYS: (0, 366),
    TUTOR_GROUP_LIMIT: (1, 200),
    VISA_WARNING_DAYS: (1, 366),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolment_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_by  TEXT,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS enrolment_settings_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT NOT NULL,
    changed_by  TEXT,
    changed_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_READY_PATHS: set[str] = set()


def _init() -> None:
    key = str(_enrolments.DB_PATH)
    if key in _READY_PATHS:
        return
    _enrolments.init_db()
    conn = _enrolments._connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    _READY_PATHS.add(key)


@contextlib.contextmanager
def _db() -> Iterator[Any]:
    _init()
    conn = _enrolments._connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ── Settings ────────────────────────────────────────────────────────

def get_setting(key: str) -> int:
    """A numeric enrolment setting (the default when never set)."""
    if key not in DEFAULTS:
        raise ValidationError(f"Unknown enrolment setting {key!r}")
    with _db() as conn:
        r = conn.execute("SELECT value FROM enrolment_settings WHERE key = ?",
                         (key,)).fetchone()
    if r is None:
        return DEFAULTS[key]
    try:
        return int(r["value"])
    except (TypeError, ValueError):
        return DEFAULTS[key]


def settings() -> dict[str, int]:
    return {k: get_setting(k) for k in DEFAULTS}


def set_setting(key: str, value: Any) -> int:
    """Change a setting (``admissions`` or ``students.manage``)."""
    _enrolments._require_writer("changing enrolment settings")
    if key not in DEFAULTS:
        raise ValidationError(f"Unknown enrolment setting {key!r}")
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError("The setting must be a whole number") from None
    lo, hi = _LIMITS[key]
    if not lo <= n <= hi:
        raise ValidationError(f"The setting must be between {lo} and {hi}")
    old = get_setting(key)
    with _db() as conn:
        conn.execute(
            "INSERT INTO enrolment_settings (key, value, updated_by) "
            "VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, updated_by = excluded.updated_by, "
            "updated_at = datetime('now')",
            (key, str(n), _enrolments._actor()))
        conn.execute(
            "INSERT INTO enrolment_settings_history (key, old_value, "
            "new_value, changed_by) VALUES (?, ?, ?, ?)",
            (key, str(old), str(n), _enrolments._actor()))
    logger.info("Enrolment setting %s: %s -> %s", key, old, n)
    return n


def settings_history(limit: int = 100) -> list[dict[str, Any]]:
    with _db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM enrolment_settings_history ORDER BY id DESC "
            "LIMIT ?", (limit,)).fetchall()]


# ── The change window ───────────────────────────────────────────────

@dataclass
class ChangeWindow:
    enrolment_id: int
    starts: str
    cutoff: str             # last day a change is allowed without override
    is_open: bool
    days_left: int          # 0 once closed

    def __str__(self) -> str:
        if self.is_open:
            return (f"Open until {self.cutoff} ({self.days_left} day(s) "
                    "left)")
        return f"Closed on {self.cutoff} — a change needs an override reason"


def _enrolment(enrolment_id: int) -> _enrolments.Enrolment:
    e = _enrolments.get_enrolment(int(enrolment_id))
    if e is None:
        raise ValidationError(f"No enrolment #{enrolment_id}")
    return e


def _window_start(e: _enrolments.Enrolment) -> str:
    if e.start_date:
        return e.start_date
    return _enrolments.academic_year_dates(e.academic_year)[0]


def change_window(enrolment_id: int, *, today: str | None = None
                  ) -> ChangeWindow:
    """Whether the course-change window is open for an enrolment."""
    e = _enrolment(enrolment_id)
    start = _dt.date.fromisoformat(_window_start(e))
    cutoff = start + _dt.timedelta(days=get_setting(CHANGE_CUTOFF_DAYS))
    now = _dt.date.fromisoformat(today) if today else _dt.date.today()
    left = (cutoff - now).days + 1
    return ChangeWindow(enrolment_id=e.enrolment_id, starts=start.isoformat(),
                        cutoff=cutoff.isoformat(), is_open=left > 0,
                        days_left=max(0, left))


# ── Class groups for a subject ──────────────────────────────────────

def subject_courses(subject: str, academic_year: str, year_group: int,
                    qualification_type: str | None = None) -> list[Any]:
    """Live courses teaching *subject* to the year group in that year;
    those of the right qualification type first."""
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _courses,
    )
    found = _courses.list_courses(subject=subject, academic_year=academic_year,
                                  year_group=int(year_group))
    if qualification_type:
        found.sort(key=lambda c: _courses.effective_qualification_type(c)
                   != qualification_type)
    return found


def subject_groups(student_id: str, subject: str) -> list[Any]:
    """The learner's current class groups on courses for *subject*."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _courses,
    )
    out = []
    for g in _cg.groups_for_student(student_id):
        c = _courses.get_course(g.course_id)
        if c is not None and c.subject == subject:
            out.append(g)
    return out


def place_in_subject(student_id: str, subject: str, academic_year: str,
                     year_group: int, *, qualification_type: str | None = None,
                     reason: str | None = None) -> tuple[Any | None, str]:
    """Put the learner in the emptiest group with space for *subject*.
    Returns (group or None, a line saying what happened)."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_group_allocation as _alloc,
        class_group_membership as _members,
    )
    courses = subject_courses(subject, academic_year, year_group,
                              qualification_type)
    if not courses:
        return None, (f"No {subject} course is set up for Year {year_group} "
                      f"in {academic_year} — place them by hand")
    for c in courses:
        g = _alloc.suggest_group_for_student(c.course_id, student_id)
        if g is None:
            continue
        _members.add_members_bulk(g.group_id, [student_id], atomic=True,
                                  actor=_enrolments._actor(), reason=reason)
        return g, f"Placed in {subject} class group {g.group_name}"
    return None, (f"Every {subject} class group is full (or none exists) — "
                  "add them to a waiting list or a new group")


# ── The change ──────────────────────────────────────────────────────

@dataclass
class CourseChangeResult:
    old_aim_id: int
    new_aim_id: int | None
    from_label: str
    to_label: str
    effective_date: str
    override_used: bool
    qualifying_met: bool | None = None
    lines: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.new_aim_id is not None


def change_course(enrolment_id: int, aim_id: int, new_subject: str,
                  new_qualification_type: str | None = None, *,
                  effective_date: str | None = None, reason: str,
                  approved_by: str,
                  override_reason: str | None = None) -> CourseChangeResult:
    """Swap one of the learner's subjects.

    Refuses (``ValidationError``) after the cut-off unless
    ``override_reason`` is given, for a non-live enrolment, or for an aim
    that is not the learner's or not in this enrolment's year. The aim
    change is all-or-nothing; class-group moves after it are reported in
    ``lines`` / ``problems`` and never undo the aim change.
    """
    _enrolments._require_writer("changing a learner's course")
    e = _enrolment(enrolment_id)
    if not e.is_live:
        raise ValidationError(
            f"Enrolment #{e.enrolment_id} is {e.status}"
            + (" (archived)" if e.is_archived else "")
            + " — course changes are for a live enrolment")
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as _aims,
    )
    aim = _aims.get_aim(int(aim_id))
    if aim is None or aim.student_id != e.student_id:
        raise ValidationError(f"Aim #{aim_id} is not one of "
                              f"{e.student_id}'s learning aims")
    if aim.aim_id not in {a.aim_id for a in
                          _enrolments.aims_for_enrolment(e)}:
        raise ValidationError(f"Aim #{aim_id} ({aim.label}) does not belong "
                              f"to the {e.academic_year} enrolment")
    eff = (effective_date or "").strip() or _dt.date.today().isoformat()
    try:
        _dt.date.fromisoformat(eff)
    except ValueError:
        raise ValidationError("Effective date must be YYYY-MM-DD") from None
    # Judged on the later of the effective date and today, so a change
    # cannot be back-dated into a window that has closed.
    window = change_window(e.enrolment_id,
                           today=max(eff, _dt.date.today().isoformat()))
    override = (override_reason or "").strip() or None
    if not window.is_open and not override:
        raise ValidationError(
            f"The course-change window closed on {window.cutoff} "
            f"({get_setting(CHANGE_CUTOFF_DAYS)} days after "
            f"{window.starts}). Give an override reason to change anyway.")
    why = (reason or "").strip()
    if override and not window.is_open:
        why = f"{why} [after cut-off {window.cutoff}; override: {override}]"
    new_aim, check = _aims.change_aim(
        aim.aim_id, new_subject=new_subject,
        new_qualification_type=new_qualification_type, effective_date=eff,
        reason=why, approved_by=approved_by,
        recorded_by=_enrolments._actor())
    result = CourseChangeResult(
        old_aim_id=aim.aim_id, new_aim_id=new_aim.aim_id,
        from_label=aim.label, to_label=new_aim.label, effective_date=eff,
        override_used=bool(override and not window.is_open),
        qualifying_met=getattr(check, "met", None))
    result.lines.append(f"Learning aim changed: {aim.label} -> "
                        f"{new_aim.label} from {eff}")
    if check is not None and not check.met:
        result.lines.append(f"{aim.label} ended before its funding "
                            f"qualifying period ({check.days_in_learning} of "
                            f"{check.qualifying_days} days)")
    _move_groups(e, aim, new_aim, eff, result)
    _log(e, result, why)
    return result


def _move_groups(e: _enrolments.Enrolment, old: Any, new: Any, eff: str,
                 result: CourseChangeResult) -> None:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_group_membership as _members,
    )
    note = f"Course change {old.label} -> {new.label} from {eff}"
    if old.subject != new.subject:
        try:
            for g in subject_groups(e.student_id, old.subject):
                _members.remove_members_bulk(
                    g.group_id, [e.student_id], actor=_enrolments._actor(),
                    reason=note, action="leave")
                result.lines.append(f"Left {old.subject} class group "
                                    f"{g.group_name}")
        except Exception as exc:  # noqa: BLE001 — reported, aim change kept
            logger.exception("Course change: leaving old groups")
            result.problems.append(f"Could not take them out of their "
                                   f"{old.subject} class group: {exc}")
    try:
        if subject_groups(e.student_id, new.subject):
            result.lines.append(f"Already in a {new.subject} class group")
            return
        group, line = place_in_subject(
            e.student_id, new.subject, e.academic_year, e.year_group,
            qualification_type=new.qualification_type, reason=note)
        (result.lines if group is not None else result.problems).append(line)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Course change: placing in new group")
        result.problems.append(f"Could not place them in a {new.subject} "
                               f"class group: {exc}")


def _log(e: _enrolments.Enrolment, result: CourseChangeResult,
         reason: str) -> None:
    try:
        conn = _enrolments._connect()
        try:
            _enrolments._log(conn, e, "course change",
                             f"{result.from_label} -> {result.to_label} from "
                             f"{result.effective_date}: {reason}")
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — the aim history has it anyway
        logger.exception("Course change not added to enrolment history")


def change_log(academic_year: str | None = None) -> list[dict[str, Any]]:
    """Course changes (``learning_aim_changes`` rows of action
    'Changed'), newest first, optionally for one academic year (by
    effective date)."""
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as _aims,
    )
    first = last = None
    if academic_year:
        first, last = _enrolments.academic_year_dates(academic_year)
    out = []
    for c in _aims.aim_history():
        if c.action != "Changed":
            continue
        if first and not (first <= (c.effective_date or "") <= last):
            continue
        out.append({
            "change_id": c.change_id, "student_id": c.student_id,
            "from": c.from_detail, "to": c.to_detail,
            "effective_date": c.effective_date, "reason": c.reason,
            "approved_by": c.approved_by, "recorded_by": c.recorded_by,
            "recorded_at": c.recorded_at, "old_aim_id": c.aim_id,
            "new_aim_id": c.new_aim_id,
            "qualifying_met": c.qualifying_met,
        })
    return out
