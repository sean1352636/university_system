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

from education_system.systems.university.domains.health.interfaces.cli.health_portal.reports.appointment_utilisation import appointment_utilization_analysis
from education_system.systems.university.domains.health.interfaces.cli.health_portal.reports.condition_prevalence import health_condition_prevalence
from education_system.systems.university.domains.health.interfaces.cli.health_portal.reports.population import population_health_statistics
from education_system.systems.university.domains.health.interfaces.cli.health_portal.reports.vaccination import vaccination_coverage_report

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

        student_id = _student_number(auth, username)
        if not student_id:
            print("Error: These reports are for a student's own health data.")
            conn.close()
            return

        if choice == '1':
            # Immunization Status Report
            print("\n" + "=" * 70)
            print("IMMUNIZATION STATUS REPORT")
            print("=" * 70)
            print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Student: {username}")
            print("-" * 70)

            # Vaccinations live in vaccination_records (keyed on the student
            # number). This used to create and read an empty 'vaccinations'
            # table keyed on users.id, so every report said "none found".
            cursor.execute("""
                SELECT vaccine_name, administered_date AS date_administered, next_due_date,
                       CASE WHEN expiry_date IS NOT NULL AND date(expiry_date) < date('now') THEN 'Expired' WHEN COALESCE(verified, 0) = 1 THEN 'Verified' ELSE 'Unverified' END AS status,
                       administered_by AS provider
                FROM vaccination_records
                WHERE student_id = ?
                ORDER BY administered_date DESC
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

            # The profile is medical_info (application/health/profile); the
            # health_records columns this used to read were never filled.
            from education_system.systems.university.domains.health.application.health import profile as _profile
            health_record = _profile.get(conn, student_id)

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
            from education_system.systems.university.domains.health.application.health import medical_history as _medical_history
            history = _medical_history.history(conn, student_id, limit=5)

            if history:
                print("\nRecent Medical History:")
                for record in history:
                    print(f"  - {record['date']}: {record['diagnosis']}")
                    if record['provider']:
                        print(f"    Provider: {record['provider']}")

            # Get emergency contacts
            cursor.execute("""
                SELECT COALESCE(contact_name, name) AS name, relationship,
                       COALESCE(phone_primary, phone) AS phone
                FROM emergency_contacts
                WHERE student_id = ?
                ORDER BY COALESCE(is_primary, 0) DESC, COALESCE(priority_order, 999), id
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
                       status, notes, scheduled_at AS created_at
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
