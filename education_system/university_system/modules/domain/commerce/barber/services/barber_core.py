"""Barber Shop Core Services Module

Provides business logic for barber shop operations including
appointments, services, staff, and transaction management.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from education_system.university_system.infrastructure.database.db import get_db_connection, transaction

logger = logging.getLogger(__name__)

# Service types
SERVICE_TYPES = {
    'haircut': 'Haircut',
    'beard_trim': 'Beard Trim',
    'haircut_beard': 'Haircut & Beard',
    'shave': 'Traditional Shave',
    'hair_wash': 'Hair Wash & Style',
    'buzz_cut': 'Buzz Cut',
    'fade': 'Fade Cut',
    'lineup': 'Line Up',
    'kids_cut': 'Kids Haircut',
    'senior_cut': 'Senior Haircut',
    'hair_color': 'Hair Coloring',
    'head_shave': 'Head Shave'
}

# Appointment statuses
APPOINTMENT_STATUSES = ['scheduled', 'checked_in', 'in_progress', 'completed', 'cancelled', 'no_show']

# Time slots (30-minute intervals)
TIME_SLOTS = [
    '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
    '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
    '15:00', '15:30', '16:00', '16:30', '17:00', '17:30'
]

def init_barber_db():
    """Initialize barber shop database tables"""
    with transaction() as conn:
        # Services table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_services (
                service_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                service_type TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER DEFAULT 30,
                price DECIMAL(10,2) NOT NULL,
                is_available INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Staff/Barbers table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_staff (
                staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE,
                specialties TEXT,
                phone TEXT,
                email TEXT,
                is_active INTEGER DEFAULT 1,
                hire_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Appointments table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_appointments (
                appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_number TEXT UNIQUE NOT NULL,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                customer_phone TEXT,
                staff_id INTEGER,
                staff_name TEXT,
                service_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 30,
                price DECIMAL(10,2) NOT NULL,
                status TEXT DEFAULT 'scheduled',
                payment_status TEXT DEFAULT 'pending',
                payment_method TEXT,
                special_requests TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (staff_id) REFERENCES barber_staff(staff_id),
                FOREIGN KEY (service_id) REFERENCES barber_services(service_id)
            )
        ''')

        # Barber transactions now use unified 'transactions' table with source_type='barber'

        # Customer preferences table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_customer_preferences (
                preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                preferred_barber_id INTEGER,
                preferred_service_id INTEGER,
                hair_type TEXT,
                style_notes TEXT,
                allergies TEXT,
                last_visit TEXT,
                visit_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Insert default services if empty
        existing = conn.execute('SELECT COUNT(*) FROM barber_services').fetchone()[0]
        if existing == 0:
            default_services = [
                ('Standard Haircut', 'haircut', 'Classic haircut with clippers and scissors', 30, 15.00),
                ('Beard Trim', 'beard_trim', 'Beard shaping and trimming', 20, 10.00),
                ('Haircut & Beard', 'haircut_beard', 'Full haircut with beard trim', 45, 22.00),
                ('Traditional Shave', 'shave', 'Hot towel traditional straight razor shave', 30, 18.00),
                ('Fade Cut', 'fade', 'Fade haircut with blending', 40, 18.00),
                ('Buzz Cut', 'buzz_cut', 'Quick buzz cut all over', 15, 10.00),
                ('Kids Haircut', 'kids_cut', 'Haircut for children under 12', 20, 12.00),
                ('Senior Haircut', 'senior_cut', 'Discounted haircut for seniors 65+', 30, 12.00),
            ]
            conn.executemany('''
                INSERT INTO barber_services (name, service_type, description, duration_minutes, price)
                VALUES (?, ?, ?, ?, ?)
            ''', default_services)

        logger.info("Barber shop database tables initialized successfully")

class ServiceManager:
    """Manages barber shop services"""

    @staticmethod
    def add_service(name: str, service_type: str, price: float,
                   duration_minutes: int = 30, description: str = None) -> int:
        """Add a new service"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_services (name, service_type, description, duration_minutes, price)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, service_type, description, duration_minutes, price))
            return cursor.lastrowid

    @staticmethod
    def get_service(service_id: int) -> Optional[Dict]:
        """Get service by ID"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM barber_services WHERE service_id = ?',
                (service_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def get_all_services(available_only: bool = True) -> List[Dict]:
        """Get all services"""
        with get_db_connection() as conn:
            query = 'SELECT * FROM barber_services'
            if available_only:
                query += ' WHERE is_available = 1'
            query += ' ORDER BY name'
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_service(service_id: int, **kwargs) -> bool:
        """Update service details"""
        allowed_fields = ['name', 'service_type', 'description', 'duration_minutes',
                         'price', 'is_available']

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        values = list(updates.values()) + [service_id]

        with transaction() as conn:
            conn.execute(
                f'UPDATE barber_services SET {set_clause} WHERE service_id = ?',
                values
            )
            return True

class StaffManager:
    """Manages barber staff"""

    @staticmethod
    def add_staff(name: str, employee_id: str = None, specialties: str = None,
                 phone: str = None, email: str = None) -> int:
        """Add new staff member"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_staff (name, employee_id, specialties, phone, email, hire_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, employee_id, specialties, phone, email, datetime.now().strftime('%Y-%m-%d')))
            return cursor.lastrowid

    @staticmethod
    def get_staff(staff_id: int) -> Optional[Dict]:
        """Get staff member by ID"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM barber_staff WHERE staff_id = ?',
                (staff_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def get_all_staff(active_only: bool = True) -> List[Dict]:
        """Get all staff members"""
        with get_db_connection() as conn:
            query = 'SELECT * FROM barber_staff'
            if active_only:
                query += ' WHERE is_active = 1'
            query += ' ORDER BY name'
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_staff_availability(staff_id: int, date: str) -> List[str]:
        """Get available time slots for a staff member on a date"""
        with get_db_connection() as conn:
            # Get booked slots
            booked = conn.execute('''
                SELECT appointment_time FROM barber_appointments
                WHERE staff_id = ? AND appointment_date = ?
                AND status NOT IN ('cancelled', 'no_show')
            ''', (staff_id, date)).fetchall()

            booked_times = set(row['appointment_time'] for row in booked)
            return [slot for slot in TIME_SLOTS if slot not in booked_times]

class AppointmentManager:
    """Manages appointments"""

    @staticmethod
    def generate_appointment_number() -> str:
        """Generate unique appointment number"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        with get_db_connection() as conn:
            count = conn.execute(
                'SELECT COUNT(*) FROM barber_appointments WHERE DATE(created_at) = DATE(?)',
                (datetime.now().isoformat(),)
            ).fetchone()[0]
        return f"BAR-{timestamp}-{count + 1:03d}"

    @staticmethod
    def book_appointment(customer_id: str, customer_name: str, service_id: int,
                        appointment_date: str, appointment_time: str,
                        staff_id: int = None, customer_email: str = None,
                        customer_phone: str = None, special_requests: str = None) -> Tuple[int, str]:
        """Book a new appointment"""
        appointment_number = AppointmentManager.generate_appointment_number()

        with transaction() as conn:
            # Get service details
            service = conn.execute(
                'SELECT * FROM barber_services WHERE service_id = ?',
                (service_id,)
            ).fetchone()

            if not service:
                raise ValueError(f"Service {service_id} not found")

            # Get staff name if provided
            staff_name = None
            if staff_id:
                staff = conn.execute(
                    'SELECT name FROM barber_staff WHERE staff_id = ?',
                    (staff_id,)
                ).fetchone()
                staff_name = staff['name'] if staff else None

            cursor = conn.execute('''
                INSERT INTO barber_appointments
                (appointment_number, customer_id, customer_name, customer_email, customer_phone,
                 staff_id, staff_name, service_id, service_name, appointment_date, appointment_time,
                 duration_minutes, price, special_requests)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (appointment_number, customer_id, customer_name, customer_email, customer_phone,
                  staff_id, staff_name, service_id, service['name'], appointment_date, appointment_time,
                  service['duration_minutes'], service['price'], special_requests))

            return cursor.lastrowid, appointment_number

    @staticmethod
    def get_appointment(appointment_id: int) -> Optional[Dict]:
        """Get appointment by ID"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM barber_appointments WHERE appointment_id = ?',
                (appointment_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def get_appointment_by_number(appointment_number: str) -> Optional[Dict]:
        """Get appointment by appointment number"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM barber_appointments WHERE appointment_number = ?',
                (appointment_number,)
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def update_status(appointment_id: int, status: str, user_id: str = None) -> bool:
        """Update appointment status"""
        if status not in APPOINTMENT_STATUSES:
            return False

        with transaction() as conn:
            conn.execute('''
                UPDATE barber_appointments
                SET status = ?, updated_at = ?
                WHERE appointment_id = ?
            ''', (status, datetime.now().isoformat(), appointment_id))
            return True

    @staticmethod
    def cancel_appointment(appointment_id: int, reason: str = None) -> bool:
        """Cancel an appointment"""
        with transaction() as conn:
            conn.execute('''
                UPDATE barber_appointments
                SET status = 'cancelled', notes = ?, updated_at = ?
                WHERE appointment_id = ?
            ''', (reason, datetime.now().isoformat(), appointment_id))
            return True

    @staticmethod
    def reschedule_appointment(appointment_id: int, new_date: str,
                              new_time: str, new_staff_id: int = None) -> bool:
        """Reschedule an appointment"""
        with transaction() as conn:
            updates = {
                'appointment_date': new_date,
                'appointment_time': new_time,
                'updated_at': datetime.now().isoformat()
            }

            if new_staff_id:
                staff = conn.execute(
                    'SELECT name FROM barber_staff WHERE staff_id = ?',
                    (new_staff_id,)
                ).fetchone()
                if staff:
                    updates['staff_id'] = new_staff_id
                    updates['staff_name'] = staff['name']

            set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
            values = list(updates.values()) + [appointment_id]

            conn.execute(
                f'UPDATE barber_appointments SET {set_clause} WHERE appointment_id = ?',
                values
            )
            return True

    @staticmethod
    def get_appointments_by_date(date: str) -> List[Dict]:
        """Get all appointments for a date"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM barber_appointments
                WHERE appointment_date = ?
                ORDER BY appointment_time
            ''', (date,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_customer_appointments(customer_id: str) -> List[Dict]:
        """Get all appointments for a customer"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM barber_appointments
                WHERE customer_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
            ''', (customer_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_todays_appointments() -> List[Dict]:
        """Get all appointments for today"""
        today = datetime.now().strftime('%Y-%m-%d')
        return AppointmentManager.get_appointments_by_date(today)

class TransactionManager:
    """Manages financial transactions"""

    @staticmethod
    def process_payment(appointment_id: int, amount: float, payment_method: str,
                       customer_id: str, tip_amount: float = 0,
                       reference_number: str = None, processed_by: str = None) -> int:
        """Process payment for an appointment"""
        with transaction() as conn:
            # Record transaction
            cursor = conn.execute('''
                INSERT INTO transactions
                (source_type, reference_id, reference_type, customer_id, amount, payment_method, tip_amount,
                 reference_number, processed_by)
                VALUES ('barber', ?, 'appointment', ?, ?, ?, ?, ?, ?)
            ''', (appointment_id, customer_id, amount, payment_method, tip_amount,
                  reference_number, processed_by))

            transaction_id = cursor.lastrowid

            # Update appointment payment status
            conn.execute('''
                UPDATE barber_appointments
                SET payment_status = 'paid', payment_method = ?, updated_at = ?
                WHERE appointment_id = ?
            ''', (payment_method, datetime.now().isoformat(), appointment_id))

            # 8.117.104: route through unified record_payment() with
            # source_type='barber' so cross-domain reports can isolate
            # barber-shop revenue.
            try:
                from education_system.university_system.modules.domain.finance.core.unified_payments import (
                    record_payment as _record_payment,
                )
                _record_payment(
                    student_id=customer_id,
                    amount=amount + tip_amount,
                    payment_method=payment_method,
                    source_type='barber',
                    source_payment_id=str(appointment_id),
                    payment_type='service',
                    reference_type='barber_appointment',
                    reference_id=str(appointment_id),
                    department='barber',
                    description='Barber Shop Service',
                    notes=(f'tip {tip_amount}' if tip_amount else None),
                    created_by=processed_by,
                )
            except Exception as e:
                logger.warning(f"Could not record to main finance system: {e}")

            return transaction_id

    @staticmethod
    def get_transaction(transaction_id: int) -> Optional[Dict]:
        """Get transaction by ID"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM transactions WHERE transaction_id = ? AND source_type = ?',
                (transaction_id, 'barber')
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def mark_receipt_sent(transaction_id: int) -> bool:
        """Mark receipt as sent"""
        with transaction() as conn:
            conn.execute(
                'UPDATE transactions SET receipt_sent = 1 WHERE transaction_id = ? AND source_type = ?',
                (transaction_id, 'barber')
            )
            return True

    @staticmethod
    def get_daily_revenue(date: str = None) -> Dict:
        """Get revenue summary for a day"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        with get_db_connection() as conn:
            row = conn.execute('''
                SELECT
                    COUNT(*) as transaction_count,
                    SUM(amount) as service_revenue,
                    SUM(tip_amount) as tips,
                    SUM(amount + tip_amount) as total_revenue
                FROM transactions
                WHERE source_type = 'barber' AND DATE(created_at) = ? AND status = 'completed'
            ''', (date,)).fetchone()

            return {
                'date': date,
                'transaction_count': row['transaction_count'] or 0,
                'service_revenue': row['service_revenue'] or 0,
                'tips': row['tips'] or 0,
                'total_revenue': row['total_revenue'] or 0
            }

class ReportManager:
    """Generates reports for the barber shop"""

    @staticmethod
    def generate_sales_report(start_date: str, end_date: str) -> Dict:
        """Generate sales report for date range"""
        with get_db_connection() as conn:
            # Revenue summary
            summary = conn.execute('''
                SELECT
                    COUNT(*) as total_appointments,
                    SUM(amount) as service_revenue,
                    SUM(tip_amount) as total_tips,
                    AVG(amount) as avg_service_value
                FROM transactions
                WHERE source_type = 'barber' AND DATE(created_at) BETWEEN ? AND ? AND status = 'completed'
            ''', (start_date, end_date)).fetchone()

            # Revenue by service
            by_service = conn.execute('''
                SELECT
                    a.service_name,
                    COUNT(*) as count,
                    SUM(t.amount) as revenue
                FROM transactions t
                JOIN barber_appointments a ON t.reference_id = a.appointment_id AND t.reference_type = 'appointment'
                WHERE t.source_type = 'barber' AND DATE(t.created_at) BETWEEN ? AND ?
                    AND t.status = 'completed'
                GROUP BY a.service_name
                ORDER BY revenue DESC
            ''', (start_date, end_date)).fetchall()

            # Revenue by staff
            by_staff = conn.execute('''
                SELECT
                    a.staff_name,
                    COUNT(*) as appointments,
                    SUM(t.amount) as revenue,
                    SUM(t.tip_amount) as tips
                FROM transactions t
                JOIN barber_appointments a ON t.reference_id = a.appointment_id AND t.reference_type = 'appointment'
                WHERE t.source_type = 'barber' AND DATE(t.created_at) BETWEEN ? AND ?
                    AND t.status = 'completed' AND a.staff_name IS NOT NULL
                GROUP BY a.staff_id, a.staff_name
                ORDER BY revenue DESC
            ''', (start_date, end_date)).fetchall()

            return {
                'period': {'start': start_date, 'end': end_date},
                'summary': dict(summary) if summary else {},
                'by_service': [dict(row) for row in by_service],
                'by_staff': [dict(row) for row in by_staff],
                'generated_at': datetime.now().isoformat()
            }

    @staticmethod
    def generate_admin_report() -> str:
        """Generate comprehensive admin report as text"""
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        daily_revenue = TransactionManager.get_daily_revenue(today)
        weekly_report = ReportManager.generate_sales_report(week_ago, today)

        # Get today's appointments
        todays_appointments = AppointmentManager.get_todays_appointments()

        report = f"""
BARBER SHOP ADMIN REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 50}

TODAY'S SUMMARY ({today})
{'-' * 30}
Appointments: {len(todays_appointments)}
Transactions: {daily_revenue['transaction_count']}
Service Revenue: £{daily_revenue['service_revenue']:.2f}
Tips: £{daily_revenue['tips']:.2f}
Total Revenue: £{daily_revenue['total_revenue']:.2f}

WEEKLY SUMMARY ({week_ago} to {today})
{'-' * 30}
Total Appointments: {weekly_report['summary'].get('total_appointments') or 0}
Service Revenue: £{(weekly_report['summary'].get('service_revenue') or 0):.2f}
Total Tips: £{(weekly_report['summary'].get('total_tips') or 0):.2f}
Avg Service Value: £{(weekly_report['summary'].get('avg_service_value') or 0):.2f}

TOP SERVICES
{'-' * 30}
"""
        for i, service in enumerate(weekly_report['by_service'][:5], 1):
            service_name = service.get('service_name', 'Unknown')
            count = service.get('count') or 0
            revenue = service.get('revenue') or 0
            report += f"{i}. {service_name}: {count} bookings (£{revenue:.2f})\n"

        report += f"""
BARBER PERFORMANCE
{'-' * 30}
"""
        for barber in weekly_report['by_staff']:
            staff_name = barber.get('staff_name', 'Unknown')
            appointments = barber.get('appointments') or 0
            revenue = barber.get('revenue') or 0
            tips = barber.get('tips') or 0
            report += f"  {staff_name}: {appointments} clients, £{revenue:.2f} revenue, £{tips:.2f} tips\n"

        report += f"""
{'=' * 50}
End of Report
"""
        return report

class WaitlistManager:
    """Manages appointment waitlist"""

    @staticmethod
    def add_to_waitlist(customer_id: str, customer_name: str, customer_email: str,
                        customer_phone: str, preferred_date: str, preferred_time: str,
                        service_id: int, staff_id: int = None, notes: str = None) -> int:
        """Add customer to waitlist"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_waitlist
                (customer_id, customer_name, customer_email, customer_phone,
                 preferred_date, preferred_time, service_id, staff_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (customer_id, customer_name, customer_email, customer_phone,
                  preferred_date, preferred_time, service_id, staff_id, notes))
            return cursor.lastrowid

    @staticmethod
    def get_waitlist(date: str = None, service_id: int = None) -> List[Dict]:
        """Get waitlist entries"""
        with get_db_connection() as conn:
            query = 'SELECT * FROM barber_waitlist WHERE status = "waiting"'
            params = []
            if date:
                query += ' AND preferred_date = ?'
                params.append(date)
            if service_id:
                query += ' AND service_id = ?'
                params.append(service_id)
            query += ' ORDER BY created_at'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def notify_waitlist(waitlist_id: int, available_slot: str) -> bool:
        """Mark waitlist entry as notified"""
        with transaction() as conn:
            conn.execute('''
                UPDATE barber_waitlist
                SET status = 'notified', notification_sent_at = ?, available_slot = ?
                WHERE waitlist_id = ?
            ''', (datetime.now().isoformat(), available_slot, waitlist_id))
            return True

    @staticmethod
    def remove_from_waitlist(waitlist_id: int, reason: str = 'booked') -> bool:
        """Remove from waitlist"""
        with transaction() as conn:
            conn.execute('''
                UPDATE barber_waitlist SET status = ? WHERE waitlist_id = ?
            ''', (reason, waitlist_id))
            return True

class BlockedSlotManager:
    """Manages blocked time slots"""

    @staticmethod
    def block_slot(staff_id: int, date: str, start_time: str, end_time: str,
                   reason: str, blocked_by: str) -> int:
        """Block a time slot"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_blocked_slots
                (staff_id, blocked_date, start_time, end_time, reason, blocked_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (staff_id, date, start_time, end_time, reason, blocked_by))
            return cursor.lastrowid

    @staticmethod
    def get_blocked_slots(staff_id: int = None, date: str = None) -> List[Dict]:
        """Get blocked slots"""
        with get_db_connection() as conn:
            query = 'SELECT * FROM barber_blocked_slots WHERE 1=1'
            params = []
            if staff_id:
                query += ' AND staff_id = ?'
                params.append(staff_id)
            if date:
                query += ' AND blocked_date = ?'
                params.append(date)
            query += ' ORDER BY blocked_date, start_time'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def unblock_slot(block_id: int) -> bool:
        """Remove a blocked slot"""
        with transaction() as conn:
            conn.execute('DELETE FROM barber_blocked_slots WHERE block_id = ?', (block_id,))
            return True

class RecurringAppointmentManager:
    """Manages recurring appointments"""

    @staticmethod
    def create_recurring(customer_id: str, customer_name: str, customer_email: str,
                         service_id: int, staff_id: int, day_of_week: int,
                         time: str, frequency: str, start_date: str,
                         end_date: str = None) -> int:
        """Create recurring appointment schedule"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_recurring_appointments
                (customer_id, customer_name, customer_email, service_id, staff_id,
                 day_of_week, appointment_time, frequency, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (customer_id, customer_name, customer_email, service_id, staff_id,
                  day_of_week, time, frequency, start_date, end_date))
            return cursor.lastrowid

    @staticmethod
    def get_customer_recurring(customer_id: str) -> List[Dict]:
        """Get customer's recurring appointments"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT r.*, s.name as service_name, st.name as staff_name
                FROM barber_recurring_appointments r
                LEFT JOIN barber_services s ON r.service_id = s.service_id
                LEFT JOIN barber_staff st ON r.staff_id = st.staff_id
                WHERE r.customer_id = ? AND r.is_active = 1
            ''', (customer_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def cancel_recurring(recurring_id: int) -> bool:
        """Cancel recurring appointment"""
        with transaction() as conn:
            conn.execute('''
                UPDATE barber_recurring_appointments SET is_active = 0 WHERE recurring_id = ?
            ''', (recurring_id,))
            return True

class CustomerManager:
    """Manages customer profiles and notes"""

    @staticmethod
    def create_profile(customer_id: str, name: str, email: str = None,
                       phone: str = None, preferences: str = None,
                       allergies: str = None, notes: str = None) -> int:
        """Create customer profile"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO barber_customer_profiles
                (customer_id, name, email, phone, preferences, allergies, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (customer_id, name, email, phone, preferences, allergies, notes))
            return cursor.lastrowid

    @staticmethod
    def get_profile(customer_id: str) -> Optional[Dict]:
        """Get customer profile"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM barber_customer_profiles WHERE customer_id = ?',
                (customer_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def update_profile(customer_id: str, **kwargs) -> bool:
        """Update customer profile"""
        allowed = ['name', 'email', 'phone', 'preferences', 'allergies', 'notes',
                   'is_vip', 'total_visits', 'total_spent']
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates['updated_at'] = datetime.now().isoformat()
        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        values = list(updates.values()) + [customer_id]
        with transaction() as conn:
            conn.execute(
                f'UPDATE barber_customer_profiles SET {set_clause} WHERE customer_id = ?',
                values
            )
            return True

    @staticmethod
    def add_note(customer_id: str, note: str, note_type: str, created_by: str) -> int:
        """Add customer note"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_customer_notes
                (customer_id, note, note_type, created_by)
                VALUES (?, ?, ?, ?)
            ''', (customer_id, note, note_type, created_by))
            return cursor.lastrowid

    @staticmethod
    def get_notes(customer_id: str) -> List[Dict]:
        """Get customer notes"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM barber_customer_notes
                WHERE customer_id = ? ORDER BY created_at DESC
            ''', (customer_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def search_customers(query: str) -> List[Dict]:
        """Search customers"""
        with get_db_connection() as conn:
            search = f'%{query}%'
            rows = conn.execute('''
                SELECT * FROM barber_customer_profiles
                WHERE name LIKE ? OR email LIKE ? OR phone LIKE ? OR customer_id LIKE ?
                ORDER BY name LIMIT 50
            ''', (search, search, search, search)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_vip_customers() -> List[Dict]:
        """Get VIP/frequent customers"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM barber_customer_profiles
                WHERE is_vip = 1 OR total_visits >= 10
                ORDER BY total_visits DESC, total_spent DESC
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_all_customers() -> List[Dict]:
        """Get all customer profiles"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM barber_customer_profiles
                ORDER BY name
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_customer(customer_id: str) -> Optional[Dict]:
        """Get customer by ID (alias for get_profile for consistency)"""
        return CustomerManager.get_profile(customer_id)

    @staticmethod
    def get_customer_appointments(customer_id: str, limit: int = None) -> List[Dict]:
        """Get customer appointments with optional limit"""
        with get_db_connection() as conn:
            query = '''
                SELECT * FROM barber_appointments
                WHERE customer_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
            '''
            if limit:
                query += f' LIMIT {limit}'
            rows = conn.execute(query, (customer_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def merge_profiles(primary_id: str, secondary_id: str) -> bool:
        """Merge duplicate customer profiles"""
        with transaction() as conn:
            # Move appointments
            conn.execute('''
                UPDATE barber_appointments SET customer_id = ?
                WHERE customer_id = ?
            ''', (primary_id, secondary_id))
            # Move transactions
            conn.execute('''
                UPDATE transactions SET customer_id = ?
                WHERE source_type = 'barber' AND customer_id = ?
            ''', (primary_id, secondary_id))
            # Move notes
            conn.execute('''
                UPDATE barber_customer_notes SET customer_id = ?
                WHERE customer_id = ?
            ''', (primary_id, secondary_id))
            # Update totals
            secondary = conn.execute(
                'SELECT total_visits, total_spent FROM barber_customer_profiles WHERE customer_id = ?',
                (secondary_id,)
            ).fetchone()
            if secondary:
                conn.execute('''
                    UPDATE barber_customer_profiles
                    SET total_visits = total_visits + ?, total_spent = total_spent + ?
                    WHERE customer_id = ?
                ''', (secondary['total_visits'] or 0, secondary['total_spent'] or 0, primary_id))
            # Delete secondary
            conn.execute('DELETE FROM barber_customer_profiles WHERE customer_id = ?', (secondary_id,))
            return True

class FeedbackManager:
    """Manages customer feedback"""

    @staticmethod
    def add_feedback(appointment_id: int, customer_id: str, rating: int,
                     comment: str = None, staff_id: int = None) -> int:
        """Add customer feedback"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_feedback
                (appointment_id, customer_id, staff_id, rating, comment)
                VALUES (?, ?, ?, ?, ?)
            ''', (appointment_id, customer_id, staff_id, rating, comment))
            return cursor.lastrowid

    @staticmethod
    def get_customer_feedback(customer_id: str) -> List[Dict]:
        """Get feedback by customer"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT f.*, a.service_name, a.appointment_date, s.name as staff_name
                FROM barber_feedback f
                LEFT JOIN barber_appointments a ON f.appointment_id = a.appointment_id
                LEFT JOIN barber_staff s ON f.staff_id = s.staff_id
                WHERE f.customer_id = ?
                ORDER BY f.created_at DESC
            ''', (customer_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_staff_feedback(staff_id: int) -> List[Dict]:
        """Get feedback for staff"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT f.*, a.service_name, a.appointment_date
                FROM barber_feedback f
                LEFT JOIN barber_appointments a ON f.appointment_id = a.appointment_id
                WHERE f.staff_id = ?
                ORDER BY f.created_at DESC
            ''', (staff_id,)).fetchall()
            return [dict(row) for row in rows]

class ServicePackageManager:
    """Manages service packages"""

    @staticmethod
    def create_package(name: str, description: str, services: List[int],
                       total_price: float, discount_percent: float = 0) -> int:
        """Create service package"""
        import json
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_service_packages
                (name, description, services, total_price, discount_percent)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, description, json.dumps(services), total_price, discount_percent))
            return cursor.lastrowid

    @staticmethod
    def get_packages(active_only: bool = True) -> List[Dict]:
        """Get all packages"""
        import json
        with get_db_connection() as conn:
            query = 'SELECT * FROM barber_service_packages'
            if active_only:
                query += ' WHERE is_active = 1'
            rows = conn.execute(query).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d['services'] = json.loads(d['services']) if d['services'] else []
                result.append(d)
            return result

class ServiceAddonManager:
    """Manages service add-ons"""

    @staticmethod
    def create_addon(name: str, description: str, price: float,
                     duration_minutes: int = 5) -> int:
        """Create service add-on"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_service_addons (name, description, price, duration_minutes)
                VALUES (?, ?, ?, ?)
            ''', (name, description, price, duration_minutes))
            return cursor.lastrowid

    @staticmethod
    def get_addons(active_only: bool = True) -> List[Dict]:
        """Get all add-ons"""
        with get_db_connection() as conn:
            query = 'SELECT * FROM barber_service_addons'
            if active_only:
                query += ' WHERE is_active = 1'
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]

class StaffScheduleManager:
    """Manages staff schedules"""

    @staticmethod
    def set_schedule(staff_id: int, day_of_week: int, start_time: str,
                     end_time: str, is_working: bool = True) -> int:
        """Set staff schedule for a day"""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM barber_staff_schedules WHERE staff_id = ? AND day_of_week = ?
            ''', (staff_id, day_of_week))
            cursor = conn.execute('''
                INSERT INTO barber_staff_schedules
                (staff_id, day_of_week, start_time, end_time, is_working)
                VALUES (?, ?, ?, ?, ?)
            ''', (staff_id, day_of_week, start_time, end_time, is_working))
            return cursor.lastrowid

    @staticmethod
    def get_schedule(staff_id: int) -> List[Dict]:
        """Get staff schedule"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM barber_staff_schedules WHERE staff_id = ?
                ORDER BY day_of_week
            ''', (staff_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_staff_calendar(staff_id: int, start_date: str, end_date: str) -> List[Dict]:
        """Get staff appointments for date range"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM barber_appointments
                WHERE staff_id = ? AND appointment_date BETWEEN ? AND ?
                AND status NOT IN ('cancelled')
                ORDER BY appointment_date, appointment_time
            ''', (staff_id, start_date, end_date)).fetchall()
            return [dict(row) for row in rows]

class CommissionManager:
    """Manages staff commissions"""

    @staticmethod
    def set_commission(staff_id: int, commission_type: str, rate: float,
                       service_id: int = None) -> int:
        """Set commission rate"""
        with transaction() as conn:
            if service_id:
                conn.execute('''
                    DELETE FROM barber_commissions
                    WHERE staff_id = ? AND service_id = ?
                ''', (staff_id, service_id))
            else:
                conn.execute('''
                    DELETE FROM barber_commissions
                    WHERE staff_id = ? AND service_id IS NULL
                ''', (staff_id,))
            cursor = conn.execute('''
                INSERT INTO barber_commissions
                (staff_id, commission_type, rate, service_id)
                VALUES (?, ?, ?, ?)
            ''', (staff_id, commission_type, rate, service_id))
            return cursor.lastrowid

    @staticmethod
    def get_staff_commissions(staff_id: int) -> List[Dict]:
        """Get staff commission rates"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT c.*, s.name as service_name
                FROM barber_commissions c
                LEFT JOIN barber_services s ON c.service_id = s.service_id
                WHERE c.staff_id = ?
            ''', (staff_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def calculate_commission(staff_id: int, start_date: str, end_date: str) -> Dict:
        """Calculate commission for period"""
        with get_db_connection() as conn:
            # Get appointments
            appointments = conn.execute('''
                SELECT a.*, t.amount, t.tip_amount
                FROM barber_appointments a
                JOIN transactions t ON a.appointment_id = t.reference_id AND t.reference_type = 'appointment' AND t.source_type = 'barber'
                WHERE a.staff_id = ? AND a.appointment_date BETWEEN ? AND ?
                AND a.status = 'completed' AND t.status = 'completed'
            ''', (staff_id, start_date, end_date)).fetchall()

            # Get commission rates
            rates = conn.execute('''
                SELECT * FROM barber_commissions WHERE staff_id = ?
            ''', (staff_id,)).fetchall()

            default_rate = 0.0
            service_rates = {}
            for r in rates:
                if r['service_id'] is None:
                    default_rate = r['rate']
                else:
                    service_rates[r['service_id']] = r['rate']

            total_revenue = 0.0
            total_commission = 0.0
            total_tips = 0.0

            for appt in appointments:
                revenue = appt['amount'] or 0
                tips = appt['tip_amount'] or 0
                rate = service_rates.get(appt['service_id'], default_rate)
                commission = revenue * (rate / 100)

                total_revenue += revenue
                total_commission += commission
                total_tips += tips

            return {
                'staff_id': staff_id,
                'period': {'start': start_date, 'end': end_date},
                'total_revenue': total_revenue,
                'total_commission': total_commission,
                'total_tips': total_tips,
                'total_earnings': total_commission + total_tips,
                'appointments_count': len(appointments)
            }

class GiftCardManager:
    """Manages gift cards"""

    @staticmethod
    def create_gift_card(amount: float, purchased_by: str,
                         recipient_name: str = None, recipient_email: str = None,
                         message: str = None, expires_at: str = None) -> Tuple[int, str]:
        """Create gift card"""
        import secrets
        code = f"GC-{secrets.token_hex(4).upper()}"

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_gift_cards
                (code, initial_amount, current_balance, purchased_by,
                 recipient_name, recipient_email, message, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (code, amount, amount, purchased_by, recipient_name,
                  recipient_email, message, expires_at))
            return cursor.lastrowid, code

    @staticmethod
    def get_gift_card(code: str) -> Optional[Dict]:
        """Get gift card by code"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM barber_gift_cards WHERE code = ?',
                (code,)
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def redeem_gift_card(code: str, amount: float, appointment_id: int = None,
                         redeemed_by: str = None) -> Tuple[bool, str]:
        """Redeem gift card"""
        with transaction() as conn:
            card = conn.execute(
                'SELECT * FROM barber_gift_cards WHERE code = ?', (code,)
            ).fetchone()

            if not card:
                return False, "Gift card not found"
            if card['is_redeemed'] and card['current_balance'] <= 0:
                return False, "Gift card has been fully redeemed"
            if card['expires_at'] and card['expires_at'] < datetime.now().isoformat():
                return False, "Gift card has expired"
            if card['current_balance'] < amount:
                return False, f"Insufficient balance. Available: £{card['current_balance']:.2f}"

            new_balance = card['current_balance'] - amount
            is_redeemed = 1 if new_balance <= 0 else 0

            conn.execute('''
                UPDATE barber_gift_cards
                SET current_balance = ?, is_redeemed = ?, redeemed_at = ?
                WHERE code = ?
            ''', (new_balance, is_redeemed, datetime.now().isoformat(), code))

            # Log redemption
            conn.execute('''
                INSERT INTO barber_gift_card_redemptions
                (gift_card_id, amount, appointment_id, redeemed_by)
                VALUES (?, ?, ?, ?)
            ''', (card['gift_card_id'], amount, appointment_id, redeemed_by))

            return True, f"Redeemed £{amount:.2f}. Remaining balance: £{new_balance:.2f}"

class DiscountManager:
    """Manages discounts"""

    @staticmethod
    def apply_discount(appointment_id: int, discount_type: str, value: float,
                       reason: str, applied_by: str) -> Tuple[float, float]:
        """Apply discount to appointment"""
        with transaction() as conn:
            appt = conn.execute(
                'SELECT price FROM barber_appointments WHERE appointment_id = ?',
                (appointment_id,)
            ).fetchone()

            if not appt:
                raise ValueError("Appointment not found")

            original_price = appt['price']
            if discount_type == 'percentage':
                discount_amount = original_price * (value / 100)
            else:
                discount_amount = value

            new_price = max(0, original_price - discount_amount)

            conn.execute('''
                UPDATE barber_appointments
                SET price = ?, notes = COALESCE(notes, '') || ? || ?
                WHERE appointment_id = ?
            ''', (new_price, '\nDiscount: ', f'{discount_type} {value} - {reason}', appointment_id))

            conn.execute('''
                INSERT INTO barber_discounts
                (appointment_id, discount_type, value, original_price, final_price, reason, applied_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (appointment_id, discount_type, value, original_price, new_price, reason, applied_by))

            return original_price, new_price

class RefundManager:
    """Manages refunds"""

    @staticmethod
    def issue_refund(transaction_id: int, amount: float, reason: str,
                     refund_type: str, processed_by: str) -> int:
        """Issue refund"""
        with transaction() as conn:
            trans = conn.execute(
                'SELECT * FROM transactions WHERE transaction_id = ? AND source_type = ?',
                (transaction_id, 'barber')
            ).fetchone()

            if not trans:
                raise ValueError("Transaction not found")

            cursor = conn.execute('''
                INSERT INTO unified_refunds
                (source_type, reference_id, reference_type, original_amount, amount,
                 refund_type, reason, processed_by, refund_date, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 'processed')
            ''', ('barber', str(trans['reference_id']), 'appointment',
                  trans['amount'], amount, refund_type, reason, processed_by,
                  f'barber_transaction_{transaction_id}'))
            refund_row_id = cursor.lastrowid

            conn.execute('''
                UPDATE transactions SET status = 'refunded' WHERE transaction_id = ? AND source_type = 'barber'
            ''', (transaction_id,))

        # Auto-post to GL (cash has moved). Never raises.
        try:
            from education_system.university_system.modules.domain.finance.ledger import notify_ledger
            notify_ledger('refund', refund_row_id, posted_by=processed_by or 'barber')
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

        return refund_row_id

class CashDrawerManager:
    """Manages cash drawer"""

    @staticmethod
    def open_drawer(opening_amount: float, opened_by: str) -> int:
        """Open cash drawer"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_cash_drawer
                (opening_amount, opened_by, status)
                VALUES (?, ?, 'open')
            ''', (opening_amount, opened_by))
            return cursor.lastrowid

    @staticmethod
    def close_drawer(drawer_id: int, closing_amount: float, closed_by: str,
                     notes: str = None) -> Dict:
        """Close cash drawer"""
        with transaction() as conn:
            drawer = conn.execute(
                'SELECT * FROM barber_cash_drawer WHERE drawer_id = ?',
                (drawer_id,)
            ).fetchone()

            if not drawer:
                raise ValueError("Drawer not found")

            # Calculate expected
            cash_trans = conn.execute('''
                SELECT SUM(amount + tip_amount) as total
                FROM transactions
                WHERE source_type = 'barber' AND payment_method = 'cash' AND DATE(created_at) = DATE(?)
                AND status = 'completed'
            ''', (drawer['opened_at'],)).fetchone()

            expected = (drawer['opening_amount'] or 0) + (cash_trans['total'] or 0)
            discrepancy = closing_amount - expected

            conn.execute('''
                UPDATE barber_cash_drawer
                SET closing_amount = ?, expected_amount = ?, discrepancy = ?,
                    closed_by = ?, closed_at = ?, notes = ?, status = 'closed'
                WHERE drawer_id = ?
            ''', (closing_amount, expected, discrepancy, closed_by,
                  datetime.now().isoformat(), notes, drawer_id))

            return {
                'opening': drawer['opening_amount'],
                'expected': expected,
                'actual': closing_amount,
                'discrepancy': discrepancy
            }

class AuditLogManager:
    """Manages audit log"""

    @staticmethod
    def log_action(action_type: str, entity_type: str, entity_id: str,
                   details: str, user_id: str, ip_address: str = None) -> int:
        """Log an action"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_audit_log
                (action_type, entity_type, entity_id, details, user_id, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (action_type, entity_type, entity_id, details, user_id, ip_address))
            return cursor.lastrowid

    @staticmethod
    def get_audit_log(start_date: str = None, end_date: str = None,
                      action_type: str = None, user_id: str = None,
                      limit: int = 100) -> List[Dict]:
        """Get audit log entries"""
        with get_db_connection() as conn:
            query = 'SELECT * FROM barber_audit_log WHERE 1=1'
            params = []
            if start_date:
                query += ' AND DATE(created_at) >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND DATE(created_at) <= ?'
                params.append(end_date)
            if action_type:
                query += ' AND action_type = ?'
                params.append(action_type)
            if user_id:
                query += ' AND user_id = ?'
                params.append(user_id)
            query += f' ORDER BY created_at DESC LIMIT {limit}'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

class AnalyticsManager:
    """Manages analytics and reporting"""

    @staticmethod
    def get_dashboard_stats() -> Dict:
        """Get dashboard statistics"""
        today = datetime.now().strftime('%Y-%m-%d')
        with get_db_connection() as conn:
            # Today's appointments
            todays = conn.execute('''
                SELECT COUNT(*) as count,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled,
                       SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) as no_shows
                FROM barber_appointments WHERE appointment_date = ?
            ''', (today,)).fetchone()

            # Today's revenue
            revenue = conn.execute('''
                SELECT SUM(amount) as revenue, SUM(tip_amount) as tips
                FROM transactions
                WHERE source_type = 'barber' AND DATE(created_at) = ? AND status = 'completed'
            ''', (today,)).fetchone()

            # Active staff
            staff = conn.execute(
                'SELECT COUNT(*) as count FROM barber_staff WHERE is_active = 1'
            ).fetchone()

            # This month stats
            month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            monthly = conn.execute('''
                SELECT COUNT(*) as appointments, SUM(amount) as revenue
                FROM transactions
                WHERE source_type = 'barber' AND DATE(created_at) >= ? AND status = 'completed'
            ''', (month_start,)).fetchone()

            return {
                'today': {
                    'total_appointments': todays['count'] or 0,
                    'completed': todays['completed'] or 0,
                    'scheduled': todays['scheduled'] or 0,
                    'no_shows': todays['no_shows'] or 0,
                    'revenue': revenue['revenue'] or 0,
                    'tips': revenue['tips'] or 0
                },
                'active_staff': staff['count'] or 0,
                'monthly': {
                    'appointments': monthly['appointments'] or 0,
                    'revenue': monthly['revenue'] or 0
                }
            }

    @staticmethod
    def get_peak_hours(start_date: str, end_date: str) -> List[Dict]:
        """Analyze peak hours"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT appointment_time, COUNT(*) as count
                FROM barber_appointments
                WHERE appointment_date BETWEEN ? AND ?
                AND status NOT IN ('cancelled')
                GROUP BY appointment_time
                ORDER BY count DESC
            ''', (start_date, end_date)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_customer_retention(start_date: str, end_date: str) -> Dict:
        """Customer retention metrics"""
        with get_db_connection() as conn:
            # Total unique customers
            total = conn.execute('''
                SELECT COUNT(DISTINCT customer_id) as count
                FROM barber_appointments
                WHERE appointment_date BETWEEN ? AND ?
            ''', (start_date, end_date)).fetchone()

            # New customers (first visit in period)
            new = conn.execute('''
                SELECT COUNT(DISTINCT customer_id) as count
                FROM barber_appointments a
                WHERE appointment_date BETWEEN ? AND ?
                AND NOT EXISTS (
                    SELECT 1 FROM barber_appointments b
                    WHERE b.customer_id = a.customer_id
                    AND b.appointment_date < ?
                )
            ''', (start_date, end_date, start_date)).fetchone()

            # Returning customers
            returning = (total['count'] or 0) - (new['count'] or 0)

            return {
                'period': {'start': start_date, 'end': end_date},
                'total_customers': total['count'] or 0,
                'new_customers': new['count'] or 0,
                'returning_customers': returning,
                'retention_rate': (returning / total['count'] * 100) if total['count'] else 0
            }

    @staticmethod
    def get_service_popularity(start_date: str, end_date: str) -> List[Dict]:
        """Service popularity report"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT service_name, COUNT(*) as bookings,
                       SUM(price) as revenue,
                       AVG(price) as avg_price
                FROM barber_appointments
                WHERE appointment_date BETWEEN ? AND ?
                AND status = 'completed'
                GROUP BY service_id, service_name
                ORDER BY bookings DESC
            ''', (start_date, end_date)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_staff_performance(start_date: str, end_date: str) -> List[Dict]:
        """Staff performance report"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT
                    a.staff_id, a.staff_name,
                    COUNT(*) as appointments,
                    SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN a.status = 'no_show' THEN 1 ELSE 0 END) as no_shows,
                    SUM(t.amount) as revenue,
                    SUM(t.tip_amount) as tips,
                    AVG(f.rating) as avg_rating
                FROM barber_appointments a
                LEFT JOIN transactions t ON a.appointment_id = t.reference_id AND t.reference_type = 'appointment' AND t.source_type = 'barber'
                LEFT JOIN barber_feedback f ON a.appointment_id = f.appointment_id
                WHERE a.appointment_date BETWEEN ? AND ?
                AND a.staff_id IS NOT NULL
                GROUP BY a.staff_id, a.staff_name
                ORDER BY revenue DESC
            ''', (start_date, end_date)).fetchall()
            return [dict(row) for row in rows]

class ScheduledReportManager:
    """Manages scheduled reports"""

    @staticmethod
    def schedule_report(report_type: str, frequency: str, recipients: str,
                        created_by: str, params: str = None) -> int:
        """Schedule automated report"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_scheduled_reports
                (report_type, frequency, recipients, params, created_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (report_type, frequency, recipients, params, created_by))
            return cursor.lastrowid

    @staticmethod
    def get_scheduled_reports() -> List[Dict]:
        """Get all scheduled reports"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM barber_scheduled_reports WHERE is_active = 1
            ''').fetchall()
            return [dict(row) for row in rows]

class NoShowManager:
    """Manages no-shows"""

    @staticmethod
    def mark_no_show(appointment_id: int, marked_by: str, add_to_watchlist: bool = False) -> bool:
        """Mark appointment as no-show"""
        with transaction() as conn:
            appt = conn.execute(
                'SELECT * FROM barber_appointments WHERE appointment_id = ?',
                (appointment_id,)
            ).fetchone()

            if not appt:
                return False

            conn.execute('''
                UPDATE barber_appointments SET status = 'no_show', updated_at = ?
                WHERE appointment_id = ?
            ''', (datetime.now().isoformat(), appointment_id))

            # Track no-show
            conn.execute('''
                INSERT INTO barber_no_shows
                (appointment_id, customer_id, marked_by, added_to_watchlist)
                VALUES (?, ?, ?, ?)
            ''', (appointment_id, appt['customer_id'], marked_by, add_to_watchlist))

            # Update customer profile no-show count
            conn.execute('''
                UPDATE barber_customer_profiles
                SET no_show_count = COALESCE(no_show_count, 0) + 1
                WHERE customer_id = ?
            ''', (appt['customer_id'],))

            return True

    @staticmethod
    def get_no_show_history(customer_id: str) -> List[Dict]:
        """Get customer's no-show history"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT n.*, a.appointment_date, a.appointment_time, a.service_name
                FROM barber_no_shows n
                JOIN barber_appointments a ON n.appointment_id = a.appointment_id
                WHERE n.customer_id = ?
                ORDER BY n.created_at DESC
            ''', (customer_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_watchlist() -> List[Dict]:
        """Get no-show watchlist"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT customer_id, COUNT(*) as no_show_count,
                       MAX(created_at) as last_no_show
                FROM barber_no_shows
                WHERE added_to_watchlist = 1
                GROUP BY customer_id
                ORDER BY no_show_count DESC
            ''').fetchall()
            return [dict(row) for row in rows]

class ReminderManager:
    """Manages appointment reminders"""

    @staticmethod
    def schedule_reminder(appointment_id: int, reminder_type: str,
                          send_at: str, channel: str) -> int:
        """Schedule appointment reminder"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO barber_reminders
                (appointment_id, reminder_type, scheduled_for, channel)
                VALUES (?, ?, ?, ?)
            ''', (appointment_id, reminder_type, send_at, channel))
            return cursor.lastrowid

    @staticmethod
    def get_pending_reminders() -> List[Dict]:
        """Get reminders to send"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT r.*, a.customer_name, a.customer_email, a.customer_phone,
                       a.appointment_date, a.appointment_time, a.service_name
                FROM barber_reminders r
                JOIN barber_appointments a ON r.appointment_id = a.appointment_id
                WHERE r.is_sent = 0 AND r.scheduled_for <= ?
                AND a.status = 'scheduled'
            ''', (datetime.now().isoformat(),)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def mark_sent(reminder_id: int) -> bool:
        """Mark reminder as sent"""
        with transaction() as conn:
            conn.execute('''
                UPDATE barber_reminders SET is_sent = 1, sent_at = ?
                WHERE reminder_id = ?
            ''', (datetime.now().isoformat(), reminder_id))
            return True

def init_extended_barber_db():
    """Initialize extended barber shop database tables"""
    with transaction() as conn:
        # Waitlist table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_waitlist (
                waitlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                customer_phone TEXT,
                preferred_date TEXT NOT NULL,
                preferred_time TEXT,
                service_id INTEGER,
                staff_id INTEGER,
                notes TEXT,
                status TEXT DEFAULT 'waiting',
                notification_sent_at TEXT,
                available_slot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Blocked slots table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_blocked_slots (
                block_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                blocked_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                reason TEXT,
                blocked_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (staff_id) REFERENCES barber_staff(staff_id)
            )
        ''')

        # Recurring appointments table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_recurring_appointments (
                recurring_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                service_id INTEGER NOT NULL,
                staff_id INTEGER,
                day_of_week INTEGER NOT NULL,
                appointment_time TEXT NOT NULL,
                frequency TEXT DEFAULT 'weekly',
                start_date TEXT NOT NULL,
                end_date TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Customer profiles (extended)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_customer_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                preferences TEXT,
                allergies TEXT,
                notes TEXT,
                is_vip INTEGER DEFAULT 0,
                total_visits INTEGER DEFAULT 0,
                total_spent DECIMAL(10,2) DEFAULT 0,
                no_show_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Customer notes
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_customer_notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                note TEXT NOT NULL,
                note_type TEXT DEFAULT 'general',
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Feedback table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_feedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER,
                customer_id TEXT NOT NULL,
                staff_id INTEGER,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (appointment_id) REFERENCES barber_appointments(appointment_id)
            )
        ''')

        # Service packages
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_service_packages (
                package_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                services TEXT,
                total_price DECIMAL(10,2) NOT NULL,
                discount_percent DECIMAL(5,2) DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Service add-ons
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_service_addons (
                addon_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price DECIMAL(10,2) NOT NULL,
                duration_minutes INTEGER DEFAULT 5,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Staff schedules
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_staff_schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                start_time TEXT,
                end_time TEXT,
                is_working INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (staff_id) REFERENCES barber_staff(staff_id)
            )
        ''')

        # Commissions
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_commissions (
                commission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                commission_type TEXT DEFAULT 'percentage',
                rate DECIMAL(5,2) NOT NULL,
                service_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (staff_id) REFERENCES barber_staff(staff_id)
            )
        ''')

        # Gift cards
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_gift_cards (
                gift_card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                initial_amount DECIMAL(10,2) NOT NULL,
                current_balance DECIMAL(10,2) NOT NULL,
                purchased_by TEXT,
                recipient_name TEXT,
                recipient_email TEXT,
                message TEXT,
                is_redeemed INTEGER DEFAULT 0,
                redeemed_at TEXT,
                expires_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Gift card redemptions
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_gift_card_redemptions (
                redemption_id INTEGER PRIMARY KEY AUTOINCREMENT,
                gift_card_id INTEGER NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                appointment_id INTEGER,
                redeemed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gift_card_id) REFERENCES barber_gift_cards(gift_card_id)
            )
        ''')

        # Discounts
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_discounts (
                discount_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                discount_type TEXT NOT NULL,
                value DECIMAL(10,2) NOT NULL,
                original_price DECIMAL(10,2) NOT NULL,
                final_price DECIMAL(10,2) NOT NULL,
                reason TEXT,
                applied_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (appointment_id) REFERENCES barber_appointments(appointment_id)
            )
        ''')

        # Refunds - uses unified_refunds table

        # Cash drawer
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_cash_drawer (
                drawer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                opening_amount DECIMAL(10,2) NOT NULL,
                closing_amount DECIMAL(10,2),
                expected_amount DECIMAL(10,2),
                discrepancy DECIMAL(10,2),
                opened_by TEXT NOT NULL,
                closed_by TEXT,
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT,
                notes TEXT,
                status TEXT DEFAULT 'open'
            )
        ''')

        # Audit log
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                details TEXT,
                user_id TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Scheduled reports
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_scheduled_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL,
                frequency TEXT NOT NULL,
                recipients TEXT NOT NULL,
                params TEXT,
                last_run TEXT,
                next_run TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # No-shows tracking
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_no_shows (
                no_show_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                customer_id TEXT NOT NULL,
                marked_by TEXT,
                added_to_watchlist INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (appointment_id) REFERENCES barber_appointments(appointment_id)
            )
        ''')

        # Reminders
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                reminder_type TEXT NOT NULL,
                scheduled_for TEXT NOT NULL,
                channel TEXT DEFAULT 'email',
                is_sent INTEGER DEFAULT 0,
                sent_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (appointment_id) REFERENCES barber_appointments(appointment_id)
            )
        ''')

        # Seasonal pricing
        conn.execute('''
            CREATE TABLE IF NOT EXISTS barber_seasonal_pricing (
                pricing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                promotional_price DECIMAL(10,2) NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (service_id) REFERENCES barber_services(service_id)
            )
        ''')

        logger.info("Extended barber shop database tables initialized successfully")

def launch_barber_gui(parent=None, auth=None):
    """Launch the Barber Shop GUI"""
    from education_system.university_system.modules.domain.commerce.barber.gui.barber_gui import BarberGUI
    return BarberGUI(parent, auth)
