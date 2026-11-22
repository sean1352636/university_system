"""
Dentist/Dental Clinic Core Services

Provides comprehensive dental clinic management including
appointments, treatments, patient records, and billing with
email and finance integration.
"""

from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.sql_safety import validate_identifier, escape_like  # nosec B608
from education_system.systems.university.domains.health.domain.health.dentist.integrations.finance import notify_payment
# Medical history, allergies and treatment notes are sealed at rest
# (application/health/sealed_fields): sealed on write, revealed on read.
from education_system.systems.university.domains.health.application.health import (
    sealed_fields as _sealed,
)

logger = logging.getLogger(__name__)

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

# The clinic's dentists are real staff: users holding the ``dentist`` role
# (see :func:`dentist_staff`). The four fictional names that used to be
# hard-coded here were never people; with no dentist accounts the list is
# empty and the screens say so.
DENTIST_ROLES = ("dentist",)


def dentist_staff() -> list:
    """``[{'id', 'name', 'specialization'}]`` for every user with the
    dentist role (local profiles, plus the shared sign-in's role mapping)."""
    found = {}
    try:
        with get_connection() as conn:
            marks = ",".join("?" * len(DENTIST_ROLES))
            for uid, username, first, last in conn.execute(
                    f"SELECT id, username, first_name, last_name FROM users "  # nosec B608
                    f"WHERE LOWER(role) IN ({marks})", DENTIST_ROLES).fetchall():
                name = f"{first or ''} {last or ''}".strip() or username
                found[str(username)] = {'id': str(username), 'name': f"Dr. {name}"
                                        if not name.lower().startswith("dr") else name,
                                        'specialization': 'General Dentistry'}
    except Exception:
        logger.debug("dentist staff not read from users", exc_info=True)
    try:
        from education_system.systems.university.domains.health.infrastructure.health import (
            shared_signin,
        )
        for role in DENTIST_ROLES:
            for username, display in shared_signin.users_with_university_role(role):
                found.setdefault(username, {
                    'id': username, 'name': display or username,
                    'specialization': 'General Dentistry'})
    except Exception:
        logger.debug("dentist staff not read from the shared sign-in", exc_info=True)
    return sorted(found.values(), key=lambda d: d['name'])


class _DentistStaff(list):
    """``DENTIST_STAFF`` kept as a name callers import, now read live."""

    def _load(self):
        self[:] = dentist_staff()
        return self

    def __iter__(self):
        return iter(self._load()[:])

    def __len__(self):
        return len(dentist_staff())

    def __getitem__(self, index):
        return list.__getitem__(self._load(), index)

    def __bool__(self):
        return bool(dentist_staff())


DENTIST_STAFF = _DentistStaff()

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

def billing_student_id(login) -> str:
    """The student number Finance bills (``users.student_id``) for a clinic
    login (username or users.id). The clinic keys patients on the login, but
    student finance accounts and ``payments.student_id`` use the student
    number; a login with no student record (staff) is billed as itself."""
    if login in (None, ""):
        return login
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT student_id FROM users WHERE username = ? OR "
                               "CAST(id AS TEXT) = ? ORDER BY username = ? DESC LIMIT 1",
                               (str(login), str(login), str(login))).fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception:
        logger.debug("student number for %s not resolved", login, exc_info=True)
    return str(login)


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
    """The clinic's tables, once per database file — declared with the rest of
    the health schema (``infrastructure/health/health_schema``, migration
    ``a0d2f4b6c8e1``), which also adds the columns older databases lacked
    (``dentist_appointments.patient_name`` / ``fee``, ``procedure_notes`` …).
    Dentist transactions use the unified ``transactions`` table
    (``source_type = 'dentist'``)."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    try:
        health_schema.ensure()
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
                      _sealed.seal_value('dentist_patients', 'medical_history', medical_history),
                      _sealed.seal_value('dentist_patients', 'allergies', allergies)))

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
                    return _sealed.unseal_row(row, columns)
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
                return _sealed.unseal_rows(cursor.fetchall(), columns)
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
            updates = _sealed.seal_values('dentist_patients', updates)

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
                return _sealed.unseal_rows(cursor.fetchall(), columns)
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
                      fee, _sealed.seal_value('dentist_treatments', 'notes', notes),
                      1 if follow_up_required else 0, follow_up_date))

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
                return _sealed.unseal_rows(cursor.fetchall(), columns)
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

class PrescribingStopped(Exception):
    """A documented severe allergy blocks the prescription (``report`` has
    the details); only a clinician can override it, with a reason."""

    def __init__(self, report):
        super().__init__("Prescribing stopped:\n" + report.summary())
        self.report = report


class PrescriptionManager:
    """Manages dental prescriptions."""

    @staticmethod
    def _student_number(conn, patient_id):
        row = conn.execute("SELECT user_id FROM dentist_patients WHERE patient_id = ?",
                           (patient_id,)).fetchone()
        return billing_student_id(row[0]) if row else None

    @staticmethod
    def screen(patient_id: int, medication: str):
        """The prescribing safety screen (``application/health/prescribing``:
        every allergy on the health and dental records, duplicates against
        active prescriptions, interactions) for this patient. Returns a
        ``SafetyReport``."""
        from education_system.systems.university.domains.health.application.health import (
            prescribing,
        )
        with get_connection() as conn:
            return prescribing.check(conn, PrescriptionManager._student_number(conn, patient_id),
                                     medication)

    @staticmethod
    def create_prescription(patient_id: int, dentist_id: str, dentist_name: str,
                           medication: str, dosage: str, frequency: str,
                           duration: str, instructions: str = None,
                           treatment_id: int = None, *, override_reason: str = None,
                           who=None) -> Optional[Dict]:
        """Create a prescription, after the same safety screen as the health
        centre's prescribing. A hard stop (documented severe allergy) raises
        :class:`PrescribingStopped` unless ``who`` is a clinician giving an
        ``override_reason`` (recorded with the prescription). Warnings are for
        the screen to confirm (:meth:`screen`)."""
        from education_system.systems.university.domains.health.application.health import (
            prescribing,
        )
        try:
            prescribed_date = datetime.now().date().isoformat()

            with transaction() as conn:
                student_number = PrescriptionManager._student_number(conn, patient_id)
                safety = prescribing.check(conn, student_number, medication)
                if safety.hard_stops:
                    if not (who is not None and who.is_clinician and override_reason
                            and len(override_reason.strip()) >= 5):
                        raise PrescribingStopped(safety)
                conn.execute('''
                    INSERT INTO dentist_prescriptions
                    (patient_id, dentist_id, dentist_name, treatment_id,
                     medication, dosage, frequency, duration, instructions, prescribed_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (patient_id, dentist_id, dentist_name, treatment_id,
                      medication, dosage, frequency, duration, instructions, prescribed_date))

                prescription_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                if safety.hard_stops:
                    prescribing.record_override(conn, who, student_number, medication, safety,
                                                override_reason)

            return {'prescription_id': prescription_id}
        except PrescribingStopped:
            raise
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
                      treatment_id: int = None, processed_by: str = None,
                      description: str = None, notes: str = None) -> Optional[Dict]:
        """Record a payment transaction and post it to Finance.

        Writes the clinic's own ``transactions`` row, then the central
        ``payments`` row Finance reports on, in one transaction; the GL is
        posted afterwards via ``integrations.finance.notify_payment``. Every
        interface (CLI and GUI) takes money through this function, so this is
        the single place the clinic posts to Finance.

        ``description`` names what was paid for (e.g. "Appointment - Routine
        Check-up"); ``notes`` overrides the composed payments note verbatim.
        """
        try:
            reference = generate_reference()
            payment_notes = notes or (
                f"Dental: {description or transaction_type.replace('_', ' ').title()} "
                f"(Ref: {reference})"
            )

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

                # Central payments row for Finance (same payload the GUI used
                # to write inline, plus the clinic's source_type).
                cur = conn.execute('''
                    INSERT INTO payments
                    (student_id, amount, payment_method, payment_date, status, notes,
                     created_by, source_type, reference_type, reference_id, processed_by)
                    VALUES (?, ?, ?, date("now"), 'completed', ?, ?, 'dentist', 'treatment', ?, ?)
                ''', (billing_student_id(user_id) or None, amount, f'dentist_{payment_method}', payment_notes,
                      processed_by or user_id,
                      str(treatment_id) if treatment_id else None, processed_by))
                payment_id = cur.lastrowid

            # Auto-post to GL (never raises; failures are logged by the hook).
            try:
                notify_payment(payment_id, processed_by or user_id)
            except Exception as e:  # pragma: no cover - hook already swallows
                logger.warning("ledger hook failed for dentist payment %s: %s", payment_id, e)

            return {
                'transaction_id': transaction_id,
                'payment_id': payment_id,
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
