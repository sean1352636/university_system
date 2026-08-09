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
            print("\nVaccination Summary:")
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
