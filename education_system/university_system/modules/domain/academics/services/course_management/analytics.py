from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_read


@log_read(module="course_management", description="Generating course analytics")
def generate_course_analytics(auth):
    """Generate comprehensive course analytics"""
    if not auth or not auth.current_user:
        print("You must be logged in to view analytics.")
        return

    if not auth.check_permission('view_courses'):
        print("You don't have permission to view analytics.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nCourse Analytics Dashboard")
        print("=========================")

        # Total courses by status
        cursor.execute("SELECT status, COUNT(*) FROM courses GROUP BY status")
        status_counts = cursor.fetchall()

        print("\n1. Courses by Status:")
        for status, count in status_counts:
            print(f"   {status}: {count}")

        # Enrollment statistics
        cursor.execute("""
        SELECT
            COUNT(*) as total_courses,
            SUM(current_enrollment) as total_enrolled,
            AVG(current_enrollment) as avg_enrollment,
            SUM(max_enrollment) as total_capacity,
            ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as avg_fill_rate
        FROM courses
        WHERE status = 'Active'
        """)

        enrollment_stats = cursor.fetchone()

        print("\n2. Enrollment Statistics:")
        print(f"   Total Active Courses: {enrollment_stats[0]}")
        print(f"   Total Students Enrolled: {enrollment_stats[1]}")
        print(f"   Average Enrollment per Course: {enrollment_stats[2]:.1f}")
        print(f"   Total Capacity: {enrollment_stats[3]}")
        print(f"   Average Fill Rate: {enrollment_stats[4]}%")

        # Department distribution
        cursor.execute("""
        SELECT department, COUNT(*) as course_count, SUM(current_enrollment) as total_students
        FROM courses
        WHERE department IS NOT NULL AND department != ''
        GROUP BY department
        ORDER BY course_count DESC
        """)

        dept_stats = cursor.fetchall()

        print("\n3. Courses by Department:")
        print(f"   {'Department':<20} {'Courses':<10} {'Students':<10}")
        print("   " + "-" * 40)
        for dept, courses, students in dept_stats:
            print(f"   {dept:<20} {courses:<10} {students or 0:<10}")

        # Level distribution
        cursor.execute("""
        SELECT level, COUNT(*) as course_count, AVG(credit_hours) as avg_credits
        FROM courses
        WHERE level IS NOT NULL AND level != ''
        GROUP BY level
        ORDER BY course_count DESC
        """)

        level_stats = cursor.fetchall()

        print("\n4. Courses by Level:")
        print(f"   {'Level':<15} {'Courses':<10} {'Avg Credits':<12}")
        print("   " + "-" * 37)
        for level, courses, avg_credits in level_stats:
            print(f"   {level:<15} {courses:<10} {avg_credits:.1f}")

        # Most popular courses
        cursor.execute("""
        SELECT course_code, course_name, current_enrollment, max_enrollment,
               ROUND(CAST(current_enrollment AS FLOAT) / max_enrollment * 100, 1) as fill_rate
        FROM courses
        WHERE status = 'Active' AND max_enrollment > 0
        ORDER BY current_enrollment DESC, fill_rate DESC
        LIMIT 10
        """)

        popular_courses = cursor.fetchall()

        print("\n5. Most Popular Courses (Top 10):")
        print(f"   {'Code':<8} {'Name':<25} {'Enrolled':<10} {'Fill Rate':<10}")
        print("   " + "-" * 53)
        for code, name, enrolled, capacity, fill_rate in popular_courses:
            name_short = name[:22] + "..." if len(name) > 25 else name
            print(f"   {code:<8} {name_short:<25} {enrolled:<10} {fill_rate}%")

        # Courses with availability
        cursor.execute("""
        SELECT COUNT(*) as available_courses
        FROM courses
        WHERE status = 'Active' AND current_enrollment < max_enrollment
        """)

        available_count = cursor.fetchone()[0]

        print(f"\n6. Course Availability:")
        print(f"   Courses with Available Spots: {available_count}")

        # Credit hour distribution
        cursor.execute("""
        SELECT credit_hours, COUNT(*) as course_count
        FROM courses
        GROUP BY credit_hours
        ORDER BY credit_hours
        """)

        credit_dist = cursor.fetchall()

        print("\n7. Credit Hour Distribution:")
        for credits, count in credit_dist:
            print(f"   {credits} credits: {count} courses")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()


@log_read(module="course_management", description="Generating enrollment report")
def generate_enrollment_report(auth):
    """Generate detailed enrollment report"""
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return False

    if not auth.check_permission('view_courses'):
        print("You don't have permission to generate reports.")
        return False

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nEnrollment Report Generator")
        print("=========================")

        # Report options
        print("Select report type:")
        print("1. Summary Report")
        print("2. Department Report")
        print("3. Course Level Report")
        print("4. Detailed Course Report")
        print("5. Capacity Analysis")

        while True:
            try:
                report_type = int(input("Enter choice (1-5): "))
                if 1 <= report_type <= 5:
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if report_type == 1:  # Summary Report
            print(f"\nENROLLMENT SUMMARY REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)

            # Overall statistics
            cursor.execute("""
            SELECT
                COUNT(*) as total_courses,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                AVG(current_enrollment) as avg_enrollment,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as avg_fill_rate
            FROM courses
            WHERE status = 'Active'
            """)

            summary = cursor.fetchone()

            print(f"Total Active Courses: {summary[0]}")
            print(f"Total Students Enrolled: {summary[1]}")
            print(f"Total System Capacity: {summary[2]}")
            print(f"Average Enrollment per Course: {summary[3]:.1f}")
            print(f"Average Fill Rate: {summary[4]}%")
            print(f"Available Spots: {summary[2] - summary[1]}")

            # Status breakdown
            cursor.execute("SELECT status, COUNT(*) FROM courses GROUP BY status")
            status_data = cursor.fetchall()

            print(f"\nCourse Status Breakdown:")
            for status, count in status_data:
                print(f"  {status}: {count}")

        elif report_type == 2:  # Department Report
            print(f"\nDEPARTMENT ENROLLMENT REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)

            cursor.execute("""
            SELECT
                COALESCE(department, 'Unknown') as dept,
                COUNT(*) as course_count,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as fill_rate
            FROM courses
            WHERE status = 'Active'
            GROUP BY department
            ORDER BY total_students DESC
            """)

            dept_data = cursor.fetchall()

            print(f"{'Department':<20} {'Courses':<10} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}")
            print("-" * 60)

            for dept, courses, students, capacity, fill_rate in dept_data:
                print(f"{dept:<20} {courses:<10} {students:<10} {capacity:<10} {fill_rate}%")

        elif report_type == 3:  # Course Level Report
            print(f"\nCOURSE LEVEL ENROLLMENT REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)

            cursor.execute("""
            SELECT
                COALESCE(level, 'Unknown') as course_level,
                COUNT(*) as course_count,
                SUM(current_enrollment) as total_students,
                AVG(credit_hours) as avg_credits,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as fill_rate
            FROM courses
            WHERE status = 'Active'
            GROUP BY level
            ORDER BY total_students DESC
            """)

            level_data = cursor.fetchall()

            print(f"{'Level':<15} {'Courses':<10} {'Students':<10} {'Avg Credits':<12} {'Fill Rate':<10}")
            print("-" * 57)

            for level, courses, students, avg_credits, fill_rate in level_data:
                print(f"{level:<15} {courses:<10} {students:<10} {avg_credits:.1f} {fill_rate}%")

        elif report_type == 4:  # Detailed Course Report
            print(f"\nDETAILED COURSE ENROLLMENT REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)

            cursor.execute("""
            SELECT course_code, course_name, department, level,
                   current_enrollment, max_enrollment,
                   ROUND(CAST(current_enrollment AS FLOAT) / max_enrollment * 100, 1) as fill_rate,
                   course_type, credit_hours
            FROM courses
            WHERE status = 'Active'
            ORDER BY current_enrollment DESC
            """)

            course_data = cursor.fetchall()

            print(f"{'Code':<8} {'Name':<20} {'Dept':<10} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}")
            print("-" * 70)

            for course in course_data:
                name_short = course[1][:17] + "..." if len(course[1]) > 20 else course[1]
                enrollment_str = f"{course[4]}/{course[5]}"
                print(f"{course[0]:<8} {name_short:<20} {course[2]:<10} {course[3]:<12} {enrollment_str:<10} {course[6]}%")

        elif report_type == 5:  # Capacity Analysis
            print(f"\nCAPACITY ANALYSIS REPORT")
            print(f"Generated: {timestamp}")
            print("=" * 50)

            # Over-enrolled courses
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment
            FROM courses
            WHERE current_enrollment > max_enrollment AND status = 'Active'
            ORDER BY (current_enrollment - max_enrollment) DESC
            """)

            over_enrolled = cursor.fetchall()

            print("Over-enrolled Courses:")
            if over_enrolled:
                for course in over_enrolled:
                    excess = course[2] - course[3]
                    print(f"  {course[0]} - {course[1]}: {excess} over capacity")
            else:
                print("  None")

            # Under-enrolled courses
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment,
                   (max_enrollment - current_enrollment) as available
            FROM courses
            WHERE current_enrollment < max_enrollment * 0.5 AND status = 'Active'
            ORDER BY available DESC
            """)

            under_enrolled = cursor.fetchall()

            print(f"\nUnder-enrolled Courses (< 50% capacity):")
            if under_enrolled:
                for course in under_enrolled:
                    fill_rate = (course[2] / course[3]) * 100
                    print(f"  {course[0]} - {course[1]}: {fill_rate:.1f}% full ({course[4]} spots available)")
            else:
                print("  None")

        # Option to save report
        save_option = input(f"\nSave report to file? (y/n): ").strip().lower()
        if save_option == 'y':
            filename = f"enrollment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            print(f"Report saved as {filename}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()


@log_read(module="course_management", description="Viewing department statistics")
def department_statistics(auth):
    """Show department-specific statistics"""
    if not auth or not auth.current_user:
        print("You must be logged in to view statistics.")
        return

    if not auth.check_permission('view_courses'):
        print("You don't have permission to view statistics.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get list of departments
        cursor.execute("""
        SELECT DISTINCT COALESCE(department, 'Unknown') as dept
        FROM courses
        WHERE department IS NOT NULL AND department != ''
        ORDER BY dept
        """)

        departments = [row[0] for row in cursor.fetchall()]

        if not departments:
            print("No departments found.")
            conn.close()
            return

        print("\nSelect Department for Statistics:")
        print("0. All Departments Overview")
        for i, dept in enumerate(departments, 1):
            print(f"{i}. {dept}")

        while True:
            try:
                choice = int(input(f"Enter choice (0-{len(departments)}): "))
                if choice == 0:
                    selected_dept = None
                    break
                elif 1 <= choice <= len(departments):
                    selected_dept = departments[choice - 1]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        if selected_dept:
            # Single department statistics
            print(f"\nDETAILED STATISTICS FOR {selected_dept.upper()} DEPARTMENT")
            print("=" * 60)

            # Basic stats
            cursor.execute("""
            SELECT
                COUNT(*) as total_courses,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                AVG(current_enrollment) as avg_enrollment,
                AVG(credit_hours) as avg_credits,
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
            FROM courses
            WHERE department = ?
            """, (selected_dept,))

            stats = cursor.fetchone()

            print(f"Total Courses: {stats[0]}")
            print(f"Active Courses: {stats[5]}")
            print(f"Total Students: {stats[1]}")
            print(f"Total Capacity: {stats[2]}")
            print(f"Average Enrollment: {stats[3]:.1f}")
            print(f"Average Credit Hours: {stats[4]:.1f}")
            if stats[2] > 0:
                print(f"Department Fill Rate: {(stats[1]/stats[2]*100):.1f}%")

            # Course breakdown by level
            cursor.execute("""
            SELECT level, COUNT(*), SUM(current_enrollment)
            FROM courses
            WHERE department = ?
            GROUP BY level
            ORDER BY COUNT(*) DESC
            """, (selected_dept,))

            level_stats = cursor.fetchall()

            print(f"\nCourses by Level:")
            for level, count, enrollment in level_stats:
                level_name = level or "Unknown"
                print(f"  {level_name}: {count} courses, {enrollment} students")

            # Top courses by enrollment
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment
            FROM courses
            WHERE department = ? AND status = 'Active'
            ORDER BY current_enrollment DESC
            LIMIT 5
            """, (selected_dept,))

            top_courses = cursor.fetchall()

            print(f"\nTop 5 Most Enrolled Courses:")
            for course in top_courses:
                print(f"  {course[0]} - {course[1]}: {course[2]}/{course[3]} students")

            # Instructors in department
            cursor.execute("""
            SELECT COUNT(DISTINCT i.id) as instructor_count
            FROM instructors i
            WHERE i.department = ? AND i.status = 'Active'
            """, (selected_dept,))

            instructor_count = cursor.fetchone()[0]
            print(f"\nActive Instructors: {instructor_count}")

        else:
            # All departments overview
            print(f"\nALL DEPARTMENTS OVERVIEW")
            print("=" * 50)

            cursor.execute("""
            SELECT
                COALESCE(department, 'Unknown') as dept,
                COUNT(*) as course_count,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 1) as fill_rate,
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_courses
            FROM courses
            GROUP BY department
            ORDER BY total_students DESC
            """)

            all_dept_stats = cursor.fetchall()

            print(f"{'Department':<20} {'Courses':<10} {'Active':<8} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}")
            print("-" * 68)

            for dept_stat in all_dept_stats:
                dept, courses, students, capacity, fill_rate, active = dept_stat
                print(f"{dept:<20} {courses:<10} {active:<8} {students:<10} {capacity:<10} {fill_rate}%")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
