"""
Dentist/Dental Clinic CLI for University Management System

Provides comprehensive dental services including appointments, treatments,
patient records, and billing with finance and email integration.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# Import centralized database and authentication
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.shared_context import get_auth

# Import dentist core services
try:
    from education_system.university_system.modules.domain.health.dentist.services.dentist_core import (
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
    DENTIST_STAFF = [
        {'id': 'DEN001', 'name': 'Dr. Sarah Mitchell', 'specialization': 'General Dentistry'},
        {'id': 'DEN002', 'name': 'Dr. James Wilson', 'specialization': 'Orthodontics'},
        {'id': 'DEN003', 'name': 'Dr. Emily Chen', 'specialization': 'Periodontics'},
        {'id': 'DEN004', 'name': 'Dr. Michael Brown', 'specialization': 'Endodontics'}
    ]
    APPOINTMENT_SLOTS = ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
                         '13:00', '13:30', '14:00', '14:30', '15:00', '15:30']

    def generate_appointment_ref():
        return f"DEN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    def generate_patient_id():
        return f"PAT-{uuid.uuid4().hex[:8].upper()}"

    def generate_reference():
        return f"REF-{uuid.uuid4().hex[:12].upper()}"

    def init_dentist_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dentist_patients (
                        patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        patient_number TEXT UNIQUE NOT NULL,
                        user_id TEXT NOT NULL,
                        user_name TEXT NOT NULL,
                        user_email TEXT,
                        user_phone TEXT,
                        medical_history TEXT,
                        allergies TEXT,
                        last_visit DATE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dentist_appointments (
                        appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        appointment_ref TEXT UNIQUE NOT NULL,
                        patient_id INTEGER NOT NULL,
                        patient_name TEXT,
                        dentist_id TEXT,
                        dentist_name TEXT,
                        appointment_date DATE NOT NULL,
                        appointment_time TEXT NOT NULL,
                        treatment_type TEXT NOT NULL,
                        duration_minutes INTEGER,
                        fee REAL,
                        status TEXT DEFAULT 'scheduled',
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dentist_treatments (
                        treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        appointment_id INTEGER NOT NULL,
                        patient_id INTEGER NOT NULL,
                        dentist_id TEXT,
                        treatment_type TEXT NOT NULL,
                        treatment_date DATE NOT NULL,
                        diagnosis TEXT,
                        procedure_notes TEXT,
                        fee REAL,
                        payment_status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (appointment_id) REFERENCES dentist_appointments(appointment_id),
                        FOREIGN KEY (patient_id) REFERENCES dentist_patients(patient_id)
                    )
                ''')

            return True
        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

# Import activity logger
try:
    from education_system.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None


def get_current_user():
    """Get current authenticated user"""
    auth = get_auth()
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
                  medical_history or None, allergies or None))

        print(f"\n✅ Patient profile created successfully!")
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

        # Select dentist
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
        print(f"\n━━━ Appointment Summary ━━━")
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

        print(f"\n✅ Appointment booked successfully!")
        print(f"Reference: {appointment_ref}")

        log_activity('create', 'dentist_appointment', appointment_ref=appointment_ref,
                     details={'treatment': treatment_details['name'], 'date': appointment_date})

        # Send confirmation email
        user_email = user.get('email', '')
        if user_email and EMAIL_AVAILABLE:
            subject = f"Dental Appointment Confirmed - {appointment_ref}"
            body = f"""Dear {patient_name},

Your dental appointment has been confirmed.

Appointment Reference: {appointment_ref}
Date: {appointment_date}
Time: {appointment_time}
Treatment: {treatment_details['name']}
Dentist: {dentist['name']}
Duration: {treatment_details['duration']} minutes
Fee: £{treatment_details['fee']:.2f}

Please arrive 10 minutes early for check-in.

University Dental Clinic"""

            try:
                send_email(user_email, subject, body)
                print("📧 Confirmation email sent")
            except Exception as e:
                print(f"⚠️  Email notification failed: {e}")

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

        except Exception as e:
            print(f"❌ Error: {e}")


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
                      procedure_notes or None, fee, payment_status))

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


def dentist_menu():
    """Main dentist menu"""
    # Initialize database
    init_dentist_db()

    user = get_current_user()
    is_staff = user and user.get('role') in ['admin', 'staff']

    while True:
        print_header("UNIVERSITY DENTAL CLINIC")

        if user:
            print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

        print("\n🦷 PATIENT SERVICES:")
        print("1. View My Patient Profile")
        print("2. Book Appointment")
        print("3. View My Appointments")
        print("4. View Treatment History")

        if is_staff:
            print("\n🔧 STAFF OPTIONS:")
            print("5. View All Appointments")
            print("6. Complete Appointment")
            print("7. Clinic Statistics")

        print("\n0. Return to Main Menu")

        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            view_patient_profile()
        elif choice == "2":
            book_appointment()
        elif choice == "3":
            view_my_appointments()
        elif choice == "4":
            view_treatment_history()
        elif choice == "5" and is_staff:
            view_all_appointments()
        elif choice == "6" and is_staff:
            complete_appointment()
        elif choice == "7" and is_staff:
            view_clinic_statistics()
        elif choice == "0":
            break
        else:
            print("Invalid choice")
            input("Press Enter to continue...")


if __name__ == "__main__":
    dentist_menu()
