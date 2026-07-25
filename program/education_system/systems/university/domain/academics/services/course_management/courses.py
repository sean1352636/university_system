from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_create,
    log_read,
    log_update,
    log_delete,
)
from education_system.systems.university.infrastructure.i18n import get_text
from education_system.systems.university.domain.academics.services.course_management.database import initialize_enhanced_database
from education_system.systems.university.domain.academics.services.course_management.validation import validate_course_code


@log_create(module="course_management", description="Creating new course with enhanced features")
def create_enhanced_course(auth):
    """Create a new course with all enhanced features"""
    if not auth or not auth.current_user:
        print(get_text('course_mgmt.login_required', default='You must be logged in to create courses.'))
        return False

    if not auth.check_permission('manage_courses'):
        print(get_text('course_mgmt.no_permission_create', default="You don't have permission to create courses."))
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Ensure enhanced schema exists
        initialize_enhanced_database()

        print(f"\n{get_text('course_mgmt.create_title', default='Create New Enhanced Course')}")
        print("==========================")

        # Basic course information
        while True:
            course_code = input(f"{get_text('course_mgmt.prompts.course_code', default='Enter course code (e.g., CS101)')}: ").strip().upper()
            if not course_code:
                print(get_text('course_mgmt.errors.code_empty', default='Error: Course code cannot be empty.'))
                continue

            if not validate_course_code(course_code):
                print(get_text('course_mgmt.errors.code_invalid', default='Error: Invalid course code format. It should be 2-4 letters followed by 2-3 numbers.'))
                continue

            cursor.execute("SELECT course_code FROM courses WHERE course_code = ?", (course_code,))
            if cursor.fetchone():
                print(get_text('course_mgmt.errors.code_exists', default="Error: Course code '{code}' already exists.").format(code=course_code))
                continue
            break

        while True:
            course_name = input(f"{get_text('course_mgmt.prompts.course_name', default='Enter course name')}: ").strip()
            if not course_name:
                print(get_text('course_mgmt.errors.name_empty', default='Error: Course name cannot be empty.'))
                continue
            if len(course_name) < 5:
                print(get_text('course_mgmt.errors.name_short', default='Error: Course name must be at least 5 characters.'))
                continue
            break

        description = input(f"{get_text('course_mgmt.prompts.description', default='Enter course description')}: ").strip()

        # Duration
        duration = None
        duration_input = input(f"{get_text('course_mgmt.prompts.duration', default='Enter course duration in years (e.g., 3, 4)')}: ").strip()
        if duration_input:
            try:
                duration = int(duration_input)
                if duration <= 0:
                    print(get_text('course_mgmt.warnings.duration_positive', default='Warning: Duration must be positive. Setting to null.'))
                    duration = None
            except ValueError:
                print(get_text('course_mgmt.warnings.duration_number', default='Warning: Duration must be a number. Setting to null.'))

        # Level
        level_options = ["Undergraduate", "Postgraduate", "PhD", "Certificate", "Diploma"]
        print(f"\n{get_text('course_mgmt.prompts.select_level', default='Select course level')}:")
        for i, level in enumerate(level_options, 1):
            print(f"{i}. {level}")

        level = None
        level_choice = input(f"{get_text('course_mgmt.prompts.enter_choice_or_type', default='Enter choice (1-5) or type level')}: ").strip()
        if level_choice:
            if level_choice.isdigit():
                idx = int(level_choice) - 1
                if 0 <= idx < len(level_options):
                    level = level_options[idx]
            else:
                level = level_choice

        department = input(f"{get_text('course_mgmt.prompts.department', default='Enter department')}: ").strip()

        # Enhanced fields
        credit_hours = 3.0
        credit_input = input("Enter credit hours (default 3.0): ").strip()
        if credit_input:
            try:
                credit_hours = float(credit_input)
            except ValueError:
                print("Warning: Invalid credit hours. Using default 3.0")

        contact_hours = 3
        contact_input = input("Enter contact hours per week (default 3): ").strip()
        if contact_input:
            try:
                contact_hours = int(contact_input)
            except ValueError:
                print("Warning: Invalid contact hours. Using default 3")

        learning_outcomes = input("Enter learning outcomes (optional): ").strip()
        assessment_methods = input("Enter assessment methods (optional): ").strip()
        required_textbooks = input("Enter required textbooks (optional): ").strip()

        course_fee = 0.0
        fee_input = input("Enter course fee (default 0.0): ").strip()
        if fee_input:
            try:
                course_fee = float(fee_input)
            except ValueError:
                print("Warning: Invalid fee. Using default 0.0")

        lab_required = input("Is lab required? (y/n): ").strip().lower() == 'y'
        online_available = input("Is online version available? (y/n): ").strip().lower() == 'y'

        max_enrollment = 30
        max_input = input("Enter maximum enrollment (default 30): ").strip()
        if max_input:
            try:
                max_enrollment = int(max_input)
            except ValueError:
                print("Warning: Invalid enrollment number. Using default 30")

        # Course type
        type_options = ["Core", "Elective", "Major-specific", "General Education"]
        print("\nSelect course type:")
        for i, ctype in enumerate(type_options, 1):
            print(f"{i}. {ctype}")

        course_type = "Core"
        type_choice = input("Enter choice (1-4) or type: ").strip()
        if type_choice:
            if type_choice.isdigit():
                idx = int(type_choice) - 1
                if 0 <= idx < len(type_options):
                    course_type = type_options[idx]
            else:
                course_type = type_choice

        tags = input("Enter tags (comma-separated, optional): ").strip()

        # Availability periods
        print("\nSelect availability periods (comma-separated):")
        print("Options: Fall, Spring, Summer, Winter")
        availability = input("Enter periods (default: Fall,Spring): ").strip()
        if not availability:
            availability = "Fall,Spring"

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Generate unique ID for the course
        import uuid
        course_id = str(uuid.uuid4())

        # Insert the course
        cursor.execute('''
        INSERT INTO courses (
            id, code, name, date_added,
            course_code, course_name, description, duration, level, department,
            credit_hours, contact_hours_per_week, learning_outcomes, assessment_methods,
            required_textbooks, course_fee, lab_required, online_available,
            max_enrollment, course_type, tags, availability_periods,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            course_id, course_code, course_name, timestamp,
            course_code, course_name, description, duration, level, department,
            credit_hours, contact_hours, learning_outcomes, assessment_methods,
            required_textbooks, course_fee, lab_required, online_available,
            max_enrollment, course_type, tags, availability,
            timestamp, timestamp
        ))

        course_id = cursor.lastrowid
        conn.commit()

        print(f"\nEnhanced course '{course_name}' (Code: {course_code}) created successfully!")
        print(f"Course ID: {course_id}")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error creating course: {e}")
        return False
    finally:
        if conn:
            conn.close()


@log_create(module="course_management", description="Creating new course")
def create_course(auth):
    """Legacy function - redirects to enhanced version"""
    return create_enhanced_course(auth)


@log_read(module="course_management", description="Viewing all courses")
def view_all_courses(auth):
    """View all courses in the system with enhanced display"""
    if not auth or not auth.current_user:
        print(get_text('course_mgmt.login_required', default='You must be logged in to view courses.'))
        return

    if not auth.check_permission('view_courses'):
        print(get_text('course_mgmt.no_permission_view', default="You don't have permission to view courses."))
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if the courses table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
        if not cursor.fetchone():
            print(get_text('course_mgmt.no_courses_table', default='No courses found. The courses table has not been created yet.'))
            return

        # Get all courses with enhanced information
        cursor.execute("""
        SELECT id, course_code, course_name, department, level, course_type,
               credit_hours, current_enrollment, max_enrollment, status, created_at
        FROM courses
        ORDER BY course_code
        """)

        courses = cursor.fetchall()

        if not courses:
            print(get_text('course_mgmt.no_courses_found', default='No courses found in the system.'))
            return

        print(f"\n{get_text('course_mgmt.all_courses_title', default='All Courses (Enhanced View)')}:")
        print(f"{get_text('course_mgmt.headers.id', default='ID'):<5} {get_text('course_mgmt.headers.code', default='Code'):<8} {get_text('course_mgmt.headers.name', default='Name'):<25} {get_text('course_mgmt.headers.dept', default='Dept'):<12} {get_text('course_mgmt.headers.level', default='Level'):<12} {get_text('course_mgmt.headers.type', default='Type'):<12} {get_text('course_mgmt.headers.credits', default='Credits'):<8} {get_text('course_mgmt.headers.enrolled', default='Enrolled'):<10} {get_text('course_mgmt.headers.status', default='Status'):<10}")
        print("-" * 102)

        for course in courses:
            course_id, code, name, dept, level, ctype, credits, current, max_enroll, status, created = course

            # Truncate long names
            name_display = name[:22] + "..." if len(name) > 25 else name
            dept_display = dept[:9] + "..." if dept and len(dept) > 12 else dept or get_text('common.na', default='N/A')
            level_display = level[:9] + "..." if level and len(level) > 12 else level or get_text('common.na', default='N/A')
            type_display = ctype[:9] + "..." if ctype and len(ctype) > 12 else ctype or get_text('common.na', default='N/A')
            enrollment_display = f"{current or 0}/{max_enroll or 0}"

            print(f"{course_id:<5} {code:<8} {name_display:<25} {dept_display:<12} {level_display:<12} {type_display:<12} {credits:<8} {enrollment_display:<10} {status:<10}")

        # Enhanced detail view option
        detail_choice = input(f"\n{get_text('course_mgmt.prompts.detail_view', default='Enter a course ID for detailed view (or press Enter to return)')}: ")
        if detail_choice.strip():
            try:
                detail_id = int(detail_choice)
                view_course_details(cursor, detail_id)
            except ValueError:
                print(get_text('course_mgmt.errors.invalid_id', default='Invalid ID. Please enter a number.'))

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error viewing courses: {e}")
    finally:
        if conn:
            conn.close()


def view_course_details(cursor, course_id):
    """View detailed information about a specific course"""
    cursor.execute("""
    SELECT * FROM courses WHERE id = ?
    """, (course_id,))

    course = cursor.fetchone()
    if not course:
        print("Course not found.")
        return

    print("\nDetailed Course Information:")
    print("-" * 40)
    print(f"ID: {course[0]}")
    print(f"Code: {course[1]}")
    print(f"Name: {course[2]}")
    print(f"Description: {course[3] or 'N/A'}")
    print(f"Duration: {course[4]} years" if course[4] else "Duration: N/A")
    print(f"Level: {course[5] or 'N/A'}")
    print(f"Department: {course[6] or 'N/A'}")
    print(f"Credit Hours: {course[7]}")
    print(f"Contact Hours/Week: {course[8]}")
    print(f"Course Type: {course[15]}")
    print(f"Max Enrollment: {course[14]}")
    print(f"Current Enrollment: {course[15]}")
    print(f"Status: {course[16]}")
    print(f"Lab Required: {'Yes' if course[12] else 'No'}")
    print(f"Online Available: {'Yes' if course[13] else 'No'}")
    print(f"Course Fee: £{course[11]}")
    print(f"Tags: {course[17] or 'None'}")
    print(f"Availability: {course[18]}")


@log_update(module="course_management", description="Updating course")
def update_course(auth):
    """Update an existing course with enhanced features"""
    if not auth or not auth.current_user:
        print("You must be logged in to update courses.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to update courses.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if the courses table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
        if not cursor.fetchone():
            print("No courses found. The courses table has not been created yet.")
            return False

        # Show all courses for selection
        cursor.execute("SELECT id, course_code, course_name, status FROM courses ORDER BY course_code")
        courses = cursor.fetchall()

        if not courses:
            print("No courses found in the system.")
            return False

        print("\nSelect a course to update:")
        for i, course in enumerate(courses, 1):
            db_id, code, name, status = course
            print(f"{i}. {code} - {name} ({status})")

        while True:
            try:
                choice_num = int(input("\nEnter course number to update (or 0 to cancel): "))
                if choice_num == 0:
                    print("Update cancelled.")
                    return False

                if 1 <= choice_num <= len(courses):
                    course_id = courses[choice_num - 1][0]
                else:
                    print(f"Please enter a number between 0 and {len(courses)}.")
                    continue

                # Get current course details
                cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
                course = cursor.fetchone()

                if not course:
                    print(f"No course found with ID {course_id}.")
                    continue

                break
            except ValueError:
                print("Please enter a valid number.")

        # Current values - use index-based access for flexibility with schema changes
        id = course[0]
        code = course[1] or course[10] or ""  # code or course_code
        name = course[2] or course[11] or ""  # name or course_name
        desc = course[16] if len(course) > 16 else ""
        credit_hours = course[13] if len(course) > 13 and course[13] else (course[3] if course[3] else 3)
        max_enrollment = course[15] if len(course) > 15 and course[15] else 30
        current_enrollment = course[14] if len(course) > 14 and course[14] else 0
        status = course[8] if len(course) > 8 else "Active"
        course_type = course[18] if len(course) > 18 else "Core"
        tags = course[21] if len(course) > 21 else ""
        availability = course[22] if len(course) > 22 else "Fall,Spring"
        learning_outcomes = course[23] if len(course) > 23 else ""
        assessment_methods = course[24] if len(course) > 24 else ""
        textbooks = course[25] if len(course) > 25 else ""
        course_fee = course[26] if len(course) > 26 and course[26] else 0.0
        lab_required = course[27] if len(course) > 27 else False
        online_available = course[28] if len(course) > 28 else False
        contact_hours = course[29] if len(course) > 29 and course[29] else 3

        print(f"\nUpdating Course: {code} - {name}")
        print("Enter new values (leave blank to keep current):")

        new_code = input(f"Course Code [{code}]: ").strip().upper() or code
        new_name = input(f"Course Name [{name}]: ").strip() or name
        new_desc = input(f"Description [{desc}]: ").strip() or desc

        # Enhanced fields
        new_credit_hours = credit_hours
        credit_input = input(f"Credit Hours [{credit_hours}]: ").strip()
        if credit_input:
            try:
                new_credit_hours = float(credit_input)
            except ValueError:
                print("Invalid credit hours. Keeping current value.")

        new_max_enrollment = max_enrollment
        max_input = input(f"Max Enrollment [{max_enrollment}]: ").strip()
        if max_input:
            try:
                new_max_enrollment = int(max_input)
            except ValueError:
                print("Invalid enrollment number. Keeping current value.")

        # Update the course
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Update query handling both schemas
        cursor.execute("""
        UPDATE courses
        SET course_code = ?, course_name = ?, description = ?, credit_hours = ?,
            max_enrollment = ?, updated_at = ?
        WHERE id = ?
        """, (new_code, new_name, new_desc, new_credit_hours, new_max_enrollment, timestamp, course_id))

        conn.commit()

        print(f"\nCourse updated successfully: {new_code} - {new_name}")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()


@log_delete(module="course_management", description="Deleting course")
def delete_course(auth):
    """Delete an existing course (enhanced with safety checks)"""
    # Keep the original implementation but add enhanced safety checks
    if not auth or not auth.current_user:
        print("You must be logged in to delete courses.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to delete courses.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show all courses for selection
        cursor.execute("SELECT id, course_code, course_name, current_enrollment FROM courses ORDER BY course_code")
        courses = cursor.fetchall()

        if not courses:
            print("No courses found in the system.")
            return False

        print("\nSelect a course to delete:")
        for i, course in enumerate(courses, 1):
            db_id, code, name, enrolled = course
            enrolled_display = enrolled if enrolled is not None else 0
            print(f"{i}. {code} - {name} (Enrolled: {enrolled_display})")

        while True:
            try:
                choice_num = int(input("\nEnter course number to delete (or 0 to cancel): "))
                if choice_num == 0:
                    print("Delete cancelled.")
                    return False

                if 1 <= choice_num <= len(courses):
                    course_id = courses[choice_num - 1][0]
                else:
                    print(f"Please enter a number between 0 and {len(courses)}.")
                    continue

                # Check if course exists
                cursor.execute("SELECT course_code, course_name, current_enrollment FROM courses WHERE id = ?", (course_id,))
                course = cursor.fetchone()

                if not course:
                    print(f"No course found with ID {course_id}.")
                    continue

                code, name, enrolled = course
                break
            except ValueError:
                print("Please enter a valid number.")

        # Enhanced safety checks
        enrolled = enrolled or 0

        # Check for prerequisites
        cursor.execute("SELECT COUNT(*) FROM course_prerequisites WHERE prerequisite_course_id = ?", (course_id,))
        prereq_count = cursor.fetchone()[0]

        # Check for schedules
        cursor.execute("SELECT COUNT(*) FROM course_schedule WHERE course_id = ?", (course_id,))
        schedule_count = cursor.fetchone()[0]

        # Check for waitlists
        cursor.execute("SELECT COUNT(*) FROM course_waitlist WHERE course_id = ?", (course_id,))
        waitlist_count = cursor.fetchone()[0]

        print(f"\nDELETION IMPACT ANALYSIS for '{code} - {name}':")
        print(f"- Students enrolled: {enrolled}")
        print(f"- Courses depending on this as prerequisite: {prereq_count}")
        print(f"- Schedule entries: {schedule_count}")
        print(f"- Waitlist entries: {waitlist_count}")

        if enrolled > 0 or prereq_count > 0:
            print("\n⚠️  WARNING: This deletion will have significant impact!")
            confirm = input("Type 'DELETE CONFIRMED' to proceed: ")

            if confirm != 'DELETE CONFIRMED':
                print("Delete cancelled.")
                return False
        else:
            confirm = input(f"\nAre you sure you want to delete '{code} - {name}'? This cannot be undone. (y/n): ").lower()

            if confirm != 'y':
                print("Delete cancelled.")
                return False

        # Delete related records first
        cursor.execute("DELETE FROM course_prerequisites WHERE course_id = ? OR prerequisite_course_id = ?", (course_id, course_id))
        cursor.execute("DELETE FROM course_schedule WHERE course_id = ?", (course_id,))
        cursor.execute("DELETE FROM course_waitlist WHERE course_id = ?", (course_id,))
        cursor.execute("DELETE FROM course_history WHERE course_id = ?", (course_id,))
        cursor.execute("DELETE FROM course_analytics WHERE course_id = ?", (course_id,))

        # Delete the course
        cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        rows_deleted = cursor.rowcount

        conn.commit()

        if rows_deleted > 0:
            print(f"\nCourse '{code} - {name}' and all related data deleted successfully.")

            if enrolled > 0:
                print(f"\nIMPORTANT: {enrolled} students now need to be assigned to different courses.")
            if prereq_count > 0:
                print(f"IMPORTANT: {prereq_count} courses had this as a prerequisite - please review.")
        else:
            print("Error: No course was deleted.")

        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()
