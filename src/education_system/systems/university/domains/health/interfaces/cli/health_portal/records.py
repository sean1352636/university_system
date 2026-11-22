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

def view_health_records(auth):
    """View student health records."""
    print("\n--- Health Records ---")

    from education_system.systems.university.domains.health.application.health import (
        access,
        profile,
    )
    from education_system.systems.university.domains.health.interfaces.cli.health_portal.emergency_contacts import (
        _subject,
    )

    try:
        # Health data is keyed on the student number (a student sees their
        # own; the health team names the student), never users.id. The
        # profile lives in medical_info (application/health/profile).
        who, student_id = _subject(auth)
        if not student_id:
            return
        access.require_view(who, student_id)
        access.record_view(who, "profile", student_id=student_id)
        conn = get_connection()
        cursor = conn.cursor()

        record = profile.get(conn, student_id)

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

            if record['doctor_name'] or record['doctor_phone']:
                print(f"\nDoctor / GP: {record['doctor_name'] or '-'}"
                      f"{'  (' + record['doctor_phone'] + ')' if record['doctor_phone'] else ''}")

            if record['insurance_provider']:
                print("\nInsurance Information:")
                print(f"  Provider: {record['insurance_provider']}")
                if record['insurance_policy']:
                    print(f"  Policy Number: {record['insurance_policy']}")

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

    except PermissionError as e:
        print(f"\n{e}")
    except Exception as e:
        logger.error(f"Error viewing health records: {e}")
        print(f"\nError accessing health records: {e}")
        print("Please contact the health center for assistance.")
