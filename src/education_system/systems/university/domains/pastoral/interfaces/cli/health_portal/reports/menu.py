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
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.reports.appointment_utilisation import appointment_utilization_analysis
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.reports.condition_prevalence import health_condition_prevalence
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.reports.population import population_health_statistics
from education_system.systems.university.domains.pastoral.interfaces.cli.health_portal.reports.vaccination import vaccination_coverage_report

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

                print("\nAppointment Statistics:")
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
