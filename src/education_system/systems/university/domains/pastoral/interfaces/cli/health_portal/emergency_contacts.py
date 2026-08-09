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

def manage_emergency_contacts(auth):
    """Manage emergency contacts."""
    print("\n--- Emergency Contacts ---")
    print("1. View Current Contacts")
    print("2. Add New Contact")
    print("3. Update Contact")
    print("4. Remove Contact")

    choice = input("Select option (1-4): ").strip()

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

        # Create emergency_contacts table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emergency_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                relationship TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                is_primary INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        """)
        conn.commit()

        if choice == '1':
            # View current contacts
            cursor.execute("""
                SELECT id, name, relationship, phone, email, is_primary
                FROM emergency_contacts
                WHERE student_id = ?
                ORDER BY is_primary DESC, name ASC
            """, (student_id,))

            contacts = cursor.fetchall()

            if contacts:
                print("\nYour Emergency Contacts:")
                print("=" * 70)
                for i, contact in enumerate(contacts, 1):
                    primary = " (PRIMARY)" if contact['is_primary'] else ""
                    print(f"\n{i}. {contact['name']} - {contact['relationship']}{primary}")
                    print(f"   Phone: {contact['phone']}")
                    if contact['email']:
                        print(f"   Email: {contact['email']}")
                    print(f"   Contact ID: {contact['id']}")
                print("=" * 70)
                print("\nTo add, update, or remove contacts, select options 2-4.")
            else:
                print("\nNo emergency contacts found.")
                print("Please add at least one emergency contact for your safety.")

        elif choice == '2':
            # Add new contact
            print("\nAdd New Emergency Contact:")
            name = input("Contact name: ").strip()
            relationship = input("Relationship: ").strip()
            phone = input("Phone number: ").strip()
            email = input("Email (optional): ").strip()
            is_primary = input("Set as primary contact? (y/n): ").strip().lower()

            if not name or not relationship or not phone:
                print("Error: Name, relationship, and phone are required.")
                conn.close()
                return

            is_primary_val = 1 if is_primary == 'y' else 0

            # If setting as primary, unset other primary contacts
            if is_primary_val:
                cursor.execute("""
                    UPDATE emergency_contacts
                    SET is_primary = 0
                    WHERE student_id = ?
                """, (student_id,))

            cursor.execute("""
                INSERT INTO emergency_contacts
                (student_id, name, relationship, phone, email, is_primary)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, name, relationship, phone, email or None, is_primary_val))

            conn.commit()
            contact_id = cursor.lastrowid

            print("\nEmergency contact added successfully!")
            print("=" * 50)
            print(f"Contact ID: {contact_id}")
            print(f"Name: {name} ({relationship})")
            print(f"Phone: {phone}")
            if email:
                print(f"Email: {email}")
            if is_primary_val:
                print("Status: PRIMARY CONTACT")
            print("=" * 50)

            logger.info(f"Emergency contact added for {username}: {name}")

        elif choice == '3':
            # Update existing contact
            print("\nUpdate Emergency Contact:")
            contact_id = input("Enter contact ID to update: ").strip()

            # Verify contact exists and belongs to student
            cursor.execute("""
                SELECT id, name, relationship, phone, email, is_primary
                FROM emergency_contacts
                WHERE id = ? AND student_id = ?
            """, (contact_id, student_id))

            existing = cursor.fetchone()

            if not existing:
                print(f"Error: Contact ID {contact_id} not found or doesn't belong to you.")
                conn.close()
                return

            print("\nCurrent contact information:")
            print(f"  Name: {existing['name']}")
            print(f"  Relationship: {existing['relationship']}")
            print(f"  Phone: {existing['phone']}")
            print(f"  Email: {existing['email'] or 'Not set'}")
            print(f"  Primary: {'Yes' if existing['is_primary'] else 'No'}")

            print("\nEnter new information (press Enter to keep current value):")
            name = input(f"Name [{existing['name']}]: ").strip() or existing['name']
            relationship = input(f"Relationship [{existing['relationship']}]: ").strip() or existing['relationship']
            phone = input(f"Phone [{existing['phone']}]: ").strip() or existing['phone']
            email = input(f"Email [{existing['email'] or 'none'}]: ").strip()
            if not email:
                email = existing['email']
            is_primary = input(f"Primary contact? (y/n) [{'y' if existing['is_primary'] else 'n'}]: ").strip().lower()

            if is_primary == 'y':
                is_primary_val = 1
                # Unset other primary contacts
                cursor.execute("""
                    UPDATE emergency_contacts
                    SET is_primary = 0
                    WHERE student_id = ? AND id != ?
                """, (student_id, contact_id))
            elif is_primary == 'n':
                is_primary_val = 0
            else:
                is_primary_val = existing['is_primary']

            cursor.execute("""
                UPDATE emergency_contacts
                SET name = ?, relationship = ?, phone = ?, email = ?, is_primary = ?
                WHERE id = ? AND student_id = ?
            """, (name, relationship, phone, email, is_primary_val, contact_id, student_id))

            conn.commit()

            print(f"\nContact #{contact_id} updated successfully!")
            logger.info(f"Emergency contact updated for {username}: contact {contact_id}")

        elif choice == '4':
            # Remove contact
            print("\nRemove Emergency Contact:")
            contact_id = input("Enter contact ID to remove: ").strip()

            # Verify contact exists and belongs to student
            cursor.execute("""
                SELECT id, name
                FROM emergency_contacts
                WHERE id = ? AND student_id = ?
            """, (contact_id, student_id))

            existing = cursor.fetchone()

            if not existing:
                print(f"Error: Contact ID {contact_id} not found or doesn't belong to you.")
                conn.close()
                return

            confirm = input(f"Are you sure you want to remove '{existing['name']}'? (y/n): ").strip().lower()
            if confirm == 'y':
                cursor.execute("""
                    DELETE FROM emergency_contacts
                    WHERE id = ? AND student_id = ?
                """, (contact_id, student_id))

                conn.commit()
                print(f"\nContact '{existing['name']}' removed successfully!")
                logger.info(f"Emergency contact removed for {username}: {existing['name']}")
            else:
                print("Removal cancelled.")

        else:
            print("Invalid option.")

        conn.close()

    except Exception as e:
        logger.error(f"Error managing emergency contacts: {e}")
        print(f"\nError managing emergency contacts: {e}")
        print("Please try again or contact support.")
