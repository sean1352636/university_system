"""
Health portal service module for student health management.
"""

import os
import sys
import logging
import csv
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from education_system.university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH
from education_system.university_system.modules.shared.constants import paths

# Add the domain health portal to path if not already
current_dir = os.path.dirname(os.path.abspath(__file__))
domain_health_dir = os.path.join(current_dir, '..', 'domain', 'health', 'portal')

if os.path.exists(domain_health_dir) and domain_health_dir not in sys.path:
    sys.path.insert(0, domain_health_dir)

# Setup logging
logger = logging.getLogger(__name__)

def display_health_portal_menu(auth):
    """Display the health portal menu."""
    if not auth.check_session():
        print("Please log in to access the health portal.")
        return

    try:
        # Try to import from the domain health portal
        from education_system.university_system.modules.domain.health.portal.health_portal_core import display_health_portal_menu
        display_health_portal_menu(auth)
    except ImportError as e:
        logger.warning(f"Could not import health portal core: {e}")
        # Fallback implementation
        display_basic_health_menu(auth)

def display_basic_health_menu(auth):
    """Basic health portal menu implementation."""
    while True:
        print("\n" + "="*100)
        print("                    HEALTH PORTAL SYSTEM")
        print("="*100)

        print("\nBASIC FEATURES:")
        print(f"{'1.  Health Records':<25} {'2.  Schedule Appointment':<25} {'3.  Medical History':<25} {'4.  Emergency Contacts':<25}")
        print(f"{'5.  Health Reports':<25} {'6.  Vaccination Records':<25}")

        print("\nADVANCED FEATURES:")
        print(f"{'7.  Data Export/Backup':<25} {'8.  Security & Audit':<25} {'9.  Backup Management':<25} {'10. Population Reports':<25}")

        print("\n0.  Return to Main Menu")
        print("="*100)

        choice = input("Enter your choice (0-10): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            view_health_records(auth)
        elif choice == '2':
            schedule_appointment(auth)
        elif choice == '3':
            view_medical_history(auth)
        elif choice == '4':
            manage_emergency_contacts(auth)
        elif choice == '5':
            generate_health_reports(auth)
        elif choice == '6':
            view_vaccination_records(auth)
        elif choice == '7':
            data_export_menu(auth)
        elif choice == '8':
            security_audit_menu(auth)
        elif choice == '9':
            backup_management_menu(auth)
        elif choice == '10':
            advanced_reports_menu(auth)
        else:
            print("Invalid choice. Please try again.")

def view_health_records(auth):
    """View student health records."""
    print("\n--- Health Records ---")

    try:
        # Get student ID from username
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found in database.")
            conn.close()
            return

        student_id = user_row['id']

        # Create health_records table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                blood_type TEXT,
                allergies TEXT,
                medications TEXT,
                conditions TEXT,
                insurance_provider TEXT,
                insurance_policy_number TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        """)
        conn.commit()

        # Query health records
        cursor.execute("""
            SELECT blood_type, allergies, medications, conditions,
                   insurance_provider, insurance_policy_number, last_updated
            FROM health_records
            WHERE student_id = ?
        """, (student_id,))

        record = cursor.fetchone()

        if record:
            print("\nYour Health Information:")
            print("=" * 50)

            if record['blood_type']:
                print(f"Blood Type: {record['blood_type']}")

            if record['allergies']:
                print(f"\nAllergies:\n  {record['allergies']}")

            if record['medications']:
                print(f"\nCurrent Medications:\n  {record['medications']}")

            if record['conditions']:
                print(f"\nMedical Conditions:\n  {record['conditions']}")

            if record['insurance_provider']:
                print(f"\nInsurance Information:")
                print(f"  Provider: {record['insurance_provider']}")
                if record['insurance_policy_number']:
                    print(f"  Policy Number: {record['insurance_policy_number']}")

            if record['last_updated']:
                print(f"\nLast Updated: {record['last_updated']}")

            print("\n" + "=" * 50)
        else:
            print("\nNo health records found in the system.")
            print("Please visit the health center to create your health profile.")

        # Show recent appointments
        cursor.execute("""
            SELECT appointment_type, appointment_date, appointment_time, status
            FROM health_appointments
            WHERE student_id = ?
            ORDER BY appointment_date DESC, appointment_time DESC
            LIMIT 5
        """, (student_id,))

        appointments = cursor.fetchall()
        if appointments:
            print("\nRecent Appointments:")
            for apt in appointments:
                print(f"  - {apt['appointment_type']}: {apt['appointment_date']} at {apt['appointment_time']} (Status: {apt['status']})")

        conn.close()

        print("\nNote: For detailed medical records or to update your health information,")
        print("please contact the health center or visit in person.")

    except Exception as e:
        logger.error(f"Error viewing health records: {e}")
        print(f"\nError accessing health records: {e}")
        print("Please contact the health center for assistance.")

def schedule_appointment(auth):
    """Schedule a health appointment."""
    print("\n--- Schedule Appointment ---")
    print("Available appointment types:")
    print("1. General Check-up")
    print("2. Mental Health Consultation")
    print("3. Vaccination")
    print("4. Emergency")

    choice = input("Select appointment type (1-4): ").strip()

    if choice in ['1', '2', '3', '4']:
        date = input("Preferred date (YYYY-MM-DD): ").strip()
        time = input("Preferred time (HH:MM): ").strip()
        notes = input("Additional notes (optional): ").strip()

        appointment_types = ['General Check-up', 'Mental Health Consultation', 'Vaccination', 'Emergency']
        appointment_type = appointment_types[int(choice) - 1]

        try:
            # Get student ID from username
            username = auth.get_username()
            conn = get_connection()
            cursor = conn.cursor()

            # Get user ID
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            user_row = cursor.fetchone()
            if not user_row:
                print("Error: User not found in database.")
                conn.close()
                return

            student_id = user_row['id']

            # Create health_appointments table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    appointment_type TEXT NOT NULL,
                    appointment_date TEXT NOT NULL,
                    appointment_time TEXT NOT NULL,
                    notes TEXT,
                    status TEXT DEFAULT 'Pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES users(id)
                )
            """)

            # Insert appointment
            cursor.execute("""
                INSERT INTO health_appointments
                (student_id, appointment_type, appointment_date, appointment_time, notes, status)
                VALUES (?, ?, ?, ?, ?, 'Pending')
            """, (student_id, appointment_type, date, time, notes))

            conn.commit()
            appointment_id = cursor.lastrowid
            conn.close()

            print(f"\nAppointment successfully scheduled!")
            print("=" * 50)
            print(f"Appointment ID: {appointment_id}")
            print(f"Type: {appointment_type}")
            print(f"Date: {date}")
            print(f"Time: {time}")
            if notes:
                print(f"Notes: {notes}")
            print(f"Status: Pending")
            print("=" * 50)
            print("\nYou will receive confirmation via email.")
            print("The health center will contact you to confirm your appointment.")

            logger.info(f"Appointment scheduled for {username}: {date} {time} - {appointment_type}")

        except Exception as e:
            logger.error(f"Error scheduling appointment: {e}")
            print(f"\nError scheduling appointment: {e}")
            print("Please try again or contact the health center.")
    else:
        print("Invalid appointment type.")

def view_medical_history(auth):
    """View medical history."""
    print("\n--- Medical History ---")

    try:
        # Get student ID from username
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found in database.")
            conn.close()
            return

        student_id = user_row['id']

        # Create medical_history table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medical_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                diagnosis TEXT NOT NULL,
                treatment TEXT,
                date TEXT NOT NULL,
                provider TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        """)
        conn.commit()

        # Query medical history
        cursor.execute("""
            SELECT diagnosis, treatment, date, provider, notes
            FROM medical_history
            WHERE student_id = ?
            ORDER BY date DESC
        """, (student_id,))

        history = cursor.fetchall()
        conn.close()

        if history:
            print("\nYour Medical History:")
            print("=" * 70)
            for i, record in enumerate(history, 1):
                print(f"\nRecord #{i}")
                print(f"  Date: {record['date']}")
                print(f"  Diagnosis: {record['diagnosis']}")
                if record['treatment']:
                    print(f"  Treatment: {record['treatment']}")
                if record['provider']:
                    print(f"  Provider: {record['provider']}")
                if record['notes']:
                    print(f"  Notes: {record['notes']}")
                print("-" * 70)
        else:
            print("\nNo medical history records found in the system.")
            print("Your medical history will be added as you receive care at the health center.")

        print("\nNote: For complete medical history or to update records,")
        print("please contact the health center or visit in person.")

    except Exception as e:
        logger.error(f"Error viewing medical history: {e}")
        print(f"\nError accessing medical history: {e}")
        print("Please contact the health center for assistance.")

def manage_emergency_contacts(auth):
    """Manage emergency contacts."""
    print("\n--- Emergency Contacts ---")
    print("1. View Current Contacts")
    print("2. Add New Contact")
    print("3. Update Contact")
    print("4. Remove Contact")

    choice = input("Select option (1-4): ").strip()

    try:
        # Get student ID from username
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found in database.")
            conn.close()
            return

        student_id = user_row['id']

        # Create emergency_contacts table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emergency_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                relationship TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                is_primary INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        """)
        conn.commit()

        if choice == '1':
            # View current contacts
            cursor.execute("""
                SELECT id, name, relationship, phone, email, is_primary
                FROM emergency_contacts
                WHERE student_id = ?
                ORDER BY is_primary DESC, name ASC
            """, (student_id,))

            contacts = cursor.fetchall()

            if contacts:
                print("\nYour Emergency Contacts:")
                print("=" * 70)
                for i, contact in enumerate(contacts, 1):
                    primary = " (PRIMARY)" if contact['is_primary'] else ""
                    print(f"\n{i}. {contact['name']} - {contact['relationship']}{primary}")
                    print(f"   Phone: {contact['phone']}")
                    if contact['email']:
                        print(f"   Email: {contact['email']}")
                    print(f"   Contact ID: {contact['id']}")
                print("=" * 70)
                print("\nTo add, update, or remove contacts, select options 2-4.")
            else:
                print("\nNo emergency contacts found.")
                print("Please add at least one emergency contact for your safety.")

        elif choice == '2':
            # Add new contact
            print("\nAdd New Emergency Contact:")
            name = input("Contact name: ").strip()
            relationship = input("Relationship: ").strip()
            phone = input("Phone number: ").strip()
            email = input("Email (optional): ").strip()
            is_primary = input("Set as primary contact? (y/n): ").strip().lower()

            if not name or not relationship or not phone:
                print("Error: Name, relationship, and phone are required.")
                conn.close()
                return

            is_primary_val = 1 if is_primary == 'y' else 0

            # If setting as primary, unset other primary contacts
            if is_primary_val:
                cursor.execute("""
                    UPDATE emergency_contacts
                    SET is_primary = 0
                    WHERE student_id = ?
                """, (student_id,))

            cursor.execute("""
                INSERT INTO emergency_contacts
                (student_id, name, relationship, phone, email, is_primary)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, name, relationship, phone, email or None, is_primary_val))

            conn.commit()
            contact_id = cursor.lastrowid

            print(f"\nEmergency contact added successfully!")
            print("=" * 50)
            print(f"Contact ID: {contact_id}")
            print(f"Name: {name} ({relationship})")
            print(f"Phone: {phone}")
            if email:
                print(f"Email: {email}")
            if is_primary_val:
                print("Status: PRIMARY CONTACT")
            print("=" * 50)

            logger.info(f"Emergency contact added for {username}: {name}")

        elif choice == '3':
            # Update existing contact
            print("\nUpdate Emergency Contact:")
            contact_id = input("Enter contact ID to update: ").strip()

            # Verify contact exists and belongs to student
            cursor.execute("""
                SELECT id, name, relationship, phone, email, is_primary
                FROM emergency_contacts
                WHERE id = ? AND student_id = ?
            """, (contact_id, student_id))

            existing = cursor.fetchone()

            if not existing:
                print(f"Error: Contact ID {contact_id} not found or doesn't belong to you.")
                conn.close()
                return

            print(f"\nCurrent contact information:")
            print(f"  Name: {existing['name']}")
            print(f"  Relationship: {existing['relationship']}")
            print(f"  Phone: {existing['phone']}")
            print(f"  Email: {existing['email'] or 'Not set'}")
            print(f"  Primary: {'Yes' if existing['is_primary'] else 'No'}")

            print("\nEnter new information (press Enter to keep current value):")
            name = input(f"Name [{existing['name']}]: ").strip() or existing['name']
            relationship = input(f"Relationship [{existing['relationship']}]: ").strip() or existing['relationship']
            phone = input(f"Phone [{existing['phone']}]: ").strip() or existing['phone']
            email = input(f"Email [{existing['email'] or 'none'}]: ").strip()
            if not email:
                email = existing['email']
            is_primary = input(f"Primary contact? (y/n) [{'y' if existing['is_primary'] else 'n'}]: ").strip().lower()

            if is_primary == 'y':
                is_primary_val = 1
                # Unset other primary contacts
                cursor.execute("""
                    UPDATE emergency_contacts
                    SET is_primary = 0
                    WHERE student_id = ? AND id != ?
                """, (student_id, contact_id))
            elif is_primary == 'n':
                is_primary_val = 0
            else:
                is_primary_val = existing['is_primary']

            cursor.execute("""
                UPDATE emergency_contacts
                SET name = ?, relationship = ?, phone = ?, email = ?, is_primary = ?
                WHERE id = ? AND student_id = ?
            """, (name, relationship, phone, email, is_primary_val, contact_id, student_id))

            conn.commit()

            print(f"\nContact #{contact_id} updated successfully!")
            logger.info(f"Emergency contact updated for {username}: contact {contact_id}")

        elif choice == '4':
            # Remove contact
            print("\nRemove Emergency Contact:")
            contact_id = input("Enter contact ID to remove: ").strip()

            # Verify contact exists and belongs to student
            cursor.execute("""
                SELECT id, name
                FROM emergency_contacts
                WHERE id = ? AND student_id = ?
            """, (contact_id, student_id))

            existing = cursor.fetchone()

            if not existing:
                print(f"Error: Contact ID {contact_id} not found or doesn't belong to you.")
                conn.close()
                return

            confirm = input(f"Are you sure you want to remove '{existing['name']}'? (y/n): ").strip().lower()
            if confirm == 'y':
                cursor.execute("""
                    DELETE FROM emergency_contacts
                    WHERE id = ? AND student_id = ?
                """, (contact_id, student_id))

                conn.commit()
                print(f"\nContact '{existing['name']}' removed successfully!")
                logger.info(f"Emergency contact removed for {username}: {existing['name']}")
            else:
                print("Removal cancelled.")

        else:
            print("Invalid option.")

        conn.close()

    except Exception as e:
        logger.error(f"Error managing emergency contacts: {e}")
        print(f"\nError managing emergency contacts: {e}")
        print("Please try again or contact support.")

def generate_health_reports(auth):
    """Generate health reports."""
    print("\n--- Health Reports ---")
    print("Available reports:")
    print("1. Immunization Status")
    print("2. Health Summary")
    print("3. Appointment History")

    choice = input("Select report type (1-3): ").strip()

    try:
        # Get student ID from username
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found in database.")
            conn.close()
            return

        student_id = user_row['id']

        if choice == '1':
            # Immunization Status Report
            print("\n" + "=" * 70)
            print("IMMUNIZATION STATUS REPORT")
            print("=" * 70)
            print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Student: {username}")
            print("-" * 70)

            # Ensure vaccinations table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vaccinations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    vaccine_name TEXT NOT NULL,
                    date_administered TEXT NOT NULL,
                    next_due_date TEXT,
                    status TEXT DEFAULT 'Complete',
                    provider TEXT,
                    lot_number TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES users(id)
                )
            """)
            conn.commit()

            cursor.execute("""
                SELECT vaccine_name, date_administered, next_due_date, status, provider
                FROM vaccinations
                WHERE student_id = ?
                ORDER BY date_administered DESC
            """, (student_id,))

            vaccinations = cursor.fetchall()

            if vaccinations:
                print("\nVaccination Records:")
                for vax in vaccinations:
                    print(f"\n  Vaccine: {vax['vaccine_name']}")
                    print(f"  Date Administered: {vax['date_administered']}")
                    if vax['next_due_date']:
                        print(f"  Next Due Date: {vax['next_due_date']}")
                    print(f"  Status: {vax['status']}")
                    if vax['provider']:
                        print(f"  Provider: {vax['provider']}")
                    print("  " + "-" * 65)
            else:
                print("\nNo vaccination records found.")
                print("Please visit the health center to update your immunization records.")

        elif choice == '2':
            # Health Summary Report
            print("\n" + "=" * 70)
            print("HEALTH SUMMARY REPORT")
            print("=" * 70)
            print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Student: {username}")
            print("-" * 70)

            # Get health records
            cursor.execute("""
                SELECT blood_type, allergies, medications, conditions
                FROM health_records
                WHERE student_id = ?
            """, (student_id,))

            health_record = cursor.fetchone()

            if health_record:
                print("\nBasic Health Information:")
                if health_record['blood_type']:
                    print(f"  Blood Type: {health_record['blood_type']}")
                if health_record['allergies']:
                    print(f"  Allergies: {health_record['allergies']}")
                if health_record['medications']:
                    print(f"  Current Medications: {health_record['medications']}")
                if health_record['conditions']:
                    print(f"  Medical Conditions: {health_record['conditions']}")
            else:
                print("\nNo health records found.")

            # Get recent medical history
            cursor.execute("""
                SELECT diagnosis, date, provider
                FROM medical_history
                WHERE student_id = ?
                ORDER BY date DESC
                LIMIT 5
            """, (student_id,))

            history = cursor.fetchall()

            if history:
                print("\nRecent Medical History:")
                for record in history:
                    print(f"  - {record['date']}: {record['diagnosis']}")
                    if record['provider']:
                        print(f"    Provider: {record['provider']}")

            # Get emergency contacts
            cursor.execute("""
                SELECT name, relationship, phone
                FROM emergency_contacts
                WHERE student_id = ?
                ORDER BY is_primary DESC
                LIMIT 2
            """, (student_id,))

            contacts = cursor.fetchall()

            if contacts:
                print("\nEmergency Contacts:")
                for contact in contacts:
                    print(f"  - {contact['name']} ({contact['relationship']}): {contact['phone']}")

        elif choice == '3':
            # Appointment History Report
            print("\n" + "=" * 70)
            print("APPOINTMENT HISTORY REPORT")
            print("=" * 70)
            print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Student: {username}")
            print("-" * 70)

            cursor.execute("""
                SELECT appointment_type, appointment_date, appointment_time,
                       status, notes, created_at
                FROM health_appointments
                WHERE student_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
            """, (student_id,))

            appointments = cursor.fetchall()

            if appointments:
                print("\nAppointment History:")
                for apt in appointments:
                    print(f"\n  Date: {apt['appointment_date']} at {apt['appointment_time']}")
                    print(f"  Type: {apt['appointment_type']}")
                    print(f"  Status: {apt['status']}")
                    if apt['notes']:
                        print(f"  Notes: {apt['notes']}")
                    print(f"  Scheduled On: {apt['created_at']}")
                    print("  " + "-" * 65)

                # Statistics
                total = len(appointments)
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM health_appointments
                    WHERE student_id = ?
                    GROUP BY status
                """, (student_id,))
                stats = cursor.fetchall()

                print(f"\nAppointment Statistics:")
                print(f"  Total Appointments: {total}")
                for stat in stats:
                    print(f"  {stat['status']}: {stat['count']}")
            else:
                print("\nNo appointment history found.")
                print("Schedule your first appointment to begin tracking your health visits.")

        else:
            print("Invalid report type.")
            conn.close()
            return

        print("\n" + "=" * 70)
        print("End of Report")
        print("=" * 70)
        print("\nNote: For official medical reports, please contact the health center.")

        conn.close()

    except Exception as e:
        logger.error(f"Error generating health report: {e}")
        print(f"\nError generating report: {e}")
        print("Please try again or contact the health center.")

def view_vaccination_records(auth):
    """View vaccination records."""
    print("\n--- Vaccination Records ---")

    try:
        # Get student ID from username
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found in database.")
            conn.close()
            return

        student_id = user_row['id']

        # Create vaccinations table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vaccinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                vaccine_name TEXT NOT NULL,
                date_administered TEXT NOT NULL,
                next_due_date TEXT,
                status TEXT DEFAULT 'Complete',
                provider TEXT,
                lot_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        """)
        conn.commit()

        # Query vaccination records
        cursor.execute("""
            SELECT vaccine_name, date_administered, next_due_date, status, provider, lot_number
            FROM vaccinations
            WHERE student_id = ?
            ORDER BY date_administered DESC
        """, (student_id,))

        vaccinations = cursor.fetchall()
        conn.close()

        if vaccinations:
            print("\nYour Vaccination Records:")
            print("=" * 70)

            # Group by status for better presentation
            up_to_date = []
            due_soon = []
            overdue = []

            current_date = datetime.now().date()

            for vax in vaccinations:
                if vax['status'] == 'Complete':
                    if vax['next_due_date']:
                        try:
                            next_due = datetime.strptime(vax['next_due_date'], '%Y-%m-%d').date()
                            days_until_due = (next_due - current_date).days
                            if days_until_due < 0:
                                overdue.append(vax)
                            elif days_until_due <= 30:
                                due_soon.append(vax)
                            else:
                                up_to_date.append(vax)
                        except ValueError:
                            up_to_date.append(vax)
                    else:
                        up_to_date.append(vax)
                else:
                    overdue.append(vax)

            # Display overdue vaccinations first
            if overdue:
                print("\nOVERDUE / ATTENTION NEEDED:")
                print("-" * 70)
                for vax in overdue:
                    print(f"\n  Vaccine: {vax['vaccine_name']}")
                    print(f"  Last Administered: {vax['date_administered']}")
                    if vax['next_due_date']:
                        print(f"  Due Date: {vax['next_due_date']}")
                    print(f"  Status: {vax['status']}")
                    print("  ACTION REQUIRED: Please schedule an appointment")

            # Display due soon vaccinations
            if due_soon:
                print("\n\nDUE SOON (within 30 days):")
                print("-" * 70)
                for vax in due_soon:
                    print(f"\n  Vaccine: {vax['vaccine_name']}")
                    print(f"  Last Administered: {vax['date_administered']}")
                    print(f"  Next Due Date: {vax['next_due_date']}")
                    if vax['provider']:
                        print(f"  Provider: {vax['provider']}")

            # Display up to date vaccinations
            if up_to_date:
                print("\n\nUP TO DATE:")
                print("-" * 70)
                for vax in up_to_date:
                    print(f"\n  Vaccine: {vax['vaccine_name']}")
                    print(f"  Date Administered: {vax['date_administered']}")
                    if vax['next_due_date']:
                        print(f"  Next Due Date: {vax['next_due_date']}")
                    print(f"  Status: {vax['status']}")
                    if vax['provider']:
                        print(f"  Provider: {vax['provider']}")
                    if vax['lot_number']:
                        print(f"  Lot Number: {vax['lot_number']}")

            print("\n" + "=" * 70)

            # Summary
            print(f"\nVaccination Summary:")
            print(f"  Total Vaccines: {len(vaccinations)}")
            print(f"  Up to Date: {len(up_to_date)}")
            print(f"  Due Soon: {len(due_soon)}")
            print(f"  Overdue: {len(overdue)}")

        else:
            print("\nNo vaccination records found in the system.")
            print("Please visit the health center to add your vaccination history.")

        print("\nNote: Keep your vaccination records up to date.")
        print("Contact the health center to schedule vaccinations or update your records.")
        print("For official vaccination certificates, please visit the health center.")

    except Exception as e:
        logger.error(f"Error viewing vaccination records: {e}")
        print(f"\nError accessing vaccination records: {e}")
        print("Please contact the health center for assistance.")


# ============================================================================
# DATA EXPORT & BACKUP MENU
# ============================================================================

def data_export_menu(auth):
    """Data export and backup menu."""
    print("\n--- Data Export & Backup ---")

    while True:
        print("\n" + "="*60)
        print("             DATA EXPORT & BACKUP")
        print("="*60)
        print("1. Export Health Records (CSV/JSON)")
        print("2. Export Vaccination Records")
        print("3. Export Appointment Data")
        print("4. Export Emergency Contacts")
        print("5. Export Custom Dataset")
        print("0. Return to Main Menu")
        print("="*60)

        choice = input("Enter your choice (0-5): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            export_health_records(auth)
        elif choice == '2':
            export_vaccination_records(auth)
        elif choice == '3':
            export_appointment_data(auth)
        elif choice == '4':
            export_emergency_contacts(auth)
        elif choice == '5':
            export_custom_dataset(auth)
        else:
            print("Invalid choice. Please try again.")


def export_health_records(auth):
    """Export health records to CSV or JSON."""
    print("\n--- Export Health Records ---")

    try:
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found.")
            conn.close()
            return

        student_id = user_row['id']

        # Select format
        print("\nSelect export format:")
        print("1. CSV")
        print("2. JSON")
        format_choice = input("Enter choice (1-2): ").strip()

        # Query health records
        cursor.execute("""
            SELECT blood_type, allergies, medications, conditions,
                   insurance_provider, insurance_policy_number, last_updated
            FROM health_records
            WHERE student_id = ?
        """, (student_id,))

        record = cursor.fetchone()
        conn.close()

        if not record:
            print("\nNo health records found to export.")
            return

        # Create exports directory
        export_dir = paths.DATA_DIR / 'exports' / 'health'
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if format_choice == '1':
            # CSV export
            filename = export_dir / f'health_records_{username}_{timestamp}.csv'
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Field', 'Value'])
                writer.writerow(['Blood Type', record['blood_type'] or 'N/A'])
                writer.writerow(['Allergies', record['allergies'] or 'N/A'])
                writer.writerow(['Medications', record['medications'] or 'N/A'])
                writer.writerow(['Conditions', record['conditions'] or 'N/A'])
                writer.writerow(['Insurance Provider', record['insurance_provider'] or 'N/A'])
                writer.writerow(['Policy Number', record['insurance_policy_number'] or 'N/A'])
                writer.writerow(['Last Updated', record['last_updated'] or 'N/A'])
            print(f"\n✓ Health records exported to: {filename}")

        elif format_choice == '2':
            # JSON export
            filename = export_dir / f'health_records_{username}_{timestamp}.json'
            data = {
                'student': username,
                'export_date': datetime.now().isoformat(),
                'health_records': {
                    'blood_type': record['blood_type'],
                    'allergies': record['allergies'],
                    'medications': record['medications'],
                    'conditions': record['conditions'],
                    'insurance_provider': record['insurance_provider'],
                    'insurance_policy_number': record['insurance_policy_number'],
                    'last_updated': record['last_updated']
                }
            }
            with open(filename, 'w') as jsonfile:
                json.dump(data, jsonfile, indent=2)
            print(f"\n✓ Health records exported to: {filename}")
        else:
            print("Invalid format choice.")

        logger.info(f"Health records exported by {username}")

    except Exception as e:
        logger.error(f"Error exporting health records: {e}")
        print(f"\nError exporting health records: {e}")


def export_vaccination_records(auth):
    """Export vaccination records to CSV."""
    print("\n--- Export Vaccination Records ---")

    try:
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found.")
            conn.close()
            return

        student_id = user_row['id']

        # Query vaccination records
        cursor.execute("""
            SELECT vaccine_name, date_administered, next_due_date, status, provider, lot_number
            FROM vaccinations
            WHERE student_id = ?
            ORDER BY date_administered DESC
        """, (student_id,))

        vaccinations = cursor.fetchall()
        conn.close()

        if not vaccinations:
            print("\nNo vaccination records found to export.")
            return

        # Create exports directory
        export_dir = paths.DATA_DIR / 'exports' / 'health'
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = export_dir / f'vaccinations_{username}_{timestamp}.csv'

        # Write CSV
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Vaccine Name', 'Date Administered', 'Next Due Date', 'Status', 'Provider', 'Lot Number'])
            for vax in vaccinations:
                writer.writerow([
                    vax['vaccine_name'],
                    vax['date_administered'],
                    vax['next_due_date'] or 'N/A',
                    vax['status'],
                    vax['provider'] or 'N/A',
                    vax['lot_number'] or 'N/A'
                ])

        print(f"\n✓ Vaccination records exported to: {filename}")
        print(f"  Total records: {len(vaccinations)}")
        logger.info(f"Vaccination records exported by {username}")

    except Exception as e:
        logger.error(f"Error exporting vaccination records: {e}")
        print(f"\nError exporting vaccination records: {e}")


def export_appointment_data(auth):
    """Export appointment data to CSV."""
    print("\n--- Export Appointment Data ---")

    try:
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found.")
            conn.close()
            return

        student_id = user_row['id']

        # Query appointments
        cursor.execute("""
            SELECT appointment_type, appointment_date, appointment_time,
                   status, notes, created_at
            FROM health_appointments
            WHERE student_id = ?
            ORDER BY appointment_date DESC, appointment_time DESC
        """, (student_id,))

        appointments = cursor.fetchall()
        conn.close()

        if not appointments:
            print("\nNo appointment data found to export.")
            return

        # Create exports directory
        export_dir = paths.DATA_DIR / 'exports' / 'health'
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = export_dir / f'appointments_{username}_{timestamp}.csv'

        # Write CSV
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Type', 'Date', 'Time', 'Status', 'Notes', 'Created At'])
            for apt in appointments:
                writer.writerow([
                    apt['appointment_type'],
                    apt['appointment_date'],
                    apt['appointment_time'],
                    apt['status'],
                    apt['notes'] or 'N/A',
                    apt['created_at']
                ])

        print(f"\n✓ Appointment data exported to: {filename}")
        print(f"  Total appointments: {len(appointments)}")
        logger.info(f"Appointment data exported by {username}")

    except Exception as e:
        logger.error(f"Error exporting appointment data: {e}")
        print(f"\nError exporting appointment data: {e}")


def export_emergency_contacts(auth):
    """Export emergency contacts to CSV."""
    print("\n--- Export Emergency Contacts ---")

    try:
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found.")
            conn.close()
            return

        student_id = user_row['id']

        # Query emergency contacts
        cursor.execute("""
            SELECT name, relationship, phone, email, is_primary
            FROM emergency_contacts
            WHERE student_id = ?
            ORDER BY is_primary DESC, name ASC
        """, (student_id,))

        contacts = cursor.fetchall()
        conn.close()

        if not contacts:
            print("\nNo emergency contacts found to export.")
            return

        # Create exports directory
        export_dir = paths.DATA_DIR / 'exports' / 'health'
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = export_dir / f'emergency_contacts_{username}_{timestamp}.csv'

        # Write CSV
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Name', 'Relationship', 'Phone', 'Email', 'Primary Contact'])
            for contact in contacts:
                writer.writerow([
                    contact['name'],
                    contact['relationship'],
                    contact['phone'],
                    contact['email'] or 'N/A',
                    'Yes' if contact['is_primary'] else 'No'
                ])

        print(f"\n✓ Emergency contacts exported to: {filename}")
        print(f"  Total contacts: {len(contacts)}")
        logger.info(f"Emergency contacts exported by {username}")

    except Exception as e:
        logger.error(f"Error exporting emergency contacts: {e}")
        print(f"\nError exporting emergency contacts: {e}")


def export_custom_dataset(auth):
    """Export custom dataset with filters."""
    print("\n--- Export Custom Dataset ---")
    print("\nAvailable datasets:")
    print("1. All Health Data (comprehensive export)")
    print("2. Medical History Only")
    print("3. Complete Health Profile")

    choice = input("Select dataset (1-3): ").strip()

    try:
        username = auth.get_username()
        conn = get_connection()
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        if not user_row:
            print("Error: User not found.")
            conn.close()
            return

        student_id = user_row['id']

        # Create exports directory
        export_dir = paths.DATA_DIR / 'exports' / 'health'
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if choice == '1':
            # Comprehensive export (JSON)
            filename = export_dir / f'complete_health_data_{username}_{timestamp}.json'

            data = {
                'student': username,
                'export_date': datetime.now().isoformat(),
                'health_records': {},
                'vaccinations': [],
                'appointments': [],
                'medical_history': [],
                'emergency_contacts': []
            }

            # Health records
            cursor.execute("""
                SELECT blood_type, allergies, medications, conditions,
                       insurance_provider, insurance_policy_number
                FROM health_records WHERE student_id = ?
            """, (student_id,))
            health_rec = cursor.fetchone()
            if health_rec:
                data['health_records'] = dict(health_rec)

            # Vaccinations
            cursor.execute("SELECT * FROM vaccinations WHERE student_id = ?", (student_id,))
            data['vaccinations'] = [dict(row) for row in cursor.fetchall()]

            # Appointments
            cursor.execute("SELECT * FROM health_appointments WHERE student_id = ?", (student_id,))
            data['appointments'] = [dict(row) for row in cursor.fetchall()]

            # Medical history
            cursor.execute("SELECT * FROM medical_history WHERE student_id = ?", (student_id,))
            data['medical_history'] = [dict(row) for row in cursor.fetchall()]

            # Emergency contacts
            cursor.execute("SELECT * FROM emergency_contacts WHERE student_id = ?", (student_id,))
            data['emergency_contacts'] = [dict(row) for row in cursor.fetchall()]

            with open(filename, 'w') as jsonfile:
                json.dump(data, jsonfile, indent=2)

            print(f"\n✓ Complete health data exported to: {filename}")

        elif choice == '2':
            # Medical history only
            filename = export_dir / f'medical_history_{username}_{timestamp}.csv'

            cursor.execute("""
                SELECT diagnosis, treatment, date, provider, notes
                FROM medical_history
                WHERE student_id = ?
                ORDER BY date DESC
            """, (student_id,))

            history = cursor.fetchall()

            if history:
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Date', 'Diagnosis', 'Treatment', 'Provider', 'Notes'])
                    for record in history:
                        writer.writerow([
                            record['date'],
                            record['diagnosis'],
                            record['treatment'] or 'N/A',
                            record['provider'] or 'N/A',
                            record['notes'] or 'N/A'
                        ])
                print(f"\n✓ Medical history exported to: {filename}")
                print(f"  Total records: {len(history)}")
            else:
                print("\nNo medical history found to export.")

        elif choice == '3':
            # Complete health profile (formatted text)
            filename = export_dir / f'health_profile_{username}_{timestamp}.txt'

            with open(filename, 'w') as txtfile:
                txtfile.write("="*70 + "\n")
                txtfile.write(f"HEALTH PROFILE FOR: {username}\n")
                txtfile.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                txtfile.write("="*70 + "\n\n")

                # Health records
                cursor.execute("""
                    SELECT * FROM health_records WHERE student_id = ?
                """, (student_id,))
                health_rec = cursor.fetchone()
                if health_rec:
                    txtfile.write("HEALTH RECORDS:\n")
                    txtfile.write(f"  Blood Type: {health_rec['blood_type'] or 'N/A'}\n")
                    txtfile.write(f"  Allergies: {health_rec['allergies'] or 'None'}\n")
                    txtfile.write(f"  Medications: {health_rec['medications'] or 'None'}\n")
                    txtfile.write(f"  Conditions: {health_rec['conditions'] or 'None'}\n")
                    txtfile.write(f"  Insurance: {health_rec['insurance_provider'] or 'N/A'}\n\n")

                # Emergency contacts
                cursor.execute("""
                    SELECT * FROM emergency_contacts WHERE student_id = ?
                    ORDER BY is_primary DESC
                """, (student_id,))
                contacts = cursor.fetchall()
                if contacts:
                    txtfile.write("EMERGENCY CONTACTS:\n")
                    for contact in contacts:
                        primary = " (PRIMARY)" if contact['is_primary'] else ""
                        txtfile.write(f"  {contact['name']}{primary} - {contact['relationship']}\n")
                        txtfile.write(f"    Phone: {contact['phone']}\n")
                        if contact['email']:
                            txtfile.write(f"    Email: {contact['email']}\n")
                        txtfile.write("\n")

            print(f"\n✓ Health profile exported to: {filename}")
        else:
            print("Invalid choice.")
            conn.close()
            return

        conn.close()
        logger.info(f"Custom dataset exported by {username}")

    except Exception as e:
        logger.error(f"Error exporting custom dataset: {e}")
        print(f"\nError exporting custom dataset: {e}")


# ============================================================================
# SECURITY & AUDIT TOOLS
# ============================================================================

def security_audit_menu(auth):
    """Security and audit tools menu."""
    print("\n--- Security & Audit Tools ---")

    while True:
        print("\n" + "="*60)
        print("           SECURITY & AUDIT TOOLS")
        print("="*60)
        print("1. View Audit Log")
        print("2. Export Audit Log")
        print("3. View Access Summary")
        print("4. View Failed Login Attempts")
        print("5. Generate Security Report")
        print("0. Return to Main Menu")
        print("="*60)

        choice = input("Enter your choice (0-5): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            view_audit_log(auth)
        elif choice == '2':
            export_audit_log(auth)
        elif choice == '3':
            view_access_summary(auth)
        elif choice == '4':
            view_failed_logins(auth)
        elif choice == '5':
            generate_security_report(auth)
        else:
            print("Invalid choice. Please try again.")


def view_audit_log(auth):
    """View audit log with filtering."""
    print("\n--- Audit Log ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create audit_trail table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                table_name TEXT,
                record_id TEXT,
                details TEXT,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

        # Filter options
        print("\nFilter options:")
        print("1. All records")
        print("2. My records only")
        print("3. Last 24 hours")
        print("4. Last 7 days")

        filter_choice = input("Select filter (1-4): ").strip()

        query = "SELECT * FROM audit_trail"
        params = []

        if filter_choice == '2':
            username = auth.get_username()
            query += " WHERE username = ?"
            params.append(username)
        elif filter_choice == '3':
            cutoff = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            query += " WHERE timestamp >= ?"
            params.append(cutoff)
        elif filter_choice == '4':
            cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            query += " WHERE timestamp >= ?"
            params.append(cutoff)

        query += " ORDER BY timestamp DESC LIMIT 50"

        cursor.execute(query, params)
        logs = cursor.fetchall()
        conn.close()

        if logs:
            print("\n" + "="*90)
            print(f"{'ID':<6} {'User':<15} {'Action':<15} {'Table':<15} {'Timestamp':<20}")
            print("="*90)
            for log in logs:
                print(f"{log['id']:<6} {log['username'] or 'System':<15} "
                      f"{log['action']:<15} {log['table_name'] or 'N/A':<15} "
                      f"{log['timestamp']:<20}")
                if log['details']:
                    print(f"       Details: {log['details'][:70]}")
            print("="*90)
            print(f"\nShowing {len(logs)} records")
        else:
            print("\nNo audit log entries found.")

    except Exception as e:
        logger.error(f"Error viewing audit log: {e}")
        print(f"\nError viewing audit log: {e}")


def export_audit_log(auth):
    """Export audit log to CSV."""
    print("\n--- Export Audit Log ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Date range filter
        print("\nDate range options:")
        print("1. All time")
        print("2. Last 30 days")
        print("3. Last 90 days")
        print("4. Custom date range")

        range_choice = input("Select range (1-4): ").strip()

        query = "SELECT * FROM audit_trail"
        params = []

        if range_choice == '2':
            cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            query += " WHERE timestamp >= ?"
            params.append(cutoff)
        elif range_choice == '3':
            cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
            query += " WHERE timestamp >= ?"
            params.append(cutoff)
        elif range_choice == '4':
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            query += " WHERE date(timestamp) BETWEEN ? AND ?"
            params.extend([start_date, end_date])

        query += " ORDER BY timestamp DESC"

        cursor.execute(query, params)
        logs = cursor.fetchall()
        conn.close()

        if not logs:
            print("\nNo audit log entries found for the selected period.")
            return

        # Create exports directory
        export_dir = paths.DATA_DIR / 'exports' / 'audit'
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = export_dir / f'audit_log_{timestamp}.csv'

        # Write CSV
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ID', 'User ID', 'Username', 'Action', 'Table', 'Record ID', 'Details', 'IP Address', 'Timestamp'])
            for log in logs:
                writer.writerow([
                    log['id'],
                    log['user_id'] or '',
                    log['username'] or 'System',
                    log['action'],
                    log['table_name'] or '',
                    log['record_id'] or '',
                    log['details'] or '',
                    log['ip_address'] or '',
                    log['timestamp']
                ])

        print(f"\n✓ Audit log exported to: {filename}")
        print(f"  Total records: {len(logs)}")
        logger.info(f"Audit log exported by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error exporting audit log: {e}")
        print(f"\nError exporting audit log: {e}")


def view_access_summary(auth):
    """View access summary statistics."""
    print("\n--- Access Summary ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*70)
        print("ACCESS SUMMARY STATISTICS")
        print("="*70)

        # Total audit entries
        cursor.execute("SELECT COUNT(*) as count FROM audit_trail")
        total = cursor.fetchone()['count']
        print(f"\nTotal Audit Entries: {total}")

        # Entries by user
        cursor.execute("""
            SELECT username, COUNT(*) as count
            FROM audit_trail
            WHERE username IS NOT NULL
            GROUP BY username
            ORDER BY count DESC
            LIMIT 10
        """)
        user_stats = cursor.fetchall()

        if user_stats:
            print("\nTop 10 Users by Activity:")
            print(f"{'Username':<20} {'Actions':<10}")
            print("-"*30)
            for stat in user_stats:
                print(f"{stat['username']:<20} {stat['count']:<10}")

        # Entries by action type
        cursor.execute("""
            SELECT action, COUNT(*) as count
            FROM audit_trail
            GROUP BY action
            ORDER BY count DESC
        """)
        action_stats = cursor.fetchall()

        if action_stats:
            print("\nActions by Type:")
            print(f"{'Action':<20} {'Count':<10}")
            print("-"*30)
            for stat in action_stats:
                print(f"{stat['action']:<20} {stat['count']:<10}")

        # Recent activity (last 24 hours)
        cutoff = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM audit_trail
            WHERE timestamp >= ?
        """, (cutoff,))
        recent = cursor.fetchone()['count']
        print(f"\nActivity in Last 24 Hours: {recent}")

        # Activity by table
        cursor.execute("""
            SELECT table_name, COUNT(*) as count
            FROM audit_trail
            WHERE table_name IS NOT NULL
            GROUP BY table_name
            ORDER BY count DESC
            LIMIT 5
        """)
        table_stats = cursor.fetchall()

        if table_stats:
            print("\nMost Accessed Tables:")
            print(f"{'Table':<25} {'Accesses':<10}")
            print("-"*35)
            for stat in table_stats:
                print(f"{stat['table_name']:<25} {stat['count']:<10}")

        print("="*70)

        conn.close()

    except Exception as e:
        logger.error(f"Error viewing access summary: {e}")
        print(f"\nError viewing access summary: {e}")


def view_failed_logins(auth):
    """View failed login attempts."""
    print("\n--- Failed Login Attempts ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create failed_logins table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failed_logins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                ip_address TEXT,
                reason TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Query recent failed logins
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            SELECT username, ip_address, reason, timestamp
            FROM failed_logins
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 50
        """, (cutoff,))

        failed = cursor.fetchall()
        conn.close()

        if failed:
            print("\n" + "="*80)
            print("FAILED LOGIN ATTEMPTS (Last 7 Days)")
            print("="*80)
            print(f"{'Username':<20} {'IP Address':<18} {'Reason':<20} {'Timestamp':<20}")
            print("-"*80)
            for attempt in failed:
                print(f"{attempt['username'] or 'Unknown':<20} "
                      f"{attempt['ip_address'] or 'N/A':<18} "
                      f"{attempt['reason'] or 'N/A':<20} "
                      f"{attempt['timestamp']:<20}")
            print("="*80)
            print(f"\nTotal failed attempts: {len(failed)}")

            # Summary by username
            print("\nFailed Attempts by Username:")
            username_counts = {}
            for attempt in failed:
                username = attempt['username'] or 'Unknown'
                username_counts[username] = username_counts.get(username, 0) + 1

            for username, count in sorted(username_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {username}: {count} attempts")

        else:
            print("\n✓ No failed login attempts in the last 7 days.")

    except Exception as e:
        logger.error(f"Error viewing failed logins: {e}")
        print(f"\nError viewing failed logins: {e}")


def generate_security_report(auth):
    """Generate comprehensive security report."""
    print("\n--- Security Report ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*70)
        print("SECURITY COMPLIANCE REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        # User access statistics
        cursor.execute("SELECT COUNT(DISTINCT username) as count FROM audit_trail WHERE username IS NOT NULL")
        unique_users = cursor.fetchone()['count']
        print(f"\nActive Users (with audit trail): {unique_users}")

        # Recent audit activity
        cutoff_24h = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        cutoff_7d = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("SELECT COUNT(*) as count FROM audit_trail WHERE timestamp >= ?", (cutoff_24h,))
        activity_24h = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM audit_trail WHERE timestamp >= ?", (cutoff_7d,))
        activity_7d = cursor.fetchone()['count']

        print(f"\nAudit Trail Activity:")
        print(f"  Last 24 hours: {activity_24h} events")
        print(f"  Last 7 days: {activity_7d} events")

        # Failed login analysis
        cursor.execute("""
            SELECT COUNT(*) as count FROM failed_logins
            WHERE timestamp >= ?
        """, (cutoff_7d,))
        failed_7d = cursor.fetchone()['count']

        cursor.execute("""
            SELECT username, COUNT(*) as count
            FROM failed_logins
            WHERE timestamp >= ?
            GROUP BY username
            ORDER BY count DESC
            LIMIT 5
        """, (cutoff_7d,))
        top_failed = cursor.fetchall()

        print(f"\nSecurity Events (Last 7 Days):")
        print(f"  Failed Login Attempts: {failed_7d}")

        if top_failed:
            print("\n  Top Accounts with Failed Logins:")
            for record in top_failed:
                print(f"    {record['username'] or 'Unknown'}: {record['count']} attempts")

        # Data access by table
        cursor.execute("""
            SELECT table_name, COUNT(*) as count
            FROM audit_trail
            WHERE table_name IN ('health_records', 'medical_history', 'vaccinations')
              AND timestamp >= ?
            GROUP BY table_name
        """, (cutoff_7d,))
        sensitive_access = cursor.fetchall()

        if sensitive_access:
            print("\n  Sensitive Data Access (Last 7 Days):")
            for record in sensitive_access:
                print(f"    {record['table_name']}: {record['count']} accesses")

        # Recommendations
        print("\nSecurity Recommendations:")
        if failed_7d > 10:
            print("  ⚠ High number of failed login attempts detected")
            print("    → Review failed login patterns and consider additional security measures")
        else:
            print("  ✓ Failed login attempts within normal range")

        if activity_24h == 0:
            print("  ⚠ No audit trail activity in last 24 hours")
            print("    → Verify audit logging is functioning correctly")
        else:
            print("  ✓ Audit logging is active")

        print("\n" + "="*70)
        print("End of Security Report")
        print("="*70)

        conn.close()
        logger.info(f"Security report generated by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error generating security report: {e}")
        print(f"\nError generating security report: {e}")


# ============================================================================
# DATABASE BACKUP MANAGEMENT
# ============================================================================

def backup_management_menu(auth):
    """Database backup management menu."""
    print("\n--- Database Backup Management ---")

    while True:
        print("\n" + "="*60)
        print("        DATABASE BACKUP MANAGEMENT")
        print("="*60)
        print("1. Create Manual Backup")
        print("2. View Backup History")
        print("3. Restore from Backup (Admin Only)")
        print("0. Return to Main Menu")
        print("="*60)

        choice = input("Enter your choice (0-3): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            create_manual_backup(auth)
        elif choice == '2':
            view_backup_history(auth)
        elif choice == '3':
            restore_from_backup(auth)
        else:
            print("Invalid choice. Please try again.")


def create_manual_backup(auth):
    """Create a manual database backup."""
    print("\n--- Create Manual Backup ---")

    try:
        # Create backups directory
        backup_dir = paths.DATA_DIR / 'backups' / 'health'
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        username = auth.get_username()
        backup_filename = backup_dir / f'health_backup_{timestamp}_{username}.db'

        # Copy the database file
        db_path = DEFAULT_DB_PATH
        if isinstance(db_path, str):
            db_path = Path(db_path)

        if not db_path.exists():
            print(f"\nError: Database file not found at {db_path}")
            return

        # Perform the backup
        print(f"\nCreating backup...")
        shutil.copy2(db_path, backup_filename)

        # Get backup size
        backup_size = backup_filename.stat().st_size / (1024 * 1024)  # MB

        # Log backup in database
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_filename TEXT NOT NULL,
                backup_size_mb REAL,
                created_by TEXT,
                backup_type TEXT DEFAULT 'manual',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO backup_history (backup_filename, backup_size_mb, created_by, backup_type)
            VALUES (?, ?, ?, 'manual')
        """, (str(backup_filename), backup_size, username))

        conn.commit()
        backup_id = cursor.lastrowid
        conn.close()

        print(f"\n✓ Backup created successfully!")
        print("="*60)
        print(f"Backup ID: {backup_id}")
        print(f"Filename: {backup_filename.name}")
        print(f"Location: {backup_dir}")
        print(f"Size: {backup_size:.2f} MB")
        print(f"Created by: {username}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        logger.info(f"Manual backup created by {username}: {backup_filename}")

    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        print(f"\nError creating backup: {e}")


def view_backup_history(auth):
    """View backup history."""
    print("\n--- Backup History ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create backup_history table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_filename TEXT NOT NULL,
                backup_size_mb REAL,
                created_by TEXT,
                backup_type TEXT DEFAULT 'manual',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Query backup history
        cursor.execute("""
            SELECT id, backup_filename, backup_size_mb, created_by, backup_type, timestamp
            FROM backup_history
            ORDER BY timestamp DESC
            LIMIT 20
        """)

        backups = cursor.fetchall()
        conn.close()

        if backups:
            print("\n" + "="*90)
            print(f"{'ID':<6} {'Filename':<35} {'Size (MB)':<12} {'Type':<10} {'Created By':<15}")
            print("="*90)
            for backup in backups:
                filename = Path(backup['backup_filename']).name
                print(f"{backup['id']:<6} {filename:<35} {backup['backup_size_mb']:<12.2f} "
                      f"{backup['backup_type']:<10} {backup['created_by'] or 'System':<15}")
                print(f"       Created: {backup['timestamp']}")
            print("="*90)
            print(f"\nShowing {len(backups)} most recent backups")

            # Summary statistics
            total_backups = len(backups)
            total_size = sum(b['backup_size_mb'] for b in backups if b['backup_size_mb'])
            print(f"\nStatistics:")
            print(f"  Total backups shown: {total_backups}")
            print(f"  Total size: {total_size:.2f} MB")

        else:
            print("\nNo backup history found.")
            print("Create your first backup using option 1.")

    except Exception as e:
        logger.error(f"Error viewing backup history: {e}")
        print(f"\nError viewing backup history: {e}")


def restore_from_backup(auth):
    """Restore database from backup (admin only)."""
    print("\n--- Restore from Backup ---")
    print("\n⚠  WARNING: This is an admin-only operation!")
    print("⚠  Restoring will replace the current database!")

    # Check if user is admin
    try:
        user_role = auth.get_role() if hasattr(auth, 'get_role') else None
        if user_role != 'admin':
            print("\n✗ Access Denied: Admin privileges required")
            print("  This operation requires administrator access.")
            logger.warning(f"Unauthorized restore attempt by {auth.get_username()}")
            return
    except Exception:
        print("\n✗ Could not verify admin status")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Show available backups
        cursor.execute("""
            SELECT id, backup_filename, backup_size_mb, timestamp
            FROM backup_history
            ORDER BY timestamp DESC
            LIMIT 10
        """)

        backups = cursor.fetchall()
        conn.close()

        if not backups:
            print("\nNo backups available for restore.")
            return

        print("\nAvailable backups:")
        print("="*80)
        for i, backup in enumerate(backups, 1):
            filename = Path(backup['backup_filename']).name
            print(f"{i}. [{backup['id']}] {filename}")
            print(f"   Size: {backup['backup_size_mb']:.2f} MB | Created: {backup['timestamp']}")

        print("="*80)

        # Select backup to restore
        choice = input("\nEnter backup number to restore (0 to cancel): ").strip()

        if choice == '0':
            print("Restore cancelled.")
            return

        try:
            backup_index = int(choice) - 1
            if backup_index < 0 or backup_index >= len(backups):
                print("Invalid backup number.")
                return
        except ValueError:
            print("Invalid input.")
            return

        selected_backup = backups[backup_index]
        backup_path = Path(selected_backup['backup_filename'])

        if not backup_path.exists():
            print(f"\n✗ Error: Backup file not found at {backup_path}")
            print("  The backup file may have been moved or deleted.")
            return

        # Final confirmation
        print(f"\n⚠  You are about to restore from: {backup_path.name}")
        print(f"⚠  This will replace the current database!")
        confirm = input("\nType 'RESTORE' to confirm: ").strip()

        if confirm != 'RESTORE':
            print("Restore cancelled.")
            return

        # Create safety backup of current database first
        print("\nCreating safety backup of current database...")
        safety_backup_dir = paths.DATA_DIR / 'backups' / 'safety'
        safety_backup_dir.mkdir(parents=True, exist_ok=True)

        safety_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safety_backup = safety_backup_dir / f'pre_restore_backup_{safety_timestamp}.db'

        db_path = Path(DEFAULT_DB_PATH)
        shutil.copy2(db_path, safety_backup)
        print(f"✓ Safety backup created: {safety_backup}")

        # Perform restore
        print(f"\nRestoring from {backup_path.name}...")
        shutil.copy2(backup_path, db_path)

        print("\n✓ Database restored successfully!")
        print("="*60)
        print(f"Restored from: {backup_path.name}")
        print(f"Safety backup: {safety_backup}")
        print(f"Restored by: {auth.get_username()}")
        print("="*60)
        print("\nIMPORTANT: Please restart the application for changes to take effect.")

        logger.info(f"Database restored from {backup_path} by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error restoring from backup: {e}")
        print(f"\n✗ Error restoring from backup: {e}")
        print("  The database may be in an inconsistent state.")
        print("  Please contact technical support immediately.")


# ============================================================================
# ADVANCED POPULATION REPORTS
# ============================================================================

def advanced_reports_menu(auth):
    """Advanced population reports menu."""
    print("\n--- Advanced Population Reports ---")

    while True:
        print("\n" + "="*60)
        print("       ADVANCED POPULATION REPORTS")
        print("="*60)
        print("1. Population Health Statistics")
        print("2. Vaccination Coverage Report")
        print("3. Appointment Utilization Analysis")
        print("4. Health Condition Prevalence")
        print("0. Return to Main Menu")
        print("="*60)

        choice = input("Enter your choice (0-4): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            population_health_statistics(auth)
        elif choice == '2':
            vaccination_coverage_report(auth)
        elif choice == '3':
            appointment_utilization_analysis(auth)
        elif choice == '4':
            health_condition_prevalence(auth)
        else:
            print("Invalid choice. Please try again.")


def population_health_statistics(auth):
    """Generate population health statistics."""
    print("\n--- Population Health Statistics ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*70)
        print("POPULATION HEALTH STATISTICS REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        # Total students with health records
        cursor.execute("SELECT COUNT(DISTINCT student_id) as count FROM health_records")
        total_students = cursor.fetchone()['count']
        print(f"\nTotal Students with Health Records: {total_students}")

        # Blood type distribution
        cursor.execute("""
            SELECT blood_type, COUNT(*) as count
            FROM health_records
            WHERE blood_type IS NOT NULL AND blood_type != ''
            GROUP BY blood_type
            ORDER BY count DESC
        """)
        blood_types = cursor.fetchall()

        if blood_types:
            print("\nBlood Type Distribution:")
            print(f"{'Blood Type':<15} {'Count':<10} {'Percentage':<10}")
            print("-"*35)
            for bt in blood_types:
                percentage = (bt['count'] / total_students * 100) if total_students > 0 else 0
                print(f"{bt['blood_type']:<15} {bt['count']:<10} {percentage:.1f}%")

        # Students with allergies
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM health_records
            WHERE allergies IS NOT NULL AND allergies != ''
        """)
        with_allergies = cursor.fetchone()['count']
        allergy_percentage = (with_allergies / total_students * 100) if total_students > 0 else 0
        print(f"\nStudents with Documented Allergies: {with_allergies} ({allergy_percentage:.1f}%)")

        # Students with chronic conditions
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM health_records
            WHERE conditions IS NOT NULL AND conditions != ''
        """)
        with_conditions = cursor.fetchone()['count']
        condition_percentage = (with_conditions / total_students * 100) if total_students > 0 else 0
        print(f"Students with Chronic Conditions: {with_conditions} ({condition_percentage:.1f}%)")

        # Students on medications
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM health_records
            WHERE medications IS NOT NULL AND medications != ''
        """)
        on_medications = cursor.fetchone()['count']
        medication_percentage = (on_medications / total_students * 100) if total_students > 0 else 0
        print(f"Students on Current Medications: {on_medications} ({medication_percentage:.1f}%)")

        # Insurance coverage
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM health_records
            WHERE insurance_provider IS NOT NULL AND insurance_provider != ''
        """)
        with_insurance = cursor.fetchone()['count']
        insurance_percentage = (with_insurance / total_students * 100) if total_students > 0 else 0
        print(f"\nStudents with Health Insurance: {with_insurance} ({insurance_percentage:.1f}%)")

        # Emergency contacts
        cursor.execute("SELECT COUNT(DISTINCT student_id) as count FROM emergency_contacts")
        with_contacts = cursor.fetchone()['count']
        contact_percentage = (with_contacts / total_students * 100) if total_students > 0 else 0
        print(f"Students with Emergency Contacts: {with_contacts} ({contact_percentage:.1f}%)")

        # Recent medical activity (last 30 days)
        cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) as count FROM health_appointments
            WHERE date(appointment_date) >= ?
        """, (cutoff,))
        recent_appointments = cursor.fetchone()['count']
        print(f"\nHealth Center Activity (Last 30 Days):")
        print(f"  Appointments Scheduled: {recent_appointments}")

        cursor.execute("""
            SELECT COUNT(*) as count FROM medical_history
            WHERE date(date) >= ?
        """, (cutoff,))
        recent_visits = cursor.fetchone()['count']
        print(f"  Medical Visits Recorded: {recent_visits}")

        print("\n" + "="*70)
        print("End of Population Health Statistics")
        print("="*70)

        conn.close()
        logger.info(f"Population health statistics generated by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error generating population health statistics: {e}")
        print(f"\nError generating statistics: {e}")


def vaccination_coverage_report(auth):
    """Generate vaccination coverage report."""
    print("\n--- Vaccination Coverage Report ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*70)
        print("VACCINATION COVERAGE REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        # Total students with vaccination records
        cursor.execute("SELECT COUNT(DISTINCT student_id) as count FROM vaccinations")
        total_vaccinated = cursor.fetchone()['count']
        print(f"\nTotal Students with Vaccination Records: {total_vaccinated}")

        # Vaccination counts by type
        cursor.execute("""
            SELECT vaccine_name, COUNT(*) as count
            FROM vaccinations
            GROUP BY vaccine_name
            ORDER BY count DESC
        """)
        vaccine_stats = cursor.fetchall()

        if vaccine_stats:
            print("\nVaccination Distribution by Type:")
            print(f"{'Vaccine':<30} {'Doses Administered':<20}")
            print("-"*50)
            for vax in vaccine_stats:
                print(f"{vax['vaccine_name']:<30} {vax['count']:<20}")

        # Vaccination status summary
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM vaccinations
            GROUP BY status
        """)
        status_stats = cursor.fetchall()

        if status_stats:
            print("\nVaccination Status Summary:")
            print(f"{'Status':<20} {'Count':<10}")
            print("-"*30)
            for stat in status_stats:
                print(f"{stat['status']:<20} {stat['count']:<10}")

        # Recent vaccinations (last 90 days)
        cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM vaccinations
            WHERE date(date_administered) >= ?
        """, (cutoff,))
        recent_vax = cursor.fetchone()['count']
        print(f"\nVaccinations in Last 90 Days: {recent_vax}")

        # Upcoming due vaccinations (next 30 days)
        future_cutoff = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM vaccinations
            WHERE next_due_date IS NOT NULL
              AND date(next_due_date) <= ?
              AND date(next_due_date) >= date('now')
        """, (future_cutoff,))
        upcoming_due = cursor.fetchone()['count']
        print(f"Vaccinations Due in Next 30 Days: {upcoming_due}")

        # Provider distribution
        cursor.execute("""
            SELECT provider, COUNT(*) as count
            FROM vaccinations
            WHERE provider IS NOT NULL AND provider != ''
            GROUP BY provider
            ORDER BY count DESC
            LIMIT 5
        """)
        provider_stats = cursor.fetchall()

        if provider_stats:
            print("\nTop 5 Vaccination Providers:")
            print(f"{'Provider':<30} {'Doses':<10}")
            print("-"*40)
            for prov in provider_stats:
                print(f"{prov['provider']:<30} {prov['count']:<10}")

        print("\n" + "="*70)
        print("End of Vaccination Coverage Report")
        print("="*70)

        conn.close()
        logger.info(f"Vaccination coverage report generated by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error generating vaccination coverage report: {e}")
        print(f"\nError generating report: {e}")


def appointment_utilization_analysis(auth):
    """Generate appointment utilization analysis."""
    print("\n--- Appointment Utilization Analysis ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*70)
        print("APPOINTMENT UTILIZATION ANALYSIS")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        # Total appointments
        cursor.execute("SELECT COUNT(*) as count FROM health_appointments")
        total_appointments = cursor.fetchone()['count']
        print(f"\nTotal Appointments: {total_appointments}")

        # Appointments by type
        cursor.execute("""
            SELECT appointment_type, COUNT(*) as count
            FROM health_appointments
            GROUP BY appointment_type
            ORDER BY count DESC
        """)
        type_stats = cursor.fetchall()

        if type_stats:
            print("\nAppointments by Type:")
            print(f"{'Type':<30} {'Count':<10} {'Percentage':<10}")
            print("-"*50)
            for apt_type in type_stats:
                percentage = (apt_type['count'] / total_appointments * 100) if total_appointments > 0 else 0
                print(f"{apt_type['appointment_type']:<30} {apt_type['count']:<10} {percentage:.1f}%")

        # Appointments by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM health_appointments
            GROUP BY status
            ORDER BY count DESC
        """)
        status_stats = cursor.fetchall()

        if status_stats:
            print("\nAppointments by Status:")
            print(f"{'Status':<20} {'Count':<10} {'Percentage':<10}")
            print("-"*40)
            for stat in status_stats:
                percentage = (stat['count'] / total_appointments * 100) if total_appointments > 0 else 0
                print(f"{stat['status']:<20} {stat['count']:<10} {percentage:.1f}%")

        # Monthly appointment trends (last 6 months)
        print("\nMonthly Appointment Trends (Last 6 Months):")
        print(f"{'Month':<15} {'Appointments':<15}")
        print("-"*30)

        for i in range(6):
            month_start = (datetime.now() - timedelta(days=30*(i+1))).strftime('%Y-%m-01')
            month_end = (datetime.now() - timedelta(days=30*i)).strftime('%Y-%m-01')

            cursor.execute("""
                SELECT COUNT(*) as count
                FROM health_appointments
                WHERE date(appointment_date) >= ? AND date(appointment_date) < ?
            """, (month_start, month_end))

            month_count = cursor.fetchone()['count']
            month_name = datetime.strptime(month_start, '%Y-%m-%d').strftime('%B %Y')
            print(f"{month_name:<15} {month_count:<15}")

        # Utilization rate (completed vs scheduled)
        cursor.execute("""
            SELECT
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) as cancelled,
                SUM(CASE WHEN status = 'No-show' THEN 1 ELSE 0 END) as noshow
            FROM health_appointments
        """)
        utilization = cursor.fetchone()

        completed = utilization['completed'] or 0
        cancelled = utilization['cancelled'] or 0
        noshow = utilization['noshow'] or 0

        print("\nUtilization Metrics:")
        print(f"  Completed Appointments: {completed}")
        print(f"  Cancelled Appointments: {cancelled}")
        print(f"  No-shows: {noshow}")

        if total_appointments > 0:
            completion_rate = (completed / total_appointments * 100)
            cancellation_rate = (cancelled / total_appointments * 100)
            noshow_rate = (noshow / total_appointments * 100)
            print(f"\n  Completion Rate: {completion_rate:.1f}%")
            print(f"  Cancellation Rate: {cancellation_rate:.1f}%")
            print(f"  No-show Rate: {noshow_rate:.1f}%")

        # Peak days/times would require more detailed timestamp data
        # This is a simplified version

        print("\n" + "="*70)
        print("End of Appointment Utilization Analysis")
        print("="*70)

        conn.close()
        logger.info(f"Appointment utilization analysis generated by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error generating appointment utilization analysis: {e}")
        print(f"\nError generating analysis: {e}")


def health_condition_prevalence(auth):
    """Generate health condition prevalence report."""
    print("\n--- Health Condition Prevalence ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*70)
        print("HEALTH CONDITION PREVALENCE REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        # Total students
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'student'")
        total_students = cursor.fetchone()['count']
        print(f"\nTotal Student Population: {total_students}")

        # Common allergies analysis
        cursor.execute("""
            SELECT allergies, COUNT(*) as count
            FROM health_records
            WHERE allergies IS NOT NULL AND allergies != ''
            GROUP BY allergies
            ORDER BY count DESC
            LIMIT 10
        """)
        allergy_stats = cursor.fetchall()

        if allergy_stats:
            print("\nTop 10 Documented Allergies:")
            print(f"{'Allergy':<40} {'Count':<10}")
            print("-"*50)
            for allergy in allergy_stats:
                print(f"{allergy['allergies'][:38]:<40} {allergy['count']:<10}")

        # Common medical conditions
        cursor.execute("""
            SELECT conditions, COUNT(*) as count
            FROM health_records
            WHERE conditions IS NOT NULL AND conditions != ''
            GROUP BY conditions
            ORDER BY count DESC
            LIMIT 10
        """)
        condition_stats = cursor.fetchall()

        if condition_stats:
            print("\nTop 10 Documented Medical Conditions:")
            print(f"{'Condition':<40} {'Count':<10}")
            print("-"*50)
            for condition in condition_stats:
                print(f"{condition['conditions'][:38]:<40} {condition['count']:<10}")

        # Common diagnoses from medical history
        cursor.execute("""
            SELECT diagnosis, COUNT(*) as count
            FROM medical_history
            GROUP BY diagnosis
            ORDER BY count DESC
            LIMIT 10
        """)
        diagnosis_stats = cursor.fetchall()

        if diagnosis_stats:
            print("\nTop 10 Medical Diagnoses:")
            print(f"{'Diagnosis':<40} {'Count':<10}")
            print("-"*50)
            for diagnosis in diagnosis_stats:
                print(f"{diagnosis['diagnosis'][:38]:<40} {diagnosis['count']:<10}")

        # Common medications
        cursor.execute("""
            SELECT medications, COUNT(*) as count
            FROM health_records
            WHERE medications IS NOT NULL AND medications != ''
            GROUP BY medications
            ORDER BY count DESC
            LIMIT 10
        """)
        medication_stats = cursor.fetchall()

        if medication_stats:
            print("\nTop 10 Medications:")
            print(f"{'Medication':<40} {'Count':<10}")
            print("-"*50)
            for med in medication_stats:
                print(f"{med['medications'][:38]:<40} {med['count']:<10}")

        # Mental health appointments (indicator of mental health prevalence)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM health_appointments
            WHERE appointment_type = 'Mental Health Consultation'
        """)
        mental_health_appointments = cursor.fetchone()['count']
        print(f"\nMental Health Consultations Scheduled: {mental_health_appointments}")

        print("\nNote: This report shows aggregate data for health planning purposes.")
        print("Individual patient data remains confidential and protected.")

        print("\n" + "="*70)
        print("End of Health Condition Prevalence Report")
        print("="*70)

        conn.close()
        logger.info(f"Health condition prevalence report generated by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error generating health condition prevalence report: {e}")
        print(f"\nError generating report: {e}")