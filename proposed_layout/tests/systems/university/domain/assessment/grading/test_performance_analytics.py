"""
Comprehensive tests for performance_analytics.py module
Tests module performance analysis, dashboards, and reporting
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import sys
import os
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from education_system.systems.university.domain.assessment.grading.performance_analytics import (
    collect_dashboard_data,
    module_performance_summary,
    analyze_module_performance,
    display_module_performance_results,
    calculate_course_statistics,
    generate_performance_dashboard,
    display_performance_dashboard,
    export_module_performance,
    analyze_course_performance_trends,
    forecast_course_performance,
    export_performance_summary,
    performance_prediction_models,
    forecast_overall_performance,
    forecast_single_course,
    build_module_success_model
)
from education_system.systems.university.infrastructure.database.db import get_connection

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
        email_address TEXT,
        gender TEXT,
        enrollment_date TEXT
    )
    ''')

    # Create modules table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS modules (
        module_code TEXT PRIMARY KEY,
        module_name TEXT NOT NULL,
        module_type TEXT,
        credits INTEGER,
        course TEXT
    )
    ''')

    # Create module_grades table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS module_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        module_code TEXT,
        final_score REAL,
        final_grade TEXT,
        completion_date TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (module_code) REFERENCES modules (module_code)
    )
    ''')

    # Create assessments table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assessments (
        assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_name TEXT NOT NULL,
        assessment_type TEXT,
        module_code TEXT NOT NULL,
        max_points REAL NOT NULL,
        weight REAL,
        due_date TEXT,
        FOREIGN KEY (module_code) REFERENCES modules (module_code)
    )
    ''')

    # Create grades table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS grades (
        grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        assessment_id INTEGER,
        score REAL,
        letter_grade TEXT,
        submission_date TEXT,
        comments TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
    )
    ''')

    # Create student_modules table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS student_modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        module_code TEXT,
        enrollment_date TEXT,
        status TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (module_code) REFERENCES modules (module_code)
    )
    ''')

    conn.commit()
    conn.close()

    with patch('education_system.systems.university.infrastructure.database.db.get_connection', mock_get_connection):
        with patch('education_system.systems.university.domain.assessment.grading.performance_analytics.get_connection', mock_get_connection):
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
        VALUES ('ST002', 'Jane', 'Smith', 'CS', 'jane@test.com')
    ''')

    # Insert sample modules
    cursor.execute('''
        INSERT INTO modules (module_code, module_name, module_type, credits, course)
        VALUES ('CS101', 'Intro to CS', 'Core', 3, 'CS')
    ''')

    cursor.execute('''
        INSERT INTO modules (module_code, module_name, module_type, credits, course)
        VALUES ('CS102', 'Data Structures', 'Core', 3, 'CS')
    ''')

    # Insert sample module grades
    cursor.execute('''
        INSERT INTO module_grades (student_id, module_code, final_score, final_grade, completion_date)
        VALUES ('ST001', 'CS101', 85.5, 'A', '2024-01-15')
    ''')

    cursor.execute('''
        INSERT INTO module_grades (student_id, module_code, final_score, final_grade, completion_date)
        VALUES ('ST001', 'CS102', 78.0, 'B+', '2024-02-20')
    ''')

    cursor.execute('''
        INSERT INTO module_grades (student_id, module_code, final_score, final_grade, completion_date)
        VALUES ('ST002', 'CS101', 92.0, 'A+', '2024-01-15')
    ''')

    # Insert sample assessments
    cursor.execute('''
        INSERT INTO assessments (assessment_name, assessment_type, module_code, max_points, weight)
        VALUES ('Midterm', 'Exam', 'CS101', 100, 0.3)
    ''')

    cursor.execute('''
        INSERT INTO assessments (assessment_name, assessment_type, module_code, max_points, weight)
        VALUES ('Final', 'Exam', 'CS101', 100, 0.5)
    ''')

    # Insert sample grades
    cursor.execute('''
        INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
        VALUES ('ST001', 1, 85, 'A', '2024-01-10')
    ''')

    cursor.execute('''
        INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
        VALUES ('ST002', 1, 95, 'A+', '2024-01-10')
    ''')

    conn.commit()
    conn.close()

    return test_db

class TestCollectDashboardData:
    """Tests for collect_dashboard_data function"""

    def test_collect_dashboard_data_empty_database(self, test_db):
        """Test collecting dashboard data from empty database"""
        conn = test_db()
        cursor = conn.cursor()

        data = collect_dashboard_data(cursor)

        assert data is not None
        assert 'total_students' in data
        assert 'total_courses' in data
        assert 'total_grades' in data
        assert data['total_grades'] == 0

        conn.close()

    def test_collect_dashboard_data_with_data(self, sample_data):
        """Test collecting dashboard data with sample data"""
        conn = sample_data()
        cursor = conn.cursor()

        data = collect_dashboard_data(cursor)

        assert data is not None
        assert data['total_students'] >= 2
        assert data['total_grades'] >= 2
        assert 'grade_distribution' in data
        assert 'course_averages' in data

        conn.close()

    def test_collect_dashboard_data_structure(self, sample_data):
        """Test that collected data has expected structure"""
        conn = sample_data()
        cursor = conn.cursor()

        data = collect_dashboard_data(cursor)

        # Check all expected keys are present
        expected_keys = [
            'total_students', 'total_courses', 'total_grades',
            'avg_score', 'grade_distribution', 'course_averages',
            'student_averages', 'at_risk_students', 'monthly_trends',
            'missing_grades', 'notes'
        ]

        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

        conn.close()

    def test_collect_dashboard_data_grade_distribution(self, sample_data):
        """Test that grade distribution is calculated correctly"""
        conn = sample_data()
        cursor = conn.cursor()

        data = collect_dashboard_data(cursor)

        assert 'grade_distribution' in data
        assert isinstance(data['grade_distribution'], dict)
        assert 'A' in data['grade_distribution']

        conn.close()

class TestModulePerformanceSummary:
    """Tests for module_performance_summary function"""

    @patch('builtins.input', return_value='0')  # Select all modules
    @patch('builtins.print')
    def test_module_performance_summary_no_data(self, mock_print, mock_input, test_db):
        """Test module performance summary with no data"""
        module_performance_summary()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'No modules' in printed_output or 'Module Performance' in printed_output

    @patch('builtins.input', side_effect=['0', 'n'])  # Select all, don't export
    @patch('builtins.print')
    def test_module_performance_summary_with_data(self, mock_print, mock_input, sample_data):
        """Test module performance summary with sample data"""
        module_performance_summary()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'CS101' in printed_output or 'Performance' in printed_output

class TestAnalyzeModulePerformance:
    """Tests for analyze_module_performance function"""

    def test_analyze_module_performance_no_grades(self, test_db):
        """Test analyzing module with no grades"""
        conn = test_db()
        cursor = conn.cursor()

        # Insert module without grades
        cursor.execute('''
            INSERT INTO modules (module_code, module_name, module_type)
            VALUES ('TEST101', 'Test Module', 'Core')
        ''')
        conn.commit()

        stats = analyze_module_performance(cursor, 'TEST101', 'Test Module', 'Core')

        assert stats is None
        conn.close()

    def test_analyze_module_performance_with_grades(self, sample_data):
        """Test analyzing module with grades"""
        conn = sample_data()
        cursor = conn.cursor()

        stats = analyze_module_performance(cursor, 'CS101', 'Intro to CS', 'Core')

        assert stats is not None
        assert 'code' in stats
        assert 'name' in stats
        assert 'avg_score' in stats
        assert 'total_students' in stats
        assert 'passing_rate' in stats

        conn.close()

    def test_analyze_module_performance_calculations(self, sample_data):
        """Test that module performance calculations are correct"""
        conn = sample_data()
        cursor = conn.cursor()

        stats = analyze_module_performance(cursor, 'CS101', 'Intro to CS', 'Core')

        assert stats is not None
        assert stats['avg_score'] > 0
        assert stats['median_score'] > 0
        assert 0 <= stats['passing_rate'] <= 100
        assert stats['total_students'] >= 0

        conn.close()

class TestCalculateCourseStatistics:
    """Tests for calculate_course_statistics function"""

    def test_calculate_course_statistics_no_students(self, test_db):
        """Test calculating statistics for course with no students"""
        conn = test_db()
        cursor = conn.cursor()

        stats = calculate_course_statistics(cursor, 'NONEXISTENT')

        assert stats is None
        conn.close()

    @patch('education_system.systems.university.domain.assessment.grading.performance_analytics.calculate_student_gpa')
    def test_calculate_course_statistics_with_students(self, mock_gpa, sample_data):
        """Test calculating statistics for course with students"""
        mock_gpa.return_value = (3.5, 30, [])

        conn = sample_data()
        cursor = conn.cursor()

        stats = calculate_course_statistics(cursor, 'CS')

        assert stats is not None
        assert 'course' in stats
        assert 'avg_gpa' in stats
        assert 'avg_score' in stats
        assert 'passing_rate' in stats

        conn.close()

class TestGeneratePerformanceDashboard:
    """Tests for generate_performance_dashboard function"""

    @patch('education_system.systems.university.domain.assessment.grading.performance_analytics.display_performance_dashboard')
    @patch('education_system.systems.university.domain.assessment.grading.performance_analytics.generate_dashboard_report', create=True)
    @patch('education_system.systems.university.domain.assessment.grading.performance_analytics.create_dashboard_visualizations', create=True)
    @patch('builtins.print')
    def test_generate_performance_dashboard(self, mock_print, mock_viz, mock_report, mock_display, sample_data):
        """Test generating performance dashboard"""
        generate_performance_dashboard()

        # Should call the display, report, and visualization functions
        assert mock_display.called or mock_print.called

class TestDisplayModulePerformanceResults:
    """Tests for display_module_performance_results function"""

    @patch('builtins.print')
    @patch('education_system.systems.university.domain.assessment.grading.performance_analytics.letter_to_gpa')
    def test_display_module_performance_results(self, mock_gpa, mock_print):
        """Test displaying module performance results"""
        mock_gpa.return_value = 4.0

        module_stats = [
            {
                'code': 'CS101',
                'name': 'Intro to CS',
                'type': 'Core',
                'total_students': 25,
                'avg_score': 85.5,
                'median_score': 84.0,
                'std_dev': 8.5,
                'min_score': 65.0,
                'max_score': 98.0,
                'passing_rate': 92.0,
                'grade_distribution': {'A': 10, 'B': 8, 'C': 5, 'D': 2},
                'performance_level': 'Good'
            }
        ]

        display_module_performance_results(module_stats)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'CS101' in printed_output
        assert 'MODULE PERFORMANCE' in printed_output

class TestExportModulePerformance:
    """Tests for export_module_performance function"""

    @patch('builtins.print')
    def test_export_module_performance(self, mock_print, tmp_path):
        """Test exporting module performance to CSV"""
        module_stats = [
            {
                'code': 'CS101',
                'name': 'Intro to CS',
                'type': 'Core',
                'total_students': 25,
                'avg_score': 85.5,
                'median_score': 84.0,
                'std_dev': 8.5,
                'min_score': 65.0,
                'max_score': 98.0,
                'passing_rate': 92.0,
                'performance_level': 'Good'
            }
        ]

        # Mock filesystem operations so we don't need real directories
        with patch('os.path.exists', return_value=True), \
             patch('os.makedirs'), \
             patch('builtins.open', MagicMock()):
            export_module_performance(module_stats)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'exported' in printed_output.lower() or 'csv' in printed_output.lower()

class TestForecastSingleCourse:
    """Tests for forecast_single_course function"""

    @patch('builtins.print')
    def test_forecast_single_course_no_data(self, mock_print, test_db):
        """Test forecasting with no data"""
        conn = test_db()
        cursor = conn.cursor()

        forecast_single_course(cursor, 'NONEXISTENT')

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'No sufficient historical data' in printed_output or 'Forecast' in printed_output

        conn.close()

class TestBuildModuleSuccessModel:
    """Tests for build_module_success_model function"""

    @patch('builtins.print')
    def test_build_module_success_model_no_data(self, mock_print, test_db):
        """Test building module success model with no data"""
        conn = test_db()
        cursor = conn.cursor()

        build_module_success_model(cursor)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'No grade data' in printed_output or 'Module Success Model' in printed_output

        conn.close()

    @patch('builtins.print')
    def test_build_module_success_model_with_data(self, mock_print, sample_data):
        """Test building module success model with sample data"""
        conn = sample_data()
        cursor = conn.cursor()

        build_module_success_model(cursor)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'Module' in printed_output or 'model' in printed_output.lower()

        conn.close()

class TestDataValidation:
    """Tests for data validation and edge cases"""

    def test_analyze_module_performance_empty_scores(self, test_db):
        """Test analyzing module with null scores"""
        conn = test_db()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO modules (module_code, module_name, module_type)
            VALUES ('TEST101', 'Test', 'Core')
        ''')

        cursor.execute('''
            INSERT INTO students (student_id, first_name, last_name, course)
            VALUES ('ST999', 'Test', 'Student', 'CS')
        ''')

        cursor.execute('''
            INSERT INTO module_grades (student_id, module_code, final_grade)
            VALUES ('ST999', 'TEST101', 'A')
        ''')
        conn.commit()

        stats = analyze_module_performance(cursor, 'TEST101', 'Test', 'Core')

        # Should handle null scores gracefully
        assert stats is None or stats['avg_score'] is not None

        conn.close()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
