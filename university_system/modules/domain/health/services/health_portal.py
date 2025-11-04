"""
Health portal service module for student health management.
"""

import os
import sys
import logging
from datetime import datetime
from university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH

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
        from university_system.modules.domain.health.portal.health_portal_core import display_health_portal_menu
        display_health_portal_menu(auth)
    except ImportError as e:
        logger.warning(f"Could not import health portal core: {e}")
        # Fallback implementation
        display_basic_health_menu(auth)

def display_basic_health_menu(auth):
    """Basic health portal menu implementation."""
    while True:
        print("\n" + "="*50)
        print("          HEALTH PORTAL SYSTEM")
        print("="*50)
        print("1. View Health Records")
        print("2. Schedule Appointment")
        print("3. Medical History")
        print("4. Emergency Contacts")
        print("5. Health Reports")
        print("6. Vaccination Records")
        print("0. Return to Main Menu")
        print("="*50)

        choice = input("Enter your choice (0-6): ").strip()

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