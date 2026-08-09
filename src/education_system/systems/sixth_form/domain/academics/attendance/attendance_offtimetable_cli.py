"""CLI flows for registers that are not lessons.

Submenu hung off Attendance, over the three places a sixth-former is
expected to be that the timetable does not describe:

* **Activities** — tutorial, assembly, enrichment, EPQ supervision,
  supervised study (:mod:`attendance_activities`).
* **Placements** — days at an employer, confirmed by the supervisor
  (:mod:`attendance_placements`).
* **Exams** — the register taken in the hall
  (:mod:`attendance_exams`).
"""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _timedelta
from typing import Callable

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_activities as activities,
    attendance_codes as codes,
    attendance_exams as exams,
    attendance_placements as placements,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.attendance.attendance_cli import (
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


def _today() -> str:
    return _date.today().isoformat()


def _month_ago() -> str:
    return (_date.today() - _timedelta(days=30)).isoformat()


def _yes(prompt: str, *, default: str = "n") -> bool:
    return _input(prompt, default=default).lower().startswith("y")


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _pick_activity() -> int:
    rows = activities.list_activities()
    if not rows:
        print("    No activities set up yet.")
        raise _UserAbort
    print("\n  Activities:")
    for i, activity in enumerate(rows, 1):
        print(f"    {i:>3}) #{activity.activity_id:<3} {activity.label}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or activity ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].activity_id
            match = next((a for a in rows if a.activity_id == n), None)
            if match:
                return match.activity_id
            print(f"    Out of range (1..{len(rows)}).")


# ═══ Activities ═════════════════════════════════════════════════════

def activity_list() -> None:
    print("\n═══ Activities ═══")
    rows = activities.list_activities(active_only=False)
    if not rows:
        print("\n  Nothing set up yet.")
        _pause()
        return
    print(f"\n    {'#':>4}  {'Name':<24}{'Kind':<18}{'When':<14}"
          f"{'Week':<6}{'Req':<5}{'Roster':>6}")
    for activity in rows:
        when = (f"{day_name(activity.day)}"
                + (f" P{activity.period}" if activity.period else "")
                if activity.day else "ad hoc")
        print(f"    {activity.activity_id:>4}  {activity.name[:23]:<24}"
              f"{activity.kind:<18}{when:<14}{activity.week:<6}"
              f"{('yes' if activity.required else 'no'):<5}"
              f"{activities.count_members(activity.activity_id):>6}")
    _pause()


def activity_create() -> None:
    print("\n═══ New Activity ═══")
    print("\n  'Required' decides whether missing it counts against a")
    print("  learner. Assembly usually does; a voluntary club does not.")
    try:
        name = _input("Name", allow_empty=False)
        kind = _pick_from("Kind", list(activities.KINDS),
                          default=activities.DEFAULT_KIND)
        recurring = _yes("Does it run to a weekly slot? (Y/n)", default="y")
        day = period = None
        if recurring:
            day = _input("Day (1=Mon .. 5=Fri)", allow_empty=False)
            period = _input("Period (blank if not in a period)") or None
        room = _input("Room (optional)") or None
        staff = _input("Staff (optional)") or None
        week = _input("Week (A / B / Both)", default="Both")
        required = _yes("Required? (Y/n)",
                        default="y" if kind in activities.NORMALLY_REQUIRED
                        else "n")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        activity = activities.create_activity({
            "name": name, "kind": kind, "day": day, "period": period,
            "room": room, "staff": staff, "week": week, "required": required,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{activity.activity_id}: {activity.label}")
    if _yes("  Add a whole class group to the roster? (y/N)"):
        try:
            group_id = _pick_group()
            n = activities.enrol_class_group(activity.activity_id, group_id)
            print(f"\n  ✓ Added {n} learner(s).")
        except (ValidationError, _UserAbort) as e:
            print(f"\n  ✗ {e}" if isinstance(e, ValidationError)
                  else "\n  Cancelled.")
    _pause()


def activity_roster() -> None:
    print("\n═══ Activity Roster ═══")
    try:
        activity_id = _pick_activity()
    except _UserAbort:
        return
    members = activities.list_members(activity_id)
    print(f"\n  {len(members)} learner(s): "
          + (", ".join(members[:20]) if members else "(empty)"))
    print("\n  Actions:  A) Add   R) Remove   G) Add a class group   "
          "(Enter to go back)")
    try:
        choice = _input("Action", default="").lower()
        if choice == "a":
            sid = _input("Student ID", allow_empty=False)
            activities.add_member(activity_id, sid)
            print("\n  ✓ Added.")
        elif choice == "r":
            sid = _input("Student ID", allow_empty=False)
            print("\n  ✓ Removed." if activities.remove_member(activity_id, sid)
                  else "\n  ✗ Not on this roster.")
        elif choice == "g":
            group_id = _pick_group()
            n = activities.enrol_class_group(activity_id, group_id)
            print(f"\n  ✓ Added {n} learner(s).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def activity_register() -> None:
    print("\n═══ Take an Activity Register ═══")
    try:
        activity_id = _pick_activity()
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
        entries = activities.register_view(activity_id, date_s)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    if not entries:
        print("\n  ✗ Nobody on the roster for that date.")
        _pause()
        return
    if not activities.meets_on(activity_id, date_s):
        print("\n  ⚠ This activity is not scheduled to meet that day.")
        if not _yes("  Mark it anyway? (y/N)"):
            return

    print(f"\n  {len(entries)} learner(s). Codes: / present, L late,")
    print("  I illness, C authorised, N no reason yet, O unauthorised.")
    print("  Blank marks present; S skips.\n")
    payload: dict[str, dict[str, object]] = {}
    for entry in entries:
        current = f"  [now: {entry.mark.code}]" if entry.mark else ""
        try:
            raw = _input(f"  {entry.student_id} {entry.full_name}{current}",
                         default=(entry.mark.code if entry.mark else "/"))
        except _UserAbort:
            print("\n  Cancelled.")
            return
        if raw.lower() == "s":
            continue
        payload[entry.student_id] = {"code": raw}
    if not payload:
        print("\n  (nothing changed)")
        _pause()
        return
    try:
        n = activities.save_register(activity_id, date_s, payload)
        print(f"\n  ✓ Saved {n} mark(s).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def activity_summary() -> None:
    print("\n═══ Activity Attendance ═══")
    try:
        activity_id = _pick_activity()
        date_from = _input("From (YYYY-MM-DD)", default=_month_ago())
        date_to = _input("To (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    overall = activities.summary_for_activity(
        activity_id, date_from=date_from, date_to=date_to)
    per = activities.per_student_summary(
        activity_id, date_from=date_from, date_to=date_to)
    print(f"\n  Overall: {overall.attending}/{overall.possible} "
          f"({_pct(overall.percentage)}) across {overall.sessions} mark(s)")
    if per:
        print(f"\n    {'Student':<12}{'Sess.':>6}{'Att.':>6}{'Auth.':>6}"
              f"{'Unauth.':>8}{'%':>7}")
        for sid, summary in sorted(per.items()):
            print(f"    {sid:<12}{summary.sessions:>6}{summary.attending:>6}"
                  f"{summary.authorised:>6}{summary.unauthorised:>8}"
                  f"{_pct(summary.percentage):>7}")
    _pause()


def activity_gaps() -> None:
    print("\n═══ Unmarked Activity Registers ═══")
    print("\n  Nobody chases a club register unprompted. This is the list.")
    try:
        date_from = _input("From (YYYY-MM-DD)", default=_month_ago())
        date_to = _input("To (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    try:
        missing = activities.missing_registers(date_from=date_from,
                                               date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not missing:
        print("\n  ✓ Everything that met has been marked.")
        _pause()
        return
    print(f"\n  {len(missing)} unmarked session(s):\n")
    for row in missing[:40]:
        print(f"    {row.date}  {row.activity.name[:28]:<30}"
              f"{row.marked}/{row.expected} marked")
    if len(missing) > 40:
        print(f"    … and {len(missing) - 40} more.")
    _pause()


_ACTIVITY_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List activities",     activity_list),
    ("New activity",        activity_create),
    ("Roster",              activity_roster),
    ("Take a register",     activity_register),
    ("Attendance summary",  activity_summary),
    ("Unmarked registers",  activity_gaps),
]


# ═══ Placements ═════════════════════════════════════════════════════

def placement_generate() -> None:
    print("\n═══ Generate Placement Days ═══")
    print("\n  Expands a placement into the days it should run, so each")
    print("  one can be confirmed by the employer.")
    try:
        placement_id = int(_input("Placement ID", allow_empty=False))
        if _yes("Set a working pattern first? (y/N)"):
            raw = _input("Days (e.g. 1,3 for Mon+Wed)", default="1,2,3,4,5")
            hours = _input("Hours per day", default="7")
            placements.set_pattern(
                placement_id,
                days=[int(d) for d in raw.split(",") if d.strip()],
                hours_per_day=float(hours))
        days = placements.generate_days(placement_id)
    except ValueError:
        print("\n  ✗ That needs to be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    pattern = placements.get_pattern(placement_id)
    print(f"\n  ✓ {len(days)} day(s) generated. Pattern: {pattern.label}")
    _pause()


def placement_confirm() -> None:
    print("\n═══ Confirm a Placement Day ═══")
    print("\n  The supervisor's word is the record — their name is required.")
    try:
        placement_id = int(_input("Placement ID", allow_empty=False))
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
        outcome = _pick_from("What happened",
                             ["Attended", "Did not attend",
                              "Employer cancelled"],
                             default="Attended")
        confirmed_by = _input("Confirmed by (supervisor)",
                              allow_empty=(outcome == "Employer cancelled"))
        notes = _input("Notes (optional)") or None
        if outcome == "Attended":
            hours = _input("Hours", default="") or None
            arrival = _input("Arrival time (HH:MM, optional)") or None
            departure = _input("Departure time (HH:MM, optional)") or None
            day = placements.confirm_day(
                placement_id, date_s,
                hours=float(hours) if hours else None,
                arrival_time=arrival, departure_time=departure,
                confirmed_by=confirmed_by, notes=notes)
        elif outcome == "Did not attend":
            day = placements.report_missed(placement_id, date_s,
                                           confirmed_by=confirmed_by,
                                           notes=notes)
        else:
            day = placements.cancel_day(placement_id, date_s, reason=notes,
                                        confirmed_by=confirmed_by or None)
    except ValueError:
        print("\n  ✗ That needs to be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ {day.label}")
    print("    College registers for that day have been updated.")
    _pause()


def placement_chase() -> None:
    print("\n═══ Placement Days Awaiting Confirmation ═══")
    print("\n  Days that have passed with nobody saying what happened.")
    print("  Until they are confirmed they are not evidence of anything.")
    try:
        older = _input("Older than (days)", default="0")
        days = placements.awaiting_confirmation(older_than_days=int(older))
    except ValueError:
        print("\n  ✗ That needs to be a number.")
        _pause()
        return
    except _UserAbort:
        return
    if not days:
        print("\n  ✓ Nothing outstanding.")
        _pause()
        return
    print(f"\n  {len(days)} day(s):\n")
    print(f"    {'Date':<12}{'Student':<12}{'Placement':>10}")
    for day in days[:50]:
        print(f"    {day.date:<12}{day.student_id:<12}"
              f"{day.placement_id:>10}")
    if len(days) > 50:
        print(f"    … and {len(days) - 50} more.")
    _pause()


def placement_record() -> None:
    print("\n═══ Placement Attendance ═══")
    try:
        by_student = _yes("Look up by student? (y/N)")
        if by_student:
            student_id = _input("Student ID", allow_empty=False)
            record = placements.attendance_for_student(student_id)
            heading = student_id
        else:
            placement_id = int(_input("Placement ID", allow_empty=False))
            record = placements.attendance_for(placement_id)
            heading = f"Placement #{placement_id}"
    except ValueError:
        print("\n  ✗ That needs to be a number.")
        _pause()
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {heading}")
    print(f"    Days expected  : {record.expected}")
    print(f"    Confirmed      : {record.confirmed}")
    print(f"    Missed         : {record.missed}")
    print(f"    Cancelled      : {record.cancelled}")
    print(f"    Unconfirmed    : {record.unconfirmed}")
    print(f"    Hours          : {record.hours:g}")
    print(f"    Attendance     : {_pct(record.percentage)} "
          f"(of days reported on)")
    print(f"    Confirmed back : {_pct(record.confirmation_rate)}")
    _pause()


def placement_discrepancies() -> None:
    print("\n═══ Placement vs College Register ═══")
    print("\n  Where the two disagree. Usually a learner marked absent who")
    print("  was at their placement, or one marked W who never arrived.")
    try:
        date_from = _input("From (YYYY-MM-DD)", default=_month_ago())
        date_to = _input("To (YYYY-MM-DD)", default=_today())
        rows = placements.discrepancies(date_from=date_from, date_to=date_to)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    if not rows:
        print("\n  ✓ No disagreements.")
        _pause()
        return
    print(f"\n  {len(rows)} to look at:\n")
    for row in rows[:40]:
        print(f"    {row.label}")
    if len(rows) > 40:
        print(f"    … and {len(rows) - 40} more.")
    _pause()


_PLACEMENT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Generate placement days",     placement_generate),
    ("Confirm a day",               placement_confirm),
    ("Awaiting confirmation",       placement_chase),
    ("Attendance record",           placement_record),
    ("Disagreements with register", placement_discrepancies),
]


# ═══ Exams ══════════════════════════════════════════════════════════

def _pick_sitting() -> int:
    rows = exams.list_sittings(date_from=_month_ago())
    if not rows:
        print("    No sittings scheduled.")
        raise _UserAbort
    print("\n  Sittings:")
    for i, sitting in enumerate(rows, 1):
        print(f"    {i:>3}) #{sitting.sitting_id:<3} {sitting.label} "
              f"[{sitting.state}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or sitting ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].sitting_id
            match = next((s for s in rows if s.sitting_id == n), None)
            if match:
                return match.sitting_id
            print(f"    Out of range (1..{len(rows)}).")


def exam_create() -> None:
    print("\n═══ Schedule a Sitting ═══")
    try:
        sitting = exams.create_sitting({
            "paper_code": _input("Paper code", allow_empty=False),
            "paper_title": _input("Paper title (optional)") or None,
            "subject": _input("Subject (optional)") or None,
            "exam_board": _input("Board (optional)") or None,
            "date": _input("Date (YYYY-MM-DD)", allow_empty=False),
            "start_time": _input("Start time (HH:MM)", allow_empty=False),
            "end_time": _input("End time (HH:MM, optional)") or None,
            "room": _input("Room (optional)") or None,
            "series": _input("Series (e.g. Summer)") or None,
            "invigilator": _input("Invigilator (optional)") or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  ✓ #{sitting.sitting_id}: {sitting.label}")
    print(f"    Arrivals after {sitting.very_late_after} are reportable.")
    if _yes("  Fill the candidate list from exam entries? (Y/n)",
            default="y"):
        try:
            n = exams.populate_from_entries(sitting.sitting_id)
            print(f"\n  ✓ {n} candidate(s) seated.")
        except Exception as e:
            print(f"\n  ✗ Could not read entries: {e}")
    _pause()


def exam_seating() -> None:
    print("\n═══ Seating Plan ═══")
    try:
        sitting_id = _pick_sitting()
        plan = exams.seating_plan(sitting_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        return
    print(f"\n  {plan.sitting.label}")
    print(f"\n    {'Seat':<6}{'Candidate':<12}{'Name':<24}Access arrangements")
    for candidate in plan.rows:
        print(f"    {(candidate.seat or '—'):<6}"
              f"{(candidate.candidate_no or candidate.student_id)[:11]:<12}"
              f"{(candidate.full_name or '')[:23]:<24}"
              f"{candidate.access_arrangements or ''}")
    if plan.unseated:
        print(f"\n  ⚠ {len(plan.unseated)} candidate(s) with no seat: "
              + ", ".join(c.student_id for c in plan.unseated[:10]))
    _pause()


def exam_register() -> None:
    print("\n═══ Take an Exam Register ═══")
    print("\n  Filled by exception: mark everyone present, then the empty")
    print("  seats. A late arrival's time decides whether it is reportable.")
    try:
        sitting_id = _pick_sitting()
        sitting = exams.get_sitting(sitting_id)
    except _UserAbort:
        return
    if sitting is None:
        print("\n  ✗ No such sitting.")
        _pause()
        return
    if sitting.is_signed_off:
        print(f"\n  ✗ Signed off by {sitting.signed_off_by} at "
              f"{sitting.signed_off_at}. Reopen it to make changes.")
        _pause()
        return

    try:
        if _yes("Mark all unmarked candidates present first? (Y/n)",
                default="y"):
            n = exams.mark_all_present(sitting_id)
            print(f"\n  ✓ {n} marked present.")
        while True:
            student_id = _input(
                "Student ID to change (blank to finish)", default="")
            if not student_id:
                break
            state = _pick_from("State", list(exams.CANDIDATE_STATES),
                               default=exams.ABSENT)
            arrival = None
            reason = None
            if state in exams.SAT_STATES:
                arrival = _input("Arrival time (HH:MM, blank = on time)") or None
            if state in (exams.ABSENT, exams.WITHDRAWN, exams.REMOVED):
                reason = _pick_from("Reason", list(exams.ABSENCE_REASONS),
                                    default="Unexplained")
            candidate = exams.mark_candidate(
                sitting_id, student_id, state, arrival_time=arrival,
                absence_reason=reason)
            flag = "  ⚠ reportable to the board" if candidate.reportable else ""
            print(f"    ✓ {candidate.state}{flag}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    summary = exams.summary(sitting_id)
    print(f"\n  Sat {summary.sat}/{summary.entered - summary.withdrawn}"
          f" ({_pct(summary.attendance_rate)}); absent {summary.absent}, "
          f"unmarked {summary.unmarked}")
    if summary.complete and _yes("  Sign the register off now? (y/N)"):
        try:
            who = _input("Invigilator", allow_empty=False)
            exams.sign_off(sitting_id, invigilator=who)
            print("\n  ✓ Signed off.")
        except (ValidationError, _UserAbort) as e:
            print(f"\n  ✗ {e}" if isinstance(e, ValidationError)
                  else "\n  Not signed off.")
    _pause()


def exam_absentees() -> None:
    print("\n═══ Exam Absentees ═══")
    try:
        date_s = _input("Date (YYYY-MM-DD)", default=_today())
    except _UserAbort:
        return
    rows = exams.absentees(date=date_s)
    if not rows:
        print("\n  ✓ Nobody missing.")
    else:
        print(f"\n  {len(rows)} to chase:\n")
        for sitting, candidate in rows:
            print(f"    {sitting.paper_code:<10}{sitting.start_time:<7}"
                  f"{candidate.student_id:<10}"
                  f"{(candidate.full_name or '')[:22]:<24}"
                  f"{candidate.absence_reason or 'Unexplained'}")
    reportable = exams.reportable(date_from=date_s, date_to=date_s)
    if reportable:
        print(f"\n  ⚠ {len(reportable)} candidate(s) to report to the board:")
        for sitting, candidate in reportable:
            print(f"    {sitting.paper_code} — {candidate.student_id} "
                  f"({candidate.state}, {candidate.minutes_late or 0} min)")
    _pause()


def exam_unsigned() -> None:
    print("\n═══ Unsigned Exam Registers ═══")
    rows = exams.unsigned_registers()
    if not rows:
        print("\n  ✓ Every past sitting is signed off.")
        _pause()
        return
    for sitting in rows:
        summary = exams.summary(sitting.sitting_id)
        print(f"    #{sitting.sitting_id:<4} {sitting.label:<34}"
              f"{summary.unmarked} unmarked")
    _pause()


_EXAM_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Schedule a sitting",  exam_create),
    ("Seating plan",        exam_seating),
    ("Take the register",   exam_register),
    ("Absentees & reportable", exam_absentees),
    ("Unsigned registers",  exam_unsigned),
]


# ── Submenu plumbing ────────────────────────────────────────────────

def _run_menu(title: str, menu: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(menu, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(menu)):
            print("  Invalid selection.")
            continue
        _, handler = menu[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Off-timetable CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def activities_menu() -> None:
    _run_menu("Activities", _ACTIVITY_MENU)


def placements_menu() -> None:
    _run_menu("Work Placements", _PLACEMENT_MENU)


def exams_menu() -> None:
    _run_menu("Exam Registers", _EXAM_MENU)


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Activities (tutorial / enrichment / study)", activities_menu),
    ("Work Placements", placements_menu),
    ("Exam Registers",  exams_menu),
]


def run() -> None:
    _run_menu("Off-timetable Registers", _MENU)
