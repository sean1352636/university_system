"""Parents Evening CLI for managing evenings and slots."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.parents_evening.services.parents_evening_service import ParentsEveningService


def parents_evening_menu(auth: UserAuth):
    svc = ParentsEveningService(auth._db_path)

    while True:
        print_header("Parents Evening")
        options = [
            ("1", "List Evenings"),
            ("2", "Create Evening"),
            ("3", "View Slots"),
            ("4", "Add Slot"),
            ("5", "Book Slot"),
            ("6", "My Bookings"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            evenings = svc.list_evenings()
            for e in evenings:
                print(f"  [{e['id']}] {e.get('title', '')} - {e.get('event_date', '')} ({e.get('status', '')})")
            if not evenings:
                print("  No evenings found.")
        elif choice == "2":
            try:
                title = input("  Title: ").strip()
                date = input("  Date (YYYY-MM-DD): ").strip()
                user_id = auth.current_user["user_id"]
                e = svc.create_evening(title, date, created_by=user_id)
                print(f"\n  Evening #{e['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            try:
                eid = int(input("  Evening ID: ").strip())
                slots = svc.list_slots(eid)
                for s in slots:
                    status = s.get("status", "available")
                    teacher = s.get("teacher_name", s.get("teacher_id", ""))
                    print(f"  [{s['id']}] {s.get('slot_time', '')} - Teacher: {teacher} [{status}]")
                if not slots:
                    print("  No slots found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            try:
                eid = int(input("  Evening ID: ").strip())
                tid = int(input("  Teacher ID: ").strip())
                time = input("  Time (HH:MM): ").strip()
                s = svc.create_slot(eid, tid, time)
                print(f"\n  Slot #{s['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            try:
                slot_id = int(input("  Slot ID: ").strip())
                parent_id = int(input("  Parent User ID: ").strip())
                sid = int(input("  Student ID: ").strip())
                svc.book_slot(slot_id, parent_id, sid)
                print("  Slot booked.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "6":
            try:
                user_id = auth.current_user["user_id"]
                bookings = svc.get_parent_bookings(user_id)
                for b in bookings:
                    print(f"  [{b['id']}] {b.get('evening_title', '')} - {b.get('event_date', '')} {b.get('slot_time', '')} with {b.get('teacher_name', '')}")
                if not bookings:
                    print("  No bookings found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
