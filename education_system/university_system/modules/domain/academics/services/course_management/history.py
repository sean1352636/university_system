from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_read


@log_read(module="course_management", description="Viewing course history")
def view_course_history(auth):
    """View historical changes to courses"""
    if not auth or not auth.current_user:
        print("You must be logged in to view course history.")
        return

    if not auth.check_permission('view_courses'):
        print("You don't have permission to view course history.")
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nCourse History Viewer")
        print("====================")

        # Option to view specific course or all changes
        view_option = input("Enter course ID for specific history, or press Enter for all recent changes: ").strip()

        if view_option:
            try:
                course_id = int(view_option)

                # Get course info
                cursor.execute("SELECT course_code, course_name FROM courses WHERE id = ?", (course_id,))
                course_info = cursor.fetchone()

                if not course_info:
                    print("Course not found.")
                    return

                print(f"\nHistory for {course_info[0]} - {course_info[1]}:")
                print("=" * 60)

                # Get history for specific course
                cursor.execute("""
                SELECT field_name, old_value, new_value, changed_by, changed_at
                FROM course_history
                WHERE course_id = ?
                ORDER BY changed_at DESC
                """, (course_id,))

                history = cursor.fetchall()

                if not history:
                    print("No history found for this course.")
                    return

                print(f"{'Date/Time':<20} {'Field':<20} {'Old Value':<20} {'New Value':<20} {'Changed By':<15}")
                print("-" * 95)

                for entry in history:
                    field, old_val, new_val, changed_by, changed_at = entry
                    old_display = str(old_val)[:17] + "..." if old_val and len(str(old_val)) > 20 else str(old_val or "")
                    new_display = str(new_val)[:17] + "..." if new_val and len(str(new_val)) > 20 else str(new_val or "")
                    print(f"{changed_at:<20} {field:<20} {old_display:<20} {new_display:<20} {changed_by:<15}")

            except ValueError:
                print("Invalid course ID.")
                return

        else:
            # Show recent changes across all courses
            print("\nRecent Course Changes (Last 50):")
            print("=" * 80)

            cursor.execute("""
            SELECT c.course_code, c.course_name, ch.field_name, ch.old_value,
                   ch.new_value, ch.changed_by, ch.changed_at
            FROM course_history ch
            JOIN courses c ON ch.course_id = c.id
            ORDER BY ch.changed_at DESC
            LIMIT 50
            """)

            recent_changes = cursor.fetchall()

            if not recent_changes:
                print("No history found.")
                return

            print(f"{'Course':<12} {'Field':<15} {'Old Value':<15} {'New Value':<15} {'User':<12} {'Date':<12}")
            print("-" * 81)

            for change in recent_changes:
                code, name, field, old_val, new_val, user, date = change
                old_display = str(old_val)[:12] + "..." if old_val and len(str(old_val)) > 15 else str(old_val or "")
                new_display = str(new_val)[:12] + "..." if new_val and len(str(new_val)) > 15 else str(new_val or "")
                date_display = date.split()[0]  # Just the date part

                print(f"{code:<12} {field:<15} {old_display:<15} {new_display:<15} {user:<12} {date_display:<12}")

        # Statistics
        cursor.execute("""
        SELECT
            COUNT(*) as total_changes,
            COUNT(DISTINCT course_id) as courses_modified,
            COUNT(DISTINCT changed_by) as users_involved
        FROM course_history
        """)

        stats = cursor.fetchone()

        print(f"\nHistory Statistics:")
        print(f"Total Changes: {stats[0]}")
        print(f"Courses Modified: {stats[1]}")
        print(f"Users Involved: {stats[2]}")

        # Most active fields
        cursor.execute("""
        SELECT field_name, COUNT(*) as change_count
        FROM course_history
        GROUP BY field_name
        ORDER BY change_count DESC
        LIMIT 5
        """)

        field_stats = cursor.fetchall()

        print(f"\nMost Modified Fields:")
        for field, count in field_stats:
            print(f"  {field}: {count} changes")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
