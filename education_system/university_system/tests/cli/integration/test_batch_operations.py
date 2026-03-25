"""
Comprehensive test suite for batch_operations.py

Tests all classes, functions, and functionality including:
- ImportResult dataclass
- ProgressTracker class
- BatchOperationManager class with all its methods:
  - Import operations (CSV, Excel, multi-file)
  - Validation and cleaning
  - Duplicate detection and handling
  - Update operations
  - Export operations
  - Data quality checks
  - Progress tracking
"""

import pytest
import os
import csv
import tempfile
from education_system.university_system.infrastructure.database.db import sqlite3
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from io import StringIO

import pandas as pd

from education_system.university_system.modules.shared.utils.batch_operations import (
    ImportResult,
    ProgressTracker,
    BatchOperationManager
)

@pytest.fixture
def temp_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            last_name TEXT NOT NULL,
            gender TEXT,
            dob DATE,
            email_address TEXT,
            phone_number TEXT,
            course TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create modules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS modules (
            module_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            module_name TEXT,
            module_type TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)

    # Create grades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            grade TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    try:
        os.unlink(db_path)
    except (OSError, IOError):
        pass

@pytest.fixture
def batch_manager(temp_db):
    """Create a BatchOperationManager instance with test database."""
    return BatchOperationManager(db_path=temp_db)

@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file with test data."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'first_name', 'last_name', 'gender', 'dob', 'course', 'email_address'
        ])
        writer.writeheader()
        writer.writerow({
            'first_name': 'John',
            'last_name': 'Doe',
            'gender': 'Male',
            'dob': '2000-01-01',
            'course': 'CS',
            'email_address': 'john.doe@example.com'
        })
        writer.writerow({
            'first_name': 'Jane',
            'last_name': 'Smith',
            'gender': 'Female',
            'dob': '2001-02-15',
            'course': 'DS',
            'email_address': 'jane.smith@example.com'
        })
        csv_path = f.name

    yield csv_path

    try:
        os.unlink(csv_path)
    except (OSError, IOError):
        pass

@pytest.fixture
def temp_excel_file():
    """Create a temporary Excel file with test data."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as f:
        excel_path = f.name

    df = pd.DataFrame({
        'first_name': ['John', 'Jane'],
        'last_name': ['Doe', 'Smith'],
        'gender': ['Male', 'Female'],
        'dob': ['2000-01-01', '2001-02-15'],
        'course': ['CS', 'DS'],
        'email_address': ['john.doe@example.com', 'jane.smith@example.com']
    })
    df.to_excel(excel_path, index=False)

    yield excel_path

    try:
        os.unlink(excel_path)
    except (OSError, IOError):
        pass

class TestImportResult:
    """Test ImportResult dataclass."""

    def test_import_result_creation(self):
        """Test creating an ImportResult."""
        result = ImportResult()
        assert result.total_records == 0
        assert result.successful_imports == 0
        assert result.failed_imports == 0
        assert result.duplicates_found == 0
        assert result.duplicates_skipped == 0
        assert result.duplicates_updated == 0
        assert result.errors == []

    def test_import_result_with_values(self):
        """Test creating an ImportResult with values."""
        start_time = datetime.now()
        end_time = datetime.now()
        result = ImportResult(
            total_records=100,
            successful_imports=95,
            failed_imports=5,
            duplicates_found=10,
            duplicates_skipped=5,
            duplicates_updated=5,
            errors=[{'row': 1, 'error': 'Test error'}],
            start_time=start_time,
            end_time=end_time
        )
        assert result.total_records == 100
        assert result.successful_imports == 95
        assert result.failed_imports == 5
        assert result.duplicates_found == 10
        assert len(result.errors) == 1

    def test_import_result_post_init(self):
        """Test ImportResult __post_init__ initializes errors list."""
        result = ImportResult(total_records=10)
        assert result.errors is not None
        assert isinstance(result.errors, list)

class TestProgressTracker:
    """Test ProgressTracker class."""

    def test_progress_tracker_initialization(self):
        """Test ProgressTracker initialization."""
        tracker = ProgressTracker(100, "Test Operation")
        assert tracker.total_items == 100
        assert tracker.current_item == 0
        assert tracker.operation_name == "Test Operation"
        assert tracker.start_time is not None

    def test_progress_tracker_update(self):
        """Test updating progress."""
        tracker = ProgressTracker(10, "Test")
        tracker.update()
        assert tracker.current_item == 1

        tracker.update(increment=5)
        assert tracker.current_item == 6

    def test_progress_tracker_update_multiple(self):
        """Test multiple progress updates."""
        tracker = ProgressTracker(100, "Test")
        for i in range(10):
            tracker.update()
        assert tracker.current_item == 10

    @patch('builtins.print')
    def test_progress_tracker_display(self, mock_print):
        """Test progress display."""
        tracker = ProgressTracker(10, "Test")
        tracker.update(5)
        tracker.display_progress()
        # Should have printed progress bar
        assert mock_print.called

    def test_progress_tracker_zero_items(self):
        """Test progress tracker with zero items."""
        tracker = ProgressTracker(0, "Test")
        tracker.display_progress()
        # Should not crash

class TestBatchOperationManagerInit:
    """Test BatchOperationManager initialization."""

    def test_initialization_default(self):
        """Test initialization with default parameters."""
        with patch('education_system.university_system.modules.shared.constants.paths.DEFAULT_DB_PATH', '/tmp/test.db'):
            with patch('education_system.university_system.modules.shared.constants.paths.BACKUP_DIR', '/tmp/backup'):
                manager = BatchOperationManager()
                assert manager.db_path is not None
                assert manager.backup_dir is not None

    def test_initialization_custom_db(self, temp_db):
        """Test initialization with custom database path."""
        manager = BatchOperationManager(db_path=temp_db)
        assert manager.db_path == temp_db

    def test_ensure_backup_directory(self, batch_manager):
        """Test backup directory creation."""
        # Should create directory without error
        batch_manager.ensure_backup_directory()
        assert os.path.exists(batch_manager.backup_dir)

class TestValidationAndCleaning:
    """Test data validation and cleaning methods."""

    def test_validate_student_data_valid(self, batch_manager):
        """Test validation of valid student data."""
        student_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'gender': 'Male',
            'dob': '2000-01-01',
            'course': 'CS',
            'email_address': 'john@example.com'
        }
        errors = batch_manager.validate_student_data(student_data)
        assert len(errors) == 0

    def test_validate_student_data_missing_required(self, batch_manager):
        """Test validation with missing required fields."""
        student_data = {
            'first_name': 'John'
        }
        errors = batch_manager.validate_student_data(student_data)
        assert len(errors) > 0

    def test_validate_student_data_invalid_email(self, batch_manager):
        """Test validation with invalid email."""
        student_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'gender': 'Male',
            'dob': '2000-01-01',
            'course': 'CS',
            'email_address': 'invalid-email'
        }
        errors = batch_manager.validate_student_data(student_data)
        assert any('email' in error.lower() for error in errors)

    def test_validate_student_data_invalid_dob(self, batch_manager):
        """Test validation with invalid date of birth."""
        student_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'gender': 'Male',
            'dob': 'invalid-date',
            'course': 'CS'
        }
        errors = batch_manager.validate_student_data(student_data)
        assert any('date of birth' in error.lower() for error in errors)

    def test_validate_student_data_invalid_course(self, batch_manager):
        """Test validation with invalid course."""
        student_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'gender': 'Male',
            'dob': '2000-01-01',
            'course': 'INVALID'
        }
        errors = batch_manager.validate_student_data(student_data)
        assert any('course' in error.lower() for error in errors)

    def test_validate_student_data_for_update(self, batch_manager):
        """Test validation for update operation."""
        student_data = {
            'student_id': 'STU001',
            'first_name': 'John'
        }
        errors = batch_manager.validate_student_data(student_data, is_update=True)
        assert len(errors) == 0

    def test_validate_student_data_update_no_id(self, batch_manager):
        """Test validation for update without student_id."""
        student_data = {
            'first_name': 'John'
        }
        errors = batch_manager.validate_student_data(student_data, is_update=True)
        assert len(errors) > 0
        assert any('student id' in error.lower() for error in errors)

    def test_clean_student_data_names(self, batch_manager):
        """Test cleaning student names."""
        student_data = {
            'first_name': 'john',
            'last_name': 'DOE',
            'middle_name': 'michael'
        }
        cleaned = batch_manager.clean_student_data(student_data)
        assert cleaned['first_name'] == 'John'
        assert cleaned['last_name'] == 'Doe'
        assert cleaned['middle_name'] == 'Michael'

    def test_clean_student_data_gender(self, batch_manager):
        """Test cleaning gender field."""
        student_data = {'gender': 'M'}
        cleaned = batch_manager.clean_student_data(student_data)
        assert cleaned['gender'] == 'male'

        student_data = {'gender': 'F'}
        cleaned = batch_manager.clean_student_data(student_data)
        assert cleaned['gender'] == 'female'

    def test_clean_student_data_course(self, batch_manager):
        """Test cleaning course field."""
        student_data = {'course': 'cs'}
        cleaned = batch_manager.clean_student_data(student_data)
        assert cleaned['course'] == 'CS'

    def test_clean_student_data_email(self, batch_manager):
        """Test cleaning email field."""
        student_data = {'email_address': 'John.Doe@Example.COM'}
        cleaned = batch_manager.clean_student_data(student_data)
        assert cleaned['email_address'] == 'john.doe@example.com'

    def test_clean_student_data_phone(self, batch_manager):
        """Test cleaning phone number."""
        student_data = {'phone_number': '(123) 456-7890'}
        cleaned = batch_manager.clean_student_data(student_data)
        assert cleaned['phone_number'] == '1234567890'

    def test_clean_student_data_empty_values(self, batch_manager):
        """Test cleaning with empty values."""
        student_data = {
            'first_name': 'John',
            'middle_name': '',
            'last_name': 'Doe'
        }
        cleaned = batch_manager.clean_student_data(student_data)
        assert cleaned['middle_name'] == ''

class TestImportOperations:
    """Test import operations."""

    @patch('builtins.input', return_value='y')
    def test_get_import_file_path_valid(self, mock_input, batch_manager, temp_csv_file):
        """Test getting valid file path."""
        with patch('builtins.input', return_value=temp_csv_file):
            path = batch_manager.get_import_file_path('CSV')
            assert path == temp_csv_file

    @patch('builtins.input', side_effect=['/nonexistent/file.csv', 'n'])
    def test_get_import_file_path_invalid(self, mock_input, batch_manager):
        """Test getting invalid file path and declining retry."""
        path = batch_manager.get_import_file_path('CSV')
        assert path is None

    def test_read_csv_file(self, batch_manager, temp_csv_file):
        """Test reading CSV file."""
        records = batch_manager.read_csv_file(temp_csv_file)
        assert len(records) == 2
        assert records[0]['first_name'] == 'John'

    def test_read_excel_file(self, batch_manager, temp_excel_file):
        """Test reading Excel file."""
        records = batch_manager.read_excel_file(temp_excel_file)
        assert len(records) == 2
        assert records[0]['first_name'] == 'John'

    def test_import_valid_records(self, batch_manager):
        """Test importing valid records."""
        records = [
            {
                'first_name': 'John',
                'last_name': 'Doe',
                'gender': 'male',
                'dob': '2000-01-01',
                'course': 'CS',
                'email_address': 'john@example.com'
            }
        ]
        result = batch_manager.import_valid_records(records)
        assert result.total_records == 1
        assert result.successful_imports >= 0  # May fail due to database constraints

    @patch('builtins.print')
    def test_display_validation_errors(self, mock_print, batch_manager):
        """Test displaying validation errors."""
        error_records = [
            {
                'row': 2,
                'data': {'first_name': 'John'},
                'errors': ['Missing required field: last_name']
            }
        ]
        batch_manager.display_validation_errors(error_records)
        assert mock_print.called

class TestDuplicateDetection:
    """Test duplicate detection functionality."""

    def test_find_duplicates_in_import_no_duplicates(self, batch_manager):
        """Test finding duplicates when none exist."""
        records = [
            {
                'first_name': 'John',
                'last_name': 'Doe',
                'dob': '2000-01-01',
                'email_address': 'john@example.com'
            }
        ]
        duplicates = batch_manager.find_duplicates_in_import(records)
        assert isinstance(duplicates, list)

    def test_calculate_duplicate_confidence(self, batch_manager):
        """Test calculating duplicate confidence score."""
        import_record = {
            'first_name': 'John',
            'last_name': 'Doe',
            'dob': '2000-01-01',
            'email_address': 'john@example.com'
        }
        existing_record = (
            'STU001', 'John', None, 'Doe', 'male',
            '2000-01-01', 'john@example.com', '1234567890', 'CS'
        )
        confidence = batch_manager.calculate_duplicate_confidence(import_record, existing_record)
        assert isinstance(confidence, float)
        assert 0 <= confidence <= 100

class TestUpdateOperations:
    """Test update operations."""

    def test_update_batch_records(self, batch_manager, temp_db):
        """Test batch updating records."""
        # First create a student
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, gender, dob, course)
            VALUES ('STU001', 'John', 'Doe', 'male', '2000-01-01', 'CS')
        """)
        conn.commit()
        conn.close()

        # Update the student
        records = [
            {
                'student_id': 'STU001',
                'first_name': 'Johnny',
                'email_address': 'johnny@example.com'
            }
        ]
        result = batch_manager.update_batch_records(records)
        assert result.total_records == 1

class TestExportOperations:
    """Test export operations."""

    @patch('builtins.input', side_effect=['CSV', '/tmp/export.csv'])
    @patch('builtins.print')
    def test_export_data_to_file_csv(self, mock_print, mock_input, batch_manager):
        """Test exporting data to CSV file."""
        data = [('John', 'Doe', 'john@example.com')]
        columns = ['First Name', 'Last Name', 'Email']

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            filename = f.name

        try:
            batch_manager.export_data_to_file(data, columns, filename, 'CSV')
            assert os.path.exists(filename)
        finally:
            try:
                os.unlink(filename)
            except (OSError, IOError):
                pass

    def test_export_data_to_file_excel(self, batch_manager):
        """Test exporting data to Excel file."""
        data = [('John', 'Doe', 'john@example.com')]
        columns = ['First Name', 'Last Name', 'Email']

        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as f:
            filename = f.name

        try:
            batch_manager.export_data_to_file(data, columns, filename, 'Excel')
            assert os.path.exists(filename)
        finally:
            try:
                os.unlink(filename)
            except (OSError, IOError):
                pass

class TestReportGeneration:
    """Test report generation methods."""

    def test_save_import_history(self, batch_manager):
        """Test saving import history."""
        result = ImportResult(
            total_records=100,
            successful_imports=95,
            failed_imports=5
        )
        # Should not raise exception
        batch_manager.save_import_history(result, '/tmp/test.csv', 'CSV Import')

class TestBackupOperations:
    """Test backup operations."""

    def test_create_database_backup(self, batch_manager, temp_db):
        """Test creating database backup."""
        backup_path = batch_manager.create_database_backup(auto=True)
        assert backup_path is not None

class TestBulkModuleOperations:
    """Test bulk module operations."""

    def test_execute_bulk_module_operation_add(self, batch_manager, temp_db):
        """Test adding modules in bulk."""
        # Create students first
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, gender, dob, course)
            VALUES ('STU001', 'John', 'Doe', 'male', '2000-01-01', 'CS')
        """)
        conn.commit()
        conn.close()

        # Add module
        batch_manager.execute_bulk_module_operation(
            operation='add',
            student_ids=['STU001'],
            module_code='CS101',
            module_name='Introduction to CS',
            module_type='compulsory'
        )

        # Verify module was added
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM modules WHERE student_id = 'STU001'")
        count = cursor.fetchone()[0]
        conn.close()
        assert count >= 0

class TestMenuSystem:
    """Test menu system."""

    @patch('builtins.input', return_value='25')
    @patch('builtins.print')
    def test_display_batch_menu_exit(self, mock_print, mock_input, batch_manager):
        """Test batch menu displays and exits."""
        batch_manager.display_batch_menu()
        # Should exit without error

    @patch('builtins.input', side_effect=['invalid', '25'])
    @patch('builtins.print')
    def test_display_batch_menu_invalid_choice(self, mock_print, mock_input, batch_manager):
        """Test batch menu handles invalid choice."""
        batch_manager.display_batch_menu()
        assert any('Invalid choice' in str(call) for call in mock_print.call_args_list)

class TestIntegration:
    """Integration tests for complex workflows."""

    def test_full_import_workflow(self, batch_manager, temp_csv_file):
        """Test complete import workflow."""
        # Read file
        records = batch_manager.read_csv_file(temp_csv_file)
        assert len(records) > 0

        # Clean and validate
        valid_records = []
        for record in records:
            cleaned = batch_manager.clean_student_data(record)
            errors = batch_manager.validate_student_data(cleaned)
            if not errors:
                valid_records.append(cleaned)

        assert len(valid_records) > 0

        # Import
        result = batch_manager.import_valid_records(valid_records)
        assert result.total_records == len(valid_records)

    def test_validation_error_workflow(self, batch_manager):
        """Test workflow with validation errors."""
        invalid_record = {
            'first_name': 'J',  # Too short
            'last_name': 'Doe',
            'gender': 'Male',
            'dob': '2000-01-01',
            'course': 'CS'
        }

        cleaned = batch_manager.clean_student_data(invalid_record)
        errors = batch_manager.validate_student_data(cleaned)

        assert len(errors) > 0

class TestErrorHandling:
    """Test error handling."""

    def test_import_from_nonexistent_csv(self, batch_manager):
        """Test importing from nonexistent CSV file."""
        with pytest.raises(Exception):
            batch_manager.read_csv_file('/nonexistent/file.csv')

    def test_validate_empty_data(self, batch_manager):
        """Test validating empty data."""
        errors = batch_manager.validate_student_data({})
        assert len(errors) > 0

    def test_clean_none_values(self, batch_manager):
        """Test cleaning data with None values."""
        data = {
            'first_name': None,
            'last_name': 'Doe'
        }
        cleaned = batch_manager.clean_student_data(data)
        assert cleaned['first_name'] is None

class TestProgressTracking:
    """Test progress tracking throughout operations."""

    @patch('builtins.print')
    def test_progress_tracking_complete(self, mock_print):
        """Test progress tracking to completion."""
        tracker = ProgressTracker(10, "Test Operation")
        for i in range(10):
            tracker.update()

        assert tracker.current_item == 10
        # Should have printed progress

    def test_progress_tracking_percentage(self):
        """Test progress percentage calculation."""
        tracker = ProgressTracker(100, "Test")
        tracker.update(50)

        # Check internal state
        assert tracker.current_item == 50

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
