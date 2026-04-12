from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_create,
    log_read,
    log_update,
)
from education_system.university_system.modules.domain.academics.services.course_management.validation import validate_time_format, validate_days_of_week


# --- Shared helpers for create/update ---

TIME_SLOTS = [f"{h:02d}:00" for h in range(9, 18)]  # 09:00 .. 17:00

DAY_OPTIONS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _pick_time(prompt_label, current=None):
    """Show numbered time slots and return the chosen time string (or None)."""
    print(f"\n{prompt_label}:")
    for i, t in enumerate(TIME_SLOTS, 1):
        marker = " <-- current" if current and t == current else ""
        print(f"  {i}. {t}{marker}")

    while True:
        hint = f" (current: {current})" if current else ""
        raw = input(f"Enter choice 1-{len(TIME_SLOTS)}{hint} (or Enter to {'keep current' if current else 'skip'}): ").strip()
        if not raw:
            return current  # keep current or None
        try:
            idx = int(raw)
            if 1 <= idx <= len(TIME_SLOTS):
                return TIME_SLOTS[idx - 1]
            print("Invalid choice.")
        except ValueError:
            print("Please enter a valid number.")


def _pick_days(current=None):
    """Show numbered day list and accept comma-separated numbers. Returns comma-separated day names."""
    print("\nDays of the week:")
    for i, d in enumerate(DAY_OPTIONS, 1):
        print(f"  {i}. {d}")

    while True:
        hint = f" (current: {current})" if current else ""
        raw = input(f"Enter day numbers comma-separated, e.g. 1,3,5{hint} (or Enter to {'keep current' if current else 'skip'}): ").strip()
        if not raw:
            return current
        try:
            indices = [int(x.strip()) for x in raw.split(',')]
            if all(1 <= idx <= len(DAY_OPTIONS) for idx in indices):
                return ','.join(DAY_OPTIONS[idx - 1] for idx in indices)
            print("Invalid day number(s). Use 1-5.")
        except ValueError:
            print("Please enter comma-separated numbers (e.g. 1,3,5).")


def _pick_classroom(cursor, start_time, end_time, days, semester, year, exclude_schedule_id=None):
    """List rooms available at the requested time slot, return chosen room_number or free text."""
    # Find rooms that are already booked at the same time/days/semester
    booked_query = """
    SELECT DISTINCT cs.classroom FROM course_schedule cs
    WHERE cs.semester = ? AND cs.year = ?
      AND cs.start_time = ? AND cs.end_time = ?
      AND cs.classroom IS NOT NULL
    """
    params = [semester, year, start_time, end_time]

    if exclude_schedule_id:
        booked_query += " AND cs.id != ?"
        params.append(exclude_schedule_id)

    # Also filter by overlapping days if we have day info
    if days:
        day_list = [d.strip() for d in days.split(',')]
        day_conditions = " OR ".join(["cs.days_of_week LIKE ?" for _ in day_list])
        booked_query += f" AND ({day_conditions})"
        params.extend([f"%{d}%" for d in day_list])

    cursor.execute(booked_query, params)
    booked_rooms = {row[0] for row in cursor.fetchall()}

    # Get all available rooms from the rooms table
    cursor.execute("""
    SELECT id, room_number, building, capacity, room_type
    FROM rooms
    WHERE LOWER(status) = 'available' AND is_active = 1
    ORDER BY building, room_number
    """)
    all_rooms = cursor.fetchall()

    available_rooms = [r for r in all_rooms if r[1] not in booked_rooms]

    if available_rooms:
        print(f"\nAvailable Classrooms for {start_time}-{end_time} on {days or 'TBA'}:")
        print(f"  {'#':<4} {'Room':<15} {'Building':<20} {'Capacity':<10} {'Type':<15}")
        print("  " + "-" * 64)
        for i, room in enumerate(available_rooms, 1):
            print(f"  {i:<4} {room[1]:<15} {room[2] or 'N/A':<20} {room[3] or 'N/A':<10} {room[4] or 'N/A':<15}")

        while True:
            raw = input(f"Enter room number 1-{len(available_rooms)} (or Enter to skip): ").strip()
            if not raw:
                return None
            try:
                idx = int(raw)
                if 1 <= idx <= len(available_rooms):
                    return available_rooms[idx - 1][1]  # room_number
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")
    else:
        print("\nNo rooms available for the selected time slot.")
        manual = input("Enter classroom manually (or Enter to skip): ").strip()
        return manual or None


def _pick_instructor(cursor, start_time, end_time, days, semester, year, exclude_schedule_id=None):
    """List instructors not already scheduled at the same time, return chosen instructor_id."""
    # Find instructors already booked at the same slot
    booked_query = """
    SELECT DISTINCT cs.instructor_id FROM course_schedule cs
    WHERE cs.semester = ? AND cs.year = ?
      AND cs.start_time = ? AND cs.end_time = ?
      AND cs.instructor_id IS NOT NULL
    """
    params = [semester, year, start_time, end_time]

    if exclude_schedule_id:
        booked_query += " AND cs.id != ?"
        params.append(exclude_schedule_id)

    if days:
        day_list = [d.strip() for d in days.split(',')]
        day_conditions = " OR ".join(["cs.days_of_week LIKE ?" for _ in day_list])
        booked_query += f" AND ({day_conditions})"
        params.extend([f"%{d}%" for d in day_list])

    cursor.execute(booked_query, params)
    booked_ids = {row[0] for row in cursor.fetchall()}

    cursor.execute("""
    SELECT id, first_name, last_name, department
    FROM instructors
    WHERE LOWER(status) = 'active'
    ORDER BY last_name, first_name
    """)
    all_instructors = cursor.fetchall()

    available = [i for i in all_instructors if i[0] not in booked_ids]

    if not available:
        print("\nNo instructors available for the selected time slot.")
        return None

    print(f"\nAvailable Instructors for {start_time}-{end_time} on {days or 'TBA'}:")
    print(f"  {'#':<4} {'Name':<25} {'Department':<20}")
    print("  " + "-" * 49)
    for i, inst in enumerate(available, 1):
        print(f"  {i:<4} {inst[1] + ' ' + inst[2]:<25} {inst[3] or 'N/A':<20}")

    while True:
        raw = input(f"Enter instructor number 1-{len(available)} (or Enter to skip): ").strip()
        if not raw:
            return None
        try:
            idx = int(raw)
            if 1 <= idx <= len(available):
                return available[idx - 1][0]  # instructor id
            print("Invalid choice.")
        except ValueError:
            print("Please enter a valid number.")


def _send_schedule_email(cursor, course_id, semester, year, start_time, end_time,
                         days, classroom, instructor_id, action_type, change_details=""):
    """Send schedule notification email to the instructor (if assigned)."""
    if not instructor_id:
        return

    try:
        from education_system.university_system.infrastructure.email import send_template_email
        from education_system.university_system.core.defaults import UNIVERSITY_EMAIL_DOMAIN

        # Get course info
        cursor.execute("SELECT course_code, course_name FROM courses WHERE id = ?", (course_id,))
        course_row = cursor.fetchone()
        if not course_row:
            return
        course_code, course_name = course_row[0], course_row[1]

        # Get instructor info
        cursor.execute("SELECT first_name, last_name, email FROM instructors WHERE id = ?", (instructor_id,))
        instr_row = cursor.fetchone()
        if not instr_row:
            return
        instr_first, instr_last, instr_email = instr_row[0], instr_row[1], instr_row[2]

        if not instr_email:
            return

        template_vars = {
            'recipient_name': f"{instr_first} {instr_last}",
            'course_code': course_code,
            'course_name': course_name,
            'semester': semester,
            'year': str(year),
            'days': days or 'TBA',
            'start_time': start_time or 'TBA',
            'end_time': end_time or 'TBA',
            'classroom': classroom or 'TBA',
            'instructor_name': f"{instr_first} {instr_last}",
            'action_type': action_type,
            'action_type_lower': action_type.lower(),
            'change_details': change_details,
        }

        send_template_email(
            'user_management/schedule_notification',
            instr_email,
            template_vars,
        )
        print(f"  Schedule notification email sent to {instr_email}")

    except Exception as e:
        print(f"  Warning: Could not send schedule notification email: {e}")


# --- Main functions ---

@log_create(module="course_management", description="Creating course schedule")
def create_course_schedule(auth):
    """Create a schedule for a course"""
    if not auth or not auth.current_user:
        print("You must be logged in to create schedules.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to create schedules.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show available courses
        cursor.execute("SELECT id, course_code, course_name FROM courses WHERE LOWER(status) = 'active' ORDER BY course_code")
        courses = cursor.fetchall()

        if not courses:
            print("No active courses found.")
            return False

        print("\nAvailable Courses:")
        for idx, course in enumerate(courses, 1):
            print(f"{idx}. {course[1]} - {course[2]}")

        # Select course
        while True:
            raw = input("\nEnter course number to schedule (or Enter to go back): ").strip()
            if not raw:
                return False
            try:
                choice = int(raw)
                if 1 <= choice <= len(courses):
                    course_id = courses[choice - 1][0]
                    selected_course = courses[choice - 1]
                    break
                print("Invalid course number.")
            except ValueError:
                print("Please enter a valid number.")

        # Semester and year
        semester_options = ["Fall", "Spring", "Summer", "Winter"]
        print("\nSelect semester:")
        for i, sem in enumerate(semester_options, 1):
            print(f"{i}. {sem}")

        while True:
            raw = input("Enter choice (1-4, or Enter to go back): ").strip()
            if not raw:
                return False
            try:
                sem_choice = int(raw)
                if 1 <= sem_choice <= 4:
                    semester = semester_options[sem_choice - 1]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        current_year = datetime.now().year
        while True:
            raw = input(f"Enter year (default {current_year}, or Enter to accept default): ").strip()
            if not raw:
                year = current_year
                break
            try:
                year = int(raw)
                if year >= current_year:
                    break
                print("Year must be current year or later.")
            except ValueError:
                print("Please enter a valid year.")

        # Check if schedule already exists
        cursor.execute("SELECT id FROM course_schedule WHERE course_id = ? AND semester = ? AND year = ?",
                      (course_id, semester, year))
        if cursor.fetchone():
            print(f"Schedule already exists for this course in {semester} {year}.")
            return False

        # Start time
        start_time = _pick_time("Select start time")

        # End time
        end_time = _pick_time("Select end time")

        # Validate end > start
        if start_time and end_time and end_time <= start_time:
            print("Warning: End time should be after start time.")

        # Days
        days = _pick_days()

        # Classroom (availability-aware)
        classroom = _pick_classroom(cursor, start_time, end_time, days, semester, year)

        # Instructor (availability-aware)
        instructor_id = _pick_instructor(cursor, start_time, end_time, days, semester, year)

        # Confirm
        print(f"\nSchedule Summary:")
        print(f"  Course: {selected_course[1]} - {selected_course[2]}")
        print(f"  Semester: {semester} {year}")
        print(f"  Time: {start_time or 'TBA'} - {end_time or 'TBA'}")
        print(f"  Days: {days or 'TBA'}")
        print(f"  Classroom: {classroom or 'TBA'}")

        # Show instructor name
        instr_name = "None"
        if instructor_id:
            cursor.execute("SELECT first_name, last_name FROM instructors WHERE id = ?", (instructor_id,))
            instr_row = cursor.fetchone()
            if instr_row:
                instr_name = f"{instr_row[0]} {instr_row[1]}"
        print(f"  Instructor: {instr_name}")

        confirm = input("\nCreate this schedule? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Schedule creation cancelled.")
            return False

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO course_schedule (course_id, semester, year, start_time, end_time,
                                   days_of_week, classroom, instructor_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (course_id, semester, year, start_time or None, end_time or None,
              days or None, classroom or None, instructor_id, timestamp))

        conn.commit()

        print(f"\nSchedule created successfully for {semester} {year}!")

        # Send notification email to instructor
        _send_schedule_email(cursor, course_id, semester, year, start_time, end_time,
                            days, classroom, instructor_id, "Created")

        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()


@log_read(module="course_management", description="Viewing course schedules")
def view_course_schedules(auth):
    """View course schedules"""
    if not auth or not auth.current_user:
        print("You must be logged in to view schedules.")
        return

    if not auth.check_permission('view_courses'):
        print("You don't have permission to view schedules.")
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Filter options
        print("\nSchedule Filters:")
        semester = input("Enter semester (Fall/Spring/Summer/Winter) or press Enter for all: ").strip()
        year_input = input("Enter year or press Enter for current year: ").strip()

        current_year = datetime.now().year
        year = int(year_input) if year_input else current_year

        # Build query
        conditions = ["cs.year = ?"]
        params = [year]

        if semester:
            conditions.append("cs.semester = ?")
            params.append(semester)

        query = """
        SELECT cs.id, c.course_code, c.course_name, cs.semester, cs.year,
               cs.start_time, cs.end_time, cs.days_of_week, cs.classroom,
               COALESCE(i.first_name || ' ' || i.last_name, 'Unassigned') as instructor
        FROM course_schedule cs
        JOIN courses c ON cs.course_id = c.id
        LEFT JOIN instructors i ON cs.instructor_id = i.id
        WHERE """ + " AND ".join(conditions) + """
        ORDER BY cs.semester, c.course_code, cs.start_time
        """

        cursor.execute(query, params)
        schedules = cursor.fetchall()

        if not schedules:
            filter_desc = f"{semester + ' ' if semester else ''}{year}"
            print(f"No schedules found for {filter_desc}.")
            return

        # Group by semester
        current_semester = None
        print(f"\nCourse Schedules for {year}:")
        print("=" * 80)

        for schedule in schedules:
            if current_semester != schedule[3]:
                current_semester = schedule[3]
                print(f"\n{current_semester} {schedule[4]}:")
                print(f"{'Code':<8} {'Name':<25} {'Time':<15} {'Days':<20} {'Room':<12} {'Instructor':<15}")
                print("-" * 95)

            time_display = f"{schedule[5] or 'TBA'}-{schedule[6] or 'TBA'}" if schedule[5] and schedule[6] else "TBA"
            days_display = schedule[7] or "TBA"
            room_display = schedule[8] or "TBA"
            instructor_display = schedule[9]

            # Truncate long names for display
            name_display = schedule[2][:22] + "..." if len(schedule[2]) > 25 else schedule[2]
            days_display = days_display[:17] + "..." if len(days_display) > 20 else days_display
            instructor_display = instructor_display[:12] + "..." if len(instructor_display) > 15 else instructor_display

            print(f"{schedule[1]:<8} {name_display:<25} {time_display:<15} {days_display:<20} {room_display:<12} {instructor_display:<15}")

        # Summary statistics
        cursor.execute("""
        SELECT COUNT(*) as total_schedules,
               COUNT(DISTINCT cs.course_id) as unique_courses,
               COUNT(cs.instructor_id) as assigned_instructors
        FROM course_schedule cs
        WHERE cs.year = ?""" + (" AND cs.semester = ?" if semester else ""),
        params)

        stats = cursor.fetchone()

        print(f"\nSummary:")
        print(f"Total Schedules: {stats[0]}")
        print(f"Unique Courses: {stats[1]}")
        print(f"Assigned Instructors: {stats[2]}")
        print(f"Unassigned Schedules: {stats[0] - stats[2]}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except ValueError:
        print("Invalid year format.")
    finally:
        if conn:
            conn.close()


@log_update(module="course_management", description="Updating course schedule")
def update_schedule(auth):
    """Update course schedule"""
    if not auth or not auth.current_user:
        print("You must be logged in to update schedules.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to update schedules.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show existing schedules
        cursor.execute("""
        SELECT cs.id, c.course_code, c.course_name, cs.semester, cs.year,
               cs.start_time, cs.end_time, cs.days_of_week, cs.classroom,
               COALESCE(i.first_name || ' ' || i.last_name, 'Unassigned') as instructor
        FROM course_schedule cs
        JOIN courses c ON cs.course_id = c.id
        LEFT JOIN instructors i ON cs.instructor_id = i.id
        ORDER BY cs.year DESC, cs.semester, c.course_code
        """)

        schedules = cursor.fetchall()

        if not schedules:
            print("No schedules found.")
            return False

        print("\nExisting Schedules:")
        print(f"{'#':<5} {'Code':<8} {'Name':<20} {'Semester':<10} {'Year':<6} {'Time':<15} {'Days':<15}")
        print("-" * 79)

        for idx, schedule in enumerate(schedules, 1):
            time_str = f"{schedule[5] or 'TBA'}-{schedule[6] or 'TBA'}"
            days_str = schedule[7] or "TBA"
            name_short = schedule[2][:17] + "..." if len(schedule[2]) > 20 else schedule[2]
            days_short = days_str[:12] + "..." if len(days_str) > 15 else days_str

            print(f"{idx:<5} {schedule[1]:<8} {name_short:<20} {schedule[3]:<10} {schedule[4]:<6} {time_str:<15} {days_short:<15}")

        # Select schedule to update
        while True:
            raw = input("\nEnter schedule number to update (or Enter to go back): ").strip()
            if not raw:
                return False
            try:
                choice = int(raw)
                if 1 <= choice <= len(schedules):
                    schedule_id = schedules[choice - 1][0]
                    cursor.execute("SELECT * FROM course_schedule WHERE id = ?", (schedule_id,))
                    current_schedule = cursor.fetchone()
                    if current_schedule:
                        break
                print("Invalid schedule number.")
            except ValueError:
                print("Please enter a valid number.")

        # Current values
        (sid, course_id, semester, year, start_time, end_time, days_of_week,
         classroom, instructor_id, created_at) = current_schedule

        # Get course info for display
        cursor.execute("SELECT course_code, course_name FROM courses WHERE id = ?", (course_id,))
        course_row = cursor.fetchone()
        course_code = course_row[0] if course_row else "?"
        course_name = course_row[1] if course_row else "?"

        print(f"\nUpdating Schedule: {course_code} - {course_name} ({semester} {year})")
        print(f"Current: {start_time or 'TBA'} - {end_time or 'TBA'}, {days_of_week or 'TBA'}, Room: {classroom or 'TBA'}")

        # Start time
        new_start = _pick_time("Select new start time", current=start_time)

        # End time
        new_end = _pick_time("Select new end time", current=end_time)

        # Validate end > start
        if new_start and new_end and new_end <= new_start:
            print("Warning: End time should be after start time.")

        # Days
        new_days = _pick_days(current=days_of_week)

        # Classroom (availability-aware, excluding current schedule)
        new_classroom = _pick_classroom(cursor, new_start, new_end, new_days, semester, year,
                                        exclude_schedule_id=schedule_id)
        if new_classroom is None:
            new_classroom = classroom  # keep current if skipped

        # Instructor (availability-aware, excluding current schedule)
        print(f"\nCurrent instructor ID: {instructor_id or 'None'}")
        print("0. Remove instructor")
        new_instructor_id = _pick_instructor(cursor, new_start, new_end, new_days, semester, year,
                                              exclude_schedule_id=schedule_id)
        if new_instructor_id is None:
            # Check if user wants to remove or keep
            keep = input("Keep current instructor? (y/n, default y): ").strip().lower()
            if keep == 'n':
                new_instructor_id = None
            else:
                new_instructor_id = instructor_id

        # Check that something actually changed
        if (new_start == start_time and new_end == end_time and
                new_days == days_of_week and new_classroom == classroom and
                new_instructor_id == instructor_id):
            print("\nNo changes made. Schedule remains the same.")
            return False

        # Build change details for email
        changes = []
        if new_start != start_time:
            changes.append(f"Start time: {start_time or 'TBA'} -> {new_start or 'TBA'}")
        if new_end != end_time:
            changes.append(f"End time: {end_time or 'TBA'} -> {new_end or 'TBA'}")
        if new_days != days_of_week:
            changes.append(f"Days: {days_of_week or 'TBA'} -> {new_days or 'TBA'}")
        if new_classroom != classroom:
            changes.append(f"Classroom: {classroom or 'TBA'} -> {new_classroom or 'TBA'}")
        if new_instructor_id != instructor_id:
            # Get names for display
            old_name = "None"
            new_name = "None"
            if instructor_id:
                cursor.execute("SELECT first_name, last_name FROM instructors WHERE id = ?", (instructor_id,))
                r = cursor.fetchone()
                if r:
                    old_name = f"{r[0]} {r[1]}"
            if new_instructor_id:
                cursor.execute("SELECT first_name, last_name FROM instructors WHERE id = ?", (new_instructor_id,))
                r = cursor.fetchone()
                if r:
                    new_name = f"{r[0]} {r[1]}"
            changes.append(f"Instructor: {old_name} -> {new_name}")

        change_details = "\nChanges:\n" + "\n".join(f"  - {c}" for c in changes) + "\n"

        # Show summary
        print(f"\nUpdate Summary:")
        for c in changes:
            print(f"  - {c}")

        confirm = input("\nApply these changes? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Update cancelled.")
            return False

        # Update the schedule
        cursor.execute("""
        UPDATE course_schedule
        SET start_time = ?, end_time = ?, days_of_week = ?, classroom = ?, instructor_id = ?
        WHERE id = ?
        """, (new_start, new_end, new_days, new_classroom, new_instructor_id, schedule_id))

        conn.commit()

        print(f"\nSchedule updated successfully!")

        # Email the current instructor (old one if changed)
        if instructor_id and instructor_id != new_instructor_id:
            _send_schedule_email(cursor, course_id, semester, year, new_start, new_end,
                                new_days, new_classroom, instructor_id, "Updated (Unassigned)",
                                change_details)

        # Email the new/current instructor
        if new_instructor_id:
            _send_schedule_email(cursor, course_id, semester, year, new_start, new_end,
                                new_days, new_classroom, new_instructor_id, "Updated",
                                change_details)

        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()
