"""Departments in the terminal.

The old Departments menu keeps its numbering (its section headings took
numbers 1, 12 and 19): 2 List all, 3 Active only, 4 Over budget, 5 Filter,
6 View, 7 New department, 8 Edit department, 9 Change status, 10 Add spend,
11 Delete department, 13 List memberships, 14 Add member, 15 Edit
membership, 16 End membership, 17 Delete membership, 18 Per-staff,
20 Summary. New: 21 Subjects in a department, 22 Add a subject, 23 Remove a
subject, 24 Import departments from subjects, 25 Overview, 26 Meetings,
27 New meeting, 28 Edit meeting / minutes, 29 Show minutes, 30 Add action,
31 Set action status, 32 Delete meeting, 33 History, 34 Export CSV.
Rules live in :mod:`modules.staff.domain.departments`.
"""

from __future__ import annotations

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.staff.cli.staff_directory_cli import (
    Field,
    ask_fields,
)
from education_system.systems.secondary.modules.staff.domain import departments as DP
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (DP.ValidationError, DP.PermissionDenied, DP.NotFound)
_int = prompts.ask_int

_DEPT: list[Field] = [
    ("name", "Name", None), ("code", "Code", None), ("faculty", "Faculty", DP.FACULTIES),
    ("head_id", "Head of dept (staff code)", None),
    ("second_id", "Deputy head (staff code)", None), ("location", "Location", None),
    ("budget_year", "Budget year", None), ("budget_total", "Budget total (£)", None),
    ("budget_allocated", "Budget allocated (£)", None),
    ("budget_spent", "Budget spent (£)", None), ("aims", "Aims", None),
    ("policies", "Policies", None), ("status", "Status", DP.STATUSES), ("notes", "Notes", None)]
_MEMBER: list[Field] = [
    ("role_in_department", "Role", DP.DEPT_ROLES), ("is_primary", "Primary department", "bool"),
    ("joined_on", "Joined on (blank = today)", None), ("left_on", "Left on", None),
    ("notes", "Notes", None)]
_MEETING: list[Field] = [
    ("meeting_date", "Date (blank = today)", None), ("title", "Title", None),
    ("attendees", "Present", None), ("apologies", "Apologies", None),
    ("agenda", "Agenda", None), ("minutes", "Minutes", None)]


def _table(rows: list[DP.Department]) -> None:
    if not rows:
        print("\n  (no departments)")
        return
    print(f"\n  {'ID':<4} {'Name':<24} {'Code':<6} {'Faculty':<22} {'Head':<18} {'Members':>7} "
          f"{'Budget':<20} Status")
    for d in rows:
        print(f"  {d.department_id:<4} {d.name[:24]:<24} {(d.code or '')[:6]:<6} "
              f"{d.faculty[:22]:<22} {(d.head_name or '')[:18]:<18} {d.member_count:>7} "
              f"{d.budget_text + (' OVER' if d.budget_over else ''):<20} {d.status}")


def _dept() -> DP.Department | None:
    ref = _prompt("  Department (id or name): ")
    d = DP.find(ref) if ref else None
    if ref and d is None:
        print(f"  ✗ No department {ref}")
    return d


def _list_all(_p: Principal) -> None:
    _table(DP.list_departments())


def _active(_p: Principal) -> None:
    _table(DP.list_departments(active_only=True))


def _over(_p: Principal) -> None:
    _table(DP.list_departments(over_budget=True))


def _filter(_p: Principal) -> None:
    fac = prompts.pick("Faculty (blank = all)", DP.FACULTIES)
    st = prompts.pick("Status (blank = all)", DP.STATUSES)
    _table(DP.list_departments(faculty=fac or None, status=st or None,
                               name=_prompt("  Name contains: ")))


def _view(_p: Principal) -> None:
    d = _dept()
    if d is None:
        return
    print(f"\n  #{d.department_id} {d.name} ({d.code or '-'}) - {d.faculty}, {d.status}")
    for label, v in (("Head", d.head_name), ("Deputy", d.second_name), ("Location", d.location),
                     ("Budget", f"{d.budget_text} ({d.budget_year or 'no year'}), remaining "
                                f"{d.budget_remaining}" if d.budget_total is not None else None),
                     ("Aims", d.aims), ("Policies", d.policies), ("Notes", d.notes)):
        if v:
            print(f"    {label + ':':<10} {v}")
    print("    Subjects: " + (", ".join(s.label for s in DP.subjects_for(d.department_id))
                              or "(none)"))
    _members_table(DP.list_memberships(d.department_id))


def _new(p: Principal) -> None:
    d = DP.create(ask_fields(_DEPT), actor=p)
    print(f"  ✓ Created #{d.department_id} {d.name}")


def _edit(p: Principal) -> None:
    d = _dept()
    if d:
        print("  (Enter keeps a value, '-' clears it)")
        DP.update(d.department_id, ask_fields(_DEPT, d), actor=p)
        print("  ✓ Saved.")


def _status(p: Principal) -> None:
    d = _dept()
    if d:
        st = prompts.pick("Status", DP.STATUSES, d.status)
        DP.set_status(d.department_id, st or d.status, actor=p)
        print("  ✓ Saved.")


def _spend(p: Principal) -> None:
    d = _dept()
    if d:
        d = DP.add_spend(d.department_id, amount=_prompt("  Amount (£, negative = refund): "),
                         actor=p)
        print(f"  ✓ Spent now {d.budget_text}" + (" - OVER BUDGET" if d.budget_over else ""))


def _delete(p: Principal) -> None:
    d = _dept()
    if d and _yes(f"  Delete {d.name} and its memberships?"):
        DP.delete(d.department_id, actor=p)
        print("  ✓ Deleted.")


def _members_table(rows: list[DP.Membership]) -> None:
    if not rows:
        print("    (no members)")
        return
    print(f"    {'ID':<5} {'Staff':<26} {'Role':<22} {'Prim':<5} {'Joined':<11} Left")
    for m in rows:
        print(f"    {m.membership_id:<5} {m.staff_name[:26]:<26} {m.role_in_department[:22]:<22} "
              f"{'yes' if m.is_primary else '':<5} {m.joined_on:<11} {m.left_on or ''}")


def _memberships(_p: Principal) -> None:
    d = _dept()
    if d:
        _members_table(DP.list_memberships(d.department_id))


def _add_member(p: Principal) -> None:
    d = _dept()
    if d:
        ref = _prompt("  Staff (code / username): ")
        m = DP.add_member(d.department_id, {"staff_id": ref, **ask_fields(_MEMBER)}, actor=p)
        print(f"  ✓ Added {m.staff_name} as {m.role_in_department}")


def _membership() -> DP.Membership | None:
    mid = _int("  Membership ID: ")
    return DP.get_membership(mid) if mid else None


def _edit_member(p: Principal) -> None:
    m = _membership()
    if m:
        DP.update_membership(m.membership_id, ask_fields(_MEMBER, m), actor=p)
        print("  ✓ Saved.")


def _end_member(p: Principal) -> None:
    m = _membership()
    if m:
        DP.end_membership(m.membership_id, _prompt("  Left on (blank = today): ") or None,
                          actor=p)
        print("  ✓ Ended (kept with a left date).")


def _delete_member(p: Principal) -> None:
    m = _membership()
    if m and _yes(f"  Delete {m.staff_name}'s membership record?"):
        DP.delete_membership(m.membership_id, actor=p)
        print("  ✓ Deleted.")


def _per_staff(_p: Principal) -> None:
    m = SD.find(_prompt("  Staff (code / username): "))
    if m is None:
        print("  ✗ No such member of staff")
        return
    for x in DP.memberships_for_staff(m.staff_id):
        print(f"    {x.department_name:<24} {x.role_in_department:<22} "
              f"{'primary' if x.is_primary else '':<8} {x.joined_on} {x.left_on or ''}")


def _summary(_p: Principal) -> None:
    s = DP.summary()
    print(f"\n  Departments: {s['total']}  Active: {s['active']}  Members: {s['members']}")
    print(f"  Budget: £{s['budget_spent']:,.2f} spent of £{s['budget_total']:,.2f}  "
          f"Over budget: {s['over_budget']}")
    if s["without_head"]:
        print("  ⚠ No head: " + ", ".join(s["without_head"]))
    print("\n  By faculty:")
    for k, n in s["by_faculty"].items():
        print(f"    {k:<26}: {n}")
    print("\n  By status:")
    for k, n in s["by_status"].items():
        print(f"    {k:<14}: {n}")


def _subjects(_p: Principal) -> None:
    d = _dept()
    if d:
        for s in DP.subjects_for(d.department_id):
            print(f"    {s.code:<8} {s.name}")


def _add_subject(p: Principal) -> None:
    d = _dept()
    if d:
        free = DP.unassigned_subjects()
        print("  Not in a department: " + (", ".join(s.code for s in free) or "(none)"))
        s = S.get_by_code(_prompt("  Subject code: "))
        if s is None:
            print("  ✗ No such subject")
            return
        DP.assign_subject(d.department_id, s.subject_id, actor=p)
        print(f"  ✓ {s.name} is now in {d.name}")


def _remove_subject(p: Principal) -> None:
    d = _dept()
    if d:
        s = S.get_by_code(_prompt("  Subject code: "))
        if s:
            DP.remove_subject(d.department_id, s.subject_id, actor=p)
            print("  ✓ Removed.")


def _import(p: Principal) -> None:
    made = DP.import_from_subjects(actor=p)
    print("  ✓ Made: " + ", ".join(d.name for d in made) if made
          else "  Every department named on a subject already exists.")


def _overview(p: Principal) -> None:
    d = _dept()
    if d is None:
        return
    o = DP.overview(d.department_id, actor=p)
    c = o["counts"]
    print(f"\n  {d.name}: head {d.head_name or '-'}, 2nd {d.second_name or '-'}")
    print(f"  Staff {c['staff']} ({c['teaching_staff']} teaching, {c['fte']} FTE), subjects "
          f"{c['subjects']}, groups {c['groups']}, pupil places {c['pupil_places']}, lessons/"
          f"week {c['lessons_per_week']}, open actions {c['open_actions']} "
          f"({c['overdue_actions']} overdue)")
    _members_table(o["members"])
    for g in o["groups"]:
        print(f"    {g.group.code:<10} Yr {g.group.year_group:<3} {g.pupils:>3} pupils  "
              f"{g.group.teacher_name or g.group.teacher_username or ''}")


def _meetings(_p: Principal) -> None:
    d = _dept()
    if d:
        for mt in DP.list_meetings(d.department_id):
            n = len(DP.list_actions(meeting_id=mt.meeting_id, open_only=True))
            print(f"    #{mt.meeting_id:<4} {mt.meeting_date}  {mt.title}  ({n} open action(s))")


def _new_meeting(p: Principal) -> None:
    d = _dept()
    if d:
        mt = DP.add_meeting(d.department_id, ask_fields(_MEETING), actor=p)
        print(f"  ✓ Meeting #{mt.meeting_id} saved.")


def _meeting() -> DP.Meeting | None:
    mid = _int("  Meeting ID: ")
    return DP.get_meeting(mid) if mid else None


def _edit_meeting(p: Principal) -> None:
    mt = _meeting()
    if mt:
        DP.update_meeting(mt.meeting_id, ask_fields(_MEETING, mt), actor=p)
        print("  ✓ Saved.")


def _minutes(_p: Principal) -> None:
    mt = _meeting()
    if mt:
        print("\n" + "\n".join("  " + x for x in DP.minutes_text(mt.meeting_id).splitlines()))


def _add_action(p: Principal) -> None:
    mt = _meeting()
    if mt:
        a = DP.add_action(mt.meeting_id, {"description": _prompt("  Action: "),
                                          "owner": _prompt("  Owner (staff code, blank ok): "),
                                          "due_date": _prompt("  Due date (blank ok): ")},
                          actor=p)
        print(f"  ✓ Action #{a.action_id} added.")


def _action_status(p: Principal) -> None:
    aid = _int("  Action ID: ")
    if aid:
        st = prompts.pick("Status", DP.ACTION_STATUSES, "Done")
        DP.set_action_status(aid, st or "Done", actor=p)
        print("  ✓ Saved.")


def _delete_meeting(p: Principal) -> None:
    mt = _meeting()
    if mt and _yes(f"  Delete the meeting of {mt.meeting_date} and its actions?"):
        DP.delete_meeting(mt.meeting_id, actor=p)
        print("  ✓ Deleted.")


def _history(_p: Principal) -> None:
    d = _dept()
    if d:
        for h in DP.history(d.department_id):
            print(f"  {h['at']}  {h['actor']:<12} {h['action']:<15} "
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(p: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. departments.csv): ")
    if path:
        print(f"  Exported {DP.export_csv(path, actor=p)} department(s).")


_OPTIONS = {"2": _list_all, "3": _active, "4": _over, "5": _filter, "6": _view, "7": _new,
            "8": _edit, "9": _status, "10": _spend, "11": _delete, "13": _memberships,
            "14": _add_member, "15": _edit_member, "16": _end_member, "17": _delete_member,
            "18": _per_staff, "20": _summary, "21": _subjects, "22": _add_subject,
            "23": _remove_subject, "24": _import, "25": _overview, "26": _meetings,
            "27": _new_meeting, "28": _edit_meeting, "29": _minutes, "30": _add_action,
            "31": _action_status, "32": _delete_meeting, "33": _history, "34": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("departments.view")
        print("\n── Departments ──")
        print("      ── Departments ──\n   2) List all\n   3) Active only\n   4) Over budget"
              "\n   5) Filter\n   6) View\n   7) New department\n   8) Edit department"
              "\n   9) Change status\n  10) Add spend\n  11) Delete department"
              "\n      ── Members ──\n  13) List memberships\n  14) Add member"
              "\n  15) Edit membership\n  16) End membership\n  17) Delete membership"
              "\n  18) Per-staff\n      ──\n  20) Summary")
        print("  More")
        print("  21) Subjects in a department\n  22) Add a subject\n  23) Remove a subject"
              "\n  24) Import departments from subjects\n  25) Overview\n  26) Meetings"
              "\n  27) New meeting\n  28) Edit meeting / minutes\n  29) Show minutes"
              "\n  30) Add action\n  31) Set action status\n  32) Delete meeting"
              "\n  33) History\n  34) Export CSV")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            prompts.problem(e)
        except OSError as e:
            print(f"\n  ✗ {e}")
        _pause()
