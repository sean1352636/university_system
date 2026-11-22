"""Staff timetables built from the class timetable.

Nothing is stored here. A teacher's week is read straight from
``timetable_slots`` → ``class_groups`` → ``courses``: the teacher of a
slot is the group's ``teacher`` or, when that is blank, the course's
``teacher`` (inherited). Both are free text, so they are matched to staff
records with :func:`cover.staff_aliases` — the same rule Cover uses — so
"Mr Smith", "John Smith", ``T1234567`` and the e-mail local part all
resolve to one person.

Provides:

* :func:`staff_timetable` / :func:`staff_grid` — one person's lessons;
* :func:`teaching_loads` — periods and hours a week, non-contact
  periods (pro-rata by FTE from Staff HR) and double-booked cells;
* :func:`free_staff` — who is free at a (day, period), for Cover;
* :func:`unmatched_lessons` — slots whose teacher text matches nobody,
  and slots with no teacher at all.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_TIMETABLE_DB


class ValidationError(ValueError):
    pass


@dataclass
class StaffLesson:
    slot_id: int
    group_id: int
    group_name: str
    course_id: int
    course_code: str
    course_title: str
    subject: str
    day: int
    period: int
    start_time: str | None
    end_time: str | None
    room: str | None
    teacher_text: str | None
    inherited: bool              # teacher comes from the course default

    @property
    def minutes(self) -> int:
        return period_minutes(self.period, self.start_time, self.end_time)

    @property
    def label(self) -> str:
        return f"{self.course_code} {self.group_name}"


@dataclass
class TeachingLoad:
    staff_id: str
    name: str
    role: str
    department: str
    fte_percent: float
    periods: int = 0
    minutes: int = 0
    available_periods: int = 0
    double_booked: list[tuple[int, int]] = field(default_factory=list)
    groups: set[int] = field(default_factory=set)

    @property
    def hours(self) -> float:
        return round(self.minutes / 60, 2)

    @property
    def non_contact_periods(self) -> int:
        return max(0, self.available_periods - self.periods)

    @property
    def contact_ratio(self) -> float | None:
        if not self.available_periods:
            return None
        return round(100 * self.periods / self.available_periods, 1)


@dataclass
class FreeStaff:
    staff_id: str
    name: str
    role: str
    department: str
    lessons_that_day: int
    lessons_this_week: int
    note: str | None = None


# ── Plumbing ─────────────────────────────────────────────────────────

def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _tt():
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _timetable,
    )
    return _timetable


def _init() -> None:
    _tt().init_db()


def _hhmm(s: str | None) -> int | None:
    try:
        h, m = (s or "").split(":")
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def period_minutes(period: int, start: str | None = None,
                   end: str | None = None) -> int:
    """Length of one lesson: the slot's own times, else the default
    times for that period, else 55 minutes."""
    a, b = _hhmm(start), _hhmm(end)
    if a is None or b is None or b <= a:
        da, db = _tt().DEFAULT_PERIOD_TIMES.get(period, ("", ""))
        a, b = _hhmm(da), _hhmm(db)
    if a is None or b is None or b <= a:
        return 55
    return b - a


def parse_day(day: Any) -> int:
    tt = _tt()
    try:
        d = int(day)
    except (TypeError, ValueError):
        d = tt.day_number(str(day or "")) or 0
    if d not in tt.DAY_NUMBERS:
        raise ValidationError(f"Day must be one of: {', '.join(tt.DAYS)}")
    return d


def parse_period(period: Any) -> int:
    tt = _tt()
    try:
        p = int(str(period).strip().upper().lstrip("P"))
    except (TypeError, ValueError):
        raise ValidationError("Period must be a whole number") from None
    if p not in tt.PERIODS:
        raise ValidationError(f"Period must be one of {list(tt.PERIODS)}")
    return p


# ── Lessons ──────────────────────────────────────────────────────────

_LESSON_SQL = """
SELECT t.slot_id, t.group_id, t.day, t.period, t.start_time, t.end_time,
       COALESCE(NULLIF(t.room, ''), NULLIF(cg.room, ''), c.room) AS room,
       cg.group_name, cg.course_id, c.course_code, c.title, c.subject,
       NULLIF(TRIM(cg.teacher), '') AS gt, NULLIF(TRIM(c.teacher), '') AS ct
FROM timetable_slots t
JOIN class_groups cg ON cg.group_id = t.group_id
JOIN courses c       ON c.course_id = cg.course_id
WHERE t.archived_at IS NULL
ORDER BY t.day, t.period, c.course_code, cg.group_name
"""


def all_lessons() -> list[StaffLesson]:
    _init()
    with _connect() as conn:
        rows = conn.execute(_LESSON_SQL).fetchall()
    return [StaffLesson(
        slot_id=r["slot_id"], group_id=r["group_id"],
        group_name=r["group_name"], course_id=r["course_id"],
        course_code=r["course_code"], course_title=r["title"],
        subject=r["subject"], day=r["day"], period=r["period"],
        start_time=r["start_time"], end_time=r["end_time"],
        room=r["room"], teacher_text=r["gt"] or r["ct"],
        inherited=not r["gt"] and bool(r["ct"])) for r in rows]


def _norm(s: str | None) -> str:
    return " ".join((s or "").split()).lower()


def _staff_module():
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    return _staff


def _aliases(st: Any) -> set[str]:
    from education_system.systems.sixth_form.domain.academics.cover.cover import (
        staff_aliases,
    )
    return staff_aliases(st)


def _alias_index(staff_rows: list[Any]) -> dict[str, str]:
    """alias -> staff_id. An alias two people share (two "Mr Smith"s) is
    dropped, so the lesson shows as unmatched instead of mis-assigned."""
    seen: dict[str, str] = {}
    clash: set[str] = set()
    for st in staff_rows:
        for a in _aliases(st):
            if a in seen and seen[a] != st.staff_id:
                clash.add(a)
            seen.setdefault(a, st.staff_id)
    for a in clash:
        seen.pop(a, None)
    return seen


def lessons_by_staff(*, active_only: bool = True
                     ) -> tuple[dict[str, list[StaffLesson]],
                                list[StaffLesson]]:
    """``({staff_id: lessons}, unmatched)`` for the whole timetable."""
    staff_rows = _staff_module().list_staff(active_only=active_only)
    index = _alias_index(staff_rows)
    out: dict[str, list[StaffLesson]] = {s.staff_id: [] for s in staff_rows}
    unmatched: list[StaffLesson] = []
    for lesson in all_lessons():
        sid = index.get(_norm(lesson.teacher_text))
        if sid is None:
            unmatched.append(lesson)
        else:
            out[sid].append(lesson)
    return out, unmatched


def _require_staff(staff_id: str) -> Any:
    sid = (staff_id or "").strip().upper()
    if not sid:
        raise ValidationError("Staff member is required")
    st = _staff_module().get_staff(sid)
    if st is None:
        raise ValidationError(f"No staff member {sid}")
    return st


def staff_timetable(staff_id: str) -> list[StaffLesson]:
    """Every lesson this person teaches in a normal week."""
    st = _require_staff(staff_id)
    index = _alias_index(_staff_module().list_staff())
    mine = {a for a in _aliases(st) if index.get(a) == st.staff_id}
    return [ls for ls in all_lessons() if _norm(ls.teacher_text) in mine]


def staff_grid(staff_id: str) -> dict[tuple[int, int], list[StaffLesson]]:
    grid: dict[tuple[int, int], list[StaffLesson]] = {}
    for ls in staff_timetable(staff_id):
        grid.setdefault((ls.day, ls.period), []).append(ls)
    return grid


def unmatched_lessons() -> list[StaffLesson]:
    """Slots whose teacher text matches no (active) staff record, or that
    have no teacher on the group or the course."""
    return lessons_by_staff(active_only=False)[1]


# ── Load ─────────────────────────────────────────────────────────────

def fte_for(staff_id: str) -> float:
    """FTE % from the Staff HR record; 100 when there is none."""
    try:
        from education_system.systems.sixth_form.domain.staff.staff_hr import (
            staff_hr as _hr,
        )
        rec = _hr.get_record_for_staff(staff_id)
    except Exception:  # noqa: BLE001 - HR store optional here
        logger.debug("No HR record available for %s", staff_id,
                     exc_info=True)
        rec = None
    return float(rec.fte_percent) if rec and rec.fte_percent else 100.0


def _fte_map() -> dict[str, float]:
    try:
        from education_system.systems.sixth_form.domain.staff.staff_hr import (
            staff_hr as _hr,
        )
        return {r.staff_id: float(r.fte_percent or 100)
                for r in _hr.list_records()}
    except Exception:  # noqa: BLE001
        logger.debug("Staff HR records unavailable", exc_info=True)
        return {}


def periods_per_week() -> int:
    tt = _tt()
    return len(tt.DAYS) * len(tt.PERIODS)


def _load_for(st: Any, lessons: list[StaffLesson], fte: float
              ) -> TeachingLoad:
    load = TeachingLoad(
        staff_id=st.staff_id,
        name=" ".join(f"{st.first_name} {st.last_name}".split()),
        role=st.role, department=st.department, fte_percent=fte,
        available_periods=round(periods_per_week() * fte / 100))
    cells: dict[tuple[int, int], int] = {}
    for ls in lessons:
        key = (ls.day, ls.period)
        cells[key] = cells.get(key, 0) + 1
        load.groups.add(ls.group_id)
    # A double-booked cell is still one period of the teacher's time.
    load.periods = len(cells)
    seen: set[tuple[int, int]] = set()
    for ls in lessons:
        key = (ls.day, ls.period)
        if key not in seen:
            seen.add(key)
            load.minutes += ls.minutes
    load.double_booked = sorted(k for k, n in cells.items() if n > 1)
    return load


def teaching_load(staff_id: str) -> TeachingLoad:
    st = _require_staff(staff_id)
    return _load_for(st, staff_timetable(st.staff_id), fte_for(st.staff_id))


def teaching_loads(*, include_zero: bool = False,
                   department: str | None = None) -> list[TeachingLoad]:
    """Load for every active member of staff, heaviest first."""
    by_staff, _ = lessons_by_staff()
    staff_rows = {s.staff_id: s for s in _staff_module().list_staff(
        active_only=True)}
    ftes = _fte_map()
    out = []
    for sid, lessons in by_staff.items():
        st = staff_rows.get(sid)
        if st is None or (department and st.department != department):
            continue
        if not lessons and not include_zero:
            continue
        out.append(_load_for(st, lessons, ftes.get(sid, 100.0)))
    out.sort(key=lambda x: (-x.periods, x.name))
    return out


# ── Who is free ──────────────────────────────────────────────────────

def free_staff(day: Any, period: Any, *, on_date: str | None = None,
               teaching_roles_only: bool = True,
               department: str | None = None) -> list[FreeStaff]:
    """Active staff with no lesson at (``day``, ``period``).

    ``day`` is 1-5 or a name ("Mon", "Tuesday"); ``period`` 1-6 or "P3".
    With ``on_date`` (YYYY-MM-DD, which must fall on ``day``) staff who
    are absent that day, or already allocated to cover that period, are
    left out too. ``teaching_roles_only`` keeps to the roles Cover can
    put in front of a class. Fewest lessons that day first.
    """
    d = parse_day(day)
    p = parse_period(period)
    from education_system.systems.sixth_form.domain.academics.cover import (
        cover as _cover,
    )
    if on_date:
        try:
            when = _dt.date.fromisoformat(str(on_date).strip())
        except ValueError:
            raise ValidationError("Date must be YYYY-MM-DD") from None
        if when.weekday() + 1 != d:
            raise ValidationError(
                f"{when.isoformat()} is not a {_tt().day_name(d)}")
        on_date = when.isoformat()
    by_staff, _ = lessons_by_staff()
    covering: dict[str, str] = {}
    if on_date:
        for req in _cover.list_requests(date_from=on_date, date_to=on_date):
            if req.status not in ("Allocated", "Confirmed", "Completed") \
                    or not req.cover_staff:
                continue
            periods = _cover._periods_of(req)
            if not periods or p in periods:
                covering[_norm(req.cover_staff)] = f"covering #{req.cover_id}"
    out: list[FreeStaff] = []
    for st in _staff_module().list_staff(active_only=True):
        if teaching_roles_only and st.role not in _cover.COVER_ROLES:
            continue
        if department and st.department != department:
            continue
        lessons = by_staff.get(st.staff_id, [])
        if any(ls.day == d and ls.period == p for ls in lessons):
            continue
        if on_date:
            if _cover._absent_on(st.staff_id, on_date):
                continue
            if any(a in covering for a in _aliases(st)):
                continue
        out.append(FreeStaff(
            staff_id=st.staff_id,
            name=" ".join(f"{st.first_name} {st.last_name}".split()),
            role=st.role, department=st.department,
            lessons_that_day=len({ls.period for ls in lessons
                                  if ls.day == d}),
            lessons_this_week=len({(ls.day, ls.period) for ls in lessons})))
    out.sort(key=lambda f: (f.lessons_that_day, f.lessons_this_week, f.name))
    return out


def free_periods(staff_id: str) -> list[tuple[int, int]]:
    """(day, period) cells with no lesson for this person."""
    taken = {(ls.day, ls.period) for ls in staff_timetable(staff_id)}
    tt = _tt()
    return [(d, p) for d in tt.DAY_NUMBERS for p in tt.PERIODS
            if (d, p) not in taken]
