from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
import csv
from datetime import datetime
from education_system.systems.university.infrastructure.utils.activity_logger import (
    log_create,
    log_read,
    log_update,
)
from education_system.systems.university.domain.academics.services.course_management.validation import validate_course_code


@log_create(module="course_management", description="Importing courses from CSV")
def import_courses_from_csv(auth):
    """
    Import courses in bulk from a CSV file.

    Reads course data from a CSV file and inserts valid courses into the
    database. Performs validation on each row and reports successes and
    failures. Duplicate course codes are skipped.

    Parameters
    ----------
    auth : UserAuth
        The authentication instance. Must have an authenticated user with
        'manage_courses' permission.

    Returns
    -------
    bool
        True if import was attempted (regardless of individual row outcomes),
        False if user lacks permission or file path is invalid.

    CSV Format
    ----------
    Required columns:
        - course_code : str - Course code (e.g., 'CS101')
        - course_name : str - Full course name
        - department : str - Department name

    Optional columns:
        - description : str - Course description
        - level : str - Course level (Undergraduate, Postgraduate, etc.)
        - credit_hours : float - Number of credit hours (default: 3.0)
        - max_enrollment : int - Maximum enrollment capacity (default: 30)
        - course_type : str - Course type (Core, Elective, etc.) (default: 'Core')

    Examples
    --------
    >>> # Interactive prompt for file path
    >>> import_courses_from_csv(auth)
    Enter CSV file path: /path/to/courses.csv
    Row 1: Course code already exists
    Row 2: Invalid course code format: invalid
    Import complete: 10 successful, 2 errors

    Sample CSV content::

        course_code,course_name,department,credit_hours,level
        CS101,Introduction to Programming,Computer Science,3.0,Undergraduate
        CS201,Data Structures,Computer Science,4.0,Undergraduate

    Raises
    ------
    FileNotFoundError
        If the specified CSV file does not exist.
    UnicodeDecodeError
        If the CSV file has encoding issues (expects UTF-8).

    See Also
    --------
    export_courses_to_csv : Export courses to CSV format.
    create_enhanced_course : Create a single course interactively.
    """
    if not auth or not auth.current_user:
        print("You must be logged in to import courses.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to import courses.")
        return False

    file_path = input("Enter CSV file path: ").strip()
    if not file_path:
        print("File path cannot be empty.")
        return False

    conn = None
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            required_fields = ['course_code', 'course_name', 'department']
            if not all(field in reader.fieldnames for field in required_fields):
                print(f"CSV must contain these required columns: {', '.join(required_fields)}")
                return False

            conn = get_connection()
            cursor = conn.cursor()

            success_count = 0
            error_count = 0
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for row_num, row in enumerate(reader, 1):
                try:
                    # Validate required fields
                    course_code = row['course_code'].strip().upper()
                    course_name = row['course_name'].strip()
                    department = row['department'].strip()

                    if not course_code or not course_name:
                        print(f"Row {row_num}: Missing required fields")
                        error_count += 1
                        continue

                    if not validate_course_code(course_code):
                        print(f"Row {row_num}: Invalid course code format: {course_code}")
                        error_count += 1
                        continue

                    # Check for duplicates
                    cursor.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,))
                    if cursor.fetchone():
                        print(f"Row {row_num}: Course code {course_code} already exists")
                        error_count += 1
                        continue

                    # Prepare optional fields with defaults
                    description = row.get('description', '').strip()
                    level = row.get('level', '').strip()
                    credit_hours = float(row.get('credit_hours', 3.0))
                    max_enrollment = int(row.get('max_enrollment', 30))
                    course_type = row.get('course_type', 'Core').strip()

                    # Generate unique ID for the course
                    import uuid
                    course_uuid = str(uuid.uuid4())

                    # Insert course
                    cursor.execute('''
                    INSERT INTO courses (
                        id, code, name, date_added,
                        course_code, course_name, description, level, department,
                        credit_hours, max_enrollment, course_type, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (course_uuid, course_code, course_name, timestamp,
                          course_code, course_name, description, level, department,
                          credit_hours, max_enrollment, course_type, timestamp, timestamp))

                    success_count += 1

                except (ValueError, sqlite3.Error) as e:
                    print(f"Row {row_num}: Error - {e}")
                    error_count += 1
                    continue

            conn.commit()

            print("\nImport completed!")
            print(f"Successfully imported: {success_count} courses")
            print(f"Errors: {error_count} courses")

            return success_count > 0

    except FileNotFoundError:
        print("File not found.")
        return False
    except Exception as e:
        print(f"Error importing courses: {e}")
        return False
    finally:
        if conn:
            conn.close()


@log_read(module="course_management", description="Exporting courses to CSV")
def export_courses_to_csv(auth):
    """Export courses to a CSV file"""
    if not auth or not auth.current_user:
        print("You must be logged in to export courses.")
        return False

    if not auth.check_permission('view_courses'):
        print("You don't have permission to export courses.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get filter criteria
        print("\nExport Filters (leave blank for all):")
        department = input("Department: ").strip()
        level = input("Level: ").strip()
        status = input("Status: ").strip()

        # Build query
        conditions = []
        params = []

        if department:
            conditions.append("department = ?")
            params.append(department)

        if level:
            conditions.append("level = ?")
            params.append(level)

        if status:
            conditions.append("status = ?")
            params.append(status)

        query = "SELECT * FROM courses"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY course_code"

        cursor.execute(query, params)
        courses = cursor.fetchall()

        if not courses:
            print("No courses found to export.")
            return False

        # Get column names
        cursor.execute("PRAGMA table_info(courses)")
        columns = [col[1] for col in cursor.fetchall()]

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"courses_export_{timestamp}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(columns)

            # Write data
            for course in courses:
                writer.writerow(course)

        print(f"\nExported {len(courses)} courses to {filename}")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error exporting courses: {e}")
        return False
    finally:
        if conn:
            conn.close()


@log_update(module="course_management", description="Bulk updating courses")
def bulk_update_courses(auth):
    """Bulk update multiple courses"""
    if not auth or not auth.current_user:
        print("You must be logged in to bulk update courses.")
        return False

    if not auth.check_permission('manage_courses'):
        print("You don't have permission to bulk update courses.")
        return False

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nBulk Update Courses")
        print("==================")

        # Select criteria for courses to update
        print("Select courses to update by:")
        print("1. Department")
        print("2. Level")
        print("3. Status")
        print("4. Course Type")
        print("5. Manual Selection")

        while True:
            try:
                raw = input("Enter choice (1-5): ").strip()
                if not raw:
                    print("Bulk update cancelled.")
                    return False
                criteria = int(raw)
                if 1 <= criteria <= 5:
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        courses_to_update = []

        if criteria == 1:  # By Department
            cursor.execute("SELECT DISTINCT department FROM courses WHERE department IS NOT NULL ORDER BY department")
            departments = [row[0] for row in cursor.fetchall()]

            print("\nAvailable Departments:")
            for i, dept in enumerate(departments, 1):
                print(f"{i}. {dept}")

            dept_choice = int(input("Select department: ")) - 1
            if 0 <= dept_choice < len(departments):
                selected_dept = departments[dept_choice]
                cursor.execute("SELECT id, course_code, course_name FROM courses WHERE department = ?", (selected_dept,))
                courses_to_update = cursor.fetchall()

        elif criteria == 2:  # By Level
            cursor.execute("SELECT DISTINCT level FROM courses WHERE level IS NOT NULL ORDER BY level")
            levels = [row[0] for row in cursor.fetchall()]

            print("\nAvailable Levels:")
            for i, level in enumerate(levels, 1):
                print(f"{i}. {level}")

            level_choice = int(input("Select level: ")) - 1
            if 0 <= level_choice < len(levels):
                selected_level = levels[level_choice]
                cursor.execute("SELECT id, course_code, course_name FROM courses WHERE level = ?", (selected_level,))
                courses_to_update = cursor.fetchall()

        elif criteria == 3:  # By Status
            statuses = ["Active", "Inactive", "Archived", "Cancelled"]
            print("\nAvailable Statuses:")
            for i, status in enumerate(statuses, 1):
                print(f"{i}. {status}")

            status_choice = int(input("Select status: ")) - 1
            if 0 <= status_choice < len(statuses):
                selected_status = statuses[status_choice]
                cursor.execute("SELECT id, course_code, course_name FROM courses WHERE status = ?", (selected_status,))
                courses_to_update = cursor.fetchall()

        elif criteria == 4:  # By Course Type
            cursor.execute("SELECT DISTINCT course_type FROM courses WHERE course_type IS NOT NULL ORDER BY course_type")
            types = [row[0] for row in cursor.fetchall()]

            print("\nAvailable Course Types:")
            for i, ctype in enumerate(types, 1):
                print(f"{i}. {ctype}")

            type_choice = int(input("Select course type: ")) - 1
            if 0 <= type_choice < len(types):
                selected_type = types[type_choice]
                cursor.execute("SELECT id, course_code, course_name FROM courses WHERE course_type = ?", (selected_type,))
                courses_to_update = cursor.fetchall()

        elif criteria == 5:  # Manual Selection
            cursor.execute("SELECT id, course_code, course_name, status FROM courses ORDER BY course_code")
            all_courses = cursor.fetchall()

            print("\nSelect courses (enter row numbers separated by commas):")
            for i, course in enumerate(all_courses, 1):
                print(f"{i}. {course[1]} - {course[2]} ({course[3]})")

            id_input = input("\nEnter course numbers: ").strip()
            selected_indices = [int(idx.strip()) for idx in id_input.split(',') if idx.strip().isdigit()]
            selected_ids = [all_courses[i - 1][0] for i in selected_indices if 1 <= i <= len(all_courses)]

            if selected_ids:
                cursor.execute("SELECT id, course_code, course_name FROM courses WHERE id IN (" + ','.join(['?']*len(selected_ids)) + ")", selected_ids)
                courses_to_update = cursor.fetchall()

        if not courses_to_update:
            print("No courses selected for update.")
            return False

        print(f"\nSelected {len(courses_to_update)} courses for update:")
        for course in courses_to_update:
            print(f"  {course[1]} - {course[2]}")

        # Select field to update
        print("\nSelect field to update:")
        print("1. Status")
        print("2. Max Enrollment")
        print("3. Course Fee")
        print("4. Course Type")
        print("5. Department")
        print("6. Level")

        while True:
            try:
                raw = input("Enter choice (1-6): ").strip()
                if not raw:
                    print("Bulk update cancelled.")
                    return False
                field_choice = int(raw)
                if 1 <= field_choice <= 6:
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a valid number.")

        # Get new value
        if field_choice == 1:  # Status
            new_value = input("Enter new status (Active/Inactive/Archived/Cancelled): ").strip()
            field_name = "status"
        elif field_choice == 2:  # Max Enrollment
            new_value = int(input("Enter new max enrollment: "))
            field_name = "max_enrollment"
        elif field_choice == 3:  # Course Fee
            new_value = float(input("Enter new course fee: "))
            field_name = "course_fee"
        elif field_choice == 4:  # Course Type
            new_value = input("Enter new course type: ").strip()
            field_name = "course_type"
        elif field_choice == 5:  # Department
            new_value = input("Enter new department: ").strip()
            field_name = "department"
        elif field_choice == 6:  # Level
            new_value = input("Enter new level: ").strip()
            field_name = "level"

        # Confirm update
        confirm = input(f"\nUpdate {field_name} to '{new_value}' for {len(courses_to_update)} courses? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Bulk update cancelled.")
            return False

        # Perform bulk update
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        course_ids = [course[0] for course in courses_to_update]

        _BULK_UPDATE_ALLOWED_COLUMNS = frozenset({
            'status', 'max_enrollment', 'course_fee', 'course_type', 'department', 'level',
        })
        if field_name not in _BULK_UPDATE_ALLOWED_COLUMNS:
            print(f"Invalid field name: {field_name}")
            return False

        placeholders = ','.join(['?'] * len(course_ids))
        update_query = f"UPDATE courses SET {field_name} = ?, updated_at = ? WHERE id IN ({placeholders})"

        cursor.execute(update_query, [new_value, timestamp] + course_ids)
        updated_count = cursor.rowcount

        # Log changes in history
        changed_by = auth.current_user.get('username', 'system') if isinstance(auth.current_user, dict) else str(auth.current_user)
        for course_id in course_ids:
            cursor.execute('''
            INSERT INTO course_history (course_id, field_name, old_value, new_value, changed_by, changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (course_id, field_name, "bulk_update", str(new_value), changed_by, timestamp))

        conn.commit()

        print("\nBulk update completed!")
        print(f"Updated {updated_count} courses")
        print(f"Field: {field_name}")
        print(f"New value: {new_value}")
        return True

    except (ValueError, sqlite3.Error) as e:
        print(f"Error during bulk update: {e}")
        return False
    finally:
        if conn:
            conn.close()
