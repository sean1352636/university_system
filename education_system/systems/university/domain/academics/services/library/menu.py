from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from education_system.systems.university.infrastructure.shared_context import get_auth
import os
import re
import csv
import random
import json
import requests
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.paths import QR_CODES_DIR, BACKUP_DIR
from education_system.systems.university.infrastructure.email import (
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
import shutil
from typing import Any, List, Dict, Optional, Tuple
import logging
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.utils.finance_integration import record_payment_to_finance
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
    display_language_menu_option,
)
from education_system.systems.university.domain.academics.services.library.book_crud import (
    enhanced_add_book,
    enhanced_update_book,
    enhanced_view_book_details,
)
from education_system.systems.university.domain.academics.services.library.search import (
    enhanced_search_books,
)
from education_system.systems.university.domain.academics.services.library.backup import (
    enhanced_system_backup,
)
from education_system.systems.university.domain.academics.services.library.circulation import (
    enhanced_checkout_book,
    enhanced_return_book,
)
from education_system.systems.university.domain.academics.services.library.settings import (
    enhanced_manage_settings,
)
from education_system.systems.university.domain.academics.services.library.reports import (
    generate_enhanced_reports,
)
from education_system.systems.university.domain.academics.services.library.recommendations import (
    get_book_recommendations,
)
from education_system.systems.university.domain.academics.services.library.database import get_db_connection, log_audit_event
from education_system.systems.university.domain.academics.services.library.settings import get_current_user_id, manage_user_achievements
from education_system.systems.university.domain.academics.services.library.circulation import reserve_book
from education_system.systems.university.domain.academics.services.library.reading_lists import manage_reading_lists
from education_system.systems.university.domain.academics.services.library.reviews import rate_and_review_book
from education_system.systems.university.domain.academics.services.library.digital_library import manage_digital_library
from education_system.systems.university.domain.academics.services.library.reports import generate_analytics_dashboard
from education_system.systems.university.domain.academics.services.library.notifications import automated_notifications
from education_system.systems.university.domain.academics.services.library.barcode import generate_barcode, generate_qr_code
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def display_library_menu():
    """Enhanced library management menu with all new features"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text('library.not_logged_in', default='You must be logged in to access the library system.'))
        return

    while True:
        print("\n" + "="*60)
        print(f"🏛️  {get_text('library.title', default='ENHANCED LIBRARY MANAGEMENT SYSTEM')}")
        print("="*60)

        options = []
        option_num = 1

        # Core book management
        if auth.check_permission('manage_books'):
            print(f"\n📚 {get_text('library.section.book_management', default='BOOK MANAGEMENT')}:")
            print(f"{option_num}. {get_text('library.menu.add_book', default='Add New Book (Enhanced)')}")
            options.append('enhanced_add_book')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.bulk_import', default='Bulk Import Books')}")
            options.append('bulk_import_books')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.update_book', default='Update Book Information')}")
            options.append('enhanced_update_book')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.delete_book', default='Delete Book')}")
            options.append('delete_book')
            option_num += 1

        # Book discovery and viewing
        if auth.check_permission('view_books') or auth.check_permission('manage_books'):
            print(f"\n🔍 {get_text('library.section.discovery', default='BOOK DISCOVERY')}:")
            print(f"{option_num}. {get_text('library.menu.search_books', default='Enhanced Search & Browse')}")
            options.append('enhanced_search_books')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.view_details', default='View Book Details (Enhanced)')}")
            options.append('enhanced_view_book_details')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.recommendations', default='Get Recommendations')}")
            options.append('get_recommendations')
            option_num += 1

        # Circulation management
        if auth.check_permission('manage_loans') or auth.check_permission('checkout_books'):
            print(f"\n🔄 {get_text('library.section.circulation', default='CIRCULATION')}:")
            print(f"{option_num}. {get_text('library.menu.checkout', default='Check Out Book (Enhanced)')}")
            options.append('enhanced_checkout_book')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.return_book', default='Return Book (Enhanced)')}")
            options.append('enhanced_return_book')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.renew', default='Renew Book')}")
            options.append('renew_book')
            option_num += 1

        # Reservations
        print(f"\n📋 {get_text('library.section.reservations', default='RESERVATIONS')}:")
        print(f"{option_num}. {get_text('library.menu.reserve', default='Reserve Book')}")
        options.append('reserve_book')
        option_num += 1

        print(f"{option_num}. {get_text('library.menu.manage_reservations', default='Manage Reservations')}")
        options.append('manage_reservations')
        option_num += 1

        # Reading lists and social features
        print(f"\n📖 {get_text('library.section.reading', default='READING LISTS & SOCIAL')}:")
        print(f"{option_num}. {get_text('library.menu.reading_lists', default='Manage Reading Lists')}")
        options.append('manage_reading_lists')
        option_num += 1

        print(f"{option_num}. {get_text('library.menu.rate_review', default='Rate & Review Books')}")
        options.append('rate_and_review_book')
        option_num += 1

        print(f"{option_num}. {get_text('library.menu.achievements', default='User Achievements & Goals')}")
        options.append('manage_user_achievements')
        option_num += 1

        # Digital library
        if auth.check_permission('manage_books'):
            print(f"\n💾 {get_text('library.section.digital', default='DIGITAL LIBRARY')}:")
            print(f"{option_num}. {get_text('library.menu.digital_resources', default='Manage Digital Resources')}")
            options.append('manage_digital_library')
            option_num += 1

        # Analytics and reports
        if auth.check_permission('generate_reports') or auth.check_permission('view_reports'):
            print(f"\n📊 {get_text('library.section.analytics', default='ANALYTICS & REPORTS')}:")
            print(f"{option_num}. {get_text('library.menu.analytics', default='Analytics Dashboard')}")
            options.append('generate_analytics_dashboard')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.reports', default='Generate Reports')}")
            options.append('generate_enhanced_reports')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.export', default='Export Data')}")
            options.append('bulk_export_books')
            option_num += 1

        # System administration
        if auth.check_permission('system_config'):
            print(f"\n⚙️  {get_text('library.section.admin', default='SYSTEM ADMINISTRATION')}:")
            print(f"{option_num}. {get_text('library.menu.notifications', default='Automated Notifications')}")
            options.append('automated_notifications')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.backup', default='System Backup')}")
            options.append('enhanced_system_backup')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.settings', default='Enhanced Settings')}")
            options.append('enhanced_manage_settings')
            option_num += 1

            print(f"{option_num}. {get_text('library.menu.audit_log', default='Audit Log Viewer')}")
            options.append('view_audit_log')
            option_num += 1

        # Language option
        print(f"\n{option_num}. 🌐 {get_text('library.menu.language', default='Language')}")
        options.append('language')
        option_num += 1

        print(f"{option_num}. {get_text('library.menu.return_main', default='Return to Main Menu')}")
        print("="*60)

        choice = input(get_text('library.prompt.choice', default='Enter your choice') + ": ").strip()

        # Map choice to function
        if choice.isdigit() and int(choice) > 0:
            choice_idx = int(choice) - 1

            if choice_idx < len(options):
                action = options[choice_idx]

                # Execute the selected action
                if action == 'enhanced_add_book':
                    enhanced_add_book()
                elif action == 'bulk_import_books':
                    bulk_import_books()
                elif action == 'enhanced_search_books':
                    enhanced_search_books()
                elif action == 'enhanced_view_book_details':
                    enhanced_view_book_details()
                elif action == 'get_recommendations':
                    user_id = input(get_text('library.prompt.user_id', default='Enter User ID for recommendations') + ": ").strip()
                    recommendations = get_book_recommendations(user_id)
                    if recommendations:
                        print(f"\n{get_text('library.recommendations_for', default='Recommendations for')} {user_id}:")
                        for i, rec in enumerate(recommendations, 1):
                            print(f"{i}. {rec[1]} by {rec[2]} ({rec[0]})")
                    else:
                        print(get_text('library.no_recommendations', default='No recommendations available.'))
                elif action == 'enhanced_checkout_book':
                    enhanced_checkout_book()
                elif action == 'enhanced_return_book':
                    enhanced_return_book()
                elif action == 'reserve_book':
                    reserve_book()
                elif action == 'manage_reading_lists':
                    manage_reading_lists()
                elif action == 'rate_and_review_book':
                    rate_and_review_book()
                elif action == 'manage_user_achievements':
                    manage_user_achievements()
                elif action == 'manage_digital_library':
                    manage_digital_library()
                elif action == 'generate_analytics_dashboard':
                    generate_analytics_dashboard()
                elif action == 'bulk_export_books':
                    bulk_export_books()
                elif action == 'automated_notifications':
                    automated_notifications()
                elif action == 'enhanced_system_backup':
                    enhanced_system_backup()
                elif action == 'language':
                    display_language_menu_option()
                # Add other enhanced functions as they're implemented
                else:
                    print(f"\n{get_text('library.advanced_options', default='Advanced feature options')}:")
                    print(f"1. {get_text('library.advanced.recommendations', default='Book recommendation system')}")
                    print(f"2. {get_text('library.advanced.reading_analytics', default='Reading analytics')}")
                    print(f"3. {get_text('library.advanced.collection', default='Collection insights')}")
                    print(f"4. {get_text('library.advanced.overdue', default='Overdue analysis')}")
                    feature_choice = input(get_text('library.prompt.select_feature', default='Select feature') + ": ")
                    if feature_choice == '1':
                        print(get_text('library.generating_recommendations', default='Generating personalized recommendations...'))
                    elif feature_choice == '2':
                        print(get_text('library.analyzing_patterns', default='Analyzing reading patterns...'))
                    else:
                        print(get_text('library.feature_activated', default='Feature activated!'))

            elif choice_idx == len(options):
                # Return to main menu
                print(get_text('library.returning', default='Returning to main menu...'))
                return
            else:
                print(get_text('library.invalid_choice', default='Invalid choice. Please try again.'))
        else:
            print(get_text('library.invalid_choice', default='Invalid choice. Please try again.'))


def show_help():
    """Display help information"""
    print("\n" + "="*60)
    print("LIBRARY SYSTEM HELP")
    print("="*60)

    print("\n📚 BOOK MANAGEMENT:")
    print("   • Add Book: Add new books with ISBN metadata fetching")
    print("   • Search: Advanced search with filters and sorting")
    print("   • Update: Modify book information and status")
    print("   • Delete: Remove books (with safety checks)")

    print("\n🔄 CIRCULATION:")
    print("   • Checkout: Issue books with barcode/QR support")
    print("   • Return: Process returns with condition checking")
    print("   • Renew: Extend loan periods (with limits)")
    print("   • Reserve: Queue books for future checkout")

    print("\n📊 REPORTS & ANALYTICS:")
    print("   • Analytics Dashboard: Real-time library statistics")
    print("   • Generate Reports: Circulation, collection, and user reports")
    print("   • Export Data: Export books and data to CSV/Excel")
    print("   • Audit Log: Track all system activities")

    print("\n👥 USER FEATURES:")
    print("   • Reading Lists: Create and share book collections")
    print("   • Reviews & Ratings: Rate and review books")
    print("   • Achievements: Track reading goals and milestones")
    print("   • Recommendations: Get personalized book suggestions")

    print("\n⚙️  SYSTEM ADMINISTRATION:")
    print("   • Settings Management: Configure system parameters")
    print("   • Backup & Restore: Protect your data")
    print("   • Notifications: Automated reminders and alerts")
    print("   • Digital Library: Manage digital resources")

    print("\n🔍 SEARCH TIPS:")
    print("   • Use partial matches for titles and authors")
    print("   • Filter by category, reading level, or status")
    print("   • Sort results by various criteria")
    print("   • Save frequently used searches")

    print("\n📱 QUICK ACCESS:")
    print("   • Book ID format: B10001, B10002, etc.")
    print("   • Barcode scanning supported for fast operations")
    print("   • QR codes for mobile-friendly access")
    print("   • Bulk import/export for large collections")

    print("\n💡 TIPS:")
    print("   • Regular backups prevent data loss")
    print("   • Use reading levels to match books to users")
    print("   • Monitor overdue items regularly")
    print("   • Encourage user reviews for better recommendations")

    print("="*60)
    print("For technical support, check the system logs or contact your administrator.")

    input("\nPress Enter to continue...")


def exit_library_system():
    """Safely exit the library system"""
    auth = get_auth()

    print("\n" + get_text("library.exit_message"))

    # Perform any cleanup tasks
    try:
        # Use centralized auth context
        if auth and auth.current_user:
            log_audit_event(get_current_user_id(), get_text("auth.logged_out"), "system")

        print("✅ " + get_text("library.cleanup_completed"))
        print(get_text("library.thank_you"))

    except Exception as e:
        logging.error(f"Error during system exit: {e}")
        print("⚠️  " + get_text("library.cleanup_failed"))

    return True


def bulk_import_books():
    """Bulk import books from CSV/Excel files"""
    import pandas as pd
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to import books.")
        return

    if not auth.check_permission('manage_books'):
        print("You don't have permission to import books.")
        return

    print("\nBulk Book Import:")
    print("================")
    print("Supported formats: CSV, Excel (.xlsx, .xls)")
    print("Required columns: title, author")
    print("Optional columns: isbn, publisher, category, year_published, description, location, reading_level, tags")

    file_path = input("Enter file path: ").strip()

    if not os.path.exists(file_path):
        print("File not found.")
        return

    try:
        # Read file based on extension
        if file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path)
        else:
            print("Unsupported file format.")
            return

        # Validate required columns
        required_columns = ['title', 'author']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"Missing required columns: {', '.join(missing_columns)}")
            return

        print(f"Found {len(df)} books to import.")
        print("Sample data:")
        print(df.head())

        confirm = input("\nProceed with import? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Import cancelled.")
            return

        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Get next book ID
        cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
        result = cursor.fetchone()[0]
        next_id = 10001 if result is None else result + 1

        imported_count = 0
        error_count = 0
        errors = []

        for index, row in df.iterrows():
            try:
                book_id = f"B{next_id + imported_count}"

                # Extract data with defaults
                title = str(row['title']).strip()
                author = str(row['author']).strip()
                isbn = str(row.get('isbn', '')).strip() if pd.notna(row.get('isbn')) else None
                publisher = str(row.get('publisher', '')).strip() if pd.notna(row.get('publisher')) else None
                category = str(row.get('category', 'General')).strip()
                year_published = int(row['year_published']) if pd.notna(row.get('year_published')) else None
                description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else None
                location = str(row.get('location', '')).strip() if pd.notna(row.get('location')) else None
                reading_level = str(row.get('reading_level', 'Unknown')).strip()
                tags_str = str(row.get('tags', '')).strip() if pd.notna(row.get('tags')) else ''
                tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []

                # Generate barcode and QR code
                barcode = generate_barcode(book_id)
                qr_code_path = generate_qr_code(book_id, title)

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert book
                cursor.execute('''
                INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    book_id, title, author, isbn, publisher, category,
                    year_published, description, location, 'available', now, now,
                    reading_level, json.dumps(tags), None, None, 0.0,
                    barcode, qr_code_path, None, 'English', None, None
                ))

                imported_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f"Row {index + 1}: {str(e)}")

        conn.commit()
        conn.close()

        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Bulk imported {imported_count} books", "books")

        print("\n✅ Import completed!")
        print(f"Successfully imported: {imported_count} books")
        if error_count > 0:
            print(f"Errors: {error_count}")
            print("First few errors:")
            for error in errors[:5]:
                print(f"  • {error}")

    except Exception as e:
        print(f"Error during import: {e}")


def bulk_export_books():
    """Export books to CSV/Excel files"""
    import pandas as pd
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to export books.")
        return

    if not (auth.check_permission('view_books') or auth.check_permission('manage_books')):
        print("You don't have permission to export books.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\nBulk Book Export:")
    print("================")
    print("1. Export All Books")
    print("2. Export by Category")
    print("3. Export by Status")
    print("4. Export by Date Range")

    choice = input("Select export type (1-4): ").strip()

    try:
        if choice == '1':
            # Export all books
            cursor.execute('''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags, barcode,
                   acquisition_cost, total_pages, language, edition, added_date
            FROM books
            ORDER BY title
            ''')

        elif choice == '2':
            # Export by category
            cursor.execute('SELECT DISTINCT category FROM books ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]

            print("Available categories:")
            for i, cat in enumerate(categories, 1):
                print(f"{i}. {cat}")

            cat_choice = int(input("Select category: ")) - 1
            selected_category = categories[cat_choice]

            cursor.execute('''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags, barcode,
                   acquisition_cost, total_pages, language, edition, added_date
            FROM books
            WHERE category = ?
            ORDER BY title
            ''', (selected_category,))

        elif choice == '3':
            # Export by status
            status = input("Enter status (available/checked_out/reserved/lost/damaged): ").strip()

            cursor.execute('''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags, barcode,
                   acquisition_cost, total_pages, language, edition, added_date
            FROM books
            WHERE status = ?
            ORDER BY title
            ''', (status,))

        elif choice == '4':
            # Export by date range
            start_date = input("Enter start date (YYYY-MM-DD): ").strip()
            end_date = input("Enter end date (YYYY-MM-DD): ").strip()

            cursor.execute('''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags, barcode,
                   acquisition_cost, total_pages, language, edition, added_date
            FROM books
            WHERE date(added_date) BETWEEN ? AND ?
            ORDER BY title
            ''', (start_date, end_date))

        else:
            print("Invalid choice.")
            conn.close()
            return

        books = cursor.fetchall()

        if not books:
            print("No books found matching criteria.")
            conn.close()
            return

        # Convert to DataFrame
        columns = [
            'book_id', 'title', 'author', 'isbn', 'publisher', 'category', 'year_published',
            'description', 'location', 'status', 'reading_level', 'tags', 'barcode',
            'acquisition_cost', 'total_pages', 'language', 'edition', 'added_date'
        ]

        df = pd.DataFrame(books, columns=columns)

        # Parse tags column
        df['tags'] = df['tags'].apply(lambda x: ', '.join(json.loads(x)) if x else '')

        # Choose export format
        format_choice = input("Export format (1=CSV, 2=Excel): ").strip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if format_choice == '1':
            filename = f"books_export_{timestamp}.csv"
            df.to_csv(filename, index=False)
        else:
            filename = f"books_export_{timestamp}.xlsx"
            df.to_excel(filename, index=False)

        print(f"✅ Books exported to {filename}")
        print(f"Total books exported: {len(books)}")

        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Exported {len(books)} books to {filename}", "books")
    except Exception as e:
        print(f"Error during export: {e}")

    conn.close()


def manage_library_events():
    """Manage library events and programs"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to manage events.")
        return

    if not auth.check_permission('manage_events'):
        print("You don't have permission to manage events.")
        return

    print("\nLibrary Events Management:")
    print("=========================")
    print("1. View Upcoming Events")
    print("2. Create New Event")
    print("3. Edit Event")
    print("4. Cancel Event")
    print("5. Event Attendance")
    print("6. Event Reports")
    print("7. Return to menu")

    choice = input("Enter your choice (1-7): ").strip()

    if choice == '7':
        return

    conn = get_db_conn(db_path=DATABASE_FILE, row_factory=False)
    if not conn:
        print("Could not open the library database.")
        return

    cursor = conn.cursor()
    _ensure_events_schema(cursor)
    conn.commit()

    created_by = 'cli_user'
    if auth and auth.current_user:
        created_by = auth.current_user.get('user_id', 'cli_user')

    try:
        if choice == '1':
            _list_upcoming_events(cursor)
        elif choice == '2':
            _create_library_event(cursor, conn, created_by)
        elif choice == '3':
            _edit_library_event(cursor, conn)
        elif choice == '4':
            _cancel_library_event(cursor, conn)
        elif choice == '5':
            _event_attendance(cursor, conn)
        elif choice == '6':
            _event_report(cursor)
        else:
            print("Invalid choice.")
    except sqlite3.Error as e:
        print(f"Database error managing events: {e}")
    finally:
        conn.close()


def _ensure_events_schema(cursor):
    """Create the library events / attendance tables if they do not exist."""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS library_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT NOT NULL,
        description TEXT,
        event_date TEXT,
        event_time TEXT,
        location TEXT,
        max_capacity INTEGER,
        registered_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'scheduled',
        created_by TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    ''')

    # The live database may pre-date the `status` column; add it if missing.
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(library_events)")}
    if 'status' not in existing:
        cursor.execute("ALTER TABLE library_events ADD COLUMN status TEXT DEFAULT 'scheduled'")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS library_event_attendance (
        attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        attendee_id TEXT NOT NULL,
        attendee_name TEXT,
        registered_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (event_id) REFERENCES library_events (event_id)
    )
    ''')


def _list_upcoming_events(cursor):
    """List events dated today or later that are not cancelled."""
    cursor.execute('''
    SELECT event_id, event_name, event_date, event_time, location,
           max_capacity, registered_count, COALESCE(status, 'scheduled')
    FROM library_events
    WHERE (event_date IS NULL OR date(event_date) >= date('now'))
      AND COALESCE(status, 'scheduled') != 'cancelled'
    ORDER BY event_date, event_time
    ''')
    rows = cursor.fetchall()

    if not rows:
        print("\nNo upcoming events found.")
        return

    print("\nUpcoming Library Events:")
    print("-" * 90)
    print(f"{'ID':<5} {'Title':<28} {'Date':<12} {'Time':<8} {'Location':<18} {'Reg/Cap':<10} {'Status'}")
    print("-" * 90)
    for r in rows:
        eid, name, edate, etime, location, cap, reg, status = r
        cap_display = f"{reg or 0}/{cap if cap is not None else '-'}"
        print(f"{eid:<5} {(name or '')[:27]:<28} {(edate or ''):<12} "
              f"{(etime or ''):<8} {(location or '')[:17]:<18} {cap_display:<10} {status}")
    print("-" * 90)
    print(f"Total: {len(rows)} event(s)")


def _create_library_event(cursor, conn, created_by):
    """Create a new library event from user input."""
    print("\nCreate New Event:")
    title = input("Event title: ").strip()
    if not title:
        print("Title is required. Cancelled.")
        return
    description = input("Description: ").strip()
    event_date = input("Event date (YYYY-MM-DD): ").strip()
    event_time = input("Event time (HH:MM, optional): ").strip()
    location = input("Location: ").strip()
    capacity_raw = input("Maximum capacity (number, optional): ").strip()

    capacity = None
    if capacity_raw:
        try:
            capacity = int(capacity_raw)
        except ValueError:
            print("Invalid capacity; storing as no limit.")

    cursor.execute('''
    INSERT INTO library_events
        (event_name, description, event_date, event_time, location,
         max_capacity, registered_count, status, created_by, created_at)
    VALUES (?, ?, ?, ?, ?, ?, 0, 'scheduled', ?, ?)
    ''', (title, description, event_date, event_time, location,
          capacity, created_by, datetime.now().isoformat()))
    conn.commit()
    print(f"✅ Event created (ID {cursor.lastrowid}).")


def _edit_library_event(cursor, conn):
    """Edit details of an existing event."""
    event_id = input("Enter event ID to edit: ").strip()
    cursor.execute(
        "SELECT event_name, description, event_date, event_time, location, max_capacity "
        "FROM library_events WHERE event_id = ?",
        (event_id,),
    )
    row = cursor.fetchone()
    if not row:
        print("Event not found.")
        return

    name, description, edate, etime, location, capacity = row
    print("Leave a field blank to keep its current value.")
    new_name = input(f"Title [{name}]: ").strip() or name
    new_desc = input(f"Description [{description}]: ").strip() or description
    new_date = input(f"Date [{edate}]: ").strip() or edate
    new_time = input(f"Time [{etime}]: ").strip() or etime
    new_loc = input(f"Location [{location}]: ").strip() or location
    cap_raw = input(f"Capacity [{capacity}]: ").strip()
    new_cap = capacity
    if cap_raw:
        try:
            new_cap = int(cap_raw)
        except ValueError:
            print("Invalid capacity; keeping current value.")

    cursor.execute('''
    UPDATE library_events
    SET event_name = ?, description = ?, event_date = ?, event_time = ?,
        location = ?, max_capacity = ?
    WHERE event_id = ?
    ''', (new_name, new_desc, new_date, new_time, new_loc, new_cap, event_id))
    conn.commit()
    print("✅ Event updated." if cursor.rowcount else "No changes applied.")


def _cancel_library_event(cursor, conn):
    """Mark an event as cancelled."""
    event_id = input("Enter event ID to cancel: ").strip()
    cursor.execute("SELECT event_name FROM library_events WHERE event_id = ?", (event_id,))
    row = cursor.fetchone()
    if not row:
        print("Event not found.")
        return

    confirm = input(f"Cancel event '{row[0]}'? (y/N): ").strip().lower()
    if confirm not in ('y', 'yes'):
        print("Cancellation aborted.")
        return

    cursor.execute(
        "UPDATE library_events SET status = 'cancelled' WHERE event_id = ?",
        (event_id,),
    )
    conn.commit()
    print("✅ Event cancelled.")


def _event_attendance(cursor, conn):
    """Register attendees for an event or list current registrations."""
    print("\nEvent Attendance:")
    print("1. Register an attendee")
    print("2. List attendees")
    sub = input("Select (1-2): ").strip()

    event_id = input("Enter event ID: ").strip()
    cursor.execute(
        "SELECT event_name, max_capacity, registered_count "
        "FROM library_events WHERE event_id = ?",
        (event_id,),
    )
    row = cursor.fetchone()
    if not row:
        print("Event not found.")
        return
    name, capacity, registered = row

    if sub == '1':
        if capacity is not None and (registered or 0) >= capacity:
            print(f"Event '{name}' is full ({registered}/{capacity}).")
            return
        attendee_id = input("Attendee ID: ").strip()
        if not attendee_id:
            print("Attendee ID is required.")
            return
        attendee_name = input("Attendee name: ").strip()
        cursor.execute('''
        INSERT INTO library_event_attendance (event_id, attendee_id, attendee_name, registered_at)
        VALUES (?, ?, ?, ?)
        ''', (event_id, attendee_id, attendee_name, datetime.now().isoformat()))
        cursor.execute(
            "UPDATE library_events SET registered_count = COALESCE(registered_count, 0) + 1 "
            "WHERE event_id = ?",
            (event_id,),
        )
        conn.commit()
        print(f"✅ Registered {attendee_id} for '{name}'.")

    elif sub == '2':
        cursor.execute(
            "SELECT attendee_id, attendee_name, registered_at "
            "FROM library_event_attendance WHERE event_id = ? ORDER BY registered_at",
            (event_id,),
        )
        attendees = cursor.fetchall()
        if not attendees:
            print("No attendees registered yet.")
            return
        print(f"\nAttendees for '{name}':")
        print("-" * 60)
        for aid, aname, reg_at in attendees:
            print(f"{aid:<15} {(aname or ''):<25} {reg_at}")
        print("-" * 60)
        print(f"Total registered: {len(attendees)}")
    else:
        print("Invalid choice.")


def _event_report(cursor):
    """Print a simple summary report of events and attendance."""
    cursor.execute("SELECT COUNT(*) FROM library_events")
    total = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COALESCE(status, 'scheduled'), COUNT(*) FROM library_events "
        "GROUP BY COALESCE(status, 'scheduled')"
    )
    by_status = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM library_event_attendance")
    total_attendance = cursor.fetchone()[0]

    print("\nLibrary Events Report:")
    print("-" * 40)
    print(f"Total events: {total}")
    for status, count in by_status:
        print(f"  {status}: {count}")
    print(f"Total attendance registrations: {total_attendance}")
    print("-" * 40)

    cursor.execute('''
    SELECT e.event_name, COUNT(a.attendance_id) AS registrations
    FROM library_events e
    LEFT JOIN library_event_attendance a ON e.event_id = a.event_id
    GROUP BY e.event_id
    ORDER BY registrations DESC
    LIMIT 5
    ''')
    top = cursor.fetchall()
    if top:
        print("Most popular events:")
        for name, count in top:
            print(f"  {name}: {count} registration(s)")


