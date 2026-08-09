"""CLI handlers for form-tutor assignments and meetings."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.pastoral.form_tutors import (
    form_tutors as data,
)
from education_system.systems.secondary.domain.pastoral.form_tutors.form_tutors import (
    ROLES, ASSIGNMENT_STATUSES, MEETING_TYPES,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_assignments(rows: list[data.TutorAssignment]) -> None:
    if not rows:
        print("  (no assignments)")
        return
    print(f"  {'ID':<4} {'AYear':<8} {'Yr':<3} {'Form':<6} "
          f"{'Tutor':<22} {'Role':<10} {'Status':<10} "
          f"{'Start':<10} {'End':<10} {'Email':<24}")
    print(f"  {'-'*4} {'-'*8} {'-'*3} {'-'*6} {'-'*22} {'-'*10} "
          f"{'-'*10} {'-'*10} {'-'*10} {'-'*24}")
    for a in rows:
        print(f"  {a.assignment_id:<4} {a.academic_year:<8} "
              f"{a.year_group:<3} {a.form_group:<6} "
              f"{a.tutor_name[:22]:<22} {a.role:<10} "
              f"{a.status:<10} {a.start_date:<10} "
              f"{(a.end_date or '-'):<10} "
              f"{(a.contact_email or '-')[:24]:<24}")


def _print_meetings(rows: list[data.TutorMeeting]) -> None:
    if not rows:
        print("  (no meetings)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Type':<16} {'Form':<6} "
          f"{'Tutor':<22} {'Agenda':<32}")
    print(f"  {'-'*5} {'-'*10} {'-'*16} {'-'*6} {'-'*22} {'-'*32}")
    for m in rows:
        form = (f"{m.year_group or '-'}{m.form_group or ''}").strip()
        print(f"  {m.meeting_id:<5} {m.meeting_date:<10} "
              f"{m.meeting_type[:16]:<16} {form:<6} "
              f"{(m.tutor_name or '-')[:22]:<22} "
              f"{(m.agenda or '-')[:32]:<32}")


@_safe
def open_form_tutors() -> None:
    logger.debug("CLI: open_form_tutors")
    while True:
        print("\n  ── Form Tutors ──")
        print("  Assignments")
        print("    1) New assignment")
        print("    2) List assignments")
        print("    3) View assignment + meetings")
        print("    4) Edit assignment")
        print("    5) End assignment")
        print("    6) Delete assignment")
        print("  Meetings")
        print("    7) Log meeting")
        print("    8) List meetings (filters)")
        print("    9) Edit meeting")
        print("   10) Delete meeting")
        print("  Reports")
        print("   11) Cohort summary")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_assignment, "2": _list_assignments,
            "3": _view, "4": _edit_assignment,
            "5": _end_assignment, "6": _delete_assignment,
            "7": _log_meeting, "8": _list_meetings,
            "9": _edit_meeting, "10": _delete_meeting,
            "11": _summary,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_assignment(existing: data.TutorAssignment | None = None
                         ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["year_group"]    = ask(f"Year ({'/'.join(YEAR_GROUPS)})",
                                existing.year_group if existing
                                else None)
    f["form_group"]    = ask("Form (e.g. 7A)",
                                existing.form_group if existing
                                else None)
    f["academic_year"] = ask("Academic year (YYYY/YY)",
                                existing.academic_year if existing
                                else None)
    f["tutor_name"]    = ask("Tutor name",
                                existing.tutor_name if existing
                                else None)
    f["role"]          = ask(f"Role ({'/'.join(ROLES)})",
                                existing.role if existing else "Tutor")
    f["contact_email"] = ask("Contact email",
                                existing.contact_email if existing
                                else None)
    f["start_date"]    = ask("Start date (YYYY-MM-DD, blank = today)",
                                existing.start_date if existing
                                else None)
    f["end_date"]      = ask("End date (YYYY-MM-DD, blank ok)",
                                existing.end_date if existing
                                else None)
    f["status"]        = ask(f"Status ({'/'.join(ASSIGNMENT_STATUSES)})",
                                existing.status if existing
                                else "Active")
    f["notes"]         = ask("Notes",
                                existing.notes if existing else None)
    return f


@_safe
def _new_assignment() -> None:
    print("\n  ── New Tutor Assignment ──")
    fields = _collect_assignment()
    a = data.create_assignment(fields)
    print(f"  Created assignment #{a.assignment_id}: "
          f"Yr{a.year_group}/{a.form_group} — {a.tutor_name} "
          f"({a.role}, {a.status})")


@_safe
def _list_assignments() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    fg = _prompt("  Form (blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    tutor = _prompt("  Tutor (blank): ") or None
    status = _prompt(
        f"  Status ({'/'.join(ASSIGNMENT_STATUSES)}, blank): ") or None
    role = _prompt(f"  Role ({'/'.join(ROLES)}, blank): ") or None
    rows = data.list_assignments(year_group=yg, form_group=fg,
                                   academic_year=ay,
                                   tutor_name=tutor,
                                   status=status, role=role)
    print(f"\n  {len(rows)} assignment(s):")
    _print_assignments(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id(label: str) -> int | None:
    raw = _prompt(f"  {label}: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _view() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    s = data.assignment_summary(aid)
    a = s["assignment"]
    print(f"\n  ── Assignment #{a.assignment_id} ──")
    print(f"  Class:    Yr{a.year_group}/{a.form_group}    "
          f"({a.academic_year})")
    print(f"  Tutor:    {a.tutor_name} ({a.role})")
    print(f"  Email:    {a.contact_email or '-'}")
    print(f"  Period:   {a.start_date} → {a.end_date or 'open'}")
    print(f"  Status:   {a.status}")
    print(f"  Notes:    {a.notes or '-'}")
    print(f"\n  Meetings: {s['meeting_count']}")
    if s["by_type"]:
        print("  By type: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_type"].items()))
    _print_meetings(s["meetings"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_assignment() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    existing = data.get_assignment(aid)
    if existing is None:
        print("  No assignment with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_assignment(existing)
    a = data.update_assignment(aid, fields)
    print(f"  Updated assignment #{a.assignment_id} "
          f"(status {a.status})")


@_safe
def _end_assignment() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    end_date = _prompt(
        "  End date (YYYY-MM-DD, blank = today): ") or None
    a = data.end_assignment(aid, end_date=end_date)
    print(f"  Ended assignment #{a.assignment_id} on {a.end_date}.")


@_safe
def _delete_assignment() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        print("  No assignment with that ID.")
        return
    confirm = _prompt(
        f"  Delete assignment {a.tutor_name} on Yr{a.year_group}/"
        f"{a.form_group} and ALL its meetings? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_assignment(aid)
    print(f"  Deleted assignment #{aid}.")


@_safe
def _log_meeting() -> None:
    aid = _ask_id("Assignment ID")
    if aid is None:
        return
    if data.get_assignment(aid) is None:
        print("  No assignment with that ID.")
        return
    f: dict[str, Any] = {"assignment_id": aid}
    f["meeting_date"] = _prompt(
        "  Meeting date (YYYY-MM-DD, blank = today): ") or None
    f["meeting_type"] = _prompt(
        f"  Type ({'/'.join(MEETING_TYPES)}) [Form time]: ") or "Form time"
    f["pupils_present"] = _prompt("  Pupils present: ") or None
    f["agenda"]         = _prompt("  Agenda: ") or None
    f["decisions"]      = _prompt("  Decisions: ") or None
    f["follow_up_actions"] = _prompt("  Follow-up actions: ") or None
    f["notes"]          = _prompt("  Notes: ") or None
    m = data.add_meeting(f)
    print(f"  Logged meeting #{m.meeting_id} ({m.meeting_type})")


@_safe
def _list_meetings() -> None:
    aid_raw = _prompt("  Assignment ID (blank for all): ")
    aid = None
    if aid_raw:
        try:
            aid = int(aid_raw)
        except ValueError:
            print("  Assignment ID must be a number.")
            return
    mtype = _prompt(
        f"  Type ({'/'.join(MEETING_TYPES)}, blank): ") or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    rows = data.list_meetings(assignment_id=aid, meeting_type=mtype,
                                date_from=df, date_to=dt)
    print(f"\n  {len(rows)} meeting(s):")
    _print_meetings(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_meeting() -> None:
    mid = _ask_id("Meeting ID")
    if mid is None:
        return
    existing = data.get_meeting(mid)
    if existing is None:
        print("  No meeting with that ID.")
        return

    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {
        "meeting_date":      ask("Date", existing.meeting_date),
        "meeting_type":      ask(
            f"Type ({'/'.join(MEETING_TYPES)})",
            existing.meeting_type),
        "pupils_present":    ask("Pupils present",
                                    existing.pupils_present),
        "agenda":            ask("Agenda", existing.agenda),
        "decisions":         ask("Decisions", existing.decisions),
        "follow_up_actions": ask("Follow-up actions",
                                    existing.follow_up_actions),
        "notes":             ask("Notes", existing.notes),
    }
    m = data.update_meeting(mid, f)
    print(f"  Updated meeting #{m.meeting_id}")


@_safe
def _delete_meeting() -> None:
    mid = _ask_id("Meeting ID")
    if mid is None:
        return
    m = data.get_meeting(mid)
    if m is None:
        print("  No meeting with that ID.")
        return
    confirm = _prompt(
        f"  Delete meeting #{mid} ({m.meeting_date}, "
        f"{m.meeting_type})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_meeting(mid)
    print(f"  Deleted meeting #{mid}.")


@_safe
def _summary() -> None:
    ay = _prompt("  Academic year (blank): ") or None
    s = data.cohort_summary(academic_year=ay)
    print(f"\n  Assignments: {s['total']}    "
          f"Unique tutors: {s['tutors']}    "
          f"Unique forms: {s['forms']}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    if s["by_role"]:
        print("  By role:   "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_role"].items()))
    if s["by_year"]:
        print("  By year:")
        for k in sorted(s["by_year"].keys()):
            print(f"    Yr {k}: {s['by_year'][k]}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Form Tutors": open_form_tutors}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching form_tutors CLI label: %s", label)
    handler()
    return True
