"""
Dentist/Dental Clinic Core Services

Provides comprehensive dental clinic management including
appointments, treatments, patient records, and billing with
email and finance integration.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier, escape_like

# Constants
TREATMENT_TYPES = {
    'checkup': {'name': 'Routine Check-up', 'duration': 30, 'fee': 25.00},
    'cleaning': {'name': 'Professional Cleaning', 'duration': 45, 'fee': 45.00},
    'filling': {'name': 'Dental Filling', 'duration': 60, 'fee': 80.00},
    'extraction': {'name': 'Tooth Extraction', 'duration': 45, 'fee': 100.00},
    'root_canal': {'name': 'Root Canal', 'duration': 90, 'fee': 350.00},
    'crown': {'name': 'Dental Crown', 'duration': 60, 'fee': 450.00},
    'whitening': {'name': 'Teeth Whitening', 'duration': 60, 'fee': 150.00},
    'xray': {'name': 'Dental X-Ray', 'duration': 15, 'fee': 35.00},
    'emergency': {'name': 'Emergency Treatment', 'duration': 60, 'fee': 120.00},
    'consultation': {'name': 'Consultation', 'duration': 30, 'fee': 30.00}
}

APPOINTMENT_STATUSES = ['scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show']

DENTIST_STAFF = [
    {'id': 'DEN001', 'name': 'Dr. Sarah Mitchell', 'specialization': 'General Dentistry'},
    {'id': 'DEN002', 'name': 'Dr. James Wilson', 'specialization': 'Orthodontics'},
    {'id': 'DEN003', 'name': 'Dr. Emily Chen', 'specialization': 'Periodontics'},
    {'id': 'DEN004', 'name': 'Dr. Michael Brown', 'specialization': 'Endodontics'}
]

WORKING_HOURS = {
    'Monday': ('09:00', '17:00'),
    'Tuesday': ('09:00', '17:00'),
    'Wednesday': ('09:00', '17:00'),
    'Thursday': ('09:00', '17:00'),
    'Friday': ('09:00', '16:00'),
    'Saturday': ('10:00', '14:00')
}

APPOINTMENT_SLOTS = ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
                     '13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00']

def generate_appointment_ref() -> str:
    """Generate a unique appointment reference."""
    return f"DEN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

def generate_patient_id() -> str:
    """Generate a unique patient ID."""
    return f"PAT-{uuid.uuid4().hex[:8].upper()}"

def generate_reference() -> str:
    """Generate a unique reference number."""
    return f"REF-{uuid.uuid4().hex[:12].upper()}"

def init_dentist_db():
    """Initialize dentist database tables."""
    try:
        with transaction() as conn:
            # Patients table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dentist_patients (
                    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_number TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    user_email TEXT,
                    user_phone TEXT,
                    date_of_birth DATE,
                    address TEXT,
                    emergency_contact TEXT,
                    emergency_phone TEXT,
                    medical_history TEXT,
                    allergies TEXT,
                    insurance_provider TEXT,
                    insurance_number TEXT,
                    last_visit DATE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Appointments table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dentist_appointments (
                    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appointment_ref TEXT UNIQUE NOT NULL,
                    patient_id INTEGER NOT NULL,
                    dentist_id TEXT NOT NULL,
                    dentist_name TEXT NOT NULL,
                    appointment_date DATE NOT NULL,
                    appointment_time TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 30,
                    treatment_type TEXT NOT NULL,
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    reminder_sent INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
                )
            ''')

            # Treatments table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dentist_treatments (
                    treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appointment_id INTEGER,
                    patient_id INTEGER NOT NULL,
                    dentist_id TEXT NOT NULL,
                    dentist_name TEXT NOT NULL,
                    treatment_type TEXT NOT NULL,
                    treatment_date DATE NOT NULL,
                    tooth_number TEXT,
                    description TEXT,
                    fee DECIMAL(10,2) NOT NULL,
                    payment_status TEXT DEFAULT 'pending',
                    notes TEXT,
                    follow_up_required INTEGER DEFAULT 0,
                    follow_up_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (appointment_id) REFERENCES dentist_appointments(appointment_id),
                    FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
                )
            ''')

            # Dental records (X-rays, charts)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dentist_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    record_type TEXT NOT NULL,
                    record_date DATE NOT NULL,
                    description TEXT,
                    file_path TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
                )
            ''')

            # Prescriptions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dentist_prescriptions (
                    prescription_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    dentist_id TEXT NOT NULL,
                    dentist_name TEXT NOT NULL,
                    treatment_id INTEGER,
                    medication TEXT NOT NULL,
                    dosage TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    instructions TEXT,
                    prescribed_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id),
                    FOREIGN KEY (treatment_id) REFERENCES dentist_treatments(treatment_id)
                )
            ''')

            # NOTE: dentist transactions now use the unified 'transactions' table
            # with source_type = 'dentist'

        return True
    except Exception as e:
        print(f"Error initializing dentist database: {e}")
        return False

class PatientManager:
    """Manages patient records."""

    @staticmethod
    def register_patient(user_id: str, user_name: str, user_email: str,
                        user_phone: str = None, date_of_birth: str = None,
                        address: str = None, emergency_contact: str = None,
                        emergency_phone: str = None, medical_history: str = None,
                        allergies: str = None) -> Optional[Dict]:
        """Register a new patient."""
        try:
            patient_number = generate_patient_id()

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO dentist_patients
                    (patient_number, user_id, user_name, user_email, user_phone,
                     date_of_birth, address, emergency_contact, emergency_phone,
                     medical_history, allergies)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (patient_number, user_id, user_name, user_email, user_phone,
                      date_of_birth, address, emergency_contact, emergency_phone,
                      medical_history, allergies))

                patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            log_activity('create', 'dentist_patient', patient_id=patient_id,
                        details={'patient_number': patient_number})

            return {
                'patient_id': patient_id,
                'patient_number': patient_number
            }
        except Exception as e:
            print(f"Error registering patient: {e}")
            return None

    @staticmethod
    def get_patient(patient_id: int = None, user_id: str = None,
                   patient_number: str = None) -> Optional[Dict]:
        """Get patient details."""
        try:
            with get_connection() as conn:
                if patient_id:
                    cursor = conn.execute(
                        "SELECT * FROM dentist_patients WHERE patient_id = ?", (patient_id,))
                elif patient_number:
                    cursor = conn.execute(
                        "SELECT * FROM dentist_patients WHERE patient_number = ?", (patient_number,))
                else:
                    cursor = conn.execute(
                        "SELECT * FROM dentist_patients WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting patient: {e}")
            return None

    @staticmethod
    def get_all_patients() -> List[Dict]:
        """Get all patients."""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM dentist_patients ORDER BY user_name")
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting patients: {e}")
            return []

    @staticmethod
    def update_patient(patient_id: int, **kwargs) -> bool:
        """Update patient information."""
        try:
            allowed_fields = ['user_phone', 'address', 'emergency_contact', 'emergency_phone',
                            'medical_history', 'allergies', 'insurance_provider', 'insurance_number']
            updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
            if not updates:
                return False

            set_clause = ", ".join(validate_identifier(k, "column") + " = ?" for k in updates.keys())
            values = list(updates.values()) + [patient_id]

            with transaction() as conn:
                conn.execute(
                    "UPDATE dentist_patients SET " + set_clause + " WHERE patient_id = ?",
                    values)
            return True
        except Exception as e:
            print(f"Error updating patient: {e}")
            return False

    @staticmethod
    def search_patients(search_term: str) -> List[Dict]:
        """Search patients by name or number."""
        try:
            with get_connection() as conn:
                search = f"%{escape_like(search_term)}%"
                cursor = conn.execute('''
                    SELECT * FROM dentist_patients
                    WHERE patient_number LIKE ? OR user_name LIKE ? OR user_email LIKE ?
                    ORDER BY user_name
                ''', (search, search, search))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error searching patients: {e}")
            return []

class AppointmentManager:
    """Manages dental appointments."""

    @staticmethod
    def book_appointment(patient_id: int, dentist_id: str, dentist_name: str,
                        appointment_date: str, appointment_time: str,
                        treatment_type: str, notes: str = None,
                        created_by: str = None) -> Optional[Dict]:
        """Book a new appointment."""
        try:
            appointment_ref = generate_appointment_ref()
            treatment = TREATMENT_TYPES.get(treatment_type, TREATMENT_TYPES['consultation'])
            duration = treatment['duration']

            with transaction() as conn:
                # Check for conflicts
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM dentist_appointments
                    WHERE dentist_id = ? AND appointment_date = ? AND appointment_time = ?
                    AND status NOT IN ('cancelled', 'no_show')
                ''', (dentist_id, appointment_date, appointment_time))
                if cursor.fetchone()[0] > 0:
                    return None

                conn.execute('''
                    INSERT INTO dentist_appointments
                    (appointment_ref, patient_id, dentist_id, dentist_name,
                     appointment_date, appointment_time, duration_minutes,
                     treatment_type, notes, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (appointment_ref, patient_id, dentist_id, dentist_name,
                      appointment_date, appointment_time, duration,
                      treatment_type, notes, created_by))

                appointment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            log_activity('create', 'dentist_appointment',
                        details={'appointment_id': appointment_id, 'ref': appointment_ref, 'date': appointment_date})

            return {
                'appointment_id': appointment_id,
                'appointment_ref': appointment_ref,
                'estimated_fee': treatment['fee']
            }
        except Exception as e:
            print(f"Error booking appointment: {e}")
            return None

    @staticmethod
    def get_appointment(appointment_id: int = None, appointment_ref: str = None) -> Optional[Dict]:
        """Get appointment details."""
        try:
            with get_connection() as conn:
                if appointment_id:
                    cursor = conn.execute(
                        "SELECT * FROM dentist_appointments WHERE appointment_id = ?", (appointment_id,))
                else:
                    cursor = conn.execute(
                        "SELECT * FROM dentist_appointments WHERE appointment_ref = ?", (appointment_ref,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting appointment: {e}")
            return None

    @staticmethod
    def get_patient_appointments(patient_id: int, status: str = None) -> List[Dict]:
        """Get patient's appointments."""
        try:
            with get_connection() as conn:
                if status:
                    cursor = conn.execute('''
                        SELECT * FROM dentist_appointments
                        WHERE patient_id = ? AND status = ?
                        ORDER BY appointment_date DESC, appointment_time
                    ''', (patient_id, status))
                else:
                    cursor = conn.execute('''
                        SELECT * FROM dentist_appointments
                        WHERE patient_id = ?
                        ORDER BY appointment_date DESC, appointment_time
                    ''', (patient_id,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting appointments: {e}")
            return []

    @staticmethod
    def get_dentist_schedule(dentist_id: str, date: str) -> List[Dict]:
        """Get dentist's schedule for a date."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT a.*, p.user_name as patient_name
                    FROM dentist_appointments a
                    JOIN dentist_patients p ON a.patient_id = p.patient_id
                    WHERE a.dentist_id = ? AND a.appointment_date = ?
                    AND a.status NOT IN ('cancelled', 'no_show')
                    ORDER BY a.appointment_time
                ''', (dentist_id, date))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting schedule: {e}")
            return []

    @staticmethod
    def get_available_slots(dentist_id: str, date: str) -> List[str]:
        """Get available appointment slots."""
        try:
            booked = set()
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT appointment_time FROM dentist_appointments
                    WHERE dentist_id = ? AND appointment_date = ?
                    AND status NOT IN ('cancelled', 'no_show')
                ''', (dentist_id, date))
                for row in cursor.fetchall():
                    booked.add(row[0])

            return [slot for slot in APPOINTMENT_SLOTS if slot not in booked]
        except Exception as e:
            print(f"Error getting available slots: {e}")
            return APPOINTMENT_SLOTS

    @staticmethod
    def update_appointment_status(appointment_id: int, status: str) -> bool:
        """Update appointment status."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE dentist_appointments SET status = ? WHERE appointment_id = ?
                ''', (status, appointment_id))

                # Update patient's last visit if completed
                if status == 'completed':
                    cursor = conn.execute(
                        "SELECT patient_id, appointment_date FROM dentist_appointments WHERE appointment_id = ?",
                        (appointment_id,))
                    row = cursor.fetchone()
                    if row:
                        conn.execute('''
                            UPDATE dentist_patients SET last_visit = ? WHERE patient_id = ?
                        ''', (row[1], row[0]))
            return True
        except Exception as e:
            print(f"Error updating appointment: {e}")
            return False

    @staticmethod
    def cancel_appointment(appointment_id: int) -> bool:
        """Cancel an appointment."""
        return AppointmentManager.update_appointment_status(appointment_id, 'cancelled')

    @staticmethod
    def reschedule_appointment(appointment_id: int, new_date: str, new_time: str,
                               dentist_id: str = None) -> Optional[Dict]:
        """Reschedule an appointment to a new date/time."""
        try:
            with transaction() as conn:
                # Get current appointment details
                cursor = conn.execute(
                    "SELECT * FROM dentist_appointments WHERE appointment_id = ?",
                    (appointment_id,))
                row = cursor.fetchone()
                if not row:
                    return None

                columns = [desc[0] for desc in cursor.description]
                old_appt = dict(zip(columns, row))

                # Check for conflicts at new time slot
                check_dentist = dentist_id or old_appt['dentist_id']
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM dentist_appointments
                    WHERE dentist_id = ? AND appointment_date = ? AND appointment_time = ?
                    AND status NOT IN ('cancelled', 'no_show') AND appointment_id != ?
                ''', (check_dentist, new_date, new_time, appointment_id))
                if cursor.fetchone()[0] > 0:
                    return None  # Conflict exists

                # Update appointment
                if dentist_id:
                    # Get dentist name
                    dentist = next((d for d in DENTIST_STAFF if d['id'] == dentist_id), None)
                    dentist_name = dentist['name'] if dentist else old_appt['dentist_name']
                    conn.execute('''
                        UPDATE dentist_appointments
                        SET appointment_date = ?, appointment_time = ?,
                            dentist_id = ?, dentist_name = ?
                        WHERE appointment_id = ?
                    ''', (new_date, new_time, dentist_id, dentist_name, appointment_id))
                else:
                    conn.execute('''
                        UPDATE dentist_appointments
                        SET appointment_date = ?, appointment_time = ?
                        WHERE appointment_id = ?
                    ''', (new_date, new_time, appointment_id))

            log_activity('reschedule', 'dentist_appointment',
                        details={'appointment_id': appointment_id,
                                'old_date': old_appt['appointment_date'],
                                'old_time': old_appt['appointment_time'],
                                'new_date': new_date, 'new_time': new_time})

            return {
                'appointment_id': appointment_id,
                'old_date': old_appt['appointment_date'],
                'old_time': old_appt['appointment_time'],
                'new_date': new_date,
                'new_time': new_time
            }
        except Exception as e:
            print(f"Error rescheduling appointment: {e}")
            return None

    @staticmethod
    def get_todays_appointments() -> List[Dict]:
        """Get all appointments for today."""
        try:
            today = datetime.now().date().isoformat()
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT a.*, p.user_name as patient_name, p.user_phone
                    FROM dentist_appointments a
                    JOIN dentist_patients p ON a.patient_id = p.patient_id
                    WHERE a.appointment_date = ?
                    ORDER BY a.appointment_time
                ''', (today,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting today's appointments: {e}")
            return []

class TreatmentManager:
    """Manages dental treatments."""

    @staticmethod
    def record_treatment(patient_id: int, dentist_id: str, dentist_name: str,
                        treatment_type: str, treatment_date: str,
                        appointment_id: int = None, tooth_number: str = None,
                        description: str = None, notes: str = None,
                        follow_up_required: bool = False,
                        follow_up_date: str = None) -> Optional[Dict]:
        """Record a dental treatment."""
        try:
            treatment = TREATMENT_TYPES.get(treatment_type, TREATMENT_TYPES['consultation'])
            fee = treatment['fee']

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO dentist_treatments
                    (appointment_id, patient_id, dentist_id, dentist_name,
                     treatment_type, treatment_date, tooth_number, description,
                     fee, notes, follow_up_required, follow_up_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (appointment_id, patient_id, dentist_id, dentist_name,
                      treatment_type, treatment_date, tooth_number, description,
                      fee, notes, 1 if follow_up_required else 0, follow_up_date))

                treatment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            return {
                'treatment_id': treatment_id,
                'fee': fee
            }
        except Exception as e:
            print(f"Error recording treatment: {e}")
            return None

    @staticmethod
    def get_patient_treatments(patient_id: int) -> List[Dict]:
        """Get patient's treatment history."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM dentist_treatments
                    WHERE patient_id = ?
                    ORDER BY treatment_date DESC
                ''', (patient_id,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting treatments: {e}")
            return []

    @staticmethod
    def get_pending_payments(patient_id: int = None) -> List[Dict]:
        """Get treatments with pending payments."""
        try:
            with get_connection() as conn:
                if patient_id:
                    cursor = conn.execute('''
                        SELECT t.*, p.user_name as patient_name
                        FROM dentist_treatments t
                        JOIN dentist_patients p ON t.patient_id = p.patient_id
                        WHERE t.payment_status = 'pending' AND t.patient_id = ?
                        ORDER BY t.treatment_date DESC
                    ''', (patient_id,))
                else:
                    cursor = conn.execute('''
                        SELECT t.*, p.user_name as patient_name
                        FROM dentist_treatments t
                        JOIN dentist_patients p ON t.patient_id = p.patient_id
                        WHERE t.payment_status = 'pending'
                        ORDER BY t.treatment_date DESC
                    ''')
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting pending payments: {e}")
            return []

class PrescriptionManager:
    """Manages dental prescriptions."""

    @staticmethod
    def create_prescription(patient_id: int, dentist_id: str, dentist_name: str,
                           medication: str, dosage: str, frequency: str,
                           duration: str, instructions: str = None,
                           treatment_id: int = None) -> Optional[Dict]:
        """Create a prescription."""
        try:
            prescribed_date = datetime.now().date().isoformat()

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO dentist_prescriptions
                    (patient_id, dentist_id, dentist_name, treatment_id,
                     medication, dosage, frequency, duration, instructions, prescribed_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (patient_id, dentist_id, dentist_name, treatment_id,
                      medication, dosage, frequency, duration, instructions, prescribed_date))

                prescription_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            return {'prescription_id': prescription_id}
        except Exception as e:
            print(f"Error creating prescription: {e}")
            return None

    @staticmethod
    def get_patient_prescriptions(patient_id: int) -> List[Dict]:
        """Get patient's prescriptions."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM dentist_prescriptions
                    WHERE patient_id = ?
                    ORDER BY prescribed_date DESC
                ''', (patient_id,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting prescriptions: {e}")
            return []

class TransactionManager:
    """Manages dental transactions."""

    @staticmethod
    def record_payment(user_id: str, patient_id: int, amount: float,
                      payment_method: str, transaction_type: str = 'treatment',
                      treatment_id: int = None, processed_by: str = None) -> Optional[Dict]:
        """Record a payment transaction."""
        try:
            reference = generate_reference()

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO transactions
                    (source_type, reference_number, customer_id, user_id,
                     reference_id, reference_type, transaction_type,
                     amount, payment_method, processed_by)
                    VALUES ('dentist', ?, ?, ?, ?, 'treatment', ?, ?, ?, ?)
                ''', (reference, patient_id, user_id, treatment_id,
                      transaction_type, amount, payment_method, processed_by))

                transaction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                # Update treatment payment status
                if treatment_id:
                    conn.execute('''
                        UPDATE dentist_treatments SET payment_status = 'paid' WHERE treatment_id = ?
                    ''', (treatment_id,))

            return {
                'transaction_id': transaction_id,
                'reference': reference,
                'amount': amount
            }
        except Exception as e:
            print(f"Error recording payment: {e}")
            return None

    @staticmethod
    def get_patient_transactions(patient_id: int, limit: int = 50) -> List[Dict]:
        """Get patient's transaction history."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM transactions WHERE source_type = 'dentist' AND customer_id = ?
                    ORDER BY created_at DESC LIMIT ?
                ''', (patient_id, limit))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return []

class ReportManager:
    """Manages dental clinic reporting."""

    @staticmethod
    def get_daily_report(date: str = None) -> Dict:
        """Generate daily operations report."""
        try:
            if not date:
                date = datetime.now().date().isoformat()

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM dentist_appointments WHERE appointment_date = ?
                ''', (date,))
                total_appointments = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COUNT(*) FROM dentist_appointments
                    WHERE appointment_date = ? AND status = 'completed'
                ''', (date,))
                completed = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COALESCE(SUM(amount), 0) FROM transactions
                    WHERE source_type = 'dentist' AND DATE(created_at) = ?
                ''', (date,))
                revenue = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COUNT(*) FROM dentist_treatments WHERE treatment_date = ?
                ''', (date,))
                treatments = cursor.fetchone()[0]

                return {
                    'date': date,
                    'total_appointments': total_appointments,
                    'completed_appointments': completed,
                    'treatments_performed': treatments,
                    'revenue': revenue
                }
        except Exception as e:
            print(f"Error generating daily report: {e}")
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
                    SELECT treatment_type, COUNT(*), COALESCE(SUM(fee), 0)
                    FROM dentist_treatments
                    WHERE strftime('%Y', treatment_date) = ? AND strftime('%m', treatment_date) = ?
                    GROUP BY treatment_type
                ''', (str(year), f"{month:02d}"))
                by_type = {row[0]: {'count': row[1], 'revenue': row[2]} for row in cursor.fetchall()}

                cursor = conn.execute('''
                    SELECT COALESCE(SUM(amount), 0) FROM transactions
                    WHERE source_type = 'dentist' AND strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ?
                ''', (str(year), f"{month:02d}"))
                total_revenue = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COUNT(*) FROM dentist_patients
                    WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ?
                ''', (str(year), f"{month:02d}"))
                new_patients = cursor.fetchone()[0]

                cursor = conn.execute('''
                    SELECT COUNT(*) FROM dentist_appointments
                    WHERE strftime('%Y', appointment_date) = ? AND strftime('%m', appointment_date) = ?
                ''', (str(year), f"{month:02d}"))
                total_appointments = cursor.fetchone()[0]

                return {
                    'year': year,
                    'month': month,
                    'treatments_by_type': by_type,
                    'total_revenue': total_revenue,
                    'new_patients': new_patients,
                    'total_appointments': total_appointments
                }
        except Exception as e:
            print(f"Error generating monthly summary: {e}")
            return {}

    @staticmethod
    def get_upcoming_appointments(days: int = 7) -> List[Dict]:
        """Get upcoming appointments for reminders."""
        try:
            start_date = datetime.now().date().isoformat()
            end_date = (datetime.now() + timedelta(days=days)).date().isoformat()

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT a.*, p.user_name, p.user_email, p.user_phone
                    FROM dentist_appointments a
                    JOIN dentist_patients p ON a.patient_id = p.patient_id
                    WHERE a.appointment_date BETWEEN ? AND ?
                    AND a.status IN ('scheduled', 'confirmed')
                    ORDER BY a.appointment_date, a.appointment_time
                ''', (start_date, end_date))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting upcoming appointments: {e}")
            return []
