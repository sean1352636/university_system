"""
Module/Course operations for CLI system.

Handles course module CRUD operations and management.
"""

from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.modules.shared.cli.database_manager import DatabaseError, init_db
from education_system.post_18.university_system.modules.shared.cli.imports import (
    logging, sqlite3, datetime, DB_PATH, logger, _t,
    log_activity, log_create, log_update, log_delete, get_auth
)
from education_system.post_18.university_system.modules.domain.academics.services.modules import (
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2, optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
)

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)


def create_module():
    """Create a new module in the system"""
    auth = get_auth()

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to create modules.")
        return False

    if not auth.check_permission('manage_modules'):
        print("You don't have permission to create modules.")
        return False

    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        print("\nCreate New Module")
        print("=" * 30)

        # Get module code
        while True:
            module_code = input("Enter module code (e.g., CS101): ").strip().upper()
            if not module_code:
                print("Error: Module code cannot be empty.")
                continue

            # Check if module code already exists
            cursor.execute("SELECT module_code FROM modules WHERE module_code = ?", (module_code,))
            if cursor.fetchone():
                print(f"Error: Module code '{module_code}' already exists.")
                continue

            # Validate module code format (letters followed by numbers)
            import re
            if not re.match(r'^[A-Z]{2,4}\d{3,4}$', module_code):
                print("Error: Module code must be 2-4 letters followed by 3-4 digits (e.g., CS101).")
                continue

            break

        # Get module name
        while True:
            module_name = input("Enter module name: ").strip()
            if not module_name:
                print("Error: Module name cannot be empty.")
                continue
            if len(module_name) < 3:
                print("Error: Module name must be at least 3 characters long.")
                continue
            break

        # Get module type
        print("\nModule Types:")
        print("1. Compulsory")
        print("2. Optional")
        print("3. CS (Computer Science specific)")
        print("4. DS (Data Science specific)")

        while True:
            type_choice = input("Select module type (1-4): ")
            if type_choice == '1':
                module_type = 'compulsory'
                break
            elif type_choice == '2':
                module_type = 'optional'
                break
            elif type_choice == '3':
                module_type = 'CS'
                break
            elif type_choice == '4':
                module_type = 'DS'
                break
            else:
                print("Invalid choice. Please select 1-4.")

        # Insert the module
        cursor.execute('''
        INSERT INTO modules (module_code, module_name, module_type)
        VALUES (?, ?, ?)
        ''', (module_code, module_name, module_type))

        conn.commit()
        conn.close()

        print(f"\nModule '{module_code} - {module_name}' created successfully!")
        input("\nPress Enter to continue...")
        return True

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        input("\nPress Enter to continue...")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error creating module: {e}")
        input("\nPress Enter to continue...")
        return False


def edit_module():
    """Edit an existing module"""
    auth = get_auth()

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to edit modules.")
        return False

    if not auth.check_permission('manage_modules'):
        print("You don't have permission to edit modules.")
        return False

    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        print("\nEdit Module")
        print("=" * 30)

        # Display all modules
        cursor.execute('''
        SELECT module_code, module_name, module_type
        FROM modules
        ORDER BY module_type, module_code
        ''')

        modules = cursor.fetchall()

        if not modules:
            print("No modules found in the system.")
            conn.close()
            input("\nPress Enter to continue...")
            return False

        print("\nExisting Modules:")
        print(f"{'Code':<10} {'Name':<40} {'Type':<15}")
        print("-" * 70)

        for module in modules:
            print(f"{module[0]:<10} {module[1]:<40} {module[2]:<15}")

        # Get module to edit
        while True:
            module_code = input("\nEnter module code to edit (or 'cancel' to exit): ").strip().upper()

            if module_code.lower() == 'cancel':
                print("Edit operation cancelled.")
                conn.close()
                return False

            cursor.execute("SELECT * FROM modules WHERE module_code = ?", (module_code,))
            module = cursor.fetchone()

            if not module:
                print(f"Error: Module code '{module_code}' not found.")
                continue

            break

        # Display current module information
        print("\nCurrent module information:")
        print(f"Code: {module[0]}")
        print(f"Name: {module[1]}")
        print(f"Type: {module[2]}")

        # Choose what to edit
        print("\nWhat would you like to edit?")
        print("1. Module Name")
        print("2. Module Type")
        print("3. Both")
        print("4. Cancel")

        choice = input("Enter your choice (1-4): ")

        if choice == '4':
            print("Edit operation cancelled.")
            conn.close()
            return False

        new_name = module[1]  # Keep current name by default
        new_type = module[2]  # Keep current type by default

        # Edit module name
        if choice in ['1', '3']:
            while True:
                new_name = input(f"Enter new module name (current: {module[1]}): ").strip()
                if not new_name:
                    print("Error: Module name cannot be empty.")
                    continue
                if len(new_name) < 3:
                    print("Error: Module name must be at least 3 characters long.")
                    continue
                break

        # Edit module type
        if choice in ['2', '3']:
            print("\nModule Types:")
            print("1. Compulsory")
            print("2. Optional")
            print("3. CS (Computer Science specific)")
            print("4. DS (Data Science specific)")

            while True:
                type_choice = input("Select new module type (1-4): ")
                if type_choice == '1':
                    new_type = 'compulsory'
                    break
                elif type_choice == '2':
                    new_type = 'optional'
                    break
                elif type_choice == '3':
                    new_type = 'CS'
                    break
                elif type_choice == '4':
                    new_type = 'DS'
                    break
                else:
                    print("Invalid choice. Please select 1-4.")

        # Update the module
        cursor.execute('''
        UPDATE modules
        SET module_name = ?, module_type = ?
        WHERE module_code = ?
        ''', (new_name, new_type, module_code))

        # Update module name in student_modules table
        if new_name != module[1]:
            cursor.execute('''
            UPDATE student_modules
            SET module_name = ?
            WHERE module_code = ?
            ''', (new_name, module_code))

        conn.commit()
        conn.close()

        print(f"\nModule '{module_code}' updated successfully!")
        print(f"New name: {new_name}")
        print(f"New type: {new_type}")
        input("\nPress Enter to continue...")
        return True

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        input("\nPress Enter to continue...")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error editing module: {e}")
        input("\nPress Enter to continue...")
        return False


def delete_module():
    """Delete a module from the system"""
    auth = get_auth()

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to delete modules.")
        return False

    if not auth.check_permission('manage_modules'):
        print("You don't have permission to delete modules.")
        return False

    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        print("\nDelete Module")
        print("=" * 30)

        # Display all modules
        cursor.execute('''
        SELECT module_code, module_name, module_type
        FROM modules
        ORDER BY module_type, module_code
        ''')

        modules = cursor.fetchall()

        if not modules:
            print("No modules found in the system.")
            conn.close()
            input("\nPress Enter to continue...")
            return False

        print("\nExisting Modules:")
        print(f"{'Code':<10} {'Name':<40} {'Type':<15}")
        print("-" * 70)

        for module in modules:
            print(f"{module[0]:<10} {module[1]:<40} {module[2]:<15}")

        # Get module to delete
        while True:
            module_code = input("\nEnter module code to delete (or 'cancel' to exit): ").strip().upper()

            if module_code.lower() == 'cancel':
                print("Delete operation cancelled.")
                conn.close()
                return False

            cursor.execute("SELECT * FROM modules WHERE module_code = ?", (module_code,))
            module = cursor.fetchone()

            if not module:
                print(f"Error: Module code '{module_code}' not found.")
                continue

            break

        # Check if module is assigned to any students
        cursor.execute('''
        SELECT COUNT(*) FROM student_modules WHERE module_code = ?
        ''', (module_code,))

        student_count = cursor.fetchone()[0]

        if student_count > 0:
            print(f"\nWarning: This module is currently assigned to {student_count} student(s).")
            print("Deleting this module will remove it from all student records.")

        # Confirm deletion
        print(f"\nAre you sure you want to delete module '{module_code} - {module[1]}'?")
        confirm = input("Type 'yes' to confirm: ").strip().lower()

        if confirm != 'yes':
            print("Delete operation cancelled.")
            conn.close()
            return False

        # Delete module from student_modules first (foreign key constraint)
        cursor.execute('''
        DELETE FROM student_modules WHERE module_code = ?
        ''', (module_code,))

        # Delete module from modules table
        cursor.execute('''
        DELETE FROM modules WHERE module_code = ?
        ''', (module_code,))

        conn.commit()
        conn.close()

        print(f"\nModule '{module_code}' deleted successfully!")
        if student_count > 0:
            print(f"Module removed from {student_count} student record(s).")
        input("\nPress Enter to continue...")
        return True

    except sqlite3.IntegrityError as e:
        print(f"Cannot delete module: {e}")
        print("This module may be referenced in other tables.")
        input("\nPress Enter to continue...")
        return False
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        input("\nPress Enter to continue...")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error deleting module: {e}")
        input("\nPress Enter to continue...")
        return False


def search_module_by_module_name():
    auth = get_auth()

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search module information.")
        return

    # Check for appropriate permissions
    if not (auth.check_permission('manage_modules') or
            auth.check_permission('view_assigned_modules') or
            auth.check_permission('view_any_student')):
        print("You don't have permission to search module information.")
        return

    # First check if the modules table exists - if not, initialize the database
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Check if the modules table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modules'")
        if not cursor.fetchone():
            conn.close()
            init_db()  # Initialize the database if it doesn't exist
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()

        # Ask the user for the name of the module to search for
        module_name = input("Enter the name of the module to search for: ")

        # Find the module code that matches the name
        cursor.execute('''
        SELECT module_code, module_name FROM modules
        WHERE LOWER(module_name) LIKE LOWER(?)
        ''', (f"%{escape_like(module_name)}%",))

        modules = cursor.fetchall()

        if not modules:
            # Try searching in the module dictionary if not found in database
            found_modules = []
            all_modules = [
                compulsory_module_1, compulsory_module_2,
                optional_module_1, optional_module_2, optional_module_3, optional_module_4,
                CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
                DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4
            ]

            for module in all_modules:
                if module_name.lower() in module['name'].lower():
                    found_modules.append((module['code'], module['name']))

            if not found_modules:
                print("No module was found with that name.")
                conn.close()
                return
            else:
                modules = found_modules

        # If multiple modules match, let the user choose
        if len(modules) > 1:
            print("Multiple modules found:")
            for i, module in enumerate(modules):
                print(f"{i+1}. {module[0]} - {module[1]}")

            choice = input("Enter the number of the module you want to view: ")
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(modules):
                    raise ValueError
                module_code = modules[index][0]
                module_name = modules[index][1]
            except (ValueError, IndexError):
                print("Error: Invalid choice.")
                conn.close()
                return
        else:
            module_code = modules[0][0]
            module_name = modules[0][1]

        # Display the data associated with the module
        print(f"\nModule Code: {module_code}")
        print(f"Module Name: {module_name}")
        print("Students taking this module:")

        # Find students taking this module
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.middle_name, s.last_name
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ?
        ''', (module_code,))

        students = cursor.fetchall()

        if not students:
            print("No students are currently taking this module.")
        else:
            for student in students:
                print(f"Student ID: {student[0]}")
                print(f"Name: {student[1]} {student[2]} {student[3]}")
                print("-" * 30)

        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        print("Initializing database...")
        init_db()
        print("Please try your search again.")


def search_module_by_module_code():
    auth = get_auth()

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search module information.")
        return

    # Check for appropriate permissions
    if not (auth.check_permission('manage_modules') or
            auth.check_permission('view_assigned_modules') or
            auth.check_permission('view_any_student')):
        print("You don't have permission to search module information.")
        return

    # First check if the modules table exists - if not, initialize the database
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Check if the modules table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modules'")
        if not cursor.fetchone():
            conn.close()
            init_db()  # Initialize the database if it doesn't exist
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()

        # ask the user to input the module code
        module_code = input("Enter the module code: ")

        # check if the module code is valid
        cursor.execute('''
        SELECT module_name FROM modules
        WHERE module_code = ?
        ''', (module_code,))

        module = cursor.fetchone()

        if not module:
            # Try searching in the module dictionary if not found in database
            module_name = None
            all_modules = [
                compulsory_module_1, compulsory_module_2,
                optional_module_1, optional_module_2, optional_module_3, optional_module_4,
                CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
                DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4
            ]

            for mod in all_modules:
                if mod['code'] == module_code:
                    module_name = mod['name']
                    break

            if not module_name:
                print("Invalid module code")
                conn.close()
                return
            else:
                # display module name
                print(f"Module name: {module_name}")
                print("No students are currently taking this module.")
                conn.close()
                return

        # display module name
        print(f"Module name: {module[0]}")

        # Find students taking this module
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.middle_name, s.last_name
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ?
        ''', (module_code,))

        students = cursor.fetchall()

        if not students:
            print("No students are currently taking this module.")
        else:
            print("Students taking this module:")
            for student in students:
                print(f"Student ID: {student[0]}")
                print(f"Name: {student[1]} {student[2]} {student[3]}")
                print("-" * 30)

        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        print("Initializing database...")
        init_db()
        print("Please try your search again.")


# ---------------------------------------------------------------------------
# New features: report, timetable, schedule, email, CSV, validate, backup
# ---------------------------------------------------------------------------

def generate_module_report():
    """Generate a formatted report of all modules."""
    auth = get_auth()
    if not auth or not auth.current_user:
        print("You must be logged in."); return

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT m.module_code, m.module_name, m.module_type,
               COALESCE(m.credits, 0) as credits,
               COUNT(sm.id) as student_count
        FROM modules m
        LEFT JOIN student_modules sm ON m.module_code = sm.module_code
        GROUP BY m.module_code, m.module_name, m.module_type, m.credits
        ORDER BY m.module_type, m.module_code
        """)
        modules = cursor.fetchall()

        if not modules:
            print("No modules found."); return

        report_lines = []
        report_lines.append("MODULE REPORT")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 80)
        report_lines.append(f"{'Code':<10} {'Name':<35} {'Type':<12} {'Credits':<8} {'Students':<8}")
        report_lines.append("-" * 80)

        current_type = None
        for mod in modules:
            if current_type != mod[2]:
                current_type = mod[2]
                report_lines.append(f"\n  [{current_type.upper()}]")
            name_display = mod[1][:32] + "..." if len(mod[1]) > 35 else mod[1]
            report_lines.append(f"{mod[0]:<10} {name_display:<35} {mod[2]:<12} {mod[3]:<8} {mod[4]:<8}")

        report_lines.append(f"\nTotal modules: {len(modules)}")
        total_students = sum(m[4] for m in modules)
        report_lines.append(f"Total enrolments: {total_students}")

        for line in report_lines:
            print(line)

        # Post-report options
        print("\n1. Send report to admin via email")
        print("2. Save report to file")
        print("Press Enter to skip")
        action = input("Enter choice: ").strip()

        if action == '1':
            _send_module_report_email(cursor, report_lines)
        elif action == '2':
            filename = f"module_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
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


def _send_module_report_email(cursor, report_lines):
    """Send a module report to admin via the email system."""
    try:
        from education_system.post_18.university_system.infrastructure.email import send_email

        cursor.execute("""
        SELECT email FROM users
        WHERE LOWER(role) = 'admin' AND email IS NOT NULL AND email != ''
        LIMIT 1
        """)
        row = cursor.fetchone()
        admin_email = row[0] if row else None

        if not admin_email:
            admin_email = input("No admin email found. Enter email (or Enter to skip): ").strip()
            if not admin_email:
                return

        body = '\n'.join(report_lines)
        send_email(admin_email, "Module Report", body)
        print(f"Report sent to {admin_email}")
    except Exception as e:
        print(f"Error sending report: {e}")


def view_module_timetable():
    """View the module timetable (schedule) in a table format."""
    auth = get_auth()
    if not auth or not auth.current_user:
        print("You must be logged in."); return

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT ms.day_of_week, ms.start_time, ms.end_time,
               ms.module_code, m.module_name,
               COALESCE(r.room_number, 'TBA') as room,
               COALESCE(r.building, '') as building,
               COALESCE(i.first_name || ' ' || i.last_name, 'Unassigned') as instructor,
               COALESCE(ms.session_type, 'Lecture') as session_type
        FROM module_schedule ms
        LEFT JOIN modules m ON ms.module_code = m.module_code
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        ORDER BY
            CASE ms.day_of_week
                WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5
                ELSE 6
            END,
            ms.start_time
        """)
        rows = cursor.fetchall()

        if not rows:
            print("No module schedules found."); return

        # Optional filter
        filter_choice = input("\nFilter by: 1. Day  2. Module code  3. Instructor  (Enter for all): ").strip()

        if filter_choice == '1':
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            for i, d in enumerate(days, 1):
                print(f"  {i}. {d}")
            day_input = input("Enter day number: ").strip()
            try:
                day_filter = days[int(day_input) - 1]
                rows = [r for r in rows if r[0] == day_filter]
            except (ValueError, IndexError):
                print("Invalid choice, showing all.")
        elif filter_choice == '2':
            code = input("Enter module code: ").strip().upper()
            rows = [r for r in rows if r[3] == code]
        elif filter_choice == '3':
            name = input("Enter instructor name: ").strip().lower()
            rows = [r for r in rows if name in r[7].lower()]

        if not rows:
            print("No schedules match the filter."); return

        print(f"\n{'Day':<12} {'Time':<14} {'Code':<10} {'Module':<28} {'Room':<12} {'Instructor':<20} {'Type':<10}")
        print("-" * 106)

        current_day = None
        for row in rows:
            day = row[0]
            if current_day != day:
                if current_day is not None:
                    print()  # blank line between days
                current_day = day

            time_str = f"{row[1]}-{row[2]}"
            mod_name = row[4][:25] + "..." if row[4] and len(row[4]) > 28 else (row[4] or "Unknown")
            room_str = f"{row[5]}" if not row[6] else f"{row[5]} ({row[6]})"
            room_str = room_str[:12] if len(room_str) > 12 else room_str
            instr = row[7][:17] + "..." if len(row[7]) > 20 else row[7]

            print(f"{day:<12} {time_str:<14} {row[3]:<10} {mod_name:<28} {room_str:<12} {instr:<20} {row[8]:<10}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


def schedule_module():
    """Schedule a module (assign day, time, room, instructor)."""
    auth = get_auth()
    if not auth or not auth.current_user:
        print("You must be logged in."); return False
    if not auth.check_permission('manage_modules'):
        print("You don't have permission."); return False

    TIME_SLOTS = [f"{h:02d}:00" for h in range(9, 18)]
    DAY_OPTIONS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Pick module
        cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
        modules = cursor.fetchall()
        if not modules:
            print("No modules found."); return False

        print("\nModules:")
        for i, m in enumerate(modules, 1):
            print(f"  {i}. {m[0]} - {m[1]}")

        while True:
            raw = input("Select module number (or Enter to go back): ").strip()
            if not raw: return False
            try:
                idx = int(raw)
                if 1 <= idx <= len(modules):
                    module_code = modules[idx - 1][0]; break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a number.")

        # Pick day
        print("\nDay of week:")
        for i, d in enumerate(DAY_OPTIONS, 1):
            print(f"  {i}. {d}")
        while True:
            raw = input("Select day (or Enter to go back): ").strip()
            if not raw: return False
            try:
                idx = int(raw)
                if 1 <= idx <= len(DAY_OPTIONS):
                    day = DAY_OPTIONS[idx - 1]; break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a number.")

        # Pick start time
        print("\nStart time:")
        for i, t in enumerate(TIME_SLOTS, 1):
            print(f"  {i}. {t}")
        while True:
            raw = input("Select start time: ").strip()
            if not raw: return False
            try:
                idx = int(raw)
                if 1 <= idx <= len(TIME_SLOTS):
                    start_time = TIME_SLOTS[idx - 1]; break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a number.")

        # Pick end time
        print("\nEnd time:")
        for i, t in enumerate(TIME_SLOTS, 1):
            print(f"  {i}. {t}")
        while True:
            raw = input("Select end time: ").strip()
            if not raw: return False
            try:
                idx = int(raw)
                if 1 <= idx <= len(TIME_SLOTS):
                    end_time = TIME_SLOTS[idx - 1]; break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a number.")

        if end_time <= start_time:
            print("End time must be after start time."); return False

        # Session type
        session_types = ["Lecture", "Tutorial", "Lab", "Seminar", "Workshop"]
        print("\nSession type:")
        for i, s in enumerate(session_types, 1):
            print(f"  {i}. {s}")
        while True:
            raw = input("Select session type (default 1): ").strip()
            if not raw:
                session_type = "Lecture"; break
            try:
                idx = int(raw)
                if 1 <= idx <= len(session_types):
                    session_type = session_types[idx - 1]; break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a number.")

        # Pick room (availability-aware)
        booked_q = ("SELECT DISTINCT room_id FROM module_schedule "
                    "WHERE day_of_week = ? AND start_time = ? AND end_time = ? AND room_id IS NOT NULL")
        cursor.execute(booked_q, (day, start_time, end_time))
        booked_rooms = {r[0] for r in cursor.fetchall()}

        cursor.execute("SELECT id, room_number, building, capacity, room_type FROM rooms "
                       "WHERE is_active = 1 AND LOWER(COALESCE(status,'available')) = 'available' "
                       "ORDER BY building, room_number")
        all_rooms = cursor.fetchall()
        available_rooms = [r for r in all_rooms if r[0] not in booked_rooms]

        room_id = None
        if available_rooms:
            print(f"\nAvailable rooms for {day} {start_time}-{end_time}:")
            for i, r in enumerate(available_rooms, 1):
                print(f"  {i}. {r[1]} — {r[2] or 'N/A'} ({r[4] or 'N/A'}, cap: {r[3] or '?'})")
            raw = input("Select room (or Enter to skip): ").strip()
            if raw:
                try:
                    idx = int(raw)
                    if 1 <= idx <= len(available_rooms):
                        room_id = available_rooms[idx - 1][0]
                except ValueError:
                    pass
        else:
            print("No rooms available for this time slot.")

        # Pick instructor (availability-aware)
        booked_q = ("SELECT DISTINCT instructor_id FROM module_schedule "
                    "WHERE day_of_week = ? AND start_time = ? AND end_time = ? AND instructor_id IS NOT NULL")
        cursor.execute(booked_q, (day, start_time, end_time))
        booked_instr = {r[0] for r in cursor.fetchall()}

        cursor.execute("SELECT id, first_name, last_name, department FROM instructors "
                       "WHERE LOWER(status) = 'active' ORDER BY last_name, first_name")
        all_instr = cursor.fetchall()
        available_instr = [i for i in all_instr if i[0] not in booked_instr]

        instructor_id = None
        if available_instr:
            print(f"\nAvailable instructors for {day} {start_time}-{end_time}:")
            for i, inst in enumerate(available_instr, 1):
                print(f"  {i}. {inst[1]} {inst[2]} — {inst[3] or 'N/A'}")
            raw = input("Select instructor (or Enter to skip): ").strip()
            if raw:
                try:
                    idx = int(raw)
                    if 1 <= idx <= len(available_instr):
                        instructor_id = available_instr[idx - 1][0]
                except ValueError:
                    pass
        else:
            print("No instructors available for this time slot.")

        # Confirm
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
        INSERT INTO module_schedule (module_code, day_of_week, start_time, end_time,
                                    room_id, instructor_id, session_type, created_date, modified_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (module_code, day, start_time, end_time, room_id, instructor_id,
              session_type, timestamp, timestamp))
        conn.commit()

        print(f"\nSchedule created: {module_code} on {day} {start_time}-{end_time}")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()


def email_module_students():
    """Send an email to all students enrolled on a module."""
    auth = get_auth()
    if not auth or not auth.current_user:
        print("You must be logged in."); return
    if not auth.check_permission('manage_modules'):
        print("You don't have permission."); return

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
        modules = cursor.fetchall()
        if not modules:
            print("No modules found."); return

        print("\nModules:")
        for i, m in enumerate(modules, 1):
            print(f"  {i}. {m[0]} - {m[1]}")

        while True:
            raw = input("Select module number (or Enter to go back): ").strip()
            if not raw: return
            try:
                idx = int(raw)
                if 1 <= idx <= len(modules):
                    module_code = modules[idx - 1][0]
                    module_name = modules[idx - 1][1]
                    break
                print("Invalid choice.")
            except ValueError:
                print("Please enter a number.")

        # Get students with emails
        cursor.execute("""
        SELECT s.student_id, s.first_name, s.last_name, s.email
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ? AND s.email IS NOT NULL AND s.email != ''
        """, (module_code,))
        students = cursor.fetchall()

        if not students:
            print(f"No students with emails found on module {module_code}."); return

        print(f"\n{len(students)} student(s) on {module_code} - {module_name}:")
        for s in students:
            print(f"  {s[0]} — {s[1]} {s[2]} ({s[3]})")

        subject = input("\nEmail subject: ").strip()
        if not subject:
            print("Subject cannot be empty."); return

        body = input("Email body: ").strip()
        if not body:
            print("Body cannot be empty."); return

        confirm = input(f"\nSend to {len(students)} student(s)? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled."); return

        from education_system.post_18.university_system.infrastructure.email import send_email
        sent = 0
        for s in students:
            try:
                send_email(s[3], subject, f"Dear {s[1]} {s[2]},\n\n{body}\n\nBest regards,\nUniversity Administration")
                sent += 1
            except Exception as e:
                print(f"  Failed to send to {s[3]}: {e}")

        print(f"\nEmails sent: {sent}/{len(students)}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()


def import_modules_csv():
    """Import modules from a CSV file."""
    auth = get_auth()
    if not auth or not auth.current_user:
        print("You must be logged in."); return False
    if not auth.check_permission('manage_modules'):
        print("You don't have permission."); return False

    import csv

    filepath = input("Enter CSV file path (or Enter to go back): ").strip()
    if not filepath:
        return False

    conn = None
    try:
        with open(filepath, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            required = ['module_code', 'module_name']
            if not all(field in (reader.fieldnames or []) for field in required):
                print(f"CSV must have columns: {', '.join(required)}")
                return False

            conn = get_db_connection()
            cursor = conn.cursor()
            success = 0
            errors = 0

            for row_num, row in enumerate(reader, 1):
                try:
                    code = row['module_code'].strip().upper()
                    name = row['module_name'].strip()
                    mtype = row.get('module_type', 'optional').strip()

                    if not code or not name:
                        print(f"  Row {row_num}: missing code or name"); errors += 1; continue

                    cursor.execute("SELECT module_code FROM modules WHERE module_code = ?", (code,))
                    if cursor.fetchone():
                        print(f"  Row {row_num}: {code} already exists"); errors += 1; continue

                    cursor.execute("INSERT INTO modules (module_code, module_name, module_type) VALUES (?, ?, ?)",
                                   (code, name, mtype))
                    success += 1
                except Exception as e:
                    print(f"  Row {row_num}: {e}"); errors += 1

            conn.commit()
            print(f"\nImport complete: {success} imported, {errors} errors")
            return success > 0

    except FileNotFoundError:
        print("File not found.")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if conn:
            conn.close()


def export_modules_csv():
    """Export all modules to a CSV file."""
    auth = get_auth()
    if not auth or not auth.current_user:
        print("You must be logged in."); return False

    import csv

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT module_code, module_name, module_type, COALESCE(credits, 0),
               COALESCE(semester, ''), COALESCE(department, '')
        FROM modules ORDER BY module_code
        """)
        modules = cursor.fetchall()

        if not modules:
            print("No modules to export."); return False

        filename = f"modules_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['module_code', 'module_name', 'module_type', 'credits', 'semester', 'department'])
            for m in modules:
                writer.writerow(m)

        print(f"Exported {len(modules)} modules to {filename}")
        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except IOError as e:
        print(f"File error: {e}")
        return False
    finally:
        if conn:
            conn.close()


def validate_module_data():
    """Validate module data integrity."""
    auth = get_auth()
    if not auth or not auth.current_user:
        print("You must be logged in."); return
    if not auth.check_permission('manage_modules'):
        print("You don't have permission."); return

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        issues = []

        print("\nValidating module data...")

        # Modules with no code
        cursor.execute("SELECT module_id, module_name FROM modules WHERE module_code IS NULL OR module_code = ''")
        bad_codes = cursor.fetchall()
        if bad_codes:
            issues.append(f"{len(bad_codes)} module(s) with missing code")
            for m in bad_codes:
                print(f"  - ID {m[0]}: {m[1]} has no code")

        # Modules with no name
        cursor.execute("SELECT module_code FROM modules WHERE module_name IS NULL OR module_name = ''")
        bad_names = cursor.fetchall()
        if bad_names:
            issues.append(f"{len(bad_names)} module(s) with missing name")

        # Duplicate module codes
        cursor.execute("SELECT module_code, COUNT(*) as cnt FROM modules GROUP BY module_code HAVING cnt > 1")
        dupes = cursor.fetchall()
        if dupes:
            issues.append(f"{len(dupes)} duplicate module code(s)")
            for d in dupes:
                print(f"  - {d[0]} appears {d[1]} times")

        # Orphaned student_modules (module no longer exists)
        cursor.execute("""
        SELECT DISTINCT sm.module_code FROM student_modules sm
        LEFT JOIN modules m ON sm.module_code = m.module_code
        WHERE m.module_code IS NULL
        """)
        orphans = cursor.fetchall()
        if orphans:
            issues.append(f"{len(orphans)} orphaned student_module reference(s)")
            for o in orphans:
                print(f"  - student_modules references non-existent module: {o[0]}")

        # Orphaned module_schedule
        cursor.execute("""
        SELECT DISTINCT ms.module_code FROM module_schedule ms
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE m.module_code IS NULL
        """)
        orphan_sched = cursor.fetchall()
        if orphan_sched:
            issues.append(f"{len(orphan_sched)} orphaned schedule reference(s)")

        # Schedule conflicts (same room, same day/time)
        cursor.execute("""
        SELECT a.module_code, b.module_code, a.day_of_week, a.start_time, a.end_time
        FROM module_schedule a
        JOIN module_schedule b ON a.room_id = b.room_id
            AND a.day_of_week = b.day_of_week
            AND a.start_time = b.start_time
            AND a.id < b.id
            AND a.room_id IS NOT NULL
        """)
        conflicts = cursor.fetchall()
        if conflicts:
            issues.append(f"{len(conflicts)} room scheduling conflict(s)")
            for c in conflicts:
                print(f"  - {c[0]} and {c[1]} share a room on {c[2]} at {c[3]}")

        if not issues:
            print("\nAll checks passed. No issues found.")
        else:
            print(f"\nFound {len(issues)} issue(s):")
            for issue in issues:
                print(f"  - {issue}")

            fix = input("\nAttempt to clean orphaned records? (y/n): ").strip().lower()
            if fix == 'y':
                if orphans:
                    cursor.execute("""
                    DELETE FROM student_modules WHERE module_code NOT IN (SELECT module_code FROM modules)
                    """)
                    print(f"  Removed {cursor.rowcount} orphaned student_module records")
                if orphan_sched:
                    cursor.execute("""
                    DELETE FROM module_schedule WHERE module_code NOT IN (SELECT module_code FROM modules)
                    """)
                    print(f"  Removed {cursor.rowcount} orphaned schedule records")
                conn.commit()
                print("Cleanup complete.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


def backup_module_data():
    """Backup module-related data to a SQL dump file."""
    auth = get_auth()
    if not auth or not auth.current_user:
        print("You must be logged in."); return
    if not auth.check_permission('manage_modules'):
        print("You don't have permission."); return

    conn = None
    try:
        conn = get_db_connection()

        filename = f"module_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        tables = ['modules', 'student_modules', 'module_schedule']

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"-- Module data backup {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for table in tables:
                try:
                    for line in conn.iterdump():
                        if table in line.lower():
                            f.write(f"{line}\n")
                    break  # iterdump iterates all tables at once
                except Exception:
                    pass

        # Simpler approach: export each table as INSERT statements
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"-- Module data backup {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            cursor = conn.cursor()
            for table in tables:
                try:
                    cursor.execute(f"SELECT * FROM [{table}]")
                    rows = cursor.fetchall()
                    cols = [desc[0] for desc in cursor.description]
                    f.write(f"-- Table: {table} ({len(rows)} rows)\n")
                    for row in rows:
                        vals = ', '.join(repr(v) for v in row)
                        f.write(f"INSERT INTO [{table}] ({', '.join(cols)}) VALUES ({vals});\n")
                    f.write("\n")
                except sqlite3.Error:
                    f.write(f"-- Table {table} not found\n\n")

        print(f"Backup saved as {filename}")

    except Exception as e:
        print(f"Error creating backup: {e}")
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def display_module_management_menu():
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to access module management.")
        return

    if not (auth.check_permission('manage_modules') or auth.check_permission('view_assigned_modules')):
        print("You don't have permission to access module management.")
        return

    can_manage = auth.check_permission('manage_modules')

    while True:
        print("\n" + "=" * 60)
        print("MODULE MANAGEMENT".center(60))
        print("=" * 60)

        options = []

        if can_manage:
            print("\n📚 MODULE CRUD:")
            print("  1. Create new module")
            print("  2. Edit module")
            print("  3. Delete module")
            options.extend(['create_module', 'edit_module', 'delete_module'])

            print("\n🔍 SEARCH:")
            print("  4. Search module by name")
            print("  5. Search module by code")
            options.extend(['search_name', 'search_code'])

            print("\n📅 SCHEDULING:")
            print("  6. Schedule module")
            print("  7. View timetable")
            options.extend(['schedule', 'timetable'])

            print("\n📊 REPORTS & EMAIL:")
            print("  8. Generate module report")
            print("  9. Email students on module")
            options.extend(['report', 'email_students'])

            print("\n💾 BULK OPERATIONS:")
            print("  10. Import modules from CSV")
            print("  11. Export modules to CSV")
            options.extend(['import_csv', 'export_csv'])

            print("\n🔧 MAINTENANCE:")
            print("  12. Validate module data")
            print("  13. Backup module data")
            options.extend(['validate', 'backup'])

            max_option = 13
        else:
            print("\n🔍 SEARCH:")
            print("  1. Search module by name")
            print("  2. Search module by code")
            print("  3. View timetable")
            print("  4. Generate module report")
            options.extend(['search_name', 'search_code', 'timetable', 'report'])
            max_option = 4

        print("\n  0. Return to Main Menu")

        choice = input(f"\nEnter your choice (0-{max_option}): ").strip()

        if choice == '0' or choice == '':
            return

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                selected = options[choice_num - 1]
                _dispatch_option(selected)
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

        input("\nPress Enter to continue...")


def _dispatch_option(option):
    """Dispatch a menu option to its handler."""
    handlers = {
        'create_module': create_module,
        'edit_module': edit_module,
        'delete_module': delete_module,
        'search_name': search_module_by_module_name,
        'search_code': search_module_by_module_code,
        'schedule': schedule_module,
        'timetable': view_module_timetable,
        'report': generate_module_report,
        'email_students': email_module_students,
        'import_csv': import_modules_csv,
        'export_csv': export_modules_csv,
        'validate': validate_module_data,
        'backup': backup_module_data,
    }
    handler = handlers.get(option)
    if handler:
        handler()


__all__ = [
    'create_module',
    'edit_module',
    'delete_module',
    'search_module_by_module_name',
    'search_module_by_module_code',
    'generate_module_report',
    'view_module_timetable',
    'schedule_module',
    'email_module_students',
    'import_modules_csv',
    'export_modules_csv',
    'validate_module_data',
    'backup_module_data',
    'display_module_management_menu',
]
