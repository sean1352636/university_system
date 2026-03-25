"""
Gym/Fitness Center Core Services

Provides comprehensive gym management including memberships,
class bookings, equipment tracking, and personal training with
email and finance integration.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Constants
MEMBERSHIP_TYPES = {
    'basic': {'name': 'Basic', 'monthly_fee': 25.00, 'features': ['gym_access']},
    'standard': {'name': 'Standard', 'monthly_fee': 40.00, 'features': ['gym_access', 'classes']},
    'premium': {'name': 'Premium', 'monthly_fee': 60.00, 'features': ['gym_access', 'classes', 'pool', 'sauna']},
    'student': {'name': 'Student', 'monthly_fee': 15.00, 'features': ['gym_access', 'classes']},
    'staff': {'name': 'Staff', 'monthly_fee': 20.00, 'features': ['gym_access', 'classes', 'pool']}
}

CLASS_TYPES = ['yoga', 'pilates', 'spinning', 'hiit', 'strength', 'cardio', 'swimming', 'boxing', 'dance', 'meditation']

EQUIPMENT_CATEGORIES = ['cardio', 'strength', 'free_weights', 'machines', 'accessories']

PT_SESSION_FEES = {
    'single': 35.00,
    'package_5': 150.00,
    'package_10': 280.00
}

def generate_membership_id() -> str:
    """Generate a unique membership ID."""
    return f"GYM-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

def generate_booking_ref() -> str:
    """Generate a unique booking reference."""
    return f"BK-{uuid.uuid4().hex[:8].upper()}"

def generate_reference() -> str:
    """Generate a unique reference number."""
    return f"REF-{uuid.uuid4().hex[:12].upper()}"

def init_gym_db():
    """Initialize gym database tables."""
    try:
        with transaction() as conn:
            # Memberships table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS gym_memberships (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_number TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    user_email TEXT,
                    user_phone TEXT,
                    membership_type TEXT NOT NULL,
                    monthly_fee DECIMAL(10,2) NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE,
                    status TEXT DEFAULT 'active',
                    auto_renew INTEGER DEFAULT 1,
                    emergency_contact TEXT,
                    emergency_phone TEXT,
                    health_conditions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            ''')

            # Fitness classes table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS gym_classes (
                    class_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_name TEXT NOT NULL,
                    class_type TEXT NOT NULL,
                    instructor_id TEXT,
                    instructor_name TEXT NOT NULL,
                    schedule_day TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    location TEXT NOT NULL,
                    max_capacity INTEGER DEFAULT 20,
                    current_enrolled INTEGER DEFAULT 0,
                    description TEXT,
                    difficulty_level TEXT DEFAULT 'all_levels',
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Class bookings table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS gym_class_bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_ref TEXT UNIQUE NOT NULL,
                    class_id INTEGER NOT NULL,
                    member_id INTEGER NOT NULL,
                    booking_date DATE NOT NULL,
                    status TEXT DEFAULT 'confirmed',
                    attended INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (class_id) REFERENCES gym_classes(class_id),
                    FOREIGN KEY (member_id) REFERENCES gym_memberships(membership_id)
                )
            ''')

            # Equipment table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS gym_equipment (
                    equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    brand TEXT,
                    model TEXT,
                    serial_number TEXT,
                    purchase_date DATE,
                    location TEXT,
                    status TEXT DEFAULT 'available',
                    last_maintenance DATE,
                    next_maintenance DATE,
                    notes TEXT
                )
            ''')

            # Personal training sessions
            conn.execute('''
                CREATE TABLE IF NOT EXISTS gym_pt_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_ref TEXT UNIQUE NOT NULL,
                    member_id INTEGER NOT NULL,
                    trainer_id TEXT,
                    trainer_name TEXT NOT NULL,
                    session_date DATE NOT NULL,
                    session_time TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 60,
                    session_type TEXT DEFAULT 'single',
                    fee DECIMAL(10,2) NOT NULL,
                    payment_status TEXT DEFAULT 'pending',
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (member_id) REFERENCES gym_memberships(membership_id)
                )
            ''')

            # NOTE: gym transactions now use the unified 'transactions' table
            # with source_type = 'gym'

            # Gym attendance log
            conn.execute('''
                CREATE TABLE IF NOT EXISTS gym_attendance (
                    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_id INTEGER NOT NULL,
                    check_in TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    check_out TIMESTAMP,
                    FOREIGN KEY (member_id) REFERENCES gym_memberships(membership_id)
                )
            ''')

            # Initialize some default classes if empty
            cursor = conn.execute("SELECT COUNT(*) FROM gym_classes")
            if cursor.fetchone()[0] == 0:
                default_classes = [
                    ('Morning Yoga', 'yoga', 'Sarah Johnson', 'Monday', '07:00', '08:00', 'Studio A', 25),
                    ('HIIT Blast', 'hiit', 'Mike Thompson', 'Monday', '12:00', '13:00', 'Main Floor', 20),
                    ('Spin Class', 'spinning', 'Emma Wilson', 'Tuesday', '18:00', '19:00', 'Spin Room', 15),
                    ('Strength Training', 'strength', 'James Brown', 'Wednesday', '17:00', '18:00', 'Weight Room', 12),
                    ('Pilates', 'pilates', 'Lisa Chen', 'Thursday', '10:00', '11:00', 'Studio B', 20),
                    ('Boxing Basics', 'boxing', 'David Miller', 'Friday', '16:00', '17:00', 'Boxing Area', 10),
                    ('Aqua Aerobics', 'swimming', 'Rachel Green', 'Saturday', '09:00', '10:00', 'Pool', 15),
                    ('Meditation', 'meditation', 'Sarah Johnson', 'Sunday', '08:00', '09:00', 'Studio A', 30)
                ]
                for cls in default_classes:
                    conn.execute('''
                        INSERT INTO gym_classes
                        (class_name, class_type, instructor_name, schedule_day, start_time,
                         end_time, location, max_capacity)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', cls)

        return True
    except Exception as e:
        print(f"Error initializing gym database: {e}")
        return False

class MembershipManager:
    """Manages gym memberships."""

    @staticmethod
    def create_membership(user_id: str, user_name: str, user_email: str,
                         membership_type: str, months: int = 1,
                         emergency_contact: str = None, emergency_phone: str = None,
                         health_conditions: str = None, created_by: str = None) -> Optional[Dict]:
        """Create a new gym membership."""
        try:
            if membership_type not in MEMBERSHIP_TYPES:
                return None

            member_number = generate_membership_id()
            membership = MEMBERSHIP_TYPES[membership_type]
            monthly_fee = membership['monthly_fee']
            total_fee = monthly_fee * months

            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=30 * months)

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO gym_memberships
                    (member_number, user_id, user_name, user_email, membership_type,
                     monthly_fee, start_date, end_date, emergency_contact,
                     emergency_phone, health_conditions, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (member_number, user_id, user_name, user_email, membership_type,
                      monthly_fee, start_date.isoformat(), end_date.isoformat(),
                      emergency_contact, emergency_phone, health_conditions, created_by))

                membership_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            log_activity('create', 'gym_membership',
                        details={'membership_id': membership_id, 'member_number': member_number, 'type': membership_type})

            return {
                'membership_id': membership_id,
                'member_number': member_number,
                'total_fee': total_fee,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        except Exception as e:
            print(f"Error creating membership: {e}")
            return None

    @staticmethod
    def get_membership(membership_id: int = None, user_id: str = None,
                      member_number: str = None) -> Optional[Dict]:
        """Get membership details."""
        try:
            with get_connection() as conn:
                if membership_id:
                    cursor = conn.execute(
                        "SELECT * FROM gym_memberships WHERE membership_id = ?", (membership_id,))
                elif member_number:
                    cursor = conn.execute(
                        "SELECT * FROM gym_memberships WHERE member_number = ?", (member_number,))
                else:
                    cursor = conn.execute(
                        "SELECT * FROM gym_memberships WHERE user_id = ? AND status = 'active'", (user_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting membership: {e}")
            return None

    @staticmethod
    def get_all_memberships(status: str = None) -> List[Dict]:
        """Get all memberships."""
        try:
            with get_connection() as conn:
                if status:
                    cursor = conn.execute(
                        "SELECT * FROM gym_memberships WHERE status = ? ORDER BY created_at DESC",
                        (status,))
                else:
                    cursor = conn.execute(
                        "SELECT * FROM gym_memberships ORDER BY created_at DESC")
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting memberships: {e}")
            return []

    @staticmethod
    def renew_membership(membership_id: int, months: int = 1) -> Optional[Dict]:
        """Renew a membership."""
        try:
            membership = MembershipManager.get_membership(membership_id=membership_id)
            if not membership:
                return None

            current_end = datetime.fromisoformat(membership['end_date'])
            new_start = max(current_end, datetime.now()).date()
            new_end = new_start + timedelta(days=30 * months)
            total_fee = membership['monthly_fee'] * months

            with transaction() as conn:
                conn.execute('''
                    UPDATE gym_memberships
                    SET end_date = ?, status = 'active'
                    WHERE membership_id = ?
                ''', (new_end.isoformat(), membership_id))

            return {
                'new_end_date': new_end.isoformat(),
                'total_fee': total_fee
            }
        except Exception as e:
            print(f"Error renewing membership: {e}")
            return None

    @staticmethod
    def cancel_membership(membership_id: int) -> bool:
        """Cancel a membership."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE gym_memberships SET status = 'cancelled' WHERE membership_id = ?
                ''', (membership_id,))
            return True
        except Exception as e:
            print(f"Error cancelling membership: {e}")
            return False

    @staticmethod
    def check_in(membership_id: int) -> Optional[int]:
        """Record member check-in."""
        try:
            with transaction() as conn:
                conn.execute('''
                    INSERT INTO gym_attendance (member_id) VALUES (?)
                ''', (membership_id,))
                return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        except Exception as e:
            print(f"Error checking in: {e}")
            return None

    @staticmethod
    def check_out(attendance_id: int) -> bool:
        """Record member check-out."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE gym_attendance SET check_out = ? WHERE attendance_id = ?
                ''', (datetime.now().isoformat(), attendance_id))
            return True
        except Exception as e:
            print(f"Error checking out: {e}")
            return False

class ClassManager:
    """Manages fitness classes."""

    @staticmethod
    def get_all_classes(class_type: str = None, day: str = None) -> List[Dict]:
        """Get all available classes."""
        try:
            with get_connection() as conn:
                query = "SELECT * FROM gym_classes WHERE status = 'active'"
                params = []
                if class_type:
                    query += " AND class_type = ?"
                    params.append(class_type)
                if day:
                    query += " AND schedule_day = ?"
                    params.append(day)
                query += " ORDER BY schedule_day, start_time"
                cursor = conn.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting classes: {e}")
            return []

    @staticmethod
    def get_class(class_id: int) -> Optional[Dict]:
        """Get class details."""
        try:
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM gym_classes WHERE class_id = ?", (class_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting class: {e}")
            return None

    @staticmethod
    def book_class(class_id: int, member_id: int, booking_date: str) -> Optional[Dict]:
        """Book a class for a member."""
        try:
            booking_ref = generate_booking_ref()

            with transaction() as conn:
                # Check capacity
                cursor = conn.execute('''
                    SELECT max_capacity, current_enrolled FROM gym_classes WHERE class_id = ?
                ''', (class_id,))
                row = cursor.fetchone()
                if not row or row[1] >= row[0]:
                    return None

                conn.execute('''
                    INSERT INTO gym_class_bookings (booking_ref, class_id, member_id, booking_date)
                    VALUES (?, ?, ?, ?)
                ''', (booking_ref, class_id, member_id, booking_date))

                conn.execute('''
                    UPDATE gym_classes SET current_enrolled = current_enrolled + 1 WHERE class_id = ?
                ''', (class_id,))

                booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            return {
                'booking_id': booking_id,
                'booking_ref': booking_ref
            }
        except Exception as e:
            print(f"Error booking class: {e}")
            return None

    @staticmethod
    def cancel_booking(booking_id: int) -> bool:
        """Cancel a class booking."""
        try:
            with transaction() as conn:
                cursor = conn.execute(
                    "SELECT class_id FROM gym_class_bookings WHERE booking_id = ?", (booking_id,))
                row = cursor.fetchone()
                if not row:
                    return False

                conn.execute('''
                    UPDATE gym_class_bookings SET status = 'cancelled' WHERE booking_id = ?
                ''', (booking_id,))

                conn.execute('''
                    UPDATE gym_classes SET current_enrolled = current_enrolled - 1 WHERE class_id = ?
                ''', (row[0],))

            return True
        except Exception as e:
            print(f"Error cancelling booking: {e}")
            return False

    @staticmethod
    def get_member_bookings(member_id: int) -> List[Dict]:
        """Get member's class bookings."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT b.*, c.class_name, c.instructor_name, c.start_time, c.location
                    FROM gym_class_bookings b
                    JOIN gym_classes c ON b.class_id = c.class_id
                    WHERE b.member_id = ? AND b.status = 'confirmed'
                    ORDER BY b.booking_date DESC
                ''', (member_id,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting bookings: {e}")
            return []

class PTSessionManager:
    """Manages personal training sessions."""

    @staticmethod
    def book_session(member_id: int, trainer_name: str, session_date: str,
                    session_time: str, session_type: str = 'single',
                    duration: int = 60) -> Optional[Dict]:
        """Book a personal training session."""
        try:
            booking_ref = generate_booking_ref()
            fee = PT_SESSION_FEES.get(session_type, PT_SESSION_FEES['single'])

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO gym_pt_sessions
                    (booking_ref, member_id, trainer_name, session_date, session_time,
                     duration_minutes, session_type, fee)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (booking_ref, member_id, trainer_name, session_date, session_time,
                      duration, session_type, fee))

                session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            return {
                'session_id': session_id,
                'booking_ref': booking_ref,
                'fee': fee
            }
        except Exception as e:
            print(f"Error booking PT session: {e}")
            return None

    @staticmethod
    def get_member_sessions(member_id: int) -> List[Dict]:
        """Get member's PT sessions."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM gym_pt_sessions
                    WHERE member_id = ? ORDER BY session_date DESC
                ''', (member_id,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting PT sessions: {e}")
            return []

    @staticmethod
    def cancel_session(session_id: int) -> bool:
        """Cancel a PT session."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE gym_pt_sessions SET status = 'cancelled' WHERE session_id = ?
                ''', (session_id,))
            return True
        except Exception as e:
            print(f"Error cancelling session: {e}")
            return False

class EquipmentManager:
    """Manages gym equipment."""

    @staticmethod
    def get_all_equipment(category: str = None, status: str = None) -> List[Dict]:
        """Get all equipment."""
        try:
            with get_connection() as conn:
                query = "SELECT * FROM gym_equipment WHERE 1=1"
                params = []
                if category:
                    query += " AND category = ?"
                    params.append(category)
                if status:
                    query += " AND status = ?"
                    params.append(status)
                query += " ORDER BY category, equipment_name"
                cursor = conn.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting equipment: {e}")
            return []

    @staticmethod
    def report_issue(equipment_id: int, issue: str) -> bool:
        """Report equipment issue."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE gym_equipment SET status = 'maintenance', notes = ? WHERE equipment_id = ?
                ''', (issue, equipment_id))
            return True
        except Exception as e:
            print(f"Error reporting issue: {e}")
            return False

class TransactionManager:
    """Manages gym transactions."""

    @staticmethod
    def record_payment(user_id: str, transaction_type: str, amount: float,
                      payment_method: str, member_id: int = None,
                      processed_by: str = None) -> Optional[Dict]:
        """Record a payment transaction."""
        try:
            reference = generate_reference()

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO transactions
                    (source_type, reference_number, customer_id, user_id, transaction_type, amount,
                     payment_method, processed_by)
                    VALUES ('gym', ?, ?, ?, ?, ?, ?, ?)
                ''', (reference, member_id, user_id, transaction_type, amount,
                      payment_method, processed_by))

                transaction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            return {
                'transaction_id': transaction_id,
                'reference': reference,
                'amount': amount
            }
        except Exception as e:
            print(f"Error recording payment: {e}")
            return None

    @staticmethod
    def get_user_transactions(user_id: str, limit: int = 50) -> List[Dict]:
        """Get user's transaction history."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM transactions WHERE source_type = 'gym' AND user_id = ?
                    ORDER BY created_at DESC LIMIT ?
                ''', (user_id, limit))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return []

class ReportManager:
    """Manages gym reporting."""

    @staticmethod
    def get_daily_attendance(date: str = None) -> Dict:
        """Get daily attendance report."""
        try:
            if not date:
                date = datetime.now().date().isoformat()

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM gym_attendance WHERE DATE(check_in) = ?
                ''', (date,))
                check_ins = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE source_type = 'gym' AND DATE(created_at) = ?
                ''', (date,))
                revenue = cursor.fetchone()[0]

                return {
                    'date': date,
                    'check_ins': check_ins,
                    'revenue': revenue
                }
        except Exception as e:
            print(f"Error getting daily attendance: {e}")
            return {}

    @staticmethod
    def get_membership_stats() -> Dict:
        """Get membership statistics."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT membership_type, COUNT(*), SUM(monthly_fee)
                    FROM gym_memberships WHERE status = 'active'
                    GROUP BY membership_type
                ''')
                by_type = {row[0]: {'count': row[1], 'revenue': row[2]} for row in cursor.fetchall()}

                cursor = conn.execute("SELECT COUNT(*) FROM gym_memberships WHERE status = 'active'")
                total_active = cursor.fetchone()[0]

                return {
                    'by_type': by_type,
                    'total_active': total_active
                }
        except Exception as e:
            print(f"Error getting membership stats: {e}")
            return {}

    @staticmethod
    def get_monthly_summary(year: int = None, month: int = None) -> Dict:
        """Generate monthly summary report."""
        try:
            if not year:
                year = datetime.now().year
            if not month:
                month = datetime.now().month

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT COALESCE(SUM(amount), 0) FROM transactions
                    WHERE source_type = 'gym' AND strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ?
                ''', (str(year), f"{month:02d}"))
                total_revenue = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COUNT(*) FROM gym_memberships
                    WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ?
                ''', (str(year), f"{month:02d}"))
                new_members = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COUNT(*) FROM gym_class_bookings
                    WHERE strftime('%Y', booking_date) = ? AND strftime('%m', booking_date) = ?
                ''', (str(year), f"{month:02d}"))
                class_bookings = cursor.fetchone()[0]

                return {
                    'year': year,
                    'month': month,
                    'total_revenue': total_revenue,
                    'new_members': new_members,
                    'class_bookings': class_bookings
                }
        except Exception as e:
            print(f"Error generating monthly summary: {e}")
            return {}
