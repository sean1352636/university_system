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

def _subject(auth):
    """(who, student number) for this session: a student works on their own
    contacts; the health team names the student. The old version keyed
    contacts on users.id (the other id space) under a second layout."""
    from education_system.systems.university.domains.health.application.health import access
    user = getattr(auth, "current_user", None)
    if callable(user):
        user = user()
    who = access.from_user(user if isinstance(user, dict) else None)
    if who is None:
        print("Error: Please sign in first.")
        return None, None
    if who.is_clinician:
        sid = input("Student number: ").strip()
        return (who, sid) if sid else (who, None)
    if who.is_student:
        if who.student_id:
            return who, str(who.student_id)
        conn = get_connection()
        try:
            row = conn.execute("SELECT student_id FROM students WHERE student_id = ?",
                               (who.username,)).fetchone()
        finally:
            conn.close()
        if row:
            return who, str(row[0])
    print("Error: Emergency contacts are for the health team and the student themselves.")
    return who, None


def manage_emergency_contacts(auth):
    """Manage emergency contacts."""
    from education_system.systems.university.domains.health.domain.health.services import (
        contacts as contacts_service,
    )
    print("\n--- Emergency Contacts ---")
    print("1. View Current Contacts")
    print("2. Add New Contact")
    print("3. Update Contact")
    print("4. Remove Contact")

    choice = input("Select option (1-4): ").strip()
    if choice not in ("1", "2", "3", "4"):
        print("Invalid option.")
        return

    try:
        who, student_id = _subject(auth)
        if not student_id:
            return
        username = who.username
        contacts = contacts_service.list_contacts(who, student_id)

        if choice == '1':
            if contacts:
                print("\nEmergency Contacts:")
                print("=" * 70)
                for i, contact in enumerate(contacts, 1):
                    primary = " (PRIMARY)" if contact['is_primary'] else ""
                    print(f"\n{i}. {contact['contact_name']} - {contact['relationship']}{primary}")
                    print(f"   Phone: {contact['phone_primary']}")
                    if contact['phone_secondary']:
                        print(f"   Other phone: {contact['phone_secondary']}")
                    if contact['email']:
                        print(f"   Email: {contact['email']}")
                    print(f"   Contact ID: {contact['id']}")
                print("=" * 70)
                print("\nTo add, update, or remove contacts, select options 2-4.")
            else:
                print("\nNo emergency contacts found.")
                print("Please add at least one emergency contact for your safety.")

        elif choice == '2':
            print("\nAdd New Emergency Contact:")
            data = {
                "contact_name": input("Contact name: ").strip(),
                "relationship": input("Relationship: ").strip(),
                "phone_primary": input("Phone number: ").strip(),
                "phone_secondary": input("Other phone (optional): ").strip() or None,
                "email": input("Email (optional): ").strip() or None,
                "is_primary": input("Set as primary contact? (y/n): ").strip().lower() == 'y',
            }
            if not data["contact_name"] or not data["relationship"] or not data["phone_primary"]:
                print("Error: Name, relationship, and phone are required.")
                return
            contact_id = contacts_service.save_contact(who, student_id, data)

            print("\nEmergency contact added successfully!")
            print("=" * 50)
            print(f"Contact ID: {contact_id}")
            print(f"Name: {data['contact_name']} ({data['relationship']})")
            print(f"Phone: {data['phone_primary']}")
            if data["email"]:
                print(f"Email: {data['email']}")
            if data["is_primary"]:
                print("Status: PRIMARY CONTACT")
            print("=" * 50)
            logger.info("Emergency contact %s added for %s by %s", contact_id, student_id,
                        username)

        elif choice == '3':
            print("\nUpdate Emergency Contact:")
            contact_id = input("Enter contact ID to update: ").strip()
            existing = next((c for c in contacts if str(c['id']) == contact_id), None)
            if not existing:
                print(f"Error: Contact ID {contact_id} not found for student {student_id}.")
                return

            print("\nCurrent contact information:")
            print(f"  Name: {existing['contact_name']}")
            print(f"  Relationship: {existing['relationship']}")
            print(f"  Phone: {existing['phone_primary']}")
            print(f"  Other phone: {existing['phone_secondary'] or 'Not set'}")
            print(f"  Email: {existing['email'] or 'Not set'}")
            print(f"  Primary: {'Yes' if existing['is_primary'] else 'No'}")

            print("\nEnter new information (press Enter to keep current value):")
            data = dict(existing)
            data["contact_name"] = (input(f"Name [{existing['contact_name']}]: ").strip()
                                    or existing['contact_name'])
            data["relationship"] = (input(f"Relationship [{existing['relationship']}]: ").strip()
                                    or existing['relationship'])
            data["phone_primary"] = (input(f"Phone [{existing['phone_primary']}]: ").strip()
                                     or existing['phone_primary'])
            data["phone_secondary"] = (input(f"Other phone [{existing['phone_secondary'] or 'none'}]: ")
                                       .strip() or existing['phone_secondary'])
            data["email"] = (input(f"Email [{existing['email'] or 'none'}]: ").strip()
                             or existing['email'])
            is_primary = input(f"Primary contact? (y/n) [{'y' if existing['is_primary'] else 'n'}]: ").strip().lower()
            if is_primary in ('y', 'n'):
                data["is_primary"] = is_primary == 'y'
            contacts_service.save_contact(who, student_id, data, contact_id=int(contact_id))
            print(f"\nContact #{contact_id} updated successfully!")
            logger.info("Emergency contact %s updated by %s", contact_id, username)

        elif choice == '4':
            print("\nRemove Emergency Contact:")
            contact_id = input("Enter contact ID to remove: ").strip()
            existing = next((c for c in contacts if str(c['id']) == contact_id), None)
            if not existing:
                print(f"Error: Contact ID {contact_id} not found for student {student_id}.")
                return
            confirm = input(f"Are you sure you want to remove '{existing['contact_name']}'? (y/n): ").strip().lower()
            if confirm == 'y':
                contacts_service.delete_contact(who, student_id, int(contact_id))
                print(f"\nContact '{existing['contact_name']}' removed successfully!")
                logger.info("Emergency contact %s removed by %s", contact_id, username)
            else:
                print("Removal cancelled.")

    except (PermissionError, ValueError) as e:
        print(f"\n{e}")
    except Exception as e:
        logger.error(f"Error managing emergency contacts: {e}")
        print(f"\nError managing emergency contacts: {e}")
        print("Please try again or contact support.")
