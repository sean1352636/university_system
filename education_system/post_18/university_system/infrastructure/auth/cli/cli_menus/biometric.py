"""Split from cli_menus.py — assembled in package __init__.py."""
from __future__ import annotations

import sys
import json
import logging
import random
import secrets
import string
from pathlib import Path
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    DatabaseError,
)

logger = logging.getLogger("education_system.post_18.university_system.infrastructure.auth.cli.cli_menus")

def _display_biometric_menu(auth):
    """Display biometric authentication sub-menu"""
    while True:
        if not auth.check_session():
            return

        print("\nBiometric Authentication:")
        print("=========================")
        print("1. List Enrollments")
        print("2. Enroll Face")
        print("3. Enroll Fingerprint")
        print("4. Revoke Enrollment")
        print("5. Back")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            enrollments = auth.list_biometric_enrollments()
            if enrollments:
                print("\nBiometric Enrollments:")
                print("=" * 70)
                for e in enrollments:
                    bio_type = e.get('biometric_type', 'Unknown')
                    active = 'Active' if e.get('is_active') else 'Revoked'
                    quality = e.get('quality_score', 'N/A')
                    created = e.get('enrolled_at', 'Unknown')
                    print(f"  #{e.get('id')} - {bio_type} - {active} - Quality: {quality} - Enrolled: {created}")
                print("=" * 70)
            else:
                print("No biometric enrollments found.")

        elif choice == '2':
            print("\nFace Enrollment:")
            print("Note: In a production environment, this would capture a photo via webcam.")
            print("For CLI testing, provide a base64-encoded face template.")
            data = input("Enter face template data (base64): ").strip()
            if data:
                result = auth.enroll_biometric('face', data)
                if result.get('success'):
                    print(f"Face enrolled successfully (ID: {result.get('enrollment_id')})")
                else:
                    print(f"Failed: {result.get('error')}")
            else:
                print("No data provided.")

        elif choice == '3':
            print("\nFingerprint Enrollment:")
            print("Note: Requires a compatible fingerprint reader.")
            data = input("Enter fingerprint template data (base64): ").strip()
            if data:
                result = auth.enroll_biometric('fingerprint', data)
                if result.get('success'):
                    print(f"Fingerprint enrolled successfully (ID: {result.get('enrollment_id')})")
                else:
                    print(f"Failed: {result.get('error')}")
            else:
                print("No data provided.")

        elif choice == '4':
            enrollment_id = input("Enter enrollment ID to revoke: ").strip()
            try:
                confirm = input("Are you sure? (y/n): ").lower()
                if confirm == 'y':
                    result = auth.revoke_biometric_enrollment(int(enrollment_id))
                    if result.get('success'):
                        print("Enrollment revoked.")
                    else:
                        print(f"Failed: {result.get('error')}")
            except ValueError:
                print("Invalid enrollment ID.")

        elif choice == '5':
            return
        else:
            print("Invalid choice.")


# ============================================================================
# Delegated Access Menu
# ============================================================================

