from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_create,
    log_read,
    log_update,
    log_delete,
)
from education_system.systems.university.infrastructure.i18n import get_text
from education_system.systems.university.domains.academics.domain.services.course_management.database import initialize_enhanced_database
from education_system.systems.university.domains.academics.domain.services.course_management.validation import validate_course_code


def _snapshot_course_version(conn, cursor, course_id, *, change_reason="",
                             created_by=None):
    """Version the catalogue entry for *course_id* before it is overwritten.

    Best-effort: a versioning failure must not abort a legitimate course edit,
    so problems are reported and the update proceeds.
    """
    try:
        from education_system.systems.university.services.bus.course_versions import (
            snapshot_course,
        )
        cursor.execute(
            "SELECT COALESCE(NULLIF(TRIM(course_code), ''), code) FROM courses "
            "WHERE id = ?", (course_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            return None
        return snapshot_course(row[0], change_reason=change_reason,
                               created_by=created_by, conn=conn)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Note: could not record a catalogue version ({exc}).")
        return None


def resolve_course_id(cursor, value):
    """Resolve user input to a courses.id.

    ``courses.id`` is TEXT (normally the course code), so the input must never be
    coerced with ``int()``. Accepts the id, the course_code or the legacy code
    column, case-insensitively. Returns the real id, or None if nothing matches.
    """
    value = (value or '').strip()
    if not value:
        return None
    cursor.execute(
        """
        SELECT id FROM courses
        WHERE id = ? COLLATE NOCASE
           OR course_code = ? COLLATE NOCASE
           OR code = ? COLLATE NOCASE
        LIMIT 1
        """,
        (value, value, value),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _fit(value, width, fallback='N/A'):
    """Render a value in a fixed-width column, truncating with an ellipsis."""
    text = str(value) if value not in (None, '') else fallback
    return text[:width - 3] + "..." if len(text) > width else text


# Sentinels accepted at any prompt of the create-course flow.
_CANCEL_WORDS = {'cancel', 'quit', 'exit'}
_BACK_WORDS = {'back', 'b'}


class _UserAbort(Exception):
    """Raised when the user cancels the whole create-course flow."""


class _GoBack(Exception):
    """Raised when the user wants to re-answer the previous question."""


def _prompt(text, default=None):
    """Prompt for a single value, honouring the 'back' and 'cancel' sentinels.

    An empty answer falls back to ``default`` when one is given, so a step that
    is revisited via 'back' re-offers whatever was entered the first time.
    """
    suffix = f" [{default}]" if default not in (None, '') else ""
    try:
        raw = input(f"{text}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    value = raw.strip()
    lowered = value.lower()
    if lowered in _CANCEL_WORDS:
        raise _UserAbort
    if lowered in _BACK_WORDS:
        raise _GoBack
    if not value and default is not None:
        return str(default)
    return value


def _step_course_code(data, cursor):
    while True:
        course_code = _prompt(
            get_text('course_mgmt.prompts.course_code', default='Enter course code (e.g., CS101)'),
            data.get('course_code'),
        ).upper()
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

        data['course_code'] = course_code
        return


def _step_course_name(data, cursor):
    while True:
        course_name = _prompt(
            get_text('course_mgmt.prompts.course_name', default='Enter course name'),
            data.get('course_name'),
        )
        if not course_name:
            print(get_text('course_mgmt.errors.name_empty', default='Error: Course name cannot be empty.'))
            continue
        if len(course_name) < 5:
            print(get_text('course_mgmt.errors.name_short', default='Error: Course name must be at least 5 characters.'))
            continue
        data['course_name'] = course_name
        return


def _step_description(data, cursor):
    data['description'] = _prompt(
        get_text('course_mgmt.prompts.description', default='Enter course description'),
        data.get('description'),
    )


def _step_duration(data, cursor):
    duration = None
    duration_input = _prompt(
        get_text('course_mgmt.prompts.duration', default='Enter course duration in years (e.g., 3, 4)'),
        data.get('duration'),
    )
    if duration_input:
        try:
            duration = int(duration_input)
            if duration <= 0:
                print(get_text('course_mgmt.warnings.duration_positive', default='Warning: Duration must be positive. Setting to null.'))
                duration = None
        except ValueError:
            print(get_text('course_mgmt.warnings.duration_number', default='Warning: Duration must be a number. Setting to null.'))
    data['duration'] = duration


def _step_level(data, cursor):
    level_options = ["Undergraduate", "Postgraduate", "PhD", "Certificate", "Diploma"]
    print(f"\n{get_text('course_mgmt.prompts.select_level', default='Select course level')}:")
    for i, level in enumerate(level_options, 1):
        print(f"{i}. {level}")

    level = None
    level_choice = _prompt(
        get_text('course_mgmt.prompts.enter_choice_or_type', default='Enter choice (1-5) or type level'),
        data.get('level'),
    )
    if level_choice:
        if level_choice.isdigit():
            idx = int(level_choice) - 1
            if 0 <= idx < len(level_options):
                level = level_options[idx]
        else:
            level = level_choice
    data['level'] = level


def _step_department(data, cursor):
    data['department'] = _prompt(
        get_text('course_mgmt.prompts.department', default='Enter department'),
        data.get('department'),
    )


def _step_credit_hours(data, cursor):
    credit_hours = 3.0
    credit_input = _prompt("Enter credit hours", data.get('credit_hours', 3.0))
    if credit_input:
        try:
            credit_hours = float(credit_input)
        except ValueError:
            print("Warning: Invalid credit hours. Using default 3.0")
    data['credit_hours'] = credit_hours


def _step_contact_hours(data, cursor):
    contact_hours = 3
    contact_input = _prompt("Enter contact hours per week", data.get('contact_hours', 3))
    if contact_input:
        try:
            contact_hours = int(contact_input)
        except ValueError:
            print("Warning: Invalid contact hours. Using default 3")
    data['contact_hours'] = contact_hours


def _step_learning_outcomes(data, cursor):
    data['learning_outcomes'] = _prompt("Enter learning outcomes (optional)", data.get('learning_outcomes'))


def _step_assessment_methods(data, cursor):
    data['assessment_methods'] = _prompt("Enter assessment methods (optional)", data.get('assessment_methods'))


def _step_required_textbooks(data, cursor):
    data['required_textbooks'] = _prompt("Enter required textbooks (optional)", data.get('required_textbooks'))


def _step_course_fee(data, cursor):
    course_fee = 0.0
    fee_input = _prompt("Enter course fee", data.get('course_fee', 0.0))
    if fee_input:
        try:
            course_fee = float(fee_input)
        except ValueError:
            print("Warning: Invalid fee. Using default 0.0")
    data['course_fee'] = course_fee


def _step_lab_required(data, cursor):
    default = 'y' if data.get('lab_required') else 'n'
    data['lab_required'] = _prompt("Is lab required? (y/n)", default).lower() == 'y'


def _step_online_available(data, cursor):
    default = 'y' if data.get('online_available') else 'n'
    data['online_available'] = _prompt("Is online version available? (y/n)", default).lower() == 'y'


def _step_max_enrollment(data, cursor):
    max_enrollment = 30
    max_input = _prompt("Enter maximum enrollment", data.get('max_enrollment', 30))
    if max_input:
        try:
            max_enrollment = int(max_input)
        except ValueError:
            print("Warning: Invalid enrollment number. Using default 30")
    data['max_enrollment'] = max_enrollment


def _step_course_type(data, cursor):
    type_options = ["Core", "Elective", "Major-specific", "General Education"]
    print("\nSelect course type:")
    for i, ctype in enumerate(type_options, 1):
        print(f"{i}. {ctype}")

    course_type = "Core"
    type_choice = _prompt("Enter choice (1-4) or type", data.get('course_type', 'Core'))
    if type_choice:
        if type_choice.isdigit():
            idx = int(type_choice) - 1
            if 0 <= idx < len(type_options):
                course_type = type_options[idx]
        else:
            course_type = type_choice
    data['course_type'] = course_type


def _step_tags(data, cursor):
    data['tags'] = _prompt("Enter tags (comma-separated, optional)", data.get('tags'))


def _step_availability(data, cursor):
    print("\nSelect availability periods (comma-separated):")
    print("Options: Fall, Spring, Summer, Winter")
    availability = _prompt("Enter periods", data.get('availability', 'Fall,Spring'))
    data['availability'] = availability or "Fall,Spring"


def _step_confirm(data, cursor):
    print("\nReview new course")
    print("-----------------")
    for label, key in (
        ("Course code", 'course_code'),
        ("Course name", 'course_name'),
        ("Description", 'description'),
        ("Duration (years)", 'duration'),
        ("Level", 'level'),
        ("Department", 'department'),
        ("Credit hours", 'credit_hours'),
        ("Contact hours/week", 'contact_hours'),
        ("Learning outcomes", 'learning_outcomes'),
        ("Assessment methods", 'assessment_methods'),
        ("Required textbooks", 'required_textbooks'),
        ("Course fee", 'course_fee'),
        ("Lab required", 'lab_required'),
        ("Online available", 'online_available'),
        ("Max enrollment", 'max_enrollment'),
        ("Course type", 'course_type'),
        ("Tags", 'tags'),
        ("Availability", 'availability'),
    ):
        value = data.get(key)
        if isinstance(value, bool):
            value = 'Yes' if value else 'No'
        print(f"  {label}: {value if value not in (None, '') else '-'}")

    while True:
        answer = _prompt("Create this course? (y/n)", 'y').lower()
        if answer in ('y', 'yes'):
            return
        if answer in ('n', 'no'):
            raise _UserAbort
        print("Please answer 'y' or 'n' (or 'back' to change an answer, 'cancel' to abort).")


# Ordered prompt sequence. 'back' at any step returns to the previous entry.
_CREATE_COURSE_STEPS = (
    _step_course_code,
    _step_course_name,
    _step_description,
    _step_duration,
    _step_level,
    _step_department,
    _step_credit_hours,
    _step_contact_hours,
    _step_learning_outcomes,
    _step_assessment_methods,
    _step_required_textbooks,
    _step_course_fee,
    _step_lab_required,
    _step_online_available,
    _step_max_enrollment,
    _step_course_type,
    _step_tags,
    _step_availability,
    _step_confirm,
)


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
        print("Type 'back' at any prompt to change the previous answer, or 'cancel' to abort.")

        # Walk the prompt sequence, allowing the user to step backwards.
        data = {}
        index = 0
        while index < len(_CREATE_COURSE_STEPS):
            try:
                _CREATE_COURSE_STEPS[index](data, cursor)
            except _GoBack:
                if index == 0:
                    print("Already at the first question. Type 'cancel' to abort.")
                    continue
                index -= 1
                continue
            except _UserAbort:
                print("\nCourse creation cancelled. No course was created.")
                return False
            index += 1

        course_code = data['course_code']
        course_name = data['course_name']
        description = data['description']
        duration = data['duration']
        level = data['level']
        department = data['department']
        credit_hours = data['credit_hours']
        contact_hours = data['contact_hours']
        learning_outcomes = data['learning_outcomes']
        assessment_methods = data['assessment_methods']
        required_textbooks = data['required_textbooks']
        course_fee = data['course_fee']
        lab_required = data['lab_required']
        online_available = data['online_available']
        max_enrollment = data['max_enrollment']
        course_type = data['course_type']
        tags = data['tags']
        availability = data['availability']

        # Canonical write, shared with the Course Management GUI and the API.
        # The service owns code uniqueness, the id convention (code as id),
        # both column families and the course.changed event, so this command
        # no longer keeps its own copy of any of that.
        from education_system.systems.university.application.course_lifecycle_service import (
            CourseCommand,
            CourseLifecycleService,
            CourseValidationError,
        )
        actor = str((auth.current_user or {}).get('id', 'unknown'))
        try:
            result = CourseLifecycleService().create(
                CourseCommand(
                    course_code=course_code, course_name=course_name,
                    credit_hours=credit_hours, description=description,
                    level=level, department=department,
                    max_enrollment=max_enrollment, course_type=course_type,
                    course_fee=course_fee,
                    lab_required=bool(lab_required),
                    online_available=bool(online_available),
                ),
                actor_id=actor,
            )
        except CourseValidationError as exc:
            for field, message in exc.errors.items():
                print(f"Error: {field} {message}")
            return False

        # Fields the prompt sequence collects that the CourseCommand does not
        # carry. Written straight after creation rather than widening the
        # command, so the extra catalogue detail this CLI gathers is kept.
        extra = {
            "duration": duration,
            "contact_hours_per_week": contact_hours,
            "learning_outcomes": learning_outcomes,
            "assessment_methods": assessment_methods,
            "required_textbooks": required_textbooks,
            "tags": tags,
            "availability_periods": availability,
        }
        try:
            CourseLifecycleService().update(
                result.course_code, extra, actor_id=actor,
                reason="Detail captured during course creation",
            )
        except CourseValidationError as exc:
            print(f"Note: course created, but extra detail was not saved: {exc}")

        print(f"\nEnhanced course '{course_name}' (Code: {result.course_code}) created successfully!")
        print(f"Course ID: {result.course_id}")
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
        print(f"{get_text('course_mgmt.headers.id', default='ID'):<12} {get_text('course_mgmt.headers.code', default='Code'):<8} {get_text('course_mgmt.headers.name', default='Name'):<25} {get_text('course_mgmt.headers.dept', default='Dept'):<12} {get_text('course_mgmt.headers.level', default='Level'):<12} {get_text('course_mgmt.headers.type', default='Type'):<12} {get_text('course_mgmt.headers.credits', default='Credits'):<8} {get_text('course_mgmt.headers.enrolled', default='Enrolled'):<10} {get_text('course_mgmt.headers.status', default='Status'):<10}")
        print("-" * 117)

        for course in courses:
            course_id, code, name, dept, level, ctype, credits, current, max_enroll, status, created = course

            # Truncate long values so the columns stay aligned
            na = get_text('common.na', default='N/A')
            id_display = _fit(course_id, 12, na)
            name_display = _fit(name, 25, na)
            dept_display = _fit(dept, 12, na)
            level_display = _fit(level, 12, na)
            type_display = _fit(ctype, 12, na)
            enrollment_display = f"{current or 0}/{max_enroll or 0}"

            print(f"{id_display:<12} {code:<8} {name_display:<25} {dept_display:<12} {level_display:<12} {type_display:<12} {credits:<8} {enrollment_display:<10} {status:<10}")

        # Enhanced detail view option
        detail_choice = input(f"\n{get_text('course_mgmt.prompts.detail_view', default='Enter a course ID or code for detailed view (or press Enter to return)')}: ")
        if detail_choice.strip():
            detail_id = resolve_course_id(cursor, detail_choice)
            if detail_id is None:
                print(get_text('course_mgmt.errors.invalid_id', default='No course matches that ID or code.'))
            else:
                view_course_details(cursor, detail_id)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error viewing courses: {e}")
    finally:
        if conn:
            conn.close()


def view_course_details(cursor, course_id):
    """View detailed information about a specific course"""
    # Select the columns by name: `SELECT *` positions do not match the physical
    # column order of the courses table, which previously mislabelled every field.
    cursor.execute("""
    SELECT id, course_code, course_name, description, duration, level, department,
           credit_hours, contact_hours_per_week, course_type, max_enrollment,
           current_enrollment, status, lab_required, online_available, course_fee,
           tags, availability_periods
    FROM courses WHERE id = ?
    """, (course_id,))

    course = cursor.fetchone()
    if not course:
        print("Course not found.")
        return

    (cid, code, name, description, duration, level, department, credit_hours,
     contact_hours, course_type, max_enrollment, current_enrollment, status,
     lab_required, online_available, course_fee, tags, availability) = course

    print("\nDetailed Course Information:")
    print("-" * 40)
    print(f"ID: {cid}")
    print(f"Code: {code}")
    print(f"Name: {name}")
    print(f"Description: {description or 'N/A'}")
    print(f"Duration: {duration} years" if duration else "Duration: N/A")
    print(f"Level: {level or 'N/A'}")
    print(f"Department: {department or 'N/A'}")
    print(f"Credit Hours: {credit_hours}")
    print(f"Contact Hours/Week: {contact_hours}")
    print(f"Course Type: {course_type or 'N/A'}")
    print(f"Max Enrollment: {max_enrollment or 0}")
    print(f"Current Enrollment: {current_enrollment or 0}")
    print(f"Status: {status or 'N/A'}")
    print(f"Lab Required: {'Yes' if lab_required else 'No'}")
    print(f"Online Available: {'Yes' if online_available else 'No'}")
    print(f"Course Fee: £{course_fee or 0.0}")
    print(f"Tags: {tags or 'None'}")
    print(f"Availability: {availability or 'N/A'}")


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

        # Canonical write, shared with the GUI and the API. The service takes
        # the version snapshot itself and mirrors course_name/credit_hours
        # onto the legacy name/credits columns, which this command did not do.
        from education_system.systems.university.application.course_lifecycle_service import (
            CourseLifecycleService,
            CourseValidationError,
        )
        actor = str((auth.current_user or {}).get('id', 'unknown'))
        if new_code and str(new_code).upper() != str(code).upper():
            # students.course stores the code by value, so renaming one would
            # orphan every enrolment on it. Changing a code needs a migration.
            print(f"Note: the course code stays '{code}'. Renaming a code would "
                  "orphan existing enrolments, so it is not editable here.")
        try:
            CourseLifecycleService().update(
                course_id,
                {
                    "course_name": new_name,
                    "description": new_desc,
                    "credit_hours": new_credit_hours,
                    "max_enrollment": new_max_enrollment,
                },
                actor_id=actor,
                reason="Updated via course management CLI",
            )
        except CourseValidationError as exc:
            for field, message in exc.errors.items():
                print(f"Error: {field} {message}")
            return False

        print(f"\nCourse updated successfully: {code} - {new_name}")
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

        # Canonical cascade, shared with the GUI and the API. The impact was
        # printed and confirmed above, which is what acknowledged_impact
        # records; the service refuses a blind delete without it.
        from education_system.systems.university.application.course_lifecycle_service import (
            CourseLifecycleService,
            CourseValidationError,
        )
        actor = str((auth.current_user or {}).get('id', 'unknown'))
        try:
            CourseLifecycleService().delete(
                course_id, actor_id=actor,
                reason="Deleted via course management CLI",
                acknowledged_impact=True,
            )
            rows_deleted = 1
        except CourseValidationError as exc:
            for field, message in exc.errors.items():
                print(f"Error: {field} {message}")
            return False

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
