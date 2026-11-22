"""Health portal CLI workflow extracted from the legacy module."""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from education_system.systems.university.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    get_connection,
)
from education_system import paths
from education_system.systems.university.domains.health.infrastructure.health import (
    export_writer as _exports,
)

logger = logging.getLogger(__name__)

def _student_number(auth, username):
    """The signed-in student's student number (students.student_id) — health
    rows are keyed on it, not on users.id (the other id space)."""
    from education_system.systems.university.domains.health.application.health import access
    user = getattr(auth, "current_user", None)
    who = access.from_user(user if isinstance(user, dict) else None)
    if who is not None and who.student_id:
        return str(who.student_id)
    conn = get_connection()
    try:
        row = conn.execute("SELECT student_id FROM students WHERE student_id = ?",
                           (str(username),)).fetchone()
    finally:
        conn.close()
    return str(row[0]) if row else None


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

def _profile_record(conn, student_id):
    """The student's health profile with the field names these exports have
    always used (``insurance_policy_number``), or None."""
    from education_system.systems.university.domains.health.application.health import profile
    record = profile.get(conn, student_id)
    if record is None:
        return None
    return {"blood_type": record["blood_type"], "allergies": record["allergies"],
            "medications": record["medications"], "conditions": record["conditions"],
            "insurance_provider": record["insurance_provider"],
            "insurance_policy_number": record["insurance_policy"],
            "last_updated": record["last_updated"]}


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

        student_id = _student_number(auth, username)
        if not student_id:
            print("Error: Only a student's own health data can be exported here.")
            conn.close()
            return

        # Select format
        print("\nSelect export format:")
        print("1. CSV")
        print("2. JSON")
        format_choice = input("Enter choice (1-2): ").strip()

        # The health profile is medical_info (application/health/profile);
        # the export keeps its field names.
        record = _profile_record(conn, student_id)
        conn.close()

        if not record:
            print("\nNo health records found to export.")
            return

        # Create exports directory
        # UNIVERSITY_EXPORTS_DIR/health, owner-only (export_writer)
        export_dir = _exports.export_dir()

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

        student_id = _student_number(auth, username)
        if not student_id:
            print("Error: Only a student's own health data can be exported here.")
            conn.close()
            return

        # Query vaccination records
        cursor.execute("""
            SELECT vaccine_name, administered_date AS date_administered, next_due_date,
                   CASE WHEN expiry_date IS NOT NULL AND date(expiry_date) < date('now') THEN 'Expired'
                        WHEN COALESCE(verified, 0) = 1 THEN 'Verified' ELSE 'Unverified' END AS status,
                   administered_by AS provider, lot_number
            FROM vaccination_records
            WHERE student_id = ?
            ORDER BY administered_date DESC
        """, (student_id,))

        vaccinations = cursor.fetchall()
        conn.close()

        if not vaccinations:
            print("\nNo vaccination records found to export.")
            return

        # Create exports directory
        # UNIVERSITY_EXPORTS_DIR/health, owner-only (export_writer)
        export_dir = _exports.export_dir()

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

        student_id = _student_number(auth, username)
        if not student_id:
            print("Error: Only a student's own health data can be exported here.")
            conn.close()
            return

        # Query appointments
        cursor.execute("""
            SELECT appointment_type, appointment_date, appointment_time,
                   status, notes, scheduled_at AS created_at
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
        # UNIVERSITY_EXPORTS_DIR/health, owner-only (export_writer)
        export_dir = _exports.export_dir()

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

        student_id = _student_number(auth, username)
        if not student_id:
            print("Error: Only a student's own health data can be exported here.")
            conn.close()
            return

        # Query emergency contacts
        cursor.execute("""
            SELECT COALESCE(contact_name, name) AS name, relationship,
                   COALESCE(phone_primary, phone) AS phone, email, is_primary
            FROM emergency_contacts
            WHERE student_id = ?
            ORDER BY COALESCE(is_primary, 0) DESC, COALESCE(priority_order, 999), 1
        """, (student_id,))

        contacts = cursor.fetchall()
        conn.close()

        if not contacts:
            print("\nNo emergency contacts found to export.")
            return

        # Create exports directory
        # UNIVERSITY_EXPORTS_DIR/health, owner-only (export_writer)
        export_dir = _exports.export_dir()

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

        student_id = _student_number(auth, username)
        if not student_id:
            print("Error: Only a student's own health data can be exported here.")
            conn.close()
            return

        # Create exports directory
        # UNIVERSITY_EXPORTS_DIR/health, owner-only (export_writer)
        export_dir = _exports.export_dir()

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

            # Health profile (medical_info)
            health_rec = _profile_record(conn, student_id)
            if health_rec:
                health_rec.pop('last_updated', None)
                data['health_records'] = health_rec

            # Vaccinations
            cursor.execute("SELECT * FROM vaccination_records WHERE student_id = ?", (student_id,))
            data['vaccinations'] = [dict(row) for row in cursor.fetchall()]

            # Appointments
            cursor.execute("SELECT * FROM health_appointments WHERE student_id = ?", (student_id,))
            data['appointments'] = [dict(row) for row in cursor.fetchall()]

            # Medical history
            # (diagnoses + health-centre records; there is no medical_history table)
            from education_system.systems.university.domains.health.application.health import medical_history as _medical_history
            data['medical_history'] = _medical_history.history(conn, student_id)

            # Emergency contacts
            cursor.execute("SELECT * FROM emergency_contacts WHERE student_id = ?", (student_id,))
            data['emergency_contacts'] = [dict(row) for row in cursor.fetchall()]

            with open(filename, 'w') as jsonfile:
                json.dump(data, jsonfile, indent=2)

            print(f"\n✓ Complete health data exported to: {filename}")

        elif choice == '2':
            # Medical history only
            filename = export_dir / f'medical_history_{username}_{timestamp}.csv'

            from education_system.systems.university.domains.health.application.health import medical_history as _medical_history
            history = _medical_history.history(conn, student_id)

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

                # Health profile (medical_info)
                health_rec = _profile_record(conn, student_id)
                if health_rec:
                    txtfile.write("HEALTH RECORDS:\n")  # lgtm [py/clear-text-storage-sensitive-data] — authorized health data export
                    txtfile.write(f"  Blood Type: {health_rec['blood_type'] or 'N/A'}\n")
                    txtfile.write(f"  Allergies: {health_rec['allergies'] or 'None'}\n")
                    txtfile.write(f"  Medications: {health_rec['medications'] or 'None'}\n")
                    txtfile.write(f"  Conditions: {health_rec['conditions'] or 'None'}\n")
                    txtfile.write(f"  Insurance: {health_rec['insurance_provider'] or 'N/A'}\n\n")

                # Emergency contacts
                cursor.execute("""
                    SELECT COALESCE(contact_name, name) AS name, relationship,
                           COALESCE(phone_primary, phone) AS phone, email, is_primary
                    FROM emergency_contacts WHERE student_id = ?
                    ORDER BY COALESCE(is_primary, 0) DESC, COALESCE(priority_order, 999), id
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

            # Restrict file permissions — contains sensitive health data
            import os
            try:
                os.chmod(filename, 0o600)
            except OSError:
                pass
            print(f"\nHealth profile exported to: {filename}")
        else:
            print("Invalid choice.")
            conn.close()
            return

        conn.close()
        logger.info(f"Custom dataset exported by {username}")

    except Exception as e:
        logger.error(f"Error exporting custom dataset: {e}")
        print(f"\nError exporting custom dataset: {e}")
