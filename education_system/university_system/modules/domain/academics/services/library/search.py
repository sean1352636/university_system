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
from education_system.university_system.utils.logging.log_config import configure_logging

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

def enhanced_search_books():
    """Enhanced book search with multiple filters and smart recommendations"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text("auth.login_required", action=get_text("book.search.title")))
        return

    if not (auth.check_permission('view_books') or auth.check_permission('manage_books')):
        print(get_text("auth.permission_denied", action=get_text("book.search.title")))
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\n" + get_text("book.search.title") + ":")
    print("=" * 20)
    print("1. " + get_text("book.search.quick_search"))
    print("2. " + get_text("book.search.advanced_search"))
    print("3. " + get_text("book.search.barcode_search"))
    print("4. " + get_text("book.search.browse_category"))
    print("5. " + get_text("book.search.browse_level"))
    print("6. " + get_text("book.search.get_recommendations"))
    print("7. " + get_text("common.return_to_menu"))

    choice = input(get_text("common.enter_choice") + " (1-7): ").strip()

    if choice == '7':
        conn.close()
        return

    try:
        if choice == '1':
            # Quick search
            search_term = input(get_text("book.search.enter_search_term") + ": ").strip()

            cursor.execute('''
            SELECT book_id, title, author, category, status, reading_level
            FROM books
            WHERE title LIKE ? OR author LIKE ?
            ORDER BY title
            ''', (f'%{search_term}%', f'%{search_term}%'))

            books = cursor.fetchall()
            search_type = "quick search"

        elif choice == '2':
            # Advanced search
            print("\n" + get_text("book.search.advanced_title") + ":")
            title = input(get_text("book.search.title_contains") + ": ").strip()
            author = input(get_text("book.search.author_contains") + ": ").strip()
            category = input(get_text("book.search.category") + ": ").strip()
            reading_level = input(get_text("book.search.reading_level") + ": ").strip()
            tags = input(get_text("book.search.tags_prompt") + ": ").strip()
            year_from = input(get_text("book.search.year_from") + ": ").strip()
            year_to = input(get_text("book.search.year_to") + ": ").strip()
            status = input(get_text("book.search.status_prompt") + ": ").strip()

            # Build dynamic query
            query = """
            SELECT book_id, title, author, category, status, reading_level, year_published
            FROM books WHERE 1=1
            """
            params = []

            if title:
                query += " AND title LIKE ?"
                params.append(f'%{title}%')

            if author:
                query += " AND author LIKE ?"
                params.append(f'%{author}%')

            if category:
                query += " AND category LIKE ?"
                params.append(f'%{category}%')

            if reading_level:
                query += " AND reading_level = ?"
                params.append(reading_level)

            if tags:
                tag_list = [tag.strip() for tag in tags.split(',')]
                for tag in tag_list:
                    query += " AND tags LIKE ?"
                    params.append(f'%{tag}%')

            if year_from:
                try:
                    query += " AND year_published >= ?"
                    params.append(int(year_from))
                except ValueError:
                    pass

            if year_to:
                try:
                    query += " AND year_published <= ?"
                    params.append(int(year_to))
                except ValueError:
                    pass

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY title"

            cursor.execute(query, tuple(params))
            books = cursor.fetchall()
            search_type = "advanced search"

        elif choice == '3':
            # Barcode/QR search
            code = input(get_text("book.search.enter_barcode") + ": ").strip()

            if code.startswith("LIBRARY_BOOK:"):
                # QR code format
                parts = code.split(":")
                if len(parts) >= 2:
                    book_id = parts[1]
                    cursor.execute('''
                    SELECT book_id, title, author, category, status, reading_level
                    FROM books WHERE book_id = ?
                    ''', (book_id,))
                else:
                    print(get_text("book.search.invalid_qr"))
                    books = []
            else:
                # Barcode
                cursor.execute('''
                SELECT book_id, title, author, category, status, reading_level
                FROM books WHERE barcode = ?
                ''', (code,))

            books = cursor.fetchall()
            search_type = "barcode/QR search"

        elif choice == '4':
            # Browse by category
            cursor.execute('SELECT DISTINCT category FROM books ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]

            if not categories:
                print(get_text("book.search.no_categories"))
                conn.close()
                return

            print("\n" + get_text("book.search.available_categories") + ":")
            for i, cat in enumerate(categories, 1):
                print(f"{i}. {cat}")

            try:
                cat_choice = int(input(get_text("book.search.select_category") + ": ")) - 1
                if 0 <= cat_choice < len(categories):
                    selected_category = categories[cat_choice]

                    cursor.execute('''
                    SELECT book_id, title, author, category, status, reading_level
                    FROM books WHERE category = ?
                    ORDER BY title
                    ''', (selected_category,))

                    books = cursor.fetchall()
                    search_type = f"category: {selected_category}"
                else:
                    print(get_text("book.search.invalid_category"))
                    conn.close()
                    return

            except (ValueError, IndexError):
                print(get_text("book.search.invalid_category"))
                conn.close()
                return

        elif choice == '5':
            # Browse by reading level
            reading_levels = ['Elementary', 'Middle School', 'High School', 'College', 'Unknown']

            print("\n" + get_text("book.search.reading_levels_title") + ":")
            for i, level in enumerate(reading_levels, 1):
                print(f"{i}. {level}")

            try:
                level_choice = int(input(get_text("book.search.select_reading_level") + ": ")) - 1
                if 0 <= level_choice < len(reading_levels):
                    selected_level = reading_levels[level_choice]

                    cursor.execute('''
                    SELECT book_id, title, author, category, status, reading_level
                    FROM books WHERE reading_level = ?
                    ORDER BY title
                    ''', (selected_level,))

                    books = cursor.fetchall()
                    search_type = f"reading level: {selected_level}"
                else:
                    print(get_text("book.search.invalid_level"))
                    conn.close()
                    return

            except (ValueError, IndexError):
                print(get_text("book.search.invalid_level"))
                conn.close()
                return

        elif choice == '6':
            # Get recommendations
            books = get_book_recommendations(get_current_user_id())
            search_type = "recommendations"

        else:
            print(get_text("common.invalid_choice"))
            conn.close()
            return

        # Display results
        if not books:
            print(get_text("book.search.no_results", search_type=search_type))
            conn.close()
            return

        print("\n" + get_text("book.search.results_found", count=len(books), search_type=search_type) + ":")
        print("=" * 100)
        print(f"{get_text('table_headers.id'):<8} {get_text('table_headers.title'):<30} {get_text('table_headers.author'):<20} {get_text('table_headers.category'):<15} {get_text('table_headers.status'):<12} {get_text('table_headers.level'):<10}")
        print("-" * 100)

        for book in books:
            book_id, title, author, category, status = book[:5]
            reading_level = book[5] if len(book) > 5 else 'Unknown'

            # Truncate strings if too long
            title = (title[:27] + '...') if len(title) > 30 else title
            author = (author[:17] + '...') if len(author) > 20 else author
            category = (category[:12] + '...') if len(category) > 15 else category

            print(f"{book_id:<8} {title:<30} {author:<20} {category:<15} {status:<12} {reading_level:<10}")

        print("=" * 100)

        # Additional options
        print("\n" + get_text("book.search.options_title") + ":")
        print("1. " + get_text("book.search.view_details"))
        print("2. " + get_text("book.search.add_to_list"))
        print("3. " + get_text("book.search.reserve_book"))
        print("4. " + get_text("book.search.rate_review"))
        print("5. " + get_text("book.search.return_to_search"))

        action = input(get_text("book.search.choose_action") + ": ").strip()

        if action == '1':
            book_id = input(get_text("book.search.enter_book_id_view") + ": ").strip()
            if book_id:
                enhanced_view_book_details(book_id)
        elif action == '2':
            book_id = input(get_text("book.search.enter_book_id_list") + ": ").strip()
            if book_id:
                add_to_reading_list(book_id)
        elif action == '3':
            book_id = input(get_text("book.search.enter_book_id_reserve") + ": ").strip()
            if book_id:
                reserve_book(book_id)
        elif action == '4':
            book_id = input(get_text("book.search.enter_book_id_review") + ": ").strip()
            if book_id:
                rate_and_review_book(book_id)

    except sqlite3.Error as e:
        print(get_text("book.search.error_searching", error=str(e)))

    conn.close()


def search_books():
    """Search for books (calls enhanced version)"""
    enhanced_search_books()


def advanced_search_interface():
    """Advanced search interface with filters and sorting"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to search.")
        return

    print("\nAdvanced Search Interface:")
    print("=========================")

    # Initialize search criteria
    search_criteria = {
        'title': '',
        'author': '',
        'isbn': '',
        'category': '',
        'reading_level': '',
        'year_from': '',
        'year_to': '',
        'status': '',
        'tags': '',
        'location': ''
    }

    sort_options = ['title', 'author', 'year_published', 'category', 'added_date']
    sort_by = 'title'
    sort_order = 'ASC'

    while True:
        print(f"\nCurrent Search Criteria:")
        print("-" * 30)
        for key, value in search_criteria.items():
            display_value = value if value else "Any"
            print(f"{key.replace('_', ' ').title()}: {display_value}")

        print(f"\nSort by: {sort_by} ({sort_order})")

        print("\nOptions:")
        print("1-10. Set search criteria")
        print("11. Change sort options")
        print("12. Execute search")
        print("13. Clear all criteria")
        print("14. Save search")
        print("15. Return to menu")

        choice = input("Enter your choice: ").strip()

        if choice == '15':
            break
        elif choice == '12':
            # Execute search
            results = execute_advanced_search(search_criteria, sort_by, sort_order)
            display_search_results(results)
        elif choice == '13':
            # Clear criteria
            search_criteria = {key: '' for key in search_criteria}
            print("✅ Search criteria cleared.")
        else:
            print("Advanced search feature would allow setting individual criteria.")
            print("Implementation requires building dynamic SQL queries based on criteria.")


def execute_advanced_search(criteria: Dict, sort_by: str, sort_order: str) -> List:
    """Execute advanced search with given criteria"""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()

    # Allowlists for SQL identifiers to prevent injection
    ALLOWED_SORT_COLUMNS = {'title', 'author', 'year_published', 'category', 'added_date', 'book_id', 'status', 'reading_level'}
    ALLOWED_FILTER_COLUMNS = {'title', 'author', 'category', 'location', 'tags', 'isbn', 'reading_level', 'status', 'year_from', 'year_to'}
    ALLOWED_SORT_ORDERS = {'ASC', 'DESC'}

    # Build dynamic query
    query = "SELECT book_id, title, author, category, status, reading_level FROM books WHERE 1=1"
    params = []

    for field, value in criteria.items():
        if value and field in ALLOWED_FILTER_COLUMNS:
            if field in ['year_from']:
                query += " AND year_published >= ?"
                params.append(int(value))
            elif field in ['year_to']:
                query += " AND year_published <= ?"
                params.append(int(value))
            elif field in ['title', 'author', 'category', 'location']:
                query += f" AND {field} LIKE ?"
                params.append(f'%{value}%')
            elif field == 'tags':
                query += " AND tags LIKE ?"
                params.append(f'%{value}%')
            else:
                query += f" AND {field} = ?"
                params.append(value)

    # Validate sort parameters against allowlist
    if sort_by not in ALLOWED_SORT_COLUMNS:
        sort_by = 'title'
    if sort_order.upper() not in ALLOWED_SORT_ORDERS:
        sort_order = 'ASC'
    query += f" ORDER BY {sort_by} {sort_order}"

    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        return results
    except sqlite3.Error as e:
        print(f"Search error: {e}")
        conn.close()
        return []


def display_search_results(results: List):
    """Display search results in formatted table"""
    if not results:
        print("No books found matching your criteria.")
        return

    print(f"\nSearch Results ({len(results)} books found):")
    print("=" * 80)
    print(f"{'ID':<8} {'Title':<25} {'Author':<20} {'Category':<15} {'Status':<10}")
    print("-" * 80)

    for result in results:
        book_id, title, author, category, status, reading_level = result
        title_display = title[:24] if len(title) > 25 else title
        author_display = author[:19] if len(author) > 20 else author
        category_display = category[:14] if len(category) > 15 else category

        print(f"{book_id:<8} {title_display:<25} {author_display:<20} {category_display:<15} {status:<10}")

    print("=" * 80)


def save_search_query(user_id, search_criteria, query_name):
   """Save frequently used search queries"""
   conn = get_db_connection()
   if not conn:
       return False

   cursor = conn.cursor()

   try:
       # Check if table exists, create if not
       cursor.execute('''
       CREATE TABLE IF NOT EXISTS saved_searches (
           search_id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id TEXT NOT NULL,
           query_name TEXT NOT NULL,
           search_criteria TEXT NOT NULL,
           created_date TEXT NOT NULL,
           last_used TEXT,
           use_count INTEGER DEFAULT 0
       )
       ''')

       # Save the search
       cursor.execute('''
       INSERT INTO saved_searches (user_id, query_name, search_criteria, created_date)
       VALUES (?, ?, ?, ?)
       ''', (
           user_id,
           query_name,
           json.dumps(search_criteria),
           datetime.now().strftime('%Y-%m-%d %H:%M:%S')
       ))

       conn.commit()
       conn.close()

       print(f"✅ Search query '{query_name}' saved successfully!")
       return True

   except sqlite3.Error as e:
       logging.error(f"Error saving search query: {e}")
       conn.close()
       return False


def load_saved_searches(user_id):
   """Load user's saved search queries"""
   conn = get_db_connection()
   if not conn:
       return []

   cursor = conn.cursor()

   try:
       cursor.execute('''
       SELECT search_id, query_name, search_criteria, created_date, use_count
       FROM saved_searches
       WHERE user_id = ?
       ORDER BY use_count DESC, created_date DESC
       ''', (user_id,))

       saved_searches = cursor.fetchall()

       # Parse JSON criteria
       parsed_searches = []
       for search_id, query_name, criteria_json, created_date, use_count in saved_searches:
           try:
               criteria = json.loads(criteria_json)
               parsed_searches.append({
                   'search_id': search_id,
                   'query_name': query_name,
                   'criteria': criteria,
                   'created_date': created_date,
                   'use_count': use_count
               })
           except json.JSONDecodeError:
               continue

       conn.close()
       return parsed_searches

   except sqlite3.Error as e:
       logging.error(f"Error loading saved searches: {e}")
       conn.close()
       return []


