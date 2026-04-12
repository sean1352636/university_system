from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import secrets
import string
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_create,
    log_read,
)
from education_system.university_system.modules.domain.academics.services.course_management.validation import validate_email


def _generate_temp_password(length=12):
    """Generate a secure temporary password that meets password strength requirements."""
    # Ensure at least one of each required character type
    upper = secrets.choice(string.ascii_uppercase)
    lower = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("@#$%&!?")
    # Fill the rest randomly
    remaining = ''.join(secrets.choice(string.ascii_letters + string.digits + "@#$%&!?")
                        for _ in range(length - 4))
    # Shuffle all characters
    password_list = list(upper + lower + digit + special + remaining)
    secrets.SystemRandom().shuffle(password_list)
    return ''.join(password_list)


def _generate_university_email(first_name, last_name):
    """Generate a university email address for an instructor."""
    from education_system.university_system.core.defaults import UNIVERSITY_EMAIL_DOMAIN
    # Format: firstname.lastname@university.edu (lowercase, no spaces)
    clean_first = first_name.lower().strip().replace(' ', '')
    clean_last = last_name.lower().strip().replace(' ', '')
    return f"{clean_first}.{clean_last}@{UNIVERSITY_EMAIL_DOMAIN}"


def _create_instructor_account(auth, username, temp_password, display_name, email):
    """Create a system login account for the instructor via the shared auth system."""
    try:
        from education_system.shared.auth.core import UserAuth as SharedUserAuth
        shared_auth = SharedUserAuth()
        user_id = shared_auth.create_user(
            username=username,
            password=temp_password,
            display_name=display_name,
            email=email,
            systems=[("university", "instructor")],
        )
        return user_id
    except Exception as e:
        print(f"  Warning: Could not create login account via shared auth: {e}")
        # Fallback: try creating via the passed-in auth if it supports create_user
        if hasattr(auth, 'create_user'):
            try:
                user_id = auth.create_user(
                    username=username,
                    password=temp_password,
                    display_name=display_name,
                    email=email,
                    systems=[("university", "instructor")],
                )
                return user_id
            except Exception as e2:
                print(f"  Warning: Fallback account creation also failed: {e2}")
        return None


def _send_instructor_welcome_email(first_name, last_name, username, university_email,
                                    department, specialization, temp_password):
    """Send a welcome email to the new instructor using the template system."""
    try:
        from education_system.university_system.core.defaults import UNIVERSITY_EMAIL_DOMAIN
        from education_system.university_system.infrastructure.email import send_template_email

        template_vars = {
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'university_email': university_email,
            'department': department or 'Not assigned',
            'specialization': specialization or 'Not specified',
            'temp_password': temp_password,
            'email_domain': UNIVERSITY_EMAIL_DOMAIN,
        }

        result = send_template_email(
            'user_management/instructor_welcome',
            university_email,
            template_vars,
        )
        return result
    except Exception as e:
        print(f"  Warning: Could not send welcome email: {e}")
        return False


@log_create(module="course_management", description="Creating instructor")
def create_instructor(auth):
    """Create a new instructor with university email, login account, and welcome email"""
    if not auth or not auth.current_user:
        print("You must be logged in to create instructors.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to create instructors.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nCreate New Instructor")
        print("====================")

        first_name = input("Enter first name (or press Enter to go back): ").strip()
        if not first_name:
            return False

        last_name = input("Enter last name (or press Enter to go back): ").strip()
        if not last_name:
            return False

        # Auto-generate university email
        university_email = _generate_university_email(first_name, last_name)

        # Check if generated email already exists, append number if needed
        base_email = university_email
        counter = 1
        while True:
            cursor.execute("SELECT email FROM instructors WHERE email = ?", (university_email,))
            if not cursor.fetchone():
                break
            # Append counter: john.smith2@university.edu
            from education_system.university_system.core.defaults import UNIVERSITY_EMAIL_DOMAIN
            clean_first = first_name.lower().strip().replace(' ', '')
            clean_last = last_name.lower().strip().replace(' ', '')
            university_email = f"{clean_first}.{clean_last}{counter}@{UNIVERSITY_EMAIL_DOMAIN}"
            counter += 1

        print(f"University email: {university_email}")

        # Allow optional personal email
        personal_email = input("Enter personal email (optional, press Enter to skip): ").strip()
        if personal_email and not validate_email(personal_email):
            print("Invalid email format. Skipping personal email.")
            personal_email = ""

        department = input("Enter department: ").strip()
        specialization = input("Enter specialization: ").strip()

        max_courses = 4
        max_input = input("Enter max courses per semester (default 4): ").strip()
        if max_input:
            try:
                max_courses = int(max_input)
            except ValueError:
                print("Using default value of 4.")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert instructor record
        cursor.execute('''
        INSERT INTO instructors (first_name, last_name, email, department, specialization,
                               max_courses_per_semester, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (first_name, last_name, university_email, department, specialization,
              max_courses, timestamp, timestamp))

        instructor_id = cursor.lastrowid
        conn.commit()

        print(f"\nInstructor '{first_name} {last_name}' created successfully!")
        print(f"Instructor ID: {instructor_id}")
        print(f"University Email: {university_email}")

        # Create login account
        temp_password = _generate_temp_password()
        username = university_email.split('@')[0]  # e.g. john.smith
        display_name = f"{first_name} {last_name}"

        print("\nCreating system login account...")
        user_id = _create_instructor_account(auth, username, temp_password, display_name, university_email)

        if user_id:
            print(f"Login account created successfully!")
            print(f"  Username: {username}")
            print(f"  Temporary Password: {temp_password}")
        else:
            print("Login account could not be created. Please create manually.")
            print(f"  Suggested username: {username}")
            print(f"  Temporary password: {temp_password}")

        # Send welcome email
        print("\nSending welcome email...")
        email_sent = _send_instructor_welcome_email(
            first_name, last_name, username, university_email,
            department, specialization, temp_password,
        )

        if email_sent:
            print(f"Welcome email sent to {university_email}")
        else:
            print(f"Welcome email could not be sent. Please notify instructor manually.")

        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()


@log_read(module="course_management", description="Viewing instructors")
def view_instructors(auth):
    """View all instructors"""
    if not auth or not auth.current_user:
        print("You must be logged in to view instructors.")
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT id, first_name, last_name, email, department, specialization,
               max_courses_per_semester, status
        FROM instructors
        ORDER BY last_name, first_name
        """)

        instructors = cursor.fetchall()

        if not instructors:
            print("No instructors found.")
            return

        print("\nAll Instructors:")
        print(f"{'#':<5} {'Name':<25} {'Email':<30} {'Department':<20} {'Status':<10}")
        print("-" * 90)

        for i, instructor in enumerate(instructors, 1):
            full_name = f"{instructor[1]} {instructor[2]}"
            print(f"{i:<5} {full_name:<25} {instructor[3]:<30} {instructor[4]:<20} {instructor[7]:<10}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


@log_create(module="course_management", description="Assigning instructor to course")
def assign_instructor_to_course(auth):
    """Assign an instructor to a course"""
    if not auth or not auth.current_user:
        print("You must be logged in to assign instructors.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to assign instructors.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show available courses with schedules but no instructor
        cursor.execute("""
        SELECT cs.id, c.course_code, c.course_name, cs.semester, cs.year, cs.instructor_id
        FROM course_schedule cs
        JOIN courses c ON cs.course_id = c.id
        WHERE LOWER(c.status) = 'active'
        ORDER BY c.course_code, cs.semester, cs.year
        """)

        schedules = cursor.fetchall()

        if not schedules:
            print("No course schedules found.")
            return False

        print("\nCourse Schedules:")
        print(f"{'#':<5} {'Code':<10} {'Name':<25} {'Semester':<10} {'Year':<6} {'Current Instructor':<15}")
        print("-" * 71)

        for i, schedule in enumerate(schedules, 1):
            current_instructor = "Assigned" if schedule[5] else "None"
            print(f"{i:<5} {schedule[1]:<10} {schedule[2]:<25} {schedule[3]:<10} {schedule[4]:<6} {current_instructor:<15}")

        # Select course schedule
        while True:
            choice = input("\nEnter schedule number to assign instructor (or press Enter to go back): ").strip()
            if not choice:
                return False
            try:
                idx = int(choice)
                if 1 <= idx <= len(schedules):
                    selected_schedule = schedules[idx - 1]
                    schedule_id = selected_schedule[0]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        # Show available instructors
        cursor.execute("""
        SELECT i.id, i.first_name, i.last_name, i.department, i.specialization,
               COUNT(cs.id) as current_courses
        FROM instructors i
        LEFT JOIN course_schedule cs ON i.id = cs.instructor_id
            AND cs.semester = ? AND cs.year = ?
        WHERE LOWER(i.status) = 'active'
        GROUP BY i.id, i.first_name, i.last_name, i.department, i.specialization
        ORDER BY i.last_name, i.first_name
        """, (selected_schedule[3], selected_schedule[4]))

        instructors = cursor.fetchall()

        if not instructors:
            print("No active instructors found.")
            return False

        print(f"\nAvailable Instructors for {selected_schedule[3]} {selected_schedule[4]}:")
        print(f"{'#':<5} {'Name':<25} {'Department':<15} {'Current Load':<15}")
        print("-" * 60)

        for i, instructor in enumerate(instructors, 1):
            full_name = f"{instructor[1]} {instructor[2]}"
            print(f"{i:<5} {full_name:<25} {instructor[3]:<15} {instructor[5]} courses")

        # Select instructor
        while True:
            choice = input("\nEnter instructor number to assign (or press Enter to go back): ").strip()
            if not choice:
                return False
            try:
                idx = int(choice)
                if 1 <= idx <= len(instructors):
                    selected_instructor = instructors[idx - 1]
                    instructor_id = selected_instructor[0]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        # Check instructor's workload
        if selected_instructor[5] >= 4:  # Assuming max 4 courses per semester
            confirm = input(f"\nWarning: This instructor already has {selected_instructor[5]} courses. Continue? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Assignment cancelled.")
                return False

        # Assign instructor
        cursor.execute("UPDATE course_schedule SET instructor_id = ? WHERE id = ?",
                      (instructor_id, schedule_id))

        conn.commit()

        instructor_name = f"{selected_instructor[1]} {selected_instructor[2]}"
        print(f"\nInstructor '{instructor_name}' assigned to '{selected_schedule[1]} - {selected_schedule[2]}' successfully!")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()
