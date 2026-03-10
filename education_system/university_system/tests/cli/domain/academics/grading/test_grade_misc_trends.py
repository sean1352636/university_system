import pytest
import os
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import shutil
import numpy as np

from education_system.university_system.modules.domain.academics.grading.trends import (
    analyze_individual_student_trends,
    analyze_single_course_trends,
    analyze_seasonal_trends,
    analyze_monthly_patterns,
    analyze_day_of_week_patterns,
    analyze_academic_term_patterns,
    trend_forecasting,
    create_trend_visualization,
    create_individual_trend_visualization,
    create_course_comparison_charts
)

class TestAnalyzeIndividualStudentTrends:
    """Test the analyze_individual_student_trends function"""

    @pytest.fixture
    def mock_cursor_with_student(self):
        """Create mock cursor with student and grade data"""
        cursor = Mock()

        # Student info
        cursor.fetchone.return_value = ('John', 'Doe', 'Computer Science')

        # Student grades over time
        cursor.fetchall.return_value = [
            ('2025-01-15', 85.0, 'Quiz 1', 'CS101', 'Quiz'),
            ('2025-01-22', 78.0, 'Assignment 1', 'CS101', 'Assignment'),
            ('2025-01-29', 92.0, 'Quiz 2', 'CS101', 'Quiz'),
            ('2025-02-05', 88.0, 'Midterm', 'CS101', 'Exam'),
            ('2025-02-12', 75.0, 'Assignment 2', 'CS101', 'Assignment'),
            ('2025-02-19', 90.0, 'Quiz 3', 'CS101', 'Quiz'),
        ]

        return cursor

    @patch('university_system.modules.domain.academics.grade_misc.trends.select_student')
    @patch('university_system.modules.domain.academics.grade_misc.trends.create_individual_trend_visualization')
    @patch('university_system.modules.domain.academics.grade_misc.trends.calculate_trend_slope')
    @patch('builtins.print')
    def test_analyze_individual_student_trends_success(
        self, mock_print, mock_slope, mock_viz, mock_select, mock_cursor_with_student
    ):
        """Test successful analysis of individual student trends"""
        mock_select.return_value = 'S001'
        mock_slope.return_value = 0.5  # Improving trend

        analyze_individual_student_trends(mock_cursor_with_student)

        # Verify student was selected
        mock_select.assert_called_once()

        # Verify trend calculation
        mock_slope.assert_called()

        # Verify visualization was created
        mock_viz.assert_called_once()

        # Check that positive trend message was printed
        assert any('improvement' in str(call).lower() for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.academics.grade_misc.trends.select_student')
    @patch('builtins.print')
    def test_analyze_individual_student_trends_no_student(
        self, mock_print, mock_select
    ):
        """Test when no student is selected"""
        mock_select.return_value = None
        cursor = Mock()

        analyze_individual_student_trends(cursor)

        # Should return early
        assert not cursor.execute.called

    @patch('university_system.modules.domain.academics.grade_misc.trends.select_student')
    @patch('builtins.print')
    def test_analyze_individual_student_trends_student_not_found(
        self, mock_print, mock_select
    ):
        """Test when student ID doesn't exist"""
        mock_select.return_value = 'S999'
        cursor = Mock()
        cursor.fetchone.return_value = None

        analyze_individual_student_trends(cursor)

        mock_print.assert_any_call("Student not found.")

    @patch('university_system.modules.domain.academics.grade_misc.trends.select_student')
    @patch('builtins.print')
    def test_analyze_individual_student_trends_no_grades(
        self, mock_print, mock_select
    ):
        """Test when student has no grades"""
        mock_select.return_value = 'S001'
        cursor = Mock()
        cursor.fetchone.return_value = ('John', 'Doe', 'CS')
        cursor.fetchall.return_value = []

        analyze_individual_student_trends(cursor)

        mock_print.assert_any_call("No grades found for this student.")

    @patch('university_system.modules.domain.academics.grade_misc.trends.select_student')
    @patch('university_system.modules.domain.academics.grade_misc.trends.calculate_trend_slope')
    @patch('builtins.print')
    def test_analyze_individual_student_trends_declining(
        self, mock_print, mock_slope, mock_select
    ):
        """Test detection of declining performance"""
        mock_select.return_value = 'S001'
        mock_slope.return_value = -1.5  # Declining trend

        cursor = Mock()
        cursor.fetchone.return_value = ('John', 'Doe', 'CS')
        cursor.fetchall.return_value = [
            ('2025-01-15', 90.0, 'Quiz 1', 'CS101', 'Quiz'),
            ('2025-01-22', 85.0, 'Quiz 2', 'CS101', 'Quiz'),
            ('2025-01-29', 80.0, 'Quiz 3', 'CS101', 'Quiz'),
        ]

        with patch('university_system.modules.domain.academics.grade_misc.trends.create_individual_trend_visualization'):
            analyze_individual_student_trends(cursor)

        # Check that declining trend was detected
        assert any('declining' in str(call).lower() for call in mock_print.call_args_list)

class TestAnalyzeSingleCourseTrends:
    """Test the analyze_single_course_trends function"""

    @patch('university_system.modules.domain.academics.grade_misc.trends.calculate_trend_slope')
    @patch('builtins.print')
    def test_analyze_single_course_trends_success(
        self, mock_print, mock_slope
    ):
        """Test successful course trend analysis"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('2025-01', 85.0, 50),
            ('2025-02', 87.0, 48),
            ('2025-03', 89.0, 52),
        ]
        mock_slope.return_value = 2.0  # Improving trend

        analyze_single_course_trends(cursor, 'Computer Science')

        mock_slope.assert_called_once()
        assert any('Improving' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_analyze_single_course_trends_insufficient_data(self, mock_print):
        """Test when insufficient data for trend analysis"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('2025-01', 85.0, 50),
            ('2025-02', 87.0, 48),
        ]

        analyze_single_course_trends(cursor, 'Computer Science')

        mock_print.assert_any_call("Insufficient data for trend analysis (need at least 3 months)")

    @patch('university_system.modules.domain.academics.grade_misc.trends.calculate_trend_slope')
    @patch('builtins.print')
    def test_analyze_single_course_trends_declining(
        self, mock_print, mock_slope
    ):
        """Test detection of declining course trend"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('2025-01', 90.0, 50),
            ('2025-02', 85.0, 48),
            ('2025-03', 80.0, 52),
        ]
        mock_slope.return_value = -5.0

        analyze_single_course_trends(cursor, 'Computer Science')

        assert any('Declining' in str(call) for call in mock_print.call_args_list)

class TestAnalyzeSeasonalTrends:
    """Test the analyze_seasonal_trends function"""

    @patch('university_system.modules.domain.academics.grade_misc.trends.get_connection')
    @patch('builtins.input', side_effect=['1'])
    @patch('university_system.modules.domain.academics.grade_misc.trends.analyze_monthly_patterns')
    def test_analyze_seasonal_trends_monthly(
        self, mock_monthly, mock_input, mock_conn
    ):
        """Test monthly pattern analysis selection"""
        conn, cursor = Mock(), Mock()
        mock_conn.return_value = conn
        conn.cursor.return_value = cursor

        analyze_seasonal_trends(cursor)

        mock_monthly.assert_called_once_with(cursor)

    @patch('university_system.modules.domain.academics.grade_misc.trends.get_connection')
    @patch('builtins.input', side_effect=['2'])
    @patch('university_system.modules.domain.academics.grade_misc.trends.analyze_day_of_week_patterns')
    def test_analyze_seasonal_trends_day_of_week(
        self, mock_dow, mock_input, mock_conn
    ):
        """Test day of week pattern analysis selection"""
        conn, cursor = Mock(), Mock()
        mock_conn.return_value = conn
        conn.cursor.return_value = cursor

        analyze_seasonal_trends(cursor)

        mock_dow.assert_called_once_with(cursor)

    @patch('university_system.modules.domain.academics.grade_misc.trends.get_connection')
    @patch('builtins.input', side_effect=['3'])
    @patch('university_system.modules.domain.academics.grade_misc.trends.analyze_academic_term_patterns')
    def test_analyze_seasonal_trends_academic_term(
        self, mock_term, mock_input, mock_conn
    ):
        """Test academic term pattern analysis selection"""
        conn, cursor = Mock(), Mock()
        mock_conn.return_value = conn
        conn.cursor.return_value = cursor

        analyze_seasonal_trends(cursor)

        mock_term.assert_called_once_with(cursor)

    @patch('university_system.modules.domain.academics.grade_misc.trends.get_connection')
    @patch('builtins.input', side_effect=['invalid'])
    @patch('builtins.print')
    def test_analyze_seasonal_trends_invalid_choice(
        self, mock_print, mock_input, mock_conn
    ):
        """Test invalid choice handling"""
        conn, cursor = Mock(), Mock()
        mock_conn.return_value = conn
        conn.cursor.return_value = cursor

        analyze_seasonal_trends(cursor)

        mock_print.assert_any_call("Invalid choice.")

class TestAnalyzeMonthlyPatterns:
    """Test the analyze_monthly_patterns function"""

    @patch('builtins.print')
    def test_analyze_monthly_patterns_success(self, mock_print):
        """Test successful monthly pattern analysis"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('01', 85.5, 50),
            ('02', 87.2, 48),
            ('03', 89.0, 52),
            ('04', 86.5, 51),
        ]

        analyze_monthly_patterns(cursor)

        # Verify data was printed in table format
        assert mock_print.call_count > 4  # Headers + data rows

    @patch('builtins.print')
    def test_analyze_monthly_patterns_no_data(self, mock_print):
        """Test when no monthly data is available"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        analyze_monthly_patterns(cursor)

        mock_print.assert_any_call("Insufficient data for monthly pattern analysis.")

class TestAnalyzeDayOfWeekPatterns:
    """Test the analyze_day_of_week_patterns function"""

    @patch('builtins.print')
    def test_analyze_day_of_week_patterns_success(self, mock_print):
        """Test successful day of week pattern analysis"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('0', 82.5, 20),  # Sunday
            ('1', 85.0, 45),  # Monday
            ('2', 87.0, 50),  # Tuesday
            ('3', 86.5, 48),  # Wednesday
            ('4', 84.0, 47),  # Thursday
            ('5', 83.0, 30),  # Friday
        ]

        analyze_day_of_week_patterns(cursor)

        # Verify day names are printed
        assert any('Monday' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_analyze_day_of_week_patterns_no_data(self, mock_print):
        """Test when no daily data is available"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        analyze_day_of_week_patterns(cursor)

        mock_print.assert_any_call("Insufficient data for daily pattern analysis.")

class TestAnalyzeAcademicTermPatterns:
    """Test the analyze_academic_term_patterns function"""

    @patch('builtins.print')
    def test_analyze_academic_term_patterns_success(self, mock_print):
        """Test successful academic term pattern analysis"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('2024', 'Spring', 85.0, 150),
            ('2024', 'Summer', 82.0, 80),
            ('2024', 'Fall', 87.0, 160),
            ('2025', 'Spring', 88.0, 155),
        ]

        analyze_academic_term_patterns(cursor)

        # Verify terms are displayed
        assert any('Spring' in str(call) for call in mock_print.call_args_list)
        assert any('Fall' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_analyze_academic_term_patterns_no_data(self, mock_print):
        """Test when no term data is available"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        analyze_academic_term_patterns(cursor)

        mock_print.assert_any_call("Insufficient data for term pattern analysis.")

class TestTrendForecasting:
    """Test the trend_forecasting function"""

    @patch('university_system.modules.domain.academics.grade_misc.trends.get_connection')
    @patch('builtins.input', side_effect=['1'])
    def test_trend_forecasting_overall_performance(self, mock_input, mock_conn):
        """Test overall performance forecasting"""
        conn, cursor = Mock(), Mock()
        mock_conn.return_value = conn
        conn.cursor.return_value = cursor

        with patch(
            'university_system.modules.domain.academics.grading.performance_analytics.forecast_overall_performance'
        ) as mock_forecast:
            trend_forecasting()
            mock_forecast.assert_called_once_with(cursor)

    @patch('university_system.modules.domain.academics.grade_misc.trends.get_connection')
    @patch('builtins.input', side_effect=['3'])
    def test_trend_forecasting_module_difficulty(self, mock_input, mock_conn):
        """Test module difficulty forecasting"""
        conn, cursor = Mock(), Mock()
        mock_conn.return_value = conn
        conn.cursor.return_value = cursor

        # This should call forecast_module_difficulty if it exists
        trend_forecasting()

    @patch('university_system.modules.domain.academics.grade_misc.trends.get_connection')
    @patch('builtins.input', side_effect=['invalid'])
    @patch('builtins.print')
    def test_trend_forecasting_invalid_choice(self, mock_print, mock_input, mock_conn):
        """Test invalid choice in forecasting"""
        conn, cursor = Mock(), Mock()
        mock_conn.return_value = conn
        conn.cursor.return_value = cursor

        trend_forecasting()

        mock_print.assert_any_call("Invalid choice. Returning to menu.")

class TestCreateTrendVisualization:
    """Test the create_trend_visualization function"""

    @pytest.fixture
    def sample_trends(self):
        """Sample trend data"""
        daily = [
            ('2025-01-01', 85.0, 50),
            ('2025-01-02', 86.0, 48),
            ('2025-01-03', 87.0, 52),
        ]
        monthly = [
            ('2025-01', 85.5, 150),
            ('2025-02', 87.0, 145),
            ('2025-03', 88.5, 155),
        ]
        return daily, monthly

    @patch('university_system.modules.domain.academics.grade_misc.trends.plt')
    @patch('university_system.modules.domain.academics.grade_misc.trends.os.path.exists')
    @patch('university_system.modules.domain.academics.grade_misc.trends.os.makedirs')
    @patch('builtins.print')
    def test_create_trend_visualization_success(
        self, mock_print, mock_makedirs, mock_exists, mock_plt, sample_trends
    ):
        """Test successful trend visualization creation"""
        mock_exists.return_value = False
        daily, monthly = sample_trends

        create_trend_visualization(daily, monthly, 'test_chart')

        # Verify directory creation
        mock_makedirs.assert_called_once()

        # Verify plot was saved
        mock_plt.savefig.assert_called_once()
        mock_plt.close.assert_called_once()

        # Verify success message
        assert any('saved' in str(call).lower() for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.academics.grade_misc.trends.plt')
    @patch('builtins.print')
    def test_create_trend_visualization_error(self, mock_print, mock_plt):
        """Test error handling in visualization creation"""
        mock_plt.savefig.side_effect = Exception("Save error")

        create_trend_visualization([], [], 'test_chart')

        # Should handle error gracefully
        assert any('Error' in str(call) for call in mock_print.call_args_list)

class TestCreateIndividualTrendVisualization:
    """Test the create_individual_trend_visualization function"""

    @pytest.fixture
    def student_grades(self):
        """Sample student grades"""
        return [
            ('2025-01-15', 85.0, 'Quiz 1', 'CS101'),
            ('2025-01-22', 78.0, 'Assignment 1', 'CS101'),
            ('2025-01-29', 92.0, 'Quiz 2', 'CS101'),
        ]

    @patch('university_system.modules.domain.academics.grade_misc.trends.plt')
    @patch('university_system.modules.domain.academics.grade_misc.trends.os.makedirs')
    @patch('builtins.print')
    def test_create_individual_trend_visualization_success(
        self, mock_print, mock_makedirs, mock_plt, student_grades
    ):
        """Test successful individual trend visualization"""
        create_individual_trend_visualization(
            student_grades, 'S001', 'John', 'Doe'
        )

        # Verify plot was created and saved
        mock_plt.savefig.assert_called_once()
        mock_plt.close.assert_called_once()

        # Verify success message
        assert any('saved' in str(call).lower() for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.academics.grade_misc.trends.plt')
    @patch('builtins.print')
    def test_create_individual_trend_visualization_with_many_assessments(
        self, mock_print, mock_plt
    ):
        """Test visualization with many assessments"""
        # Create 20 assessments
        grades = [(f'2025-01-{i:02d}', 80.0 + i, f'Assessment {i}', 'CS101')
                  for i in range(1, 21)]

        create_individual_trend_visualization(grades, 'S001', 'John', 'Doe')

        # Should still create visualization
        mock_plt.savefig.assert_called_once()

class TestCreateCourseComparisonCharts:
    """Test the create_course_comparison_charts function"""

    @pytest.fixture
    def comparison_data(self):
        """Sample comparison data"""
        return [
            {
                'course': 'Computer Science',
                'avg_gpa': 3.5,
                'passing_rate': 92.0,
                'excellence_rate': 45.0,
                'std_dev': 0.8
            },
            {
                'course': 'Data Science',
                'avg_gpa': 3.3,
                'passing_rate': 88.0,
                'excellence_rate': 38.0,
                'std_dev': 0.9
            },
        ]

    @patch('university_system.modules.domain.academics.grade_misc.trends.plt')
    @patch('university_system.modules.domain.academics.grade_misc.trends.os.makedirs')
    @patch('builtins.print')
    def test_create_course_comparison_charts_success(
        self, mock_print, mock_makedirs, mock_plt, comparison_data
    ):
        """Test successful course comparison chart creation"""
        create_course_comparison_charts(comparison_data)

        # Verify plot was saved
        mock_plt.savefig.assert_called_once()
        mock_plt.close.assert_called_once()

        # Verify success message
        assert any('saved' in str(call).lower() for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.academics.grade_misc.trends.plt')
    @patch('builtins.print')
    def test_create_course_comparison_charts_error(
        self, mock_print, mock_plt, comparison_data
    ):
        """Test error handling in chart creation"""
        mock_plt.savefig.side_effect = Exception("Save error")

        # Should not raise exception
        create_course_comparison_charts(comparison_data)

class TestTrendIntegration:
    """Integration tests for trend analysis"""

    @pytest.fixture
    def temp_db_with_trends(self):
        """Create temporary database with trend data"""
        db_path = tempfile.mktemp(suffix='.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create schema
        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                course TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE assessments (
                assessment_id INTEGER PRIMARY KEY,
                assessment_name TEXT,
                module_code TEXT,
                assessment_type TEXT,
                max_points REAL
            )
        ''')

        cursor.execute('''
            CREATE TABLE grades (
                grade_id INTEGER PRIMARY KEY,
                student_id TEXT,
                assessment_id INTEGER,
                score REAL,
                submission_date TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE student_modules (
                student_id TEXT,
                module_code TEXT
            )
        ''')

        # Insert test data
        cursor.execute("INSERT INTO students VALUES ('S001', 'John', 'Doe', 'CS')")

        cursor.execute("INSERT INTO assessments VALUES (1, 'Quiz 1', 'CS101', 'Quiz', 100)")

        cursor.execute("INSERT INTO grades VALUES (1, 'S001', 1, 85.0, '2025-01-15')")
        cursor.execute("INSERT INTO grades VALUES (2, 'S001', 1, 78.0, '2025-02-15')")

        cursor.execute("INSERT INTO student_modules VALUES ('S001', 'CS101')")

        conn.commit()

        yield conn

        conn.close()
        os.unlink(db_path)

    def test_trend_data_retrieval(self, temp_db_with_trends):
        """Test that trend data can be retrieved correctly"""
        cursor = temp_db_with_trends.cursor()

        cursor.execute('''
            SELECT submission_date, score
            FROM grades
            WHERE student_id = 'S001'
            ORDER BY submission_date
        ''')

        grades = cursor.fetchall()
        assert len(grades) == 2
        assert grades[0][1] == 85.0
        assert grades[1][1] == 78.0

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
