from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
import datetime


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

        # school_calendar removed — folded into the single canonical
        # academic_calendar_events table.

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

        # NOTE: meal transactions now use the unified 'transactions' table
        # with source_type = 'meal'

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

        # Parent documents now use the unified documents table with source_type = 'parent'
        # No separate parent_documents table needed

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
