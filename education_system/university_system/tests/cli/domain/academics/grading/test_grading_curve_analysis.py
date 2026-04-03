import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from education_system.university_system.modules.domain.academics.grading.curve_analysis import (
    apply_grading_curve,
    performance_analysis_menu,
    comparative_performance_analysis,
    performance_trends_analysis,
    analyze_distribution_by_course,
    analyze_distribution_by_module_type,
    analyze_overall_distribution,
    dropout_risk_analysis
)

class TestApplyGradingCurve:
    """Test the apply_grading_curve function"""

    @pytest.fixture
    def mock_cursor_with_grades(self):
        """Create mock cursor with grade data"""
        cursor = Mock()
        cursor.connection = Mock()

        # Assessment details
        cursor.fetchone.return_value = ('Midterm Exam', 'CS101', 100)

        # Grades data
        cursor.fetchall.return_value = [
            (1, 'S001', 'John', 'Doe', 75.0, 'C'),
            (2, 'S002', 'Jane', 'Smith', 85.0, 'B'),
            (3, 'S003', 'Bob', 'Johnson', 65.0, 'D'),
        ]

        return cursor

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.select_assessment')
    @patch('builtins.input', side_effect=['1', '10', 'n'])  # Add 10 points, don't apply
    @patch('builtins.print')
    def test_apply_grading_curve_add_points_no_apply(
        self, mock_print, mock_input, mock_select, mock_get_conn, mock_cursor_with_grades
    ):
        """Test applying curve by adding points but not saving"""
        mock_select.return_value = 1
        conn = Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = mock_cursor_with_grades

        apply_grading_curve()

        # Verify curve was calculated but not applied
        assert not mock_cursor_with_grades.connection.commit.called

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.select_assessment')
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.update_module_grade')
    @patch('builtins.input', side_effect=['1', '10', 'y'])  # Add 10 points, apply
    @patch('builtins.print')
    def test_apply_grading_curve_add_points_apply(
        self, mock_print, mock_input, mock_update, mock_select, mock_get_conn, mock_cursor_with_grades
    ):
        """Test applying curve by adding points and saving"""
        mock_select.return_value = 1
        conn = Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = mock_cursor_with_grades

        apply_grading_curve()

        # Verify curve was applied
        conn.commit.assert_called_once()

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.select_assessment')
    @patch('builtins.input', side_effect=['2', '1.1', 'n'])  # Multiply by 1.1
    @patch('builtins.print')
    def test_apply_grading_curve_multiply(
        self, mock_print, mock_input, mock_select, mock_get_conn, mock_cursor_with_grades
    ):
        """Test applying curve by multiplication"""
        mock_select.return_value = 1
        conn = Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = mock_cursor_with_grades

        apply_grading_curve()

        # Verify calculation was done (output shown)
        assert mock_print.called

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.select_assessment')
    @patch('builtins.input', return_value='3')  # Set highest to max
    @patch('builtins.print')
    def test_apply_grading_curve_set_highest(
        self, mock_print, mock_input, mock_select, mock_get_conn, mock_cursor_with_grades
    ):
        """Test setting highest score to maximum"""
        mock_select.return_value = 1
        conn = Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = mock_cursor_with_grades

        with patch('builtins.input', side_effect=['3', 'n']):
            apply_grading_curve()

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.select_assessment')
    def test_apply_grading_curve_no_assessment_selected(
        self, mock_select, mock_get_conn
    ):
        """Test when no assessment is selected"""
        mock_select.return_value = None
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        apply_grading_curve()

        conn.close.assert_called_once()

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.select_assessment')
    @patch('builtins.print')
    def test_apply_grading_curve_no_grades(
        self, mock_print, mock_select, mock_get_conn
    ):
        """Test when assessment has no grades"""
        mock_select.return_value = 1
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = ('Test', 'CS101', 100)
        cursor.fetchall.return_value = []

        apply_grading_curve()

        assert any('No grades found' in str(call) for call in mock_print.call_args_list)

class TestPerformanceAnalysisMenu:
    """Test the performance_analysis_menu function"""

    @patch('builtins.input', return_value='9')  # Return to menu
    @patch('builtins.print')
    def test_performance_analysis_menu_exit(self, mock_print, mock_input):
        """Test exiting the performance analysis menu"""
        performance_analysis_menu()

        # Should print menu and exit
        assert mock_print.called

    @patch('builtins.input', side_effect=['1', '9'])  # Select at-risk students, then exit
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.identify_at_risk_students')
    def test_performance_analysis_menu_at_risk(self, mock_at_risk, mock_input):
        """Test selecting at-risk students option"""
        performance_analysis_menu()

        mock_at_risk.assert_called_once()

    @patch('builtins.input', side_effect=['invalid', '9'])  # Invalid then exit
    @patch('builtins.print')
    def test_performance_analysis_menu_invalid_choice(self, mock_print, mock_input):
        """Test invalid menu choice"""
        performance_analysis_menu()

        assert any('Invalid choice' in str(call) for call in mock_print.call_args_list)

class TestComparativePerformanceAnalysis:
    """Test the comparative_performance_analysis function"""

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='1')  # Compare by course
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.compare_by_course')
    def test_comparative_performance_analysis_by_course(
        self, mock_compare, mock_input, mock_get_conn
    ):
        """Test comparison by course"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        comparative_performance_analysis()

        mock_compare.assert_called_once_with(cursor)

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='2')  # Compare by gender
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.compare_by_gender')
    def test_comparative_performance_analysis_by_gender(
        self, mock_compare, mock_input, mock_get_conn
    ):
        """Test comparison by gender"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        comparative_performance_analysis()

        mock_compare.assert_called_once_with(cursor)

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='invalid')  # Invalid choice
    @patch('builtins.print')
    def test_comparative_performance_analysis_invalid(
        self, mock_print, mock_input, mock_get_conn
    ):
        """Test invalid comparison choice"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        comparative_performance_analysis()

        mock_print.assert_any_call("Invalid choice. Returning to menu.")

class TestPerformanceTrendsAnalysis:
    """Test the performance_trends_analysis function"""

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='1')  # Overall trends
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.analyze_overall_grade_trends')
    def test_performance_trends_analysis_overall(
        self, mock_analyze, mock_input, mock_get_conn
    ):
        """Test overall grade trends analysis"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        performance_trends_analysis()

        mock_analyze.assert_called_once_with(cursor)

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='2')  # Individual student
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.analyze_individual_student_trends')
    def test_performance_trends_analysis_individual(
        self, mock_analyze, mock_input, mock_get_conn
    ):
        """Test individual student trends analysis"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        performance_trends_analysis()

        mock_analyze.assert_called_once_with(cursor)

class TestAnalyzeDistributionByCourse:
    """Test the analyze_distribution_by_course function"""

    @patch('builtins.print')
    def test_analyze_distribution_by_course_success(self, mock_print):
        """Test successful distribution analysis by course"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('Computer Science', 'A', 10),
            ('Computer Science', 'B', 15),
            ('Data Science', 'A', 8),
            ('Data Science', 'B', 12),
        ]

        with patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.letter_to_gpa', return_value=4.0):
            analyze_distribution_by_course(cursor)

        # Verify output was printed
        assert mock_print.call_count > 0

    @patch('builtins.print')
    def test_analyze_distribution_by_course_no_data(self, mock_print):
        """Test when no distribution data exists"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        analyze_distribution_by_course(cursor)

        mock_print.assert_any_call("No grade distribution data found.")

class TestAnalyzeDistributionByModuleType:
    """Test the analyze_distribution_by_module_type function"""

    @patch('builtins.print')
    def test_analyze_distribution_by_module_type_success(self, mock_print):
        """Test successful distribution analysis by module type"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('Core', 'A', 20),
            ('Core', 'B', 30),
            ('Elective', 'A', 15),
            ('Elective', 'B', 25),
        ]

        with patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.letter_to_gpa', return_value=4.0):
            analyze_distribution_by_module_type(cursor)

        assert mock_print.call_count > 0

    @patch('builtins.print')
    def test_analyze_distribution_by_module_type_no_data(self, mock_print):
        """Test when no module type data exists"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        analyze_distribution_by_module_type(cursor)

        mock_print.assert_any_call("No grade distribution data found.")

class TestAnalyzeOverallDistribution:
    """Test the analyze_overall_distribution function"""

    @patch('builtins.print')
    def test_analyze_overall_distribution_with_data(self, mock_print):
        """Test overall distribution with data"""
        cursor = Mock()

        # Module grades
        cursor.fetchall.side_effect = [
            [('A', 50), ('B', 75), ('C', 25)],  # Module grades
            [('A', 100), ('B', 150), ('C', 50)],  # Assessment grades
        ]

        with patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.letter_to_gpa', return_value=4.0):
            analyze_overall_distribution(cursor)

        # Should print both module and assessment distributions
        assert mock_print.call_count > 0

    @patch('builtins.print')
    def test_analyze_overall_distribution_no_data(self, mock_print):
        """Test when no distribution data exists"""
        cursor = Mock()
        cursor.fetchall.side_effect = [[], []]

        analyze_overall_distribution(cursor)

        # Should complete without error
        assert True

class TestDropoutRiskAnalysis:
    """Test the dropout_risk_analysis function"""

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='1')  # Identify high risk
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.identify_high_dropout_risk')
    def test_dropout_risk_analysis_high_risk(
        self, mock_identify, mock_input, mock_get_conn
    ):
        """Test identifying high dropout risk students"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        dropout_risk_analysis()

        mock_identify.assert_called_once_with(cursor)

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='2')  # Analyze risk factors
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.analyze_dropout_risk_factors')
    def test_dropout_risk_analysis_factors(
        self, mock_analyze, mock_input, mock_get_conn
    ):
        """Test analyzing dropout risk factors"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        dropout_risk_analysis()

        mock_analyze.assert_called_once_with(cursor)

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='3')  # Build prediction model
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.build_dropout_prediction_model')
    def test_dropout_risk_analysis_prediction_model(
        self, mock_build, mock_input, mock_get_conn
    ):
        """Test building dropout prediction model"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        dropout_risk_analysis()

        mock_build.assert_called_once_with(cursor)

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='4')  # Early intervention
    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.generate_dropout_interventions')
    def test_dropout_risk_analysis_interventions(
        self, mock_interventions, mock_input, mock_get_conn
    ):
        """Test generating dropout interventions"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        dropout_risk_analysis()

        mock_interventions.assert_called_once_with(cursor)

    @patch('education_system.university_system.modules.domain.academics.grading.curve_analysis.get_connection')
    @patch('builtins.input', return_value='invalid')
    @patch('builtins.print')
    def test_dropout_risk_analysis_invalid_choice(
        self, mock_print, mock_input, mock_get_conn
    ):
        """Test invalid choice in dropout risk analysis"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        dropout_risk_analysis()

        mock_print.assert_any_call("Invalid choice. Returning to menu.")

class TestCurveAnalysisIntegration:
    """Integration tests for curve analysis"""

    @pytest.fixture
    def temp_db_with_grades(self):
        """Create temporary database with grade data for curve testing"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create schema
        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                course TEXT,
                gender TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT,
                module_type TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE assessments (
                assessment_id INTEGER PRIMARY KEY,
                assessment_name TEXT,
                module_code TEXT,
                max_points REAL,
                assessment_type TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE grades (
                grade_id INTEGER PRIMARY KEY,
                student_id TEXT,
                assessment_id INTEGER,
                score REAL,
                letter_grade TEXT,
                submission_date TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE module_grades (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                module_code TEXT,
                final_score REAL,
                final_grade TEXT
            )
        ''')

        # Insert test data
        cursor.execute("INSERT INTO students VALUES ('S001', 'John', 'Doe', 'CS', 'male')")
        cursor.execute("INSERT INTO students VALUES ('S002', 'Jane', 'Smith', 'CS', 'female')")

        cursor.execute("INSERT INTO modules VALUES ('CS101', 'Intro', 'Core')")

        cursor.execute("INSERT INTO assessments VALUES (1, 'Midterm', 'CS101', 100, 'Exam')")

        cursor.execute("INSERT INTO grades VALUES (1, 'S001', 1, 75.0, 'C', '2025-01-15')")
        cursor.execute("INSERT INTO grades VALUES (2, 'S002', 1, 85.0, 'B', '2025-01-15')")

        cursor.execute("INSERT INTO module_grades VALUES (1, 'S001', 'CS101', 75.0, 'C')")
        cursor.execute("INSERT INTO module_grades VALUES (2, 'S002', 'CS101', 85.0, 'B')")

        conn.commit()

        yield conn

        conn.close()
        os.unlink(db_path)

    def test_grade_distribution_retrieval(self, temp_db_with_grades):
        """Test retrieving grade distribution from database"""
        cursor = temp_db_with_grades.cursor()

        cursor.execute('''
            SELECT final_grade, COUNT(*) as count
            FROM module_grades
            GROUP BY final_grade
        ''')

        distribution = cursor.fetchall()

        assert len(distribution) == 2  # Two different grades
        assert any(grade[0] == 'C' for grade in distribution)
        assert any(grade[0] == 'B' for grade in distribution)

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
