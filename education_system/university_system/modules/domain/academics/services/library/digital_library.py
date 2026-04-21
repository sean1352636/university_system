from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from education_system.university_system.infrastructure.shared_context import get_auth
import os
import re
import csv
import pandas as pd
import random
import json
import qrcode
import requests
from datetime import datetime, timedelta
from education_system.university_system.modules.shared.constants.paths import QR_CODES_DIR, BACKUP_DIR
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from education_system.university_system.infrastructure.email import (
    send_book_checkout_confirmation,
    send_book_return_reminder,
    send_overdue_notification,
)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import uuid
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns
import shutil
from typing import Any, List, Dict, Optional, Tuple
import logging
from education_system.university_system.infrastructure.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def manage_digital_library():
    """Manage digital books and resources"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to manage digital library.")
        return

    if not auth.check_permission('manage_books'):
        print("You don't have permission to manage digital library.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    while True:
        print("\nDigital Library Management:")
        print("==========================")
        print("1. View Digital Collection")
        print("2. Add Digital Resource")
        print("3. Link Digital Copy to Physical Book")
        print("4. Download Statistics")
        print("5. Manage Access Levels")
        print("6. Return to menu")

        choice = input("Enter your choice (1-6): ").strip()

        if choice == '6':
            break

        try:
            if choice == '1':
                # View digital collection
                cursor.execute('''
                SELECT digital_id, title, author, file_type, access_level,
                       download_count, added_date
                FROM digital_library
                ORDER BY title
                ''')

                digital_items = cursor.fetchall()

                if not digital_items:
                    print("No digital resources found.")
                    continue

                print(f"\nDigital Collection ({len(digital_items)} items):")
                print("-" * 90)
                print(f"{'ID':<4} {'Title':<30} {'Author':<20} {'Type':<8} {'Access':<8} {'Downloads':<10}")
                print("-" * 90)

                for item in digital_items:
                    digital_id, title, author, file_type, access_level, downloads, added_date = item
                    title_display = title[:29] if len(title) > 30 else title
                    author_display = author[:19] if len(author) > 20 else author

                    print(f"{digital_id:<4} {title_display:<30} {author_display:<20} {file_type:<8} {access_level:<8} {downloads:<10}")

                print("-" * 90)

            elif choice == '2':
                # Add digital resource
                title = input("Enter title: ").strip()
                author = input("Enter author: ").strip()
                file_path = input("Enter file path: ").strip()

                if not os.path.exists(file_path):
                    print("File not found.")
                    continue

                file_type = os.path.splitext(file_path)[1][1:].upper()
                file_size = os.path.getsize(file_path)
                category = input("Enter category: ").strip()
                description = input("Enter description: ").strip()

                print("Access levels:")
                print("1. Public")
                print("2. Students Only")
                print("3. Staff Only")
                print("4. Restricted")

                access_choice = input("Select access level (1-4): ").strip()
                access_levels = {'1': 'public', '2': 'students', '3': 'staff', '4': 'restricted'}
                access_level = access_levels.get(access_choice, 'public')

                # Copy file to digital library directory
                digital_dir = "digital_library"
                os.makedirs(digital_dir, exist_ok=True)

                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(file_path)}"
                new_path = os.path.join(digital_dir, filename)
                shutil.copy2(file_path, new_path)

                cursor.execute('''
                INSERT INTO digital_library
                (title, author, file_path, file_type, file_size, category,
                 description, access_level, added_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    title, author, new_path, file_type, file_size, category,
                    description, access_level, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))

                digital_id = cursor.lastrowid
                conn.commit()

                print(f"✅ Digital resource added successfully! (ID: {digital_id})")

            elif choice == '3':
                # Link digital copy to physical book
                book_id = input("Enter physical book ID: ").strip()

                # Check if book exists
                cursor.execute('SELECT title FROM books WHERE book_id = ?', (book_id,))
                book = cursor.fetchone()

                if not book:
                    print("Physical book not found.")
                    continue

                # Show available digital resources
                cursor.execute('SELECT digital_id, title FROM digital_library ORDER BY title')
                digital_items = cursor.fetchall()

                if not digital_items:
                    print("No digital resources available.")
                    continue

                print("Available digital resources:")
                for i, (digital_id, title) in enumerate(digital_items, 1):
                    print(f"{i}. {title} (ID: {digital_id})")

                try:
                    choice_idx = int(input("Select digital resource: ")) - 1
                    selected_digital = digital_items[choice_idx]
                    digital_path = f"digital_id:{selected_digital[0]}"

                    cursor.execute('''
                    UPDATE books SET digital_copy_path = ? WHERE book_id = ?
                    ''', (digital_path, book_id))

                    conn.commit()
                    print(f"✅ Digital copy linked to book {book_id}")

                except (ValueError, IndexError):
                    print("Invalid selection.")

            elif choice == '4':
                # Download statistics
                cursor.execute('''
                SELECT title, author, file_type, download_count
                FROM digital_library
                ORDER BY download_count DESC
                LIMIT 10
                ''')

                stats = cursor.fetchall()

                print("\nTop Downloaded Digital Resources:")
                print("-" * 70)
                print(f"{'Title':<30} {'Author':<20} {'Type':<8} {'Downloads':<10}")
                print("-" * 70)

                for title, author, file_type, downloads in stats:
                    title_display = title[:29] if len(title) > 30 else title
                    author_display = author[:19] if len(author) > 20 else author
                    print(f"{title_display:<30} {author_display:<20} {file_type:<8} {downloads:<10}")

                print("-" * 70)

        except sqlite3.Error as e:
            print(f"Error managing digital library: {e}")

    conn.close()


def download_digital_resource(digital_id, user_id):
   """Handle digital resource downloads"""
   conn = get_db_connection()
   if not conn:
       return False

   cursor = conn.cursor()

   try:
       # Get digital resource info
       cursor.execute('''
       SELECT title, file_path, file_type, access_level, download_count
       FROM digital_library
       WHERE digital_id = ?
       ''', (digital_id,))

       resource = cursor.fetchone()

       if not resource:
           print("Digital resource not found.")
           return False

       title, file_path, file_type, access_level, download_count = resource

       # Check access permissions
       if not check_digital_access_permission(user_id, access_level):
           print("You don't have permission to access this resource.")
           return False

       # Check if file exists
       if not os.path.exists(file_path):
           print("File not found on server.")
           return False

       # Log the download
       log_audit_event(user_id, f"Downloaded digital resource: {digital_id}", "digital_library", str(digital_id))

       # Update download count
       cursor.execute('''
       UPDATE digital_library
       SET download_count = download_count + 1
       WHERE digital_id = ?
       ''', (digital_id,))

       # Record download in analytics
       cursor.execute('''
       INSERT INTO usage_analytics (date, metric_name, metric_value, category, additional_data)
       VALUES (?, 'digital_download', 1, ?, ?)
       ''', (
           datetime.now().strftime('%Y-%m-%d'),
           file_type,
           json.dumps({'digital_id': digital_id, 'user_id': user_id, 'title': title})
       ))

       conn.commit()
       conn.close()

       print(f"✅ Download started: {title}")
       print(f"File location: {file_path}")
       print(f"File type: {file_type}")

       return True

   except sqlite3.Error as e:
       logging.error(f"Error downloading digital resource: {e}")
       conn.close()
       return False


def check_digital_access_permission(user_id, access_level):
   """Check if user has permission to access digital resource"""
   try:
       if access_level == 'public':
           return True

       # Check user type
       conn = get_db_connection()
       cursor = conn.cursor()

       # Check if user is a student
       cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (user_id,))
       is_student = cursor.fetchone() is not None

       # Check if user is staff (would need staff table or auth system integration)
       # For now, assume non-student users are staff
       is_staff = not is_student

       conn.close()

       if access_level == 'students' and is_student:
           return True
       elif access_level == 'staff' and is_staff:
           return True
       elif access_level == 'restricted':
           # Additional permission checks would go here
           return False

       return False

   except Exception as e:
       logging.error(f"Error checking digital access permission: {e}")
       return False


def manage_digital_access_permissions():
   """Manage access permissions for digital resources"""
   auth = get_auth()

   if not auth or not auth.current_user:
       print("You must be logged in to manage digital access.")
       return

   if not auth.check_permission('manage_books'):
       print("You don't have permission to manage digital access.")
       return

   conn = get_db_connection()
   if not conn:
       return

   cursor = conn.cursor()

   while True:
       print("\nDigital Access Management:")
       print("=========================")
       print("1. View resource permissions")
       print("2. Update resource access level")
       print("3. Create access groups")
       print("4. Assign users to groups")
       print("5. View access logs")
       print("6. Return to menu")

       choice = input("Enter your choice (1-6): ").strip()

       if choice == '6':
           break

       try:
           if choice == '1':
               # View resource permissions
               cursor.execute('''
               SELECT digital_id, title, file_type, access_level, download_count
               FROM digital_library
               ORDER BY title
               ''')

               resources = cursor.fetchall()

               print(f"\nDigital Resources ({len(resources)}):")
               print("-" * 80)
               print(f"{'ID':<4} {'Title':<30} {'Type':<8} {'Access':<12} {'Downloads':<10}")
               print("-" * 80)

               for resource in resources:
                   digital_id, title, file_type, access_level, downloads = resource
                   title_display = title[:29] if len(title) > 30 else title
                   print(f"{digital_id:<4} {title_display:<30} {file_type:<8} {access_level:<12} {downloads:<10}")

               print("-" * 80)

           elif choice == '2':
               # Update resource access level
               digital_id = input("Enter Digital Resource ID: ").strip()

               cursor.execute('SELECT title, access_level FROM digital_library WHERE digital_id = ?', (digital_id,))
               resource = cursor.fetchone()

               if not resource:
                   print("Resource not found.")
                   continue

               title, current_access = resource

               print(f"Resource: {title}")
               print(f"Current access level: {current_access}")
               print("\nAccess levels:")
               print("1. public")
               print("2. students")
               print("3. staff")
               print("4. restricted")

               access_levels = ['public', 'students', 'staff', 'restricted']

               try:
                   level_choice = int(input("Select new access level (1-4): ")) - 1
                   new_access = access_levels[level_choice]

                   cursor.execute('''
                   UPDATE digital_library SET access_level = ?
                   WHERE digital_id = ?
                   ''', (new_access, digital_id))

                   conn.commit()

                   log_audit_event(get_current_user_id(),
                                 f"Changed digital resource {digital_id} access from {current_access} to {new_access}",
                                 "digital_library", digital_id)

                   print(f"✅ Access level updated to '{new_access}'")

               except (ValueError, IndexError):
                   print("Invalid selection.")

           elif choice == '3':
               print("Access groups feature would allow creating custom user groups")
               print("with specific permissions for digital resources.")
               print("Implementation requires additional tables and logic.")

           elif choice == '4':
               print("User group assignment feature would allow assigning users")
               print("to access groups for granular permission control.")
               print("Implementation requires user group management system.")

           elif choice == '5':
               # View access logs
               cursor.execute('''
               SELECT al.user_id, al.action, al.timestamp, dl.title
               FROM audit_log al
               LEFT JOIN digital_library dl ON al.record_id = dl.digital_id
               WHERE al.table_affected = 'digital_library'
               AND al.action LIKE '%download%'
               ORDER BY al.timestamp DESC
               LIMIT 50
               ''')

               logs = cursor.fetchall()

               if not logs:
                   print("No digital access logs found.")
                   continue

               print(f"\nRecent Digital Access Logs:")
               print("-" * 70)
               print(f"{'User ID':<12} {'Action':<20} {'Resource':<25} {'Timestamp':<15}")
               print("-" * 70)

               for log in logs:
                   user_id, action, timestamp, title = log
                   title_display = title[:24] if title and len(title) > 25 else (title or "Unknown")
                   print(f"{user_id:<12} {action[:19]:<20} {title_display:<25} {timestamp[:16]:<15}")

               print("-" * 70)

       except sqlite3.Error as e:
           print(f"Error managing digital access: {e}")

   conn.close()


