from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_create,
    log_read,
    log_update,
)


@log_create(module="course_management", description="Adding student to waitlist")
def add_to_waitlist(auth):
    """Add a student to a course waitlist"""
    if not auth or not auth.current_user:
        print("You must be logged in to manage waitlists.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to manage waitlists.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show full courses
        cursor.execute("""
        SELECT id, course_code, course_name, current_enrollment, max_enrollment
        FROM courses
        WHERE current_enrollment >= max_enrollment AND LOWER(status) = 'active'
        ORDER BY course_code
        """)

        full_courses = cursor.fetchall()

        if not full_courses:
            print("No full courses found.")
            return False

        print("\nFull Courses Available for Waitlist:")
        for idx, course in enumerate(full_courses, 1):
            print(f"{idx}. {course[1]} - {course[2]} ({course[3]}/{course[4]})")

        # Select course
        while True:
            choice = input("\nEnter course number (or press Enter to go back): ").strip()
            if not choice:
                return False
            try:
                idx = int(choice)
                if 1 <= idx <= len(full_courses):
                    course_id = full_courses[idx - 1][0]
                    break
                print("Invalid course number.")
            except ValueError:
                print("Please enter a valid number.")

        student_id = input("Enter student ID: ").strip()
        if not student_id:
            print("Student ID cannot be empty.")
            return False

        # Check if student is already on waitlist
        cursor.execute("SELECT id FROM course_waitlist WHERE course_id = ? AND student_id = ?",
                      (course_id, student_id))
        if cursor.fetchone():
            print("Student is already on the waitlist for this course.")
            return False

        # Get next position
        cursor.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM course_waitlist WHERE course_id = ?",
                      (course_id,))
        position = cursor.fetchone()[0]

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO course_waitlist (course_id, student_id, position, added_at)
        VALUES (?, ?, ?, ?)
        ''', (course_id, student_id, position, timestamp))

        conn.commit()

        print(f"\nStudent {student_id} added to waitlist at position {position}.")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()


@log_read(module="course_management", description="Viewing course waitlists")
def view_waitlists(auth):
    """View waitlists for courses"""
    if not auth or not auth.current_user:
        print("You must be logged in to view waitlists.")
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        course_choice = input("Enter course ID to view its waitlist (or press Enter for all): ").strip()

        if course_choice:
            try:
                course_id = int(course_choice)
                cursor.execute("""
                SELECT c.course_code, c.course_name, w.student_id, w.position, w.added_at, w.status
                FROM course_waitlist w
                JOIN courses c ON w.course_id = c.id
                WHERE w.course_id = ?
                ORDER BY w.position
                """, (course_id,))

                waitlist = cursor.fetchall()
                if waitlist:
                    print(f"\nWaitlist for {waitlist[0][0]} - {waitlist[0][1]}:")
                    print(f"{'Position':<10} {'Student ID':<15} {'Added':<20} {'Status':<10}")
                    print("-" * 55)
                    for entry in waitlist:
                        print(f"{entry[3]:<10} {entry[2]:<15} {entry[4]:<20} {entry[5]:<10}")
                else:
                    print("No waitlist entries found for this course.")
            except ValueError:
                print("Invalid course ID.")
        else:
            cursor.execute("""
            SELECT c.course_code, c.course_name, COUNT(w.id) as waitlist_count
            FROM courses c
            LEFT JOIN course_waitlist w ON c.id = w.course_id
            GROUP BY c.id, c.course_code, c.course_name
            HAVING waitlist_count > 0
            ORDER BY waitlist_count DESC, c.course_code
            """)

            waitlist_summary = cursor.fetchall()
            if waitlist_summary:
                print("\nCourses with Waitlists:")
                print(f"{'Code':<10} {'Name':<30} {'Waitlist Count':<15}")
                print("-" * 55)
                for code, name, count in waitlist_summary:
                    print(f"{code:<10} {name:<30} {count:<15}")
            else:
                print("No waitlists found in the system.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


@log_update(module="course_management", description="Processing course waitlist")
def process_waitlist(auth):
    """Process waitlist when spots become available"""
    if not auth or not auth.current_user:
        print("You must be logged in to process waitlists.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to process waitlists.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Find courses with available spots and waitlists
        cursor.execute("""
        SELECT c.id, c.course_code, c.course_name, c.current_enrollment, c.max_enrollment,
               (c.max_enrollment - c.current_enrollment) as available_spots,
               COUNT(w.id) as waitlist_count
        FROM courses c
        LEFT JOIN course_waitlist w ON c.id = w.course_id AND w.status = 'Waiting'
        WHERE LOWER(c.status) = 'active' AND c.current_enrollment < c.max_enrollment
        GROUP BY c.id, c.course_code, c.course_name, c.current_enrollment, c.max_enrollment
        HAVING waitlist_count > 0
        ORDER BY available_spots DESC, waitlist_count DESC
        """)

        courses_with_waitlists = cursor.fetchall()

        if not courses_with_waitlists:
            print("No courses with available spots and waitlists found.")
            return False

        print("\nCourses with Available Spots and Waitlists:")
        print(f"{'#':<5} {'Code':<8} {'Name':<25} {'Enrolled':<10} {'Available':<10} {'Waitlist':<10}")
        print("-" * 68)

        for idx, course in enumerate(courses_with_waitlists, 1):
            enrollment_str = f"{course[3]}/{course[4]}"
            print(f"{idx:<5} {course[1]:<8} {course[2]:<25} {enrollment_str:<10} {course[5]:<10} {course[6]:<10}")

        # Select course to process
        while True:
            choice = input("\nEnter course number to process waitlist (0 for all, or press Enter to go back): ").strip()
            if not choice:
                return False
            try:
                choice_num = int(choice)
                if choice_num == 0:
                    selected_courses = courses_with_waitlists
                    break
                elif 1 <= choice_num <= len(courses_with_waitlists):
                    selected_courses = [courses_with_waitlists[choice_num - 1]]
                    break
                else:
                    print("Invalid course number.")
            except ValueError:
                print("Please enter a valid number.")

        total_processed = 0

        for course in selected_courses:
            course_id, code, name, current_enrolled, max_enrolled, available_spots, waitlist_count = course

            print(f"\nProcessing waitlist for {code} - {name}")
            print(f"Available spots: {available_spots}")

            # Get waitlist students in order
            cursor.execute("""
            SELECT id, student_id, position
            FROM course_waitlist
            WHERE course_id = ? AND status = 'Waiting'
            ORDER BY position
            LIMIT ?
            """, (course_id, available_spots))

            waitlist_students = cursor.fetchall()

            if not waitlist_students:
                print(f"No waiting students found for {code}")
                continue

            # Process each student
            for waitlist_entry in waitlist_students:
                waitlist_id, student_id, position = waitlist_entry

                # Update waitlist status
                cursor.execute("""
                UPDATE course_waitlist
                SET status = 'Enrolled'
                WHERE id = ?
                """, (waitlist_id,))

                # Update course enrollment
                cursor.execute("""
                UPDATE courses
                SET current_enrollment = current_enrollment + 1,
                    updated_at = ?
                WHERE id = ?
                """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), course_id))

                print(f"  - Student {student_id} enrolled from position {position}")
                total_processed += 1

            # Update positions for remaining waitlist
            cursor.execute("""
            UPDATE course_waitlist
            SET position = position - ?
            WHERE course_id = ? AND status = 'Waiting'
            """, (len(waitlist_students), course_id))

        conn.commit()

        print(f"\nWaitlist processing completed!")
        print(f"Total students enrolled: {total_processed}")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()
