from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import (
    log_create,
    log_read,
    log_delete,
)
from education_system.post_18.university_system.modules.domain.academics.services.course_management.validation import check_circular_prerequisite


@log_create(module="course_management", description="Adding course prerequisite")
def add_prerequisite(auth):
    """
    Add a prerequisite requirement to a course.

    Interactive function that allows administrators to define prerequisite
    relationships between courses. Includes circular dependency detection
    to prevent invalid prerequisite chains.

    Parameters
    ----------
    auth : UserAuth
        The authentication instance. Must have an authenticated user with
        'manage_courses' permission.

    Returns
    -------
    bool
        True if the prerequisite was successfully added, False otherwise.
        Returns False if:
        - User is not logged in or lacks permission
        - Fewer than 2 courses exist in the system
        - Selected prerequisite would create a circular dependency
        - Prerequisite already exists
        - Database error occurs

    Examples
    --------
    >>> # Interactive prompts will appear
    >>> add_prerequisite(auth)
    Available Courses:
    1. CS101 - Introduction to Programming
    2. CS201 - Data Structures
    ...
    Enter course ID to add prerequisite to: 2
    Select prerequisite course:
    1. CS101 - Introduction to Programming
    Enter prerequisite course ID: 1
    Is this prerequisite required? (yes/no): yes
    Prerequisite added successfully!
    True

    Notes
    -----
    - A course cannot be its own prerequisite
    - Circular dependencies are automatically detected and rejected
    - Prerequisites can be marked as 'required' or 'recommended'

    See Also
    --------
    view_prerequisites : View existing prerequisite relationships.
    check_circular_prerequisite : Check for circular dependency.
    """
    if not auth or not auth.current_user:
        print("You must be logged in to manage prerequisites.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to manage prerequisites.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show all courses
        cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
        courses = cursor.fetchall()

        if len(courses) < 2:
            print("Need at least 2 courses to set prerequisites.")
            return False

        print("\nAvailable Courses:")
        for i, course in enumerate(courses, 1):
            print(f"{i}. {course[1]} - {course[2]}")

        # Select main course
        while True:
            choice = input("\nEnter course number to add prerequisite to (or press Enter to go back): ").strip()
            if not choice:
                return False
            try:
                idx = int(choice)
                if 1 <= idx <= len(courses):
                    course_id = courses[idx - 1][0]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        # Select prerequisite course
        print("\nSelect prerequisite course:")
        available_prereqs = [c for c in courses if c[0] != course_id]
        for i, course in enumerate(available_prereqs, 1):
            print(f"{i}. {course[1]} - {course[2]}")

        while True:
            choice = input("\nEnter prerequisite course number (or press Enter to go back): ").strip()
            if not choice:
                return False
            try:
                idx = int(choice)
                if 1 <= idx <= len(available_prereqs):
                    prereq_id = available_prereqs[idx - 1][0]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        # Check for circular dependencies
        if check_circular_prerequisite(cursor, course_id, prereq_id):
            print("Error: This would create a circular dependency.")
            return False

        is_required = input("Is this a required prerequisite? (y/n): ").strip().lower() == 'y'

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO course_prerequisites (course_id, prerequisite_course_id, is_required, created_at)
        VALUES (?, ?, ?, ?)
        ''', (course_id, prereq_id, is_required, timestamp))

        conn.commit()

        print("Prerequisite added successfully!")
        return True

    except sqlite3.IntegrityError:
        print("Error: This prerequisite already exists.")
        return False
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()


@log_read(module="course_management", description="Viewing course prerequisites")
def view_prerequisites(auth):
    """View prerequisites for all courses or a specific course"""
    if not auth or not auth.current_user:
        print("You must be logged in to view prerequisites.")
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        course_choice = input("Enter course ID to view its prerequisites (or press Enter for all): ").strip()

        if course_choice:
            try:
                course_id = int(course_choice)
                cursor.execute("""
                SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c1 ON cp.course_id = c1.id
                JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                WHERE cp.course_id = ?
                ORDER BY c2.course_code
                """, (course_id,))

                prereqs = cursor.fetchall()
                if prereqs:
                    print(f"\nPrerequisites for {prereqs[0][0]} - {prereqs[0][1]}:")
                    print("-" * 60)
                    for prereq in prereqs:
                        req_status = "Required" if prereq[4] else "Recommended"
                        print(f"{prereq[2]} - {prereq[3]} ({req_status})")
                else:
                    print("No prerequisites found for this course.")
            except ValueError:
                print("Invalid course ID.")
        else:
            cursor.execute("""
            SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
            FROM course_prerequisites cp
            JOIN courses c1 ON cp.course_id = c1.id
            JOIN courses c2 ON cp.prerequisite_course_id = c2.id
            ORDER BY c1.course_code, c2.course_code
            """)

            prereqs = cursor.fetchall()
            if prereqs:
                print("\nAll Course Prerequisites:")
                print("-" * 80)
                current_course = None
                for prereq in prereqs:
                    if current_course != prereq[0]:
                        current_course = prereq[0]
                        print(f"\n{prereq[0]} - {prereq[1]}:")

                    req_status = "Required" if prereq[4] else "Recommended"
                    print(f"  → {prereq[2]} - {prereq[3]} ({req_status})")
            else:
                print("No prerequisites found in the system.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


@log_delete(module="course_management", description="Removing course prerequisite")
def remove_prerequisite(auth):
    """Remove a prerequisite from a course"""
    if not auth or not auth.current_user:
        print("You must be logged in to remove prerequisites.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to manage prerequisites.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show courses with prerequisites
        cursor.execute("""
        SELECT DISTINCT c1.id, c1.course_code, c1.course_name, COUNT(cp.id) as prereq_count
        FROM courses c1
        JOIN course_prerequisites cp ON c1.id = cp.course_id
        GROUP BY c1.id, c1.course_code, c1.course_name
        ORDER BY c1.course_code
        """)

        courses_with_prereqs = cursor.fetchall()

        if not courses_with_prereqs:
            print("No courses with prerequisites found.")
            return False

        print("\nCourses with Prerequisites:")
        for i, course in enumerate(courses_with_prereqs, 1):
            print(f"{i}. {course[1]} - {course[2]} ({course[3]} prerequisites)")

        # Select course
        while True:
            choice = input("\nEnter course number to remove prerequisite from (or press Enter to go back): ").strip()
            if not choice:
                return False
            try:
                idx = int(choice)
                if 1 <= idx <= len(courses_with_prereqs):
                    course_id = courses_with_prereqs[idx - 1][0]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        # Show prerequisites for selected course
        cursor.execute("""
        SELECT cp.id, c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
        FROM course_prerequisites cp
        JOIN courses c1 ON cp.course_id = c1.id
        JOIN courses c2 ON cp.prerequisite_course_id = c2.id
        WHERE cp.course_id = ?
        ORDER BY c2.course_code
        """, (course_id,))

        prerequisites = cursor.fetchall()

        print(f"\nPrerequisites for {prerequisites[0][1]} - {prerequisites[0][2]}:")
        print(f"{'#':<5} {'Prerequisite Code':<15} {'Prerequisite Name':<30} {'Type':<12}")
        print("-" * 62)

        for i, prereq in enumerate(prerequisites, 1):
            req_type = "Required" if prereq[5] else "Recommended"
            print(f"{i:<5} {prereq[3]:<15} {prereq[4]:<30} {req_type:<12}")

        # Select prerequisite to remove
        while True:
            choice = input("\nEnter prerequisite number to remove (or press Enter to go back): ").strip()
            if not choice:
                return False
            try:
                idx = int(choice)
                if 1 <= idx <= len(prerequisites):
                    selected_prereq = prerequisites[idx - 1]
                    prereq_id = selected_prereq[0]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        confirm = input(f"\nRemove prerequisite '{selected_prereq[3]} - {selected_prereq[4]}'? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Removal cancelled.")
            return False

        # Remove the prerequisite
        cursor.execute("DELETE FROM course_prerequisites WHERE id = ?", (prereq_id,))
        rows_deleted = cursor.rowcount

        conn.commit()

        if rows_deleted > 0:
            print(f"\nPrerequisite '{selected_prereq[3]} - {selected_prereq[4]}' removed successfully!")
            return True
        else:
            print("Error: No prerequisite was removed.")
            return False

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()
