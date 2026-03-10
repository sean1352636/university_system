"""Cover CLI for managing cover/substitution arrangements."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.cover.services.cover_service import CoverService


def cover_menu(auth: UserAuth):
    svc = CoverService(auth._db_path)

    while True:
        print_header("Cover Arrangements")
        options = [
            ("1", "Today's Cover"),
            ("2", "List All Arrangements"),
            ("3", "New Arrangement"),
            ("4", "Update Arrangement"),
            ("5", "Delete Arrangement"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            arrangements = svc.get_today_cover()
            for a in arrangements:
                print(f"  [{a['id']}] P{a.get('period', '')} - Absent: {a.get('absent_staff_name', '')} Cover: {a.get('cover_staff_name', '')} Course: {a.get('course_name', '')} [{a.get('status', '')}]")
            if not arrangements:
                print("  No cover arrangements for today.")
        elif choice == "2":
            date = input("  Date (or Enter for all): ").strip() or None
            arrangements = svc.list_arrangements(cover_date=date)
            for a in arrangements:
                print(f"  [{a['id']}] {a.get('cover_date', '')} P{a.get('period', '')} - {a.get('absent_staff_name', '')} -> {a.get('cover_staff_name', '')} [{a.get('status', '')}]")
            if not arrangements:
                print("  No arrangements found.")
        elif choice == "3":
            try:
                absent = int(input("  Absent Staff ID: ").strip())
                cover = input("  Cover Staff ID (or Enter): ").strip()
                period = input("  Period: ").strip() or None
                course = input("  Course ID (or Enter): ").strip()
                room = input("  Room: ").strip() or None
                reason = input("  Reason: ").strip() or None
                work = input("  Work Set: ").strip() or None
                a = svc.create_arrangement(absent,
                    cover_staff_id=int(cover) if cover else None,
                    period=period,
                    course_id=int(course) if course else None,
                    room=room, reason=reason, work_set=work)
                print(f"\n  Arrangement #{a['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            try:
                aid = int(input("  Arrangement ID: ").strip())
                status = input("  Status (pending/confirmed/completed/cancelled): ").strip()
                cover = input("  Cover Staff ID (or Enter to skip): ").strip()
                kwargs = {"status": status}
                if cover:
                    kwargs["cover_staff_id"] = int(cover)
                svc.update_arrangement(aid, **kwargs)
                print("  Arrangement updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            try:
                aid = int(input("  Arrangement ID: ").strip())
                confirm = input("  Confirm delete? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_arrangement(aid)
                    print("  Arrangement deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
