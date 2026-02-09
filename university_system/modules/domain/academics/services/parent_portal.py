from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
import datetime
import os
import random
import json
import hashlib
import qrcode
import io
import base64
from university_system.infrastructure.email import send_email
from university_system.infrastructure.database.data_backup import backup_before_operation
from university_system.infrastructure.security.password_generator import generate_temp_password

class ParentPortal:
    def __init__(self, auth):
        self.auth = auth
        
    @staticmethod
    def initialize_parent_portal():
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")  # Set a longer timeout
            cursor = conn.cursor()
            
            # Original tables
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT UNIQUE,
                first_name TEXT,
                last_name TEXT,
                email TEXT UNIQUE,
                phone TEXT,
                address TEXT,
                emergency_contact BOOLEAN DEFAULT 0,
                registration_date TEXT,
                two_factor_enabled BOOLEAN DEFAULT 0,
                two_factor_secret TEXT,
                profile_photo TEXT
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_student_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                student_id TEXT,
                relationship_type TEXT,
                access_level TEXT DEFAULT 'full',
                date_added TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_user_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                parent_id TEXT UNIQUE,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                student_id TEXT,
                notification_type TEXT,
                notification_content TEXT,
                created_date TEXT,
                read_status BOOLEAN DEFAULT 0,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT UNIQUE,
                email_notifications BOOLEAN DEFAULT 1,
                sms_notifications BOOLEAN DEFAULT 0,
                grade_alerts BOOLEAN DEFAULT 1,
                attendance_alerts BOOLEAN DEFAULT 1,
                behavior_alerts BOOLEAN DEFAULT 1,
                assignment_alerts BOOLEAN DEFAULT 0,
                weekly_summary BOOLEAN DEFAULT 1,
                notification_timing TEXT DEFAULT '08:00',
                quiet_hours_start TEXT DEFAULT '20:00',
                quiet_hours_end TEXT DEFAULT '07:00',
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                teacher_id INTEGER,
                student_id TEXT,
                message_content TEXT,
                created_date TEXT,
                is_read BOOLEAN DEFAULT 0,
                is_from_parent BOOLEAN DEFAULT 1,
                message_type TEXT DEFAULT 'individual',
                group_id TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (teacher_id) REFERENCES users (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS teacher_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                teacher_id INTEGER,
                module_code TEXT,
                report_type TEXT,
                report_content TEXT,
                created_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (teacher_id) REFERENCES users (id),
                FOREIGN KEY (module_code) REFERENCES modules (module_code)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_absences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                absence_date TEXT,
                return_date TEXT,
                reason TEXT,
                reported_by TEXT,
                reported_date TEXT,
                notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS school_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                event_description TEXT,
                event_date TEXT,
                start_time TEXT,
                end_time TEXT,
                location TEXT,
                event_type TEXT,
                audience TEXT
            )
            ''')
            
            # NEW TABLES FOR ENHANCED FEATURES
            
            # Financial Management
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_fees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                fee_type TEXT,
                description TEXT,
                amount DECIMAL(10,2),
                due_date TEXT,
                paid_date TEXT,
                payment_status TEXT DEFAULT 'pending',
                payment_method TEXT,
                transaction_id TEXT,
                created_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS meal_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE,
                balance DECIMAL(10,2) DEFAULT 0.00,
                low_balance_threshold DECIMAL(10,2) DEFAULT 10.00,
                auto_topup_enabled BOOLEAN DEFAULT 0,
                auto_topup_amount DECIMAL(10,2) DEFAULT 20.00,
                last_updated TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS meal_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                transaction_type TEXT,
                amount DECIMAL(10,2),
                description TEXT,
                transaction_date TEXT,
                balance_after DECIMAL(10,2),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS fundraising_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_name TEXT,
                description TEXT,
                target_amount DECIMAL(10,2),
                current_amount DECIMAL(10,2) DEFAULT 0.00,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'active'
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS fundraising_donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                parent_id TEXT,
                student_id TEXT,
                amount DECIMAL(10,2),
                donation_date TEXT,
                anonymous BOOLEAN DEFAULT 0,
                FOREIGN KEY (campaign_id) REFERENCES fundraising_campaigns (id),
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            # Enhanced Student Monitoring
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_behavior (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                incident_date TEXT,
                behavior_type TEXT,
                severity TEXT,
                description TEXT,
                action_taken TEXT,
                reported_by TEXT,
                follow_up_required BOOLEAN DEFAULT 0,
                resolved BOOLEAN DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_medical_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                condition_type TEXT,
                description TEXT,
                medication_name TEXT,
                dosage TEXT,
                administration_time TEXT,
                emergency_contact TEXT,
                doctor_contact TEXT,
                expiry_date TEXT,
                notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS transportation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                route_name TEXT,
                bus_number TEXT,
                pickup_time TEXT,
                dropoff_time TEXT,
                pickup_location TEXT,
                dropoff_location TEXT,
                driver_name TEXT,
                driver_phone TEXT,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS library_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                book_title TEXT,
                author TEXT,
                isbn TEXT,
                checkout_date TEXT,
                due_date TEXT,
                return_date TEXT,
                fine_amount DECIMAL(10,2) DEFAULT 0.00,
                status TEXT DEFAULT 'checked_out',
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS extracurricular_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_name TEXT,
                description TEXT,
                supervisor TEXT,
                meeting_schedule TEXT,
                location TEXT,
                max_participants INTEGER,
                fee DECIMAL(10,2) DEFAULT 0.00,
                status TEXT DEFAULT 'active'
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                activity_id INTEGER,
                enrollment_date TEXT,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (activity_id) REFERENCES extracurricular_activities (id)
            )
            ''')
            
            # Academic Enhancements
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS homework_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                module_code TEXT,
                assignment_title TEXT,
                description TEXT,
                assigned_date TEXT,
                due_date TEXT,
                completion_status TEXT DEFAULT 'pending',
                submitted_date TEXT,
                grade TEXT,
                teacher_comments TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (module_code) REFERENCES modules (module_code)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_teacher_meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                teacher_id INTEGER,
                student_id TEXT,
                meeting_date TEXT,
                start_time TEXT,
                end_time TEXT,
                location TEXT,
                meeting_type TEXT,
                status TEXT DEFAULT 'scheduled',
                agenda TEXT,
                notes TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (teacher_id) REFERENCES users (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                parent_id TEXT,
                goal_title TEXT,
                description TEXT,
                target_grade TEXT,
                target_date TEXT,
                current_progress TEXT,
                status TEXT DEFAULT 'active',
                created_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')
            
            # Communication Features
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS school_announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                priority TEXT DEFAULT 'normal',
                category TEXT,
                audience TEXT,
                created_by INTEGER,
                created_date TEXT,
                expiry_date TEXT,
                requires_acknowledgment BOOLEAN DEFAULT 0,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcement_reads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                announcement_id INTEGER,
                parent_id TEXT,
                read_date TEXT,
                acknowledged BOOLEAN DEFAULT 0,
                FOREIGN KEY (announcement_id) REFERENCES school_announcements (id),
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS teacher_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER,
                day_of_week TEXT,
                start_time TEXT,
                end_time TEXT,
                meeting_type TEXT,
                location TEXT,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (teacher_id) REFERENCES users (id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS emergency_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_title TEXT,
                alert_message TEXT,
                alert_type TEXT,
                created_date TEXT,
                created_by INTEGER,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')
            
            # Administrative Tools
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                student_id TEXT,
                document_type TEXT,
                document_name TEXT,
                file_path TEXT,
                upload_date TEXT,
                status TEXT DEFAULT 'pending',
                expiry_date TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pickup_authorizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                authorized_person_name TEXT,
                relationship TEXT,
                phone_number TEXT,
                id_number TEXT,
                photo_path TEXT,
                valid_from TEXT,
                valid_until TEXT,
                active BOOLEAN DEFAULT 1,
                created_by TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS photo_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                permission_type TEXT,
                consent_given BOOLEAN DEFAULT 0,
                conditions TEXT,
                valid_from TEXT,
                valid_until TEXT,
                parent_signature TEXT,
                date_signed TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')
            
            # Security & Analytics
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                action TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS grade_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                module_code TEXT,
                assessment_date TEXT,
                grade_value DECIMAL(5,2),
                class_average DECIMAL(5,2),
                percentile_rank INTEGER,
                trend_direction TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (module_code) REFERENCES modules (module_code)
            )
            ''')
            
            conn.commit()
            print("Enhanced parent portal database initialized successfully!")
            return True
        except sqlite3.Error as e:
            print(f"Error initializing enhanced parent portal database: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def integrate_parent_portal_with_main():
        return ParentPortal.initialize_parent_portal()

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

    # ORIGINAL METHODS (keeping all existing functionality)
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
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to create parent accounts.")
            return
        
        if not (self.auth.check_permission('create_parent') or self.auth.current_user['role'] == 'admin'):
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
        
        if not (self.auth.check_permission('manage_parent_accounts') or self.auth.current_user['role'] == 'admin'):
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
        
        if self.auth.current_user['role'] != 'parent':
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
    
    def view_child_grades(self):
        """View grades for a child of the logged-in parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view your child's grades.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_child_grades'):
            print("You don't have permission to view grades.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nYour children:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")
        
        choice = input("Enter the number of the child whose grades you want to view: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            
            if selected_child[6] == 'minimal':
                print("You have minimal access to this child's records and cannot view grades.")
                return
            
            student_id = selected_child[0]
            
            print(f"\nViewing grades for {selected_child[1]} {selected_child[3]}")
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_grades'")
                
                if not cursor.fetchone():
                    print("Grade tracking is not yet set up in the system.")
                    return
                
                cursor.execute('''
                SELECT m.module_code, m.module_name, g.assessment_name, g.grade, g.grade_date
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                LEFT JOIN student_grades g ON sm.student_id = g.student_id AND sm.module_code = g.module_code
                WHERE sm.student_id = ?
                ORDER BY m.module_code, g.assessment_name
                ''', (student_id,))
                
                grades = cursor.fetchall()
                
                if not grades:
                    print("No grades recorded for this student.")
                    return
                
                current_module = None
                for grade in grades:
                    module_code, module_name, assessment_name, grade_value, grade_date = grade
                    
                    if module_code != current_module:
                        print(f"\n{module_code}: {module_name}")
                        current_module = module_code
                    
                    if assessment_name:
                        print(f"  - {assessment_name}: {grade_value} (Recorded: {grade_date})")
                    else:
                        print("  - No assessments recorded yet")
                        
            except sqlite3.Error as e:
                print(f"Database error viewing grades: {e}")
            finally:
                if conn:
                    conn.close()
                
        except (ValueError, IndexError):
            print("Invalid choice.")
    
    def view_child_attendance(self):
        """View attendance records for a child of the logged-in parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view your child's attendance.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_child_attendance'):
            print("You don't have permission to view attendance records.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nYour children:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")
        
        choice = input("Enter the number of the child whose attendance you want to view: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            print(f"\nViewing attendance for {selected_child[1]} {selected_child[3]}")
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
                
                if not cursor.fetchone():
                    print("Attendance tracking is not yet set up in the system.")
                    return
                
                cursor.execute('''
                SELECT m.module_code, m.module_name, 
                       COUNT(a.id) as total_sessions,
                       SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as attended_sessions
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                LEFT JOIN attendance a ON sm.student_id = a.student_id AND sm.module_code = a.module_code
                WHERE sm.student_id = ?
                GROUP BY m.module_code, m.module_name
                ORDER BY m.module_code
                ''', (student_id,))
                
                module_attendance = cursor.fetchall()
                
                if not module_attendance or all(row[2] == 0 for row in module_attendance):
                    print("No attendance records found for this student.")
                else:
                    total_sessions = sum(row[2] for row in module_attendance)
                    total_attended = sum(row[3] for row in module_attendance)
                    
                    if total_sessions > 0:
                        overall_percentage = (total_attended / total_sessions) * 100
                        print(f"\nOverall Attendance: {overall_percentage:.1f}% ({total_attended}/{total_sessions} sessions)")
                    
                    print("\nAttendance by Module:")
                    for module in module_attendance:
                        module_code, module_name, total_sessions, attended_sessions = module
                        
                        if total_sessions > 0:
                            percentage = (attended_sessions / total_sessions) * 100
                            print(f"{module_code}: {module_name}")
                            print(f"  {percentage:.1f}% ({attended_sessions}/{total_sessions} sessions)")
                
                cursor.execute('''
                SELECT a.date, m.module_code, m.module_name, a.status, a.reason
                FROM attendance a
                JOIN modules m ON a.module_code = m.module_code
                WHERE a.student_id = ? AND a.status != 'present'
                ORDER BY a.date DESC
                LIMIT 10
                ''', (student_id,))
                
                recent_absences = cursor.fetchall()
                
                if recent_absences:
                    print("\nRecent Absences:")
                    for absence in recent_absences:
                        date, module_code, module_name, status, reason = absence
                        print(f"{date} - {module_code}: {module_name} - {status.upper()}")
                        if reason:
                            print(f"  Reason: {reason}")
                            
            except sqlite3.Error as e:
                print(f"Database error viewing attendance: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")
    
    def view_teacher_reports(self):
        """View teacher reports for a child of the logged-in parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view teacher reports.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_teacher_reports'):
            print("You don't have permission to view teacher reports.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nYour children:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")
        
        choice = input("Enter the number of the child whose reports you want to view: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            
            if selected_child[6] == 'minimal' or selected_child[6] == 'limited':
                print("You don't have sufficient access to view teacher reports for this child.")
                return
            
            student_id = selected_child[0]
            
            print(f"\nViewing teacher reports for {selected_child[1]} {selected_child[3]}")
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teacher_reports'")
                
                if not cursor.fetchone():
                    print("Teacher reporting is not yet set up in the system.")
                    return
                
                cursor.execute('''
                SELECT r.id, r.module_code, m.module_name, r.report_type, r.created_date, u.username as teacher_name
                FROM teacher_reports r
                JOIN modules m ON r.module_code = m.module_code
                LEFT JOIN users u ON r.teacher_id = u.id
                WHERE r.student_id = ?
                ORDER BY r.created_date DESC
                ''', (student_id,))
                
                reports = cursor.fetchall()
                
                if not reports:
                    print("No teacher reports found for this student.")
                    return
                
                print("\nAvailable Reports:")
                for i, report in enumerate(reports):
                    report_id, module_code, module_name, report_type, date, teacher = report
                    print(f"{i+1}. {date} - {module_code}: {report_type} by {teacher or 'Unknown Teacher'}")
                
                report_choice = input("\nEnter the number of the report you want to view (or 0 to go back): ")
                
                if report_choice == '0':
                    return
                
                try:
                    report_index = int(report_choice) - 1
                    if report_index < 0 or report_index >= len(reports):
                        raise ValueError
                    
                    selected_report = reports[report_index]
                    report_id = selected_report[0]
                    
                    cursor.execute('SELECT report_content FROM teacher_reports WHERE id = ?', (report_id,))
                    report_content = cursor.fetchone()[0]
                    
                    print("\n" + "=" * 50)
                    print(f"REPORT: {selected_report[3]}")
                    print(f"Module: {selected_report[1]} - {selected_report[2]}")
                    print(f"Date: {selected_report[4]}")
                    print(f"Teacher: {selected_report[5] or 'Unknown'}")
                    print("=" * 50)
                    print(report_content)
                    print("=" * 50)
                    
                except (ValueError, IndexError):
                    print("Invalid report choice.")
                
            except sqlite3.Error as e:
                print(f"Database error viewing teacher reports: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")
    
    def send_message_to_teacher(self):
        """Send a message to a teacher from a parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to send messages.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('message_teachers'):
            print("You don't have permission to message teachers.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect the child related to this message:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            
            if selected_child[6] == 'minimal':
                print("You have minimal access and cannot send messages regarding this child.")
                return
            
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS parent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT,
                    teacher_id INTEGER,
                    student_id TEXT,
                    message_content TEXT,
                    created_date TEXT,
                    is_read BOOLEAN DEFAULT 0,
                    is_from_parent BOOLEAN DEFAULT 1,
                    message_type TEXT DEFAULT 'individual',
                    group_id TEXT,
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                    FOREIGN KEY (teacher_id) REFERENCES users (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
                ''')
                
                cursor.execute('''
                SELECT DISTINCT t.id, t.username, m.module_code, m.module_name
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                JOIN module_teachers mt ON m.module_code = mt.module_code
                JOIN users t ON mt.teacher_id = t.id
                WHERE sm.student_id = ? AND t.role = 'teacher'
                ORDER BY m.module_code
                ''', (student_id,))
                
                teachers = cursor.fetchall()
                
                if not teachers:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='module_teachers'")
                    if not cursor.fetchone():
                        print("Module-teacher assignments not yet set up.")
                        
                    cursor.execute('''
                    SELECT id, username FROM users WHERE role = 'teacher' ORDER BY username
                    ''')
                    
                    temp_teachers = cursor.fetchall()
                    teachers = [(t[0], t[1], 'N/A', 'N/A') for t in temp_teachers]
                    
                    if not teachers:
                        print("No teachers found in the system.")
                        return
                
                print("\nSelect teacher to message:")
                for i, teacher in enumerate(teachers):
                    teacher_id, username, module_code, module_name = teacher
                    module_info = f" ({module_code}: {module_name})" if module_code != 'N/A' else ""
                    print(f"{i+1}. {username}{module_info}")
                
                teacher_choice = input("Enter the number of the teacher: ")
                try:
                    teacher_index = int(teacher_choice) - 1
                    if teacher_index < 0 or teacher_index >= len(teachers):
                        raise ValueError
                    
                    selected_teacher = teachers[teacher_index]
                    teacher_id = selected_teacher[0]
                    
                    print("\nCompose your message:")
                    message_content = input("Message: ")
                    
                    if not message_content:
                        print("Message cannot be empty.")
                        return
                    
                    parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                    if not parent_id:
                        print("Error retrieving parent ID.")
                        return
                    
                    created_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    cursor.execute(
                        'INSERT INTO parent_messages (parent_id, teacher_id, student_id, message_content, created_date, is_read, is_from_parent) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (parent_id, teacher_id, student_id, message_content, created_date, 0, 1)
                    )
                    
                    conn.commit()
                    print("Message sent successfully.")
                    
                    cursor.execute('SELECT email FROM users WHERE id = ?', (teacher_id,))
                    teacher_email = cursor.fetchone()
                    
                    if teacher_email and teacher_email[0]:
                        try:
                            send_email(
                                teacher_email[0],
                                "New parent message",
                                f"You have received a new message from a parent regarding student {student_id}."
                            )
                        except Exception as e:
                            print(f"Note: Email notification could not be sent: {e}")
                    
                except (ValueError, IndexError):
                    print("Invalid teacher choice.")
                
            except sqlite3.Error as e:
                print(f"Database error sending message: {e}")
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")
    
    def view_messages(self):
        """View messages between parent and teachers"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view messages.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parent_messages'")
            if not cursor.fetchone():
                print("Messaging system is not yet set up.")
                return
            
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return
            
            cursor.execute('''
            SELECT DISTINCT t.id, t.username, s.student_id, s.first_name, s.last_name
            FROM parent_messages pm
            JOIN users t ON pm.teacher_id = t.id
            JOIN students s ON pm.student_id = s.student_id
            WHERE pm.parent_id = ?
            ORDER BY t.username
            ''', (parent_id,))
            
            conversations = cursor.fetchall()
            
            if not conversations:
                print("You have no message history.")
                return
            
            print("\nSelect conversation to view:")
            for i, convo in enumerate(conversations):
                teacher_id, teacher_name, student_id, first_name, last_name = convo
                print(f"{i+1}. With {teacher_name} regarding {first_name} {last_name}")
            
            print(f"{len(conversations)+1}. Back to Parent Menu")
            
            choice = input("Enter your choice: ")
            try:
                index = int(choice) - 1
                if index == len(conversations):
                    return
                
                if index < 0 or index >= len(conversations):
                    raise ValueError
                
                selected_convo = conversations[index]
                teacher_id = selected_convo[0]
                student_id = selected_convo[2]
                
                cursor.execute('''
                SELECT message_content, created_date, is_from_parent
                FROM parent_messages
                WHERE parent_id = ? AND teacher_id = ? AND student_id = ?
                ORDER BY created_date
                ''', (parent_id, teacher_id, student_id))
                
                messages = cursor.fetchall()
                
                print("\n" + "=" * 50)
                print(f"Conversation with {selected_convo[1]} about {selected_convo[3]} {selected_convo[4]}")
                print("=" * 50)
                
                for message in messages:
                    content, date, is_from_parent = message
                    sender = "You" if is_from_parent else selected_convo[1]
                    print(f"[{date}] {sender}: {content}")
                
                print("=" * 50)
                
                cursor.execute('''
                UPDATE parent_messages
                SET is_read = 1
                WHERE parent_id = ? AND teacher_id = ? AND student_id = ? AND is_from_parent = 0
                ''', (parent_id, teacher_id, student_id))
                
                conn.commit()
                
                reply = input("Would you like to reply? (y/n): ")
                if reply.lower() == 'y':
                    message_content = input("Your message: ")
                    
                    if message_content:
                        created_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        cursor.execute(
                            'INSERT INTO parent_messages (parent_id, teacher_id, student_id, message_content, created_date, is_read, is_from_parent) VALUES (?, ?, ?, ?, ?, ?, ?)',
                            (parent_id, teacher_id, student_id, message_content, created_date, 0, 1)
                        )
                        
                        conn.commit()
                        print("Reply sent successfully.")
                
            except (ValueError, IndexError):
                print("Invalid choice.")
            
        except sqlite3.Error as e:
            print(f"Database error viewing messages: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    
    def report_absence(self):
        """Report a student absence"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to report an absence.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('report_absence'):
            print("You don't have permission to report absences.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect the child to report absent:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_absences'")
                if not cursor.fetchone():
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS student_absences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        absence_date TEXT,
                        return_date TEXT,
                        reason TEXT,
                        reported_by TEXT,
                        reported_date TEXT,
                        notes TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
                    ''')
                
                print("\nReport Absence:")
                
                while True:
                    absence_date_str = input("Absence date (YYYY-MM-DD) or 'today': ")
                    if absence_date_str.lower() == 'today':
                        absence_date = datetime.datetime.now().strftime('%Y-%m-%d')
                        break
                    try:
                        absence_date = datetime.datetime.strptime(absence_date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                        break
                    except ValueError:
                        print("Invalid date format. Please use YYYY-MM-DD.")
                
                while True:
                    return_date_str = input("Expected return date (YYYY-MM-DD) or press Enter if unknown: ")
                    if not return_date_str:
                        return_date = None
                        break
                    try:
                        return_date = datetime.datetime.strptime(return_date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                        break
                    except ValueError:
                        print("Invalid date format. Please use YYYY-MM-DD.")
                
                reason = input("Reason for absence: ")
                if not reason:
                    print("A reason must be provided.")
                    return
                
                notes = input("Additional notes (optional): ")
                
                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return
                
                reported_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute(
                    'INSERT INTO student_absences (student_id, absence_date, return_date, reason, reported_by, reported_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (student_id, absence_date, return_date, reason, f"parent:{parent_id}", reported_date, notes)
                )
                
                conn.commit()
                print("Absence reported successfully.")
                
                notify = input("Would you like to notify the student's teachers? (y/n): ")
                if notify.lower() == 'y':
                    try:
                        cursor.execute('''
                        CREATE TABLE IF NOT EXISTS parent_messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            parent_id TEXT,
                            teacher_id INTEGER,
                            student_id TEXT,
                            message_content TEXT,
                            created_date TEXT,
                            is_read BOOLEAN DEFAULT 0,
                            is_from_parent BOOLEAN DEFAULT 1,
                            message_type TEXT DEFAULT 'individual',
                            group_id TEXT,
                            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                            FOREIGN KEY (teacher_id) REFERENCES users (id),
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
                        ''')
                        
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='module_teachers'")
                        if not cursor.fetchone():
                            print("Module-teacher assignments not yet set up. Cannot notify teachers.")
                            return
                        
                        cursor.execute('''
                        SELECT DISTINCT t.id, t.username, t.email
                        FROM student_modules sm
                        JOIN module_teachers mt ON sm.module_code = mt.module_code
                        JOIN users t ON mt.teacher_id = t.id
                        WHERE sm.student_id = ? AND t.role = 'teacher'
                        ''', (student_id,))
                        
                        teachers = cursor.fetchall()
                        
                        if teachers:
                            message = f"Student {selected_child[1]} {selected_child[3]} (ID: {student_id}) will be absent on {absence_date} due to {reason}."
                            if return_date:
                                message += f" Expected return date: {return_date}."
                            if notes:
                                message += f" Additional notes: {notes}"
                            
                            for teacher in teachers:
                                try:
                                    cursor.execute(
                                        'INSERT INTO parent_messages (parent_id, teacher_id, student_id, message_content, created_date, is_read, is_from_parent) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (parent_id, teacher[0], student_id, message, reported_date, 0, 1)
                                    )
                                    
                                    if teacher[2]:
                                        try:
                                            send_email(
                                                teacher[2],
                                                f"Absence Notification: {selected_child[1]} {selected_child[3]}",
                                                message
                                            )
                                        except Exception as e:
                                            print(f"Could not send email to {teacher[1]}: {e}")
                                except Exception as e:
                                    print(f"Error notifying teacher {teacher[1]}: {e}")
                            
                            conn.commit()
                            print("Teachers have been notified.")
                        else:
                            print("No teachers found to notify.")
                    except sqlite3.Error as e:
                        print(f"Error notifying teachers: {e}")
                        conn.rollback()
                
            except sqlite3.Error as e:
                print(f"Database error reporting absence: {e}")
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")
    
    def update_notification_preferences(self):
        """Update parent notification preferences"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to update notification preferences.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('set_notification_preferences'):
            print("You don't have permission to set notification preferences.")
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
            SELECT email_notifications, sms_notifications, grade_alerts, attendance_alerts, 
                   behavior_alerts, assignment_alerts, weekly_summary
            FROM parent_preferences
            WHERE parent_id = ?
            ''', (parent_id,))
            
            prefs = cursor.fetchone()
            
            if not prefs:
                cursor.execute(
                    'INSERT INTO parent_preferences (parent_id) VALUES (?)',
                    (parent_id,)
                )
                conn.commit()
                
                cursor.execute('''
                SELECT email_notifications, sms_notifications, grade_alerts, attendance_alerts, 
                       behavior_alerts, assignment_alerts, weekly_summary
                FROM parent_preferences
                WHERE parent_id = ?
                ''', (parent_id,))
                
                prefs = cursor.fetchone()
            
            print("\nCurrent Notification Preferences:")
            print(f"1. Email Notifications: {'Enabled' if prefs[0] else 'Disabled'}")
            print(f"2. SMS Notifications: {'Enabled' if prefs[1] else 'Disabled'}")
            print(f"3. Grade Alerts: {'Enabled' if prefs[2] else 'Disabled'}")
            print(f"4. Attendance Alerts: {'Enabled' if prefs[3] else 'Disabled'}")
            print(f"5. Behavior Alerts: {'Enabled' if prefs[4] else 'Disabled'}")
            print(f"6. Assignment Alerts: {'Enabled' if prefs[5] else 'Disabled'}")
            print(f"7. Weekly Summary: {'Enabled' if prefs[6] else 'Disabled'}")
            print("8. Save and Return")
            
            while True:
                choice = input("\nSelect preference to toggle (1-7) or 8 to save: ")
                
                if choice == '8':
                    break
                    
                if choice in ['1', '2', '3', '4', '5', '6', '7']:
                    columns = [
                        'email_notifications', 'sms_notifications', 'grade_alerts', 
                        'attendance_alerts', 'behavior_alerts', 'assignment_alerts', 'weekly_summary'
                    ]
                    column = columns[int(choice) - 1]
                    
                    cursor.execute(f'''
                    UPDATE parent_preferences
                    SET {column} = NOT {column}
                    WHERE parent_id = ?
                    ''', (parent_id,))
                    
                    conn.commit()
                    
                    cursor.execute('''
                    SELECT email_notifications, sms_notifications, grade_alerts, attendance_alerts, 
                           behavior_alerts, assignment_alerts, weekly_summary
                    FROM parent_preferences
                    WHERE parent_id = ?
                    ''', (parent_id,))
                    
                    prefs = cursor.fetchone()
                    
                    print("\nUpdated Notification Preferences:")
                    print(f"1. Email Notifications: {'Enabled' if prefs[0] else 'Disabled'}")
                    print(f"2. SMS Notifications: {'Enabled' if prefs[1] else 'Disabled'}")
                    print(f"3. Grade Alerts: {'Enabled' if prefs[2] else 'Disabled'}")
                    print(f"4. Attendance Alerts: {'Enabled' if prefs[3] else 'Disabled'}")
                    print(f"5. Behavior Alerts: {'Enabled' if prefs[4] else 'Disabled'}")
                    print(f"6. Assignment Alerts: {'Enabled' if prefs[5] else 'Disabled'}")
                    print(f"7. Weekly Summary: {'Enabled' if prefs[6] else 'Disabled'}")
                    print("8. Save and Return")
                else:
                    print("Invalid choice.")
            
            print("Preferences saved successfully.")
            
        except sqlite3.Error as e:
            print(f"Database error updating preferences: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    
    def update_contact_info(self):
        """Update parent contact information"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to update contact information.")
            return
        
        if self.auth.current_user['role'] != 'parent':
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
                    
                    cursor.execute(f'''
                    UPDATE parent_accounts
                    SET {column} = ?
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
    
    def view_child_timetable(self):
        """View a child's weekly timetable"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view your child's timetable.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_child_timetable'):
            print("You don't have permission to view timetables.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect the child whose timetable you want to view:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='class_schedule'")
                
                if not cursor.fetchone():
                    print("Timetable functionality is not yet set up in the system.")
                    return
                
                cursor.execute('''
                SELECT cs.day_of_week, cs.start_time, cs.end_time, cs.room_number, m.module_code, m.module_name
                FROM class_schedule cs
                JOIN student_modules sm ON cs.module_code = sm.module_code
                JOIN modules m ON sm.module_code = m.module_code
                WHERE sm.student_id = ?
                ORDER BY 
                    CASE cs.day_of_week
                        WHEN 'Monday' THEN 1
                        WHEN 'Tuesday' THEN 2
                        WHEN 'Wednesday' THEN 3
                        WHEN 'Thursday' THEN 4
                        WHEN 'Friday' THEN 5
                        WHEN 'Saturday' THEN 6
                        WHEN 'Sunday' THEN 7
                    END,
                    cs.start_time
                ''', (student_id,))
                
                timetable = cursor.fetchall()
                
                if not timetable:
                    print("No timetable information found for this student.")
                    return
                
                print(f"\nTimetable for {selected_child[1]} {selected_child[3]}:")
                
                current_day = None
                for entry in timetable:
                    day, start_time, end_time, room, module_code, module_name = entry
                    
                    if day != current_day:
                        print(f"\n{day}:")
                        current_day = day
                    
                    print(f"  {start_time} - {end_time}: {module_code} ({module_name}) in Room {room}")
                
            except sqlite3.Error as e:
                print(f"Database error viewing timetable: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")
    
    def view_child_assignments(self):
        """View a child's upcoming and overdue assignments"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view your child's assignments.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_child_assignments'):
            print("You don't have permission to view assignments.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect the child whose assignments you want to view:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            
            if selected_child[6] == 'minimal':
                print("You have minimal access and cannot view assignments for this child.")
                return
            
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_assignments'")
                
                if not cursor.fetchone():
                    print("Assignment tracking is not yet set up in the system.")
                    return
                
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                
                cursor.execute('''
                SELECT sa.id, sa.title, sa.description, sa.due_date, m.module_code, m.module_name, sa.status
                FROM student_assignments sa
                JOIN modules m ON sa.module_code = m.module_code
                WHERE sa.student_id = ? AND sa.due_date >= ? AND sa.status != 'completed'
                ORDER BY sa.due_date
                ''', (student_id, today))
                
                upcoming = cursor.fetchall()
                
                cursor.execute('''
                SELECT sa.id, sa.title, sa.description, sa.due_date, m.module_code, m.module_name, sa.status
                FROM student_assignments sa
                JOIN modules m ON sa.module_code = m.module_code
                WHERE sa.student_id = ? AND sa.due_date < ? AND sa.status != 'completed'
                ORDER BY sa.due_date
                ''', (student_id, today))
                
                overdue = cursor.fetchall()
                
                cursor.execute('''
                SELECT sa.id, sa.title, sa.description, sa.due_date, m.module_code, m.module_name, sa.status
                FROM student_assignments sa
                JOIN modules m ON sa.module_code = m.module_code
                WHERE sa.student_id = ? AND sa.status = 'completed'
                ORDER BY sa.due_date DESC
                LIMIT 5
                ''', (student_id,))
                
                completed = cursor.fetchall()
                
                print(f"\nAssignments for {selected_child[1]} {selected_child[3]}:")
                
                if not upcoming and not overdue and not completed:
                    print("No assignments found for this student.")
                else:
                    if upcoming:
                        print("\nUpcoming Assignments:")
                        for assignment in upcoming:
                            id, title, description, due_date, module_code, module_name, status = assignment
                            print(f"- {title} ({module_code})")
                            print(f"  Due: {due_date}")
                            print(f"  Status: {status}")
                            if description:
                                print(f"  Description: {description}")
                            print()
                    
                    if overdue:
                        print("\nOverdue Assignments:")
                        for assignment in overdue:
                            id, title, description, due_date, module_code, module_name, status = assignment
                            print(f"- {title} ({module_code})")
                            print(f"  Due: {due_date} (OVERDUE)")
                            print(f"  Status: {status}")
                            if description:
                                print(f"  Description: {description}")
                            print()
                    
                    if completed:
                        print("\nRecently Completed Assignments:")
                        for assignment in completed:
                            id, title, description, due_date, module_code, module_name, status = assignment
                            print(f"- {title} ({module_code})")
                            print(f"  Due: {due_date}")
                            print(f"  Status: {status}")
                            print()
                
            except sqlite3.Error as e:
                print(f"Database error viewing assignments: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")
    
    def view_school_calendar(self):
        """View school calendar events"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view the school calendar.")
            return
        
        if not self.auth.check_permission('view_school_calendar'):
            print("You don't have permission to view the school calendar.")
            return
        
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='school_calendar'")
            
            if not cursor.fetchone():
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS school_calendar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT,
                    event_description TEXT,
                    event_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    event_type TEXT,
                    audience TEXT
                )
                ''')
                
                sample_events = [
                    ('Start of Fall Semester', 'First day of classes for the fall semester', '2023-09-04', '08:00', '17:00', 'All Campuses', 'academic', 'all'),
                    ('Parents Evening', 'Meet with teachers to discuss student progress', '2023-09-20', '17:00', '20:00', 'Main Hall', 'parent', 'parents'),
                    ('Midterm Exams Begin', 'First day of midterm examinations', '2023-10-16', '09:00', '17:00', 'Examination Halls', 'academic', 'all'),
                    ('Fall Break', 'No classes during fall break', '2023-11-23', '00:00', '23:59', 'All Campuses', 'holiday', 'all'),
                    ('End of Fall Semester', 'Last day of classes for the fall semester', '2023-12-15', '08:00', '17:00', 'All Campuses', 'academic', 'all')
                ]
                
                cursor.executemany(
                    'INSERT INTO school_calendar (event_name, event_description, event_date, start_time, end_time, location, event_type, audience) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    sample_events
                )
                
                conn.commit()
            
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            
            print("\nCalendar View Options:")
            print("1. Upcoming Events")
            print("2. This Month's Events")
            print("3. All Events")
            print("4. Parent-Specific Events")
            
            view_choice = input("Select view option (1-4): ")
            
            if view_choice == '1':
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                WHERE event_date >= ?
                ORDER BY event_date, start_time
                LIMIT 10
                ''', (today,))
                print("\nUpcoming Events:")
            elif view_choice == '2':
                current_month = datetime.datetime.now().strftime('%Y-%m')
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                WHERE event_date LIKE ?
                ORDER BY event_date, start_time
                ''', (f"{current_month}%",))
                print(f"\nEvents for {datetime.datetime.now().strftime('%B %Y')}:")
            elif view_choice == '3':
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                ORDER BY event_date, start_time
                ''')
                print("\nAll Events:")
            elif view_choice == '4':
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                WHERE audience IN ('all', 'parents')
                ORDER BY event_date, start_time
                ''')
                print("\nParent-Related Events:")
            else:
                print("Invalid choice. Showing upcoming events.")
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                WHERE event_date >= ?
                ORDER BY event_date, start_time
                LIMIT 10
                ''', (today,))
                print("\nUpcoming Events:")
            
            events = cursor.fetchall()
            
            if not events:
                print("No events found for the selected view.")
            else:
                current_date = None
                
                for event in events:
                    name, description, date, start, end, location, type = event
                    
                    if date != current_date:
                        day_name = datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%A')
                        print(f"\n{date} ({day_name}):")
                        current_date = date
                    
                    print(f"  {start} - {end}: {name}")
                    print(f"  Location: {location}")
                    print(f"  Type: {type}")
                    if description:
                        print(f"  Description: {description}")
                    print()
            
        except sqlite3.Error as e:
            print(f"Database error viewing calendar: {e}")
        finally:
            if conn:
                conn.close()
    
    def view_parent_dashboard(self):
        """Display a dashboard summary for the parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view the dashboard.")
            return
        
        if self.auth.current_user['role'] != 'parent' and self.auth.current_user['role'] != 'admin':
            print("This function is only available for parent accounts and administrators.")
            return
        
        if self.auth.current_user['role'] == 'parent' and not self.auth.check_permission('access_parent_dashboard'):
            print("You don't have permission to access the dashboard.")
            return
        
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            if self.auth.current_user['role'] == 'parent':
                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return
            else:
                print("\nView Dashboard for Parent:")
                cursor.execute('SELECT parent_id, first_name, last_name FROM parent_accounts')
                parents = cursor.fetchall()
                
                if not parents:
                    print("No parent accounts found in the system.")
                    return
                
                for i, parent in enumerate(parents):
                    print(f"{i+1}. {parent[1]} {parent[2]} (ID: {parent[0]})")
                
                choice = input("Select parent (or 0 to cancel): ")
                if choice == '0':
                    return
                
                try:
                    index = int(choice) - 1
                    if index < 0 or index >= len(parents):
                        raise ValueError
                    parent_id = parents[index][0]
                except (ValueError, IndexError):
                    print("Invalid choice.")
                    return
            
            cursor.execute('SELECT first_name, last_name FROM parent_accounts WHERE parent_id = ?', (parent_id,))
            parent_info = cursor.fetchone()
            
            if not parent_info:
                print("Error: Parent account not found.")
                return
            
            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, s.course
            FROM students s
            JOIN parent_student_relationships psr ON s.student_id = psr.student_id
            WHERE psr.parent_id = ?
            ORDER BY s.last_name, s.first_name
            ''', (parent_id,))
            
            children = cursor.fetchall()
            
            if not children:
                print("No children registered for this parent.")
                return
            
            print("\n" + "=" * 60)
            print(f"PARENT DASHBOARD: {parent_info[0]} {parent_info[1]}")
            print("=" * 60)
            
            print(f"\nYou have {len(children)} student(s) registered:")
            for child in children:
                student_id, first_name, last_name, course = child
                print(f"- {first_name} {last_name} (ID: {student_id}, Course: {course})")
            
            try:
                cursor.execute('''
                SELECT COUNT(*) FROM parent_messages
                WHERE parent_id = ? AND is_read = 0 AND is_from_parent = 0
                ''', (parent_id,))
                
                unread_count = cursor.fetchone()[0]
                print(f"\nUnread Messages: {unread_count}")
            except sqlite3.Error:
                print("\nUnread Messages: Unable to retrieve")
            
            print("\nStudent Alerts:")
            
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            
            for child in children:
                student_id, first_name, last_name, course = child
                
                print(f"\n{first_name} {last_name}:")
                
                try:
                    cursor.execute('''
                    SELECT COUNT(*) 
                    FROM attendance 
                    WHERE student_id = ? AND status != 'present' AND date >= date('now', '-14 days')
                    ''', (student_id,))
                    
                    absence_count = cursor.fetchone()
                    
                    if absence_count and absence_count[0] > 0:
                        print(f"- Attendance: {absence_count[0]} absence(s) in the last 14 days")
                except sqlite3.Error:
                    pass
                
                try:
                    cursor.execute('''
                    SELECT COUNT(*) 
                    FROM student_assignments 
                    WHERE student_id = ? AND due_date < ? AND status != 'completed'
                    ''', (student_id, today))
                    
                    overdue_count = cursor.fetchone()
                    
                    if overdue_count and overdue_count[0] > 0:
                        print(f"- Assignments: {overdue_count[0]} overdue assignment(s)")
                except sqlite3.Error:
                    pass
                
                try:
                    cursor.execute('''
                    SELECT COUNT(*) 
                    FROM student_assignments 
                    WHERE student_id = ? AND due_date >= ? AND due_date <= date(?, '+7 days') 
                    AND (title LIKE '%test%' OR title LIKE '%exam%' OR title LIKE '%quiz%')
                    ''', (student_id, today, today))
                    
                    test_count = cursor.fetchone()
                    
                    if test_count and test_count[0] > 0:
                        print(f"- Upcoming: {test_count[0]} test(s) in the next 7 days")
                except sqlite3.Error:
                    pass
                
                try:
                    cursor.execute('''
                    SELECT COUNT(*) 
                    FROM student_grades 
                    WHERE student_id = ? AND grade_date >= date('now', '-7 days')
                    ''', (student_id, ))
                    
                    grade_count = cursor.fetchone()
                    
                    if grade_count and grade_count[0] > 0:
                        print(f"- Grades: {grade_count[0]} new grade(s) in the last 7 days")
                except sqlite3.Error:
                    pass
                
                try:
                    cursor.execute('''
                    SELECT COUNT(*) 
                    FROM teacher_reports 
                    WHERE student_id = ? AND created_date >= date('now', '-7 days')
                    ''', (student_id, ))
                    
                    report_count = cursor.fetchone()
                    
                    if report_count and report_count[0] > 0:
                        print(f"- Reports: {report_count[0]} new teacher report(s) in the last 7 days")
                except sqlite3.Error:
                    pass
            
            try:
                print("\nUpcoming School Events:")
                
                cursor.execute('''
                SELECT event_name, event_date, event_type
                FROM school_calendar
                WHERE event_date >= ? AND event_date <= date(?, '+14 days') AND audience IN ('all', 'parents')
                ORDER BY event_date
                LIMIT 3
                ''', (today, today))
                
                events = cursor.fetchall()
                
                if not events:
                    print("No upcoming events in the next 14 days.")
                else:
                    for event in events:
                        name, date, type = event
                        print(f"- {date}: {name} ({type})")
            except sqlite3.Error:
                print("Unable to retrieve upcoming events.")
            
            print("\n" + "=" * 60)
            
        except sqlite3.Error as e:
            print(f"Database error accessing dashboard: {e}")
        finally:
            if conn:
                conn.close()

    # NEW ENHANCED FEATURES START HERE

    # FINANCIAL MANAGEMENT FEATURES
    def view_student_fees(self):
        """View outstanding fees and payment history for children"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view fees.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_fees'):
            print("You don't have permission to view fees.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to view fees:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get outstanding fees
                cursor.execute('''
                SELECT fee_type, description, amount, due_date, payment_status
                FROM student_fees
                WHERE student_id = ? AND payment_status = 'pending'
                ORDER BY due_date
                ''', (student_id,))
                
                outstanding_fees = cursor.fetchall()
                
                # Get payment history
                cursor.execute('''
                SELECT fee_type, description, amount, paid_date, payment_method, transaction_id
                FROM student_fees
                WHERE student_id = ? AND payment_status = 'paid'
                ORDER BY paid_date DESC
                LIMIT 10
                ''', (student_id,))
                
                payment_history = cursor.fetchall()
                
                print(f"\nFees for {selected_child[1]} {selected_child[3]}:")
                
                if outstanding_fees:
                    print("\nOutstanding Fees:")
                    total_outstanding = 0
                    for fee in outstanding_fees:
                        fee_type, description, amount, due_date, status = fee
                        total_outstanding += float(amount)
                        print(f"- {fee_type}: £{amount}")
                        print(f"  Description: {description}")
                        print(f"  Due Date: {due_date}")
                        print()
                    
                    print(f"Total Outstanding: £{total_outstanding:.2f}")
                else:
                    print("\nNo outstanding fees.")
                
                if payment_history:
                    print("\nRecent Payment History:")
                    for payment in payment_history:
                        fee_type, description, amount, paid_date, method, transaction = payment
                        print(f"- {fee_type}: £{amount} paid on {paid_date}")
                        print(f"  Method: {method}")
                        if transaction:
                            print(f"  Transaction ID: {transaction}")
                        print()
                
            except sqlite3.Error as e:
                print(f"Database error viewing fees: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def manage_meal_account(self):
        """Manage student meal account and view transactions"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage meal accounts.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('manage_meal_account'):
            print("You don't have permission to manage meal accounts.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to manage meal account:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get or create meal account
                cursor.execute('SELECT balance, low_balance_threshold, auto_topup_enabled, auto_topup_amount FROM meal_accounts WHERE student_id = ?', (student_id,))
                account = cursor.fetchone()
                
                if not account:
                    cursor.execute('INSERT INTO meal_accounts (student_id, last_updated) VALUES (?, ?)', 
                                 (student_id, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    account = (0.00, 10.00, 0, 20.00)
                
                balance, threshold, auto_topup, topup_amount = account
                
                print(f"\nMeal Account for {selected_child[1]} {selected_child[3]}:")
                print(f"Current Balance: £{balance:.2f}")
                print(f"Low Balance Threshold: £{threshold:.2f}")
                print(f"Auto Top-up: {'Enabled' if auto_topup else 'Disabled'}")
                if auto_topup:
                    print(f"Auto Top-up Amount: £{topup_amount:.2f}")
                
                # Get recent transactions
                cursor.execute('''
                SELECT transaction_type, amount, description, transaction_date, balance_after
                FROM meal_transactions
                WHERE student_id = ?
                ORDER BY transaction_date DESC
                LIMIT 10
                ''', (student_id,))
                
                transactions = cursor.fetchall()
                
                if transactions:
                    print("\nRecent Transactions:")
                    for transaction in transactions:
                        trans_type, amount, description, date, balance_after = transaction
                        print(f"- {date}: {trans_type} £{amount:.2f} - {description}")
                        print(f"  Balance after: £{balance_after:.2f}")
                
                print("\nOptions:")
                print("1. Add funds")
                print("2. View all transactions")
                print("3. Update auto top-up settings")
                print("4. Back to menu")
                
                option = input("Select option: ")
                
                if option == '1':
                    try:
                        amount = float(input("Enter amount to add: £"))
                        if amount <= 0:
                            print("Invalid amount.")
                            return
                        
                        new_balance = float(balance) + amount
                        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        cursor.execute('UPDATE meal_accounts SET balance = ?, last_updated = ? WHERE student_id = ?',
                                     (new_balance, current_time, student_id))
                        
                        cursor.execute('''INSERT INTO meal_transactions 
                                       (student_id, transaction_type, amount, description, transaction_date, balance_after)
                                       VALUES (?, ?, ?, ?, ?, ?)''',
                                     (student_id, 'credit', amount, 'Parent top-up', current_time, new_balance))
                        
                        conn.commit()
                        print(f"Successfully added £{amount:.2f}. New balance: £{new_balance:.2f}")
                        
                    except ValueError:
                        print("Invalid amount entered.")
                
                elif option == '3':
                    print("\nAuto Top-up Settings:")
                    enable = input("Enable auto top-up? (y/n): ").lower() == 'y'
                    
                    if enable:
                        try:
                            new_threshold = float(input(f"Low balance threshold (current: £{threshold:.2f}): £"))
                            new_topup_amount = float(input(f"Auto top-up amount (current: £{topup_amount:.2f}): £"))
                            
                            cursor.execute('''UPDATE meal_accounts 
                                           SET auto_topup_enabled = ?, low_balance_threshold = ?, auto_topup_amount = ?
                                           WHERE student_id = ?''',
                                         (1, new_threshold, new_topup_amount, student_id))
                            conn.commit()
                            print("Auto top-up settings updated successfully.")
                        except ValueError:
                            print("Invalid values entered.")
                    else:
                        cursor.execute('UPDATE meal_accounts SET auto_topup_enabled = 0 WHERE student_id = ?', (student_id,))
                        conn.commit()
                        print("Auto top-up disabled.")
                
            except sqlite3.Error as e:
                print(f"Database error managing meal account: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_fundraising_campaigns(self):
        """View and participate in fundraising campaigns"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view fundraising campaigns.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            # Get active campaigns
            cursor.execute('''
            SELECT id, campaign_name, description, target_amount, current_amount, start_date, end_date
            FROM fundraising_campaigns
            WHERE status = 'active' AND end_date >= date('now')
            ORDER BY end_date
            ''')
            
            campaigns = cursor.fetchall()
            
            if not campaigns:
                print("No active fundraising campaigns at this time.")
                return
            
            print("\nActive Fundraising Campaigns:")
            for campaign in campaigns:
                id, name, description, target, current, start_date, end_date = campaign
                progress = (float(current) / float(target)) * 100 if target > 0 else 0
                
                print(f"\n{name}")
                print(f"Description: {description}")
                print(f"Target: £{target:.2f}")
                print(f"Raised: £{current:.2f} ({progress:.1f}%)")
                print(f"Campaign ends: {end_date}")
            
            # Get parent's donation history
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if parent_id:
                cursor.execute('''
                SELECT fc.campaign_name, fd.amount, fd.donation_date, s.first_name, s.last_name
                FROM fundraising_donations fd
                JOIN fundraising_campaigns fc ON fd.campaign_id = fc.id
                LEFT JOIN students s ON fd.student_id = s.student_id
                WHERE fd.parent_id = ?
                ORDER BY fd.donation_date DESC
                LIMIT 5
                ''', (parent_id,))
                
                donations = cursor.fetchall()
                
                if donations:
                    print("\nYour Recent Donations:")
                    for donation in donations:
                        campaign_name, amount, date, student_first, student_last = donation
                        student_info = f" (for {student_first} {student_last})" if student_first else ""
                        print(f"- £{amount:.2f} to {campaign_name} on {date}{student_info}")
            
        except sqlite3.Error as e:
            print(f"Database error viewing fundraising campaigns: {e}")
        finally:
            if conn:
                conn.close()

    # ENHANCED STUDENT MONITORING FEATURES
    def view_behavior_reports(self):
        """View behavior incidents and positive reports"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view behavior reports.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_behavior_reports'):
            print("You don't have permission to view behavior reports.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to view behavior reports:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get behavior reports
                cursor.execute('''
                SELECT incident_date, behavior_type, severity, description, action_taken, reported_by, resolved
                FROM student_behavior
                WHERE student_id = ?
                ORDER BY incident_date DESC
                ''', (student_id,))
                
                reports = cursor.fetchall()
                
                if not reports:
                    print(f"No behavior reports found for {selected_child[1]} {selected_child[3]}.")
                    return
                
                print(f"\nBehavior Reports for {selected_child[1]} {selected_child[3]}:")
                
                positive_reports = [r for r in reports if r[2] == 'positive']
                negative_reports = [r for r in reports if r[2] in ['minor', 'major', 'severe']]
                
                if positive_reports:
                    print("\nPositive Behavior Reports:")
                    for report in positive_reports:
                        date, behavior_type, severity, description, action, reporter, resolved = report
                        print(f"- {date}: {behavior_type}")
                        print(f"  {description}")
                        if action:
                            print(f"  Recognition: {action}")
                        print(f"  Reported by: {reporter}")
                        print()
                
                if negative_reports:
                    print("\nIncident Reports:")
                    for report in negative_reports:
                        date, behavior_type, severity, description, action, reporter, resolved = report
                        status = "Resolved" if resolved else "Open"
                        print(f"- {date}: {behavior_type} ({severity.upper()}) - {status}")
                        print(f"  {description}")
                        if action:
                            print(f"  Action taken: {action}")
                        print(f"  Reported by: {reporter}")
                        print()
                
                # Summary statistics
                total_positive = len(positive_reports)
                total_incidents = len(negative_reports)
                
                print(f"Summary: {total_positive} positive reports, {total_incidents} incidents")
                
            except sqlite3.Error as e:
                print(f"Database error viewing behavior reports: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_medical_information(self):
        """View and update medical information for children"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view medical information.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('manage_medical_info'):
            print("You don't have permission to view medical information.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to view medical information:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get medical information
                cursor.execute('''
                SELECT condition_type, description, medication_name, dosage, administration_time, 
                       emergency_contact, doctor_contact, expiry_date, notes
                FROM student_medical_info
                WHERE student_id = ?
                ORDER BY condition_type
                ''', (student_id,))
                
                medical_info = cursor.fetchall()
                
                print(f"\nMedical Information for {selected_child[1]} {selected_child[3]}:")
                
                if not medical_info:
                    print("No medical information on file.")
                else:
                    for info in medical_info:
                        condition, description, medication, dosage, admin_time, emergency, doctor, expiry, notes = info
                        print(f"\nCondition: {condition}")
                        print(f"Description: {description}")
                        if medication:
                            print(f"Medication: {medication}")
                            print(f"Dosage: {dosage}")
                            print(f"Administration time: {admin_time}")
                            if expiry:
                                print(f"Expires: {expiry}")
                        if emergency:
                            print(f"Emergency contact: {emergency}")
                        if doctor:
                            print(f"Doctor contact: {doctor}")
                        if notes:
                            print(f"Notes: {notes}")
                        print("-" * 40)
                
                print("\nOptions:")
                print("1. Add medical condition/medication")
                print("2. Update existing information")
                print("3. Back to menu")
                
                option = input("Select option: ")
                
                if option == '1':
                    print("\nAdd Medical Information:")
                    condition_type = input("Condition type (allergy/medication/condition): ")
                    description = input("Description: ")
                    medication = input("Medication name (if applicable): ")
                    dosage = input("Dosage (if applicable): ")
                    admin_time = input("Administration time (if applicable): ")
                    emergency = input("Emergency contact: ")
                    doctor = input("Doctor contact: ")
                    expiry = input("Expiry date (YYYY-MM-DD, if applicable): ")
                    notes = input("Additional notes: ")
                    
                    cursor.execute('''
                    INSERT INTO student_medical_info 
                    (student_id, condition_type, description, medication_name, dosage, 
                     administration_time, emergency_contact, doctor_contact, expiry_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, condition_type, description, medication, dosage, 
                          admin_time, emergency, doctor, expiry, notes))
                    
                    conn.commit()
                    print("Medical information added successfully.")
                
            except sqlite3.Error as e:
                print(f"Database error viewing medical information: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_transportation_info(self):
        """View transportation information and routes"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view transportation information.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_transportation'):
            print("You don't have permission to view transportation information.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to view transportation information:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get transportation information
                cursor.execute('''
                SELECT route_name, bus_number, pickup_time, dropoff_time, pickup_location, 
                       dropoff_location, driver_name, driver_phone, active
                FROM transportation
                WHERE student_id = ? AND active = 1
                ''', (student_id,))
                
                transport_info = cursor.fetchall()
                
                print(f"\nTransportation Information for {selected_child[1]} {selected_child[3]}:")
                
                if not transport_info:
                    print("No transportation arrangements on file.")
                else:
                    for info in transport_info:
                        route, bus_num, pickup_time, dropoff_time, pickup_loc, dropoff_loc, driver, driver_phone, active = info
                        print(f"\nRoute: {route}")
                        print(f"Bus Number: {bus_num}")
                        print(f"Pickup Time: {pickup_time}")
                        print(f"Pickup Location: {pickup_loc}")
                        print(f"Dropoff Time: {dropoff_time}")
                        print(f"Dropoff Location: {dropoff_loc}")
                        print(f"Driver: {driver}")
                        if driver_phone:
                            print(f"Driver Phone: {driver_phone}")
                
            except sqlite3.Error as e:
                print(f"Database error viewing transportation information: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_library_account(self):
        """View library account and borrowed books"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view library information.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_library_account'):
            print("You don't have permission to view library accounts.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to view library account:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get currently borrowed books
                cursor.execute('''
                SELECT book_title, author, checkout_date, due_date, fine_amount, status
                FROM library_accounts
                WHERE student_id = ? AND status = 'checked_out'
                ORDER BY due_date
                ''', (student_id,))
                
                current_books = cursor.fetchall()
                
                # Get recently returned books
                cursor.execute('''
                SELECT book_title, author, checkout_date, return_date, fine_amount
                FROM library_accounts
                WHERE student_id = ? AND status = 'returned'
                ORDER BY return_date DESC
                LIMIT 5
                ''', (student_id,))
                
                returned_books = cursor.fetchall()
                
                # Calculate total fines
                cursor.execute('''
                SELECT SUM(fine_amount)
                FROM library_accounts
                WHERE student_id = ? AND fine_amount > 0
                ''', (student_id,))
                
                total_fines = cursor.fetchone()[0] or 0
                
                print(f"\nLibrary Account for {selected_child[1]} {selected_child[3]}:")
                
                if current_books:
                    print("\nCurrently Borrowed Books:")
                    for book in current_books:
                        title, author, checkout_date, due_date, fine, status = book
                        print(f"- {title} by {author}")
                        print(f"  Checked out: {checkout_date}")
                        print(f"  Due: {due_date}")
                        if fine > 0:
                            print(f"  Fine: £{fine:.2f}")
                        
                        # Check if overdue
                        today = datetime.datetime.now().strftime('%Y-%m-%d')
                        if due_date < today:
                            print("  STATUS: OVERDUE")
                        print()
                else:
                    print("\nNo books currently borrowed.")
                
                if total_fines > 0:
                    print(f"\nTotal Outstanding Fines: £{total_fines:.2f}")
                
                if returned_books:
                    print("\nRecently Returned Books:")
                    for book in returned_books:
                        title, author, checkout_date, return_date, fine = book
                        print(f"- {title} by {author}")
                        print(f"  Returned: {return_date}")
                        if fine > 0:
                            print(f"  Fine paid: £{fine:.2f}")
                        print()
                
            except sqlite3.Error as e:
                print(f"Database error viewing library account: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_extracurricular_activities(self):
        """View and manage extracurricular activities"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view extracurricular activities.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_extracurricular'):
            print("You don't have permission to view extracurricular activities.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to view activities:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get enrolled activities
                cursor.execute('''
                SELECT ea.activity_name, ea.description, ea.supervisor, ea.meeting_schedule, 
                       ea.location, ea.fee, sa.enrollment_date, sa.status
                FROM student_activities sa
                JOIN extracurricular_activities ea ON sa.activity_id = ea.id
                WHERE sa.student_id = ? AND sa.status = 'active'
                ORDER BY ea.activity_name
                ''', (student_id,))
                
                enrolled_activities = cursor.fetchall()
                
                # Get available activities
                cursor.execute('''
                SELECT ea.id, ea.activity_name, ea.description, ea.supervisor, ea.meeting_schedule, 
                       ea.location, ea.fee, ea.max_participants
                FROM extracurricular_activities ea
                WHERE ea.status = 'active'
                AND ea.id NOT IN (
                    SELECT activity_id FROM student_activities 
                    WHERE student_id = ? AND status = 'active'
                )
                ORDER BY ea.activity_name
                ''', (student_id,))
                
                available_activities = cursor.fetchall()
                
                print(f"\nExtracurricular Activities for {selected_child[1]} {selected_child[3]}:")
                
                if enrolled_activities:
                    print("\nEnrolled Activities:")
                    for activity in enrolled_activities:
                        name, description, supervisor, schedule, location, fee, enrollment_date, status = activity
                        print(f"- {name}")
                        print(f"  Description: {description}")
                        print(f"  Supervisor: {supervisor}")
                        print(f"  Schedule: {schedule}")
                        print(f"  Location: {location}")
                        if fee > 0:
                            print(f"  Fee: £{fee:.2f}")
                        print(f"  Enrolled: {enrollment_date}")
                        print()
                else:
                    print("\nNot enrolled in any activities.")
                
                if available_activities:
                    print("\nAvailable Activities:")
                    for activity in available_activities:
                        id, name, description, supervisor, schedule, location, fee, max_participants = activity
                        print(f"- {name}")
                        print(f"  Description: {description}")
                        print(f"  Supervisor: {supervisor}")
                        print(f"  Schedule: {schedule}")
                        print(f"  Location: {location}")
                        if fee > 0:
                            print(f"  Fee: £{fee:.2f}")
                        print()
                
            except sqlite3.Error as e:
                print(f"Database error viewing activities: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    # ACADEMIC ENHANCEMENT FEATURES
    def view_homework_tracking(self):
        """View homework assignments and completion status"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view homework.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_homework'):
            print("You don't have permission to view homework.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to view homework:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            
            if selected_child[6] == 'minimal':
                print("You have minimal access and cannot view homework for this child.")
                return
            
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                
                # Get pending homework
                cursor.execute('''
                SELECT h.assignment_title, h.description, h.due_date, m.module_name, h.assigned_date
                FROM homework_assignments h
                JOIN modules m ON h.module_code = m.module_code
                WHERE h.student_id = ? AND h.completion_status = 'pending' AND h.due_date >= ?
                ORDER BY h.due_date
                ''', (student_id, today))
                
                pending_homework = cursor.fetchall()
                
                # Get overdue homework
                cursor.execute('''
                SELECT h.assignment_title, h.description, h.due_date, m.module_name, h.assigned_date
                FROM homework_assignments h
                JOIN modules m ON h.module_code = m.module_code
                WHERE h.student_id = ? AND h.completion_status = 'pending' AND h.due_date < ?
                ORDER BY h.due_date
                ''', (student_id, today))
                
                overdue_homework = cursor.fetchall()
                
                # Get recently completed homework
                cursor.execute('''
                SELECT h.assignment_title, h.submitted_date, h.grade, m.module_name, h.teacher_comments
                FROM homework_assignments h
                JOIN modules m ON h.module_code = m.module_code
                WHERE h.student_id = ? AND h.completion_status = 'completed'
                ORDER BY h.submitted_date DESC
                LIMIT 5
                ''', (student_id,))
                
                completed_homework = cursor.fetchall()
                
                print(f"\nHomework for {selected_child[1]} {selected_child[3]}:")
                
                if overdue_homework:
                    print("\nOVERDUE HOMEWORK:")
                    for hw in overdue_homework:
                        title, description, due_date, module, assigned_date = hw
                        print(f"- {title} ({module})")
                        print(f"  Due: {due_date} (OVERDUE)")
                        print(f"  Description: {description}")
                        print()
                
                if pending_homework:
                    print("\nUpcoming Homework:")
                    for hw in pending_homework:
                        title, description, due_date, module, assigned_date = hw
                        print(f"- {title} ({module})")
                        print(f"  Due: {due_date}")
                        print(f"  Description: {description}")
                        print()
                
                if completed_homework:
                    print("\nRecently Completed:")
                    for hw in completed_homework:
                        title, submitted_date, grade, module, comments = hw
                        print(f"- {title} ({module})")
                        print(f"  Submitted: {submitted_date}")
                        if grade:
                            print(f"  Grade: {grade}")
                        if comments:
                            print(f"  Teacher comments: {comments}")
                        print()
                
                if not pending_homework and not overdue_homework and not completed_homework:
                    print("No homework assignments found.")
                
            except sqlite3.Error as e:
                print(f"Database error viewing homework: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def schedule_parent_teacher_meeting(self):
        """Schedule a meeting with teachers"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to schedule meetings.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('schedule_meetings'):
            print("You don't have permission to schedule meetings.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for meeting:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get available teachers for this student
                cursor.execute('''
                SELECT DISTINCT t.id, t.username, m.module_name
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                JOIN module_teachers mt ON m.module_code = mt.module_code
                JOIN users t ON mt.teacher_id = t.id
                WHERE sm.student_id = ? AND t.role = 'teacher'
                ORDER BY t.username
                ''', (student_id,))
                
                teachers = cursor.fetchall()
                
                if not teachers:
                    print("No teachers found for this student.")
                    return
                
                print("\nSelect teacher to meet with:")
                for i, teacher in enumerate(teachers):
                    teacher_id, username, module_name = teacher
                    print(f"{i+1}. {username} ({module_name})")
                
                teacher_choice = input("Enter teacher number: ")
                try:
                    teacher_index = int(teacher_choice) - 1
                    if teacher_index < 0 or teacher_index >= len(teachers):
                        raise ValueError
                    
                    selected_teacher = teachers[teacher_index]
                    teacher_id = selected_teacher[0]
                    
                    # Get teacher availability
                    cursor.execute('''
                    SELECT day_of_week, start_time, end_time, meeting_type, location
                    FROM teacher_availability
                    WHERE teacher_id = ? AND active = 1
                    ORDER BY 
                        CASE day_of_week
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                        END,
                        start_time
                    ''', (teacher_id,))
                    
                    availability = cursor.fetchall()
                    
                    if not availability:
                        print("Teacher has not set availability. Please contact the school directly.")
                        return
                    
                    print(f"\nAvailability for {selected_teacher[1]}:")
                    for slot in availability:
                        day, start_time, end_time, meeting_type, location = slot
                        print(f"- {day}: {start_time} - {end_time} ({meeting_type}) at {location}")
                    
                    # Schedule meeting
                    print("\nSchedule Meeting:")
                    meeting_date = input("Meeting date (YYYY-MM-DD): ")
                    start_time = input("Start time (HH:MM): ")
                    end_time = input("End time (HH:MM): ")
                    meeting_type = input("Meeting type (in-person/phone/video): ")
                    agenda = input("Meeting agenda/topics: ")
                    
                    # Validate date format
                    try:
                        datetime.datetime.strptime(meeting_date, '%Y-%m-%d')
                        datetime.datetime.strptime(start_time, '%H:%M')
                        datetime.datetime.strptime(end_time, '%H:%M')
                    except ValueError:
                        print("Invalid date or time format.")
                        return
                    
                    parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                    if not parent_id:
                        print("Error retrieving parent ID.")
                        return
                    
                    # Insert meeting request
                    cursor.execute('''
                    INSERT INTO parent_teacher_meetings 
                    (parent_id, teacher_id, student_id, meeting_date, start_time, end_time, 
                     meeting_type, status, agenda)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'requested', ?)
                    ''', (parent_id, teacher_id, student_id, meeting_date, start_time, 
                          end_time, meeting_type, agenda))
                    
                    conn.commit()
                    print("Meeting request submitted successfully. The teacher will confirm the appointment.")
                    
                    # Send notification to teacher
                    cursor.execute('SELECT email FROM users WHERE id = ?', (teacher_id,))
                    teacher_email = cursor.fetchone()
                    
                    if teacher_email and teacher_email[0]:
                        try:
                            send_email(
                                teacher_email[0],
                                "Parent-Teacher Meeting Request",
                                f"A parent has requested a meeting on {meeting_date} at {start_time} regarding student {student_id}."
                            )
                        except Exception as e:
                            print(f"Note: Email notification could not be sent: {e}")
                    
                except (ValueError, IndexError):
                    print("Invalid teacher choice.")
                
            except sqlite3.Error as e:
                print(f"Database error scheduling meeting: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def manage_academic_goals(self):
        """Set and track academic goals"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage academic goals.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('set_academic_goals'):
            print("You don't have permission to set academic goals.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to manage goals:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get existing goals
                cursor.execute('''
                SELECT id, goal_title, description, target_grade, target_date, current_progress, status, created_date
                FROM academic_goals
                WHERE student_id = ?
                ORDER BY created_date DESC
                ''', (student_id,))
                
                goals = cursor.fetchall()
                
                print(f"\nAcademic Goals for {selected_child[1]} {selected_child[3]}:")
                
                if goals:
                    print("\nExisting Goals:")
                    for goal in goals:
                        id, title, description, target_grade, target_date, progress, status, created_date = goal
                        print(f"- {title} ({status.upper()})")
                        print(f"  Target: {target_grade} by {target_date}")
                        print(f"  Progress: {progress or 'Not updated'}")
                        print(f"  Created: {created_date}")
                        print()
                
                print("\nOptions:")
                print("1. Add new goal")
                print("2. Update goal progress")
                print("3. Back to menu")
                
                option = input("Select option: ")
                
                if option == '1':
                    print("\nAdd New Academic Goal:")
                    goal_title = input("Goal title: ")
                    description = input("Description: ")
                    target_grade = input("Target grade: ")
                    target_date = input("Target date (YYYY-MM-DD): ")
                    
                    # Validate date
                    try:
                        datetime.datetime.strptime(target_date, '%Y-%m-%d')
                    except ValueError:
                        print("Invalid date format.")
                        return
                    
                    parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                    if not parent_id:
                        print("Error retrieving parent ID.")
                        return
                    
                    created_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    cursor.execute('''
                    INSERT INTO academic_goals 
                    (student_id, parent_id, goal_title, description, target_grade, target_date, 
                     current_progress, status, created_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
                    ''', (student_id, parent_id, goal_title, description, target_grade, 
                          target_date, 'Goal set', created_date))
                    
                    conn.commit()
                    print("Academic goal added successfully.")
                
                elif option == '2' and goals:
                    print("\nSelect goal to update:")
                    for i, goal in enumerate(goals):
                        print(f"{i+1}. {goal[1]}")
                    
                    goal_choice = input("Enter goal number: ")
                    try:
                        goal_index = int(goal_choice) - 1
                        if goal_index < 0 or goal_index >= len(goals):
                            raise ValueError
                        
                        selected_goal = goals[goal_index]
                        goal_id = selected_goal[0]
                        
                        print(f"\nCurrent progress: {selected_goal[5] or 'Not updated'}")
                        new_progress = input("Update progress: ")
                        
                        print("\nUpdate status:")
                        print("1. Active")
                        print("2. Achieved")
                        print("3. Paused")
                        print("4. Cancelled")
                        
                        status_choice = input("Select status: ")
                        status_map = {'1': 'active', '2': 'achieved', '3': 'paused', '4': 'cancelled'}
                        new_status = status_map.get(status_choice, 'active')
                        
                        cursor.execute('''
                        UPDATE academic_goals 
                        SET current_progress = ?, status = ?
                        WHERE id = ?
                        ''', (new_progress, new_status, goal_id))
                        
                        conn.commit()
                        print("Goal updated successfully.")
                        
                    except (ValueError, IndexError):
                        print("Invalid goal choice.")
                
            except sqlite3.Error as e:
                print(f"Database error managing goals: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    # COMMUNICATION ENHANCEMENT FEATURES
    def view_school_announcements(self):
        """View school announcements"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view announcements.")
            return
        
        if not self.auth.check_permission('view_announcements'):
            print("You don't have permission to view announcements.")
            return
        
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # Get unread announcements
            cursor.execute('''
            SELECT sa.id, sa.title, sa.content, sa.priority, sa.category, sa.created_date, sa.requires_acknowledgment
            FROM school_announcements sa
            WHERE sa.audience IN ('all', 'parents') 
            AND (sa.expiry_date IS NULL OR sa.expiry_date >= ?)
            AND sa.id NOT IN (
                SELECT announcement_id FROM announcement_reads 
                WHERE parent_id = ?
            )
            ORDER BY sa.priority DESC, sa.created_date DESC
            ''', (today, parent_id))
            
            unread_announcements = cursor.fetchall()
            
            # Get recent read announcements
            cursor.execute('''
            SELECT sa.id, sa.title, sa.content, sa.priority, sa.category, sa.created_date, ar.read_date
            FROM school_announcements sa
            JOIN announcement_reads ar ON sa.id = ar.announcement_id
            WHERE ar.parent_id = ?
            ORDER BY ar.read_date DESC
            LIMIT 5
            ''', (parent_id,))
            
            read_announcements = cursor.fetchall()
            
            print("\nSchool Announcements:")
            
            if unread_announcements:
                print("\nNew Announcements:")
                for announcement in unread_announcements:
                    id, title, content, priority, category, created_date, requires_ack = announcement
                    priority_text = f" ({priority.upper()})" if priority != 'normal' else ""
                    ack_text = " [REQUIRES ACKNOWLEDGMENT]" if requires_ack else ""
                    
                    print(f"- {title}{priority_text}{ack_text}")
                    print(f"  Category: {category}")
                    print(f"  Date: {created_date}")
                    print(f"  {content}")
                    print()
                
                # Mark announcements as read
                if input("Mark all announcements as read? (y/n): ").lower() == 'y':
                    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    for announcement in unread_announcements:
                        announcement_id = announcement[0]
                        requires_ack = announcement[6]
                        
                        cursor.execute('''
                        INSERT INTO announcement_reads (announcement_id, parent_id, read_date, acknowledged)
                        VALUES (?, ?, ?, ?)
                        ''', (announcement_id, parent_id, current_time, 1 if requires_ack else 0))
                    
                    conn.commit()
                    print("All announcements marked as read.")
            
            if read_announcements:
                print("\nRecently Read Announcements:")
                for announcement in read_announcements:
                    id, title, content, priority, category, created_date, read_date = announcement
                    print(f"- {title} (read on {read_date})")
                    print(f"  {content[:100]}...")
                    print()
            
            if not unread_announcements and not read_announcements:
                print("No announcements available.")
            
        except sqlite3.Error as e:
            print(f"Database error viewing announcements: {e}")
        finally:
            if conn:
                conn.close()

    def send_group_message(self):
        """Send a message to multiple teachers at once"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to send group messages.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('group_messaging'):
            print("You don't have permission to send group messages.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for group message:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get all teachers for this student
                cursor.execute('''
                SELECT DISTINCT t.id, t.username, m.module_name
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                JOIN module_teachers mt ON m.module_code = mt.module_code
                JOIN users t ON mt.teacher_id = t.id
                WHERE sm.student_id = ? AND t.role = 'teacher'
                ORDER BY t.username
                ''', (student_id,))
                
                teachers = cursor.fetchall()
                
                if not teachers:
                    print("No teachers found for this student.")
                    return
                
                print("\nSelect teachers to message (enter numbers separated by commas, or 'all'):")
                for i, teacher in enumerate(teachers):
                    teacher_id, username, module_name = teacher
                    print(f"{i+1}. {username} ({module_name})")
                
                teacher_choice = input("Enter your selection: ")
                
                selected_teachers = []
                if teacher_choice.lower() == 'all':
                    selected_teachers = teachers
                else:
                    try:
                        indices = [int(x.strip()) - 1 for x in teacher_choice.split(',')]
                        selected_teachers = [teachers[i] for i in indices if 0 <= i < len(teachers)]
                    except (ValueError, IndexError):
                        print("Invalid selection.")
                        return
                
                if not selected_teachers:
                    print("No teachers selected.")
                    return
                
                print(f"\nSending to {len(selected_teachers)} teacher(s)")
                message_content = input("Message: ")
                
                if not message_content:
                    print("Message cannot be empty.")
                    return
                
                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return
                
                # Generate group ID for this message
                group_id = f"group_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                created_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Send message to each selected teacher
                for teacher in selected_teachers:
                    teacher_id = teacher[0]
                    
                    cursor.execute('''
                    INSERT INTO parent_messages 
                    (parent_id, teacher_id, student_id, message_content, created_date, 
                     is_read, is_from_parent, message_type, group_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'group', ?)
                    ''', (parent_id, teacher_id, student_id, message_content, created_date, 
                          0, 1, group_id))
                
                conn.commit()
                print(f"Group message sent successfully to {len(selected_teachers)} teacher(s).")
                
            except sqlite3.Error as e:
                print(f"Database error sending group message: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def emergency_contact_update(self):
        """Quick emergency contact updates"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to update emergency contacts.")
            return
        
        if self.auth.current_user['role'] != 'parent':
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

    # ADMINISTRATIVE TOOLS
    def manage_documents(self):
        """Upload and manage documents"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage documents.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('manage_documents'):
            print("You don't have permission to manage documents.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for document management:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get existing documents
                cursor.execute('''
                SELECT document_type, document_name, upload_date, status, expiry_date
                FROM parent_documents
                WHERE student_id = ?
                ORDER BY upload_date DESC
                ''', (student_id,))
                
                documents = cursor.fetchall()
                
                print(f"\nDocuments for {selected_child[1]} {selected_child[3]}:")
                
                if documents:
                    print("\nExisting Documents:")
                    for doc in documents:
                        doc_type, name, upload_date, status, expiry_date = doc
                        expiry_info = f" (expires: {expiry_date})" if expiry_date else ""
                        print(f"- {name} ({doc_type}) - {status.upper()}{expiry_info}")
                        print(f"  Uploaded: {upload_date}")
                        print()
                
                print("\nDocument Types:")
                print("1. Permission slip")
                print("2. Medical form")
                print("3. Emergency contact form")
                print("4. Photo consent")
                print("5. Other")
                
                doc_type_choice = input("Select document type to upload: ")
                doc_types = {
                    '1': 'permission_slip',
                    '2': 'medical_form',
                    '3': 'emergency_contact',
                    '4': 'photo_consent',
                    '5': 'other'
                }
                
                doc_type = doc_types.get(doc_type_choice)
                if not doc_type:
                    print("Invalid choice.")
                    return
                
                if doc_type == 'other':
                    doc_type = input("Specify document type: ")
                
                document_name = input("Document name/description: ")
                file_path = input("File path (or 'simulate' to simulate upload): ")
                
                expiry_date = input("Expiry date (YYYY-MM-DD, or leave blank): ")
                if expiry_date:
                    try:
                        datetime.datetime.strptime(expiry_date, '%Y-%m-%d')
                    except ValueError:
                        print("Invalid date format.")
                        return
                
                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return
                
                upload_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # In a real system, you would handle file upload here
                if file_path.lower() == 'simulate':
                    file_path = f"/documents/{parent_id}_{student_id}_{document_name.replace(' ', '_')}.pdf"
                
                cursor.execute('''
                INSERT INTO parent_documents 
                (parent_id, student_id, document_type, document_name, file_path, upload_date, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (parent_id, student_id, doc_type, document_name, file_path, upload_date, expiry_date))
                
                conn.commit()
                print("Document uploaded successfully.")
                
            except sqlite3.Error as e:
                print(f"Database error managing documents: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def manage_pickup_authorization(self):
        """Manage who can pick up children"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage pickup authorization.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('manage_pickup_auth'):
            print("You don't have permission to manage pickup authorization.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for pickup authorization:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get existing authorizations
                cursor.execute('''
                SELECT authorized_person_name, relationship, phone_number, valid_from, valid_until, active
                FROM pickup_authorizations
                WHERE student_id = ?
                ORDER BY authorized_person_name
                ''', (student_id,))
                
                authorizations = cursor.fetchall()
                
                print(f"\nPickup Authorization for {selected_child[1]} {selected_child[3]}:")
                
                if authorizations:
                    print("\nAuthorized Persons:")
                    for auth in authorizations:
                        name, relationship, phone, valid_from, valid_until, active = auth
                        status = "Active" if active else "Inactive"
                        print(f"- {name} ({relationship}) - {status}")
                        print(f"  Phone: {phone}")
                        print(f"  Valid: {valid_from} to {valid_until}")
                        print()
                
                print("\nOptions:")
                print("1. Add authorized person")
                print("2. Remove authorization")
                print("3. Back to menu")
                
                option = input("Select option: ")
                
                if option == '1':
                    print("\nAdd Authorized Person:")
                    person_name = input("Full name: ")
                    relationship = input("Relationship to student: ")
                    phone_number = input("Phone number: ")
                    id_number = input("ID number: ")
                    
                    valid_from = input("Valid from (YYYY-MM-DD, or leave blank for today): ")
                    if not valid_from:
                        valid_from = datetime.datetime.now().strftime('%Y-%m-%d')
                    
                    valid_until = input("Valid until (YYYY-MM-DD, or leave blank for one year): ")
                    if not valid_until:
                        future_date = datetime.datetime.now() + datetime.timedelta(days=365)
                        valid_until = future_date.strftime('%Y-%m-%d')
                    
                    # Validate dates
                    try:
                        datetime.datetime.strptime(valid_from, '%Y-%m-%d')
                        datetime.datetime.strptime(valid_until, '%Y-%m-%d')
                    except ValueError:
                        print("Invalid date format.")
                        return
                    
                    parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                    
                    cursor.execute('''
                    INSERT INTO pickup_authorizations 
                    (student_id, authorized_person_name, relationship, phone_number, id_number, 
                     valid_from, valid_until, active, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                    ''', (student_id, person_name, relationship, phone_number, id_number, 
                          valid_from, valid_until, parent_id))
                    
                    conn.commit()
                    print("Authorized person added successfully.")
                
                elif option == '2' and authorizations:
                    print("\nSelect person to remove authorization:")
                    for i, auth in enumerate(authorizations):
                        name, relationship = auth[0], auth[1]
                        print(f"{i+1}. {name} ({relationship})")
                    
                    remove_choice = input("Enter number: ")
                    try:
                        remove_index = int(remove_choice) - 1
                        if remove_index < 0 or remove_index >= len(authorizations):
                            raise ValueError
                        
                        selected_auth = authorizations[remove_index]
                        person_name = selected_auth[0]
                        
                        cursor.execute('''
                        UPDATE pickup_authorizations 
                        SET active = 0
                        WHERE student_id = ? AND authorized_person_name = ?
                        ''', (student_id, person_name))
                        
                        conn.commit()
                        print(f"Authorization removed for {person_name}.")
                        
                    except (ValueError, IndexError):
                        print("Invalid choice.")
                
            except sqlite3.Error as e:
                print(f"Database error managing pickup authorization: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def manage_photo_permissions(self):
        """Manage photo and media permissions"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage photo permissions.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('manage_photo_permissions'):
            print("You don't have permission to manage photo permissions.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for photo permissions:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get existing permissions
                cursor.execute('''
                SELECT permission_type, consent_given, conditions, valid_from, valid_until, date_signed
                FROM photo_permissions
                WHERE student_id = ?
                ORDER BY date_signed DESC
                ''', (student_id,))
                
                permissions = cursor.fetchall()
                
                print(f"\nPhoto Permissions for {selected_child[1]} {selected_child[3]}:")
                
                if permissions:
                    print("\nCurrent Permissions:")
                    for perm in permissions:
                        perm_type, consent, conditions, valid_from, valid_until, date_signed = perm
                        status = "GRANTED" if consent else "DENIED"
                        print(f"- {perm_type}: {status}")
                        if conditions:
                            print(f"  Conditions: {conditions}")
                        print(f"  Valid: {valid_from} to {valid_until}")
                        print(f"  Signed: {date_signed}")
                        print()
                
                print("\nPermission Types:")
                print("1. School website photos")
                print("2. Social media posts")
                print("3. Yearbook photos")
                print("4. Promotional materials")
                print("5. News/media coverage")
                
                perm_choice = input("Select permission type to update: ")
                perm_types = {
                    '1': 'website_photos',
                    '2': 'social_media',
                    '3': 'yearbook',
                    '4': 'promotional',
                    '5': 'media_coverage'
                }
                
                perm_type = perm_types.get(perm_choice)
                if not perm_type:
                    print("Invalid choice.")
                    return
                
                consent = input("Grant permission? (y/n): ").lower() == 'y'
                conditions = input("Any conditions or restrictions: ")
                
                valid_from = input("Valid from (YYYY-MM-DD, or leave blank for today): ")
                if not valid_from:
                    valid_from = datetime.datetime.now().strftime('%Y-%m-%d')
                
                valid_until = input("Valid until (YYYY-MM-DD, or leave blank for one year): ")
                if not valid_until:
                    future_date = datetime.datetime.now() + datetime.timedelta(days=365)
                    valid_until = future_date.strftime('%Y-%m-%d')
                
                # Validate dates
                try:
                    datetime.datetime.strptime(valid_from, '%Y-%m-%d')
                    datetime.datetime.strptime(valid_until, '%Y-%m-%d')
                except ValueError:
                    print("Invalid date format.")
                    return
                
                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return
                
                date_signed = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Remove any existing permission of this type
                cursor.execute('''
                DELETE FROM photo_permissions 
                WHERE student_id = ? AND permission_type = ?
                ''', (student_id, perm_type))
                
                # Insert new permission
                cursor.execute('''
                INSERT INTO photo_permissions 
                (student_id, permission_type, consent_given, conditions, valid_from, valid_until, 
                 parent_signature, date_signed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, perm_type, consent, conditions, valid_from, valid_until, 
                      parent_id, date_signed))
                
                conn.commit()
                
                status = "granted" if consent else "denied"
                print(f"Photo permission {status} successfully for {perm_type.replace('_', ' ')}.")
                
            except sqlite3.Error as e:
                print(f"Database error managing photo permissions: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    # ANALYTICS AND REPORTING
    def view_grade_analytics(self):
        """View grade trends and analytics"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view grade analytics.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_analytics'):
            print("You don't have permission to view analytics.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for grade analytics:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            
            if selected_child[6] == 'minimal':
                print("You have minimal access and cannot view analytics for this child.")
                return
            
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                # Get grade analytics
                cursor.execute('''
                SELECT m.module_name, ga.assessment_date, ga.grade_value, ga.class_average, 
                       ga.percentile_rank, ga.trend_direction
                FROM grade_analytics ga
                JOIN modules m ON ga.module_code = m.module_code
                WHERE ga.student_id = ?
                ORDER BY m.module_name, ga.assessment_date DESC
                ''', (student_id,))
                
                analytics = cursor.fetchall()
                
                print(f"\nGrade Analytics for {selected_child[1]} {selected_child[3]}:")
                
                if not analytics:
                    print("No grade analytics available yet.")
                    return
                
                # Group by module
                modules = {}
                for analytic in analytics:
                    module_name = analytic[0]
                    if module_name not in modules:
                        modules[module_name] = []
                    modules[module_name].append(analytic[1:])
                
                for module_name, grades in modules.items():
                    print(f"\n{module_name}:")
                    
                    # Calculate module statistics
                    recent_grades = [float(g[1]) for g in grades[:5]]  # Last 5 grades
                    class_averages = [float(g[2]) for g in grades[:5] if g[2]]
                    
                    if recent_grades:
                        student_avg = sum(recent_grades) / len(recent_grades)
                        if class_averages:
                            class_avg = sum(class_averages) / len(class_averages)
                            performance = "Above" if student_avg > class_avg else "Below" if student_avg < class_avg else "At"
                            print(f"  Recent average: {student_avg:.1f} ({performance} class average of {class_avg:.1f})")
                    
                    # Show recent assessments
                    print("  Recent assessments:")
                    for grade in grades[:3]:
                        date, grade_value, class_average, percentile, trend = grade
                        trend_arrow = "↗️" if trend == "improving" else "↘️" if trend == "declining" else "➡️"
                        print(f"    {date}: {grade_value}% (class avg: {class_average}%) {trend_arrow}")
                        if percentile:
                            print(f"              Percentile rank: {percentile}")
                
                # Overall performance summary
                all_grades = [float(a[2]) for a in analytics]
                if all_grades:
                    overall_avg = sum(all_grades) / len(all_grades)
                    print(f"\nOverall Performance:")
                    print(f"Average across all subjects: {overall_avg:.1f}%")
                    
                    # Performance trend
                    recent_avg = sum(all_grades[:10]) / min(10, len(all_grades))
                    older_avg = sum(all_grades[-10:]) / min(10, len(all_grades))
                    
                    if len(all_grades) > 10:
                        if recent_avg > older_avg + 2:
                            print("Trend: Improving ↗️")
                        elif recent_avg < older_avg - 2:
                            print("Trend: Declining ↘️")
                        else:
                            print("Trend: Stable ➡️")
                
            except sqlite3.Error as e:
                print(f"Database error viewing analytics: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def generate_qr_code(self):
        """Generate QR code for student pickup/identification"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to generate QR codes.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for QR code generation:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            student_id = selected_child[0]
            
            # Generate QR code data
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            qr_data = {
                'student_id': student_id,
                'parent_id': parent_id,
                'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'pickup_authorization'
            }
            
            qr_string = json.dumps(qr_data)
            
            try:
                # Generate QR code
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(qr_string)
                qr.make(fit=True)
                
                # In a real implementation, you would save this as an image file
                print(f"\nQR Code generated for {selected_child[1]} {selected_child[3]}")
                print("QR Code data:", qr_string)
                print("This QR code can be used for secure student pickup.")
                print("Note: In a real implementation, this would generate an actual image file.")
                
            except Exception as e:
                print(f"Error generating QR code: {e}")
                print("QR code generation requires the qrcode library.")
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    # CONVENIENCE FEATURES
    def quick_actions_menu(self):
        """Quick actions for busy parents"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to use quick actions.")
            return
        
        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        print("\nQuick Actions Menu:")
        print("==================")
        print("1. Quick absence report")
        print("2. Emergency contact update")
        print("3. View today's alerts")
        print("4. Check meal account balance")
        print("5. View urgent messages")
        print("6. Back to main menu")
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1':
            # Quick absence report
            children = self.view_children()
            if children and len(children) == 1:
                # If only one child, skip selection
                self._quick_absence_report(children[0])
            else:
                self.report_absence()
        
        elif choice == '2':
            self.emergency_contact_update()
        
        elif choice == '3':
            self._view_todays_alerts()
        
        elif choice == '4':
            self._quick_meal_balance_check()
        
        elif choice == '5':
            self._view_urgent_messages()
        
        elif choice == '6':
            return
        
        else:
            print("Invalid choice.")

    def _quick_absence_report(self, child):
        """Quick absence report for single child"""
        student_id = child[0]
        reason = input(f"Reason for {child[1]} {child[3]}'s absence today: ")
        
        if not reason:
            print("Absence report cancelled.")
            return
        
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            reported_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute(
                'INSERT INTO student_absences (student_id, absence_date, reason, reported_by, reported_date) VALUES (?, ?, ?, ?, ?)',
                (student_id, today, reason, f"parent:{parent_id}", reported_date)
            )
            
            conn.commit()
            print("Quick absence report submitted successfully.")
            
        except sqlite3.Error as e:
            print(f"Error submitting absence report: {e}")
        finally:
            if conn:
                conn.close()

    def _view_todays_alerts(self):
        """View today's alerts and important notices"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            
            print(f"\nToday's Alerts ({today}):")
            
            # Unread messages
            cursor.execute('''
            SELECT COUNT(*) FROM parent_messages
            WHERE parent_id = ? AND is_read = 0 AND is_from_parent = 0
            ''', (parent_id,))
            
            unread_count = cursor.fetchone()[0]
            if unread_count > 0:
                print(f"📧 {unread_count} unread message(s)")
            
            # Emergency alerts
            cursor.execute('''
            SELECT alert_title, alert_message FROM emergency_alerts
            WHERE active = 1 AND date(created_date) = ?
            ''', (today,))
            
            emergency_alerts = cursor.fetchall()
            for alert in emergency_alerts:
                print(f"🚨 EMERGENCY: {alert[0]}")
                print(f"   {alert[1]}")
            
            # Today's events
            cursor.execute('''
            SELECT event_name, start_time, location FROM school_calendar
            WHERE event_date = ? AND audience IN ('all', 'parents')
            ''', (today,))
            
            events = cursor.fetchall()
            for event in events:
                print(f"📅 {event[1]}: {event[0]} at {event[2]}")
            
            if unread_count == 0 and not emergency_alerts and not events:
                print("No alerts for today.")
            
        except sqlite3.Error as e:
            print(f"Error viewing alerts: {e}")
        finally:
            if conn:
                conn.close()

    def _quick_meal_balance_check(self):
        """Quick check of all children's meal balances"""
        children = self.view_children()
        
        if not children:
            print("No children registered.")
            return
        
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            print("\nMeal Account Balances:")
            
            for child in children:
                student_id = child[0]
                
                cursor.execute('SELECT balance, low_balance_threshold FROM meal_accounts WHERE student_id = ?', (student_id,))
                account = cursor.fetchone()
                
                if account:
                    balance, threshold = account
                    status = "⚠️ LOW" if float(balance) <= float(threshold) else "✅ OK"
                    print(f"  {child[1]} {child[3]}: £{balance:.2f} {status}")
                else:
                    print(f"  {child[1]} {child[3]}: No meal account")
            
        except sqlite3.Error as e:
            print(f"Error checking meal balances: {e}")
        finally:
            if conn:
                conn.close()

    def _view_urgent_messages(self):
        """View urgent/priority messages"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            
            # Get urgent messages (last 24 hours, unread)
            cursor.execute('''
            SELECT pm.message_content, pm.created_date, u.username as teacher_name, s.first_name, s.last_name
            FROM parent_messages pm
            JOIN users u ON pm.teacher_id = u.id
            JOIN students s ON pm.student_id = s.student_id
            WHERE pm.parent_id = ? AND pm.is_read = 0 AND pm.is_from_parent = 0
            AND datetime(pm.created_date) >= datetime('now', '-1 day')
            ORDER BY pm.created_date DESC
            LIMIT 5
            ''', (parent_id,))
            
            urgent_messages = cursor.fetchall()
            
            print("\nUrgent Messages (Last 24 hours):")
            
            if urgent_messages:
                for msg in urgent_messages:
                    content, date, teacher, student_first, student_last = msg
                    print(f"📨 From {teacher} re: {student_first} {student_last}")
                    print(f"   {date}: {content}")
                    print()
            else:
                print("No urgent messages.")
            
        except sqlite3.Error as e:
            print(f"Error viewing urgent messages: {e}")
        finally:
            if conn:
                conn.close()

    def advanced_notification_preferences(self):
        """Advanced notification settings"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage advanced preferences.")
            return
        
        if self.auth.current_user['role'] != 'parent':
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
            
            # Get current advanced preferences
            cursor.execute('''
            SELECT notification_timing, quiet_hours_start, quiet_hours_end
            FROM parent_preferences
            WHERE parent_id = ?
            ''', (parent_id,))
            
            prefs = cursor.fetchone()
            
            if not prefs:
                # Create default preferences
                cursor.execute('''
                INSERT INTO parent_preferences (parent_id, notification_timing, quiet_hours_start, quiet_hours_end)
                VALUES (?, '08:00', '20:00', '07:00')
                ''', (parent_id,))
                conn.commit()
                prefs = ('08:00', '20:00', '07:00')
            
            timing, quiet_start, quiet_end = prefs
            
            print("\nAdvanced Notification Preferences:")
            print(f"Current preferred notification time: {timing}")
            print(f"Quiet hours: {quiet_start} - {quiet_end}")
            
            print("\nOptions:")
            print("1. Change preferred notification time")
            print("2. Update quiet hours")
            print("3. Set subject-specific preferences")
            print("4. Back to menu")
            
            choice = input("Select option: ")
            
            if choice == '1':
                new_timing = input("Preferred notification time (HH:MM): ")
                try:
                    datetime.datetime.strptime(new_timing, '%H:%M')
                    cursor.execute('UPDATE parent_preferences SET notification_timing = ? WHERE parent_id = ?',
                                 (new_timing, parent_id))
                    conn.commit()
                    print("Notification timing updated.")
                except ValueError:
                    print("Invalid time format.")
            
            elif choice == '2':
                new_quiet_start = input(f"Quiet hours start (current: {quiet_start}): ")
                new_quiet_end = input(f"Quiet hours end (current: {quiet_end}): ")
                
                try:
                    datetime.datetime.strptime(new_quiet_start, '%H:%M')
                    datetime.datetime.strptime(new_quiet_end, '%H:%M')
                    
                    cursor.execute('''UPDATE parent_preferences 
                                   SET quiet_hours_start = ?, quiet_hours_end = ? 
                                   WHERE parent_id = ?''',
                                 (new_quiet_start, new_quiet_end, parent_id))
                    conn.commit()
                    print("Quiet hours updated.")
                except ValueError:
                    print("Invalid time format.")
            
            elif choice == '3':
                # Subject-specific preferences
                print("\n=== Subject-Specific Preferences ===")
                subjects = input("Enter subjects to get notifications for (comma-separated): ").split(',')
                subjects = [s.strip() for s in subjects if s.strip()]

                if subjects:
                    # Store preferences as JSON
                    import json
                    prefs_json = json.dumps({'subjects': subjects})
                    cursor.execute('''UPDATE parent_preferences
                                   SET subject_preferences = ?
                                   WHERE parent_id = ?''',
                                 (prefs_json, parent_id))
                    conn.commit()
                    print(f"Subject preferences updated: {', '.join(subjects)}")
                else:
                    print("No subjects entered.")
            
        except sqlite3.Error as e:
            print(f"Database error managing preferences: {e}")
        finally:
            if conn:
                conn.close()

    def report_issue(self):
        """Report an issue or concern to school administration"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to report an issue.")
            return

        if self.auth.current_user['role'] != 'parent':
            print("Only parents can report issues.")
            return

        parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])

        print("\n=== Report an Issue ===")
        print("1. Academic concern")
        print("2. Behavioral concern")
        print("3. Facility issue")
        print("4. Safety concern")
        print("5. Billing/Administrative")
        print("6. Other")

        category = input("Select issue category: ")
        category_map = {
            '1': 'Academic', '2': 'Behavioral', '3': 'Facility',
            '4': 'Safety', '5': 'Administrative', '6': 'Other'
        }

        category_name = category_map.get(category, 'Other')
        subject = input("Issue subject: ")
        description = input("Detailed description: ")
        priority = input("Priority (low/medium/high): ").lower()

        if priority not in ['low', 'medium', 'high']:
            priority = 'medium'

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                category TEXT,
                subject TEXT,
                description TEXT,
                priority TEXT,
                status TEXT DEFAULT 'open',
                created_date TEXT,
                resolved_date TEXT,
                response TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')

            cursor.execute('''
            INSERT INTO parent_issues (parent_id, category, subject, description, priority, created_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (parent_id, category_name, subject, description, priority, datetime.datetime.now().isoformat()))

            conn.commit()
            issue_id = cursor.lastrowid
            print(f"\nIssue reported successfully! Tracking ID: #{issue_id}")
            print("School administration will respond within 24-48 hours.")

        except sqlite3.Error as e:
            print(f"Database error reporting issue: {e}")
        finally:
            if conn:
                conn.close()

    def view_activity_log(self):
        """View parent account activity log"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view activity log.")
            return

        if self.auth.current_user['role'] != 'parent':
            print("Only parents can view activity logs.")
            return

        parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create activity log table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                activity_type TEXT,
                activity_description TEXT,
                ip_address TEXT,
                timestamp TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')

            # Fetch recent activities
            cursor.execute('''
            SELECT activity_type, activity_description, timestamp
            FROM parent_activity_log
            WHERE parent_id = ?
            ORDER BY timestamp DESC
            LIMIT 50
            ''', (parent_id,))

            activities = cursor.fetchall()

            print("\n=== Activity Log (Last 50 entries) ===")
            if activities:
                for act in activities:
                    print(f"[{act[2]}] {act[0]}: {act[1]}")
            else:
                print("No activity recorded yet.")

        except sqlite3.Error as e:
            print(f"Database error viewing activity log: {e}")
        finally:
            if conn:
                conn.close()

    def family_calendar_integration(self):
        """Export school events to family calendar"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to access calendar integration.")
            return

        if self.auth.current_user['role'] != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            # Get upcoming school events
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
            SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
            FROM school_calendar
            WHERE event_date >= ? AND audience IN ('all', 'parents')
            ORDER BY event_date
            LIMIT 20
            ''', (today,))
            
            events = cursor.fetchall()
            
            if not events:
                print("No upcoming events to export.")
                return
            
            print("\nCalendar Integration:")
            print("=====================")
            print(f"Found {len(events)} upcoming events")
            
            print("\nExport Options:")
            print("1. Generate iCal file (.ics)")
            print("2. Generate Google Calendar CSV")
            print("3. Display calendar URLs")
            print("4. Back to menu")
            
            choice = input("Select export option: ")
            
            if choice == '1':
                # Generate iCal content
                ical_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//School//Parent Portal//EN\n"
                
                for event in events:
                    name, description, date, start_time, end_time, location, event_type = event
                    
                    # Convert to iCal format
                    event_start = f"{date.replace('-', '')}T{start_time.replace(':', '')}00"
                    event_end = f"{date.replace('-', '')}T{end_time.replace(':', '')}00"
                    
                    ical_content += f"BEGIN:VEVENT\n"
                    ical_content += f"DTSTART:{event_start}\n"
                    ical_content += f"DTEND:{event_end}\n"
                    ical_content += f"SUMMARY:{name}\n"
                    ical_content += f"DESCRIPTION:{description or ''}\n"
                    ical_content += f"LOCATION:{location}\n"
                    ical_content += f"END:VEVENT\n"
                
                ical_content += "END:VCALENDAR\n"
                
                # In a real implementation, you would save this to a file
                print("\niCal file content generated:")
                print("Save the following content as 'school_events.ics':")
                print("-" * 50)
                print(ical_content)
                print("-" * 50)
            
            elif choice == '2':
                print("\nGoogle Calendar CSV format:")
                print("Subject,Start Date,Start Time,End Date,End Time,Description,Location")
                
                for event in events:
                    name, description, date, start_time, end_time, location, event_type = event
                    print(f'"{name}",{date},{start_time},{date},{end_time},"{description or ""}","{location}"')
            
            elif choice == '3':
                print("\nCalendar Subscription URLs:")
                print("(In a real implementation, these would be actual URLs)")
                print(f"School Events: https://school.example.com/calendar/parent/{self.get_parent_id_from_user(self.auth.current_user['id'])}")
                print("Add this URL to your calendar app to automatically sync school events.")
            
        except sqlite3.Error as e:
            print(f"Database error accessing calendar: {e}")
        finally:
            if conn:
                conn.close()

    # LOG ACTIVITY FOR SECURITY
    def log_activity(self, action, details=""):
        """Log parent activity for security purposes"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if parent_id:
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO parent_activity_log 
                (parent_id, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                ''', (parent_id, action, details, timestamp))
                
                conn.commit()
        except sqlite3.Error:
            pass  # Don't fail the main operation if logging fails
        finally:
            if conn:
                conn.close()

    @staticmethod
    def display_parent_portal_menu(auth):
        """Display the enhanced parent portal menu"""
        if not auth or not auth.current_user:
            print("You must be logged in to access the parent portal.")
            return
        
        if auth.current_user['role'] != 'parent' and auth.current_user['role'] != 'admin':
            print("This function is only available for parent accounts and administrators.")
            return
        
        portal = ParentPortal(auth)
        is_admin = auth.current_user['role'] == 'admin'
        
        while True:
            print("\n" + "=" * 60)
            print("ENHANCED PARENT PORTAL")
            print("=" * 60)
            
            if is_admin:
                print("ADMINISTRATOR MODE")
                print("\nParent Management:")
                print("1. Create Parent Account")
                print("2. Link Student to Parent")
                print("3. View Parent Dashboard")
                print("4. Return to Main Menu")
                
                choice = input("\nEnter your choice (1-4): ")
                
                if choice == '1':
                    portal.create_parent_account()
                elif choice == '2':
                    portal.link_student_to_parent()
                elif choice == '3':
                    portal.view_parent_dashboard()
                elif choice == '4':
                    return
                else:
                    print("Invalid choice. Please try again.")
            else:
                # Enhanced parent menu
                print("\n🏠 MAIN DASHBOARD")
                print("1. Dashboard Overview")
                print("2. Quick Actions")
                
                print("\n👥 MY CHILDREN")
                print("3. View Children")
                print("4. Academic Records")
                print("5. Attendance & Behavior")
                print("6. Health & Safety")
                
                print("\n💬 COMMUNICATION")
                print("7. Messages & Announcements")
                print("8. Schedule Meetings")
                print("9. Report Issues")
                
                print("\n💰 FINANCIAL")
                print("10. Fees & Payments")
                print("11. Meal Accounts")
                print("12. Fundraising")
                
                print("\n📚 ACADEMIC SUPPORT")
                print("13. Homework & Assignments")
                print("14. Academic Goals")
                print("15. Grade Analytics")
                
                print("\n⚙️ SETTINGS & TOOLS")
                print("16. Notification Preferences")
                print("17. Document Management")
                print("18. Calendar Integration")
                print("19. Account Settings")
                
                print("\n0. Logout")
                
                choice = input("\nEnter your choice (0-19): ")
                
                # Log the menu access
                portal.log_activity("menu_access", f"Selected option: {choice}")
                
                if choice == '0':
                    return
                elif choice == '1':
                    portal.view_parent_dashboard()
                elif choice == '2':
                    portal.quick_actions_menu()
                elif choice == '3':
                    children = portal.view_children()
                    if children:
                        print("\nYour children:")
                        for i, child in enumerate(children):
                            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")
                    else:
                        print("You have no children registered in the system.")
                elif choice == '4':
                    print("\nAcademic Records:")
                    print("1. View Grades")
                    print("2. View Teacher Reports")
                    print("3. View Timetable")
                    
                    sub_choice = input("Select option: ")
                    if sub_choice == '1':
                        portal.view_child_grades()
                    elif sub_choice == '2':
                        portal.view_teacher_reports()
                    elif sub_choice == '3':
                        portal.view_child_timetable()
                
                elif choice == '5':
                    print("\nAttendance & Behavior:")
                    print("1. View Attendance")
                    print("2. View Behavior Reports")
                    print("3. Report Absence")
                    
                    sub_choice = input("Select option: ")
                    if sub_choice == '1':
                        portal.view_child_attendance()
                    elif sub_choice == '2':
                        portal.view_behavior_reports()
                    elif sub_choice == '3':
                        portal.report_absence()
                
                elif choice == '6':
                    print("\nHealth & Safety:")
                    print("1. Medical Information")
                    print("2. Transportation")
                    print("3. Pickup Authorization")
                    print("4. Photo Permissions")
                    
                    sub_choice = input("Select option: ")
                    if sub_choice == '1':
                        portal.view_medical_information()
                    elif sub_choice == '2':
                        portal.view_transportation_info()
                    elif sub_choice == '3':
                        portal.manage_pickup_authorization()
                    elif sub_choice == '4':
                        portal.manage_photo_permissions()
                
                elif choice == '7':
                    print("\nCommunication:")
                    print("1. View Messages")
                    print("2. Send Message to Teacher")
                    print("3. Send Group Message")
                    print("4. School Announcements")
                    
                    sub_choice = input("Select option: ")
                    if sub_choice == '1':
                        portal.view_messages()
                    elif sub_choice == '2':
                        portal.send_message_to_teacher()
                    elif sub_choice == '3':
                        portal.send_group_message()
                    elif sub_choice == '4':
                        portal.view_school_announcements()
                
                elif choice == '8':
                    portal.schedule_parent_teacher_meeting()
                
                elif choice == '9':
                    # Report Issues
                    portal.report_issue()
                
                elif choice == '10':
                    portal.view_student_fees()
                
                elif choice == '11':
                    portal.manage_meal_account()
                
                elif choice == '12':
                    portal.view_fundraising_campaigns()
                
                elif choice == '13':
                    print("\nHomework & Assignments:")
                    print("1. View Homework")
                    print("2. View Assignments")
                    print("3. View Library Account")
                    print("4. Extracurricular Activities")
                    
                    sub_choice = input("Select option: ")
                    if sub_choice == '1':
                        portal.view_homework_tracking()
                    elif sub_choice == '2':
                        portal.view_child_assignments()
                    elif sub_choice == '3':
                        portal.view_library_account()
                    elif sub_choice == '4':
                        portal.view_extracurricular_activities()
                
                elif choice == '14':
                    portal.manage_academic_goals()
                
                elif choice == '15':
                    portal.view_grade_analytics()
                
                elif choice == '16':
                    print("\nNotification Preferences:")
                    print("1. Basic Preferences")
                    print("2. Advanced Preferences")
                    
                    sub_choice = input("Select option: ")
                    if sub_choice == '1':
                        portal.update_notification_preferences()
                    elif sub_choice == '2':
                        portal.advanced_notification_preferences()
                
                elif choice == '17':
                    portal.manage_documents()
                
                elif choice == '18':
                    print("\nCalendar & Events:")
                    print("1. View School Calendar")
                    print("2. Family Calendar Integration")
                    
                    sub_choice = input("Select option: ")
                    if sub_choice == '1':
                        portal.view_school_calendar()
                    elif sub_choice == '2':
                        portal.family_calendar_integration()
                
                elif choice == '19':
                    print("\nAccount Settings:")
                    print("1. Update Contact Information")
                    print("2. Emergency Contact Update")
                    print("3. Generate QR Code")
                    print("4. View Activity Log")
                    
                    sub_choice = input("Select option: ")
                    if sub_choice == '1':
                        portal.update_contact_info()
                    elif sub_choice == '2':
                        portal.emergency_contact_update()
                    elif sub_choice == '3':
                        portal.generate_qr_code()
                    elif sub_choice == '4':
                        portal.view_activity_log()
                
                else:
                    print("Invalid choice. Please try again.")
                
                # Pause before showing menu again
                input("\nPress Enter to continue...")

def init_parent_portal(auth):
    """Initialize the parent portal module"""
    parent_portal = ParentPortal(auth)
    parent_portal.setup_parent_permissions()
    return parent_portal

def display_parent_portal_menu(auth=None):
    """Display the parent portal menu - main entry point from the main menu"""
    if auth is None:
        print("Authentication is required to access the parent portal.")
        return
    # Call the static method with the auth parameter
    ParentPortal.display_parent_portal_menu(auth)

def integrate_parent_portal_with_main():
    """Add needed functions to integrate parent portal with main system"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()
        
        # FIRST: Ensure all parent portal tables exist before creating triggers
        # This duplicates some of the work from parent_portal.py to ensure tables exist
        
        # Create parent_accounts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT UNIQUE,
            first_name TEXT,
            last_name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            address TEXT,
            emergency_contact BOOLEAN DEFAULT 0,
            registration_date TEXT
        )
        ''')
        
        # Create parent_student_relationships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_student_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT,
            student_id TEXT,
            relationship_type TEXT,
            access_level TEXT DEFAULT 'full',
            date_added TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Create parent notifications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT,
            student_id TEXT,
            notification_type TEXT,
            notification_content TEXT,
            created_date TEXT,
            read_status BOOLEAN DEFAULT 0,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Create parent_preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT UNIQUE,
            email_notifications BOOLEAN DEFAULT 1,
            sms_notifications BOOLEAN DEFAULT 0,
            grade_alerts BOOLEAN DEFAULT 1,
            attendance_alerts BOOLEAN DEFAULT 1,
            behavior_alerts BOOLEAN DEFAULT 1,
            assignment_alerts BOOLEAN DEFAULT 0,
            weekly_summary BOOLEAN DEFAULT 1,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
        )
        ''')
        
        # Create teacher_reports table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            teacher_id INTEGER,
            module_code TEXT,
            report_type TEXT,
            report_content TEXT,
            created_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')
        
        # Create parent_messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT,
            teacher_id INTEGER,
            student_id TEXT,
            message_content TEXT,
            created_date TEXT,
            is_read BOOLEAN DEFAULT 0,
            is_from_parent BOOLEAN,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Add parent-teacher relationship table if needed
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_student_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER,
            student_id TEXT,
            permission_type TEXT,
            FOREIGN KEY (teacher_id) REFERENCES users (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # NOW: Create triggers after ensuring all tables exist
        
        # Drop existing triggers first to avoid conflicts
        cursor.execute('DROP TRIGGER IF EXISTS notify_parent_on_grade')
        cursor.execute('DROP TRIGGER IF EXISTS notify_parent_on_absence')
        
        # Set up grade notification triggers
        cursor.execute('''
        CREATE TRIGGER notify_parent_on_grade
        AFTER INSERT ON student_grades
        BEGIN
            INSERT INTO parent_notifications (
                parent_id,
                student_id,
                notification_type,
                notification_content,
                created_date,
                read_status
            )
            SELECT 
                psr.parent_id,
                NEW.student_id,
                'grade',
                'New grade recorded: ' || NEW.assessment_name || ' - ' || NEW.grade,
                datetime('now'),
                0
            FROM parent_student_relationships psr
            JOIN parent_preferences pp ON psr.parent_id = pp.parent_id
            WHERE psr.student_id = NEW.student_id AND pp.grade_alerts = 1;
        END;
        ''')
        
        # Set up attendance notification triggers
        cursor.execute('''
        CREATE TRIGGER notify_parent_on_absence
        AFTER INSERT ON attendance
        WHEN NEW.status != 'present'
        BEGIN
            INSERT INTO parent_notifications (
                parent_id,
                student_id,
                notification_type,
                notification_content,
                created_date,
                read_status
            )
            SELECT 
                psr.parent_id,
                NEW.student_id,
                'attendance',
                'Absence recorded: ' || NEW.status || ' on ' || NEW.date,
                datetime('now'),
                0
            FROM parent_student_relationships psr
            JOIN parent_preferences pp ON psr.parent_id = pp.parent_id
            WHERE psr.student_id = NEW.student_id AND pp.attendance_alerts = 1;
        END;
        ''')
        
        # Modify permissions table to include parent permissions
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
        
        conn.commit()
        conn.close()
        print("Parent portal integration complete!")
        return True
    except sqlite3.Error as e:
        print(f"Error integrating parent portal: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False
    
def get_student_parent_relationships(student_id):
    """Get parent information for a student - utility for other modules"""
    conn = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT p.parent_id, p.first_name, p.last_name, p.email, p.phone, p.emergency_contact, 
               psr.relationship_type, psr.access_level
        FROM parent_accounts p
        JOIN parent_student_relationships psr ON p.parent_id = psr.parent_id
        WHERE psr.student_id = ?
        ''', (student_id,))
        
        parents = cursor.fetchall()
        return parents
    except sqlite3.Error as e:
        print(f"Error retrieving parent relationships: {e}")
        return []
    finally:
        if conn:
            conn.close()

def send_parent_notification(student_id, notification_type, content):
    """Send a notification to all parents of a student - utility for other modules"""
    conn = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()
        
        # Get parents with appropriate notification preferences
        if notification_type == 'grade':
            preference_column = 'grade_alerts'
        elif notification_type == 'attendance':
            preference_column = 'attendance_alerts'
        elif notification_type == 'behavior':
            preference_column = 'behavior_alerts'
        elif notification_type == 'assignment':
            preference_column = 'assignment_alerts'
        else:
            preference_column = None
        
        if preference_column:
            query = f'''
            INSERT INTO parent_notifications (
                parent_id,
                student_id,
                notification_type,
                notification_content,
                created_date,
                read_status
            )
            SELECT 
                psr.parent_id,
                ?,
                ?,
                ?,
                datetime('now'),
                0
            FROM parent_student_relationships psr
            JOIN parent_preferences pp ON psr.parent_id = pp.parent_id
            WHERE psr.student_id = ? AND pp.{preference_column} = 1
            '''
        else:
            # If no specific preference, send to all parents
            query = '''
            INSERT INTO parent_notifications (
                parent_id,
                student_id,
                notification_type,
                notification_content,
                created_date,
                read_status
            )
            SELECT 
                psr.parent_id,
                ?,
                ?,
                ?,
                datetime('now'),
                0
            FROM parent_student_relationships psr
            WHERE psr.student_id = ?
            '''
        
        cursor.execute(query, (student_id, notification_type, content, student_id))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error sending parent notification: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def add_teacher_report(student_id, teacher_id, module_code, report_type, content):
    """Add a teacher report for a student - utility for other modules"""
    conn = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()
        
        # Insert report
        cursor.execute('''
        INSERT INTO teacher_reports (
            student_id,
            teacher_id,
            module_code,
            report_type,
            report_content,
            created_date
        ) VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', (student_id, teacher_id, module_code, report_type, content))
        
        # Get ID of the new report
        report_id = cursor.lastrowid
        
        # Commit the report before sending notification
        conn.commit()
        
        # Notify parents (use a separate function call to avoid nested transactions)
        send_parent_notification(
            student_id, 
            'report', 
            f"New {report_type} report has been added for module {module_code}"
        )
        
        return report_id
    except sqlite3.Error as e:
        print(f"Error adding teacher report: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

# Missing functions to add to parent_portal.py

def view_activity_log(self):
    """View parent activity log for security purposes"""
    if not self.auth or not self.auth.current_user:
        print("You must be logged in to view activity log.")
        return
    
    if self.auth.current_user['role'] != 'parent':
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
        
        # Get recent activity log entries
        cursor.execute('''
        SELECT action, details, ip_address, user_agent, timestamp
        FROM parent_activity_log
        WHERE parent_id = ?
        ORDER BY timestamp DESC
        LIMIT 50
        ''', (parent_id,))
        
        activities = cursor.fetchall()
        
        print(f"\nActivity Log:")
        print("=" * 60)
        
        if not activities:
            print("No activity recorded.")
            return
        
        for activity in activities:
            action, details, ip_address, user_agent, timestamp = activity
            print(f"[{timestamp}] {action}")
            if details:
                print(f"  Details: {details}")
            if ip_address:
                print(f"  IP: {ip_address}")
            print()
        
    except sqlite3.Error as e:
        print(f"Database error viewing activity log: {e}")
    finally:
        if conn:
            conn.close()

def enable_two_factor_auth(self):
    """Enable two-factor authentication for parent account"""
    if not self.auth or not self.auth.current_user:
        print("You must be logged in to enable two-factor authentication.")
        return
    
    if self.auth.current_user['role'] != 'parent':
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

def view_all_transactions(self, student_id):
    """View all meal account transactions for a student"""
    conn = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()
        
        # Get all transactions
        cursor.execute('''
        SELECT transaction_type, amount, description, transaction_date, balance_after
        FROM meal_transactions
        WHERE student_id = ?
        ORDER BY transaction_date DESC
        ''', (student_id,))
        
        transactions = cursor.fetchall()
        
        if not transactions:
            print("No transactions found.")
            return
            
        print("\nAll Meal Account Transactions:")
        print("-" * 60)
        
        for transaction in transactions:
            trans_type, amount, description, date, balance_after = transaction
            print(f"{date}: {trans_type.upper()} £{amount:.2f}")
            print(f"  Description: {description}")
            print(f"  Balance after: £{balance_after:.2f}")
            print()
            
    except sqlite3.Error as e:
        print(f"Database error viewing transactions: {e}")
    finally:
        if conn:
            conn.close()

def donate_to_campaign(self):
    """Make a donation to a fundraising campaign"""
    if not self.auth or not self.auth.current_user:
        print("You must be logged in to make donations.")
        return
    
    if self.auth.current_user['role'] != 'parent':
        print("This function is only available for parent accounts.")
        return
    
    conn = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()
        
        # Get active campaigns
        cursor.execute('''
        SELECT id, campaign_name, description, target_amount, current_amount
        FROM fundraising_campaigns
        WHERE status = 'active' AND end_date >= date('now')
        ORDER BY campaign_name
        ''')
        
        campaigns = cursor.fetchall()
        
        if not campaigns:
            print("No active fundraising campaigns at this time.")
            return
        
        print("\nSelect campaign to donate to:")
        for i, campaign in enumerate(campaigns):
            id, name, description, target, current = campaign
            remaining = float(target) - float(current)
            print(f"{i+1}. {name}")
            print(f"   Target: £{target:.2f}, Raised: £{current:.2f}, Remaining: £{remaining:.2f}")
            print(f"   {description}")
            print()
        
        choice = input("Enter campaign number: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(campaigns):
                raise ValueError
            
            selected_campaign = campaigns[index]
            campaign_id = selected_campaign[0]
            
            # Get donation details
            amount = float(input("Enter donation amount: £"))
            if amount <= 0:
                print("Invalid donation amount.")
                return
            
            children = self.view_children()
            if children:
                print("\nDonate on behalf of (optional):")
                print("0. Anonymous donation")
                for i, child in enumerate(children):
                    print(f"{i+1}. {child[1]} {child[3]}")
                
                child_choice = input("Enter choice: ")
                if child_choice == '0':
                    student_id = None
                    anonymous = True
                else:
                    try:
                        child_index = int(child_choice) - 1
                        if 0 <= child_index < len(children):
                            student_id = children[child_index][0]
                            anonymous = False
                        else:
                            student_id = None
                            anonymous = True
                    except ValueError:
                        student_id = None
                        anonymous = True
            else:
                student_id = None
                anonymous = True
            
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return
            
            donation_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Record donation
            cursor.execute('''
            INSERT INTO fundraising_donations
            (campaign_id, parent_id, student_id, amount, donation_date, anonymous)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (campaign_id, parent_id, student_id, amount, donation_date, anonymous))
            
            # Update campaign total
            cursor.execute('''
            UPDATE fundraising_campaigns
            SET current_amount = current_amount + ?
            WHERE id = ?
            ''', (amount, campaign_id))
            
            conn.commit()
            print(f"Thank you for your donation of £{amount:.2f}!")
            
        except (ValueError, IndexError):
            print("Invalid selection.")
        except ValueError:
            print("Invalid donation amount.")
            
    except sqlite3.Error as e:
        print(f"Database error processing donation: {e}")
    finally:
        if conn:
            conn.close()

def update_profile_photo(self):
    """Update parent profile photo"""
    if not self.auth or not self.auth.current_user:
        print("You must be logged in to update profile photo.")
        return
    
    if self.auth.current_user['role'] != 'parent':
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

def export_child_data(self):
    """Export all data for a child (for data portability)"""
    if not self.auth or not self.auth.current_user:
        print("You must be logged in to export data.")
        return
    
    if self.auth.current_user['role'] != 'parent':
        print("This function is only available for parent accounts.")
        return
    
    children = self.view_children()
    
    if not children:
        print("You have no children registered in the system.")
        return
    
    print("\nSelect child to export data for:")
    for i, child in enumerate(children):
        print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
    
    choice = input("Enter the number of the child: ")
    try:
        index = int(choice) - 1
        if index < 0 or index >= len(children):
            raise ValueError
        
        selected_child = children[index]
        student_id = selected_child[0]
        
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()
            
            export_data = {
                'student_info': {
                    'student_id': student_id,
                    'name': f"{selected_child[1]} {selected_child[3]}",
                    'course': selected_child[4]
                },
                'export_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data': {}
            }
            
            # Export various data types
            tables_to_export = [
                ('grades', 'student_grades', 'student_id'),
                ('attendance', 'attendance', 'student_id'),
                ('assignments', 'homework_assignments', 'student_id'),
                ('behavior', 'student_behavior', 'student_id'),
                ('medical', 'student_medical_info', 'student_id'),
                ('fees', 'student_fees', 'student_id'),
                ('meal_transactions', 'meal_transactions', 'student_id'),
                ('library', 'library_accounts', 'student_id'),
                ('activities', 'student_activities', 'student_id')
            ]
            
            for data_type, table_name, id_column in tables_to_export:
                try:
                    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                    if cursor.fetchone():
                        cursor.execute(f"SELECT * FROM {table_name} WHERE {id_column} = ?", (student_id,))
                        rows = cursor.fetchall()
                        
                        # Get column names
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = [col[1] for col in cursor.fetchall()]
                        
                        # Convert to list of dictionaries
                        export_data['data'][data_type] = [
                            dict(zip(columns, row)) for row in rows
                        ]
                except sqlite3.Error:
                    export_data['data'][data_type] = []
            
            # Generate export file content
            import json
            export_json = json.dumps(export_data, indent=2, default=str)
            
            print(f"\nData export completed for {selected_child[1]} {selected_child[3]}")
            print("Export file content (save as JSON file):")
            print("=" * 60)
            print(export_json)
            print("=" * 60)
            
            # Log the activity
            self.log_activity("data_export", f"Data exported for student {student_id}")
            
        except sqlite3.Error as e:
            print(f"Database error exporting data: {e}")
        finally:
            if conn:
                conn.close()
        
    except (ValueError, IndexError):
        print("Invalid choice.")

# Additional utility function for better menu organization
def get_notification_count(self):
    """Get count of unread notifications for dashboard"""
    conn = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()
        
        parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
        if not parent_id:
            return 0
        
        cursor.execute('''
        SELECT COUNT(*) FROM parent_notifications
        WHERE parent_id = ? AND read_status = 0
        ''', (parent_id,))
        
        count = cursor.fetchone()[0]
        return count
        
    except sqlite3.Error:
        return 0
    finally:
        if conn:
            conn.close()

def mark_notifications_read(self):
    """Mark all notifications as read"""
    if not self.auth or not self.auth.current_user:
        print("You must be logged in to mark notifications as read.")
        return
    
    if self.auth.current_user['role'] != 'parent':
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
        
        cursor.execute('''
        UPDATE parent_notifications
        SET read_status = 1
        WHERE parent_id = ? AND read_status = 0
        ''', (parent_id,))
        
        updated_count = cursor.rowcount
        conn.commit()
        
        print(f"Marked {updated_count} notifications as read.")

    except sqlite3.Error as e:
        print(f"Database error marking notifications as read: {e}")
    finally:
        if conn:
            conn.close()


# GUI Launcher using factory pattern
try:
    from university_system.modules.shared.feature_gui_factory import create_gui_launcher

    launch_parent_portal_gui = create_gui_launcher(
        title="Parent Portal Enhancement",
        description="""Comprehensive parent portal for student monitoring and communication.

Features:
• Parent access management
• Student progress monitoring
• Grade and attendance viewing
• Communication preferences
• Financial information access
• Academic records viewing
• Event calendar & notifications
• Permission management
• Meeting requests
• Document access
• Activity logging
• Multi-student support""",
        cli_instruction="Use CLI: Parent Portal Enhancement"
    )
except ImportError:
    # Fallback if factory not available
    def launch_parent_portal_gui(root, auth):
        from tkinter import messagebox
        messagebox.showinfo("Parent Portal", "Please use the CLI: Parent Portal Enhancement")


# Alias for consistency - both names refer to the same comprehensive system
display_parent_portal_enhancement_menu = display_parent_portal_menu


# Export public API
__all__ = [
    'ParentPortal',
    'display_parent_portal_menu',
    'display_parent_portal_enhancement_menu',
    'launch_parent_portal_gui',
    'integrate_parent_portal_with_main',
]
