"""
Comprehensive tests for grade_tracking.py module
Tests database initialization, menu functions, and grade tracking features
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from education_system.university_system.modules.domain.academics.grading.grade_tracking import (
    init_basic_database,
    init_enhanced_grades_db,
    display_enhanced_grade_menu,
    grade_curve_analysis_menu,
    learning_outcome_menu,
    competency_assessment_menu,
    predictive_analytics_menu,
    performance_analysis_menu
)
from education_system.university_system.infrastructure.database.db import get_connection

@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database"""
    db_path = tmp_path / "test_student_records.db"

    # Patch get_connection to use our test database
    original_get_connection = get_connection

    def mock_get_connection():
        return sqlite3.connect(str(db_path))

    with patch('education_system.university_system.infrastructure.database.db.get_connection', mock_get_connection):
        with patch('education_system.university_system.modules.domain.academics.grading.grade_tracking.get_connection', mock_get_connection):
            yield mock_get_connection

class TestDatabaseInitialization:
    """Tests for database initialization functions"""

    def test_init_basic_database_creates_tables(self, test_db):
        """Test that init_basic_database creates all required tables"""
        result = init_basic_database()
        assert result is True

        conn = test_db()
        cursor = conn.cursor()

        # Check that all tables exist
        tables = ['students', 'modules', 'student_modules', 'assessments']
        for table in tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            assert cursor.fetchone() is not None, f"Table {table} was not created"

        conn.close()

    def test_init_basic_database_students_table_structure(self, test_db):
        """Test students table has correct columns"""
        init_basic_database()

        conn = test_db()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(students)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'student_id', 'first_name', 'middle_name', 'last_name',
            'course', 'email_address', 'gender', 'dob',
            'enrollment_date', 'status'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_init_basic_database_modules_table_structure(self, test_db):
        """Test modules table has correct columns"""
        init_basic_database()

        conn = test_db()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(modules)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'module_code', 'module_name', 'module_type',
            'credits', 'description', 'course',
            'semester', 'year'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_init_basic_database_assessments_table_structure(self, test_db):
        """Test assessments table has correct columns"""
        init_basic_database()

        conn = test_db()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(assessments)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'assessment_id', 'assessment_name', 'assessment_type',
            'module_code', 'max_points', 'weight',
            'due_date', 'date_created', 'description'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_init_basic_database_idempotent(self, test_db):
        """Test that running init_basic_database multiple times is safe"""
        # Run twice
        result1 = init_basic_database()
        result2 = init_basic_database()

        assert result1 is True
        assert result2 is True

        # Verify tables still exist
        conn = test_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        )
        count = cursor.fetchone()[0]
        assert count >= 4  # At least the 4 basic tables
        conn.close()

    def test_init_enhanced_grades_db_creates_tables(self, test_db):
        """Test that init_enhanced_grades_db creates all enhanced tables"""
        init_basic_database()  # Create base tables first
        result = init_enhanced_grades_db()
        assert result is True

        conn = test_db()
        cursor = conn.cursor()

        # Check that enhanced tables exist
        enhanced_tables = [
            'grades', 'module_grades', 'grade_statistics',
            'normalized_grades', 'learning_outcomes', 'assessment_outcomes',
            'outcome_results', 'competencies', 'competency_levels',
            'assessment_competencies', 'student_competencies',
            'risk_factors', 'student_risk_assessment', 'risk_details',
            'intervention_types', 'recommended_interventions'
        ]

        for table in enhanced_tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            assert cursor.fetchone() is not None, f"Enhanced table {table} was not created"

        conn.close()

    def test_init_enhanced_grades_db_inserts_default_data(self, test_db):
        """Test that init_enhanced_grades_db inserts default risk factors and intervention types"""
        init_basic_database()
        init_enhanced_grades_db()

        conn = test_db()
        cursor = conn.cursor()

        # Check risk factors
        cursor.execute("SELECT COUNT(*) FROM risk_factors")
        risk_factor_count = cursor.fetchone()[0]
        assert risk_factor_count > 0, "No default risk factors were inserted"

        # Check intervention types
        cursor.execute("SELECT COUNT(*) FROM intervention_types")
        intervention_count = cursor.fetchone()[0]
        assert intervention_count > 0, "No default intervention types were inserted"

        conn.close()

    def test_init_enhanced_grades_db_risk_factors_structure(self, test_db):
        """Test risk_factors table structure"""
        init_basic_database()
        init_enhanced_grades_db()

        conn = test_db()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(risk_factors)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {'factor_id', 'name', 'description', 'weight'}
        assert expected_columns.issubset(columns)
        conn.close()

    def test_init_enhanced_grades_db_idempotent_default_data(self, test_db):
        """Test that default data is not duplicated on multiple runs"""
        init_basic_database()
        init_enhanced_grades_db()
        init_enhanced_grades_db()  # Run again

        conn = test_db()
        cursor = conn.cursor()

        # Count should remain the same
        cursor.execute("SELECT COUNT(*) FROM risk_factors")
        count = cursor.fetchone()[0]
        assert count == 6, "Default risk factors were duplicated"

        cursor.execute("SELECT COUNT(*) FROM intervention_types")
        count = cursor.fetchone()[0]
        assert count == 6, "Default intervention types were duplicated"

        conn.close()

class TestMenuFunctions:
    """Tests for menu display and navigation functions"""

    @patch('builtins.input', side_effect=['11'])  # Exit immediately
    @patch('builtins.print')
    def test_display_enhanced_grade_menu_basic(self, mock_print, mock_input, test_db):
        """Test that display_enhanced_grade_menu can be called without errors"""
        init_basic_database()
        display_enhanced_grade_menu()

        # Verify menu was printed
        assert any('Grade and Performance Tracking' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['6'])  # Exit immediately
    @patch('builtins.print')
    def test_grade_curve_analysis_menu_basic(self, mock_print, mock_input, test_db):
        """Test that grade_curve_analysis_menu can be called"""
        init_basic_database()
        grade_curve_analysis_menu()

        # Verify menu was printed
        assert any('Grade Curve Analysis' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['6'])  # Exit immediately
    @patch('builtins.print')
    def test_learning_outcome_menu_basic(self, mock_print, mock_input, test_db):
        """Test that learning_outcome_menu can be called"""
        init_basic_database()
        init_enhanced_grades_db()
        learning_outcome_menu()

        # Verify menu was printed
        assert any('Learning Outcome Tracking' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['7'])  # Exit immediately
    @patch('builtins.print')
    def test_competency_assessment_menu_basic(self, mock_print, mock_input, test_db):
        """Test that competency_assessment_menu can be called"""
        init_basic_database()
        init_enhanced_grades_db()
        competency_assessment_menu()

        # Verify menu was printed
        assert any('Competency-Based Assessment' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['10'])  # Exit immediately
    @patch('builtins.print')
    def test_predictive_analytics_menu_basic(self, mock_print, mock_input, test_db):
        """Test that predictive_analytics_menu can be called"""
        init_basic_database()
        init_enhanced_grades_db()
        predictive_analytics_menu()

        # Verify menu was printed
        assert any('Predictive Analytics' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['9'])  # Exit immediately
    @patch('builtins.print')
    def test_performance_analysis_menu_basic(self, mock_print, mock_input, test_db):
        """Test that performance_analysis_menu can be called"""
        init_basic_database()
        init_enhanced_grades_db()
        performance_analysis_menu()

        # Verify menu was printed
        assert any('Performance Analysis' in str(call) for call in mock_print.call_args_list)

class TestDatabaseIntegrity:
    """Tests for database integrity and constraints"""

    def test_student_modules_foreign_keys(self, test_db):
        """Test that student_modules enforces foreign key constraints"""
        init_basic_database()

        conn = test_db()
        cursor = conn.cursor()

        # Try to insert a student_module with non-existent student
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO student_modules (student_id, module_code)
                VALUES ('NONEXISTENT', 'TEST101')
            """)
            conn.commit()

        conn.close()

    def test_unique_constraint_student_modules(self, test_db):
        """Test that student_modules enforces unique constraint"""
        init_basic_database()

        conn = test_db()
        cursor = conn.cursor()

        # Insert a student and module first
        cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, course)
            VALUES ('TEST001', 'Test', 'Student', 'CS')
        """)
        cursor.execute("""
            INSERT INTO modules (module_code, module_name)
            VALUES ('CS101', 'Intro to CS')
        """)
        conn.commit()

        # Insert student_module
        cursor.execute("""
            INSERT INTO student_modules (student_id, module_code)
            VALUES ('TEST001', 'CS101')
        """)
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO student_modules (student_id, module_code)
                VALUES ('TEST001', 'CS101')
            """)
            conn.commit()

        conn.close()

class TestErrorHandling:
    """Tests for error handling in grade tracking functions"""

    @patch('education_system.university_system.modules.domain.academics.grading.grade_tracking.get_connection')
    @patch('builtins.print')
    def test_init_basic_database_handles_errors(self, mock_print, mock_conn):
        """Test that init_basic_database handles database errors gracefully"""
        mock_conn.side_effect = sqlite3.Error("Test error")

        result = init_basic_database()
        assert result is False

        # Check that error was printed
        assert any('Database error' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.university_system.modules.domain.academics.grading.grade_tracking.get_connection')
    @patch('builtins.print')
    def test_init_enhanced_grades_db_handles_errors(self, mock_print, mock_conn):
        """Test that init_enhanced_grades_db handles database errors gracefully"""
        mock_conn.side_effect = sqlite3.Error("Test error")

        result = init_enhanced_grades_db()
        assert result is False

        # Check that error was printed
        assert any('Database error' in str(call) for call in mock_print.call_args_list)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
