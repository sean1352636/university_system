"""
Dentist/Dental Clinic CLI for University Management System

Provides comprehensive dental services including appointments, treatments,
patient records, and billing with finance and email integration.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# Import centralized database and authentication
from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection, transaction
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.domains.health.application.health import (
    sealed_fields as _sealed,
)

# Import dentist core services
try:
    from education_system.systems.university.domains.health.domain.health.dentist.services.dentist_core import (
        init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS,
        generate_appointment_ref, generate_patient_id, generate_reference
    )
    DENTIST_CORE_AVAILABLE = True
except ImportError:
    DENTIST_CORE_AVAILABLE = False
    TREATMENT_TYPES = {
        'checkup': {'name': 'Routine Check-up', 'duration': 30, 'fee': 25.00},
        'cleaning': {'name': 'Professional Cleaning', 'duration': 45, 'fee': 45.00},
        'filling': {'name': 'Dental Filling', 'duration': 60, 'fee': 80.00},
        'extraction': {'name': 'Tooth Extraction', 'duration': 45, 'fee': 100.00},
        'root_canal': {'name': 'Root Canal', 'duration': 90, 'fee': 350.00},
        'whitening': {'name': 'Teeth Whitening', 'duration': 60, 'fee': 150.00},
        'xray': {'name': 'Dental X-Ray', 'duration': 15, 'fee': 35.00},
        'emergency': {'name': 'Emergency Treatment', 'duration': 60, 'fee': 120.00},
    }
    DENTIST_STAFF = []          # real staff only (dentist_core.dentist_staff)
    APPOINTMENT_SLOTS = ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
                         '13:00', '13:30', '14:00', '14:30', '15:00', '15:30']

    def generate_appointment_ref():
        return f"DEN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    def generate_patient_id():
        return f"PAT-{uuid.uuid4().hex[:8].upper()}"

    def generate_reference():
        return f"REF-{uuid.uuid4().hex[:12].upper()}"

    def init_dentist_db():
        """Fallback: the same one health schema dentist_core uses."""
        from education_system.systems.university.domains.health.infrastructure.health import (
            health_schema,
        )
        try:
            health_schema.ensure()
            return True
        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

logger = logging.getLogger(__name__)

# Import email service
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

# Import activity logger
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None


# ---------------------------------------------------------------------------
# Notifying the patient
# ---------------------------------------------------------------------------
# The clinic's JSON templates already existed under
# assets/templates/email/finance_commerce/commerce/dentist/ but only the
# booking flow sent anything, and it built its body inline instead of using
# them — so cancelling, rescheduling and completing a treatment told the
# patient nothing at all. Everything now renders a template and goes through
# the university email system.

_DENTIST_TEMPLATE_DIR = "finance_commerce/commerce/dentist"
DENTIST_CONFIRMATION_TEMPLATE = f"{_DENTIST_TEMPLATE_DIR}/appointment_confirmation"
DENTIST_CANCELLED_TEMPLATE = f"{_DENTIST_TEMPLATE_DIR}/appointment_cancelled"
DENTIST_RESCHEDULED_TEMPLATE = f"{_DENTIST_TEMPLATE_DIR}/appointment_rescheduled"
DENTIST_REMINDER_TEMPLATE = f"{_DENTIST_TEMPLATE_DIR}/appointment_reminder"
DENTIST_TREATMENT_TEMPLATE = f"{_DENTIST_TEMPLATE_DIR}/treatment_summary"


def send_dentist_email(template_name, recipient_email, template_vars):
    """Render a dental template and hand it to the university email system.

    Best-effort: no address, an unavailable email service or a delivery
    failure is reported as False. The appointment change has already been
    committed by the time we notify, so failing here must not undo it.
    """
    address = (recipient_email or '').strip()
    if not address:
        return False
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email as _send,
        )
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
    except ImportError:
        return False
    try:
        subject, body = render_template(template_name, template_vars)
        if subject is None or body is None:
            return False
        _send(recipient_email=address, subject=subject, body=body)
        return True
    except Exception as exc:
        logger.warning("Dental email '%s' to %s failed: %s", template_name, address, exc)
        return False


def _report_email(sent, what):
    """Consistent one-line outcome for the operator."""
    if sent:
        print(f"📧 {what} emailed to the patient.")
    else:
        print(f"⚠️  {what} could not be emailed.")


def _appointment_contact(appointment_ref):
    """(patient_name, email, row) for an appointment, or (None, None, None)."""
    try:
        with get_connection() as conn:
            # COALESCE onto the patient record: patient_name is a
            # denormalised copy that older rows may not carry.
            row = conn.execute('''
                SELECT a.appointment_ref,
                       COALESCE(a.patient_name, p.user_name, 'Patient'),
                       a.appointment_date, a.appointment_time, a.treatment_type,
                       a.dentist_name, p.user_email, a.patient_id
                FROM dentist_appointments a
                LEFT JOIN dentist_patients p ON a.patient_id = p.patient_id
                WHERE a.appointment_ref = ?
            ''', (appointment_ref,)).fetchone()
    except Exception as exc:
        logger.warning("Could not read appointment %s: %s", appointment_ref, exc)
        return None, None, None
    if not row:
        return None, None, None
    return row[1], row[6], row


def ensure_dentist_columns():
    """Kept for its callers. The columns older databases lacked
    (``dentist_appointments.patient_name`` / ``fee`` / ``duration_minutes`` /
    ``reminder_sent``, ``dentist_treatments.procedure_notes``) are added by
    the health schema (``infrastructure/health/health_schema``), which
    :func:`init_dentist_db` has already applied. Returns 0."""
    return 0


#: The signed-in auth handed to :func:`dentist_menu` (the health portal and
#: the main menu pass theirs); the shared context is only the fallback.
_SESSION_AUTH = None


def get_current_user():
    """Get current authenticated user"""
    auth = _SESSION_AUTH or get_auth()
    if auth and hasattr(auth, 'current_user') and auth.current_user:
        return auth.current_user
    return None


def print_header(title: str):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def view_patient_profile():
    """View or create patient profile"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("MY PATIENT PROFILE")

    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT patient_number, user_name, user_email, user_phone,
                       medical_history, allergies, last_visit
                FROM dentist_patients
                WHERE user_id = ?
            ''', (user_id,))

            patient = cursor.fetchone()

            if not patient:
                print("\n📋 No patient profile found")
                print("\nWould you like to create a patient profile?")
                choice = input("(yes/no): ").strip().lower()
                if choice == 'yes':
                    create_patient_profile()
            else:
                pat_num, name, email, phone, med_hist, allergies, last_visit = patient
                med_hist, allergies = _sealed.reveal(med_hist), _sealed.reveal(allergies)

                print(f"\nPatient Number: {pat_num}")
                print(f"Name: {name}")
                print(f"Email: {email or 'N/A'}")
                print(f"Phone: {phone or 'N/A'}")
                print(f"Medical History: {med_hist or 'None recorded'}")
                print(f"Allergies: {allergies or 'None recorded'}")
                print(f"Last Visit: {last_visit or 'No visits yet'}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def create_patient_profile():
    """Create a new patient profile"""
    user = get_current_user()
    if not user:
        return

    print_header("CREATE PATIENT PROFILE")

    user_id = str(user.get('id') or user.get('username'))
    user_name = user.get('username', 'Unknown')
    user_email = user.get('email', '')

    phone = input("\nPhone number: ").strip()
    medical_history = input("Medical history (optional): ").strip()
    allergies = input("Allergies (optional): ").strip()

    try:
        patient_number = generate_patient_id()

        with transaction() as conn:
            conn.execute('''
                INSERT INTO dentist_patients (
                    patient_number, user_id, user_name, user_email, user_phone,
                    medical_history, allergies
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (patient_number, user_id, user_name, user_email or None, phone or None,
                  _sealed.seal_value('dentist_patients', 'medical_history', medical_history or None),
                  _sealed.seal_value('dentist_patients', 'allergies', allergies or None)))

        print("\n✅ Patient profile created successfully!")
        print(f"Patient Number: {patient_number}")

        log_activity('create', 'dentist_patient', patient_id=patient_number)

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def book_appointment():
    """Book a dental appointment"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("BOOK APPOINTMENT")

    user_id = str(user.get('id') or user.get('username'))

    # Check if patient profile exists
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT patient_id, patient_number, user_name
                FROM dentist_patients
                WHERE user_id = ?
            ''', (user_id,))

            patient = cursor.fetchone()

            if not patient:
                print("\n❌ Patient profile required. Please create one first.")
                choice = input("Create profile now? (yes/no): ").strip().lower()
                if choice == 'yes':
                    create_patient_profile()
                input("Press Enter to continue...")
                return

            patient_id, patient_number, patient_name = patient

        # Select treatment type
        print("\nAvailable Treatments:\n")
        treatments_list = []
        for i, (key, details) in enumerate(TREATMENT_TYPES.items(), 1):
            treatments_list.append(key)
            print(f"{i}. {details['name']:<30} £{details['fee']:.2f}  ({details['duration']} min)")

        treatment_choice = input("\nSelect treatment: ").strip()
        try:
            treatment_index = int(treatment_choice) - 1
            if 0 <= treatment_index < len(treatments_list):
                treatment_type = treatments_list[treatment_index]
                treatment_details = TREATMENT_TYPES[treatment_type]
            else:
                print("❌ Invalid selection")
                input("Press Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid input")
            input("Press Enter to continue...")
            return

        # Select dentist (staff holding the dentist role)
        if not DENTIST_STAFF:
            print("\nNo dentists are set up yet: a dentist is a staff account with the 'dentist' role. Ask an administrator to add one.")
            input("Press Enter to continue...")
            return
        print("\nAvailable Dentists:\n")
        for i, dentist in enumerate(DENTIST_STAFF, 1):
            print(f"{i}. {dentist['name']} - {dentist['specialization']}")

        dentist_choice = input("\nSelect dentist: ").strip()
        try:
            dentist_index = int(dentist_choice) - 1
            if 0 <= dentist_index < len(DENTIST_STAFF):
                dentist = DENTIST_STAFF[dentist_index]
            else:
                print("❌ Invalid selection")
                input("Press Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid input")
            input("Press Enter to continue...")
            return

        # Select date and time
        appointment_date = input("\nAppointment date (YYYY-MM-DD): ").strip()

        print("\nAvailable Time Slots:")
        for i, slot in enumerate(APPOINTMENT_SLOTS, 1):
            print(f"{i}. {slot}")

        slot_choice = input("\nSelect time slot: ").strip()
        try:
            slot_index = int(slot_choice) - 1
            if 0 <= slot_index < len(APPOINTMENT_SLOTS):
                appointment_time = APPOINTMENT_SLOTS[slot_index]
            else:
                print("❌ Invalid selection")
                input("Press Enter to continue...")
                return
        except ValueError:
            print("❌ Invalid input")
            input("Press Enter to continue...")
            return

        # Confirm appointment
        print("\n━━━ Appointment Summary ━━━")
        print(f"Patient: {patient_name} ({patient_number})")
        print(f"Treatment: {treatment_details['name']}")
        print(f"Dentist: {dentist['name']}")
        print(f"Date: {appointment_date}")
        print(f"Time: {appointment_time}")
        print(f"Duration: {treatment_details['duration']} minutes")
        print(f"Fee: £{treatment_details['fee']:.2f}")

        confirm = input("\nConfirm appointment? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Appointment cancelled")
            input("Press Enter to continue...")
            return

        appointment_ref = generate_appointment_ref()

        with transaction() as conn:
            conn.execute('''
                INSERT INTO dentist_appointments (
                    appointment_ref, patient_id, patient_name, dentist_id, dentist_name,
                    appointment_date, appointment_time, treatment_type, duration_minutes, fee, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')
            ''', (appointment_ref, patient_id, patient_name, dentist['id'], dentist['name'],
                  appointment_date, appointment_time, treatment_type,
                  treatment_details['duration'], treatment_details['fee']))

        print("\n✅ Appointment booked successfully!")
        print(f"Reference: {appointment_ref}")

        log_activity('create', 'dentist_appointment', appointment_ref=appointment_ref,
                     details={'treatment': treatment_details['name'], 'date': appointment_date})

        # Confirmation email. This used to build its body inline while a
        # commerce/dentist/appointment_confirmation template sat unused, so
        # the clinic's wording lived in two places and only one was
        # maintained.
        _report_email(send_dentist_email(
            DENTIST_CONFIRMATION_TEMPLATE, user.get('email', ''), {
                'patient_name': patient_name,
                'appointment_ref': appointment_ref,
                'appointment_date': appointment_date,
                'appointment_time': appointment_time,
                'treatment_type': treatment_details['name'],
                'dentist_name': dentist['name'],
                'amount_paid': f"{treatment_details['fee']:.2f}",
                'payment_method': 'Due at the appointment',
                'transaction_ref': appointment_ref,
            }), "Confirmation")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_my_appointments():
    """View current user's appointments"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("MY APPOINTMENTS")

    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            # Get patient ID
            cursor = conn.execute('SELECT patient_id FROM dentist_patients WHERE user_id = ?', (user_id,))
            patient = cursor.fetchone()

            if not patient:
                print("\n❌ No patient profile found")
                input("Press Enter to continue...")
                return

            patient_id = patient[0]

            # Get appointments
            cursor = conn.execute('''
                SELECT appointment_ref, dentist_name, appointment_date, appointment_time,
                       treatment_type, fee, status
                FROM dentist_appointments
                WHERE patient_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
            ''', (patient_id,))

            appointments = cursor.fetchall()

            if not appointments:
                print("\n📅 No appointments found")
            else:
                print(f"\nYou have {len(appointments)} appointment(s):\n")
                print("Ref            Dentist              Date          Time    Treatment         Fee      Status")
                print("-" * 95)

                for appt in appointments:
                    ref, dentist, date, time, treatment, fee, status = appt
                    treatment_name = TREATMENT_TYPES.get(treatment, {}).get('name', treatment)[:15]
                    print(f"{ref:<14} {dentist:<20} {date:<13} {time:<7} {treatment_name:<17} £{fee:6.2f}  {status}")

                # Option to view details
                ref = input("\nEnter appointment reference for details (or Enter to return): ").strip()
                if ref:
                    view_appointment_details(ref)

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_appointment_details(appointment_ref: str):
    """Show detailed appointment information"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT appointment_ref, patient_name, dentist_name, appointment_date,
                       appointment_time, treatment_type, duration_minutes, fee, status, notes
                FROM dentist_appointments
                WHERE appointment_ref = ?
            ''', (appointment_ref,))

            appt = cursor.fetchone()

            if appt:
                ref, patient, dentist, date, time, treatment, duration, fee, status, notes = appt
                treatment_name = TREATMENT_TYPES.get(treatment, {}).get('name', treatment)

                print(f"\n━━━ Appointment {ref} ━━━")
                print(f"Patient: {patient}")
                print(f"Dentist: {dentist}")
                print(f"Date: {date}")
                print(f"Time: {time}")
                print(f"Treatment: {treatment_name}")
                print(f"Duration: {duration} minutes")
                print(f"Fee: £{fee:.2f}")
                print(f"Status: {status.upper()}")
                if notes:
                    print(f"Notes: {notes}")

                if status == 'scheduled':
                    print("\nOptions:")
                    print("1. Cancel appointment")
                    choice = input("\nEnter choice (or Enter to return): ").strip()
                    if choice == "1":
                        cancel_appointment(ref)

    except Exception as e:
        print(f"Error: {e}")


def cancel_appointment(appointment_ref: str):
    """Cancel an appointment"""
    confirm = input(f"\nCancel appointment {appointment_ref}? (yes/no): ").strip().lower()
    if confirm == 'yes':
        # Capture the details before the status changes — the email describes
        # the appointment that has just been cancelled.
        name, email, row = _appointment_contact(appointment_ref)
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE dentist_appointments
                    SET status = 'cancelled'
                    WHERE appointment_ref = ?
                ''', (appointment_ref,))

            print(f"✅ Appointment {appointment_ref} cancelled")
            log_activity('update', 'dentist_appointment', appointment_ref=appointment_ref,
                         details={'status': 'cancelled'})

            # Cancelling silently was the worst of the gaps here: the patient
            # would have turned up.
            if row:
                _report_email(send_dentist_email(
                    DENTIST_CANCELLED_TEMPLATE, email, {
                        'patient_name': name or 'Patient',
                        'appointment_ref': row[0],
                        'appointment_date': row[2],
                        'appointment_time': row[3],
                        'treatment_type': row[4],
                    }), "Cancellation notice")

        except Exception as e:
            print(f"❌ Error: {e}")


def reschedule_appointment(appointment_ref: str = None):
    """Move an appointment to a new date/time and tell the patient.

    A commerce/dentist/appointment_rescheduled template already existed with
    nothing calling it — the clinic could only cancel and rebook, which loses
    the reference and sends the patient two confusing emails instead of one.
    """
    if not appointment_ref:
        appointment_ref = input("\nAppointment reference to reschedule: ").strip()
    if not appointment_ref:
        return

    name, email, row = _appointment_contact(appointment_ref)
    if not row:
        print("❌ Appointment not found.")
        input("\nPress Enter to continue...")
        return

    old_date, old_time = row[2], row[3]
    print(f"\nCurrent: {old_date} at {old_time} with {row[5]}")

    new_date = None
    while True:
        raw = input("New date (YYYY-MM-DD, blank to cancel): ").strip()
        if not raw:
            print("Reschedule cancelled. Nothing has been changed.")
            return
        try:
            if datetime.strptime(raw, '%Y-%m-%d').date() < datetime.now().date():
                print("That date is in the past. Please choose a future date.")
                continue
            new_date = raw
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    new_time = None
    while True:
        raw = input("New time (HH:MM, blank to cancel): ").strip()
        if not raw:
            print("Reschedule cancelled. Nothing has been changed.")
            return
        try:
            datetime.strptime(raw, '%H:%M')
            new_time = raw
            break
        except ValueError:
            print("Invalid time format. Please use HH:MM.")

    if new_date == old_date and new_time == old_time:
        print("That is the same slot — nothing has been changed.")
        input("\nPress Enter to continue...")
        return

    print(f"\nMoving {appointment_ref}:")
    print(f"  From: {old_date} at {old_time}")
    print(f"  To:   {new_date} at {new_time}")
    if input("\nConfirm? (yes/no): ").strip().lower() != 'yes':
        print("Reschedule cancelled. Nothing has been changed.")
        return

    try:
        with transaction() as conn:
            conn.execute('''
                UPDATE dentist_appointments
                SET appointment_date = ?, appointment_time = ?, status = 'scheduled'
                WHERE appointment_ref = ?
            ''', (new_date, new_time, appointment_ref))

        print(f"✅ Appointment {appointment_ref} moved to {new_date} at {new_time}")
        log_activity('update', 'dentist_appointment', appointment_ref=appointment_ref,
                     details={'rescheduled_from': f"{old_date} {old_time}",
                              'rescheduled_to': f"{new_date} {new_time}"})

        _report_email(send_dentist_email(
            DENTIST_RESCHEDULED_TEMPLATE, email, {
                'patient_name': name or 'Patient',
                'old_date': old_date, 'old_time': old_time,
                'new_date': new_date, 'new_time': new_time,
                'dentist_name': row[5] or 'your dentist',
            }), "Reschedule notice")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def send_appointment_reminders():
    """Email everyone with an appointment in the next few days (staff).

    A commerce/dentist/appointment_reminder template existed with no caller,
    so the clinic had no way to remind anyone.
    """
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("❌ Staff access required")
        input("\nPress Enter to continue...")
        return

    raw = input("\nRemind patients with appointments in the next how many days? [2]: ").strip()
    try:
        days = int(raw) if raw else 2
        if days < 0:
            raise ValueError
    except ValueError:
        print("Not a valid number of days — using 2.")
        days = 2

    today = datetime.now().strftime('%Y-%m-%d')
    horizon = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT a.appointment_ref,
                       COALESCE(a.patient_name, p.user_name, 'Patient'),
                       a.appointment_date, a.appointment_time, a.dentist_name,
                       p.user_email
                FROM dentist_appointments a
                LEFT JOIN dentist_patients p ON a.patient_id = p.patient_id
                WHERE a.status = 'scheduled'
                  AND a.appointment_date BETWEEN ? AND ?
                ORDER BY a.appointment_date, a.appointment_time
            ''', (today, horizon)).fetchall()
    except Exception as e:
        print(f"❌ Error: {e}")
        input("\nPress Enter to continue...")
        return

    if not rows:
        print(f"\nNo scheduled appointments between {today} and {horizon}.")
        input("\nPress Enter to continue...")
        return

    print(f"\n===== Appointment Reminders ({len(rows)}) =====")
    without_email = 0
    for ref, patient, date, time_, dentist, email in rows:
        print(f"• {patient} — {date} at {time_} with {dentist} ({ref})")
        if not email:
            without_email += 1
            print("  (no email address on file — cannot be reminded)")

    reachable = len(rows) - without_email
    if without_email:
        print(f"\n{without_email} of {len(rows)} have no email address on file.")

    if input(f"\nEmail reminders to {reachable} patient(s)? (y/n): ").strip().lower() != 'y':
        print("Reminder sending cancelled. Nothing has been sent.")
        input("\nPress Enter to continue...")
        return

    sent = failed = 0
    for ref, patient, date, time_, dentist, email in rows:
        if not email:
            continue
        if send_dentist_email(DENTIST_REMINDER_TEMPLATE, email, {
                'patient_name': patient or 'Patient',
                'appointment_date': date,
                'appointment_time': time_,
                'dentist_name': dentist or 'your dentist'}):
            sent += 1
        else:
            failed += 1

    summary = f"\nReminders: {sent} sent"
    if failed:
        summary += f", {failed} failed"
    if without_email:
        summary += f", {without_email} with no address on file"
    print(summary + ".")
    log_activity('update', 'dentist_appointment',
                 details={'reminders_sent': sent, 'reminders_failed': failed})

    input("\nPress Enter to continue...")


def view_treatment_history():
    """View treatment history"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("TREATMENT HISTORY")

    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            # Get patient ID
            cursor = conn.execute('SELECT patient_id FROM dentist_patients WHERE user_id = ?', (user_id,))
            patient = cursor.fetchone()

            if not patient:
                print("\n❌ No patient profile found")
                input("Press Enter to continue...")
                return

            patient_id = patient[0]

            # Get treatments
            cursor = conn.execute('''
                SELECT treatment_id, treatment_type, treatment_date, dentist_id,
                       diagnosis, fee, payment_status
                FROM dentist_treatments
                WHERE patient_id = ?
                ORDER BY treatment_date DESC
            ''', (patient_id,))

            treatments = cursor.fetchall()

            if not treatments:
                print("\n📋 No treatment history found")
            else:
                print(f"\nTotal treatments: {len(treatments)}\n")
                print("ID     Date          Treatment                  Fee      Payment")
                print("-" * 70)

                for treatment in treatments:
                    tid, ttype, date, dentist_id, diagnosis, fee, payment = treatment
                    treatment_name = TREATMENT_TYPES.get(ttype, {}).get('name', ttype)[:25]
                    print(f"{tid:<6} {date:<13} {treatment_name:<26} £{fee:6.2f}  {payment}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_all_appointments():
    """View all appointments (staff)"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Staff access required")
        input("Press Enter to continue...")
        return

    print_header("ALL APPOINTMENTS")

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT appointment_ref, patient_name, dentist_name, appointment_date,
                       appointment_time, treatment_type, status
                FROM dentist_appointments
                ORDER BY appointment_date DESC, appointment_time DESC
                LIMIT 50
            ''')

            appointments = cursor.fetchall()

            if not appointments:
                print("\n📅 No appointments found")
            else:
                print(f"\nShowing last {len(appointments)} appointments:\n")
                print("Ref            Patient              Dentist              Date          Time    Treatment      Status")
                print("-" * 105)

                for appt in appointments:
                    ref, patient, dentist, date, time, treatment, status = appt
                    treatment_abbr = TREATMENT_TYPES.get(treatment, {}).get('name', treatment)[:12]
                    print(f"{ref:<14} {patient:<20} {dentist:<20} {date:<13} {time:<7} {treatment_abbr:<14} {status}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def complete_appointment():
    """Mark appointment as completed and record treatment (staff)"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Staff access required")
        input("Press Enter to continue...")
        return

    print_header("COMPLETE APPOINTMENT")

    appointment_ref = input("\nEnter appointment reference: ").strip()
    if not appointment_ref:
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT appointment_id, patient_id, patient_name, dentist_id, treatment_type, fee, status
                FROM dentist_appointments
                WHERE appointment_ref = ?
            ''', (appointment_ref,))

            appt = cursor.fetchone()

            if not appt:
                print("❌ Appointment not found")
                input("Press Enter to continue...")
                return

            appt_id, patient_id, patient_name, dentist_id, treatment_type, fee, status = appt

            if status == 'completed':
                print("❌ Appointment already completed")
                input("Press Enter to continue...")
                return

            diagnosis = input("Diagnosis/notes: ").strip()
            procedure_notes = input("Procedure notes (optional): ").strip()

            payment_status = input("Payment status (pending/paid): ").strip().lower()
            if payment_status not in ['pending', 'paid']:
                payment_status = 'pending'

            with transaction() as conn:
                # Update appointment status
                conn.execute('''
                    UPDATE dentist_appointments
                    SET status = 'completed'
                    WHERE appointment_id = ?
                ''', (appt_id,))

                # Record treatment
                conn.execute('''
                    INSERT INTO dentist_treatments (
                        appointment_id, patient_id, dentist_id, treatment_type, treatment_date,
                        diagnosis, procedure_notes, fee, payment_status
                    )
                    VALUES (?, ?, ?, ?, DATE('now'), ?, ?, ?, ?)
                ''', (appt_id, patient_id, dentist_id, treatment_type, diagnosis,
                      _sealed.seal_value('dentist_treatments', 'procedure_notes',
                                         procedure_notes or None), fee, payment_status))

                # Update patient last visit
                conn.execute('''
                    UPDATE dentist_patients
                    SET last_visit = DATE('now')
                    WHERE patient_id = ?
                ''', (patient_id,))

            print(f"\n✅ Appointment {appointment_ref} completed")
            print(f"Treatment recorded for patient: {patient_name}")

            log_activity('update', 'dentist_appointment', appointment_ref=appointment_ref,
                         details={'status': 'completed'})

            # Send the patient what was found, what was done, what it cost and
            # what to watch for. Nothing was sent on completion before, so a
            # patient left with no written record of their own treatment.
            _name, patient_email, row = _appointment_contact(appointment_ref)
            payment_note = ("There is nothing left to pay."
                            if str(payment_status).lower() in ('paid', 'complete', 'completed')
                            else "Please settle the balance through the Finance Portal "
                                 "or at reception.")
            _report_email(send_dentist_email(
                DENTIST_TREATMENT_TEMPLATE, patient_email, {
                    'patient_name': patient_name,
                    'appointment_ref': appointment_ref,
                    'treatment_date': datetime.now().strftime('%Y-%m-%d'),
                    'treatment_type': treatment_type,
                    'dentist_name': row[5] if row else 'your dentist',
                    'diagnosis': diagnosis or 'No diagnosis was recorded.',
                    'procedure_notes': procedure_notes or 'No procedure notes were recorded.',
                    'fee': f"{float(fee or 0):.2f}",
                    'payment_status': payment_status,
                    'payment_note': payment_note,
                }), "Treatment summary")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_clinic_statistics():
    """View clinic statistics (staff)"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Staff access required")
        input("Press Enter to continue...")
        return

    print_header("CLINIC STATISTICS")

    try:
        with get_connection() as conn:
            # Total patients
            cursor = conn.execute('SELECT COUNT(*) FROM dentist_patients')
            total_patients = cursor.fetchone()[0]

            # Total appointments
            cursor = conn.execute('SELECT COUNT(*) FROM dentist_appointments')
            total_appts = cursor.fetchone()[0]

            # Appointments by status
            cursor = conn.execute('''
                SELECT status, COUNT(*)
                FROM dentist_appointments
                GROUP BY status
            ''')
            by_status = cursor.fetchall()

            # Total revenue
            cursor = conn.execute('''
                SELECT SUM(fee)
                FROM dentist_treatments
                WHERE payment_status = 'paid'
            ''')
            total_revenue = cursor.fetchone()[0] or 0.00

            # Most common treatments
            cursor = conn.execute('''
                SELECT treatment_type, COUNT(*) as count
                FROM dentist_treatments
                GROUP BY treatment_type
                ORDER BY count DESC
                LIMIT 5
            ''')
            common_treatments = cursor.fetchall()

            print(f"\n📊 Total Patients: {total_patients}")
            print(f"📅 Total Appointments: {total_appts}")
            print(f"💰 Total Revenue (Paid): £{total_revenue:.2f}")

            print("\nAppointments by Status:")
            for status, count in by_status:
                print(f"  {status}: {count}")

            if common_treatments:
                print("\n🏆 Most Common Treatments:")
                for treatment, count in common_treatments:
                    treatment_name = TREATMENT_TYPES.get(treatment, {}).get('name', treatment)
                    print(f"  {treatment_name}: {count} times")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def dentist_menu(auth=None):
    """Main dentist menu, for the signed-in ``auth`` (the shared session
    when none is passed)."""
    global _SESSION_AUTH
    previous, _SESSION_AUTH = _SESSION_AUTH, auth or _SESSION_AUTH
    try:
        return _dentist_menu()
    finally:
        _SESSION_AUTH = previous


def _dentist_menu():
    # Initialize database
    # One health schema (tables and the columns older databases lacked).
    init_dentist_db()

    user = get_current_user()
    is_staff = user and user.get('role') in ['admin', 'staff']

    while True:
        print_header("UNIVERSITY DENTAL CLINIC")

        if user:
            print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

        # Reschedule and Cancel were previously unreachable from here —
        # cancel_appointment existed but only opened from inside the
        # appointment-details screen, and reschedule did not exist at all.
        print("\n🦷 PATIENT SERVICES:")
        print("1. View My Patient Profile")
        print("2. Book Appointment")
        print("3. View My Appointments")
        print("4. Reschedule an Appointment")
        print("5. Cancel an Appointment")
        print("6. View Treatment History")

        if is_staff:
            print("\n🔧 STAFF OPTIONS:")
            print("7. View All Appointments")
            print("8. Complete Appointment")
            print("9. Send Appointment Reminders")
            print("10. Clinic Statistics")

        print("\n0. Return to Main Menu")

        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            view_patient_profile()
        elif choice == "2":
            book_appointment()
        elif choice == "3":
            view_my_appointments()
        elif choice == "4":
            reschedule_appointment()
        elif choice == "5":
            ref = input("\nAppointment reference to cancel: ").strip()
            if ref:
                cancel_appointment(ref)
                input("\nPress Enter to continue...")
        elif choice == "6":
            view_treatment_history()
        elif choice == "7" and is_staff:
            view_all_appointments()
        elif choice == "8" and is_staff:
            complete_appointment()
        elif choice == "9" and is_staff:
            send_appointment_reminders()
        elif choice == "10" and is_staff:
            view_clinic_statistics()
        elif choice == "0":
            break
        else:
            print("Invalid choice")
            input("Press Enter to continue...")


if __name__ == "__main__":
    dentist_menu()
