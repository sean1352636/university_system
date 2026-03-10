"""Timetable CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.timetable.services.timetable_service import TimetableService
from education_system.college_system.modules.domain.timetable.services.room_service import RoomService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.infrastructure.auth.core import UserAuth


def timetable_menu(auth: UserAuth):
    """Timetable management menu."""
    svc = TimetableService(auth._db_path)
    room_svc = RoomService(auth._db_path)
    course_svc = CourseService(auth._db_path)
    role = auth.current_user.get("role", "student")
    is_admin = role in ("admin", "staff")

    while True:
        print_header("Timetable Management")
        options = []
        if is_admin:
            options.append(("1", "Add Slot"))
        options.extend([
            ("2", "View Course Timetable"),
            ("3", "View Room Schedule"),
        ])
        if is_admin:
            options.extend([
                ("4", "Update Slot"),
                ("5", "Delete Slot"),
            ])
        options.append(("6", "My Timetable"))
        if is_admin:
            options.append(("7", "Generate Full Timetable (Admin)"))
        options.extend([
            ("8", "Room Management"),
            ("9", "Available Rooms"),
            ("A", "Check Student Clashes"),
        ])
        options.append(("0", "Back"))
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1" and is_admin:
            _add_slot(svc, course_svc)
        elif choice == "2":
            _view_course_timetable(svc)
        elif choice == "3":
            _view_room_schedule(svc)
        elif choice == "4" and is_admin:
            _update_slot(svc)
        elif choice == "5" and is_admin:
            _delete_slot(svc)
        elif choice == "6":
            _my_timetable(svc, auth)
        elif choice == "7" and is_admin:
            _generate_full_timetable(svc, auth)
        elif choice == "8":
            _room_management(room_svc)
        elif choice == "9":
            _available_rooms(room_svc)
        elif choice == "A":
            _check_student_clashes(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _add_slot(svc: TimetableService, course_svc: CourseService):
    print_header("Add Timetable Slot")
    try:
        course_id = int(input("Course ID: ").strip())
        day = input("Day (Mon-Fri): ").strip()
        start = input("Start time (HH:MM): ").strip()
        end = input("End time (HH:MM): ").strip()
        room = input("Room: ").strip() or None
        instructor = input("Instructor name: ").strip() or None

        slot = svc.add_slot(course_id, day, start, end, room, instructor)
        print(f"\n  Slot added (ID: {slot['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_course_timetable(svc: TimetableService):
    print_header("Course Timetable")
    try:
        course_id = int(input("Course ID: ").strip())
        slots = svc.get_course_timetable(course_id)
        if not slots:
            print("\n  No timetable slots found.")
            return
        print(f"\n  {'Day':<6} {'Time':<14} {'Room':<12} {'Instructor':<20}")
        print(f"  {'-'*52}")
        for s in slots:
            print(f"  {s['day_of_week']:<6} {s['start_time']}-{s['end_time']:<8} "
                  f"{(s['room'] or '-'):<12} {(s['instructor_name'] or '-'):<20}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_room_schedule(svc: TimetableService):
    print_header("Room Schedule")
    try:
        room = input("Room name: ").strip()
        slots = svc.get_room_schedule(room)
        if not slots:
            print("\n  No slots found for this room.")
            return
        print(f"\n  {'Day':<6} {'Time':<14} {'Course':<12}")
        print(f"  {'-'*32}")
        for s in slots:
            print(f"  {s['day_of_week']:<6} {s['start_time']}-{s['end_time']:<8} "
                  f"{s['course_code']:<12}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_slot(svc: TimetableService):
    print_header("Update Timetable Slot")
    try:
        slot_id = int(input("Slot ID: ").strip())
        print("  (Leave blank to keep current value)")
        day = input("Day (Mon-Fri): ").strip() or None
        start = input("Start time (HH:MM): ").strip() or None
        end = input("End time (HH:MM): ").strip() or None
        room = input("Room: ").strip() or None
        instructor = input("Instructor name: ").strip() or None

        updates = {}
        if day:
            updates["day_of_week"] = day
        if start:
            updates["start_time"] = start
        if end:
            updates["end_time"] = end
        if room:
            updates["room"] = room
        if instructor:
            updates["instructor_name"] = instructor

        slot = svc.update_slot(slot_id, **updates)
        print(f"\n  Slot {slot['id']} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_slot(svc: TimetableService):
    print_header("Delete Timetable Slot")
    try:
        slot_id = int(input("Slot ID: ").strip())
        svc.delete_slot(slot_id)
        print(f"\n  Slot {slot_id} deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _my_timetable(svc: TimetableService, auth: UserAuth):
    print_header("My Timetable")
    try:
        from education_system.college_system.infrastructure.database.db import connect
        conn = connect(auth._db_path)
        try:
            student = conn.execute(
                "SELECT id FROM students WHERE user_id = ?",
                (auth.current_user["user_id"],),
            ).fetchone()
        finally:
            conn.close()

        if not student:
            print("\n  No student record linked to your account.")
            return

        slots = svc.get_student_timetable(student["id"])
        if not slots:
            print("\n  No timetable slots found.")
            return
        print(f"\n  {'Day':<6} {'Time':<14} {'Course':<10} {'Room':<12} {'Instructor':<20}")
        print(f"  {'-'*62}")
        for s in slots:
            print(f"  {s['day_of_week']:<6} {s['start_time']}-{s['end_time']:<8} "
                  f"{s['course_code']:<10} {(s['room'] or '-'):<12} "
                  f"{(s['instructor_name'] or '-'):<20}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _room_management(room_svc: RoomService):
    print_header("Room Management")
    try:
        rooms = room_svc.list_rooms()
        if not rooms:
            print("\n  No rooms found.")
        else:
            print(f"\n  {'ID':<5} {'Code':<12} {'Type':<15} {'Capacity':<10} {'Status':<12}")
            print(f"  {'-'*54}")
            for r in rooms:
                print(f"  {r['id']:<5} {r['room_code']:<12} {r['room_type']:<15} "
                      f"{r['capacity']:<10} {r['status']:<12}")

        print("\n  [1] Create Room  [2] Update Room  [0] Back")
        sub = input("  Choice: ").strip()
        if sub == "1":
            code = input("  Room code: ").strip()
            room_type = input("  Type (classroom/lab/workshop/lecture_hall/it_suite/office/other) [classroom]: ").strip() or "classroom"
            capacity = int(input("  Capacity [30]: ").strip() or "30")
            building = input("  Building: ").strip() or None
            floor = input("  Floor: ").strip() or None
            room = room_svc.create_room(
                room_code=code, room_type=room_type, capacity=capacity,
                building=building, floor=floor,
            )
            print(f"\n  Room created (ID: {room['id']}).")
        elif sub == "2":
            room_id = int(input("  Room ID: ").strip())
            print("  (Leave blank to keep current)")
            capacity = input("  New capacity: ").strip()
            status = input("  New status (active/maintenance/decommissioned): ").strip()
            updates = {}
            if capacity:
                updates["capacity"] = int(capacity)
            if status:
                room_svc.set_room_status(room_id, status)
            if updates:
                room_svc.update_room(room_id, **updates)
            print("\n  Room updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _available_rooms(room_svc: RoomService):
    print_header("Find Available Rooms")
    try:
        day = input("  Day (Mon-Fri): ").strip()
        start = input("  Start time (HH:MM): ").strip()
        end = input("  End time (HH:MM): ").strip()
        min_cap = input("  Minimum capacity [0]: ").strip()
        min_capacity = int(min_cap) if min_cap else 0

        rooms = room_svc.find_available_rooms(day, start, end, min_capacity=min_capacity)
        if not rooms:
            print("\n  No available rooms found.")
            return
        print(f"\n  {'Code':<12} {'Type':<15} {'Capacity':<10} {'Building':<12}")
        print(f"  {'-'*49}")
        for r in rooms:
            print(f"  {r['room_code']:<12} {r['room_type']:<15} "
                  f"{r['capacity']:<10} {(r.get('building') or '-'):<12}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _check_student_clashes(svc: TimetableService):
    print_header("Check Student Timetable Clashes")
    try:
        student_pk = int(input("  Student PK (database ID): ").strip())
        clashes = svc.check_student_clashes(student_pk)
        if not clashes:
            print("\n  No clashes found.")
            return
        print(f"\n  Found {len(clashes)} clash(es):")
        for c in clashes:
            print(f"  - {c['reason']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _generate_full_timetable(svc: TimetableService, auth: UserAuth):
    print_header("Generate Full Timetable")

    if auth.current_user.get("role") != "admin":
        print("\n  Access denied. Admin role required.")
        return

    print("  This will replace ALL existing timetable slots with an auto-generated schedule:")
    print()
    print("    Period 1:  09:00 - 10:00")
    print("    Period 2:  10:00 - 11:00")
    print("    Break:     11:00 - 11:20")
    print("    Period 3:  11:20 - 12:20")
    print("    Lunch:     12:20 - 13:00")
    print("    Period 4:  13:00 - 14:00")
    print("    Period 5:  14:00 - 15:00")
    print()
    print("  Double lessons (2hrs) are added on 2 days per course.")
    print("  Remaining gaps show as Study Periods on student timetables.")
    print()

    confirm = input("  Are you sure? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("\n  Cancelled.")
        return

    try:
        result = svc.generate_full_timetable()
        print(f"\n  Timetable generated successfully!")
        print(f"  Slots created: {result['slots_created']}")
        print(f"  Double lessons added: {result.get('doubles_added', 0)}")
        print(f"  Courses scheduled: {result['courses_scheduled']}/{result['courses_total']}")
        if result["partial"]:
            print(f"  Partially scheduled: {', '.join(result['partial'])}")
        if result["unscheduled"]:
            print(f"  Unscheduled: {', '.join(result['unscheduled'])}")
    except Exception as e:
        print(f"\n  Error: {e}")
