from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.infrastructure.security.password_generator import generate_temp_password
import datetime
import random


class AccountsMixin:
    def setup_parent_permissions(self):
        """Set up permission system for parent users"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='permissions'")
            if not cursor.fetchone():
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT,
                    permission TEXT,
                    UNIQUE(role, permission)
                )
                ''')

            # Extended parent role permissions
            parent_permissions = [
                ('parent', 'view_child_records'),
                ('parent', 'view_child_grades'),
                ('parent', 'view_child_attendance'),
                ('parent', 'view_teacher_reports'),
                ('parent', 'message_teachers'),
                ('parent', 'view_child_timetable'),
                ('parent', 'view_child_assignments'),
                ('parent', 'set_notification_preferences'),
                ('parent', 'update_contact_info'),
                ('parent', 'view_school_calendar'),
                ('parent', 'report_absence'),
                ('parent', 'access_parent_dashboard'),
                ('parent', 'view_fees'),
                ('parent', 'manage_meal_account'),
                ('parent', 'view_behavior_reports'),
                ('parent', 'manage_medical_info'),
                ('parent', 'view_transportation'),
                ('parent', 'view_library_account'),
                ('parent', 'view_extracurricular'),
                ('parent', 'schedule_meetings'),
                ('parent', 'view_homework'),
                ('parent', 'set_academic_goals'),
                ('parent', 'view_announcements'),
                ('parent', 'manage_documents'),
                ('parent', 'manage_pickup_auth'),
                ('parent', 'manage_photo_permissions'),
                ('parent', 'view_analytics'),
                ('parent', 'group_messaging'),
                ('parent', 'emergency_contact_update')
            ]

            for role, permission in parent_permissions:
                try:
                    cursor.execute('INSERT INTO permissions (role, permission) VALUES (?, ?)',
                                  (role, permission))
                except sqlite3.IntegrityError:
                    pass

            conn.commit()
            print("Enhanced parent permissions set up successfully!")
        except sqlite3.Error as e:
            print(f"An error occurred while setting up parent permissions: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    @staticmethod
    def create_parent_user(auth, first_name, last_name, email, phone="", address=""):
        """Create a new parent user account"""
        parent_id = f"P{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        base = ''.join(c for c in f"{first_name[0]}{last_name}".lower() if c.isalnum())[:16]
        suffix = str(random.randint(100, 999))
        username = f"{base}{suffix}"
        password = generate_temp_password()  # Secure random password
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            cursor.execute(
                '''INSERT INTO parent_accounts
                   (parent_id, first_name, last_name, email, phone, address, registration_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (parent_id, first_name, last_name, email, phone, address, timestamp)
            )
            cursor.execute(
                'INSERT INTO parent_preferences (parent_id) VALUES (?)',
                (parent_id,)
            )

            conn.commit()
            conn.close()
            conn = None

            if not auth.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role='parent',
                password_reset_required=False
            ):
                return {'success': False, 'message': 'Failed to create user account'}

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return {'success': False, 'message': 'Could not retrieve user ID'}

            user_id = row[0]
            cursor.execute(
                'INSERT INTO parent_user_mapping (user_id, parent_id) VALUES (?, ?)',
                (user_id, parent_id)
            )

            conn.commit()
            return {
                'success': True,
                'parent_id': parent_id,
                'username': username,
                'password': password
            }

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            return {'success': False, 'message': f'Database error: {e}'}
        finally:
            if conn:
                conn.close()

    @staticmethod
    def create_parent_account_interactive(auth):
        """Interactive function to create a parent account"""
        from education_system.university_system.modules.domain.academics.services.parent_portal.portal import ParentPortal
        print("\nCreate New Parent Account")
        print("========================")

        first_name = ""
        while not first_name:
            first_name = input("Enter parent's first name: ")
            if not first_name:
                print("Error. Please enter a name.")

        last_name = ""
        while not last_name:
            last_name = input("Enter parent's last name: ")
            if not last_name:
                print("Error. Please enter a name.")

        email = ""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            while not email:
                email = input("Enter parent's email address: ")
                if not email or '@' not in email:
                    print("Error. Please enter a valid email address.")
                    email = ""
                    continue

                cursor.execute('SELECT email FROM parent_accounts WHERE email = ?', (email,))
                if cursor.fetchone():
                    print("Error. This email is already registered.")
                    email = ""
        finally:
            if conn:
                conn.close()

        phone = input("Enter parent's phone number: ")
        address = input("Enter parent's address: ")

        result = ParentPortal.create_parent_user(auth, first_name, last_name, email, phone, address)

        if result['success']:
            print("\nParent account created successfully!")
            print(f"Parent ID: {result['parent_id']}")
            print(f"Username: {result['username']}")
            print(f"Password: {result['password']}")
            print("Please make note of these credentials for login.")

            link_now = input("\nDo you want to link a student to this parent now? (y/n): ")
            if link_now.lower() == 'y':
                portal = ParentPortal(auth)
                portal.link_student_to_parent(result['parent_id'])
        else:
            print(f"\nFailed to create parent account: {result['message']}")

    def create_parent_account(self):
        """Create a new parent account by direct database insertion"""
        from education_system.university_system.modules.domain.academics.services.parent_portal.portal import ParentPortal
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to create parent accounts.")
            return

        if not (self.auth.check_permission('create_parent') or self.auth.current_user.get('role', '') == 'admin'):
            print("You don't have permission to create parent accounts.")
            return

        first_name = last_name = email = phone = None

        while not first_name:
            first_name = input("Enter parent's first name: ")
            if not first_name:
                print("Error. Please enter a name.")

        while not last_name:
            last_name = input("Enter parent's last name: ")
            if not last_name:
                print("Error. Please enter a name.")

        email_conn = None
        try:
            email_conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            email_conn.execute("PRAGMA busy_timeout = 30000")
            email_cursor = email_conn.cursor()

            while not email:
                email = input("Enter parent's email address: ")
                if not email or '@' not in email:
                    print("Error. Please enter a valid email address.")
                    email = None
                    continue

                email_cursor.execute('SELECT email FROM parent_accounts WHERE email = ?', (email,))
                if email_cursor.fetchone():
                    print("Error. This email is already registered.")
                    email = None
        finally:
            if email_conn:
                email_conn.close()

        phone = input("Enter parent's phone number: ")
        address = input("Enter parent's address: ")

        try:
            backup_before_operation('create_parent')
        except Exception as e:
            print(f"Warning: Backup failed: {e}")

        result = ParentPortal.create_parent_user(self.auth, first_name, last_name, email, phone, address)

        if result['success']:
            print("\nParent account created successfully!")
            print(f"Parent ID: {result['parent_id']}")
            print(f"Username: {result['username']}")
            print(f"Password: {result['password']}")
            print("Please make note of these credentials for login.")

            link_now = input("\nDo you want to link a student to this parent now? (y/n): ")
            if link_now.lower() == 'y':
                self.link_student_to_parent(result['parent_id'])
        else:
            print(f"\nFailed to create parent account: {result['message']}")

    def get_parent_id_from_user(self, user_id):
        """Get the parent_id linked to a user account"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            cursor.execute('SELECT parent_id FROM parent_user_mapping WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()

            if not result:
                cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
                username_result = cursor.fetchone()

                if username_result:
                    cursor.execute('SELECT parent_id FROM parent_accounts WHERE email = ?', (username_result[0],))
                    result = cursor.fetchone()

            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Database error in get_parent_id_from_user: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def link_student_to_parent(self, parent_id=None):
        """Link a student to a parent account"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to link students to parents.")
            return

        if not (self.auth.check_permission('manage_parent_accounts') or self.auth.current_user.get('role', '') == 'admin'):
            print("You don't have permission to link students to parents.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            if not parent_id:
                parent_id = input("Enter parent ID: ")

                cursor.execute('SELECT parent_id FROM parent_accounts WHERE parent_id = ?', (parent_id,))
                if not cursor.fetchone():
                    print("Error. Parent ID not found.")
                    return

            student_id = input("Enter student ID to link to this parent: ")

            cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
            if not cursor.fetchone():
                print("Error. Student ID not found.")
                return

            cursor.execute(
                'SELECT id FROM parent_student_relationships WHERE parent_id = ? AND student_id = ?',
                (parent_id, student_id)
            )
            if cursor.fetchone():
                print("This student is already linked to this parent.")
                return

            print("\nRelationship types:")
            print("1. Mother")
            print("2. Father")
            print("3. Guardian")
            print("4. Other")

            relationship_choice = input("Select relationship type (1-4): ")

            if relationship_choice == '1':
                relationship_type = 'Mother'
            elif relationship_choice == '2':
                relationship_type = 'Father'
            elif relationship_choice == '3':
                relationship_type = 'Guardian'
            elif relationship_choice == '4':
                relationship_type = input("Specify relationship: ")
            else:
                print("Invalid choice. Using 'Guardian' as default.")
                relationship_type = 'Guardian'

            print("\nAccess levels:")
            print("1. Full access (grades, attendance, reports, messages)")
            print("2. Limited access (grades and attendance only)")
            print("3. Minimal access (attendance only)")

            access_choice = input("Select access level (1-3): ")

            if access_choice == '1':
                access_level = 'full'
            elif access_choice == '2':
                access_level = 'limited'
            elif access_choice == '3':
                access_level = 'minimal'
            else:
                print("Invalid choice. Using 'full' as default.")
                access_level = 'full'

            date_added = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                'INSERT INTO parent_student_relationships (parent_id, student_id, relationship_type, access_level, date_added) VALUES (?, ?, ?, ?, ?)',
                (parent_id, student_id, relationship_type, access_level, date_added)
            )

            conn.commit()
            print(f"Student {student_id} successfully linked to parent {parent_id} as {relationship_type}.")

            emergency = input("Set this parent as an emergency contact for this student? (y/n): ")
            if emergency.lower() == 'y':
                cursor.execute(
                    'UPDATE parent_accounts SET emergency_contact = 1 WHERE parent_id = ?',
                    (parent_id,)
                )
                conn.commit()
                print("Parent set as emergency contact.")

        except sqlite3.Error as e:
            print(f"Error linking student to parent: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def view_children(self):
        """View all children linked to the logged-in parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view your children's records.")
            return []

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return []

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])

            if not parent_id:
                print("No parent ID associated with your account.")
                return []

            cursor.execute('''
            SELECT s.student_id, s.first_name, s.middle_name, s.last_name, s.course, psr.relationship_type, psr.access_level
            FROM students s
            JOIN parent_student_relationships psr ON s.student_id = psr.student_id
            WHERE psr.parent_id = ?
            ORDER BY s.last_name, s.first_name
            ''', (parent_id,))

            children = cursor.fetchall()
            return children

        except sqlite3.Error as e:
            print(f"Database error in view_children: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def update_contact_info(self):
        """Update parent contact information"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to update contact information.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('update_contact_info'):
            print("You don't have permission to update contact information.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return

            cursor.execute('''
            SELECT first_name, last_name, email, phone, address
            FROM parent_accounts
            WHERE parent_id = ?
            ''', (parent_id,))

            info = cursor.fetchone()

            if not info:
                print("Error: Parent account not found.")
                return

            print("\nCurrent Contact Information:")
            print(f"1. First Name: {info[0]}")
            print(f"2. Last Name: {info[1]}")
            print(f"3. Email: {info[2]}")
            print(f"4. Phone: {info[3] or 'Not set'}")
            print(f"5. Address: {info[4] or 'Not set'}")
            print("6. Save and Return")

            from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

            while True:
                choice = input("\nSelect information to update (1-5) or 6 to save: ")

                if choice == '6':
                    break

                if choice in ['1', '2', '3', '4', '5']:
                    columns = ['first_name', 'last_name', 'email', 'phone', 'address']
                    prompts = [
                        "Enter new first name: ",
                        "Enter new last name: ",
                        "Enter new email: ",
                        "Enter new phone number: ",
                        "Enter new address: "
                    ]

                    column = columns[int(choice) - 1]
                    prompt = prompts[int(choice) - 1]

                    new_value = input(prompt)

                    if column == 'email' and '@' not in new_value:
                        print("Invalid email address.")
                        continue

                    if column in ['first_name', 'last_name'] and not new_value:
                        print(f"{column.replace('_', ' ').title()} cannot be empty.")
                        continue

                    safe_column = validate_identifier(column, "column")
                    cursor.execute('''
                    UPDATE parent_accounts
                    SET [''' + safe_column + '''] = ?
                    WHERE parent_id = ?
                    ''', (new_value, parent_id))

                    if column == 'email':
                        cursor.execute('SELECT user_id FROM parent_user_mapping WHERE parent_id = ?', (parent_id,))
                        user_id_result = cursor.fetchone()

                        if user_id_result:
                            cursor.execute('''
                            UPDATE users
                            SET email = ?
                            WHERE id = ?
                            ''', (new_value, user_id_result[0]))

                    conn.commit()

                    cursor.execute('''
                    SELECT first_name, last_name, email, phone, address
                    FROM parent_accounts
                    WHERE parent_id = ?
                    ''', (parent_id,))

                    info = cursor.fetchone()

                    print("\nUpdated Contact Information:")
                    print(f"1. First Name: {info[0]}")
                    print(f"2. Last Name: {info[1]}")
                    print(f"3. Email: {info[2]}")
                    print(f"4. Phone: {info[3] or 'Not set'}")
                    print(f"5. Address: {info[4] or 'Not set'}")
                    print("6. Save and Return")
                else:
                    print("Invalid choice.")

            print("Contact information updated successfully.")

        except sqlite3.Error as e:
            print(f"Database error updating contact info: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def emergency_contact_update(self):
        """Quick emergency contact updates"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to update emergency contacts.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('emergency_contact_update'):
            print("You don't have permission to update emergency contacts.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return

            # Get current contact info
            cursor.execute('''
            SELECT first_name, last_name, phone, email, address
            FROM parent_accounts
            WHERE parent_id = ?
            ''', (parent_id,))

            current_info = cursor.fetchone()

            if not current_info:
                print("Error: Parent account not found.")
                return

            print("\nEmergency Contact Update:")
            print("Current information:")
            print(f"Name: {current_info[0]} {current_info[1]}")
            print(f"Phone: {current_info[2] or 'Not set'}")
            print(f"Email: {current_info[3]}")
            print(f"Address: {current_info[4] or 'Not set'}")

            print("\nWhat would you like to update?")
            print("1. Phone number")
            print("2. Email address")
            print("3. Address")
            print("4. All contact details")

            choice = input("Enter your choice (1-4): ")

            if choice == '1':
                new_phone = input("Enter new phone number: ")
                cursor.execute('UPDATE parent_accounts SET phone = ? WHERE parent_id = ?',
                             (new_phone, parent_id))
                print("Phone number updated successfully.")

            elif choice == '2':
                new_email = input("Enter new email address: ")
                if '@' not in new_email:
                    print("Invalid email address.")
                    return

                cursor.execute('UPDATE parent_accounts SET email = ? WHERE parent_id = ?',
                             (new_email, parent_id))

                # Update in users table too
                cursor.execute('SELECT user_id FROM parent_user_mapping WHERE parent_id = ?', (parent_id,))
                user_id_result = cursor.fetchone()
                if user_id_result:
                    cursor.execute('UPDATE users SET email = ? WHERE id = ?',
                                 (new_email, user_id_result[0]))

                print("Email address updated successfully.")

            elif choice == '3':
                new_address = input("Enter new address: ")
                cursor.execute('UPDATE parent_accounts SET address = ? WHERE parent_id = ?',
                             (new_address, parent_id))
                print("Address updated successfully.")

            elif choice == '4':
                new_phone = input("Enter new phone number: ")
                new_email = input("Enter new email address: ")
                new_address = input("Enter new address: ")

                if '@' not in new_email:
                    print("Invalid email address.")
                    return

                cursor.execute('''
                UPDATE parent_accounts
                SET phone = ?, email = ?, address = ?
                WHERE parent_id = ?
                ''', (new_phone, new_email, new_address, parent_id))

                # Update email in users table
                cursor.execute('SELECT user_id FROM parent_user_mapping WHERE parent_id = ?', (parent_id,))
                user_id_result = cursor.fetchone()
                if user_id_result:
                    cursor.execute('UPDATE users SET email = ? WHERE id = ?',
                                 (new_email, user_id_result[0]))

                print("All contact details updated successfully.")

            else:
                print("Invalid choice.")
                return

            conn.commit()

            # Log the activity
            cursor.execute('''
            INSERT INTO parent_activity_log
            (parent_id, action, details, timestamp)
            VALUES (?, 'emergency_contact_update', 'Emergency contact information updated', ?)
            ''', (parent_id, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()

        except sqlite3.Error as e:
            print(f"Database error updating emergency contact: {e}")
        finally:
            if conn:
                conn.close()

    def update_profile_photo(self):
        """Update parent profile photo"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to update profile photo.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return

            photo_path = input("Enter photo file path (or 'remove' to remove current photo): ")

            if photo_path.lower() == 'remove':
                photo_path = None
                print("Profile photo removed.")
            else:
                print(f"Profile photo set to: {photo_path}")
                print("Note: In a real implementation, the photo would be uploaded and validated.")

            cursor.execute('''
            UPDATE parent_accounts
            SET profile_photo = ?
            WHERE parent_id = ?
            ''', (photo_path, parent_id))

            conn.commit()

            # Log the activity
            self.log_activity("profile_photo_updated", f"Profile photo {'removed' if not photo_path else 'updated'}")

        except sqlite3.Error as e:
            print(f"Database error updating profile photo: {e}")
        finally:
            if conn:
                conn.close()

    def enable_two_factor_auth(self):
        """Enable two-factor authentication for parent account"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to enable two-factor authentication.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return

            # Check if 2FA is already enabled
            cursor.execute('SELECT two_factor_enabled FROM parent_accounts WHERE parent_id = ?', (parent_id,))
            result = cursor.fetchone()

            if result and result[0]:
                print("Two-factor authentication is already enabled.")
                return

            # Generate a secret key (in real implementation, use proper TOTP library)
            import secrets
            secret = secrets.token_hex(16)

            # Enable 2FA
            cursor.execute('''
            UPDATE parent_accounts
            SET two_factor_enabled = 1, two_factor_secret = ?
            WHERE parent_id = ?
            ''', (secret, parent_id))

            conn.commit()

            print("Two-factor authentication has been enabled.")
            print(f"Secret key: {secret}")
            print("Please save this secret key in your authenticator app.")

            # Log the activity
            self.log_activity("two_factor_enabled", "Two-factor authentication enabled")

        except sqlite3.Error as e:
            print(f"Database error enabling 2FA: {e}")
        finally:
            if conn:
                conn.close()
