"""CLI flows for expected sessions and AM/PM statutory marks.

Submenu hung off Attendance, over :mod:`attendance_sessions`: what the
timetable expected, which of it never got marked, the true attendance
percentage that follows, and the AM/PM session marks a statutory return
is actually counted in.
"""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _timedelta
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_codes as codes,
    attendance_sessions as sessions,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.academics.attendance.attendance_cli import (
    _input,
    _pause,
    _pick_from,
    _pick_group,
    _UserAbort,
)
from education_system.systems.sixth_form.domain.academics.timetable.timetable import (
    day_name,
)

logger = logging.getLogger(__name__)

_WINDOW_DAYS: int = 14


def _today() -> str:
    return _date.today().isoformat()


def _window() -> tuple[str, str]:
    default_from = (_date.today() - _timedelta(days=_WINDOW_DAYS)).isoformat()
    date_from = _input("From (YYYY-MM-DD)", default=default_from)
    date_to = _input("To (YYYY-MM-DD)", default=_today())
    return date_from, date_to


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


# ── Expected sessions ───────────────────────────────────────────────

def expected() -> None:
    print("\n═══ Expected Lessons ═══")
    print("\n  The timetable expanded across a date window: what should")
    print("  have happened, whether or not anyone marked it.")
    date_from, date_to = _window()
    group_id = None
    if _input("Limit to one group? (y/N)", default="n").lower().startswith("y"):
        group_id = _pick_group()
    try:
        lessons = sessions.expected_lessons(
            group_id=group_id, date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return

    open_days = sessions.teaching_dates(date_from, date_to)
    print(f"\n  {len(open_days)} teaching day(s), {len(lessons)} lesson(s).")
    if not lessons:
        print("\n  Nothing timetabled in that window.")
        _pause()
        return
    print(f"\n    {'Date':<12}{'Day':<6}{'Period':>7}  {'Slot':>5}"
          f"  {'Group':>6}  Session")
    for lesson in lessons[:80]:
        print(f"    {lesson.date:<12}{day_name(lesson.day):<6}"
              f"{lesson.period:>7}  {lesson.slot_id:>5}"
              f"  {lesson.group_id:>6}  {lesson.session}")
    if len(lessons) > 80:
        print(f"    … and {len(lessons) - 80} more.")
    print(f"\n  {sessions.sessions_expected(date_from=date_from, date_to=date_to)}"
          f" AM/PM session(s) in the same window.")
    _pause()


def gaps() -> None:
    print("\n═══ Unmarked Lessons ═══")
    print("\n  Expected lessons with no attendance row. These are the")
    print("  ones that quietly flatter every percentage in the system.")
    date_from, date_to = _window()
    group_id = None
    if _input("Limit to one group? (y/N)", default="n").lower().startswith("y"):
        group_id = _pick_group()
    try:
        missing = sessions.missing_marks(
            group_id=group_id, date_from=date_from, date_to=date_to)
        cover = sessions.coverage(group_id=group_id, date_from=date_from,
                                  date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return

    print(f"\n  Coverage: {cover.recorded}/{cover.expected} marks "
          f"({_pct(cover.percentage)}); {cover.missing} missing.")
    if not missing:
        print("\n  ✓ Every expected lesson has been marked.")
        _pause()
        return

    by_lesson: dict[tuple[str, int], list[str]] = {}
    for gap in missing:
        by_lesson.setdefault(
            (gap.lesson.date, gap.lesson.slot_id), []).append(gap.student_name)
    print(f"\n  {len(missing)} missing mark(s) across "
          f"{len(by_lesson)} lesson(s):\n")
    for (date_s, slot_id), names in sorted(by_lesson.items())[:40]:
        print(f"    {date_s}  slot #{slot_id:<4} {len(names):>3} learner(s)"
              f"  {', '.join(names[:4])}"
              f"{' …' if len(names) > 4 else ''}")
    if len(by_lesson) > 40:
        print(f"    … and {len(by_lesson) - 40} more lessons.")
    _pause()


def true_percentage() -> None:
    print("\n═══ True Attendance (against the timetable) ═══")
    print("\n  Divides by what was timetabled rather than by the marks")
    print("  that happen to exist, so an unmarked lesson counts against")
    print("  the college instead of vanishing.")
    student_id = _input("Student ID", allow_empty=False)
    date_from, date_to = _window()
    try:
        summary = sessions.true_summary(
            student_id, date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return

    print(f"\n  {student_id}, {date_from} to {date_to}\n")
    print(f"    Expected lessons     {summary.expected:>6}")
    print(f"    Marked               {summary.recorded:>6}")
    print(f"    Never marked         {summary.unrecorded:>6}")
    print(f"    Present              {summary.present:>6}")
    print(f"    Approved (off site)  {summary.approved:>6}")
    print(f"    Authorised absence   {summary.authorised:>6}")
    print(f"    Unauthorised absence {summary.unauthorised:>6}")
    print(f"    Not counted          {summary.not_counted:>6}")
    print(f"\n    Against timetable    {_pct(summary.percentage)}")
    print(f"    Against marks only   {_pct(summary.recorded_percentage)}")
    print(f"    Unauthorised rate    {_pct(summary.unauthorised_percentage)}")
    if summary.unrecorded:
        print(f"\n  The gap between those two figures is {summary.unrecorded}")
        print("  unmarked lesson(s), not a change in behaviour.")
    _pause()


# ── AM/PM sessions ──────────────────────────────────────────────────

def mark_session() -> None:
    print("\n═══ Record an AM/PM Session Mark ═══")
    print("\n  For a day with no lesson to infer from — a whole-day")
    print("  absence, or a session outside the timetable.")
    student_id = _input("Student ID", allow_empty=False)
    date_s = _input("Date (YYYY-MM-DD)", default=_today())
    session = _pick_from("Session", list(sessions.SESSIONS), default="AM")
    print("\n  Codes: " + "  ".join(
        f"{m.code}={m.label}" for m in codes.MARK_CODES[:8]))
    code = _input("Mark code", allow_empty=False)
    notes = _input("Notes (optional)")
    try:
        mark = sessions.mark_session(
            student_id, date_s, session, code, notes=notes or None,
            recorded_by=_input("Your username", default="cli"))
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {mark.student_id} {mark.date} {mark.session} = "
          f"[{mark.code}] {mark.status}.")
    _pause()


def roll_up() -> None:
    print("\n═══ Roll Lesson Marks Up Into Sessions ═══")
    print("\n  Collapses each day's lesson marks into an AM and a PM")
    print("  mark, taking the most favourable meaning in each half —")
    print("  in the room for any of it means present for the session.")
    print("  Marks a human typed are left alone.")
    date_from, date_to = _window()
    group_id = None
    if _input("Limit to one group? (y/N)", default="n").lower().startswith("y"):
        group_id = _pick_group()
    overwrite = _input("Overwrite manually entered session marks too? (y/N)",
                       default="n").lower().startswith("y")
    try:
        written = sessions.roll_up_range(
            date_from=date_from, date_to=date_to, group_id=group_id,
            recorded_by=_input("Your username", default="cli"),
            overwrite_manual=overwrite)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Wrote {written} session mark(s).")
    _pause()


def session_marks() -> None:
    print("\n═══ Session Marks ═══")
    student_id = _input("Student ID (blank for all)")
    date_from, date_to = _window()
    try:
        marks = sessions.list_session_marks(
            student_id=student_id or None,
            date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not marks:
        print("\n  No session marks in that window.")
        _pause()
        return
    print(f"\n  {len(marks)} session mark(s):\n")
    print(f"    {'Date':<12}{'Student':<14}{'Sess':<6}{'Code':<6}"
          f"{'Status':<12}Source")
    for mark in marks[:100]:
        print(f"    {mark.date:<12}{mark.student_id:<14}{mark.session:<6}"
              f"{mark.code:<6}{mark.status:<12}"
              f"{'derived' if mark.derived else 'manual'}")
    if len(marks) > 100:
        print(f"    … and {len(marks) - 100} more.")
    _pause()


def statutory_summary() -> None:
    print("\n═══ Statutory Session Summary ═══")
    student_id = _input("Student ID", allow_empty=False)
    date_from, date_to = _window()
    try:
        summary = sessions.session_summary(
            student_id, date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  {student_id}, {date_from} to {date_to}\n")
    print(f"    Possible sessions    {summary.possible:>6}")
    print(f"    Attended             {summary.attended:>6}")
    print(f"    Authorised absence   {summary.authorised:>6}")
    print(f"    Unauthorised absence {summary.unauthorised:>6}")
    print(f"    Not counted          {summary.not_counted:>6}")
    print(f"\n    Attendance           {_pct(summary.percentage)}")
    print(f"    Unauthorised rate    {_pct(summary.unauthorised_percentage)}")
    if summary.persistently_absent:
        print("\n  ! Below 90% — this learner is persistently absent on the")
        print("    sector's definition.")
    _pause()


# ── Submenu dispatcher ─────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Expected Lessons",            expected),
    ("Unmarked Lessons (coverage)", gaps),
    ("True Attendance %",           true_percentage),
    ("Record a Session Mark",       mark_session),
    ("Roll Lessons Up to Sessions", roll_up),
    ("List Session Marks",          session_marks),
    ("Statutory Session Summary",   statutory_summary),
]


def run() -> None:
    while True:
        print("\n── Expected & Statutory Sessions ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Attendance sessions CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()
