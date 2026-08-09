import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import numpy as np

from education_system.systems.university.domain.assessment.grading.grade_calculation import (
    GRADE_SYSTEMS,
    percentage_to_letter,
    letter_to_percentage,
    init_enhanced_grades_db,
    display_enhanced_grade_menu,
    select_student,
    calculate_trend_slope,
    create_trend_visualization,
    export_batch_predictions,
    extract_student_features
)

class TestGradeConstants:
    """Test the GRADE_SYSTEMS constant"""

    def test_grade_systems_structure(self):
        """Test that GRADE_SYSTEMS has correct structure"""
        assert 'letter' in GRADE_SYSTEMS
        assert isinstance(GRADE_SYSTEMS['letter'], dict)

    def test_grade_systems_has_all_grades(self):
        """Test that all standard letter grades are present"""
        expected_grades = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']

        for grade in expected_grades:
            assert grade in GRADE_SYSTEMS['letter']

    def test_grade_systems_gpa_values(self):
        """Test that GPA values are in correct range"""
        for grade, gpa in GRADE_SYSTEMS['letter'].items():
            assert 0.0 <= gpa <= 4.3

    def test_grade_systems_descending_order(self):
        """Test that GPA values are in descending order for letter grades"""
        gpas = list(GRADE_SYSTEMS['letter'].values())

        # A+ should be highest
        assert gpas[0] == 4.3

        # F should be lowest
        assert GRADE_SYSTEMS['letter']['F'] == 0.0

class TestPercentageToLetter:
    """Test the percentage_to_letter function"""

    def test_percentage_to_letter_a_plus(self):
        """Test conversion to A+"""
        assert percentage_to_letter(100) == 'A+'
        assert percentage_to_letter(97) == 'A+'

    def test_percentage_to_letter_a(self):
        """Test conversion to A"""
        assert percentage_to_letter(95) == 'A'
        assert percentage_to_letter(93) == 'A'

    def test_percentage_to_letter_b(self):
        """Test conversion to B grades"""
        assert percentage_to_letter(87) == 'B+'
        assert percentage_to_letter(85) == 'B'
        assert percentage_to_letter(80) == 'B-'

    def test_percentage_to_letter_c(self):
        """Test conversion to C grades"""
        assert percentage_to_letter(77) == 'C+'
        assert percentage_to_letter(75) == 'C'
        assert percentage_to_letter(70) == 'C-'

    def test_percentage_to_letter_d(self):
        """Test conversion to D grades"""
        assert percentage_to_letter(67) == 'D+'
        assert percentage_to_letter(65) == 'D'
        assert percentage_to_letter(60) == 'D-'

    def test_percentage_to_letter_f(self):
        """Test conversion to F"""
        assert percentage_to_letter(59) == 'F'
        assert percentage_to_letter(0) == 'F'

    def test_percentage_to_letter_boundary_cases(self):
        """Test boundary cases"""
        assert percentage_to_letter(96.9) == 'A'
        assert percentage_to_letter(97.0) == 'A+'

class TestLetterToPercentage:
    """Test the letter_to_percentage function"""

    def test_letter_to_percentage_all_grades(self):
        """Test conversion for all letter grades"""
        for letter in ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']:
            result = letter_to_percentage(letter)
            assert isinstance(result, (int, float))
            assert 0 <= result <= 100

    def test_letter_to_percentage_ordering(self):
        """Test that higher grades convert to higher percentages"""
        assert letter_to_percentage('A+') > letter_to_percentage('A')
        assert letter_to_percentage('A') > letter_to_percentage('B')
        assert letter_to_percentage('B') > letter_to_percentage('C')

    def test_letter_to_percentage_invalid_grade(self):
        """Test with invalid letter grade"""
        result = letter_to_percentage('Z')
        assert result == 0

class TestInitEnhancedGradesDb:
    """Test the init_enhanced_grades_db function"""

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.get_connection')
    def test_init_enhanced_grades_db_success(self, mock_get_conn):
        """Test successful database initialization"""
        conn = Mock()
        cursor = Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = (0,)  # No existing data

        result = init_enhanced_grades_db()

        assert result is True
        conn.commit.assert_called()
        conn.close.assert_called()

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.get_connection')
    def test_init_enhanced_grades_db_with_existing_data(self, mock_get_conn):
        """Test initialization with existing data"""
        conn = Mock()
        cursor = Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = (5,)  # Existing risk factors

        result = init_enhanced_grades_db()

        assert result is True

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.get_connection')
    @patch('builtins.print')
    def test_init_enhanced_grades_db_error(self, mock_print, mock_get_conn):
        """Test database initialization error handling"""
        mock_get_conn.side_effect = sqlite3.Error("Database error")

        result = init_enhanced_grades_db()

        assert result is False
        mock_print.assert_called()

class TestDisplayEnhancedGradeMenu:
    """Test the display_enhanced_grade_menu function"""

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.init_basic_database')
    @patch('builtins.input', return_value='11')  # Return to main menu
    @patch('builtins.print')
    def test_display_enhanced_grade_menu_exit(self, mock_print, mock_input, mock_init):
        """Test exiting the grade menu"""
        mock_init.return_value = True

        with patch('education_system.systems.university.domain.assessment.grading.grade_calculation.init_enhanced_grades_db'):
            display_enhanced_grade_menu()

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.init_basic_database')
    @patch('builtins.input', side_effect=['1', '11'])  # Select option 1, then exit
    @patch('builtins.print')
    def test_display_enhanced_grade_menu_record_grades(
        self, mock_print, mock_input, mock_init
    ):
        """Test selecting record grades option"""
        mock_init.return_value = True

        with patch('education_system.systems.university.domain.assessment.grading.grade_calculation.init_enhanced_grades_db'):
            with patch('education_system.systems.university.domain.assessment.grading.grade_calculation.record_assessment_grades'):
                display_enhanced_grade_menu()

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.init_basic_database')
    def test_display_enhanced_grade_menu_init_failure(self, mock_init):
        """Test when database initialization fails"""
        mock_init.return_value = False

        with patch('builtins.print') as mock_print:
            display_enhanced_grade_menu()

        assert any('Failed' in str(call) for call in mock_print.call_args_list)

class TestSelectStudent:
    """Test the select_student function"""

    @pytest.fixture
    def cursor_with_students(self):
        """Create mock cursor with student data"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('S001', 'John', 'M', 'Doe', 'CS'),
            ('S002', 'Jane', '', 'Smith', 'DS'),
        ]
        return cursor

    @patch('builtins.input', return_value='1')
    @patch('builtins.print')
    def test_select_student_valid(self, mock_print, mock_input, cursor_with_students):
        """Test selecting a valid student"""
        result = select_student(cursor_with_students)

        assert result == 'S001'

    @patch('builtins.input', return_value='0')
    @patch('builtins.print')
    def test_select_student_invalid_index(
        self, mock_print, mock_input, cursor_with_students
    ):
        """Test selecting with invalid index"""
        result = select_student(cursor_with_students)

        assert result is None
        mock_print.assert_any_call("Invalid selection.")

    @patch('builtins.input', return_value='abc')
    @patch('builtins.print')
    def test_select_student_non_numeric(
        self, mock_print, mock_input, cursor_with_students
    ):
        """Test selecting with non-numeric input"""
        result = select_student(cursor_with_students)

        assert result is None

    @patch('builtins.print')
    def test_select_student_no_students(self, mock_print):
        """Test when no students exist"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        result = select_student(cursor)

        assert result is None
        mock_print.assert_any_call("No students found.")

class TestCalculateTrendSlope:
    """Test the calculate_trend_slope function"""

    def test_calculate_trend_slope_increasing(self):
        """Test with increasing trend"""
        values = [10, 20, 30, 40, 50]
        slope = calculate_trend_slope(values)

        assert slope > 0

    def test_calculate_trend_slope_decreasing(self):
        """Test with decreasing trend"""
        values = [50, 40, 30, 20, 10]
        slope = calculate_trend_slope(values)

        assert slope < 0

    def test_calculate_trend_slope_flat(self):
        """Test with flat trend"""
        values = [25, 25, 25, 25, 25]
        slope = calculate_trend_slope(values)

        assert abs(slope) < 0.001

    def test_calculate_trend_slope_insufficient_data(self):
        """Test with insufficient data"""
        values = [10]
        slope = calculate_trend_slope(values)

        assert slope == 0

    def test_calculate_trend_slope_empty(self):
        """Test with empty list"""
        values = []
        slope = calculate_trend_slope(values)

        assert slope == 0

class TestCreateTrendVisualization:
    """Test the create_trend_visualization function"""

    @pytest.fixture
    def sample_trend_data(self):
        """Create sample trend data"""
        daily = [('2025-01-01', 85.0, 50), ('2025-01-02', 87.0, 48)]
        monthly = [('2025-01', 86.0, 150), ('2025-02', 88.0, 145)]
        return daily, monthly

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.plt')
    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.os.makedirs')
    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.os.path.exists')
    @patch('builtins.print')
    def test_create_trend_visualization_success(
        self, mock_print, mock_exists, mock_makedirs, mock_plt, sample_trend_data
    ):
        """Test successful trend visualization creation"""
        mock_exists.return_value = False
        daily, monthly = sample_trend_data

        create_trend_visualization(daily, monthly, 'test')

        mock_plt.savefig.assert_called_once()
        mock_plt.close.assert_called_once()

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.plt')
    @patch('builtins.print')
    def test_create_trend_visualization_error(
        self, mock_print, mock_plt, sample_trend_data
    ):
        """Test error handling in visualization"""
        mock_plt.savefig.side_effect = Exception("Save error")
        daily, monthly = sample_trend_data

        create_trend_visualization(daily, monthly, 'test')

        assert any('Error' in str(call) for call in mock_print.call_args_list)

class TestExportBatchPredictions:
    """Test the export_batch_predictions function"""

    @pytest.fixture
    def sample_predictions(self):
        """Create sample prediction data"""
        return [
            {'student_id': 'S001', 'risk_score': 75, 'risk_level': 'High'},
            {'student_id': 'S002', 'risk_score': 35, 'risk_level': 'Medium'},
        ]

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.os.makedirs')
    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.os.path.exists')
    @patch('builtins.open', create=True)
    @patch('builtins.print')
    def test_export_batch_predictions_success(
        self, mock_print, mock_open, mock_exists, mock_makedirs, sample_predictions
    ):
        """Test successful predictions export"""
        mock_exists.return_value = False
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        export_batch_predictions(sample_predictions, 'test_predictions')

        assert any('exported' in str(call).lower() for call in mock_print.call_args_list)

    @patch('education_system.systems.university.domain.assessment.grading.grade_calculation.os.makedirs')
    @patch('builtins.open', side_effect=Exception("Write error"))
    @patch('builtins.print')
    def test_export_batch_predictions_error(
        self, mock_print, mock_open, mock_makedirs, sample_predictions
    ):
        """Test error handling in predictions export"""
        export_batch_predictions(sample_predictions, 'test_predictions')

        assert any('Error' in str(call) for call in mock_print.call_args_list)

class TestExtractStudentFeatures:
    """Test the extract_student_features function"""

    @pytest.fixture
    def feature_cursor(self):
        """Create mock cursor for feature extraction"""
        cursor = Mock()
        cursor.execute.return_value = cursor
        # Assessment scores - multiple queries may call fetchall/fetchone
        cursor.fetchall.side_effect = [
            [(85.0, 'A'), (78.0, 'B'), (92.0, 'A')],  # grade data
            [],  # any follow-up queries
            [],
        ]
        cursor.fetchone.return_value = (3,)  # count of records

        return cursor

    def test_extract_student_features_success(self, feature_cursor):
        """Test successful feature extraction"""
        features = extract_student_features(feature_cursor, 'S001')
        assert features is not None
        assert isinstance(features, dict)

    def test_extract_student_features_no_data(self):
        """Test feature extraction with no data"""
        cursor = Mock()
        cursor.execute.return_value = cursor
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = None

        features = extract_student_features(cursor, 'S999')
        # Should handle empty data gracefully (returns None or empty dict)
        assert features is None or isinstance(features, dict)

class TestGradeCalculationIntegration:
    """Integration tests for grade calculation"""

    @pytest.fixture
    def temp_db_full_schema(self):
        """Create temporary database with full schema"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create minimal schema for testing
        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                course TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE grades (
                grade_id INTEGER PRIMARY KEY,
                student_id TEXT,
                assessment_id INTEGER,
                score REAL,
                letter_grade TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE assessments (
                assessment_id INTEGER PRIMARY KEY,
                module_code TEXT,
                max_points REAL
            )
        ''')

        # Insert test data
        cursor.execute("INSERT INTO students VALUES ('S001', 'John', 'M', 'Doe', 'CS')")
        cursor.execute("INSERT INTO assessments VALUES (1, 'CS101', 100)")
        cursor.execute("INSERT INTO grades VALUES (1, 'S001', 1, 85.0, 'B')")

        conn.commit()

        yield conn

        conn.close()
        os.unlink(db_path)

    def test_grade_retrieval_integration(self, temp_db_full_schema):
        """Test retrieving grades from database"""
        cursor = temp_db_full_schema.cursor()

        cursor.execute('''
            SELECT score, letter_grade
            FROM grades
            WHERE student_id = 'S001'
        ''')

        grades = cursor.fetchall()

        assert len(grades) == 1
        assert grades[0][0] == 85.0
        assert grades[0][1] == 'B'

    def test_percentage_to_letter_integration(self):
        """Test percentage to letter conversion in realistic scenario"""
        test_cases = [
            (98, 'A+'),
            (95, 'A'),
            (85, 'B'),
            (75, 'C'),
            (65, 'D'),
            (55, 'F'),
        ]

        for percentage, expected_letter in test_cases:
            result = percentage_to_letter(percentage)
            assert result == expected_letter, f"Failed for {percentage}%"

class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_percentage_to_letter_with_float(self):
        """Test with floating point percentage"""
        assert percentage_to_letter(85.5) == 'B'
        assert percentage_to_letter(92.7) == 'A-'

    def test_letter_to_percentage_case_sensitive(self):
        """Test case sensitivity of letter grades"""
        # Function should handle as implemented
        result = letter_to_percentage('a+')
        assert isinstance(result, (int, float))

    def test_calculate_trend_slope_with_numpy_array(self):
        """Test trend slope calculation with numpy array"""
        values = np.array([10, 20, 30, 40, 50])
        slope = calculate_trend_slope(values)

        assert slope > 0

    def test_select_student_with_special_characters(self):
        """Test selecting student with special characters in name"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('S001', "O'Brien", '', "Smith-Jones", 'CS'),
        ]

        with patch('builtins.input', return_value='1'):
            with patch('builtins.print'):
                result = select_student(cursor)

        assert result == 'S001'

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
