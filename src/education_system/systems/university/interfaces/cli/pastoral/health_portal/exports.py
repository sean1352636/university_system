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

logger = logging.getLogger(__name__)

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
        export_dir = paths.UNIVERSITY_DATA_DIR / 'exports' / 'health'
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
        export_dir = paths.UNIVERSITY_DATA_DIR / 'exports' / 'health'
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
        export_dir = paths.UNIVERSITY_DATA_DIR / 'exports' / 'health'
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
        export_dir = paths.UNIVERSITY_DATA_DIR / 'exports' / 'health'
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
        export_dir = paths.UNIVERSITY_DATA_DIR / 'exports' / 'health'
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
                    txtfile.write("HEALTH RECORDS:\n")  # lgtm [py/clear-text-storage-sensitive-data] — authorized health data export
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
