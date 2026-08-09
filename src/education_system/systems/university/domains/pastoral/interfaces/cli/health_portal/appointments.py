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
            print("\nYou will receive confirmation via email.")
            print("The health center will contact you to confirm your appointment.")

            logger.info(f"Appointment scheduled for {username}: {date} {time} - {appointment_type}")

        except Exception as e:
            logger.error(f"Error scheduling appointment: {e}")
            print(f"\nError scheduling appointment: {e}")
            print("Please try again or contact the health center.")
    else:
        print("Invalid appointment type.")
