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
