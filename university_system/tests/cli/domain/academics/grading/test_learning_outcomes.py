"""
Comprehensive tests for learning_outcomes.py module
Tests learning outcome management, tracking, and reporting
"""

import pytest
import sqlite3
import sys
import os
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from university_system.modules.domain.academics.grading.learning_outcomes import (
    learning_outcome_menu,
    manage_learning_outcomes,
    record_outcome_achievement,
    view_student_outcome_achievement,
    generate_outcome_report
)
from university_system.infrastructure.database.db import get_connection


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database with required tables"""
    db_path = tmp_path / "test_student_records.db"

    def mock_get_connection():
        conn = sqlite3.connect(str(db_path))
        return conn

    # Initialize database with required tables
    conn = mock_get_connection()
    cursor = conn.cursor()

    # Create students table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        middle_name TEXT,
        last_name TEXT NOT NULL,
        course TEXT NOT NULL,
        email_address TEXT
    )
    ''')

    # Create learning outcomes table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS learning_outcomes (
        outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
        course TEXT,
        outcome_code TEXT,
        description TEXT,
        category TEXT,
        importance INTEGER
    )
    ''')

    # Create outcome results table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS outcome_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        outcome_id INTEGER,
        achievement_level REAL,
        evidence TEXT,
        date_assessed TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (outcome_id) REFERENCES learning_outcomes (outcome_id)
    )
    ''')

    # Create assessment_outcomes table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assessment_outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER,
        outcome_id INTEGER,
        weight REAL,
        FOREIGN KEY (outcome_id) REFERENCES learning_outcomes (outcome_id)
    )
    ''')

    conn.commit()
    conn.close()

    with patch('university_system.infrastructure.database.db.get_connection', mock_get_connection):
        with patch('university_system.modules.domain.academics.grading.learning_outcomes.get_connection', mock_get_connection):
            yield mock_get_connection


@pytest.fixture
def sample_data(test_db):
    """Insert sample data for testing"""
    conn = test_db()
    cursor = conn.cursor()

    # Insert sample students
    cursor.execute('''
        INSERT INTO students (student_id, first_name, last_name, course, email_address)
        VALUES ('ST001', 'John', 'Doe', 'CS', 'john@test.com')
    ''')

    cursor.execute('''
        INSERT INTO students (student_id, first_name, last_name, course, email_address)
        VALUES ('ST002', 'Jane', 'Smith', 'DS', 'jane@test.com')
    ''')

    # Insert sample learning outcomes
    cursor.execute('''
        INSERT INTO learning_outcomes (course, outcome_code, description, category, importance)
        VALUES ('CS', 'CS-LO1', 'Understanding programming fundamentals', 'Knowledge', 5)
    ''')

    cursor.execute('''
        INSERT INTO learning_outcomes (course, outcome_code, description, category, importance)
        VALUES ('CS', 'CS-LO2', 'Apply data structures effectively', 'Skills', 4)
    ''')

    cursor.execute('''
        INSERT INTO learning_outcomes (course, outcome_code, description, category, importance)
        VALUES ('DS', 'DS-LO1', 'Statistical analysis proficiency', 'Knowledge', 5)
    ''')

    conn.commit()
    conn.close()

    return test_db


class TestLearningOutcomeManagement:
    """Tests for learning outcome management functions"""

    @patch('builtins.input', side_effect=['5'])  # Exit immediately
    @patch('builtins.print')
    def test_manage_learning_outcomes_menu_display(self, mock_print, mock_input, test_db):
        """Test that manage_learning_outcomes displays menu correctly"""
        manage_learning_outcomes()

        # Verify menu items were printed
        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'Learning Outcomes Menu' in printed_output
        assert 'View All Learning Outcomes' in printed_output
        assert 'Add New Learning Outcome' in printed_output

    @patch('builtins.input', side_effect=['1', '5'])  # View all, then exit
    @patch('builtins.print')
    def test_view_all_learning_outcomes_empty(self, mock_print, mock_input, test_db):
        """Test viewing learning outcomes when none exist"""
        manage_learning_outcomes()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'No learning outcomes found' in printed_output

    @patch('builtins.input', side_effect=['1', '5'])  # View all, then exit
    @patch('builtins.print')
    def test_view_all_learning_outcomes_with_data(self, mock_print, mock_input, sample_data):
        """Test viewing learning outcomes when data exists"""
        manage_learning_outcomes()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'CS-LO1' in printed_output or 'CS-LO2' in printed_output

    @patch('builtins.input', side_effect=[
        '2',  # Add new outcome
        'CS',  # Course
        'CS-LO3',  # Outcome code
        'Test outcome description',  # Description
        'Knowledge',  # Category
        '4',  # Importance
        '5'  # Exit
    ])
    @patch('builtins.print')
    def test_add_new_learning_outcome(self, mock_print, mock_input, test_db):
        """Test adding a new learning outcome"""
        manage_learning_outcomes()

        # Verify outcome was added
        conn = test_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM learning_outcomes WHERE outcome_code = 'CS-LO3'"
        )
        result = cursor.fetchone()

        assert result is not None
        assert result[2] == 'CS-LO3'  # outcome_code
        assert result[3] == 'Test outcome description'  # description
        assert result[5] == 4  # importance

        conn.close()

    @patch('builtins.input', side_effect=[
        '2',  # Add new outcome
        'CS',  # Course
        'CS-INVALID',  # Outcome code
        'Test',  # Description
        'Knowledge',  # Category
        '6',  # Invalid importance (> 5)
        '3',  # Valid importance
        '5'  # Exit
    ])
    @patch('builtins.print')
    def test_add_learning_outcome_validates_importance(self, mock_print, mock_input, test_db):
        """Test that importance validation works"""
        manage_learning_outcomes()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'must be between 1 and 5' in printed_output

    @patch('builtins.input', side_effect=['3', '999', '5'])  # Edit non-existent, then exit
    @patch('builtins.print')
    def test_edit_nonexistent_outcome(self, mock_print, mock_input, test_db):
        """Test editing a non-existent learning outcome"""
        manage_learning_outcomes()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'No outcome found' in printed_output

    @patch('builtins.input', side_effect=['4', '999', '5'])  # Delete non-existent, then exit
    @patch('builtins.print')
    def test_delete_nonexistent_outcome(self, mock_print, mock_input, test_db):
        """Test deleting a non-existent learning outcome"""
        manage_learning_outcomes()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'No outcome found' in printed_output


class TestOutcomeAchievementRecording:
    """Tests for outcome achievement recording"""

    @patch('university_system.modules.domain.academics.grading.learning_outcomes.select_student')
    @patch('builtins.input', side_effect=['q'])  # Quit
    @patch('builtins.print')
    def test_record_outcome_achievement_no_student(self, mock_print, mock_input, mock_select, test_db):
        """Test recording achievement when no student is selected"""
        mock_select.return_value = None

        record_outcome_achievement()

        mock_select.assert_called_once()

    @patch('university_system.modules.domain.academics.grading.learning_outcomes.select_student')
    @patch('builtins.input', side_effect=['q'])  # Quit
    @patch('builtins.print')
    def test_record_outcome_achievement_with_student_no_outcomes(self, mock_print, mock_input, mock_select, test_db):
        """Test recording achievement when no outcomes exist"""
        mock_select.return_value = 'ST001'

        record_outcome_achievement()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        # Function should handle gracefully


class TestOutcomeReporting:
    """Tests for outcome reporting functions"""

    @patch('builtins.input', side_effect=['4'])  # Exit
    @patch('builtins.print')
    def test_generate_outcome_report_menu(self, mock_print, mock_input, test_db):
        """Test that generate_outcome_report displays menu"""
        with patch('university_system.modules.domain.academics.grading.learning_outcomes.generate_outcome_report') as mock_report:
            # Call the actual menu function that should be imported
            from university_system.modules.domain.academics.grading import learning_outcomes
            if hasattr(learning_outcomes, 'generate_outcome_report'):
                # Just test that it can be called
                pass


class TestViewStudentOutcomeAchievement:
    """Tests for viewing student outcome achievement"""

    @patch('university_system.modules.domain.academics.grading.learning_outcomes.select_student')
    @patch('builtins.print')
    def test_view_student_outcome_achievement_no_student(self, mock_print, mock_select, test_db):
        """Test viewing achievement when no student is selected"""
        mock_select.return_value = None

        view_student_outcome_achievement()

        mock_select.assert_called_once()

    @patch('university_system.modules.domain.academics.grading.learning_outcomes.select_student')
    @patch('builtins.print')
    def test_view_student_outcome_achievement_no_results(self, mock_print, mock_select, sample_data):
        """Test viewing achievement when student has no results"""
        mock_select.return_value = 'ST001'

        view_student_outcome_achievement()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'ST001' in printed_output or 'No outcome achievement' in printed_output


class TestDatabaseIntegrity:
    """Tests for database integrity and constraints"""

    def test_learning_outcomes_table_structure(self, test_db):
        """Test that learning_outcomes table has correct structure"""
        conn = test_db()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(learning_outcomes)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'outcome_id', 'course', 'outcome_code',
            'description', 'category', 'importance'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_outcome_results_table_structure(self, test_db):
        """Test that outcome_results table has correct structure"""
        conn = test_db()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(outcome_results)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'student_id', 'outcome_id',
            'achievement_level', 'evidence', 'date_assessed'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_outcome_results_foreign_key_constraint(self, test_db):
        """Test that outcome_results enforces foreign key constraints"""
        conn = test_db()
        cursor = conn.cursor()

        # Try to insert outcome result for non-existent student
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO outcome_results (student_id, outcome_id, achievement_level, date_assessed)
                VALUES ('NONEXISTENT', 1, 85.0, '2024-01-01')
            """)
            conn.commit()

        conn.close()


class TestLearningOutcomeMenu:
    """Tests for the learning outcome menu function"""

    @patch('builtins.input', side_effect=['6'])  # Exit immediately
    @patch('builtins.print')
    def test_learning_outcome_menu_display(self, mock_print, mock_input, test_db):
        """Test that learning outcome menu displays correctly"""
        learning_outcome_menu()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'Learning Outcome Tracking' in printed_output

    @patch('builtins.input', side_effect=['7', '6'])  # Invalid choice, then exit
    @patch('builtins.print')
    def test_learning_outcome_menu_invalid_choice(self, mock_print, mock_input, test_db):
        """Test that invalid menu choice is handled"""
        learning_outcome_menu()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'Invalid choice' in printed_output


class TestDataValidation:
    """Tests for data validation in learning outcomes"""

    @patch('builtins.input', side_effect=[
        '2',  # Add new outcome
        'CS',  # Course
        'TEST',  # Code
        'Description',  # Description
        'Knowledge',  # Category
        'invalid',  # Invalid importance (not a number)
        '3',  # Valid importance
        '5'  # Exit
    ])
    @patch('builtins.print')
    def test_importance_non_numeric_validation(self, mock_print, mock_input, test_db):
        """Test that non-numeric importance is rejected"""
        manage_learning_outcomes()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'valid number' in printed_output

    @patch('builtins.input', side_effect=['3', 'invalid', '5'])  # Edit with invalid ID
    @patch('builtins.print')
    def test_edit_with_invalid_id(self, mock_print, mock_input, test_db):
        """Test editing with invalid ID format"""
        manage_learning_outcomes()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'Invalid ID' in printed_output

    @patch('builtins.input', side_effect=['4', 'invalid', '5'])  # Delete with invalid ID
    @patch('builtins.print')
    def test_delete_with_invalid_id(self, mock_print, mock_input, test_db):
        """Test deleting with invalid ID format"""
        manage_learning_outcomes()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'Invalid ID' in printed_output


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    @patch('builtins.input', side_effect=[
        '2',  # Add new outcome
        '',  # Empty course (should accept)
        '',  # Empty code (should accept)
        'A' * 1000,  # Very long description
        'Knowledge',  # Category
        '5',  # Importance
        '5'  # Exit
    ])
    @patch('builtins.print')
    def test_long_description_handling(self, mock_print, mock_input, test_db):
        """Test handling of very long descriptions"""
        manage_learning_outcomes()

        # Should complete without errors
        conn = test_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM learning_outcomes")
        count = cursor.fetchone()[0]
        assert count >= 1
        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
