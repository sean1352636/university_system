from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import log_read


def _send_enrollment_report_to_admin(cursor, report_name, timestamp, report_lines):
    """Send the enrollment report to admin users via the email system."""
    try:
        from education_system.post_18.university_system.infrastructure.email import send_template_email

        # Find admin email
        cursor.execute("""
        SELECT email FROM users
        WHERE LOWER(role) = 'admin' AND email IS NOT NULL AND email != ''
        LIMIT 1
        """)
        admin_row = cursor.fetchone()

        if admin_row:
            admin_email = admin_row[0]
        else:
            admin_email = input("No admin email found. Enter email address (or Enter to skip): ").strip()
            if not admin_email:
                print("Email skipped.")
                return

        # Get admin name
        admin_name = "Administrator"
        cursor.execute("SELECT first_name, last_name FROM users WHERE email = ?", (admin_email,))
        name_row = cursor.fetchone()
        if name_row:
            first = name_row[0] or ""
            last = name_row[1] or ""
            if first or last:
                admin_name = f"{first} {last}".strip()

        report_body = '\n'.join(report_lines)

        template_vars = {
            'recipient_name': admin_name,
            'report_type': f"{report_name} Report",
            'generated_date': timestamp,
            'report_body': report_body,
        }

        result = send_template_email(
            'user_management/enrollment_report',
            admin_email,
            template_vars,
        )

        if result:
            print(f"Report sent to {admin_email}")
        else:
            print(f"Failed to send report to {admin_email}")

    except Exception as e:
        print(f"Error sending report: {e}")


@log_read(module="course_management", description="Generating course analytics")
def generate_course_analytics(auth):
    """Generate comprehensive course analytics"""
    if not auth or not auth.current_user:
        print("You must be logged in to view analytics.")
        return

    if not auth.check_permission('view_courses'):
        print("You don't have permission to view analytics.")
        return

    conn = None
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
        WHERE LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'
        """)

        enrollment_stats = cursor.fetchone()

        print("\n2. Enrollment Statistics:")
        print(f"   Total Active Courses: {enrollment_stats[0] or 0}")
        print(f"   Total Students Enrolled: {enrollment_stats[1] or 0}")
        print(f"   Average Enrollment per Course: {enrollment_stats[2]:.1f}" if enrollment_stats[2] is not None else "   Average Enrollment per Course: N/A")
        print(f"   Total Capacity: {enrollment_stats[3] or 0}")
        print(f"   Average Fill Rate: {enrollment_stats[4]}%" if enrollment_stats[4] is not None else "   Average Fill Rate: N/A")

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
            avg_display = f"{avg_credits:.1f}" if avg_credits is not None else "N/A"
            print(f"   {level:<15} {courses:<10} {avg_display}")

        # Most popular courses
        cursor.execute("""
        SELECT course_code, course_name, current_enrollment, max_enrollment,
               ROUND(CAST(current_enrollment AS FLOAT) / max_enrollment * 100, 1) as fill_rate
        FROM courses
        WHERE LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active' AND max_enrollment > 0
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
        WHERE LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active' AND current_enrollment < max_enrollment
        """)

        available_count = cursor.fetchone()[0]

        print("\n6. Course Availability:")
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

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
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

    conn = None
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
            raw = input("Enter choice (1-5) or press Enter to go back: ").strip()
            if raw == "":
                return
            try:
                report_type = int(raw)
                if 1 <= report_type <= 5:
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report_lines = []  # collect for email/save

        def out(line=""):
            """Print and capture a report line."""
            print(line)
            report_lines.append(line)

        report_type_names = {1: "Summary", 2: "Department", 3: "Course Level",
                             4: "Detailed Course", 5: "Capacity Analysis"}
        report_name = report_type_names.get(report_type, "Enrollment")

        if report_type == 1:  # Summary Report
            out("\nENROLLMENT SUMMARY REPORT")
            out(f"Generated: {timestamp}")
            out("=" * 50)

            cursor.execute("""
            SELECT
                COUNT(*) as total_courses,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                AVG(current_enrollment) as avg_enrollment,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as avg_fill_rate
            FROM courses
            WHERE LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'
            """)

            summary = cursor.fetchone()

            out(f"Total Active Courses: {summary[0] or 0}")
            out(f"Total Students Enrolled: {summary[1] or 0}")
            out(f"Total System Capacity: {summary[2] or 0}")
            out(f"Average Enrollment per Course: {summary[3]:.1f}" if summary[3] is not None else "Average Enrollment per Course: N/A")
            out(f"Average Fill Rate: {summary[4]}%" if summary[4] is not None else "Average Fill Rate: N/A")
            out(f"Available Spots: {(summary[2] or 0) - (summary[1] or 0)}")

            cursor.execute("SELECT status, COUNT(*) FROM courses GROUP BY status")
            status_data = cursor.fetchall()

            out("\nCourse Status Breakdown:")
            for status, count in status_data:
                out(f"  {status}: {count}")

        elif report_type == 2:  # Department Report
            out("\nDEPARTMENT ENROLLMENT REPORT")
            out(f"Generated: {timestamp}")
            out("=" * 50)

            cursor.execute("""
            SELECT
                COALESCE(department, 'Unknown') as dept,
                COUNT(*) as course_count,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as fill_rate
            FROM courses
            WHERE LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'
            GROUP BY department
            ORDER BY total_students DESC
            """)

            dept_data = cursor.fetchall()

            out(f"{'Department':<20} {'Courses':<10} {'Students':<10} {'Capacity':<10} {'Fill Rate':<10}")
            out("-" * 60)

            for dept, courses, students, capacity, fill_rate in dept_data:
                out(f"{dept:<20} {courses:<10} {students:<10} {capacity:<10} {fill_rate}%")

        elif report_type == 3:  # Course Level Report
            out("\nCOURSE LEVEL ENROLLMENT REPORT")
            out(f"Generated: {timestamp}")
            out("=" * 50)

            cursor.execute("""
            SELECT
                COALESCE(level, 'Unknown') as course_level,
                COUNT(*) as course_count,
                SUM(current_enrollment) as total_students,
                AVG(credit_hours) as avg_credits,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 2) as fill_rate
            FROM courses
            WHERE LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'
            GROUP BY level
            ORDER BY total_students DESC
            """)

            level_data = cursor.fetchall()

            out(f"{'Level':<15} {'Courses':<10} {'Students':<10} {'Avg Credits':<12} {'Fill Rate':<10}")
            out("-" * 57)

            for level, courses, students, avg_credits, fill_rate in level_data:
                avg_c = f"{avg_credits:.1f}" if avg_credits is not None else "N/A"
                fr = f"{fill_rate}%" if fill_rate is not None else "N/A"
                out(f"{level:<15} {courses:<10} {students or 0:<10} {avg_c} {fr}")

        elif report_type == 4:  # Detailed Course Report
            out("\nDETAILED COURSE ENROLLMENT REPORT")
            out(f"Generated: {timestamp}")
            out("=" * 50)

            cursor.execute("""
            SELECT course_code, course_name, department, level,
                   current_enrollment, max_enrollment,
                   ROUND(CAST(current_enrollment AS FLOAT) / max_enrollment * 100, 1) as fill_rate,
                   course_type, credit_hours
            FROM courses
            WHERE LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'
            ORDER BY current_enrollment DESC
            """)

            course_data = cursor.fetchall()

            out(f"{'Code':<8} {'Name':<20} {'Dept':<10} {'Level':<12} {'Enrolled':<10} {'Fill Rate':<10}")
            out("-" * 70)

            for course in course_data:
                name_short = course[1][:17] + "..." if len(course[1]) > 20 else course[1]
                enrollment_str = f"{course[4]}/{course[5]}"
                out(f"{course[0]:<8} {name_short:<20} {course[2]:<10} {course[3]:<12} {enrollment_str:<10} {course[6]}%")

        elif report_type == 5:  # Capacity Analysis
            out("\nCAPACITY ANALYSIS REPORT")
            out(f"Generated: {timestamp}")
            out("=" * 50)

            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment
            FROM courses
            WHERE current_enrollment > max_enrollment AND LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'
            ORDER BY (current_enrollment - max_enrollment) DESC
            """)

            over_enrolled = cursor.fetchall()

            out("Over-enrolled Courses:")
            if over_enrolled:
                for course in over_enrolled:
                    excess = course[2] - course[3]
                    out(f"  {course[0]} - {course[1]}: {excess} over capacity")
            else:
                out("  None")

            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment,
                   (max_enrollment - current_enrollment) as available
            FROM courses
            WHERE current_enrollment < max_enrollment * 0.5 AND LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'
            ORDER BY available DESC
            """)

            under_enrolled = cursor.fetchall()

            out("\nUnder-enrolled Courses (< 50% capacity):")
            if under_enrolled:
                for course in under_enrolled:
                    fill_rate = (course[2] / course[3] * 100) if course[3] else 0
                    out(f"  {course[0]} - {course[1]}: {fill_rate:.1f}% full ({course[4]} spots available)")
            else:
                out("  None")

        # Post-report actions
        print("\nOptions:")
        print("1. Send report to admin via email")
        print("2. Save report to file")
        print("Press Enter to skip")

        action = input("Enter choice: ").strip()

        if action == '1':
            _send_enrollment_report_to_admin(cursor, report_name, timestamp, report_lines)
        elif action == '2':
            filename = f"enrollment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(report_lines))
                print(f"Report saved as {filename}")
            except IOError as e:
                print(f"Error saving report: {e}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
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

    conn = None
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
            return

        print("\nSelect Department for Statistics:")
        print("0. All Departments Overview")
        for i, dept in enumerate(departments, 1):
            print(f"{i}. {dept}")

        while True:
            raw = input(f"Enter choice (0-{len(departments)}) or press Enter to go back: ").strip()
            if raw == "":
                return
            try:
                choice = int(raw)
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
                COUNT(CASE WHEN LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active' THEN 1 END) as active_courses
            FROM courses
            WHERE department = ?
            """, (selected_dept,))

            stats = cursor.fetchone()

            print(f"Total Courses: {stats[0] or 0}")
            print(f"Active Courses: {stats[5] or 0}")
            print(f"Total Students: {stats[1] or 0}")
            print(f"Total Capacity: {stats[2] or 0}")
            print(f"Average Enrollment: {stats[3]:.1f}" if stats[3] is not None else "Average Enrollment: N/A")
            print(f"Average Credit Hours: {stats[4]:.1f}" if stats[4] is not None else "Average Credit Hours: N/A")
            if stats[2] and stats[1]:
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

            print("\nCourses by Level:")
            for level, count, enrollment in level_stats:
                level_name = level or "Unknown"
                print(f"  {level_name}: {count} courses, {enrollment} students")

            # Top courses by enrollment
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment
            FROM courses
            WHERE department = ? AND LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'
            ORDER BY current_enrollment DESC
            LIMIT 5
            """, (selected_dept,))

            top_courses = cursor.fetchall()

            print("\nTop 5 Most Enrolled Courses:")
            for course in top_courses:
                print(f"  {course[0]} - {course[1]}: {course[2]}/{course[3]} students")

            # Instructors in department
            cursor.execute("""
            SELECT COUNT(DISTINCT i.id) as instructor_count
            FROM instructors i
            WHERE i.department = ? AND LOWER(i.status) = 'active'
            """, (selected_dept,))

            instructor_count = cursor.fetchone()[0]
            print(f"\nActive Instructors: {instructor_count}")

        else:
            # All departments overview
            print("\nALL DEPARTMENTS OVERVIEW")
            print("=" * 50)

            cursor.execute("""
            SELECT
                COALESCE(department, 'Unknown') as dept,
                COUNT(*) as course_count,
                SUM(current_enrollment) as total_students,
                SUM(max_enrollment) as total_capacity,
                ROUND(AVG(CAST(current_enrollment AS FLOAT) / max_enrollment * 100), 1) as fill_rate,
                COUNT(CASE WHEN LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active' THEN 1 END) as active_courses
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

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
