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

            # The health record keys students on their student number
            # (users.student_id) — never the login's users.id.
            cursor.execute("SELECT student_id FROM users WHERE username = ?", (username,))
            user_row = cursor.fetchone()
            student_id = (user_row[0] if user_row else None) or None
            if not student_id:
                print("Error: No student record is linked to your account.")
                conn.close()
                return
            try:
                datetime.strptime(date, '%Y-%m-%d')
                datetime.strptime(time, '%H:%M')
            except ValueError:
                print("Invalid date or time. Use YYYY-MM-DD and HH:MM.")
                conn.close()
                return

            # Same checks as every booking screen (application/health/diary):
            # your other appointments in any clinic, time off, waiting list.
            from education_system.systems.university.domains.health.application.health import (
                diary,
            )
            diary.ensure_schema(conn)
            check = diary.check_booking(conn, student_id=student_id, provider=None,
                                        date=date, time=time)
            if not check.ok:
                print("\n" + check.summary())
                if input("Join the waiting list for this appointment type instead? (y/n): "
                         ).strip().lower() == 'y':
                    diary.join_waitlist(conn, student_id=student_id,
                                        appointment_type=appointment_type,
                                        preferred_from=date, notes=notes, by=username)
                    conn.commit()
                    print("Added to the waiting list; a freed slot will be offered by e-mail.")
                conn.close()
                return

            appointment_id = diary.book(conn, student_id=student_id,
                                        appointment_type=appointment_type, date=date, time=time,
                                        provider=None, reason=notes, status='Pending')
            conn.commit()
            row = conn.execute("SELECT email_address, first_name, last_name FROM students "
                               "WHERE student_id = ?", (student_id,)).fetchone()
            conn.close()
            diary.publish_booking(appointment_id, student_id=student_id, date=date, time=time,
                                  provider=None, appointment_type=appointment_type)
            emailed = False
            if row and row[0]:
                emailed = diary.send_emails([(
                    "health_appointment_confirmation", row[0],
                    {"patient_name": f"{row[1] or ''} {row[2] or ''}".strip() or student_id,
                     "date": date, "appointment_date": date, "time": time,
                     "appointment_time": time, "appointment_type": appointment_type,
                     "practitioner": "To be assigned", "provider": "To be assigned",
                     "department": appointment_type, "location": "University Health Center",
                     "appointment_id": appointment_id})])[0] > 0

            print("\nAppointment successfully scheduled!")
            print("=" * 50)
            print(f"Appointment ID: {appointment_id}")
            print(f"Type: {appointment_type}")
            print(f"Date: {date}")
            print(f"Time: {time}")
            if notes:
                print(f"Notes: {notes}")
            print("Status: Pending")
            print("=" * 50)
            print("\nA confirmation e-mail has been sent." if emailed else
                  "\nNote: the confirmation e-mail could not be sent.")
            print("The health center will contact you to confirm your appointment.")

            logger.info(f"Appointment scheduled for {username}: {date} {time} - {appointment_type}")

        except Exception as e:
            logger.error(f"Error scheduling appointment: {e}")
            print(f"\nError scheduling appointment: {e}")
            print("Please try again or contact the health center.")
    else:
        print("Invalid appointment type.")
