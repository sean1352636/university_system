from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_update


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
        print(f"{'ID':<5} {'Code':<10} {'Name':<30} {'Status':<12}")
        print("-" * 57)
        for course in courses:
            print(f"{course[0]:<5} {course[1]:<10} {course[2]:<30} {course[3]:<12}")

        # Select course (handle both integer and string IDs)
        while True:
            course_id_input = input("\nEnter course ID to update status (or press Enter to go back): ").strip()
            if not course_id_input:
                conn.close()
                return False
            # Try to convert to int, but also accept string IDs
            try:
                course_id = int(course_id_input)
            except ValueError:
                course_id = course_id_input
            selected_course = next((c for c in courses if str(c[0]) == str(course_id)), None)
            if selected_course:
                break
            print("Invalid course ID.")

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

        # Try with updated_at first, fall back to just status if column doesn't exist
        try:
            cursor.execute("UPDATE courses SET status = ?, updated_at = ? WHERE id = ?",
                          (new_status, timestamp, selected_course[0]))
        except sqlite3.OperationalError:
            cursor.execute("UPDATE courses SET status = ? WHERE id = ?",
                          (new_status, selected_course[0]))

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

        print(f"\nStatus updated successfully!")
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
