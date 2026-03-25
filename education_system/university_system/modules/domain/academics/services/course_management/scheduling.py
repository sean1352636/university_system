from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_create,
    log_read,
    log_update,
)
from education_system.university_system.modules.domain.academics.services.course_management.validation import validate_time_format, validate_days_of_week


@log_create(module="course_management", description="Creating course schedule")
def create_course_schedule(auth):
    """Create a schedule for a course"""
    if not auth or not auth.current_user:
        print("You must be logged in to create schedules.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to create schedules.")
        return False

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show available courses
        cursor.execute("SELECT id, course_code, course_name FROM courses WHERE status = 'Active' ORDER BY course_code")
        courses = cursor.fetchall()

        if not courses:
            print("No active courses found.")
            conn.close()
            return False

        print("\nAvailable Courses:")
        for course in courses:
            print(f"{course[0]}. {course[1]} - {course[2]}")

        # Select course
        while True:
            try:
                course_id = int(input("\nEnter course ID to schedule: "))
                if any(c[0] == course_id for c in courses):
                    break
                print("Invalid course ID.")
            except ValueError:
                print("Please enter a valid number.")

        # Semester and year
        semester_options = ["Fall", "Spring", "Summer", "Winter"]
        print("\nSelect semester:")
        for i, sem in enumerate(semester_options, 1):
            print(f"{i}. {sem}")

        while True:
            try:
                sem_choice = int(input("Enter choice (1-4): "))
                if 1 <= sem_choice <= 4:
                    semester = semester_options[sem_choice - 1]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        current_year = datetime.now().year
        while True:
            try:
                year = int(input(f"Enter year (default {current_year}): ") or str(current_year))
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
            conn.close()
            return False

        # Time and days
        while True:
            start_time = input("Enter start time (HH:MM): ").strip()
            if not start_time:
                break
            if validate_time_format(start_time):
                break
            print("Invalid time format. Use HH:MM")

        while True:
            end_time = input("Enter end time (HH:MM): ").strip()
            if not end_time:
                break
            if validate_time_format(end_time):
                break
            print("Invalid time format. Use HH:MM")

        while True:
            days = input("Enter days of week (comma-separated, e.g., Monday,Wednesday,Friday): ").strip()
            if not days:
                break
            if validate_days_of_week(days):
                break
            print("Invalid days format. Use full day names separated by commas.")

        classroom = input("Enter classroom/location: ").strip()

        # Select instructor
        cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE status = 'Active' ORDER BY last_name")
        instructors = cursor.fetchall()

        instructor_id = None
        if instructors:
            print("\nAvailable Instructors:")
            for instructor in instructors:
                print(f"{instructor[0]}. {instructor[1]} {instructor[2]}")

            instr_choice = input("Enter instructor ID (or press Enter to skip): ").strip()
            if instr_choice:
                try:
                    instructor_id = int(instr_choice)
                    if not any(i[0] == instructor_id for i in instructors):
                        print("Invalid instructor ID. Proceeding without instructor.")
                        instructor_id = None
                except ValueError:
                    print("Invalid instructor ID. Proceeding without instructor.")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO course_schedule (course_id, semester, year, start_time, end_time,
                                   days_of_week, classroom, instructor_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (course_id, semester, year, start_time or None, end_time or None,
              days or None, classroom or None, instructor_id, timestamp))

        conn.commit()
        conn.close()

        print(f"\nSchedule created successfully for {semester} {year}!")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False


@log_read(module="course_management", description="Viewing course schedules")
def view_course_schedules(auth):
    """View course schedules"""
    if not auth or not auth.current_user:
        print("You must be logged in to view schedules.")
        return

    if not auth.check_permission('view_courses'):
        print("You don't have permission to view schedules.")
        return

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
            conn.close()
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

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
    except ValueError:
        print("Invalid year format.")


@log_update(module="course_management", description="Updating course schedule")
def update_schedule(auth):
    """Update course schedule"""
    if not auth or not auth.current_user:
        print("You must be logged in to update schedules.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to update schedules.")
        return False

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
            conn.close()
            return False

        print("\nExisting Schedules:")
        print(f"{'ID':<5} {'Code':<8} {'Name':<20} {'Semester':<10} {'Year':<6} {'Time':<15} {'Days':<15}")
        print("-" * 79)

        for schedule in schedules:
            time_str = f"{schedule[5] or 'TBA'}-{schedule[6] or 'TBA'}"
            days_str = schedule[7] or "TBA"
            name_short = schedule[2][:17] + "..." if len(schedule[2]) > 20 else schedule[2]
            days_short = days_str[:12] + "..." if len(days_str) > 15 else days_str

            print(f"{schedule[0]:<5} {schedule[1]:<8} {name_short:<20} {schedule[3]:<10} {schedule[4]:<6} {time_str:<15} {days_short:<15}")

        # Select schedule to update
        while True:
            try:
                schedule_id = int(input("\nEnter schedule ID to update: "))
                cursor.execute("SELECT * FROM course_schedule WHERE id = ?", (schedule_id,))
                current_schedule = cursor.fetchone()
                if current_schedule:
                    break
                print("Invalid schedule ID.")
            except ValueError:
                print("Please enter a valid number.")

        # Current values
        (id, course_id, semester, year, start_time, end_time, days_of_week, classroom, instructor_id, created_at) = current_schedule

        print(f"\nUpdating Schedule ID {schedule_id}")
        print("Enter new values (leave blank to keep current):")

        # Start time
        while True:
            new_start = input(f"Start time [{start_time or 'TBA'}]: ").strip()
            if not new_start:
                new_start = start_time
                break
            if validate_time_format(new_start):
                break
            print("Invalid time format. Use HH:MM")

        # End time
        while True:
            new_end = input(f"End time [{end_time or 'TBA'}]: ").strip()
            if not new_end:
                new_end = end_time
                break
            if validate_time_format(new_end):
                break
            print("Invalid time format. Use HH:MM")

        # Days of week
        while True:
            new_days = input(f"Days of week [{days_of_week or 'TBA'}]: ").strip()
            if not new_days:
                new_days = days_of_week
                break
            if validate_days_of_week(new_days):
                break
            print("Invalid days format. Use full day names separated by commas.")

        # Classroom
        new_classroom = input(f"Classroom [{classroom or 'TBA'}]: ").strip()
        if not new_classroom:
            new_classroom = classroom

        # Instructor
        cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE status = 'Active'")
        instructors = cursor.fetchall()

        print(f"\nCurrent instructor: {instructor_id or 'None'}")
        if instructors:
            print("Available instructors:")
            print("0. Remove instructor")
            for instructor in instructors:
                print(f"{instructor[0]}. {instructor[1]} {instructor[2]}")

            instr_choice = input("Enter instructor ID (or press Enter to keep current): ").strip()
            if instr_choice:
                try:
                    new_instructor_id = int(instr_choice)
                    if new_instructor_id == 0:
                        new_instructor_id = None
                    elif not any(i[0] == new_instructor_id for i in instructors):
                        print("Invalid instructor ID. Keeping current.")
                        new_instructor_id = instructor_id
                except ValueError:
                    print("Invalid instructor ID. Keeping current.")
                    new_instructor_id = instructor_id
            else:
                new_instructor_id = instructor_id
        else:
            new_instructor_id = instructor_id

        # Update the schedule
        cursor.execute("""
        UPDATE course_schedule
        SET start_time = ?, end_time = ?, days_of_week = ?, classroom = ?, instructor_id = ?
        WHERE id = ?
        """, (new_start, new_end, new_days, new_classroom, new_instructor_id, schedule_id))

        conn.commit()
        conn.close()

        print(f"\nSchedule updated successfully!")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False
