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

def _display_webauthn_menu(auth):
    """Display WebAuthn/FIDO2 security key sub-menu"""
    while True:
        if not auth.check_session():
            return

        print("\nSecurity Keys (WebAuthn/FIDO2):")
        print("===============================")
        print("1. List Registered Keys")
        print("2. Register New Key")
        print("3. Remove Key")
        print("4. Rename Key")
        print("5. Back")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            keys = auth.list_webauthn_keys()
            if keys:
                print("\nRegistered Security Keys:")
                print("=" * 70)
                for key in keys:
                    name = key.get('credential_name', 'Unnamed')
                    cred_id = key.get('credential_id', '')[:16] + '...'
                    created = key.get('created_at', 'Unknown')
                    active = 'Active' if key.get('is_active') else 'Inactive'
                    print(f"  {name} (ID: {cred_id}) - {active} - Registered: {created}")
                print("=" * 70)
            else:
                print("No security keys registered.")

        elif choice == '2':
            name = input("Key name (e.g., 'My YubiKey'): ").strip()
            result = auth.register_webauthn_key(name or None)
            if result.get('success'):
                print(f"\nRegistration challenge created (session: {result.get('session_id', '')[:8]}...)")
                print("Complete registration using your security key device.")
                print("Note: Full WebAuthn registration requires a browser or compatible client.")
            else:
                print(f"Failed: {result.get('error')}")

        elif choice == '3':
            cred_id = input("Enter credential ID to remove: ").strip()
            if cred_id:
                confirm = input("Are you sure? (y/n): ").lower()
                if confirm == 'y':
                    result = auth.remove_webauthn_key(cred_id)
                    if result.get('success'):
                        print("Key removed.")
                    else:
                        print(f"Failed: {result.get('error')}")

        elif choice == '4':
            cred_id = input("Enter credential ID to rename: ").strip()
            new_name = input("New name: ").strip()
            if cred_id and new_name:
                result = auth.rename_webauthn_key(cred_id, new_name)
                if result.get('success'):
                    print("Key renamed.")
                else:
                    print(f"Failed: {result.get('error')}")

        elif choice == '5':
            return
        else:
            print("Invalid choice.")


# ============================================================================
# Biometric Menu
# ============================================================================

