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
from education_system.systems.university.domain.academics.services.library.database import get_db_connection, log_audit_event
from education_system.systems.university.domain.academics.services.library.settings import get_current_user_id
from education_system.systems.university.domain.academics.services.library.barcode import generate_barcode, generate_qr_code
from education_system.systems.university.domain.academics.services.library.recommendations import get_similar_books
from education_system.systems.university.domain.academics.services.library.circulation import enhanced_checkout_book, reserve_book
from education_system.systems.university.domain.academics.services.library.reviews import rate_and_review_book
from education_system.systems.university.domain.academics.services.library.reading_lists import add_to_reading_list
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def fetch_book_metadata(isbn: str) -> Dict:
    """Fetch book metadata from online sources"""
    try:
        # Try Google Books API
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get('items'):
                book_info = data['items'][0]['volumeInfo']

                metadata = {
                    'title': book_info.get('title', ''),
                    'authors': book_info.get('authors', []),
                    'publisher': book_info.get('publisher', ''),
                    'published_date': book_info.get('publishedDate', ''),
                    'description': book_info.get('description', ''),
                    'page_count': book_info.get('pageCount', 0),
                    'categories': book_info.get('categories', []),
                    'language': book_info.get('language', 'en'),
                    'thumbnail': book_info.get('imageLinks', {}).get('thumbnail', '')
                }

                return metadata
    except Exception as e:
        logging.error(f"Error fetching book metadata: {e}")

    return {}


def assess_reading_level(text: str) -> str:
    """Assess reading level using simple algorithms"""
    try:
        # Simple reading level assessment based on sentence and word complexity
        sentences = text.split('.')
        words = text.split()

        if not sentences or not words:
            return "Unknown"

        avg_sentence_length = len(words) / len(sentences)
        avg_word_length = sum(len(word) for word in words) / len(words)

        # Simple scoring system
        if avg_sentence_length < 10 and avg_word_length < 4:
            return "Elementary"
        elif avg_sentence_length < 15 and avg_word_length < 5:
            return "Middle School"
        elif avg_sentence_length < 20 and avg_word_length < 6:
            return "High School"
        else:
            return "College"

    except Exception as e:
        logging.error(f"Error assessing reading level: {e}")
        return "Unknown"


def enhanced_add_book():
    """Enhanced add book function with metadata fetching and QR code generation"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text("auth.login_required", action=get_text("book.add.title")))
        return

    if not auth.check_permission('manage_books'):
        print(get_text("auth.permission_denied", action=get_text("book.add.title")))
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    # Generate book ID
    cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
    result = cursor.fetchone()[0]
    next_id = 10001 if result is None else result + 1
    book_id = f"B{next_id}"

    print("\n" + get_text("book.add.title"))
    print("=" * 32)

    # Get ISBN first to fetch metadata
    isbn = input(get_text("book.add.enter_isbn") + ": ").strip()
    metadata = {}

    if isbn:
        print(get_text("book.add.fetching_metadata"))
        metadata = fetch_book_metadata(isbn)
        if metadata:
            print("✓ " + get_text("book.add.metadata_fetched"))

    # Title
    while True:
        default_title = metadata.get('title', '')
        title = input(get_text("book.add.enter_title") + (f" [{default_title}]" if default_title else "") + ": ").strip()
        if not title and default_title:
            title = default_title
        if title:
            break
        print(get_text("book.add.error_title_empty"))

    # Author
    while True:
        default_authors = ', '.join(metadata.get('authors', []))
        author = input(get_text("book.add.enter_author") + (f" [{default_authors}]" if default_authors else "") + ": ").strip()
        if not author and default_authors:
            author = default_authors
        if author:
            break
        print(get_text("book.add.error_author_empty"))

    # Publisher
    default_publisher = metadata.get('publisher', '')
    publisher = input(get_text("book.add.enter_publisher") + (f" [{default_publisher}]" if default_publisher else "") + ": ").strip()
    if not publisher and default_publisher:
        publisher = default_publisher

    # Category
    default_categories = metadata.get('categories', [])
    categories = ['Fiction', 'Non-Fiction', 'Science', 'History', 'Computer Science',
                  'Mathematics', 'Philosophy', 'Psychology', 'Business', 'Biography',
                  'Fantasy', 'Mystery', 'Romance', 'Thriller', 'Self-Help', 'Other']

    print("\n" + get_text("book.add.categories_title") + ":")
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")

    while True:
        choice = input(get_text("book.add.enter_category", count=len(categories)) + ": ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(categories):
            category = categories[int(choice) - 1]
            break
        elif choice:
            category = choice
            break
        print(get_text("book.add.error_category"))

    # Year Published
    default_year = metadata.get('published_date', '')[:4] if metadata.get('published_date') else ''
    while True:
        year_str = input(get_text("book.add.enter_year") + (f" [{default_year}]" if default_year else "") + ": ").strip()
        if not year_str and default_year:
            year_published = int(default_year)
            break
        elif not year_str:
            year_published = None
            break

        try:
            year_published = int(year_str)
            current_year = datetime.now().year
            if 1500 <= year_published <= current_year:
                break
            print(get_text("book.add.error_year_range", year=current_year))
        except ValueError:
            print(get_text("book.add.error_year_invalid"))

    # Description
    default_description = metadata.get('description', '')
    description = input(get_text("book.add.enter_description") + (" [auto-filled]" if default_description else "") + ": ").strip()
    if not description and default_description:
        description = default_description

    # Location
    location = input(get_text("book.add.enter_location") + ": ").strip()

    # Additional fields
    edition = input(get_text("book.add.enter_edition") + ": ").strip() or None
    total_pages = metadata.get('page_count', 0) or None
    language = metadata.get('language', 'English')

    # Reading level assessment
    reading_level = "Unknown"
    if description:
        reading_level = assess_reading_level(description)
        print(get_text("book.add.assessed_reading_level", level=reading_level))

    # Tags
    tags_input = input(get_text("book.add.enter_tags") + ": ").strip()
    tags = [tag.strip() for tag in tags_input.split(',')] if tags_input else []

    # Acquisition cost
    while True:
        cost_str = input(get_text("book.add.enter_cost") + ": $").strip()
        if not cost_str:
            acquisition_cost = 0.0
            break
        try:
            acquisition_cost = float(cost_str)
            if acquisition_cost >= 0:
                break
            print(get_text("book.add.error_cost_negative"))
        except ValueError:
            print(get_text("book.add.error_cost_invalid"))

    # Generate barcode and QR code
    barcode = generate_barcode(book_id)
    qr_code_path = generate_qr_code(book_id, title)

    # Status defaults to 'available'
    status = 'available'

    # Timestamps
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        # Insert the book into the database
        cursor.execute('''
        INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            book_id, title, author, isbn, publisher, category,
            year_published, description, location, status, now, now,
            reading_level, json.dumps(tags), None, None, acquisition_cost,
            barcode, qr_code_path, total_pages, language, edition, None
        ))

        conn.commit()

        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Added book: {book_id}", "books", book_id)
        print("\n✓ " + get_text("book.add.success", book_id=book_id))
        print("✓ " + get_text("book.add.barcode_generated", barcode=barcode))
        if qr_code_path:
            print("✓ " + get_text("book.add.qr_saved", path=str(qr_code_path)))

        # Display book details
        print("\n" + get_text("book.add.details_title") + ":")
        print(f"{get_text('book.labels.id')}: {book_id}")
        print(f"{get_text('book.labels.title')}: {title}")
        print(f"{get_text('book.labels.author')}: {author}")
        print(f"{get_text('book.labels.isbn')}: {isbn if isbn else get_text('common.na')}")
        print(f"{get_text('book.labels.category')}: {category}")
        print(f"{get_text('book.labels.level')}: {reading_level}")
        print(f"{get_text('book.labels.tags')}: {', '.join(tags) if tags else get_text('common.none')}")

    except sqlite3.Error as e:
        conn.rollback()
        print(get_text("book.add.error_adding", error=str(e)))
        log_audit_event(get_current_user_id(), get_text("book.add.failed_audit"), success=False)

    conn.close()


def add_book():
    """Add a new book to the library (calls enhanced version)"""
    enhanced_add_book()


def enhanced_update_book(book_id=None):
    """Enhanced update book function with validation and audit logging"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to update books.")
        return

    if not auth.check_permission('manage_books'):
        print("You don't have permission to update books.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        if book_id is None:
            book_id = input("Enter Book ID to update: ").strip()

        # Get current book data
        cursor.execute('SELECT * FROM books WHERE book_id = ?', (book_id,))
        book_data = cursor.fetchone()

        if not book_data:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return

        print(f"\nUpdating book: {book_data[1]} by {book_data[2]}")
        print("Leave fields blank to keep current values.")

        # Current values
        current_title = book_data[1]
        current_author = book_data[2]
        current_isbn = book_data[3]
        current_publisher = book_data[4]
        current_category = book_data[5]
        current_year = book_data[6]
        current_description = book_data[7]
        current_location = book_data[8]
        current_reading_level = book_data[12]

        # Get updates
        title = input(f"Title [{current_title}]: ").strip() or current_title
        author = input(f"Author [{current_author}]: ").strip() or current_author
        isbn = input(f"ISBN [{current_isbn or 'None'}]: ").strip() or current_isbn
        publisher = input(f"Publisher [{current_publisher or 'None'}]: ").strip() or current_publisher
        category = input(f"Category [{current_category}]: ").strip() or current_category

        year_input = input(f"Year [{current_year or 'None'}]: ").strip()
        year_published = int(year_input) if year_input else current_year

        description = input(f"Description [{current_description[:50]}...]: ").strip() or current_description
        location = input(f"Location [{current_location}]: ").strip() or current_location
        reading_level = input(f"Reading Level [{current_reading_level}]: ").strip() or current_reading_level

        # Update book
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE books SET
        title = ?, author = ?, isbn = ?, publisher = ?, category = ?,
        year_published = ?, description = ?, location = ?, reading_level = ?,
        last_updated = ?
        WHERE book_id = ?
        ''', (title, author, isbn, publisher, category, year_published,
              description, location, reading_level, now, book_id))

        conn.commit()

        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Updated book: {book_id}", "books", book_id)

        print(f"✅ Book {book_id} updated successfully!")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error updating book: {e}")

    conn.close()


def update_book():
    """Update book information (calls enhanced version)"""
    enhanced_update_book()


def delete_book():
    """Delete a book from the library"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to delete books.")
        return

    if not auth.check_permission('manage_books'):
        print("You don't have permission to delete books.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        book_id = input("Enter Book ID to delete: ").strip()

        # Check if book exists and get details
        cursor.execute('SELECT title, author, status FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()

        if not book:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return

        title, author, status = book

        # Check for active loans or reservations
        cursor.execute('''
        SELECT COUNT(*) FROM book_loans
        WHERE book_id = ? AND status IN ('active', 'overdue')
        ''', (book_id,))

        active_loans = cursor.fetchone()[0]

        cursor.execute('''
        SELECT COUNT(*) FROM book_reservations
        WHERE book_id = ? AND status = 'active'
        ''', (book_id,))

        active_reservations = cursor.fetchone()[0]

        if active_loans > 0:
            print(f"Cannot delete book: {active_loans} active loan(s)")
            conn.close()
            return

        if active_reservations > 0:
            print(f"Cannot delete book: {active_reservations} active reservation(s)")
            conn.close()
            return

        print(f"\nBook to delete: {title} by {author}")
        print(f"Status: {status}")

        confirm = input("Are you sure you want to delete this book? (type 'DELETE' to confirm): ").strip()

        if confirm != 'DELETE':
            print("Deletion cancelled.")
            conn.close()
            return

        # Delete book and related records
        cursor.execute('DELETE FROM book_reviews WHERE book_id = ?', (book_id,))
        cursor.execute('DELETE FROM book_loans WHERE book_id = ?', (book_id,))
        cursor.execute('DELETE FROM book_reservations WHERE book_id = ?', (book_id,))
        cursor.execute('DELETE FROM reading_list_items WHERE book_id = ?', (book_id,))
        cursor.execute('DELETE FROM books WHERE book_id = ?', (book_id,))

        conn.commit()

        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Deleted book: {book_id} - {title}", "books", book_id)

        print(f"✅ Book {book_id} deleted successfully!")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error deleting book: {e}")

    conn.close()


def enhanced_view_book_details(book_id=None):
    """Enhanced book details view with reviews, recommendations, and analytics"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text("auth.login_required", action=get_text("book.details.title", book_id="")))
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    if book_id is None:
        book_id = input(get_text("book.details.enter_book_id") + ": ").strip()

    try:
        # Get comprehensive book details
        cursor.execute('''
        SELECT b.*,
               COALESCE(AVG(r.rating), 0) as avg_rating,
               COUNT(r.review_id) as review_count,
               COUNT(DISTINCT bl.loan_id) as total_loans
        FROM books b
        LEFT JOIN book_reviews r ON b.book_id = r.book_id AND r.status = 'approved'
        LEFT JOIN book_loans bl ON b.book_id = bl.book_id
        WHERE b.book_id = ?
        GROUP BY b.book_id
        ''', (book_id,))

        book_data = cursor.fetchone()

        if not book_data:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return

        # Parse book data
        book = {
            'book_id': book_data[0],
            'title': book_data[1],
            'author': book_data[2],
            'isbn': book_data[3],
            'publisher': book_data[4],
            'category': book_data[5],
            'year_published': book_data[6],
            'description': book_data[7],
            'location': book_data[8],
            'status': book_data[9],
            'added_date': book_data[10],
            'last_updated': book_data[11],
            'reading_level': book_data[12],
            'tags': json.loads(book_data[13]) if book_data[13] else [],
            'cover_image_path': book_data[14],
            'digital_copy_path': book_data[15],
            'acquisition_cost': book_data[16],
            'barcode': book_data[17],
            'qr_code_path': book_data[18],
            'total_pages': book_data[19],
            'language': book_data[20],
            'edition': book_data[21],
            'condition_notes': book_data[22],
            'avg_rating': round(book_data[23], 1),
            'review_count': book_data[24],
            'total_loans': book_data[25]
        }

        # Display enhanced book details
        print("\n" + "=" * 80)
        print("                    " + get_text("book.details.title", book_id=book['book_id']))
        print("=" * 80)

        print(f"{get_text('book.details.title_label')}: {book['title']}")
        print(f"{get_text('book.details.author_label')}: {book['author']}")
        print(f"{get_text('book.details.category_label')}: {book['category']}")
        print(f"{get_text('book.details.status_label')}: {book['status'].upper()}")

        if book['avg_rating'] > 0:
            stars = "★" * int(book['avg_rating']) + "☆" * (5 - int(book['avg_rating']))
            print(f"{get_text('book.details.rating_label')}: {get_text('book.details.rating_format', stars=stars, rating=book['avg_rating'], count=book['review_count'])}")

        print(f"{get_text('book.details.total_borrowed')}: {book['total_loans']}")

        if book['isbn']:
            print(f"{get_text('book.details.isbn_label')}: {book['isbn']}")
        if book['publisher']:
            print(f"{get_text('book.details.publisher_label')}: {book['publisher']}")
        if book['year_published']:
            print(f"{get_text('book.details.year_label')}: {book['year_published']}")
        if book['edition']:
            print(f"{get_text('book.details.edition_label')}: {book['edition']}")
        if book['total_pages']:
            print(f"{get_text('book.details.pages_label')}: {book['total_pages']}")

        print(f"{get_text('book.details.language_label')}: {book['language']}")
        print(f"{get_text('book.details.reading_level_label')}: {book['reading_level']}")
        print(f"{get_text('book.details.location_label')}: {book['location']}")

        if book['tags']:
            print(f"{get_text('book.details.tags_label')}: {', '.join(book['tags'])}")

        if book['barcode']:
            print(f"{get_text('book.details.barcode_label')}: {book['barcode']}")

        if book['description']:
            print(f"\n{get_text('book.details.description_label')}:")
            print("-" * 40)
            print(book['description'])

        if book['condition_notes']:
            print(f"\n{get_text('book.details.condition_label')}: {book['condition_notes']}")

        print("-" * 80)

        # Show recent reviews
        cursor.execute('''
        SELECT r.rating, r.review_text, r.review_date, r.user_id
        FROM book_reviews r
        WHERE r.book_id = ? AND r.status = 'approved'
        ORDER BY r.review_date DESC
        LIMIT 3
        ''', (book_id,))

        reviews = cursor.fetchall()

        if reviews:
            print("\n" + get_text("book.details.recent_reviews") + ":")
            print("-" * 40)
            for review in reviews:
                rating, text, date, user_id = review
                stars = "★" * rating + "☆" * (5 - rating)
                print(f"{stars} by {user_id} on {date[:10]}")
                if text:
                    print(f"   \"{text[:100]}{'...' if len(text) > 100 else ''}\"")
                print()

        # Show loan history
        cursor.execute('''
        SELECT bl.checkout_date, bl.due_date, bl.return_date, bl.user_id, bl.status
        FROM book_loans bl
        WHERE bl.book_id = ?
        ORDER BY bl.checkout_date DESC
        LIMIT 5
        ''', (book_id,))

        loans = cursor.fetchall()

        if loans:
            print(get_text("book.details.loan_history") + ":")
            print("-" * 60)
            print(f"{get_text('table_headers.user_id'):<12} {get_text('table_headers.checkout'):<12} {get_text('table_headers.due_date'):<12} {get_text('table_headers.returned'):<12} {get_text('table_headers.status'):<10}")
            print("-" * 60)

            for loan in loans:
                checkout, due, returned, user_id, status = loan
                checkout_str = checkout[:10] if checkout else 'N/A'
                due_str = due[:10] if due else 'N/A'
                returned_str = returned[:10] if returned else 'N/A'

                print(f"{user_id:<12} {checkout_str:<12} {due_str:<12} {returned_str:<12} {status:<10}")

        # Show current reservations
        cursor.execute('''
        SELECT user_id, reservation_date, priority_order
        FROM book_reservations
        WHERE book_id = ? AND status = 'active'
        ORDER BY priority_order, reservation_date
        ''', (book_id,))

        reservations = cursor.fetchall()

        if reservations:
            print("\n" + get_text("book.details.current_reservations", count=len(reservations)) + ":")
            print("-" * 40)
            for i, (user_id, res_date, priority) in enumerate(reservations, 1):
                print(f"{i}. {user_id} (reserved {res_date[:10]})")

        # Show similar books
        similar_books = get_similar_books(book_id, book['category'], book['author'])
        if similar_books:
            print(f"\n{get_text('book.details.similar_books')}:")
            print("-" * 40)
            for similar_book in similar_books[:3]:
                print(f"• {similar_book[1]} by {similar_book[2]} ({similar_book[0]})")

        print("="*80)

        # Action options
        if auth.check_permission('manage_books') or auth.check_permission('checkout_books'):
            print("\n" + get_text("book.details.actions_title") + ":")
            actions = []

            if book['status'] == 'available':
                print("1. " + get_text("book.details.checkout_action"))
                actions.append('checkout')

            if book['status'] in ['available', 'checked_out']:
                print(f"{len(actions)+1}. " + get_text("book.details.reserve_action"))
                actions.append('reserve')

            print(f"{len(actions)+1}. " + get_text("book.details.review_action"))
            actions.append('review')

            print(f"{len(actions)+1}. " + get_text("book.details.reading_list_action"))
            actions.append('reading_list')

            if auth.check_permission('manage_books'):
                print(f"{len(actions)+1}. " + get_text("book.details.edit_action"))
                actions.append('edit')

            print(f"{len(actions)+1}. " + get_text("common.return_to_menu"))

            action = input(get_text("book.details.choose_action") + ": ").strip()

            try:
                action_idx = int(action) - 1
                if 0 <= action_idx < len(actions):
                    selected_action = actions[action_idx]

                    if selected_action == 'checkout':
                        enhanced_checkout_book(book_id)
                    elif selected_action == 'reserve':
                        reserve_book(book_id)
                    elif selected_action == 'review':
                        rate_and_review_book(book_id)
                    elif selected_action == 'reading_list':
                        add_to_reading_list(book_id)
                    elif selected_action == 'edit':
                        enhanced_update_book(book_id)
            except ValueError:
                pass

    except sqlite3.Error as e:
        print(f"Error viewing book details: {e}")

    conn.close()


def view_book_details():
    """View detailed information about a specific book"""
    enhanced_view_book_details()


def list_all_books():
    """List all books in the library"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to view books.")
        return

    if not (auth.check_permission('view_books') or auth.check_permission('manage_books')):
        print("You don't have permission to view books.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        cursor.execute('''
        SELECT book_id, title, author, category, status
        FROM books
        ORDER BY title
        ''')

        books = cursor.fetchall()

        if not books:
            print("No books found in the library.")
            return

        print(f"\nAll Books ({len(books)} total):")
        print("=" * 80)
        print(f"{'ID':<8} {'Title':<30} {'Author':<25} {'Category':<15} {'Status':<10}")
        print("-" * 80)

        for book in books:
            book_id, title, author, category, status = book
            title_display = (title[:27] + '...') if len(title) > 30 else title
            author_display = (author[:22] + '...') if len(author) > 25 else author
            category_display = (category[:12] + '...') if len(category) > 15 else category

            print(f"{book_id:<8} {title_display:<30} {author_display:<25} {category_display:<15} {status:<10}")

        print("=" * 80)

    except sqlite3.Error as e:
        print(f"Error listing books: {e}")

    conn.close()


