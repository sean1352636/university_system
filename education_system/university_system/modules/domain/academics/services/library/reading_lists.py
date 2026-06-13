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
from education_system.university_system.core.paths import QR_CODES_DIR, BACKUP_DIR
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
from education_system.university_system.core.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.university_system.core.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def manage_reading_lists():
    """Manage personal and collaborative reading lists"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to manage reading lists.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()
    # FIXED: Use the helper function to get user_id safely
    user_id = get_current_user_id()

    while True:
        print("\nReading Lists Management:")
        print("========================")
        print("1. View My Reading Lists")
        print("2. Create New Reading List")
        print("3. Browse Public Reading Lists")
        print("4. Manage List Items")
        print("5. Share Reading List")
        print("6. Import Reading List")
        print("7. Return to menu")

        choice = input("Enter your choice (1-7): ").strip()

        if choice == '7':
            break

        try:
            if choice == '1':
                # View user's reading lists
                cursor.execute('''
                SELECT rl.list_id, rl.name, rl.description, rl.created_date,
                       rl.is_public, rl.is_collaborative,
                       COUNT(rli.item_id) as item_count
                FROM reading_lists rl
                LEFT JOIN reading_list_items rli ON rl.list_id = rli.list_id
                WHERE rl.creator_id = ?
                GROUP BY rl.list_id
                ORDER BY rl.created_date DESC
                ''', (user_id,))

                lists = cursor.fetchall()

                if not lists:
                    print("You don't have any reading lists yet.")
                    continue

                print(f"\nYour Reading Lists ({len(lists)}):")
                print("-" * 80)
                print(f"{'ID':<4} {'Name':<25} {'Items':<6} {'Type':<15} {'Created':<12}")
                print("-" * 80)

                for lst in lists:
                    list_id, name, desc, created, is_public, is_collab, count = lst
                    list_type = "Public" if is_public else "Private"
                    if is_collab:
                        list_type += " + Collab"

                    print(f"{list_id:<4} {name[:24]:<25} {count:<6} {list_type:<15} {created[:10]:<12}")

                print("-" * 80)

            elif choice == '2':
                # Create new reading list
                name = input("Enter list name: ").strip()
                if not name:
                    print("List name cannot be empty.")
                    continue

                description = input("Enter description (optional): ").strip()

                is_public = input("Make this list public? (y/n): ").strip().lower() == 'y'
                is_collaborative = False

                if is_public:
                    is_collaborative = input("Allow others to add books? (y/n): ").strip().lower() == 'y'

                category = input("Enter category (optional): ").strip()
                reading_level = input("Target reading level (optional): ").strip()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO reading_lists
                (name, description, creator_id, created_date, is_public, is_collaborative, category, target_reading_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, description, user_id, now, is_public, is_collaborative, category, reading_level))

                list_id = cursor.lastrowid
                conn.commit()

                print(f"✅ Reading list '{name}' created successfully! (ID: {list_id})")

            elif choice == '3':
                # Browse public reading lists
                cursor.execute('''
                SELECT rl.list_id, rl.name, rl.description, rl.creator_id,
                       rl.category, rl.target_reading_level,
                       COUNT(rli.item_id) as item_count
                FROM reading_lists rl
                LEFT JOIN reading_list_items rli ON rl.list_id = rli.list_id
                WHERE rl.is_public = 1
                GROUP BY rl.list_id
                ORDER BY item_count DESC, rl.name
                ''', )

                public_lists = cursor.fetchall()

                if not public_lists:
                    print("No public reading lists available.")
                    continue

                print(f"\nPublic Reading Lists ({len(public_lists)}):")
                print("-" * 90)
                print(f"{'ID':<4} {'Name':<25} {'Creator':<12} {'Category':<15} {'Items':<6} {'Level':<12}")
                print("-" * 90)

                for lst in public_lists:
                    list_id, name, desc, creator, category, level, count = lst
                    category = category or "General"
                    level = level or "Any"

                    print(f"{list_id:<4} {name[:24]:<25} {creator[:11]:<12} {category[:14]:<15} {count:<6} {level[:11]:<12}")

                print("-" * 90)

                # Option to view details
                view_id = input("\nEnter list ID to view details (or press Enter): ").strip()
                if view_id:
                    view_reading_list_details(int(view_id))

            elif choice == '4':
                # Manage list items
                manage_reading_list_items(user_id)

            elif choice == '5':
                # Share reading list
                share_reading_list(user_id)

            elif choice == '6':
                # Import reading list
                import_reading_list(user_id)

        except sqlite3.Error as e:
            print(f"Error managing reading lists: {e}")

    conn.close()


def manage_reading_list_items(user_id: str):
    """Manage items within reading lists"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    while True:
        print("\nManage Reading List Items:")
        print("=========================")
        print("1. Add book to list")
        print("2. Remove book from list")
        print("3. Reorder list items")
        print("4. Add notes to book")
        print("5. View list contents")
        print("6. Return to menu")

        choice = input("Enter your choice (1-6): ").strip()

        if choice == '6':
            break

        try:
            if choice == '1':
                # Show user's lists
                cursor.execute('''
                SELECT list_id, name FROM reading_lists
                WHERE creator_id = ? OR is_collaborative = 1
                ORDER BY name
                ''', (user_id,))

                lists = cursor.fetchall()

                if not lists:
                    print("No reading lists available.")
                    continue

                print("Available lists:")
                for i, (list_id, name) in enumerate(lists, 1):
                    print(f"{i}. {name}")

                try:
                    list_choice = int(input("Select list: ")) - 1
                    selected_list_id = lists[list_choice][0]

                    book_id = input("Enter Book ID to add: ").strip()

                    # Check if book exists
                    cursor.execute('SELECT title FROM books WHERE book_id = ?', (book_id,))
                    book = cursor.fetchone()

                    if not book:
                        print("Book not found.")
                        continue

                    # Check if already in list
                    cursor.execute('''
                    SELECT item_id FROM reading_list_items
                    WHERE list_id = ? AND book_id = ?
                    ''', (selected_list_id, book_id))

                    if cursor.fetchone():
                        print("Book already in this list.")
                        continue

                    notes = input("Add notes (optional): ").strip()

                    cursor.execute('''
                    INSERT INTO reading_list_items
                    (list_id, book_id, added_date, added_by, notes)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (selected_list_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, notes))

                    conn.commit()
                    print(f"✅ Book added to list.")

                except (ValueError, IndexError):
                    print("Invalid selection.")

            elif choice == '2':
                # Remove book from list
                cursor.execute('''
                SELECT rl.list_id, rl.name, rli.item_id, b.title
                FROM reading_lists rl
                JOIN reading_list_items rli ON rl.list_id = rli.list_id
                JOIN books b ON rli.book_id = b.book_id
                WHERE rl.creator_id = ? OR rl.is_collaborative = 1
                ORDER BY rl.name, b.title
                ''', (user_id,))

                items = cursor.fetchall()

                if not items:
                    print("No items in your reading lists.")
                    continue

                print("Items in your lists:")
                for i, (list_id, list_name, item_id, book_title) in enumerate(items, 1):
                    print(f"{i}. {book_title} (from {list_name})")

                try:
                    item_choice = int(input("Select item to remove: ")) - 1
                    selected_item_id = items[item_choice][2]

                    cursor.execute('DELETE FROM reading_list_items WHERE item_id = ?', (selected_item_id,))
                    conn.commit()
                    print("✅ Item removed from list.")

                except (ValueError, IndexError):
                    print("Invalid selection.")

            elif choice == '3':
                # Reorder list items
                print("List reordering feature would allow drag-and-drop or number-based reordering.")
                print("Implementation requires updating order_index values.")

            elif choice == '4':
                # Add notes to book
                cursor.execute('''
                SELECT rli.item_id, rl.name, b.title, rli.notes
                FROM reading_list_items rli
                JOIN reading_lists rl ON rli.list_id = rl.list_id
                JOIN books b ON rli.book_id = b.book_id
                WHERE rl.creator_id = ? OR (rl.is_collaborative = 1 AND rli.added_by = ?)
                ''', (user_id, user_id))

                items = cursor.fetchall()

                if not items:
                    print("No items found.")
                    continue

                print("Your reading list items:")
                for i, (item_id, list_name, book_title, current_notes) in enumerate(items, 1):
                    notes_preview = current_notes[:30] + "..." if current_notes and len(current_notes) > 30 else current_notes or "No notes"
                    print(f"{i}. {book_title} - {notes_preview}")

                try:
                    item_choice = int(input("Select item to add notes: ")) - 1
                    selected_item_id = items[item_choice][0]

                    current_notes = items[item_choice][3] or ""
                    print(f"Current notes: {current_notes}")

                    new_notes = input("Enter new notes: ").strip()

                    cursor.execute('''
                    UPDATE reading_list_items SET notes = ? WHERE item_id = ?
                    ''', (new_notes, selected_item_id))

                    conn.commit()
                    print("✅ Notes updated.")

                except (ValueError, IndexError):
                    print("Invalid selection.")

            elif choice == '5':
                # View list contents
                cursor.execute('''
                SELECT list_id, name FROM reading_lists
                WHERE creator_id = ?
                ORDER BY name
                ''', (user_id,))

                lists = cursor.fetchall()

                if not lists:
                    print("No reading lists found.")
                    continue

                print("Your reading lists:")
                for i, (list_id, name) in enumerate(lists, 1):
                    print(f"{i}. {name}")

                try:
                    list_choice = int(input("Select list to view: ")) - 1
                    selected_list_id = lists[list_choice][0]

                    view_reading_list_details(selected_list_id)

                except (ValueError, IndexError):
                    print("Invalid selection.")

        except sqlite3.Error as e:
            print(f"Error managing reading list items: {e}")

    conn.close()


def add_to_reading_list(book_id: str = None):
    """Add a book to a reading list"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to add books to reading lists.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()
    # FIXED: Use the helper function to get user_id safely
    user_id = get_current_user_id()

    try:
        if book_id is None:
            book_id = input("Enter Book ID to add: ").strip()

        # Verify book exists
        cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()

        if not book:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return

        title, author = book

        # Get user's reading lists
        cursor.execute('''
        SELECT list_id, name, description
        FROM reading_lists
        WHERE creator_id = ? OR is_collaborative = 1
        ORDER BY creator_id = ? DESC, name
        ''', (user_id, user_id))

        lists = cursor.fetchall()

        if not lists:
            print("You don't have any reading lists. Create one first.")
            conn.close()
            return

        print(f"\nAdding '{title}' to reading list:")
        print("Available Lists:")
        for i, (list_id, name, desc) in enumerate(lists, 1):
            print(f"{i}. {name} - {desc[:50]}{'...' if len(desc) > 50 else ''}")

        try:
            choice = int(input("Select list number: ")) - 1
            selected_list = lists[choice]
            list_id = selected_list[0]

            # Check if book is already in the list
            cursor.execute('''
            SELECT item_id FROM reading_list_items
            WHERE list_id = ? AND book_id = ?
            ''', (list_id, book_id))

            if cursor.fetchone():
                print("This book is already in the selected list.")
                conn.close()
                return

            # Add book to list
            cursor.execute('''
            INSERT INTO reading_list_items
            (list_id, book_id, added_date, added_by)
            VALUES (?, ?, ?, ?)
            ''', (list_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))

            conn.commit()
            print(f"✅ '{title}' added to reading list '{selected_list[1]}'")

        except (ValueError, IndexError):
            print("Invalid selection.")

    except sqlite3.Error as e:
        print(f"Error adding book to reading list: {e}")

    conn.close()


def view_reading_list_details(list_id: int):
    """View detailed information about a reading list"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        # Get list details
        cursor.execute('''
        SELECT rl.name, rl.description, rl.creator_id, rl.created_date,
               rl.is_public, rl.is_collaborative, rl.category, rl.target_reading_level
        FROM reading_lists rl
        WHERE rl.list_id = ?
        ''', (list_id,))

        list_info = cursor.fetchone()

        if not list_info:
            print("Reading list not found.")
            conn.close()
            return

        name, desc, creator, created, is_public, is_collab, category, level = list_info

        print(f"\n📖 Reading List: {name}")
        print("=" * 60)
        print(f"Created by: {creator}")
        print(f"Created: {created[:10]}")
        print(f"Type: {'Public' if is_public else 'Private'}{' + Collaborative' if is_collab else ''}")
        if category:
            print(f"Category: {category}")
        if level:
            print(f"Target Reading Level: {level}")
        if desc:
            print(f"Description: {desc}")

        # Get list items
        cursor.execute('''
        SELECT b.book_id, b.title, b.author, b.category, b.status,
               rli.added_date, rli.added_by, rli.notes
        FROM reading_list_items rli
        JOIN books b ON rli.book_id = b.book_id
        WHERE rli.list_id = ?
        ORDER BY rli.order_index, rli.added_date
        ''', (list_id,))

        items = cursor.fetchall()

        if not items:
            print("\nThis reading list is empty.")
        else:
            print(f"\nBooks in this list ({len(items)}):")
            print("-" * 80)
            print(f"{'Book ID':<8} {'Title':<30} {'Author':<20} {'Status':<12} {'Added By':<12}")
            print("-" * 80)

            for item in items:
                book_id, title, author, category, status, added_date, added_by, notes = item
                title_display = title[:29] if len(title) > 30 else title
                author_display = author[:19] if len(author) > 20 else author

                print(f"{book_id:<8} {title_display:<30} {author_display:<20} {status:<12} {added_by:<12}")
                if notes:
                    print(f"         Note: {notes}")

        print("=" * 60)

    except sqlite3.Error as e:
        print(f"Error viewing reading list: {e}")

    conn.close()


def share_reading_list(user_id: str):
    """Share a reading list"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        # Get user's reading lists
        cursor.execute('''
        SELECT list_id, name, is_public, is_collaborative
        FROM reading_lists
        WHERE creator_id = ?
        ORDER BY name
        ''', (user_id,))

        lists = cursor.fetchall()

        if not lists:
            print("You don't have any reading lists.")
            conn.close()
            return

        print("Your Reading Lists:")
        for i, (list_id, name, is_public, is_collab) in enumerate(lists, 1):
            status = "Public" if is_public else "Private"
            if is_collab:
                status += " + Collaborative"
            print(f"{i}. {name} ({status})")

        try:
            choice = int(input("Select list to share: ")) - 1
            selected_list = lists[choice]
            list_id, name, current_public, current_collab = selected_list

            print(f"\nSharing options for '{name}':")
            print("1. Make Public")
            print("2. Make Private")
            print("3. Enable Collaboration")
            print("4. Disable Collaboration")
            print("5. Generate Share Link")

            action = input("Choose action (1-5): ").strip()

            if action == '1':
                cursor.execute('''
                UPDATE reading_lists SET is_public = 1 WHERE list_id = ?
                ''', (list_id,))
                print("✅ Reading list is now public!")

            elif action == '2':
                cursor.execute('''
                UPDATE reading_lists SET is_public = 0 WHERE list_id = ?
                ''', (list_id,))
                print("✅ Reading list is now private!")

            elif action == '3':
                cursor.execute('''
                UPDATE reading_lists SET is_collaborative = 1 WHERE list_id = ?
                ''', (list_id,))
                print("✅ Collaboration enabled!")

            elif action == '4':
                cursor.execute('''
                UPDATE reading_lists SET is_collaborative = 0 WHERE list_id = ?
                ''', (list_id,))
                print("✅ Collaboration disabled!")

            elif action == '5':
                share_link = f"library://reading-list/{list_id}"
                print(f"Share link: {share_link}")

            conn.commit()

        except (ValueError, IndexError):
            print("Invalid selection.")

    except sqlite3.Error as e:
        print(f"Error sharing reading list: {e}")

    conn.close()


def import_reading_list(user_id: str):
    """Import a reading list from various sources"""
    print("\nImport Reading List:")
    print("===================")
    print("1. Import from CSV file")
    print("2. Import from share link")
    print("3. Copy public reading list")

    choice = input("Select import method (1-3): ").strip()

    if choice == '1':
        # Import from CSV
        file_path = input("Enter CSV file path: ").strip()

        if not os.path.exists(file_path):
            print("File not found.")
            return

        try:
            df = pd.read_csv(file_path)

            if 'book_id' not in df.columns and 'title' not in df.columns:
                print("CSV must contain either 'book_id' or 'title' column.")
                return

            list_name = input("Enter name for imported list: ").strip()

            conn = get_db_connection()
            cursor = conn.cursor()

            # Create new reading list
            cursor.execute('''
            INSERT INTO reading_lists (name, creator_id, created_date)
            VALUES (?, ?, ?)
            ''', (list_name, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            list_id = cursor.lastrowid
            imported_count = 0

            for _, row in df.iterrows():
                book_id = None

                if 'book_id' in row and pd.notna(row['book_id']):
                    book_id = str(row['book_id']).strip()
                elif 'title' in row and pd.notna(row['title']):
                    title = str(row['title']).strip()
                    author = str(row.get('author', '')).strip() if pd.notna(row.get('author')) else ''

                    # Find book by title and author
                    if author:
                        cursor.execute('''
                        SELECT book_id FROM books
                        WHERE title LIKE ? AND author LIKE ?
                        LIMIT 1
                        ''', (f'%{title}%', f'%{author}%'))
                    else:
                        cursor.execute('''
                        SELECT book_id FROM books WHERE title LIKE ? LIMIT 1
                        ''', (f'%{title}%',))

                    result = cursor.fetchone()
                    if result:
                        book_id = result[0]

                if book_id:
                    # Check if book exists in our library
                    cursor.execute('SELECT book_id FROM books WHERE book_id = ?', (book_id,))
                    if cursor.fetchone():
                        # Add to reading list
                        cursor.execute('''
                        INSERT OR IGNORE INTO reading_list_items
                        (list_id, book_id, added_date, added_by)
                        VALUES (?, ?, ?, ?)
                        ''', (list_id, book_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))

                        imported_count += 1

            conn.commit()
            conn.close()

            print(f"✅ Imported {imported_count} books to reading list '{list_name}'")

        except Exception as e:
            print(f"Error importing reading list: {e}")

    elif choice == '2':
        # Import from share link
        share_link = input("Enter share link: ").strip()

        if share_link.startswith("library://reading-list/"):
            source_list_id = share_link.split("/")[-1]

            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if source list exists and is public
            cursor.execute('''
            SELECT name, is_public FROM reading_lists WHERE list_id = ?
            ''', (source_list_id,))

            source_list = cursor.fetchone()

            if not source_list:
                print("Reading list not found.")
                conn.close()
                return

            if not source_list[1]:
                print("This reading list is not public.")
                conn.close()
                return

            # Copy the list
            new_name = input(f"Name for copied list (original: {source_list[0]}): ").strip() or f"Copy of {source_list[0]}"

            cursor.execute('''
            INSERT INTO reading_lists (name, creator_id, created_date)
            VALUES (?, ?, ?)
            ''', (new_name, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            new_list_id = cursor.lastrowid

            # Copy all items from source list
            cursor.execute('''
            INSERT INTO reading_list_items (list_id, book_id, added_date, added_by, notes)
            SELECT ?, book_id, ?, ?, notes
            FROM reading_list_items
            WHERE list_id = ?
            ''', (new_list_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id, source_list_id))

            conn.commit()
            conn.close()

            print(f"✅ Reading list copied successfully as '{new_name}'")

        else:
            print("Invalid share link format.")


