"""
Student operations for CLI system.

Handles student CRUD operations, record management, and display.
"""

import hashlib
import random
import secrets

from education_system.university_system.modules.shared.cli.imports import (
    logging, sqlite3, time, datetime, DB_PATH, logger, _t,
    log_activity, log_create, log_read, log_update, log_delete, get_auth,
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2, optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
)

from education_system.university_system.modules.shared.cli.auth_manager import ensure_user_in_communication_system
from education_system.university_system.modules.shared.cli.database_manager import DatabaseError, ValidationError, safe_db_operation_with_retry, enhanced_db_operation
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.infrastructure.email.email_service import (
    send_registration_confirmation, send_update_confirmation
)

# Global auth
auth = None

def set_auth(auth_instance):
    """Set the authentication instance for this module"""
    global auth
    auth = auth_instance

def get_db_connection(timeout=5.0):
    """Get database connection"""
    return sqlite3.connect(DB_PATH, timeout=timeout)


def create_student_record():
    global auth

    # Check for permission
    if not auth or not auth.current_user:
        print("You must be logged in to create student records.")
        return

    if not auth.check_permission('create_student'):
        print("You don't have permission to create student records.")
        return

    # Get student name
    first_name = None
    while not first_name:
        first_name = input("Enter first name: ").strip()
        if not first_name:
            print("Error. Please enter a name.")
    
    middle_name = input("Enter middle name (optional): ").strip()
    
    last_name = None
    while not last_name:
        last_name = input("Enter last name: ").strip()
        if not last_name:
            print("Error. Please enter a name.")

    # Get gender and title
    while True:
        gender = input("Are you 'male', 'female', or 'other'?: ").strip().lower()
        if gender == 'male':
            title = 'Mr'
            break
        elif gender == 'female':
            title = 'Miss'
            break
        elif gender == 'other':
            title = input("Enter title (Mr/Ms/Dr/etc.): ").strip()
            if not title:
                title = ''
            break
        else:
            print("Error. Please enter 'male', 'female', or 'other'.")

    # Get date of birth
    def get_valid_date():
        while True:
            dob_str = input("Enter the date of birth (YYYY-MM-DD): ").strip()
            try:
                return datetime.strptime(dob_str, "%Y-%m-%d")
            except ValueError:
                print("Invalid date. Please enter a valid date in YYYY-MM-DD format.")
    
    dob = get_valid_date()

    # Compute age
    now_dt = datetime.now()
    age = now_dt.year - dob.year - ((now_dt.month, now_dt.day) < (dob.month, dob.day))
    print(f"Your age is {age}.")

    # Randomly choose course
    course = random.choice(['CS', 'DS'])
    print(f"Automatically selected course: {course}")

    # Show compulsory modules
    print("You will be required to study 2 compulsory modules which are:")
    print(f"{compulsory_module_1['code']} - {compulsory_module_1['name']}")
    print(f"{compulsory_module_2['code']} - {compulsory_module_2['name']}")
    input("Press Enter to proceed...")

    # Generate student ID and email
    student_id = secrets.randbelow(10000000)
    student_id_str = str(student_id).zfill(7)
    email_address = f"C{student_id_str}@tees.ac.uk"
    print(f"Student ID: {student_id_str}")
    print(f"Email address: {email_address}")
    input("Press Enter to proceed...")

    # Randomly select two optional modules
    modules = {
        '1': optional_module_1,
        '2': optional_module_2,
        '3': optional_module_3,
        '4': optional_module_4,
    }
    opt_keys = random.sample(list(modules.keys()), 2)
    module1, module2 = modules[opt_keys[0]], modules[opt_keys[1]]
    print("Selected optional modules:")
    print(f"{module1['code']} - {module1['name']}")
    print(f"{module2['code']} - {module2['name']}")
    input("Press Enter to proceed...")

    # Randomly select two course-specific modules
    pool = {
        'CS': {'1': CS_optional_module_1, '2': CS_optional_module_2, '3': CS_optional_module_3, '4': CS_optional_module_4},
        'DS': {'1': DS_optional_module_1, '2': DS_optional_module_2, '3': DS_optional_module_3, '4': DS_optional_module_4}
    }[course]
    course_keys = random.sample(list(pool.keys()), 2)
    module3, module4 = pool[course_keys[0]], pool[course_keys[1]]
    print(f"Selected {course}-specific modules:")
    print(f"{module3['code']} - {module3['name']}")
    print(f"{module4['code']} - {module4['name']}")

    # Record registration datetime
    registration_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')
    print(f"Registration completed on {registration_time}")

    # Add retry logic for database operations
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        conn = None
        try:
            conn = get_db_connection(timeout=30.0)
            if not conn:
                raise sqlite3.Error("Could not connect to database")
                
            cursor = conn.cursor()

            # Temporarily disable foreign key checks to avoid module_code issues
            cursor.execute("PRAGMA foreign_keys = OFF")

            # Insert into students table with better error handling
            try:
                cursor.execute(
                    '''INSERT INTO students (student_id, email_address, title,
                       first_name, middle_name, last_name, gender, dob, age,
                       course, registration_datetime, status, enrollment_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        student_id_str,
                        email_address,
                        title,
                        first_name,
                        middle_name,
                        last_name,
                        gender,
                        dob.strftime('%Y-%m-%d'),
                        age,
                        course,
                        registration_time,
                        'Active',  # status
                        registration_time  # enrollment_date
                    )
                )

                # Insert modules
                module_data = [
                    (student_id_str, compulsory_module_1['code']),
                    (student_id_str, compulsory_module_2['code']),
                    (student_id_str, module1['code']),
                    (student_id_str, module2['code']),
                    (student_id_str, module3['code']),
                    (student_id_str, module4['code'])
                ]
                cursor.executemany(
                    'INSERT INTO student_modules (student_id, module_code) VALUES (?, ?)',
                    module_data
                )

                # Re-enable foreign key checks
                cursor.execute("PRAGMA foreign_keys = ON")

                # Commit all student data before creating user
                conn.commit()
                conn.close()
                conn = None  # Mark as closed to avoid double-close
                
                # Add a small delay to ensure the database commit is fully processed
                time.sleep(0.1)
                
                # Success - break out of retry loop
                break
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and retry_count < max_retries - 1:
                    print(f"Database temporarily locked, retrying... (attempt {retry_count + 1})")
                    retry_count += 1
                    time.sleep(1)  # Wait 1 second before retry
                    if conn:
                        try:
                            conn.close()
                        except sqlite3.Error as close_error:
                            logging.debug(f"Error closing connection during retry: {close_error}")
                        except (sqlite3.Error, DatabaseError) as close_error:
                            logging.warning(f"Unexpected error closing connection during retry: {close_error}")
                        finally:
                            conn = None
                    continue
                else:
                    raise e
                    
        except (ValueError, TypeError, ValidationError) as e:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error as close_error:
                    logging.debug(f"Error closing connection after exception: {close_error}")
                except (RuntimeError, OSError) as close_error:
                    logging.warning(f"Unexpected error closing connection after exception: {close_error}")
                finally:
                    conn = None
                    
            if retry_count >= max_retries - 1:
                logging.error(f"Failed to create student record after {max_retries} attempts: {e}")
                print(f"Error: Failed to create student record after {max_retries} attempts. Please try again later.")
                return
            retry_count += 1
            time.sleep(1)

    # Add a small delay to ensure the database commit is fully processed
    time.sleep(0.1)

    # Create user account and integrate with communication system
    temp_password = f"{first_name}123456"
    try:
        # Create user account through authentication system
        created = auth.create_user(
            username=student_id_str,
            password=temp_password,
            email=email_address,
            first_name=first_name,
            last_name=last_name,
            role='student',
            student_id=student_id_str,
            password_reset_required=False
        )
        
        if created:
            print("\nUser account created successfully!")
            print(f"  Username: {student_id_str}")
            print(f"  Password: {temp_password}")
            
            # Ensure the user is integrated with the communication system
            ensure_user_in_communication_system(
                username=student_id_str,
                first_name=first_name,
                last_name=last_name,
                email=email_address,
                role='student',
                student_id=student_id_str
            )
            
            print(f"Student '{first_name} {last_name}' can now send and receive messages through the communication system.")
            
            # Send registration confirmation email
            try:
                send_registration_confirmation(student_id_str)
                print("Registration confirmation email has been sent.")
            except (ValueError, TypeError, ValidationError) as e:
                logging.warning(f"Registration confirmation email could not be sent: {e}")
            
        else:
            print("Failed to create user account. It may already exist.")
            
    except (ValueError, TypeError, ValidationError) as e:
        logging.error(f"Error creating student user account: {e}")
        print("Warning: Student record created but user account creation failed. Please contact an administrator.")

    print(f"\nStudent record creation complete!")
    print(f"Student ID: {student_id_str}")
    print(f"Email: {email_address}")
    print(f"The student can now log in and use all system features including messaging.")
    input("\nPress Enter to continue...")


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


def update_student_record():
    global auth

    # --- Permission checks ---
    if not auth or not auth.current_user:
        print("You must be logged in to update student records.")
        return

    if not (auth.has_permission('update_any_student') or auth.has_permission('update_own_profile')):
        print("You don't have permission to update student records.")
        return

    # Backup before making changes
    backup_before_operation('update')

    # Use safe database operation with retry logic
    def perform_update_operation(conn):
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- Identify student record ---
        if auth.has_permission('update_any_student'):
            # Admin/staff: pick any student
            while True:
                student_id = input("Enter student ID to update: ").strip()
                if not student_id:
                    print("Error: Student ID is required.")
                    continue

                cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
                student = cursor.fetchone()
                if student:
                    break
                print("Error: Student ID not found.")
        else:
            # Student: only own record - updated query for new database structure
            cursor.execute(
                "SELECT student_id FROM users WHERE id = ?",
                (auth.current_user['id'],)
            )
            row = cursor.fetchone()
            if not row or not row['student_id']:
                print("No student ID linked to your account.")
                return False

            student_id = row['student_id']
            cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
            student = cursor.fetchone()
            if not student:
                print("Your student record was not found.")
                return False

        # Initialize updated_fields dictionary
        updated_fields = {}
        last_field_num = None

        # --- Select field to update (loop for multiple updates) ---
        while True:
            while True:
                print("\nWhich field do you want to update?")
                print("1. First Name")
                print("2. Middle Name")
                print("3. Last Name")
                print("4. Gender")
                if auth.has_permission('update_any_student'):
                    print("5. Course")
                    print("6. Modules")
                    max_option = 6
                else:
                    max_option = 4
                print(f"{max_option + 1}. Return to Student Records Menu")

                choice = input(f"Select (1-{max_option + 1}): ").strip()
                if not choice:
                    continue
                if choice.isdigit() and int(choice) == max_option + 1:
                    if updated_fields:
                        # Already made changes, proceed to save them
                        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
                        updated = cursor.fetchone()
                        return {
                            'success': True,
                            'updated_student': updated,
                            'updated_fields': updated_fields,
                            'student_id': student_id,
                            'field_num': last_field_num
                        }
                    return None
                if choice.isdigit() and 1 <= int(choice) <= max_option:
                    break
                print("Invalid selection. Please try again.")

            field_num = int(choice)
            last_field_num = field_num

            # --- Perform update ---
            if field_num == 1:
                # First Name Update with Password Change
                while True:
                    new_first = input("New first name: ").strip()
                    if new_first:
                        # Update student record
                        cursor.execute(
                            "UPDATE students SET first_name = ? WHERE student_id = ?",
                            (new_first, student_id)
                        )
                        updated_fields["First Name"] = new_first

                        # Update password for corresponding user account
                        try:
                            # Find the user account associated with this student
                            cursor.execute("""
                                SELECT ua.id, ua.user_id, ua.username, u.email
                                FROM user_accounts ua
                                JOIN users u ON ua.user_id = u.id
                                WHERE u.student_id = ?
                            """, (student_id,))

                            user_account = cursor.fetchone()

                            if user_account:
                                account_id, user_id, username, email = user_account

                                # Generate new password: {firstname}123456
                                new_password = f"{new_first.lower()}123456"

                                # Hash the new password using the same method as UserAuth
                                salt = secrets.token_hex(16)
                                key = hashlib.pbkdf2_hmac(
                                    'sha256',
                                    new_password.encode(),
                                    salt.encode(),
                                    100000,
                                    dklen=64
                                )
                                password_hash = key.hex()

                                # Update the password in user_accounts table
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                cursor.execute("""
                                    UPDATE user_accounts
                                    SET password_hash = ?, salt = ?, updated_at = ?, password_reset_required = 0
                                    WHERE id = ?
                                """, (password_hash, salt, timestamp, account_id))

                                # Also update the first name in users table to keep it in sync
                                cursor.execute("""
                                    UPDATE users
                                    SET first_name = ?, updated_at = ?
                                    WHERE id = ?
                                """, (new_first, timestamp, user_id))

                                print(f"✅ Password automatically updated to: {new_password}")
                                print(f"🔐 User '{username}' can now log in with the new password.")

                                # Log the password change activity using the same connection
                                try:
                                    log_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    ip_address = "127.0.0.1"  # Default IP
                                    current_user_id = auth.current_user['id'] if auth.current_user else None
                                    current_username = auth.current_user['username'] if auth.current_user else 'system'

                                    cursor.execute("""
                                        INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    """, (
                                        current_user_id,
                                        current_username,
                                        f'Password auto-updated for user: {username}',
                                        f'Due to first name change to: {new_first}',
                                        log_timestamp,
                                        ip_address
                                    ))
                                except sqlite3.Error as log_error:
                                    # Don't fail the update if logging fails
                                    print(f"Note: Activity logging failed: {log_error}")

                                updated_fields["Password"] = f"Updated to {new_password}"
                            else:
                                print("⚠️  No user account found for this student. Password not updated.")

                        except sqlite3.Error as e:
                            print(f"⚠️  Error updating password: {e}")
                            # Continue with the student record update even if password update fails

                        break
                    print("Error: Name cannot be empty.")

            elif field_num == 2:
                new_middle = input("New middle name: ").strip()
                cursor.execute(
                    "UPDATE students SET middle_name = ? WHERE student_id = ?",
                    (new_middle, student_id)
                )
                updated_fields["Middle Name"] = new_middle

            elif field_num == 3:
                while True:
                    new_last = input("New last name: ").strip()
                    if new_last:
                        cursor.execute(
                            "UPDATE students SET last_name = ? WHERE student_id = ?",
                            (new_last, student_id)
                        )
                        updated_fields["Last Name"] = new_last

                        # Also update last name in users table to keep it in sync
                        try:
                            cursor.execute("""
                                SELECT u.id FROM users u WHERE u.student_id = ?
                            """, (student_id,))
                            user_record = cursor.fetchone()

                            if user_record:
                                user_id = user_record[0]
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                cursor.execute("""
                                    UPDATE users
                                    SET last_name = ?, updated_at = ?
                                    WHERE id = ?
                                """, (new_last, timestamp, user_id))
                                print("✅ User profile last name also updated.")
                        except sqlite3.Error as e:
                            print(f"⚠️  Error updating user profile last name: {e}")

                        break
                    print("Error: Name cannot be empty.")

            elif field_num == 4:
                while True:
                    gender = input("Gender ('male','female','other'): ").strip().lower()
                    if gender in ('male', 'female', 'other'):
                        title = {'male': 'Mr', 'female': 'Miss', 'other': ''}[gender]
                        break
                    print("Error: Enter 'male', 'female', or 'other'.")

                cursor.execute(
                    "UPDATE students SET gender = ?, title = ? WHERE student_id = ?",
                    (gender, title, student_id)
                )
                updated_fields["Gender"] = gender
                updated_fields["Title"] = title

            elif field_num == 5 and auth.check_permission('update_any_student'):
                # Swap course
                cursor.execute(
                    "SELECT course FROM students WHERE student_id = ?",
                    (student_id,)
                )
                old_course = cursor.fetchone()[0]
                new_course = 'DS' if old_course == 'CS' else 'CS'
                cursor.execute(
                    "UPDATE students SET course = ? WHERE student_id = ?",
                    (new_course, student_id)
                )

                # Delete old course-specific modules
                if old_course == 'CS':
                    old_modules = [CS_optional_module_1['code'], CS_optional_module_2['code'],
                                  CS_optional_module_3['code'], CS_optional_module_4['code']]
                else:
                    old_modules = [DS_optional_module_1['code'], DS_optional_module_2['code'],
                                  DS_optional_module_3['code'], DS_optional_module_4['code']]

                if old_modules:
                    placeholders = ','.join('?' * len(old_modules))
                    cursor.execute(
                        f"DELETE FROM student_modules WHERE student_id = ? AND module_code IN ({placeholders})",
                        [student_id] + old_modules
                    )

                # Add new course-specific modules
                if new_course == 'CS':
                    modules = [CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4]
                else:
                    modules = [DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4]

                selected_modules = random.sample(modules, 2)
                for module in selected_modules:
                    cursor.execute(
                        "INSERT INTO student_modules (student_id, module_code) VALUES (?, ?)",
                        (student_id, module['code'])
                    )

                updated_fields["Course"] = new_course

            elif field_num == 6 and auth.check_permission('update_any_student'):
                sel = input("1. Optional modules  2. Course-specific modules: ").strip()
                if sel == '1':
                    modules = [optional_module_1, optional_module_2, optional_module_3, optional_module_4]
                    # Get codes of old optional modules to delete
                    old_module_codes = [optional_module_1['code'], optional_module_2['code'],
                                       optional_module_3['code'], optional_module_4['code']]
                elif sel == '2':
                    cursor.execute("SELECT course FROM students WHERE student_id = ?", (student_id,))
                    course = cursor.fetchone()[0]
                    if course == 'CS':
                        modules = [CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4]
                        old_module_codes = [CS_optional_module_1['code'], CS_optional_module_2['code'],
                                           CS_optional_module_3['code'], CS_optional_module_4['code']]
                    else:
                        modules = [DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4]
                        old_module_codes = [DS_optional_module_1['code'], DS_optional_module_2['code'],
                                           DS_optional_module_3['code'], DS_optional_module_4['code']]
                else:
                    print("Invalid choice.")
                    continue

                # Delete old modules by their codes
                if old_module_codes:
                    placeholders = ','.join('?' * len(old_module_codes))
                    cursor.execute(
                        f"DELETE FROM student_modules WHERE student_id = ? AND module_code IN ({placeholders})",
                        [student_id] + old_module_codes
                    )

                selected_modules = random.sample(modules, 2)
                for module in selected_modules:
                    cursor.execute(
                        "INSERT INTO student_modules (student_id, module_code) VALUES (?, ?)",
                        (student_id, module['code'])
                    )

                updated_fields["Modules"] = "Updated modules"

            else:
                print("Invalid option.")
                continue

            # Ask if user wants to update another field
            another = input("\nWould you like to update another field? (y/n): ").strip().lower()
            if another != 'y':
                break

        # Get updated student record and return the data for display
        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
        updated = cursor.fetchone()

        return {
            'success': True,
            'updated_student': updated,
            'updated_fields': updated_fields,
            'student_id': student_id,
            'field_num': last_field_num
        }

    # Execute the update operation using safe database handling
    try:
        result = safe_db_operation_with_retry(perform_update_operation, max_retries=3)

        if result is None:
            return
        if not result.get('success'):
            print("Failed to update student record. Please try again.")
            return
        
        # Display the updated record
        display_student_record(result['updated_student'])

        # Send confirmation email with error handling
        try:
            student_email = result['updated_student']['email_address']
            send_update_confirmation(student_email, result['updated_fields'])
        except (ValueError, TypeError, ValidationError) as e:
            logging.warning(f"Update confirmation email could not be sent ({type(e).__name__})")
        
        print("\nStudent record updated successfully!")
        
        # Display password change summary if first name was updated
        if result['field_num'] == 1:
            print("\n" + "="*50)
            print("🔐 PASSWORD UPDATE SUMMARY")
            print("="*50)
            print(f"Student ID: {result['student_id']}")
            print(f"New First Name: {result['updated_fields'].get('First Name', 'N/A')}")
            if "Password" in result['updated_fields']:
                print(f"New Password: {result['updated_fields']['Password'].replace('Updated to ', '')}")
                print("\n⚠️  IMPORTANT: Please inform the student of their new password!")
            print("="*50)
            
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error during student record update: {e}")
        print("An error occurred while updating the student record. Please try again.")
    

def delete_student_record():
    global auth
    
    # Check for permission
    if not auth or not auth.current_user:
        print("You must be logged in to delete student records.")
        return
    
    if not auth.check_permission('delete_any_student'):
        print("You don't have permission to delete student records.")
        return
    
    backup_before_operation('delete')
    
    def perform_delete_operation(conn):
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ask the user for the student ID to delete
        id_num = input("Enter the ID number of the student to delete: ").strip()
        
        if not id_num:
            print("Error: Student ID cannot be empty.")
            return False
        
        # Check if the student exists
        cursor.execute('SELECT student_id, first_name, last_name FROM students WHERE student_id = ?', (id_num,))
        student = cursor.fetchone()
        
        if not student:
            print("No student records found with that ID.")
            return False
        
        # Display student info and confirm deletion
        print(f"\nStudent to delete:")
        print(f"ID: {student['student_id']}")
        print(f"Name: {student['first_name']} {student['last_name']}")
        
        confirm = input(f"\nAre you sure you want to delete student {id_num}? This will also delete all related records. (y/n): ")
        if confirm.lower() != 'y':
            print("Delete operation cancelled.")
            return False
        
        try:
            # Disable foreign key constraints temporarily for this operation
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            # Delete from all related tables in the correct order
            # Start with tables that reference the student
            
            # Delete student grades
            cursor.execute('DELETE FROM student_grades WHERE student_id = ?', (id_num,))
            print(f"Deleted {cursor.rowcount} grade records.")
            
            # Delete attendance records
            cursor.execute('DELETE FROM attendance WHERE student_id = ?', (id_num,))
            print(f"Deleted {cursor.rowcount} attendance records.")
            
            # Delete student modules
            cursor.execute('DELETE FROM student_modules WHERE student_id = ?', (id_num,))
            print(f"Deleted {cursor.rowcount} module assignments.")
            
            # Delete user account (if exists) - first get the user_id
            cursor.execute('SELECT id, username FROM users WHERE student_id = ?', (id_num,))
            user_record = cursor.fetchone()

            if user_record:
                user_id = user_record['id']
                username = user_record['username']

                # Use auth system to delete user if available
                if auth:
                    if auth.delete_user(user_id):
                        print(f"Deleted user account via auth system (username: {username}).")
                        # Log activity
                        log_delete('user', user_id=user_id, details={'username': username, 'student_id': id_num, 'reason': 'Student deletion'})
                    else:
                        print(f"Warning: Failed to delete user via auth system for {username}.")
                else:
                    # Fallback to direct deletion if auth not available
                    cursor.execute('DELETE FROM user_accounts WHERE user_id = ?', (user_id,))
                    print(f"Deleted {cursor.rowcount} user account records.")

                    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                    print(f"Deleted {cursor.rowcount} user profile records.")
                    # Log activity even in fallback mode
                    log_delete('user', user_id=user_id, details={'username': username, 'student_id': id_num, 'reason': 'Student deletion (fallback)'})
            
            # Delete any parking permits
            try:
                cursor.execute('DELETE FROM parking_permits WHERE id IN (SELECT id FROM users WHERE student_id = ?)', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} parking permit records.")
            except sqlite3.OperationalError as e:
                # Table might not exist
                logger.debug(f"Parking permits table may not exist: {e}")
            
            # Delete any finance records
            try:
                cursor.execute('DELETE FROM student_fees WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} finance records.")
            except sqlite3.OperationalError as e:
                # Table might not exist
                logger.debug(f"Student fees table may not exist: {e}")
            
            # Delete any library records
            try:
                cursor.execute('DELETE FROM loans WHERE borrower_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} library loan records.")
            except sqlite3.OperationalError as e:
                # Table might not exist
                logger.debug(f"Loans table may not exist: {e}")
            
            # Delete any trip participation records
            try:
                cursor.execute('DELETE FROM trip_participants WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} trip participation records.")
            except sqlite3.OperationalError as e:
                # Table might not exist
                logger.debug(f"Trip participants table may not exist: {e}")
            
            # Delete any assignment submissions
            try:
                cursor.execute('DELETE FROM assignment_submissions WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} assignment submission records.")
            except sqlite3.OperationalError as e:
                # Table might not exist
                logger.debug(f"Assignment submissions table may not exist: {e}")
            
            # Delete any accommodation requests
            try:
                cursor.execute('DELETE FROM accommodation_requests WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} accommodation request records.")
            except sqlite3.OperationalError as e:
                # Table might not exist
                logger.debug(f"Accommodation requests table may not exist: {e}")
            
            # Delete any housing accommodation requests
            try:
                cursor.execute('DELETE FROM housing_requests WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} housing request records.")
            except sqlite3.OperationalError as e:
                # Table might not exist
                logger.debug(f"Housing requests table may not exist: {e}")
            
            # Delete any health records
            try:
                cursor.execute('DELETE FROM health_records WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} health records.")
            except sqlite3.OperationalError as e:
                # Table might not exist
                logger.debug(f"Health records table may not exist: {e}")
            
            # Delete any internship applications
            try:
                cursor.execute('DELETE FROM internship_applications WHERE student_id = ?', (id_num,))
                if cursor.rowcount > 0:
                    print(f"Deleted {cursor.rowcount} internship application records.")
            except sqlite3.OperationalError as e:
                # Table might not exist
                logger.debug(f"Internship applications table may not exist: {e}")
            
            # Finally, delete the main student record
            cursor.execute('DELETE FROM students WHERE student_id = ?', (id_num,))
            if cursor.rowcount > 0:
                print(f"Deleted main student record.")
            else:
                print("Warning: Student record was not found during final deletion.")
                return False
            
            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")
            
            print(f"\nStudent {id_num} and all related records have been successfully deleted.")
            return True
            
        except sqlite3.Error as e:
            # Re-enable foreign keys even if there was an error
            cursor.execute("PRAGMA foreign_keys = ON")
            logging.error(f"Database error during student deletion: {e}")
            print(f"Error during deletion: {e}")
            return False
    
    # Execute the delete operation using safe database handling
    try:
        success = safe_db_operation_with_retry(perform_delete_operation, max_retries=3)
        
        if success:
            print("Student record deletion completed successfully!")
        else:
            print("Failed to delete student record. Please try again.")
            
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error during student record deletion: {e}")
        print("An error occurred while deleting the student record. Please try again.")
    
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
    
    # Fetch and display modules
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT m.module_type, sm.module_code, m.module_name
            FROM student_modules sm
            JOIN modules m ON sm.module_code = m.module_code
            WHERE sm.student_id = ?
            ORDER BY m.module_type, sm.module_code
            ''', (student[0],))
            modules = cursor.fetchall()
            
            if modules:
                print("\nModules:")
                print("-" * 40)
                for module in modules:
                    print(f"{module[0]}: {module[1]} - {module[2]}")
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
        
        if auth.check_permission('delete_any_student'):
            print(f"{option_num}. Delete student record")
            options[str(option_num)] = 'delete_student'
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
            elif action == 'delete_student':
                delete_student_record()
            elif action == 'search_first_name':
                from education_system.university_system.modules.shared.cli.student_search import search_student_by_first_name
                search_student_by_first_name()
            elif action == 'search_last_name':
                from education_system.university_system.modules.shared.cli.student_search import search_student_by_last_name
                search_student_by_last_name()
            elif action == 'search_id':
                from education_system.university_system.modules.shared.cli.student_search import search_student_by_student_id
                search_student_by_student_id()
            elif action == 'search_date':
                from education_system.university_system.modules.shared.cli.student_search import search_student_by_registration_date
                search_student_by_registration_date()
        elif choice == str(option_num):
            return
        else:
            print("Invalid choice or insufficient permissions. Please try again.")


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


def example_create_student_operation(conn, student_data):
    """
    Example database operation that creates a student record.
    This shows how to structure operations for use with the retry function.
    """
    cursor = conn.cursor()
    
    try:
        # Insert student data
        cursor.execute('''
        INSERT INTO students (student_id, email_address, first_name, last_name, course)
        VALUES (?, ?, ?, ?, ?)
        ''', student_data)
        
        logging.info(f"Successfully created student record for ID: {student_data[0]}")
        return True
        
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            logging.warning(f"Student with ID {student_data[0]} already exists")
            raise  # Re-raise to be handled by the retry function
        else:
            logging.error(f"Data integrity issue when creating student: {e}")
            raise
            
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error creating student record: {e}")
        raise


# Helper function to use the enhanced operation


def create_student_with_retry(student_data):
    """
    Create a student record with retry logic and enhanced error handling.
    
    Args:
        student_data: Tuple containing student information
    
    Returns:
        Boolean indicating success or failure
    """
    success, result, error_type = enhanced_db_operation(
        example_create_student_operation, 
        student_data
    )
    
    if not success:
        if error_type == "integrity_error":
            print(f"Error: Student with ID {student_data[0]} already exists or data conflicts with existing records.")
        elif error_type == "database_locked":
            print("Error: Database is currently busy. Please try again in a moment.")
        elif error_type == "operational_error":
            print("Error: Database operational issue. Please contact system administrator.")
        else:
            print("Error: An unexpected issue occurred. Please try again or contact support.")
    
    return success


__all__ = [
    'create_student_record',
    'view_student_record',
    'update_student_record',
    'delete_student_record',
    'display_student_record',
    'display_student_records_menu',
    'fetch_student_data',
    'example_create_student_operation',
    'create_student_with_retry',
]
