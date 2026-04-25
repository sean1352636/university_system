"""Console menu for tutor groups — mirrors employer_portal_cli.py style."""
from __future__ import annotations

from typing import Any

from education_system.university_system.modules.domain.academics.tutor_groups.services.tutor_group_service import (
    TutorGroupService,
    TutorGroupError,
)


auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _require_login() -> bool:
    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to access tutor groups.")
        return False
    return True


def _list_groups(svc: TutorGroupService) -> None:
    year = input("Academic year filter (Enter for all): ").strip() or None
    programme = input("Programme filter (Enter for all): ").strip() or None
    show_all = input("Include inactive? (y/n, default=n): ").strip().lower() == "y"
    groups = svc.list_groups(
        academic_year=year, programme=programme, active_only=not show_all,
    )
    if not groups:
        print("No tutor groups found.")
        return
    print(f"\n{'ID':<5} {'Name':<22} {'Year':<10} {'Programme':<20} "
          f"{'Lead':<6} {'Cap':<5} {'Pattern':<10} {'Active':<6}")
    print("-" * 90)
    for g in groups:
        print(f"{g['group_id']:<5} "
              f"{(g.get('name') or '')[:22]:<22} "
              f"{(g.get('academic_year') or '-'):<10} "
              f"{(g.get('programme') or '-')[:20]:<20} "
              f"{str(g.get('lead_tutor_id') or '-'):<6} "
              f"{g.get('capacity') or 0:<5} "
              f"{(g.get('meeting_pattern') or '-'):<10} "
              f"{'Yes' if g.get('is_active') else 'No':<6}")
    print(f"\nTotal: {len(groups)}")


def _create_group(svc: TutorGroupService) -> None:
    name = input("Group name: ").strip()
    year = input("Academic year (e.g. 2025/26): ").strip()
    programme = input("Programme: ").strip()
    try:
        lead = int(input("Lead tutor id: ").strip())
        cap = int(input("Capacity (default=20): ").strip() or "20")
    except ValueError:
        print("Error: lead tutor id and capacity must be integers.")
        return
    pattern = input("Meeting pattern (default=weekly): ").strip() or "weekly"
    notes = input("Notes (optional): ").strip()
    try:
        gid = svc.create_group(name, year, programme, lead,
                               capacity=cap, meeting_pattern=pattern, notes=notes)
        print(f"Tutor group #{gid} created.")
    except TutorGroupError as exc:
        print(f"Error: {exc}")


def _update_group(svc: TutorGroupService) -> None:
    try:
        gid = int(input("Group ID: ").strip())
    except ValueError:
        print("Error: invalid id.")
        return
    updates: dict[str, Any] = {}
    for field, prompt in [
        ("name",            "New name (Enter to keep): "),
        ("academic_year",   "New academic year (Enter to keep): "),
        ("programme",       "New programme (Enter to keep): "),
        ("meeting_pattern", "New meeting pattern (Enter to keep): "),
        ("notes",           "New notes (Enter to keep): "),
    ]:
        v = input(prompt).strip()
        if v:
            updates[field] = v
    cap = input("New capacity (Enter to keep): ").strip()
    if cap:
        try:
            updates["capacity"] = int(cap)
        except ValueError:
            print("Error: capacity must be an integer.")
            return
    lead = input("New lead tutor id (Enter to keep): ").strip()
    if lead:
        try:
            updates["lead_tutor_id"] = int(lead)
        except ValueError:
            print("Error: lead tutor id must be an integer.")
            return
    active = input("Active? (y/n/Enter to keep): ").strip().lower()
    if active in ("y", "n"):
        updates["is_active"] = 1 if active == "y" else 0
    if updates:
        try:
            svc.update_group(gid, **updates)
            print("Tutor group updated.")
        except TutorGroupError as exc:
            print(f"Error: {exc}")
    else:
        print("No changes made.")


def _add_member(svc: TutorGroupService) -> None:
    try:
        gid = int(input("Group ID: ").strip())
        sid = int(input("Student ID: ").strip())
        role = input("Role (student/co-tutor/observer, default=student): ").strip() or "student"
        mid = svc.add_member(gid, sid, role=role)
        print(f"Membership #{mid} created.")
    except (TutorGroupError, ValueError) as exc:
        print(f"Error: {exc}")


def _remove_member(svc: TutorGroupService) -> None:
    try:
        gid = int(input("Group ID: ").strip())
        sid = int(input("Student ID: ").strip())
        ld = input("Left date YYYY-MM-DD (blank=today): ").strip() or None
        svc.remove_member(gid, sid, left_date=ld)
        print("Member removed.")
    except (TutorGroupError, ValueError) as exc:
        print(f"Error: {exc}")


def _list_members(svc: TutorGroupService) -> None:
    try:
        gid = int(input("Group ID: ").strip())
    except ValueError:
        print("Error: invalid id.")
        return
    show_all = input("Include left? (y/n, default=n): ").strip().lower() == "y"
    members = svc.list_members(gid, active_only=not show_all)
    if not members:
        print("No members found.")
        return
    print(f"\n{'M.ID':<6} {'Student':<10} {'Role':<10} "
          f"{'Joined':<12} {'Left':<12} {'Active':<6}")
    print("-" * 60)
    for m in members:
        print(f"{m['membership_id']:<6} {m['student_id']:<10} "
              f"{(m.get('role') or '-'):<10} "
              f"{(m.get('joined_date') or '-'):<12} "
              f"{(m.get('left_date') or '-'):<12} "
              f"{'Yes' if m.get('is_active') else 'No':<6}")
    print(f"\nTotal: {len(members)}")


def _assign_tutor(svc: TutorGroupService) -> None:
    try:
        gid = int(input("Group ID: ").strip())
        tid = int(input("Tutor ID: ").strip())
        role = input(
            "Role (personal_tutor/co-tutor/pastoral_lead, default=personal_tutor): ",
        ).strip() or "personal_tutor"
        ad = input("Assigned date YYYY-MM-DD (blank=today): ").strip() or None
        aid = svc.assign_tutor(gid, tid, role=role, assigned_date=ad)
        print(f"Pastoral assignment #{aid} created.")
    except (TutorGroupError, ValueError) as exc:
        print(f"Error: {exc}")


def _end_assignment(svc: TutorGroupService) -> None:
    try:
        aid = int(input("Assignment ID: ").strip())
        ed = input("Ended date YYYY-MM-DD (blank=today): ").strip() or None
        svc.end_assignment(aid, ended_date=ed)
        print("Assignment ended.")
    except (TutorGroupError, ValueError) as exc:
        print(f"Error: {exc}")


def _list_assignments(svc: TutorGroupService) -> None:
    g = input("Group ID filter (Enter for all): ").strip()
    t = input("Tutor ID filter (Enter for all): ").strip()
    show_all = input("Include ended? (y/n, default=n): ").strip().lower() == "y"
    try:
        rows = svc.list_assignments(
            group_id=int(g) if g else None,
            tutor_id=int(t) if t else None,
            active_only=not show_all,
        )
    except (TutorGroupError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    if not rows:
        print("No assignments found.")
        return
    print(f"\n{'ID':<5} {'Group':<6} {'Tutor':<6} {'Role':<16} "
          f"{'Assigned':<12} {'Ended':<12} {'Active':<6}")
    print("-" * 70)
    for a in rows:
        print(f"{a['assignment_id']:<5} {a['group_id']:<6} {a['tutor_id']:<6} "
              f"{(a.get('role') or '-'):<16} "
              f"{(a.get('assigned_date') or '-'):<12} "
              f"{(a.get('ended_date') or '-'):<12} "
              f"{'Yes' if a.get('is_active') else 'No':<6}")
    print(f"\nTotal: {len(rows)}")


def _schedule_meeting(svc: TutorGroupService) -> None:
    try:
        gid = int(input("Group ID: ").strip())
        sa = input("Scheduled at (YYYY-MM-DD HH:MM): ").strip()
        dur = int(input("Duration minutes (default=60): ").strip() or "60")
        loc = input("Location: ").strip()
        agenda = input("Agenda: ").strip()
        mid = svc.schedule_meeting(gid, sa, duration_minutes=dur,
                                   location=loc, agenda=agenda)
        print(f"Meeting #{mid} scheduled.")
    except (TutorGroupError, ValueError) as exc:
        print(f"Error: {exc}")


def _record_meeting(svc: TutorGroupService) -> None:
    try:
        mid = int(input("Meeting ID: ").strip())
        att = int(input("Attendance count: ").strip())
        notes = input("Notes (blank=none): ").strip()
        status = input("Status (held/cancelled, default=held): ").strip() or "held"
        svc.record_meeting(mid, att, notes=notes, status=status)
        print("Meeting recorded.")
    except (TutorGroupError, ValueError) as exc:
        print(f"Error: {exc}")


def _list_meetings(svc: TutorGroupService) -> None:
    try:
        gid = int(input("Group ID: ").strip())
    except ValueError:
        print("Error: invalid id.")
        return
    upcoming = input("Upcoming only? (y/n, default=n): ").strip().lower() == "y"
    rows = svc.list_meetings(gid, upcoming_only=upcoming)
    if not rows:
        print("No meetings found.")
        return
    print(f"\n{'ID':<5} {'When':<18} {'Min':<5} {'Loc':<16} "
          f"{'Att':<4} {'Status':<10}")
    print("-" * 65)
    for m in rows:
        print(f"{m['meeting_id']:<5} "
              f"{(m.get('scheduled_at') or '-'):<18} "
              f"{m.get('duration_minutes') or 0:<5} "
              f"{(m.get('location') or '-')[:16]:<16} "
              f"{str(m.get('attendance_count') if m.get('attendance_count') is not None else '-'):<4} "
              f"{(m.get('status') or '-'):<10}")
    print(f"\nTotal: {len(rows)}")


def _group_summary(svc: TutorGroupService) -> None:
    try:
        gid = int(input("Group ID: ").strip())
        s = svc.group_summary(gid)
    except (TutorGroupError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    g = s["group"]
    print(f"\nTutor Group #{g['group_id']}: {g['name']}")
    print(f"Year: {g.get('academic_year','-')}   Programme: {g.get('programme','-')}")
    print(f"Lead tutor: {g.get('lead_tutor_id','-')}   Capacity: {g.get('capacity',0)}")
    print(f"Pattern: {g.get('meeting_pattern','-')}   Active: "
          f"{'Yes' if g.get('is_active') else 'No'}")
    print(f"Members (active): {s['member_count']}")
    print(f"Assignments (active): {len(s['assignments'])}")
    for a in s["assignments"]:
        print(f"  - #{a['assignment_id']} tutor {a['tutor_id']} "
              f"({a['role']}) since {a['assigned_date']}")
    print(f"\nRecent meetings ({len(s['recent_meetings'])}):")
    for m in s["recent_meetings"]:
        print(f"  - #{m['meeting_id']} {m['scheduled_at']} "
              f"[{m['status']}] att={m.get('attendance_count','-')}")
    print(f"\nUpcoming meetings ({len(s['upcoming_meetings'])}):")
    for m in s["upcoming_meetings"]:
        print(f"  - #{m['meeting_id']} {m['scheduled_at']} "
              f"@ {m.get('location','-')}")


def display_tutor_group_menu() -> None:
    """Top-level tutor groups menu."""
    if not _require_login():
        return
    db_path = getattr(auth, "_db_path", None)
    svc = TutorGroupService(db_path)

    actions = {
        "1":  ("List Tutor Groups",      _list_groups),
        "2":  ("Create Tutor Group",     _create_group),
        "3":  ("Update Tutor Group",     _update_group),
        "4":  ("Add Member",             _add_member),
        "5":  ("Remove Member",          _remove_member),
        "6":  ("List Members",           _list_members),
        "7":  ("Assign Pastoral Tutor",  _assign_tutor),
        "8":  ("End Pastoral Assignment", _end_assignment),
        "9":  ("List Assignments",       _list_assignments),
        "10": ("Schedule Meeting",       _schedule_meeting),
        "11": ("Record Meeting",         _record_meeting),
        "12": ("List Meetings",          _list_meetings),
        "13": ("Group Summary",          _group_summary),
    }
    while True:
        print("\nTutor Groups")
        print("=" * 30)
        for k, (label, _) in actions.items():
            print(f"{k}. {label}")
        print("0. Return to Previous Menu")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        try:
            action[1](svc)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except TutorGroupError as exc:
            print(f"Error: {exc}")
