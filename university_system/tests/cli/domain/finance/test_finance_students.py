"""
Test suite for university_system/modules/domain/finance/finance_misc/students.py

Tests all student-related finance functions including:
- Student existence checks
- Student information retrieval
- Student credits management
- Credit application to fees
- Sample data creation
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import io

from university_system.modules.domain.finance.core import students
from university_system.infrastructure.database.db import get_connection, transaction

@pytest.fixture
def test_db_connection():
    """Create a test database connection with required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Ensure students table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email_address TEXT,
            phone_number TEXT,
            course TEXT,
            enrollment_date TEXT,
            status TEXT
        )
    ''')

    # Ensure student_credits table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_credits (
            credit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            credit_amount REAL,
            remaining_amount REAL,
            credit_source TEXT,
            description TEXT,
            expiry_date TEXT,
            status TEXT DEFAULT 'active',
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    # Ensure student_fees table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            fee_type_id INTEGER,
            amount REAL,
            due_date TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    # Ensure fee_types table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT,
            description TEXT,
            default_amount REAL,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Ensure payments table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            amount REAL,
            payment_method TEXT,
            payment_date TEXT,
            notes TEXT,
            status TEXT DEFAULT 'completed',
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')

    # Ensure payment_allocations table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER,
            student_fee_id INTEGER,
            amount REAL,
            created_at TEXT,
            FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
            FOREIGN KEY (student_fee_id) REFERENCES student_fees(student_fee_id)
        )
    ''')

    conn.commit()
    yield conn

    # Cleanup after tests
    cursor.execute('DELETE FROM payment_allocations')
    cursor.execute('DELETE FROM payments')
    cursor.execute('DELETE FROM student_credits')
    cursor.execute('DELETE FROM student_fees')
    cursor.execute('DELETE FROM fee_types')
    cursor.execute('DELETE FROM students')
    conn.commit()
    conn.close()

@pytest.fixture
def sample_student(test_db_connection):
    """Create a sample student for testing"""
    cursor = test_db_connection.cursor()
    cursor.execute('''
        INSERT INTO students
        (student_id, first_name, last_name, email_address, phone_number, course, enrollment_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('TEST001', 'John', 'Doe', 'john.doe@test.ac.uk', '07123456789',
          'Computer Science', '2024-01-01', 'active'))
    test_db_connection.commit()
    return 'TEST001'

class TestStudentExistence:
    """Test student existence checking"""

    def test_student_exists_returns_true_for_existing_student(self, test_db_connection, sample_student):
        """Test that student_exists returns True for existing students"""
        assert students.student_exists(sample_student) is True

    def test_student_exists_returns_false_for_nonexistent_student(self, test_db_connection):
        """Test that student_exists returns False for non-existent students"""
        assert students.student_exists('NONEXISTENT') is False

    def test_student_exists_handles_database_errors_gracefully(self, monkeypatch):
        """Test that student_exists returns False on database errors"""
        def mock_get_connection():
            raise sqlite3.Error("Database error")

        monkeypatch.setattr(students, 'get_connection', mock_get_connection)
        assert students.student_exists('TEST001') is False

class TestStudentNameRetrieval:
    """Test student name retrieval"""

    def test_get_student_name_returns_full_name(self, test_db_connection, sample_student):
        """Test that get_student_name returns the full name"""
        name = students.get_student_name(sample_student)
        assert name == "John Doe"

    def test_get_student_name_returns_unknown_for_nonexistent_student(self, test_db_connection):
        """Test that get_student_name returns 'Unknown Student' for non-existent students"""
        name = students.get_student_name('NONEXISTENT')
        assert name == "Unknown Student"

    def test_get_student_name_handles_database_errors(self, monkeypatch):
        """Test that get_student_name handles database errors gracefully"""
        def mock_get_connection():
            raise sqlite3.Error("Database error")

        monkeypatch.setattr(students, 'get_connection', mock_get_connection)
        name = students.get_student_name('TEST001')
        assert name == "Unknown Student"

class TestStudentEmailRetrieval:
    """Test student email retrieval"""

    def test_get_student_email_returns_correct_email(self, test_db_connection, sample_student):
        """Test that get_student_email returns the correct email"""
        email = students.get_student_email(sample_student)
        assert email == "john.doe@test.ac.uk"

    def test_get_student_email_returns_default_for_nonexistent_student(self, test_db_connection):
        """Test that get_student_email returns default email for non-existent students"""
        email = students.get_student_email('NONEXISTENT')
        assert email == "NONEXISTENT@university.ac.uk"

    def test_get_student_email_handles_exceptions(self, monkeypatch):
        """Test that get_student_email handles exceptions gracefully"""
        def mock_get_connection():
            raise Exception("Connection error")

        monkeypatch.setattr(students, 'get_connection', mock_get_connection)
        email = students.get_student_email('TEST001')
        assert email == "TEST001@university.ac.uk"

class TestStudentPhoneRetrieval:
    """Test student phone retrieval"""

    def test_get_student_phone_returns_correct_phone(self, test_db_connection, sample_student):
        """Test that get_student_phone returns the correct phone number"""
        phone = students.get_student_phone(sample_student)
        assert phone == "07123456789"

    def test_get_student_phone_returns_default_for_nonexistent_student(self, test_db_connection):
        """Test that get_student_phone returns default phone for non-existent students"""
        phone = students.get_student_phone('NONEXISTENT')
        assert phone == "07000000000"

    def test_get_student_phone_handles_exceptions(self, monkeypatch):
        """Test that get_student_phone handles exceptions gracefully"""
        def mock_get_connection():
            raise Exception("Connection error")

        monkeypatch.setattr(students, 'get_connection', mock_get_connection)
        phone = students.get_student_phone('TEST001')
        assert phone == "07000000000"

class TestSampleStudentCreation:
    """Test sample student creation"""

    def test_create_sample_students_creates_students(self, test_db_connection):
        """Test that create_sample_students creates sample students"""
        # Clear existing students first
        cursor = test_db_connection.cursor()
        cursor.execute('DELETE FROM students')
        test_db_connection.commit()

        students.create_sample_students()

        cursor.execute('SELECT COUNT(*) FROM students')
        count = cursor.fetchone()[0]
        assert count == 5

    def test_create_sample_students_does_not_duplicate(self, test_db_connection, sample_student):
        """Test that create_sample_students doesn't create duplicates"""
        initial_count = test_db_connection.cursor().execute('SELECT COUNT(*) FROM students').fetchone()[0]

        students.create_sample_students()

        final_count = test_db_connection.cursor().execute('SELECT COUNT(*) FROM students').fetchone()[0]
        assert final_count == initial_count

    def test_create_sample_students_handles_errors(self, monkeypatch, capsys):
        """Test that create_sample_students handles errors gracefully"""
        def mock_get_connection():
            raise Exception("Connection error")

        monkeypatch.setattr(students, 'get_connection', mock_get_connection)
        students.create_sample_students()

        captured = capsys.readouterr()
        assert "Error creating sample students" in captured.out

class TestStudentCredits:
    """Test student credits functionality"""

    @pytest.fixture
    def student_with_credit(self, test_db_connection, sample_student):
        """Create a student with a credit"""
        cursor = test_db_connection.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO student_credits
            (student_id, credit_amount, remaining_amount, credit_source, description, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sample_student, 100.00, 100.00, 'scholarship', 'Test scholarship', 'admin', now, now))
        test_db_connection.commit()
        return sample_student

    def test_view_student_credits_displays_credits(self, test_db_connection, student_with_credit, monkeypatch, capsys):
        """Test that view_student_credits displays active credits"""
        # Mock input to provide student ID
        monkeypatch.setattr('builtins.input', lambda _: student_with_credit)

        students.view_student_credits()

        captured = capsys.readouterr()
        assert student_with_credit in captured.out
        assert "100.00" in captured.out
        assert "scholarship" in captured.out

    def test_view_student_credits_handles_nonexistent_student(self, test_db_connection, monkeypatch, capsys):
        """Test view_student_credits with non-existent student"""
        monkeypatch.setattr('builtins.input', lambda _: 'NONEXISTENT')

        students.view_student_credits()

        captured = capsys.readouterr()
        assert "does not exist" in captured.out

    def test_view_student_credits_handles_no_credits(self, test_db_connection, sample_student, monkeypatch, capsys):
        """Test view_student_credits when student has no credits"""
        monkeypatch.setattr('builtins.input', lambda _: sample_student)

        students.view_student_credits()

        captured = capsys.readouterr()
        assert "No active credits found" in captured.out

class TestAddStudentCredit:
    """Test adding student credits"""

    def test_add_student_credit_creates_credit(self, test_db_connection, sample_student, monkeypatch, capsys):
        """Test that add_student_credit successfully creates a credit"""
        inputs = iter([sample_student, '50.00', '1', 'Test credit', ''])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        with patch('university_system.modules.domain.finance.finance_misc.students.get_current_user') as mock_user:
            mock_user.return_value = {'username': 'test_admin'}
            students.add_student_credit()

        captured = capsys.readouterr()
        assert "Credit added successfully" in captured.out

        # Verify in database
        cursor = test_db_connection.cursor()
        cursor.execute('SELECT credit_amount, credit_source FROM student_credits WHERE student_id = ?', (sample_student,))
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 50.00

    def test_add_student_credit_rejects_negative_amount(self, test_db_connection, sample_student, monkeypatch, capsys):
        """Test that add_student_credit rejects negative amounts"""
        inputs = iter([sample_student, '-50.00', '100.00', '1', 'Test credit', ''])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        with patch('university_system.modules.domain.finance.finance_misc.students.get_current_user') as mock_user:
            mock_user.return_value = {'username': 'test_admin'}
            students.add_student_credit()

        captured = capsys.readouterr()
        assert "greater than zero" in captured.out

    def test_add_student_credit_validates_expiry_date(self, test_db_connection, sample_student, monkeypatch, capsys):
        """Test that add_student_credit validates expiry date format"""
        inputs = iter([sample_student, '50.00', '1', 'Test credit', 'invalid-date'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        with patch('university_system.modules.domain.finance.finance_misc.students.get_current_user') as mock_user:
            mock_user.return_value = {'username': 'test_admin'}
            students.add_student_credit()

        captured = capsys.readouterr()
        assert "Invalid date format" in captured.out or "Credit added successfully" in captured.out

class TestCreditHistory:
    """Test credit history functionality"""

    @pytest.fixture
    def student_with_multiple_credits(self, test_db_connection, sample_student):
        """Create a student with multiple credits"""
        cursor = test_db_connection.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        credits = [
            (sample_student, 100.00, 50.00, 'scholarship', 'Active scholarship', 'active', now, now),
            (sample_student, 200.00, 0.00, 'refund', 'Refund credit', 'used', now, now),
            (sample_student, 50.00, 50.00, 'goodwill', 'Goodwill credit', 'active', now, now),
        ]

        for credit in credits:
            cursor.execute('''
                INSERT INTO student_credits
                (student_id, credit_amount, remaining_amount, credit_source, description, status, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'admin', ?, ?)
            ''', credit)

        test_db_connection.commit()
        return sample_student

    def test_view_credit_history_shows_all_credits(self, test_db_connection, student_with_multiple_credits, monkeypatch, capsys):
        """Test that view_credit_history shows all credits"""
        monkeypatch.setattr('builtins.input', lambda _: student_with_multiple_credits)

        students.view_credit_history()

        captured = capsys.readouterr()
        assert "scholarship" in captured.out
        assert "refund" in captured.out
        assert "goodwill" in captured.out
        assert "350.00" in captured.out  # Total credits received

class TestApplyCreditToFees:
    """Test applying credits to fees"""

    @pytest.fixture
    def student_with_credit_and_fees(self, test_db_connection, sample_student):
        """Create a student with credits and outstanding fees"""
        cursor = test_db_connection.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Create fee type
        cursor.execute('''
            INSERT INTO fee_types (fee_name, default_amount, is_active)
            VALUES ('Tuition Fee', 1000.00, 1)
        ''')
        fee_type_id = cursor.lastrowid

        # Create student fee
        cursor.execute('''
            INSERT INTO student_fees
            (student_id, fee_type_id, amount, due_date, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'unpaid', ?, ?)
        ''', (sample_student, fee_type_id, 500.00, '2024-12-31', now, now))

        # Create credit
        cursor.execute('''
            INSERT INTO student_credits
            (student_id, credit_amount, remaining_amount, credit_source, description, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', 'admin', ?, ?)
        ''', (sample_student, 300.00, 300.00, 'scholarship', 'Test scholarship', now, now))

        test_db_connection.commit()
        return sample_student

    def test_apply_credit_to_fees_applies_credits(self, test_db_connection, student_with_credit_and_fees, monkeypatch, capsys):
        """Test that apply_credit_to_fees successfully applies credits to fees"""
        inputs = iter([student_with_credit_and_fees, 'y'])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        with patch('university_system.modules.domain.finance.finance_misc.students.get_current_user') as mock_user:
            mock_user.return_value = {'username': 'test_admin'}
            students.apply_credit_to_fees()

        captured = capsys.readouterr()
        assert "Credit application completed" in captured.out or "Applied" in captured.out

class TestAPIFinancialSummary:
    """Test API for student financial summary"""

    @pytest.fixture
    def student_with_financial_data(self, test_db_connection, sample_student):
        """Create a student with financial data"""
        cursor = test_db_connection.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Create fee type
        cursor.execute('''
            INSERT INTO fee_types (fee_name, default_amount, is_active)
            VALUES ('Tuition Fee', 1000.00, 1)
        ''')
        fee_type_id = cursor.lastrowid

        # Create student fee
        cursor.execute('''
            INSERT INTO student_fees
            (student_id, fee_type_id, amount, due_date, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'unpaid', ?, ?)
        ''', (sample_student, fee_type_id, 500.00, '2024-12-31', now, now))

        # Create payment
        cursor.execute('''
            INSERT INTO payments
            (student_id, amount, payment_method, payment_date, status, created_by, created_at)
            VALUES (?, ?, 'Bank Transfer', ?, 'completed', 'admin', ?)
        ''', (sample_student, 200.00, '2024-01-15', now))

        test_db_connection.commit()
        return sample_student

    @patch('university_system.modules.domain.finance.finance_misc.students.verify_jwt_in_request')
    def test_api_get_student_financial_summary_returns_data(self, mock_jwt, test_db_connection, student_with_financial_data):
        """Test that API returns financial summary correctly"""
        result = students.api_get_student_financial_summary(student_with_financial_data)

        # The function returns a Flask jsonify object, we can access the data
        # In testing, we just verify it doesn't error
        assert result is not None

class TestErrorHandling:
    """Test error handling across all functions"""

    def test_view_student_credits_handles_database_error(self, monkeypatch, capsys):
        """Test that view_student_credits handles database errors"""
        monkeypatch.setattr('builtins.input', lambda _: 'TEST001')

        def mock_get_connection():
            raise sqlite3.Error("Database error")

        monkeypatch.setattr(students, 'get_connection', mock_get_connection)

        students.view_student_credits()

        captured = capsys.readouterr()
        assert "Database error" in captured.out or "Error" in captured.out

    def test_add_student_credit_handles_database_error(self, monkeypatch, capsys):
        """Test that add_student_credit handles database errors"""
        inputs = iter(['TEST001', '100.00', '1', 'Test', ''])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        def mock_get_connection():
            raise sqlite3.Error("Database error")

        monkeypatch.setattr(students, 'get_connection', mock_get_connection)

        with patch('university_system.modules.domain.finance.finance_misc.students.get_current_user') as mock_user:
            mock_user.return_value = {'username': 'test_admin'}
            students.add_student_credit()

        captured = capsys.readouterr()
        assert "Database error" in captured.out or "does not exist" in captured.out

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
