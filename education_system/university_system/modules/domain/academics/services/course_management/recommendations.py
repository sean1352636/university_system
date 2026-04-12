from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_read


@log_read(module="course_management", description="Generating course recommendations")
def recommend_courses(auth):
    """Recommend courses based on various criteria"""
    if not auth or not auth.current_user:
        print("You must be logged in to get recommendations.")
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nCourse Recommendation System")
        print("===========================")

        recommendation_type = input("Select recommendation type:\n1. Popular courses\n2. Courses with availability\n3. Prerequisites for a course\nEnter choice (1-3): ").strip()

        if recommendation_type == '1':
            # Popular courses
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment,
                   ROUND(CAST(current_enrollment AS FLOAT) / max_enrollment * 100, 1) as popularity
            FROM courses
            WHERE LOWER(status) = 'active' AND max_enrollment > 0
            ORDER BY current_enrollment DESC, popularity DESC
            LIMIT 10
            """)

            popular = cursor.fetchall()
            print("\nMost Popular Courses:")
            print(f"{'Code':<10} {'Name':<30} {'Enrolled':<10} {'Popularity':<12}")
            print("-" * 62)
            for code, name, enrolled, popularity in popular:
                print(f"{code:<10} {name:<30} {enrolled:<10} {popularity}%")

        elif recommendation_type == '2':
            # Available courses
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment,
                   (max_enrollment - current_enrollment) as available_spots
            FROM courses
            WHERE LOWER(status) = 'active' AND current_enrollment < max_enrollment
            ORDER BY available_spots DESC, course_code
            """)

            available = cursor.fetchall()
            print("\nCourses with Available Spots:")
            print(f"{'Code':<10} {'Name':<30} {'Available':<12} {'Total':<8}")
            print("-" * 60)
            for code, name, current, max_enroll, available_spots in available:
                print(f"{code:<10} {name:<30} {available_spots:<12} {max_enroll:<8}")

        elif recommendation_type == '3':
            # Prerequisites for a course
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()

            print("\nAvailable Courses:")
            for i, course in enumerate(courses[:10], 1):  # Show first 10
                print(f"{i}. {course[1]} - {course[2]}")

            if len(courses) > 10:
                print("... and more")

            try:
                choice_num = int(input("\nEnter course number to see prerequisites: "))
                if 1 <= choice_num <= len(courses[:10]):
                    target_course_id = courses[choice_num - 1][0]
                else:
                    print("Invalid course number.")
                    return

                cursor.execute("""
                SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c1 ON cp.course_id = c1.id
                JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                WHERE cp.course_id = ?
                ORDER BY cp.is_required DESC, c2.course_code
                """, (target_course_id,))

                prereqs = cursor.fetchall()
                if prereqs:
                    print(f"\nPrerequisites for {prereqs[0][0]} - {prereqs[0][1]}:")
                    print(f"{'Code':<10} {'Name':<30} {'Type':<12}")
                    print("-" * 52)
                    for prereq in prereqs:
                        req_type = "Required" if prereq[4] else "Recommended"
                        print(f"{prereq[2]:<10} {prereq[3]:<30} {req_type:<12}")
                else:
                    print("No prerequisites found for this course.")
            except ValueError:
                print("Invalid course number.")

        else:
            print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


@log_read(module="course_management", description="Finding alternative courses")
def find_alternative_courses(auth):
    """Find alternative courses for students"""
    if not auth or not auth.current_user:
        print("You must be logged in to find alternatives.")
        return

    if not auth.check_permission('view_courses'):
        print("You don't have permission to view courses.")
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nFind Alternative Courses")
        print("=======================")

        # Show courses for reference
        cursor.execute("SELECT id, course_code, course_name, department, level FROM courses WHERE LOWER(status) = 'active' ORDER BY course_code")
        courses = cursor.fetchall()

        if not courses:
            print("No active courses found.")
            return

        displayed = courses[:20]
        print("\nActive Courses:")
        for i, course in enumerate(displayed, 1):
            print(f"{i}. {course[1]} - {course[2]} ({course[3]}, {course[4]})")

        if len(courses) > 20:
            print("... and more")

        # Get reference course
        while True:
            ref_input = input("\nEnter course number to find alternatives for (or press Enter to go back): ").strip()
            if not ref_input:
                return
            try:
                ref_num = int(ref_input)
            except ValueError:
                print("Invalid course number.")
                continue
            if 1 <= ref_num <= len(displayed):
                ref_course = displayed[ref_num - 1]
                break
            print("Invalid course number.")

        ref_id, ref_code, ref_name, ref_dept, ref_level = ref_course

        print(f"\nFinding alternatives for: {ref_code} - {ref_name}")
        print(f"Department: {ref_dept}, Level: {ref_level}")

        # Find alternatives based on different criteria
        alternatives = []

        # 1. Same department and level
        cursor.execute("""
        SELECT id, course_code, course_name, department, level, current_enrollment, max_enrollment,
               'Same Dept & Level' as match_type
        FROM courses
        WHERE department = ? AND level = ? AND id != ? AND LOWER(status) = 'active'
        ORDER BY course_name
        """, (ref_dept, ref_level, ref_id))

        alternatives.extend(cursor.fetchall())

        # 2. Same department, different level
        cursor.execute("""
        SELECT id, course_code, course_name, department, level, current_enrollment, max_enrollment,
               'Same Department' as match_type
        FROM courses
        WHERE department = ? AND level != ? AND id != ? AND LOWER(status) = 'active'
        ORDER BY course_name
        """, (ref_dept, ref_level, ref_id))

        alternatives.extend(cursor.fetchall())

        # 3. Same level, different department
        cursor.execute("""
        SELECT id, course_code, course_name, department, level, current_enrollment, max_enrollment,
               'Same Level' as match_type
        FROM courses
        WHERE level = ? AND department != ? AND id != ? AND LOWER(status) = 'active'
        ORDER BY course_name
        """, (ref_level, ref_dept, ref_id))

        alternatives.extend(cursor.fetchall())

        # 4. Similar credit hours
        cursor.execute("SELECT credit_hours FROM courses WHERE id = ?", (ref_id,))
        _credits_row = cursor.fetchone()
        ref_credits = _credits_row[0] if _credits_row else 3.0

        cursor.execute("""
        SELECT id, course_code, course_name, department, level, current_enrollment, max_enrollment,
               'Similar Credits' as match_type
        FROM courses
        WHERE credit_hours = ? AND id != ? AND LOWER(status) = 'active'
          AND NOT (department = ? AND level = ?)
        ORDER BY course_name
        """, (ref_credits, ref_id, ref_dept, ref_level))

        alternatives.extend(cursor.fetchall())

        if not alternatives:
            print("No alternative courses found.")
            return

        # Remove duplicates while preserving order
        seen = set()
        unique_alternatives = []
        for alt in alternatives:
            if alt[0] not in seen:
                seen.add(alt[0])
                unique_alternatives.append(alt)

        print(f"\nAlternative Courses Found ({len(unique_alternatives)}):")
        print(f"{'Code':<8} {'Name':<25} {'Department':<12} {'Level':<12} {'Available':<10} {'Match Type':<15}")
        print("-" * 82)

        for alt in unique_alternatives:
            course_id, code, name, dept, level, current, max_enroll, match_type = alt
            available_spots = max_enroll - current if max_enroll and current else "Unknown"
            name_short = name[:22] + "..." if len(name) > 25 else name

            print(f"{code:<8} {name_short:<25} {dept:<12} {level:<12} {available_spots:<10} {match_type:<15}")

        # Detailed view option
        detail_choice = input("\nEnter course code for detailed comparison (or press Enter to continue): ").strip().upper()

        if detail_choice:
            alt_course = next((a for a in unique_alternatives if a[1] == detail_choice), None)
            if alt_course:
                print(f"\nDETAILED COMPARISON")
                print("-" * 30)

                # Get detailed info for both courses
                cursor.execute("SELECT * FROM courses WHERE id = ?", (ref_id,))
                ref_details = cursor.fetchone()

                cursor.execute("SELECT * FROM courses WHERE id = ?", (alt_course[0],))
                alt_details = cursor.fetchone()

                print(f"Original Course: {ref_code} - {ref_name}")
                print(f"Alternative: {alt_course[1]} - {alt_course[2]}")
                print()

                # Compare key fields
                fields_to_compare = [
                    ("Department", ref_details[6], alt_details[6]),
                    ("Level", ref_details[5], alt_details[5]),
                    ("Credit Hours", ref_details[7], alt_details[7]),
                    ("Course Type", ref_details[18] if len(ref_details) > 18 else "N/A",
                     alt_details[18] if len(alt_details) > 18 else "N/A"),
                    ("Max Enrollment", ref_details[15] if len(ref_details) > 15 else "N/A",
                     alt_details[15] if len(alt_details) > 15 else "N/A")
                ]

                print(f"{'Field':<15} {'Original':<20} {'Alternative':<20}")
                print("-" * 55)
                for field, orig_val, alt_val in fields_to_compare:
                    print(f"{field:<15} {str(orig_val):<20} {str(alt_val):<20}")
            else:
                print("Course code not found in alternatives.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
