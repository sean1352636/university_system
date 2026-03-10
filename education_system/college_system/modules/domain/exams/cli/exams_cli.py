"""Exams CLI for managing exam entries, timetable, access, and results."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.exams.services.exams_service import ExamsService


def exams_menu(auth: UserAuth):
    svc = ExamsService(auth._db_path)

    while True:
        print_header("Exams & Assessment")
        options = [
            ("1", "List Exam Entries"),
            ("2", "New Exam Entry"),
            ("3", "View Exam Timetable"),
            ("4", "Add Timetable Slot"),
            ("5", "Access Arrangements"),
            ("6", "New Access Arrangement"),
            ("7", "View Results"),
            ("8", "Record Result"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            sid = input("  Student ID (or Enter for all): ").strip()
            entries = svc.list_entries(student_id=int(sid) if sid else None)
            for e in entries:
                name = f"{e.get('first_name', '')} {e.get('last_name', '')}".strip() or str(e.get("student_id", ""))
                print(f"  [{e['id']}] {name} - {e.get('exam_board', '')} {e.get('subject', '')} ({e.get('status', '')})")
            if not entries:
                print("  No entries found.")
        elif choice == "2":
            try:
                sid = int(input("  Student ID: ").strip())
                board = input("  Exam Board: ").strip()
                subject = input("  Subject: ").strip()
                level = input("  Level (A-Level/BTEC/GCSE): ").strip()
                e = svc.create_entry(sid, board, subject, level)
                print(f"\n  Entry #{e['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            date = input("  Date (or Enter for all): ").strip() or None
            slots = svc.list_timetable(exam_date=date)
            for s in slots:
                print(f"  [{s['id']}] {s.get('exam_date', '')} {s.get('start_time', '')} - {s.get('subject', '')} ({s.get('duration_mins', '')}m) Room: {s.get('room', '')}")
            if not slots:
                print("  No timetable slots found.")
        elif choice == "4":
            try:
                board = input("  Exam Board: ").strip()
                subject = input("  Subject: ").strip()
                component = input("  Component Code: ").strip()
                date = input("  Date (YYYY-MM-DD): ").strip()
                time = input("  Start Time (HH:MM): ").strip()
                duration = int(input("  Duration (mins): ").strip())
                room = input("  Room: ").strip() or None
                s = svc.create_timetable_slot(board, subject, component, date, time, duration, room=room)
                print(f"\n  Slot #{s['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            sid = input("  Student ID (or Enter for all): ").strip()
            arrangements = svc.list_access_arrangements(student_id=int(sid) if sid else None)
            for a in arrangements:
                name = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() or str(a.get("student_id", ""))
                extra = f"+{a.get('extra_time_percent', 0)}%" if a.get("extra_time_percent") else ""
                print(f"  [{a['id']}] {name} - {a.get('arrangement_type', '')} {extra}")
            if not arrangements:
                print("  No arrangements found.")
        elif choice == "6":
            try:
                sid = int(input("  Student ID: ").strip())
                atype = input("  Arrangement Type: ").strip()
                extra = input("  Extra Time % (or Enter): ").strip()
                a = svc.create_access_arrangement(sid, atype,
                    extra_time_percent=int(extra) if extra else None)
                print(f"\n  Arrangement #{a['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "7":
            sid = input("  Student ID (or Enter for all): ").strip()
            results = svc.list_results(student_id=int(sid) if sid else None)
            for r in results:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                print(f"  [{r['id']}] {name} - {r.get('subject', '')} ({r.get('qualification_level', '')}): {r.get('grade', '')}")
            if not results:
                print("  No results found.")
        elif choice == "8":
            try:
                sid = int(input("  Student ID: ").strip())
                board = input("  Exam Board: ").strip()
                subject = input("  Subject: ").strip()
                level = input("  Level: ").strip()
                grade = input("  Grade: ").strip()
                r = svc.record_result(sid, board, subject, level, grade)
                print(f"\n  Result #{r['id']} recorded.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
