from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.systems.university.infrastructure.utils.activity_logger import log_update
from education_system.systems.university.domains.academics.domain.services.course_management.courses import (
    _fit,
    resolve_course_id,
)


@log_update(module="course_management", description="Updating course status")
def manage_course_status(auth):
    """Manage course status (Active, Inactive, Archived, Cancelled)"""
    if not auth or not auth.current_user:
        print("You must be logged in to manage course status.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to manage course status.")
        return False

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show all courses with current status
        cursor.execute("SELECT id, course_code, course_name, status FROM courses ORDER BY course_code")
        courses = cursor.fetchall()

        if not courses:
            print("No courses found.")
            conn.close()
            return False

        print("\nAll Courses:")
        print(f"{'ID':<12} {'Code':<10} {'Name':<30} {'Status':<12}")
        print("-" * 67)
        for course in courses:
            print(f"{_fit(course[0], 12):<12} {_fit(course[1], 10):<10} {_fit(course[2], 30):<30} {_fit(course[3], 12):<12}")

        # Select course by id or code (courses.id is TEXT, never an integer)
        while True:
            course_id_input = input("\nEnter course ID or code to update status (or press Enter to go back): ").strip()
            if not course_id_input:
                conn.close()
                return False
            course_id = resolve_course_id(cursor, course_id_input)
            selected_course = next((c for c in courses if str(c[0]) == str(course_id)), None)
            if selected_course:
                break
            print("No course matches that ID or code.")

        current_status = selected_course[3]
        print(f"\nCurrent status: {current_status}")

        # Status options
        status_options = ["Active", "Inactive", "Archived", "Cancelled"]
        print("\nSelect new status:")
        for i, status in enumerate(status_options, 1):
            print(f"{i}. {status}")

        while True:
            status_input = input("Enter choice (1-4, or press Enter to go back): ").strip()
            if not status_input:
                conn.close()
                return False
            try:
                status_choice = int(status_input)
                if 1 <= status_choice <= 4:
                    new_status = status_options[status_choice - 1]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        if new_status == current_status:
            print("Status is already set to this value.")
            conn.close()
            return False

        # Confirmation and reason
        reason = input("Enter reason for status change (optional): ").strip()

        confirm = input(f"\nChange status from '{current_status}' to '{new_status}'? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Status change cancelled.")
            conn.close()
            return False

        # Update status
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Canonical write, shared with the GUI status dialogs and the API.
        # The service normalises casing, so a status entered as "Active" no
        # longer becomes invisible to student enrolment.
        from education_system.systems.university.application.course_lifecycle_service import (
            CourseLifecycleService,
            CourseValidationError,
        )
        try:
            new_status = CourseLifecycleService().set_status(
                selected_course[0], new_status,
                actor_id=str((auth.current_user or {}).get('id', 'unknown')),
                reason="Status changed via course management CLI",
            ).status
        except CourseValidationError as exc:
            for field, message in exc.errors.items():
                print(f"Error: {field} {message}")
            conn.close()
            return False

        # Log the change in history (wrap in try/except in case table doesn't exist)
        try:
            changed_by = 'system'
            if auth and auth.current_user:
                if isinstance(auth.current_user, dict):
                    changed_by = auth.current_user.get('username', 'system')
                else:
                    changed_by = str(auth.current_user)
            cursor.execute('''
            INSERT INTO course_history (course_id, field_name, old_value, new_value, changed_by, changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (selected_course[0], 'status', current_status, new_status,
                  changed_by, timestamp))
        except sqlite3.OperationalError:
            pass  # Table may not exist

        conn.commit()
        conn.close()

        print("\nStatus updated successfully!")
        print(f"Course: {selected_course[1]} - {selected_course[2]}")
        print(f"Status changed from '{current_status}' to '{new_status}'")
        if reason:
            print(f"Reason: {reason}")

        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False
