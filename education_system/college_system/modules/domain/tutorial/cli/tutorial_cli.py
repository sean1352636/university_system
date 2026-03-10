"""Tutorial System CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.tutorial.services.tutorial_service import TutorialService
from education_system.college_system.infrastructure.auth.core import UserAuth


def tutorial_menu(auth: UserAuth):
    """Tutorial System management menu."""
    svc = TutorialService(auth._db_path)

    while True:
        print_header("Tutorial System")
        options = [
            ("1", "List Assignments"),
            ("2", "View Assignment"),
            ("3", "New Assignment"),
            ("4", "Update Assignment"),
            ("5", "End Assignment"),
            ("6", "List Sessions"),
            ("7", "New Session"),
            ("8", "Complete Session"),
            ("9", "List Records"),
            ("A", "New Record"),
            ("B", "Update Record"),
            ("C", "Follow-Ups Due"),
            ("D", "Tutor Group Students"),
            ("E", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "0":
            break
        elif choice == "1":
            _list_assignments(svc)
        elif choice == "2":
            _view_assignment(svc)
        elif choice == "3":
            _new_assignment(svc)
        elif choice == "4":
            _update_assignment(svc)
        elif choice == "5":
            _end_assignment(svc)
        elif choice == "6":
            _list_sessions(svc)
        elif choice == "7":
            _new_session(svc)
        elif choice == "8":
            _complete_session(svc)
        elif choice == "9":
            _list_records(svc)
        elif choice == "A":
            _new_record(svc)
        elif choice == "B":
            _update_record(svc)
        elif choice == "C":
            _follow_ups(svc)
        elif choice == "D":
            _tutor_group_students(svc)
        elif choice == "E":
            _statistics(svc)
        else:
            print("\n  Invalid option.")


# ── Assignments ────────────────────────────────────────────────────────

def _list_assignments(svc):
    print_header("Tutor Assignments")
    try:
        status = input("  Filter by status (active/ended/transferred) [all]: ").strip() or None
        group = input("  Filter by tutor group [all]: ").strip() or None
        records = svc.list_assignments(status=status, tutor_group=group)
        if not records:
            print("\n  No assignments found.")
            return
        print(f"\n  {'ID':<5} {'Student':<20} {'Tutor':<20} {'Year':<10} {'Group':<10} {'Status'}")
        print(f"  {'-'*70}")
        for r in records:
            student = f"{r.get('student_first', '')} {r.get('student_last', '')}".strip() or str(r['student_id'])
            tutor = f"{r.get('tutor_first', '')} {r.get('tutor_last', '')}".strip() or str(r['tutor_id'])
            print(f"  {r['id']:<5} {student:<20} {tutor:<20} "
                  f"{(r.get('academic_year') or '-'):<10} "
                  f"{(r.get('tutor_group') or '-'):<10} {r['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_assignment(svc):
    try:
        aid = int(input("  Assignment ID: ").strip())
        r = svc.get_assignment(aid)
        if not r:
            print("\n  Assignment not found.")
            return
        student = f"{r.get('student_first', '')} {r.get('student_last', '')}".strip() or str(r['student_id'])
        tutor = f"{r.get('tutor_first', '')} {r.get('tutor_last', '')}".strip() or str(r['tutor_id'])
        print(f"\n  ID:            {r['id']}")
        print(f"  Student:       {student} (ID: {r['student_id']})")
        print(f"  Tutor:         {tutor} (ID: {r['tutor_id']})")
        print(f"  Academic Year: {r.get('academic_year') or '-'}")
        print(f"  Tutor Group:   {r.get('tutor_group') or '-'}")
        print(f"  Status:        {r['status']}")
        print(f"  Created:       {r.get('created_at') or '-'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_assignment(svc):
    print_header("New Tutor Assignment")
    try:
        student_id = int(input("  Student PK: ").strip())
        tutor_id = int(input("  Tutor PK: ").strip())
        academic_year = input("  Academic Year (e.g. 2025/26): ").strip() or None
        tutor_group = input("  Tutor Group: ").strip() or None
        kwargs = {}
        if academic_year:
            kwargs["academic_year"] = academic_year
        if tutor_group:
            kwargs["tutor_group"] = tutor_group
        record = svc.create_assignment(student_id, tutor_id, **kwargs)
        print(f"\n  Assignment created (ID: {record['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_assignment(svc):
    try:
        aid = int(input("  Assignment ID: ").strip())
        print("  Leave blank to keep current value.")
        academic_year = input("  Academic Year: ").strip() or None
        tutor_group = input("  Tutor Group: ").strip() or None
        status = input("  Status (active/ended/transferred): ").strip() or None
        updates = {}
        if academic_year:
            updates["academic_year"] = academic_year
        if tutor_group:
            updates["tutor_group"] = tutor_group
        if status:
            updates["status"] = status
        if not updates:
            print("\n  No changes provided.")
            return
        svc.update_assignment(aid, **updates)
        print("\n  Assignment updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _end_assignment(svc):
    try:
        aid = int(input("  Assignment ID: ").strip())
        svc.end_assignment(aid)
        print("\n  Assignment ended.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Sessions ───────────────────────────────────────────────────────────

def _list_sessions(svc):
    print_header("Tutorial Sessions")
    try:
        status = input("  Filter by status (scheduled/completed/cancelled) [all]: ").strip() or None
        group = input("  Filter by tutor group [all]: ").strip() or None
        sessions = svc.list_sessions(status=status, tutor_group=group)
        if not sessions:
            print("\n  No sessions found.")
            return
        print(f"\n  {'ID':<5} {'Tutor':<18} {'Group':<10} {'Date':<12} {'Type':<12} {'Topic':<20} {'Status'}")
        print(f"  {'-'*80}")
        for r in sessions:
            tutor = f"{r.get('tutor_first', '')} {r.get('tutor_last', '')}".strip() or str(r['tutor_id'])
            topic = (r.get("topic") or "-")[:18]
            print(f"  {r['id']:<5} {tutor:<18} {(r.get('tutor_group') or '-'):<10} "
                  f"{r['session_date']:<12} {(r.get('session_type') or 'group'):<12} "
                  f"{topic:<20} {r['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_session(svc):
    print_header("New Tutorial Session")
    try:
        tutor_id = int(input("  Tutor PK: ").strip())
        session_date = input("  Session Date (YYYY-MM-DD): ").strip()
        if not session_date:
            print("\n  Session date is required.")
            return
        tutor_group = input("  Tutor Group: ").strip() or None
        session_type = input("  Type (group/1to1/assembly/enrichment/careers) [group]: ").strip() or "group"
        topic = input("  Topic: ").strip() or None
        resources = input("  Resources: ").strip() or None
        notes = input("  Notes: ").strip() or None
        kwargs = {"session_type": session_type}
        if tutor_group:
            kwargs["tutor_group"] = tutor_group
        if topic:
            kwargs["topic"] = topic
        if resources:
            kwargs["resources"] = resources
        if notes:
            kwargs["notes"] = notes
        session = svc.create_session(tutor_id, session_date, **kwargs)
        print(f"\n  Session created (ID: {session['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _complete_session(svc):
    try:
        sid = int(input("  Session ID: ").strip())
        notes = input("  Completion notes (optional): ").strip() or None
        svc.complete_session(sid, notes=notes)
        print("\n  Session completed.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Records ────────────────────────────────────────────────────────────

def _list_records(svc):
    print_header("Tutorial Records")
    try:
        sid_str = input("  Filter by student PK [all]: ").strip()
        student_id = int(sid_str) if sid_str else None
        mtype = input("  Filter by type (1to1/progress_review/pastoral/target_setting/careers/other) [all]: ").strip() or None
        records = svc.list_records(student_id=student_id, meeting_type=mtype)
        if not records:
            print("\n  No records found.")
            return
        print(f"\n  {'ID':<5} {'Student':<18} {'Tutor':<18} {'Date':<12} {'Type':<16} {'F/U'}")
        print(f"  {'-'*72}")
        for r in records:
            student = f"{r.get('student_first', '')} {r.get('student_last', '')}".strip() or str(r['student_id'])
            tutor = f"{r.get('tutor_first', '')} {r.get('tutor_last', '')}".strip() or str(r['tutor_id'])
            follow = "Yes" if r.get("follow_up_required") else "No"
            print(f"  {r['id']:<5} {student:<18} {tutor:<18} "
                  f"{r['meeting_date']:<12} {(r.get('meeting_type') or '1to1'):<16} {follow}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_record(svc):
    print_header("New Tutorial Record")
    try:
        student_id = int(input("  Student PK: ").strip())
        tutor_id = int(input("  Tutor PK: ").strip())
        meeting_date = input("  Meeting Date (YYYY-MM-DD): ").strip()
        if not meeting_date:
            print("\n  Meeting date is required.")
            return
        meeting_type = input("  Type (1to1/progress_review/pastoral/target_setting/careers/other) [1to1]: ").strip() or "1to1"
        session_id_str = input("  Session ID (optional): ").strip()
        discussion = input("  Discussion Notes: ").strip() or None
        targets = input("  Targets Set: ").strip() or None
        concerns = input("  Student Concerns: ").strip() or None
        follow_str = input("  Follow-up Required? (y/n) [n]: ").strip().lower()
        follow_up = 1 if follow_str in ("y", "yes") else 0
        follow_notes = None
        if follow_up:
            follow_notes = input("  Follow-up Notes: ").strip() or None

        kwargs = {"meeting_type": meeting_type, "follow_up_required": follow_up}
        if session_id_str:
            kwargs["session_id"] = int(session_id_str)
        if discussion:
            kwargs["discussion_notes"] = discussion
        if targets:
            kwargs["targets_set"] = targets
        if concerns:
            kwargs["student_concerns"] = concerns
        if follow_notes:
            kwargs["follow_up_notes"] = follow_notes

        record = svc.create_record(student_id, tutor_id, meeting_date, **kwargs)
        print(f"\n  Record created (ID: {record['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_record(svc):
    try:
        rid = int(input("  Record ID: ").strip())
        print("  Leave blank to keep current value.")
        meeting_date = input("  Meeting Date (YYYY-MM-DD): ").strip() or None
        meeting_type = input("  Type (1to1/progress_review/pastoral/target_setting/careers/other): ").strip() or None
        discussion = input("  Discussion Notes: ").strip() or None
        targets = input("  Targets Set: ").strip() or None
        concerns = input("  Student Concerns: ").strip() or None
        follow_str = input("  Follow-up Required? (y/n/blank): ").strip().lower()
        follow_notes = input("  Follow-up Notes: ").strip() or None

        updates = {}
        if meeting_date:
            updates["meeting_date"] = meeting_date
        if meeting_type:
            updates["meeting_type"] = meeting_type
        if discussion:
            updates["discussion_notes"] = discussion
        if targets:
            updates["targets_set"] = targets
        if concerns:
            updates["student_concerns"] = concerns
        if follow_str in ("y", "yes"):
            updates["follow_up_required"] = 1
        elif follow_str in ("n", "no"):
            updates["follow_up_required"] = 0
        if follow_notes:
            updates["follow_up_notes"] = follow_notes

        if not updates:
            print("\n  No changes provided.")
            return
        svc.update_record(rid, **updates)
        print("\n  Record updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _follow_ups(svc):
    print_header("Follow-Ups Due")
    try:
        tid_str = input("  Filter by tutor PK [all]: ").strip()
        tutor_id = int(tid_str) if tid_str else None
        records = svc.get_follow_ups(tutor_id=tutor_id)
        if not records:
            print("\n  No follow-ups pending.")
            return
        print(f"\n  {'ID':<5} {'Student':<18} {'Tutor':<18} {'Date':<12} {'Type':<14} {'Notes'}")
        print(f"  {'-'*80}")
        for r in records:
            student = f"{r.get('student_first', '')} {r.get('student_last', '')}".strip() or str(r['student_id'])
            tutor = f"{r.get('tutor_first', '')} {r.get('tutor_last', '')}".strip() or str(r['tutor_id'])
            notes = (r.get("follow_up_notes") or "-")[:25]
            print(f"  {r['id']:<5} {student:<18} {tutor:<18} "
                  f"{r['meeting_date']:<12} {(r.get('meeting_type') or '1to1'):<14} {notes}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _tutor_group_students(svc):
    print_header("Tutor Group Students")
    try:
        group = input("  Tutor Group: ").strip()
        if not group:
            print("\n  Tutor group is required.")
            return
        students = svc.get_tutor_group(group)
        if not students:
            print(f"\n  No active students in group '{group}'.")
            return
        print(f"\n  Students in group '{group}':")
        print(f"\n  {'ID':<5} {'Student Ref':<12} {'Name'}")
        print(f"  {'-'*40}")
        for r in students:
            name = f"{r.get('student_first', '')} {r.get('student_last', '')}".strip() or "-"
            print(f"  {r['student_id']:<5} {(r.get('student_ref') or '-'):<12} {name}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _statistics(svc):
    print_header("Tutorial Statistics")
    try:
        stats = svc.get_stats()
        print(f"\n  Assignments")
        print(f"    Total:           {stats['total_assignments']}")
        print(f"    Active:          {stats['active_assignments']}")
        print(f"    Tutor Groups:    {stats['tutor_groups_count']}")
        print(f"\n  Sessions")
        print(f"    Total:           {stats['total_sessions']}")
        print(f"    Completed:       {stats['completed_sessions']}")
        st = stats.get("by_session_type", {})
        if st:
            print(f"    By Type:")
            for k, v in st.items():
                print(f"      {k:<14} {v}")
        print(f"\n  Records")
        print(f"    Total:           {stats['total_records']}")
        mt = stats.get("by_meeting_type", {})
        if mt:
            print(f"    By Type:")
            for k, v in mt.items():
                print(f"      {k:<16} {v}")
        print(f"    Follow-Ups Due:  {stats['follow_ups_pending']}")
    except Exception as e:
        print(f"\n  Error: {e}")
