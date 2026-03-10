"""Pastoral CLI for managing notes, wellbeing, and LAC records."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.pastoral.services.pastoral_service import PastoralService


def pastoral_menu(auth: UserAuth):
    svc = PastoralService(auth._db_path)

    while True:
        print_header("Pastoral Care")
        options = [
            ("1", "Add Pastoral Note"),
            ("2", "View Student Notes"),
            ("3", "Record Wellbeing Check"),
            ("4", "View Wellbeing Records"),
            ("5", "LAC Records"),
            ("6", "Add LAC Record"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            try:
                sid = int(input("  Student ID: ").strip())
                category = input("  Category (general/academic/personal/attendance): ").strip() or "general"
                content = input("  Content: ").strip()
                conf = input("  Confidential? (y/n): ").strip().lower() == "y"
                user_id = auth.current_user["user_id"]
                n = svc.add_note(sid, user_id, category, content, is_confidential=1 if conf else 0)
                print(f"\n  Note #{n['id']} added.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "2":
            try:
                sid = int(input("  Student ID: ").strip())
                notes = svc.list_notes(student_id=sid)
                for n in notes:
                    conf = " [CONFIDENTIAL]" if n.get("is_confidential") else ""
                    print(f"  [{n['id']}] {n.get('category', '')} - {n.get('created_at', '')}{conf}")
                    print(f"    {n.get('content', '')[:80]}")
                if not notes:
                    print("  No notes found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            try:
                sid = int(input("  Student ID: ").strip())
                score = int(input("  Mood Score (1-10): ").strip())
                concerns = input("  Concerns: ").strip() or None
                support = input("  Support Offered: ").strip() or None
                user_id = auth.current_user["user_id"]
                r = svc.record_wellbeing(sid, user_id, score, concerns=concerns, support_offered=support)
                print(f"\n  Wellbeing check #{r['id']} recorded.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            try:
                sid = int(input("  Student ID: ").strip())
                records = svc.list_wellbeing(student_id=sid)
                for r in records:
                    print(f"  [{r['id']}] Score: {r.get('mood_score', '')} - {r.get('check_date', '')} - {r.get('concerns', '')}")
                if not records:
                    print("  No records found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            records = svc.list_lac_records()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                print(f"  [{r['id']}] {name} - {r.get('local_authority', '')} ({r.get('care_status', '')})")
            if not records:
                print("  No LAC records found.")
        elif choice == "6":
            try:
                sid = int(input("  Student ID: ").strip())
                la = input("  Local Authority: ").strip()
                sw = input("  Social Worker: ").strip() or None
                r = svc.create_lac_record(sid, la, social_worker_name=sw)
                print(f"\n  LAC record #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
