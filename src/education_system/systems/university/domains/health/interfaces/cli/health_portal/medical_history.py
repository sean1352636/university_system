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
    """View medical history (diagnoses and health-centre records)."""
    from education_system.systems.university.domains.health.application.health import (
        access,
        medical_history,
    )
    from education_system.systems.university.domains.health.interfaces.cli.health_portal.emergency_contacts import (
        _subject,
    )
    print("\n--- Medical History ---")

    try:
        who, student_id = _subject(auth)
        if not student_id:
            return
        access.require_view(who, student_id)
        access.record_view(who, "medical_history", student_id=student_id)
        conn = get_connection()
        try:
            history = medical_history.history(conn, student_id)
        finally:
            conn.close()

        if history:
            print("\nMedical History:")
            print("=" * 70)
            for i, record in enumerate(history, 1):
                print(f"\nRecord #{i}")
                print(f"  Date: {record['date'] or 'unknown'}")
                print(f"  Diagnosis: {record['diagnosis']}")
                if record['severity'] or record['status']:
                    print(f"  Severity / status: {record['severity'] or '-'} / "
                          f"{record['status'] or '-'}")
                if record['treatment']:
                    print(f"  Treatment: {record['treatment']}")
                if record['provider']:
                    print(f"  Provider: {record['provider']}")
                if record['notes']:
                    print(f"  Notes: {record['notes']}")
                print("-" * 70)
        else:
            print("\nNo medical history records found in the system.")
            print("Medical history is added as care is received at the health centre.")

        print("\nNote: For complete medical history or to update records,")
        print("please contact the health centre or visit in person.")

    except PermissionError as e:
        print(f"\n{e}")
    except Exception as e:
        logger.error(f"Error viewing medical history: {e}")
        print(f"\nError accessing medical history: {e}")
        print("Please contact the health center for assistance.")
