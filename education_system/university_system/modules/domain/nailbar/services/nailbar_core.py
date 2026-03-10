"""Nail Bar/Salon Core Services Module

Provides business logic for nail bar/salon operations including
treatments, appointments, technicians, and transaction management.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from education_system.university_system.infrastructure.database.db import get_db_connection, transaction

logger = logging.getLogger(__name__)

# Treatment categories
TREATMENT_CATEGORIES = {
    'manicure': 'Manicure',
    'pedicure': 'Pedicure',
    'gel_nails': 'Gel Nails',
    'acrylic_nails': 'Acrylic Nails',
    'nail_art': 'Nail Art',
    'polish_change': 'Polish Change',
    'nail_repair': 'Nail Repair',
    'spa_treatment': 'Spa Treatment',
    'waxing': 'Waxing',
    'lash_brow': 'Lash & Brow'
}

# Appointment statuses
APPOINTMENT_STATUSES = ['booked', 'confirmed', 'checked_in', 'in_progress', 'completed', 'cancelled', 'no_show']

# Time slots (30-minute intervals)
TIME_SLOTS = [
    '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
    '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
    '15:00', '15:30', '16:00', '16:30', '17:00', '17:30', '18:00'
]

def init_nailbar_db():
    """Initialize nail bar database tables"""
    with transaction() as conn:
        # Treatments table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS nailbar_treatments (
                treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER DEFAULT 45,
                price DECIMAL(10,2) NOT NULL,
                is_available INTEGER DEFAULT 1,
                requires_appointment INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Technicians table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS nailbar_technicians (
                technician_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE,
                specialties TEXT,
                phone TEXT,
                email TEXT,
                certification TEXT,
                is_active INTEGER DEFAULT 1,
                hire_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Appointments table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS nailbar_appointments (
                appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_reference TEXT UNIQUE NOT NULL,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                customer_phone TEXT,
                technician_id INTEGER,
                technician_name TEXT,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                status TEXT DEFAULT 'booked',
                total_amount DECIMAL(10,2) DEFAULT 0.00,
                payment_status TEXT DEFAULT 'pending',
                payment_method TEXT,
                special_requests TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (technician_id) REFERENCES nailbar_technicians(technician_id)
            )
        ''')

        # Appointment treatments (many-to-many)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS nailbar_appointment_treatments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                treatment_id INTEGER NOT NULL,
                treatment_name TEXT NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                duration_minutes INTEGER NOT NULL,
                notes TEXT,
                FOREIGN KEY (appointment_id) REFERENCES nailbar_appointments(appointment_id),
                FOREIGN KEY (treatment_id) REFERENCES nailbar_treatments(treatment_id)
            )
        ''')

        # Transactions table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS nailbar_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER,
                customer_id TEXT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_method TEXT NOT NULL,
                transaction_type TEXT DEFAULT 'service',
                tip_amount DECIMAL(10,2) DEFAULT 0,
                reference_number TEXT,
                status TEXT DEFAULT 'completed',
                receipt_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_by TEXT,
                FOREIGN KEY (appointment_id) REFERENCES nailbar_appointments(appointment_id)
            )
        ''')

        # Customer preferences table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS nailbar_customer_preferences (
                preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL UNIQUE,
                preferred_technician_id INTEGER,
                favorite_colors TEXT,
                nail_type TEXT,
                allergies TEXT,
                last_visit TEXT,
                visit_count INTEGER DEFAULT 0,
                loyalty_points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Insert default treatments if empty
        existing = conn.execute('SELECT COUNT(*) FROM nailbar_treatments').fetchone()[0]
        if existing == 0:
            default_treatments = [
                ('Classic Manicure', 'manicure', 'Nail shaping, cuticle care, hand massage, polish', 30, 18.00),
                ('Deluxe Manicure', 'manicure', 'Classic manicure with exfoliation and mask', 45, 28.00),
                ('Classic Pedicure', 'pedicure', 'Foot soak, nail care, callus removal, polish', 45, 25.00),
                ('Deluxe Pedicure', 'pedicure', 'Luxury pedicure with scrub, mask and massage', 60, 38.00),
                ('Gel Manicure', 'gel_nails', 'Long-lasting gel polish manicure', 45, 32.00),
                ('Gel Pedicure', 'gel_nails', 'Long-lasting gel polish pedicure', 60, 40.00),
                ('Acrylic Full Set', 'acrylic_nails', 'Full set of acrylic nail extensions', 90, 45.00),
                ('Acrylic Infill', 'acrylic_nails', 'Acrylic nail maintenance and infill', 60, 30.00),
                ('Nail Art (per nail)', 'nail_art', 'Custom nail art design per nail', 10, 5.00),
                ('Polish Change', 'polish_change', 'Quick polish change', 15, 10.00),
                ('Nail Repair', 'nail_repair', 'Single nail repair', 15, 8.00),
                ('Eyebrow Wax', 'waxing', 'Eyebrow shaping with wax', 15, 12.00),
            ]
            conn.executemany('''
                INSERT INTO nailbar_treatments (name, category, description, duration_minutes, price)
                VALUES (?, ?, ?, ?, ?)
            ''', default_treatments)

        logger.info("Nail bar database tables initialized successfully")

class TreatmentManager:
    """Manages nail bar treatments"""

    @staticmethod
    def add_treatment(name: str, category: str, price: float,
                     duration_minutes: int = 45, description: str = None) -> int:
        """Add a new treatment"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO nailbar_treatments (name, category, description, duration_minutes, price)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, category, description, duration_minutes, price))
            return cursor.lastrowid

    @staticmethod
    def get_treatment(treatment_id: int) -> Optional[Dict]:
        """Get treatment by ID"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM nailbar_treatments WHERE treatment_id = ?',
                (treatment_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def get_all_treatments(category: str = None, available_only: bool = True) -> List[Dict]:
        """Get all treatments, optionally filtered by category"""
        with get_db_connection() as conn:
            query = 'SELECT * FROM nailbar_treatments WHERE 1=1'
            params = []

            if category:
                query += ' AND category = ?'
                params.append(category)

            if available_only:
                query += ' AND is_available = 1'

            query += ' ORDER BY category, name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_treatment(treatment_id: int, **kwargs) -> bool:
        """Update treatment details"""
        allowed_fields = ['name', 'category', 'description', 'duration_minutes',
                         'price', 'is_available']

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        values = list(updates.values()) + [treatment_id]

        with transaction() as conn:
            conn.execute(
                f'UPDATE nailbar_treatments SET {set_clause} WHERE treatment_id = ?',
                values
            )
            return True

class TechnicianManager:
    """Manages nail technicians"""

    @staticmethod
    def add_technician(name: str, employee_id: str = None, specialties: str = None,
                      phone: str = None, email: str = None, certification: str = None) -> int:
        """Add new technician"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO nailbar_technicians
                (name, employee_id, specialties, phone, email, certification, hire_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, employee_id, specialties, phone, email, certification,
                  datetime.now().strftime('%Y-%m-%d')))
            return cursor.lastrowid

    @staticmethod
    def get_technician(technician_id: int) -> Optional[Dict]:
        """Get technician by ID"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM nailbar_technicians WHERE technician_id = ?',
                (technician_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def get_all_technicians(active_only: bool = True) -> List[Dict]:
        """Get all technicians"""
        with get_db_connection() as conn:
            query = 'SELECT * FROM nailbar_technicians'
            if active_only:
                query += ' WHERE is_active = 1'
            query += ' ORDER BY name'
            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_technician_availability(technician_id: int, date: str) -> List[str]:
        """Get available time slots for a technician on a date"""
        with get_db_connection() as conn:
            booked = conn.execute('''
                SELECT appointment_time FROM nailbar_appointments
                WHERE technician_id = ? AND appointment_date = ?
                AND status NOT IN ('cancelled', 'no_show')
            ''', (technician_id, date)).fetchall()

            booked_times = set(row['appointment_time'] for row in booked)
            return [slot for slot in TIME_SLOTS if slot not in booked_times]

class AppointmentManager:
    """Manages appointments"""

    @staticmethod
    def generate_booking_reference() -> str:
        """Generate unique booking reference"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        with get_db_connection() as conn:
            count = conn.execute(
                'SELECT COUNT(*) FROM nailbar_appointments WHERE DATE(created_at) = DATE(?)',
                (datetime.now().isoformat(),)
            ).fetchone()[0]
        return f"NB-{timestamp}-{count + 1:03d}"

    @staticmethod
    def create_appointment(customer_id: str, customer_name: str,
                          appointment_date: str, appointment_time: str,
                          treatment_ids: List[int], technician_id: int = None,
                          customer_email: str = None, customer_phone: str = None,
                          special_requests: str = None) -> Tuple[int, str]:
        """Create a new appointment with treatments"""
        booking_reference = AppointmentManager.generate_booking_reference()

        with transaction() as conn:
            # Get technician name if provided
            technician_name = None
            if technician_id:
                tech = conn.execute(
                    'SELECT name FROM nailbar_technicians WHERE technician_id = ?',
                    (technician_id,)
                ).fetchone()
                technician_name = tech['name'] if tech else None

            # Create appointment
            cursor = conn.execute('''
                INSERT INTO nailbar_appointments
                (booking_reference, customer_id, customer_name, customer_email, customer_phone,
                 technician_id, technician_name, appointment_date, appointment_time, special_requests)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (booking_reference, customer_id, customer_name, customer_email, customer_phone,
                  technician_id, technician_name, appointment_date, appointment_time, special_requests))

            appointment_id = cursor.lastrowid
            total_amount = 0

            # Add treatments
            for treatment_id in treatment_ids:
                treatment = conn.execute(
                    'SELECT * FROM nailbar_treatments WHERE treatment_id = ?',
                    (treatment_id,)
                ).fetchone()

                if treatment:
                    conn.execute('''
                        INSERT INTO nailbar_appointment_treatments
                        (appointment_id, treatment_id, treatment_name, price, duration_minutes)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (appointment_id, treatment_id, treatment['name'],
                          treatment['price'], treatment['duration_minutes']))
                    total_amount += treatment['price']

            # Update total amount
            conn.execute(
                'UPDATE nailbar_appointments SET total_amount = ? WHERE appointment_id = ?',
                (total_amount, appointment_id)
            )

            return appointment_id, booking_reference

    @staticmethod
    def get_appointment(appointment_id: int) -> Optional[Dict]:
        """Get appointment by ID with treatments"""
        with get_db_connection() as conn:
            appt = conn.execute(
                'SELECT * FROM nailbar_appointments WHERE appointment_id = ?',
                (appointment_id,)
            ).fetchone()

            if not appt:
                return None

            appt_dict = dict(appt)

            treatments = conn.execute(
                'SELECT * FROM nailbar_appointment_treatments WHERE appointment_id = ?',
                (appointment_id,)
            ).fetchall()
            appt_dict['treatments'] = [dict(t) for t in treatments]

            return appt_dict

    @staticmethod
    def get_appointment_by_reference(booking_reference: str) -> Optional[Dict]:
        """Get appointment by booking reference"""
        with get_db_connection() as conn:
            appt = conn.execute(
                'SELECT * FROM nailbar_appointments WHERE booking_reference = ?',
                (booking_reference,)
            ).fetchone()

            if appt:
                return AppointmentManager.get_appointment(appt['appointment_id'])
            return None

    @staticmethod
    def update_status(appointment_id: int, status: str, user_id: str = None) -> bool:
        """Update appointment status"""
        if status not in APPOINTMENT_STATUSES:
            return False

        with transaction() as conn:
            conn.execute('''
                UPDATE nailbar_appointments
                SET status = ?, updated_at = ?
                WHERE appointment_id = ?
            ''', (status, datetime.now().isoformat(), appointment_id))
            return True

    @staticmethod
    def cancel_appointment(appointment_id: int, reason: str = None) -> bool:
        """Cancel an appointment"""
        with transaction() as conn:
            conn.execute('''
                UPDATE nailbar_appointments
                SET status = 'cancelled', notes = ?, updated_at = ?
                WHERE appointment_id = ?
            ''', (reason, datetime.now().isoformat(), appointment_id))
            return True

    @staticmethod
    def reschedule_appointment(appointment_id: int, new_date: str,
                              new_time: str, new_technician_id: int = None) -> bool:
        """Reschedule an appointment"""
        with transaction() as conn:
            updates = {
                'appointment_date': new_date,
                'appointment_time': new_time,
                'updated_at': datetime.now().isoformat()
            }

            if new_technician_id:
                tech = conn.execute(
                    'SELECT name FROM nailbar_technicians WHERE technician_id = ?',
                    (new_technician_id,)
                ).fetchone()
                if tech:
                    updates['technician_id'] = new_technician_id
                    updates['technician_name'] = tech['name']

            set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
            values = list(updates.values()) + [appointment_id]

            conn.execute(
                f'UPDATE nailbar_appointments SET {set_clause} WHERE appointment_id = ?',
                values
            )
            return True

    @staticmethod
    def get_appointments_by_date(date: str) -> List[Dict]:
        """Get all appointments for a date"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM nailbar_appointments
                WHERE appointment_date = ?
                ORDER BY appointment_time
            ''', (date,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_customer_appointments(customer_id: str) -> List[Dict]:
        """Get all appointments for a customer"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM nailbar_appointments
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
            cursor = conn.execute('''
                INSERT INTO nailbar_transactions
                (appointment_id, customer_id, amount, payment_method, tip_amount,
                 reference_number, processed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (appointment_id, customer_id, amount, payment_method, tip_amount,
                  reference_number, processed_by))

            transaction_id = cursor.lastrowid

            conn.execute('''
                UPDATE nailbar_appointments
                SET payment_status = 'paid', payment_method = ?, updated_at = ?
                WHERE appointment_id = ?
            ''', (payment_method, datetime.now().isoformat(), appointment_id))

            # Record in main finance system
            try:
                conn.execute('''
                    INSERT INTO payments
                    (student_id, amount, payment_method, payment_date, status, notes, created_by)
                    VALUES (?, ?, ?, ?, 'completed', 'Nail Bar Service', ?)
                ''', (customer_id, amount + tip_amount, payment_method,
                      datetime.now().isoformat(), processed_by))
            except Exception as e:
                logger.warning(f"Could not record to main finance system: {e}")

            # Update customer loyalty
            try:
                loyalty_points = int(amount)
                conn.execute('''
                    INSERT INTO nailbar_customer_preferences (customer_id, visit_count, loyalty_points, last_visit)
                    VALUES (?, 1, ?, ?)
                    ON CONFLICT(customer_id) DO UPDATE SET
                        visit_count = visit_count + 1,
                        loyalty_points = loyalty_points + ?,
                        last_visit = ?
                ''', (customer_id, loyalty_points, datetime.now().strftime('%Y-%m-%d'),
                      loyalty_points, datetime.now().strftime('%Y-%m-%d')))
            except Exception:
                pass

            return transaction_id

    @staticmethod
    def get_transaction(transaction_id: int) -> Optional[Dict]:
        """Get transaction by ID"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM nailbar_transactions WHERE transaction_id = ?',
                (transaction_id,)
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def mark_receipt_sent(transaction_id: int) -> bool:
        """Mark receipt as sent"""
        with transaction() as conn:
            conn.execute(
                'UPDATE nailbar_transactions SET receipt_sent = 1 WHERE transaction_id = ?',
                (transaction_id,)
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
                FROM nailbar_transactions
                WHERE DATE(created_at) = ? AND status = 'completed'
            ''', (date,)).fetchone()

            return {
                'date': date,
                'transaction_count': row['transaction_count'] or 0,
                'service_revenue': row['service_revenue'] or 0,
                'tips': row['tips'] or 0,
                'total_revenue': row['total_revenue'] or 0
            }

class ReportManager:
    """Generates reports for the nail bar"""

    @staticmethod
    def generate_sales_report(start_date: str, end_date: str) -> Dict:
        """Generate sales report for date range"""
        with get_db_connection() as conn:
            summary = conn.execute('''
                SELECT
                    COUNT(*) as total_appointments,
                    SUM(amount) as service_revenue,
                    SUM(tip_amount) as total_tips,
                    AVG(amount) as avg_service_value
                FROM nailbar_transactions
                WHERE DATE(created_at) BETWEEN ? AND ? AND status = 'completed'
            ''', (start_date, end_date)).fetchone()

            by_treatment = conn.execute('''
                SELECT
                    at.treatment_name,
                    COUNT(*) as count,
                    SUM(at.price) as revenue
                FROM nailbar_appointment_treatments at
                JOIN nailbar_appointments a ON at.appointment_id = a.appointment_id
                WHERE DATE(a.created_at) BETWEEN ? AND ?
                    AND a.payment_status = 'paid'
                GROUP BY at.treatment_name
                ORDER BY count DESC
            ''', (start_date, end_date)).fetchall()

            by_technician = conn.execute('''
                SELECT
                    a.technician_name,
                    COUNT(*) as appointments,
                    SUM(t.amount) as revenue,
                    SUM(t.tip_amount) as tips
                FROM nailbar_transactions t
                JOIN nailbar_appointments a ON t.appointment_id = a.appointment_id
                WHERE DATE(t.created_at) BETWEEN ? AND ?
                    AND t.status = 'completed' AND a.technician_name IS NOT NULL
                GROUP BY a.technician_id, a.technician_name
                ORDER BY revenue DESC
            ''', (start_date, end_date)).fetchall()

            return {
                'period': {'start': start_date, 'end': end_date},
                'summary': dict(summary) if summary else {},
                'by_treatment': [dict(row) for row in by_treatment],
                'by_technician': [dict(row) for row in by_technician],
                'generated_at': datetime.now().isoformat()
            }

    @staticmethod
    def generate_admin_report() -> str:
        """Generate comprehensive admin report as text"""
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        daily_revenue = TransactionManager.get_daily_revenue(today)
        weekly_report = ReportManager.generate_sales_report(week_ago, today)
        todays_appointments = AppointmentManager.get_todays_appointments()

        # Safely get values with None handling
        weekly_summary = weekly_report.get('summary', {})
        weekly_total_appts = weekly_summary.get('total_appointments') or 0
        weekly_service_rev = weekly_summary.get('service_revenue') or 0
        weekly_tips = weekly_summary.get('total_tips') or 0
        weekly_avg_value = weekly_summary.get('avg_service_value') or 0

        report = f"""
NAIL BAR/SALON ADMIN REPORT
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
Total Appointments: {weekly_total_appts}
Service Revenue: £{weekly_service_rev:.2f}
Total Tips: £{weekly_tips:.2f}
Avg Service Value: £{weekly_avg_value:.2f}

TOP TREATMENTS
{'-' * 30}
"""
        for i, treatment in enumerate(weekly_report['by_treatment'][:5], 1):
            t_name = treatment.get('treatment_name', 'Unknown')
            t_count = treatment.get('count') or 0
            t_revenue = treatment.get('revenue') or 0
            report += f"{i}. {t_name}: {t_count} bookings (£{t_revenue:.2f})\n"

        if not weekly_report['by_treatment']:
            report += "No treatments recorded this week.\n"

        report += f"""
TECHNICIAN PERFORMANCE
{'-' * 30}
"""
        for tech in weekly_report['by_technician']:
            tech_name = tech.get('technician_name') or 'Unknown'
            tech_appts = tech.get('appointments') or 0
            tech_revenue = tech.get('revenue') or 0
            tech_tips = tech.get('tips') or 0
            report += f"  {tech_name}: {tech_appts} clients, £{tech_revenue:.2f} revenue, £{tech_tips:.2f} tips\n"

        if not weekly_report['by_technician']:
            report += "No technician performance data available.\n"

        report += f"""
{'=' * 50}
End of Report
"""
        return report

def launch_nailbar_gui(parent=None, auth=None):
    """Launch the Nail Bar GUI"""
    from education_system.university_system.modules.domain.nailbar.gui.nailbar_gui import NailBarGUI
    return NailBarGUI(parent, auth)
