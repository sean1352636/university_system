"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_department_schedule(scheduler, department):
    """Display schedule for all instructors in a department"""
    conn = get_connection(scheduler.db_path, row_factory=False)
    cursor = conn.cursor()

    cursor.execute('''
    SELECT id, first_name, last_name FROM instructors
    WHERE department = ? AND is_active = 1
    ORDER BY last_name, first_name
    ''', (department,))

    instructors = cursor.fetchall()

    if not instructors:
        print(f"No active instructors found in department: {department}")
        conn.close()
        return

    print(f"\nSchedule for {department} Department:")
    print("=" * 100)

    for instructor in instructors:
        instructor_id, first_name, last_name = instructor
        print(f"\n{first_name} {last_name} (ID: {instructor_id}):")
        print("-" * 80)

        cursor.execute('''
        SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        WHERE ms.instructor_id = ?
        ORDER BY ms.day_of_week, ms.start_time
        ''', (instructor_id,))

        schedules = cursor.fetchall()

        if schedules:
            print(f"{'Module':<10} {'Day':<10} {'Time':<15} {'Room':<15} {'Type':<10}")
            print("-" * 70)

            for schedule in schedules:
                module_code, day, start, end, building, room, session_type = schedule
                time_slot = f"{start}-{end}"
                room_str = f"{building}-{room}" if building and room else "TBA"
                print(f"{module_code:<10} {day:<10} {time_slot:<15} {room_str:<15} {session_type:<10}")
        else:
            print("No scheduled classes")

    conn.close()
    print("=" * 100)
