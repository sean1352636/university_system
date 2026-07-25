from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.utils.activity_logger import log_read
from education_system.systems.university.domain.academics.services.course_management.courses import view_course_details


@log_read(module="course_management", description="Searching courses")
def search_courses(auth):
    """Advanced course search and filtering"""
    if not auth or not auth.current_user:
        print("You must be logged in to search courses.")
        return

    if not auth.check_permission('view_courses'):
        print("You don't have permission to view courses.")
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nAdvanced Course Search")
        print("=====================")

        # Build search criteria
        conditions = []
        params = []

        keyword = input("Enter keyword (search in name/description): ").strip()
        if keyword:
            conditions.append("(course_name LIKE ? OR description LIKE ?)")
            params.extend([f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%"])

        department = input("Enter department: ").strip()
        if department:
            conditions.append("department LIKE ?")
            params.append(f"%{escape_like(department)}%")

        level = input("Enter level: ").strip()
        if level:
            conditions.append("level LIKE ?")
            params.append(f"%{escape_like(level)}%")

        course_type = input("Enter course type: ").strip()
        if course_type:
            conditions.append("course_type LIKE ?")
            params.append(f"%{escape_like(course_type)}%")

        status = input("Enter status (Active/Inactive): ").strip()
        if status:
            conditions.append("status = ?")
            params.append(status)

        # Credit hours range
        min_credits = input("Enter minimum credit hours: ").strip()
        if min_credits:
            try:
                conditions.append("credit_hours >= ?")
                params.append(float(min_credits))
            except ValueError:
                print("Invalid credit hours, ignoring.")

        max_credits = input("Enter maximum credit hours: ").strip()
        if max_credits:
            try:
                conditions.append("credit_hours <= ?")
                params.append(float(max_credits))
            except ValueError:
                print("Invalid credit hours, ignoring.")

        # Enrollment availability
        show_available = input("Show only courses with available spots? (y/n): ").strip().lower()
        if show_available == 'y':
            conditions.append("current_enrollment < max_enrollment")

        # Build query
        base_query = """
        SELECT id, course_code, course_name, department, level, course_type,
               credit_hours, current_enrollment, max_enrollment, status
        FROM courses
        """

        if conditions:
            query = base_query + " WHERE " + " AND ".join(conditions)
        else:
            query = base_query

        query += " ORDER BY course_code"

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            print("\nNo courses found matching your criteria.")
            return

        print(f"\nSearch Results ({len(results)} courses found):")
        print(f"{'Code':<10} {'Name':<30} {'Department':<15} {'Level':<15} {'Credits':<8} {'Enrollment':<12} {'Status':<10}")
        print("-" * 100)

        for course in results:
            enrollment_str = f"{course[7]}/{course[8]}"
            print(f"{course[1]:<10} {course[2]:<30} {course[3]:<15} {course[4]:<15} {course[6]:<8} {enrollment_str:<12} {course[9]:<10}")

        # Option to view details
        detail_choice = input("\nEnter course ID for details (or press Enter to continue): ").strip()
        if detail_choice:
            try:
                course_id = int(detail_choice)
                view_course_details(cursor, course_id)
            except ValueError:
                print("Invalid course ID.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
