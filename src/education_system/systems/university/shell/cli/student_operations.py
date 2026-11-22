"""
Student operations for CLI system.

Handles student CRUD operations, record management, and display.
"""

import random
import secrets

from education_system.systems.university.shell.cli.imports import (
    logging, sqlite3, time, datetime, DB_PATH, logger, _t,
    log_activity, log_create, log_read, log_update, log_delete, get_auth,
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2, optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
)

from education_system.systems.university.shell.cli.auth_manager import ensure_user_in_communication_system
from education_system.systems.university.shell.cli.database_manager import DatabaseError, ValidationError, safe_db_operation_with_retry, enhanced_db_operation
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.infrastructure.email.email_service import (
    send_registration_confirmation, send_update_confirmation
)
from education_system.systems.university.domains.admissions.domain.services.admissions_selection import (
    ensure_selection_schema,
    prompt_alevels_cli,
    format_qualifications,
    list_active_courses,
    eligible_courses,
    enrol_student_in_curriculum,
    ensure_module_chat_rooms_and_join,
    purge_user_chat_on_cursor,
    get_course,
)
from education_system.systems.university.services.student_provisioning import (
    compute_age as _compute_age,
    default_student_password as _default_student_password,
    provision_student_login as _provision_student_login,
)
from education_system.systems.university.infrastructure.database.db import foreign_keys_off

# Global auth
auth = None

def set_auth(auth_instance):
    """Set the authentication instance for this module"""
    global auth
    auth = auth_instance

def get_db_connection(timeout=5.0):
    """Get database connection"""
    return sqlite3.connect(DB_PATH, timeout=timeout)


def _print_course_table(courses, tariff=None):
    """Render the catalogue with an eligibility marker for a given tariff."""
    print(f"\n{'#':<3} {'Code':<8} {'Course':<32} {'Req. tariff':<12} Status")
    print("-" * 72)
    for i, c in enumerate(courses, 1):
        if tariff is None:
            status = ""
        else:
            status = "ELIGIBLE" if tariff >= c['min_tariff'] else "below requirement"
        print(f"{i:<3} {c['code']:<8} {str(c['name'])[:32]:<32} {c['min_tariff']:<12} {status}")


def _pick_course(courses):
    """Prompt for a course number; returns the chosen dict or None to cancel."""
    while True:
        choice = input("\nEnter course number (or 0 to cancel): ").strip()
        if choice == '0':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(courses):
            return courses[int(choice) - 1]
        print("Invalid selection. Please enter a number from the list.")


def _select_course_for_applicant(allow_override=False):
    """Capture A-level grades, gate on tariff, and pick a course.

    Returns a dict ``{code, name, entry_qualifications, tariff}`` or ``None``
    if the applicant cancels or qualifies for nothing.
    """
    ensure_selection_schema()

    pairs, tariff = prompt_alevels_cli()
    entry_qual = format_qualifications(pairs)

    courses = list_active_courses()
    if not courses:
        print("\nNo courses are available to study. Add a course via course "
              "management first.")
        return None

    print("\nCourses available to study:")
    _print_course_table(courses, tariff)
    chosen = _pick_course(courses)
    if chosen is None:
        return None

    # Eligibility gate: if they picked something they don't qualify for,
    # show only the courses they CAN study and let them pick again.
    override = ""
    if tariff < chosen['min_tariff'] and allow_override:
        print(f"\n{chosen['code']} needs {chosen['min_tariff']} UCAS points; the grades "
              f"give {tariff}.")
        if input("Admit with an admissions override? (y/n): ").strip().lower() == 'y':
            while not override:
                override = input("Reason for the override: ").strip()
    if tariff < chosen['min_tariff'] and not override:
        print(f"\nYou do not meet the entry requirement for "
              f"{chosen['code']} - {chosen['name']} "
              f"(needs {chosen['min_tariff']} UCAS points; you have {tariff}).")
        eligible = eligible_courses(tariff)
        if not eligible:
            print("Unfortunately your grades do not meet the entry requirement "
                  "for any course currently on offer.")
            return None
        print("\nCourses you ARE eligible to study:")
        _print_course_table(eligible, tariff)
        chosen = _pick_course(eligible)
        if chosen is None:
            return None

    return {
        'code': chosen['code'],
        'name': chosen['name'],
        'entry_qualifications': entry_qual,
        'tariff': tariff,
        'override': override,
    }


def create_student_record():
    """Create a student (contact details, entry route, duplicate check,
    visa) through the lifecycle service."""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to create student records.")
        return
    if not auth.check_permission('create_student'):
        print("You don't have permission to create student records.")
        return
    from education_system.systems.university.shell.cli import student_records_cli
    student_records_cli.create_student(
        auth, select_course_for_applicant=_select_course_for_applicant,
        list_courses=list_active_courses, pick_course=_course_menu_pick)
    input("\nPress Enter to continue...")


def _course_menu_pick(courses):
    _print_course_table(courses)
    return _pick_course(courses)

def view_student_record():
    global auth

    # Check for permission
    if not auth or not auth.current_user:
        print("You must be logged in to view student records.")
        return

    # Different behavior based on role/permissions
    if not (auth.has_permission('view_any_student') or auth.has_permission('view_own_record')):
        print("You don't have permission to view student records.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    if auth.has_permission('view_any_student'):
        # Admin or staff - can view any student
        cursor.execute('''
        SELECT * FROM students
        ''')

        students = cursor.fetchall()

        if not students:
            print("No student records found.")
            conn.close()
            return

        for student in students:
            display_student_record(student)

    elif auth.has_permission('view_own_record'):
        # Student - can only view their own record
        student_id = None

        # Get the student_id associated with this user - updated query for new database structure
        cursor.execute('''
        SELECT student_id FROM users WHERE id = ?
        ''', (auth.current_user['id'],))

        result = cursor.fetchone()
        if result and result[0]:
            student_id = result[0]

            # Fetch and display just this student's record
            cursor.execute('''
            SELECT * FROM students WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()
            if student:
                display_student_record(student)
            else:
                print("Your student record was not found.")
        else:
            print("No student ID associated with your account.")

    conn.close()


#: Fields a student may change on their own record.
OWN_PROFILE_FIELDS = ("pronouns", "emergency_contact", "phone", "personal_email", "address")


def update_student_record():
    """Edit a record (with a reason) or transfer it to another course."""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to update student records.")
        return
    if not (auth.has_permission('update_any_student') or auth.has_permission('update_own_profile')):
        print("You don't have permission to update student records.")
        return
    from education_system.systems.university.shell.cli import student_records_cli
    if not auth.has_permission('update_any_student'):
        with get_db_connection() as lookup_conn:
            row = lookup_conn.execute(
                "SELECT student_id FROM users WHERE id=?", (auth.current_user['id'],)
            ).fetchone()
        if not row or not row[0]:
            print("No student ID linked to your account.")
            return
        student_records_cli.update_student(auth, str(row[0]), allowed=OWN_PROFILE_FIELDS)
        return
    student_id = input("Enter student ID to update: ").strip()
    if not student_id:
        return
    if input("1. Edit details  2. Transfer to another course: ").strip() == '2':
        selected = _course_menu_pick(list_active_courses())
        if selected:
            student_records_cli.transfer_student(auth, student_id, selected['code'])
        return
    student_records_cli.update_student(auth, student_id)

def delete_student_record():
    """Withdraw a student: records kept, sign-in switched off, reversible.
    Permanent erasure is a separate dual-control request (Erasure requests)."""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to withdraw students.")
        return
    if not auth.check_permission('delete_any_student'):
        print("You don't have permission to withdraw students.")
        return
    student_id = input("Enter the ID number of the student to withdraw: ").strip()
    if not student_id:
        print("Student ID is required.")
        return
    from education_system.systems.university.shell.cli import student_records_cli
    student_records_cli.withdraw_student(auth, student_id)
    input("\nPress Enter to continue...")

def display_student_record(student):
    """Helper function to display a student record"""
    if not student:
        print("Invalid student record.")
        return

    print("\n" + "=" * 40)
    print("Student Record:")
    print("=" * 40)
    print(f"Student ID: {student[0]}")
    print(f"Email: {student[1]}")
    print(f"Title: {student[2]}")
    print(f"First Name: {student[3]}")
    print(f"Middle Name: {student[4]}")
    print(f"Last Name: {student[5]}")
    print(f"Gender: {student[6]}")
    print(f"Date of Birth: {student[7]}")
    print(f"Age: {student[8]}")
    print(f"Course: {student[9]}")
    print(f"Registration Date/Time: {student[10]}")

    # Fetch and display sixth-form entry grades + the enrolled curriculum
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            # Sixth-form entry grades / UCAS tariff
            try:
                cursor.execute(
                    "SELECT entry_qualifications, ucas_tariff FROM students "
                    "WHERE student_id = ?", (student[0],))
                grow = cursor.fetchone()
                if grow and (grow[0] or grow[1] is not None):
                    quals = grow[0] or 'N/A'
                    tariff = grow[1] if grow[1] is not None else 'N/A'
                    print(f"Entry grades: {quals} ({tariff} UCAS pts)")
            except sqlite3.Error:
                pass

            # Modules grouped by year (LEFT JOIN so legacy/untyped rows still show)
            cursor.execute('''
            SELECT COALESCE(m.year, sm.year) AS yr, sm.module_code,
                   COALESCE(m.module_name, sm.module_name)
            FROM student_modules sm
            LEFT JOIN modules m ON sm.module_code = m.module_code
            WHERE sm.student_id = ?
            ORDER BY yr, sm.module_code
            ''', (student[0],))
            modules = cursor.fetchall()

            if modules:
                print("\nModules:")
                print("-" * 40)
                current_year = object()  # sentinel so the first row prints a header
                for yr, code, name in modules:
                    if yr != current_year:
                        current_year = yr
                        label = f"Year {yr}" if yr not in (None, '') else "Other modules"
                        print(f"{label}:")
                    print(f"  {code} - {name}")
            conn.close()
    except sqlite3.Error as e:
        logging.error(f"Error fetching modules: {e}")

    print("=" * 40 + "\n")

# Add this to your main menu function


def display_student_records_menu():
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to access student records.")
        return

    while True:
        print("\nStudent Records Menu:")
        print("=====================")

        # Show options based on permissions
        option_num = 1
        options = {}

        if auth.check_permission('create_student'):
            print(f"{option_num}. Create student record")
            options[str(option_num)] = 'create_student'
            option_num += 1

        if auth.check_permission('view_any_student') or auth.check_permission('view_own_record'):
            print(f"{option_num}. View student records")
            options[str(option_num)] = 'view_student'
            option_num += 1

        if auth.check_permission('update_any_student') or auth.check_permission('update_own_profile'):
            print(f"{option_num}. Update student record")
            options[str(option_num)] = 'update_student'
            option_num += 1

        if auth.check_permission('update_any_student'):
            print(f"{option_num}. Registration status / study details")
            options[str(option_num)] = 'lifecycle'
            option_num += 1

        if auth.check_permission('update_any_student'):
            print(f"{option_num}. Reinstate a withdrawn student")
            options[str(option_num)] = 'reinstate'
            option_num += 1

        if auth.check_permission('delete_any_student'):
            print(f"{option_num}. Withdraw student")
            options[str(option_num)] = 'delete_student'
            option_num += 1

            print(f"{option_num}. Erasure requests")
            options[str(option_num)] = 'erasure'
            option_num += 1

        if auth.check_permission('view_any_student'):
            print(f"{option_num}. Change history of a student")
            options[str(option_num)] = 'history'
            option_num += 1

        if auth.check_permission('update_any_student'):
            print(f"{option_num}. Data check")
            options[str(option_num)] = 'data_check'
            option_num += 1

        if auth.check_permission('view_any_student'):
            print(f"{option_num}. Search student by first name")
            options[str(option_num)] = 'search_first_name'
            option_num += 1

            print(f"{option_num}. Search student by last name")
            options[str(option_num)] = 'search_last_name'
            option_num += 1

            print(f"{option_num}. Search student by ID")
            options[str(option_num)] = 'search_id'
            option_num += 1

            print(f"{option_num}. Search student by registration date")
            options[str(option_num)] = 'search_date'
            option_num += 1

        print(f"{option_num}. Return to Main Menu")

        choice = input("Enter your choice: ")

        if choice in options:
            action = options[choice]

            if action == 'create_student':
                create_student_record()
            elif action == 'view_student':
                view_student_record()
            elif action == 'update_student':
                update_student_record()
            elif action == 'lifecycle':
                manage_student_lifecycle_record()
            elif action == 'delete_student':
                delete_student_record()
            elif action in ('reinstate', 'erasure', 'history', 'data_check'):
                _records_tool(action)
            elif action == 'search_first_name':
                from education_system.systems.university.shell.cli.student_search import search_student_by_first_name
                search_student_by_first_name()
            elif action == 'search_last_name':
                from education_system.systems.university.shell.cli.student_search import search_student_by_last_name
                search_student_by_last_name()
            elif action == 'search_id':
                from education_system.systems.university.shell.cli.student_search import search_student_by_student_id
                search_student_by_student_id()
            elif action == 'search_date':
                from education_system.systems.university.shell.cli.student_search import search_student_by_registration_date
                search_student_by_registration_date()
        elif choice == str(option_num):
            return
        else:
            print("Invalid choice or insufficient permissions. Please try again.")



def _records_tool(action):
    from education_system.systems.university.shell.cli import student_records_cli as tools
    if action == 'erasure':
        tools.erasure_menu(auth)
    elif action == 'data_check':
        tools.data_check(auth)
    else:
        student_id = input("Student ID: ").strip()
        if student_id:
            (tools.show_history(student_id) if action == 'history'
             else tools.reinstate_student(auth, student_id))
    input("\nPress Enter to continue...")


def manage_student_lifecycle_record():
    """Registration-status and study-detail changes from the CLI.

    Parity with the records GUI: both drive the same
    ``domains.learners.domain.student_lifecycle`` service, so a change made
    here writes the same immutable history and downstream reconciliation
    work as one made in the GUI.
    """
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to change a registration status.")
        return
    if not auth.check_permission('update_any_student'):
        print("You don't have permission to change registration statuses.")
        return

    from education_system.systems.university.domains.learners.domain import (
        student_lifecycle,
    )

    # Username, not the numeric id: auth.db and student_records.db use
    # different id spaces, so the history column would be ambiguous.
    actor = str(auth.current_user.get('username')
                or auth.current_user.get('id') or 'unknown')

    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("No student ID entered.")
        return

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT first_name, last_name, status, course, mode_of_study, "
            "campus_code, is_active FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    if not row:
        print(f"Student {student_id} was not found.")
        return

    name = f"{row[0] or ''} {row[1] or ''}".strip() or student_id
    status = row[2]
    print(f"\n{name} ({student_id})")
    print(f"  Status         : {status}")
    print(f"  Course         : {row[3] or '-'}")
    print(f"  Mode of study  : {row[4] or '-'}")
    print(f"  Campus         : {row[5] or '-'}")
    print(f"  is_active      : {row[6]}")

    history = student_lifecycle.history(student_id)
    if history:
        print("\n  History:")
        for h in history:
            print(f"    #{h.get('history_id')} {h.get('effective_date')} "
                  f"{h.get('action')}: {h.get('from_status')} -> "
                  f"{h.get('to_status')} by {h.get('actor_id')} "
                  f"({h.get('reason')})")

    actions = student_lifecycle.available_actions(status)
    if not actions:
        print(f"\n'{status}' is not a lifecycle status, so no transition can "
              "be applied. Valid statuses are: Active, Registration Pending, "
              "Interrupted, Withdrawn, Deferred, Suspended, Completed, Closed.")
        return

    print("\nAvailable actions:")
    for i, action in enumerate(actions, 1):
        print(f"  {i}. {action} -> {student_lifecycle.target_status(action)}")
    print(f"  {len(actions) + 1}. Change study details "
          "(programme / mode / campus / repeat year)")
    print(f"  {len(actions) + 2}. Cancel")

    choice = input("Select: ").strip()
    if not choice.isdigit():
        print("Invalid selection.")
        return
    choice = int(choice)

    if choice == len(actions) + 2 or choice < 1:
        return

    reason = input("Reason (recorded in the immutable history): ").strip()
    if not reason:
        print("A reason is required.")
        return

    try:
        if choice <= len(actions):
            action = actions[choice - 1]
            effective = input("Effective date [today, YYYY-MM-DD]: ").strip() or None
            expected_return = None
            if action in ('interrupt', 'defer', 'suspend'):
                expected_return = input(
                    "Expected return date [blank for none, YYYY-MM-DD]: "
                ).strip() or None
            student_lifecycle.change_status(
                student_id, action, actor_id=actor, reason=reason,
                effective_date=effective,
                expected_return_date=expected_return,
            )
            from education_system.systems.university.services.student_provisioning import (
                sync_sign_in_for_status,
            )
            sync_sign_in_for_status(student_id, student_lifecycle.target_status(action))
            print(f"{name} is now "
                  f"'{student_lifecycle.target_status(action)}'.")
        elif choice == len(actions) + 1:
            print("1. Programme  2. Mode of study  3. Campus  4. Repeat year")
            which = input("Select: ").strip()
            value = input("New value: ").strip()
            if not value:
                print("No value entered.")
                return
            kwargs = {}
            if which == '1':
                # A programme change is a transfer: the curriculum moves too.
                from education_system.systems.university.shell.cli import student_records_cli
                student_records_cli.transfer_student(auth, student_id, value, reason)
                return
            elif which == '2':
                kwargs['mode_of_study'] = value
            elif which == '3':
                kwargs['campus_code'] = value
            elif which == '4':
                if not value.lstrip('-').isdigit():
                    print("Repeat year must be a whole number.")
                    return
                kwargs['repeat_year'] = int(value)
            else:
                print("Invalid selection.")
                return
            student_lifecycle.change_study(
                student_id, actor_id=actor, reason=reason, **kwargs)
            print("Study details updated.")
        else:
            print("Invalid selection.")
            return
    except Exception as exc:
        print(f"The change could not be applied: {exc}")


def fetch_student_data(include_modules=True):
    """Helper function to fetch all student data from the database"""
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor()

        # Fetch all students
        cursor.execute('SELECT * FROM students')
        students = cursor.fetchall()

        if include_modules:
            # For each student, fetch their modules
            student_data = []
            for student in students:
                student_id = student[0]

                # Fetch modules for this student
                cursor.execute('''
                SELECT m.module_type, sm.module_code, m.module_name
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                WHERE sm.student_id = ?
                ORDER BY m.module_type, sm.module_code
                ''', (student_id,))

                modules = cursor.fetchall()

                # Combine student info with modules
                student_data.append({
                    'student': student,
                    'modules': modules
                })

            conn.close()
            return student_data
        else:
            # Just return the students without modules
            conn.close()
            return students

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return []
