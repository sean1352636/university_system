from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_create,
    log_read,
)
from education_system.university_system.modules.domain.academics.services.course_management.validation import validate_email


@log_create(module="course_management", description="Creating instructor")
def create_instructor(auth):
    """Create a new instructor"""
    if not auth or not auth.current_user:
        print("You must be logged in to create instructors.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to create instructors.")
        return False

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nCreate New Instructor")
        print("====================")

        first_name = input("Enter first name: ").strip()
        if not first_name:
            print("First name cannot be empty.")
            return False

        last_name = input("Enter last name: ").strip()
        if not last_name:
            print("Last name cannot be empty.")
            return False

        while True:
            email = input("Enter email: ").strip()
            if not email:
                print("Email cannot be empty.")
                continue
            if not validate_email(email):
                print("Invalid email format.")
                continue

            cursor.execute("SELECT email FROM instructors WHERE email = ?", (email,))
            if cursor.fetchone():
                print("Email already exists.")
                continue
            break

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

        cursor.execute('''
        INSERT INTO instructors (first_name, last_name, email, department, specialization,
                               max_courses_per_semester, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (first_name, last_name, email, department, specialization, max_courses, timestamp, timestamp))

        instructor_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"\nInstructor '{first_name} {last_name}' created successfully!")
        print(f"Instructor ID: {instructor_id}")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False


@log_read(module="course_management", description="Viewing instructors")
def view_instructors(auth):
    """View all instructors"""
    if not auth or not auth.current_user:
        print("You must be logged in to view instructors.")
        return

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
            conn.close()
            return

        print("\nAll Instructors:")
        print(f"{'ID':<5} {'Name':<25} {'Email':<30} {'Department':<20} {'Status':<10}")
        print("-" * 90)

        for instructor in instructors:
            full_name = f"{instructor[1]} {instructor[2]}"
            print(f"{instructor[0]:<5} {full_name:<25} {instructor[3]:<30} {instructor[4]:<20} {instructor[7]:<10}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
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

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show available courses with schedules but no instructor
        cursor.execute("""
        SELECT cs.id, c.course_code, c.course_name, cs.semester, cs.year, cs.instructor_id
        FROM course_schedule cs
        JOIN courses c ON cs.course_id = c.id
        WHERE c.status = 'Active'
        ORDER BY c.course_code, cs.semester, cs.year
        """)

        schedules = cursor.fetchall()

        if not schedules:
            print("No course schedules found.")
            conn.close()
            return False

        print("\nCourse Schedules:")
        print(f"{'ID':<5} {'Code':<10} {'Name':<25} {'Semester':<10} {'Year':<6} {'Current Instructor':<15}")
        print("-" * 71)

        for schedule in schedules:
            current_instructor = "Assigned" if schedule[5] else "None"
            print(f"{schedule[0]:<5} {schedule[1]:<10} {schedule[2]:<25} {schedule[3]:<10} {schedule[4]:<6} {current_instructor:<15}")

        # Select course schedule
        while True:
            try:
                schedule_id = int(input("\nEnter schedule ID to assign instructor: "))
                selected_schedule = next((s for s in schedules if s[0] == schedule_id), None)
                if selected_schedule:
                    break
                print("Invalid schedule ID.")
            except ValueError:
                print("Please enter a valid number.")

        # Show available instructors
        cursor.execute("""
        SELECT i.id, i.first_name, i.last_name, i.department, i.specialization,
               COUNT(cs.id) as current_courses
        FROM instructors i
        LEFT JOIN course_schedule cs ON i.id = cs.instructor_id
            AND cs.semester = ? AND cs.year = ?
        WHERE i.status = 'Active'
        GROUP BY i.id, i.first_name, i.last_name, i.department, i.specialization
        ORDER BY i.last_name, i.first_name
        """, (selected_schedule[3], selected_schedule[4]))

        instructors = cursor.fetchall()

        if not instructors:
            print("No active instructors found.")
            conn.close()
            return False

        print(f"\nAvailable Instructors for {selected_schedule[3]} {selected_schedule[4]}:")
        print(f"{'ID':<5} {'Name':<25} {'Department':<15} {'Current Load':<15}")
        print("-" * 60)

        for instructor in instructors:
            full_name = f"{instructor[1]} {instructor[2]}"
            print(f"{instructor[0]:<5} {full_name:<25} {instructor[3]:<15} {instructor[5]} courses")

        # Select instructor
        while True:
            try:
                instructor_id = int(input("\nEnter instructor ID to assign: "))
                selected_instructor = next((i for i in instructors if i[0] == instructor_id), None)
                if selected_instructor:
                    break
                print("Invalid instructor ID.")
            except ValueError:
                print("Please enter a valid number.")

        # Check instructor's workload
        if selected_instructor[5] >= 4:  # Assuming max 4 courses per semester
            confirm = input(f"\nWarning: This instructor already has {selected_instructor[5]} courses. Continue? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Assignment cancelled.")
                conn.close()
                return False

        # Assign instructor
        cursor.execute("UPDATE course_schedule SET instructor_id = ? WHERE id = ?",
                      (instructor_id, schedule_id))

        conn.commit()
        conn.close()

        instructor_name = f"{selected_instructor[1]} {selected_instructor[2]}"
        print(f"\nInstructor '{instructor_name}' assigned to '{selected_schedule[1]} - {selected_schedule[2]}' successfully!")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
        return False
