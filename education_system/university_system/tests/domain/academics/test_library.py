"""
Comprehensive tests for library.py

Tests library management system including books, loans, reservations, and reviews
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from education_system.university_system.modules.domain.academics.services.library.models import (
    Book, BookLoan, BookReservation, BookReview, ReadingList
)
from education_system.university_system.modules.domain.academics.services.library.database import (
    get_db_connection, init_library_db, log_audit_event
)
from education_system.university_system.modules.domain.academics.services.library.settings import set_auth
from education_system.university_system.modules.domain.academics.services.library.barcode import generate_barcode

class TestBookClass:
    """Test suite for Book class"""

    def test_book_initialization(self):
        """Test Book object initialization"""
        book = Book(
            book_id='B001',
            title='Test Book',
            author='Test Author',
            isbn='1234567890',
            publisher='Test Publisher',
            category='Fiction',
            year_published=2024,
            description='A test book',
            location='A1-01',
            status='available',
            added_date='2024-01-01',
            last_updated='2024-01-01'
        )

        assert book.book_id == 'B001'
        assert book.title == 'Test Book'
        assert book.author == 'Test Author'
        assert book.isbn == '1234567890'
        assert book.status == 'available'

    def test_book_with_optional_fields(self):
        """Test Book with optional fields"""
        book = Book(
            book_id='B002',
            title='Advanced Book',
            author='Author Name',
            isbn='0987654321',
            publisher='Publisher',
            category='Science',
            year_published=2024,
            description='Description',
            location='B2-05',
            status='available',
            added_date='2024-01-01',
            last_updated='2024-01-01',
            reading_level='Advanced',
            tags=['science', 'technology'],
            cover_image_path='/path/to/cover.jpg',
            digital_copy_path='/path/to/digital.pdf'
        )

        assert book.reading_level == 'Advanced'
        assert book.tags == ['science', 'technology']
        assert book.cover_image_path == '/path/to/cover.jpg'
        assert book.digital_copy_path == '/path/to/digital.pdf'

    def test_book_default_tags(self):
        """Test Book default tags is empty list"""
        book = Book(
            book_id='B003',
            title='Test',
            author='Author',
            isbn='123',
            publisher='Pub',
            category='Cat',
            year_published=2024,
            description='Desc',
            location='Loc',
            status='available',
            added_date='2024-01-01',
            last_updated='2024-01-01'
        )

        assert book.tags == []

class TestBookLoanClass:
    """Test suite for BookLoan class"""

    def test_book_loan_initialization(self):
        """Test BookLoan object initialization"""
        loan = BookLoan(
            loan_id=1,
            book_id='B001',
            user_id='U001',
            checkout_date='2024-01-01',
            due_date='2024-01-15',
            return_date=None,
            status='active',
            fine_amount=0.0
        )

        assert loan.loan_id == 1
        assert loan.book_id == 'B001'
        assert loan.user_id == 'U001'
        assert loan.status == 'active'
        assert loan.fine_amount == 0.0

    def test_book_loan_with_defaults(self):
        """Test BookLoan with default values"""
        loan = BookLoan(
            loan_id=2,
            book_id='B002',
            user_id='U002',
            checkout_date='2024-01-01',
            due_date='2024-01-15',
            return_date=None,
            status='active',
            fine_amount=0.0,
            renewal_count=2,
            reading_progress=50
        )

        assert loan.renewal_count == 2
        assert loan.reading_progress == 50

class TestBookReservationClass:
    """Test suite for BookReservation class"""

    def test_book_reservation_initialization(self):
        """Test BookReservation object initialization"""
        reservation = BookReservation(
            reservation_id=1,
            book_id='B001',
            user_id='U001',
            reservation_date='2024-01-01',
            expiry_date='2024-01-03',
            status='active',
            priority_order=1
        )

        assert reservation.reservation_id == 1
        assert reservation.book_id == 'B001'
        assert reservation.user_id == 'U001'
        assert reservation.status == 'active'
        assert reservation.priority_order == 1

class TestBookReviewClass:
    """Test suite for BookReview class"""

    def test_book_review_initialization(self):
        """Test BookReview object initialization"""
        review = BookReview(
            review_id=1,
            book_id='B001',
            user_id='U001',
            rating=5,
            review_text='Excellent book!',
            review_date='2024-01-01',
            status='pending'
        )

        assert review.review_id == 1
        assert review.book_id == 'B001'
        assert review.rating == 5
        assert review.review_text == 'Excellent book!'
        assert review.status == 'pending'

    def test_book_review_default_status(self):
        """Test BookReview default status is pending"""
        review = BookReview(
            review_id=2,
            book_id='B002',
            user_id='U002',
            rating=4,
            review_text='Good',
            review_date='2024-01-01'
        )

        assert review.status == 'pending'

class TestReadingListClass:
    """Test suite for ReadingList class"""

    def test_reading_list_initialization(self):
        """Test ReadingList object initialization"""
        reading_list = ReadingList(
            list_id=1,
            name='Summer Reading',
            description='Books for summer',
            creator_id='U001',
            created_date='2024-01-01',
            is_public=False,
            is_collaborative=False
        )

        assert reading_list.list_id == 1
        assert reading_list.name == 'Summer Reading'
        assert reading_list.creator_id == 'U001'
        assert reading_list.is_public is False
        assert reading_list.is_collaborative is False

class TestLibraryDatabaseFunctions:
    """Test suite for library database functions"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        # Create stub payments table needed by init_library_db
        conn = sqlite3.connect(path)
        conn.execute('''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL, payment_date TEXT, source_type TEXT,
            reference_id TEXT, reference_type TEXT, payment_reference TEXT
        )''')
        conn.commit()
        conn.close()
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def mock_db_path(self, temp_db, monkeypatch):
        """Mock the database path"""
        from education_system.university_system.modules.domain.academics.services.library import database
        monkeypatch.setattr(database, 'DATABASE_FILE', temp_db)
        return temp_db

    def test_get_db_connection(self, mock_db_path):
        """Test get_db_connection function"""
        conn = get_db_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)

        # Test foreign keys are enabled
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        assert result[0] == 1  # Foreign keys should be ON

        conn.close()

    def test_init_library_db_creates_tables(self, mock_db_path):
        """Test init_library_db creates all required tables"""
        result = init_library_db()

        # Should return True or not raise error
        assert result is not False

        conn = sqlite3.connect(mock_db_path)
        cursor = conn.cursor()

        # Check some key tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            'books',
            'book_loans',
            'book_reservations',
            'book_reviews',
            'reading_lists',
            'library_settings'
        ]

        for table in expected_tables:
            assert table in tables, f"Table {table} not found"

        conn.close()

    def test_init_library_db_creates_settings(self, mock_db_path):
        """Test init_library_db creates default settings"""
        init_library_db()

        conn = sqlite3.connect(mock_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM library_settings")
        count = cursor.fetchone()[0]

        assert count > 0, "No settings were created"

        # Check specific settings
        cursor.execute("SELECT setting_value FROM library_settings WHERE setting_name = 'loan_period_days'")
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == '14'

        conn.close()

    def test_init_library_db_idempotent(self, mock_db_path):
        """Test init_library_db can be called multiple times"""
        init_library_db()
        init_library_db()
        init_library_db()

        # Should not raise errors
        conn = sqlite3.connect(mock_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'books' in tables
        conn.close()

class TestLibraryAuth:
    """Test suite for library authentication functions"""

    def test_set_auth(self):
        """Test set_auth function"""
        mock_auth = Mock()
        mock_auth.current_user = {'user_id': 'U001'}

        set_auth(mock_auth)

        # Import the settings module to check the global auth
        from education_system.university_system.modules.domain.academics.services.library import settings
        assert settings.auth == mock_auth

class TestLibraryUtilityFunctions:
    """Test suite for library utility functions"""

    def test_generate_barcode(self):
        """Test generate_barcode function"""
        barcode = generate_barcode('B001')

        assert barcode is not None
        assert isinstance(barcode, str)
        assert len(barcode) > 0

    def test_generate_barcode_unique(self):
        """Test generate_barcode generates consistent output"""
        barcode1 = generate_barcode('B001')
        barcode2 = generate_barcode('B001')

        # Should generate same barcode for same book_id
        assert barcode1 == barcode2

    def test_generate_barcode_different_books(self):
        """Test generate_barcode generates different barcodes for different books"""
        barcode1 = generate_barcode('B001')
        barcode2 = generate_barcode('B002')

        # Different books should have different barcodes
        assert barcode1 != barcode2

    @patch('education_system.university_system.modules.domain.academics.services.library.database.get_db_connection')
    def test_log_audit_event(self, mock_get_connection):
        """Test log_audit_event function"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        log_audit_event(
            user_id='U001',
            action='checkout',
            table_affected='book_loans',
            record_id='B001'
        )

        # Verify cursor.execute was called
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called()

class TestLibraryDatabaseSchema:
    """Test suite for library database schema"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.execute('''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL, payment_date TEXT, source_type TEXT,
            reference_id TEXT, reference_type TEXT, payment_reference TEXT
        )''')
        conn.commit()
        conn.close()
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def initialized_db(self, temp_db, monkeypatch):
        """Initialize database and return path"""
        from education_system.university_system.modules.domain.academics.services.library import database
        monkeypatch.setattr(database, 'DATABASE_FILE', temp_db)
        init_library_db()
        return temp_db

    def test_books_table_structure(self, initialized_db):
        """Test books table has correct structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(books)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = [
            'book_id', 'title', 'author', 'isbn', 'publisher',
            'category', 'year_published', 'description', 'location',
            'status', 'added_date', 'last_updated'
        ]

        for col in expected_columns:
            assert col in columns, f"Column {col} not found in books table"

        conn.close()

    def test_book_loans_table_structure(self, initialized_db):
        """Test book_loans table has correct structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(book_loans)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'loan_id', 'book_id', 'user_id', 'checkout_date',
            'due_date', 'return_date', 'status', 'fine_amount'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_book_reviews_table_structure(self, initialized_db):
        """Test book_reviews table has correct structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(book_reviews)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'review_id', 'book_id', 'user_id', 'rating',
            'review_text', 'review_date', 'status'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_reading_lists_table_structure(self, initialized_db):
        """Test reading_lists table has correct structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(reading_lists)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'list_id', 'name', 'description', 'creator_id',
            'created_date', 'is_public', 'is_collaborative'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_library_settings_table_structure(self, initialized_db):
        """Test library_settings table has correct structure"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(library_settings)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'setting_name', 'setting_value', 'description',
            'setting_type', 'min_value', 'max_value', 'allowed_values'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_default_library_settings(self, initialized_db):
        """Test default library settings are created"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute("SELECT setting_name, setting_value FROM library_settings")
        settings = {row[0]: row[1] for row in cursor.fetchall()}

        # Check key settings exist
        assert 'loan_period_days' in settings
        assert 'max_loans' in settings
        assert 'fine_per_day' in settings
        assert 'max_renewals' in settings

        # Check default values
        assert settings['loan_period_days'] == '14'
        assert settings['max_loans'] == '5'
        assert settings['fine_per_day'] == '0.50'

        conn.close()

    def test_audit_log_table_exists(self, initialized_db):
        """Test audit_log table exists"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        result = cursor.fetchone()

        assert result is not None
        conn.close()

    def test_digital_library_table_exists(self, initialized_db):
        """Test digital_library table exists"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='digital_library'")
        result = cursor.fetchone()

        assert result is not None
        conn.close()

class TestLibraryDataOperations:
    """Test suite for library data operations"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.execute('''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL, payment_date TEXT, source_type TEXT,
            reference_id TEXT, reference_type TEXT, payment_reference TEXT
        )''')
        conn.commit()
        conn.close()
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def initialized_db(self, temp_db, monkeypatch):
        """Initialize database and return path"""
        from education_system.university_system.modules.domain.academics.services.library import database
        monkeypatch.setattr(database, 'DATABASE_FILE', temp_db)
        init_library_db()
        return temp_db

    def test_insert_book(self, initialized_db):
        """Test inserting a book into the database"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO books (book_id, title, author, isbn, publisher, category,
                             year_published, description, location, status,
                             added_date, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('B001', 'Test Book', 'Test Author', '1234567890', 'Test Pub',
              'Fiction', 2024, 'Test description', 'A1-01', 'available',
              '2024-01-01', '2024-01-01'))

        conn.commit()

        cursor.execute("SELECT * FROM books WHERE book_id = ?", ('B001',))
        result = cursor.fetchone()

        assert result is not None
        assert result[1] == 'Test Book'

        conn.close()

    def test_insert_book_loan(self, initialized_db):
        """Test inserting a book loan"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        # First insert a book
        cursor.execute('''
            INSERT INTO books (book_id, title, author, status, added_date, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('B001', 'Test', 'Author', 'checked_out', '2024-01-01', '2024-01-01'))

        # Then insert a loan
        cursor.execute('''
            INSERT INTO book_loans (book_id, user_id, checkout_date, due_date, status)
            VALUES (?, ?, ?, ?, ?)
        ''', ('B001', 'U001', '2024-01-01', '2024-01-15', 'active'))

        conn.commit()

        cursor.execute("SELECT * FROM book_loans WHERE book_id = ?", ('B001',))
        result = cursor.fetchone()

        assert result is not None
        assert result[2] == 'U001'

        conn.close()

    def test_insert_book_review(self, initialized_db):
        """Test inserting a book review"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO book_reviews (book_id, user_id, rating, review_text,
                                     review_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('B001', 'U001', 5, 'Great book!', '2024-01-01', 'approved'))

        conn.commit()

        cursor.execute("SELECT * FROM book_reviews WHERE book_id = ?", ('B001',))
        result = cursor.fetchone()

        assert result is not None
        assert result[3] == 5
        assert result[4] == 'Great book!'

        conn.close()

    def test_rating_constraint(self, initialized_db):
        """Test rating constraint on book_reviews"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        # Test valid rating
        cursor.execute('''
            INSERT INTO book_reviews (book_id, user_id, rating, review_date)
            VALUES (?, ?, ?, ?)
        ''', ('B001', 'U001', 5, '2024-01-01'))
        conn.commit()

        # Test invalid rating should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute('''
                INSERT INTO book_reviews (book_id, user_id, rating, review_date)
                VALUES (?, ?, ?, ?)
            ''', ('B002', 'U002', 6, '2024-01-01'))
            conn.commit()

        conn.close()

class TestLibraryEdgeCases:
    """Test suite for edge cases"""

    def test_book_with_none_tags(self):
        """Test Book handles None tags"""
        book = Book(
            book_id='B001',
            title='Test',
            author='Author',
            isbn='123',
            publisher='Pub',
            category='Cat',
            year_published=2024,
            description='Desc',
            location='Loc',
            status='available',
            added_date='2024-01-01',
            last_updated='2024-01-01',
            tags=None
        )

        assert book.tags == []

    def test_book_loan_zero_fine(self):
        """Test BookLoan with zero fine"""
        loan = BookLoan(
            loan_id=1,
            book_id='B001',
            user_id='U001',
            checkout_date='2024-01-01',
            due_date='2024-01-15',
            return_date=None,
            status='active',
            fine_amount=0.0
        )

        assert loan.fine_amount == 0.0

    def test_book_review_empty_text(self):
        """Test BookReview with empty review text"""
        review = BookReview(
            review_id=1,
            book_id='B001',
            user_id='U001',
            rating=5,
            review_text='',
            review_date='2024-01-01'
        )

        assert review.review_text == ''
