"""
Comprehensive tests for predictive_analytics.py module
Tests risk assessment, early warning systems, and dropout prediction
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import sys
import os
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from education_system.university_system.modules.domain.academics.grading.predictive_analytics import (
    predictive_analytics_menu,
    identify_at_risk_students,
    calculate_risk_factors,
    early_warning_system,
    generate_early_warning_alert,
    export_at_risk_students,
    export_early_warning_alerts,
    export_dropout_risk_list,
    build_at_risk_prediction_model,
    analyze_dropout_risk_factors,
    build_dropout_prediction_model,
    generate_dropout_interventions,
    generate_dropout_intervention_plan,
    identify_high_dropout_risk,
    calculate_dropout_risk_score,
    generate_risk_report,
    collect_comprehensive_risk_data,
    generate_comprehensive_risk_report
)
from education_system.university_system.infrastructure.database.db import get_connection

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

    # Create module_grades table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS module_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        module_code TEXT,
        final_score REAL,
        final_grade TEXT,
        completion_date TEXT,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
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
        weight REAL
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
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    # Create student_risk_assessment table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS student_risk_assessment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        risk_score REAL,
        risk_level TEXT,
        assessment_date TEXT,
        prediction_model TEXT,
        confidence REAL,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    ''')

    # Create risk_factors table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS risk_factors (
        factor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        weight REAL
    )
    ''')

    # Create risk_details table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS risk_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        risk_assessment_id INTEGER,
        factor_id INTEGER,
        factor_value REAL,
        factor_contribution REAL,
        FOREIGN KEY (risk_assessment_id) REFERENCES student_risk_assessment (id),
        FOREIGN KEY (factor_id) REFERENCES risk_factors (factor_id)
    )
    ''')

    conn.commit()
    conn.close()

    with patch('university_system.infrastructure.database.db.get_connection', mock_get_connection):
        with patch('university_system.modules.domain.academics.grading.predictive_analytics.get_connection', mock_get_connection):
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

    # Insert sample module grades with low scores (at-risk students)
    cursor.execute('''
        INSERT INTO module_grades (student_id, module_code, final_score, final_grade)
        VALUES ('ST001', 'CS101', 45.0, 'F')
    ''')

    cursor.execute('''
        INSERT INTO module_grades (student_id, module_code, final_score, final_grade)
        VALUES ('ST001', 'CS102', 52.0, 'D')
    ''')

    cursor.execute('''
        INSERT INTO module_grades (student_id, module_code, final_score, final_grade)
        VALUES ('ST002', 'CS101', 88.0, 'A')
    ''')

    # Insert assessments
    cursor.execute('''
        INSERT INTO assessments (assessment_name, assessment_type, module_code, max_points, weight)
        VALUES ('Midterm', 'Exam', 'CS101', 100, 0.3)
    ''')

    # Insert grades with failed assessments
    cursor.execute('''
        INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
        VALUES ('ST001', 1, 40, 'F', '2024-01-10')
    ''')

    cursor.execute('''
        INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
        VALUES ('ST002', 1, 90, 'A', '2024-01-10')
    ''')

    # Insert student modules
    cursor.execute('''
        INSERT INTO student_modules (student_id, module_code)
        VALUES ('ST001', 'CS101')
    ''')

    cursor.execute('''
        INSERT INTO student_modules (student_id, module_code)
        VALUES ('ST002', 'CS101')
    ''')

    # Insert risk factors
    cursor.execute('''
        INSERT INTO risk_factors (name, description, weight)
        VALUES ('Low GPA', 'GPA below 2.0', 1.0)
    ''')

    cursor.execute('''
        INSERT INTO risk_factors (name, description, weight)
        VALUES ('Failed Assessments', 'Multiple failed assessments', 0.8)
    ''')

    conn.commit()
    conn.close()

    return test_db

class TestPredictiveAnalyticsMenu:
    """Tests for predictive analytics menu"""

    @patch('builtins.input', side_effect=['10'])  # Exit immediately
    @patch('builtins.print')
    def test_predictive_analytics_menu_display(self, mock_print, mock_input, test_db):
        """Test that predictive analytics menu displays correctly"""
        predictive_analytics_menu()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'Predictive Analytics' in printed_output

    @patch('builtins.input', side_effect=['11', '10'])  # Invalid choice, then exit
    @patch('builtins.print')
    def test_predictive_analytics_menu_invalid_choice(self, mock_print, mock_input, test_db):
        """Test that invalid menu choice is handled"""
        predictive_analytics_menu()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'Invalid choice' in printed_output

class TestIdentifyAtRiskStudents:
    """Tests for identify_at_risk_students function"""

    @patch('builtins.input', side_effect=['2.0', 'n'])  # Threshold 2.0, don't export
    @patch('builtins.print')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    def test_identify_at_risk_students_no_data(self, mock_gpa, mock_print, mock_input, test_db):
        """Test identifying at-risk students with no data"""
        mock_gpa.return_value = (None, 0, [])

        identify_at_risk_students()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'No students' in printed_output or 'at-risk' in printed_output.lower()

    @patch('builtins.input', side_effect=['2.0', 'n'])  # Threshold 2.0, don't export
    @patch('builtins.print')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    def test_identify_at_risk_students_with_data(self, mock_gpa, mock_print, mock_input, sample_data):
        """Test identifying at-risk students with sample data"""
        # Mock GPA to return low GPA for ST001
        def mock_gpa_func(cursor, student_id):
            if student_id == 'ST001':
                return (1.5, 6, [])
            else:
                return (3.5, 6, [])

        mock_gpa.side_effect = mock_gpa_func

        identify_at_risk_students()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'ST001' in printed_output or 'at-risk' in printed_output.lower()

class TestCalculateRiskFactors:
    """Tests for calculate_risk_factors function"""

    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    def test_calculate_risk_factors_high_risk(self, mock_gpa, sample_data):
        """Test calculating risk factors for high-risk student"""
        mock_gpa.return_value = (1.5, 6, [])

        conn = sample_data()
        cursor = conn.cursor()

        factors = calculate_risk_factors(cursor, 'ST001')

        assert factors is not None
        assert 'total_score' in factors
        assert 'primary_factors' in factors
        assert factors['total_score'] > 0

        conn.close()

    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    def test_calculate_risk_factors_low_risk(self, mock_gpa, sample_data):
        """Test calculating risk factors for low-risk student"""
        mock_gpa.return_value = (3.8, 6, [])

        conn = sample_data()
        cursor = conn.cursor()

        factors = calculate_risk_factors(cursor, 'ST002')

        assert factors is not None
        assert factors['total_score'] >= 0  # May be 0 or low for good student

        conn.close()

class TestEarlyWarningSystem:
    """Tests for early warning system functions"""

    @patch('builtins.input', side_effect=['n'])  # Don't export
    @patch('builtins.print')
    def test_early_warning_system_no_data(self, mock_print, mock_input, test_db):
        """Test early warning system with no data"""
        early_warning_system()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'No students' in printed_output or 'Early Warning' in printed_output

    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    def test_generate_early_warning_alert(self, mock_gpa, sample_data):
        """Test generating early warning alert"""
        mock_gpa.return_value = (1.8, 6, [])

        conn = sample_data()
        cursor = conn.cursor()

        alert = generate_early_warning_alert(
            cursor, 'ST001', 'John', 'Doe', 'CS', 'john@test.com', 75.0, 'High'
        )

        assert alert is not None
        assert 'student_id' in alert
        assert 'recommended_actions' in alert
        assert len(alert['recommended_actions']) > 0

        conn.close()

class TestDropoutRiskAnalysis:
    """Tests for dropout risk analysis functions"""

    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    def test_calculate_dropout_risk_score_high_risk(self, mock_gpa, sample_data):
        """Test calculating dropout risk score for high-risk student"""
        mock_gpa.return_value = (1.5, 6, [])

        conn = sample_data()
        cursor = conn.cursor()

        risk_score = calculate_dropout_risk_score(cursor, 'ST001')

        assert risk_score >= 0
        assert risk_score <= 100
        assert risk_score > 50  # Should be high risk

        conn.close()

    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    def test_calculate_dropout_risk_score_low_risk(self, mock_gpa, sample_data):
        """Test calculating dropout risk score for low-risk student"""
        mock_gpa.return_value = (3.8, 6, [])

        conn = sample_data()
        cursor = conn.cursor()

        risk_score = calculate_dropout_risk_score(cursor, 'ST002')

        assert risk_score >= 0
        assert risk_score <= 100
        # Should be low risk (score depends on other factors too)

        conn.close()

    @patch('builtins.input', side_effect=['n'])  # Don't export
    @patch('builtins.print')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_dropout_risk_score')
    def test_identify_high_dropout_risk(self, mock_risk_score, mock_print, mock_input, sample_data):
        """Test identifying high dropout risk students"""
        # Mock to return high risk for ST001
        def mock_risk_func(cursor, student_id):
            return 80.0 if student_id == 'ST001' else 30.0

        mock_risk_score.side_effect = mock_risk_func

        identify_high_dropout_risk(None)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'dropout' in printed_output.lower() or 'risk' in printed_output.lower()

    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    def test_analyze_dropout_risk_factors(self, mock_gpa, sample_data):
        """Test analyzing dropout risk factors"""
        mock_gpa.return_value = (2.5, 6, [])

        conn = sample_data()
        cursor = conn.cursor()

        # Just check it doesn't crash
        # The function prints results, doesn't return them
        analyze_dropout_risk_factors(cursor)

        conn.close()

class TestInterventionGeneration:
    """Tests for intervention generation functions"""

    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_dropout_risk_score')
    def test_generate_dropout_intervention_plan(self, mock_risk, mock_gpa, sample_data):
        """Test generating dropout intervention plan"""
        mock_gpa.return_value = (1.5, 6, [])
        mock_risk.return_value = 85.0

        conn = sample_data()
        cursor = conn.cursor()

        plan = generate_dropout_intervention_plan(
            cursor, 'ST001', 'John', 'Doe', 'CS', 'john@test.com'
        )

        assert plan is not None
        assert 'student_id' in plan
        assert 'interventions' in plan
        assert len(plan['interventions']) > 0

        conn.close()

    @patch('builtins.print')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.generate_dropout_intervention_plan')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_dropout_risk_score')
    def test_generate_dropout_interventions(self, mock_risk, mock_plan, mock_print, sample_data):
        """Test generating dropout interventions"""
        mock_risk.return_value = 80.0
        mock_plan.return_value = {
            'student_id': 'ST001',
            'name': 'John Doe',
            'course': 'CS',
            'risk_score': 80.0,
            'interventions': [
                {
                    'intervention': 'Academic Advising',
                    'timeline': 'Immediate',
                    'rationale': 'High risk'
                }
            ]
        }

        generate_dropout_interventions(None)

        # Should print intervention plans
        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'dropout' in printed_output.lower() or 'intervention' in printed_output.lower()

class TestRiskReporting:
    """Tests for risk reporting functions"""

    @patch('builtins.print')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.collect_comprehensive_risk_data')
    def test_generate_risk_report(self, mock_collect, mock_print, test_db):
        """Test generating comprehensive risk report"""
        mock_collect.return_value = None  # No data

        generate_risk_report()

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'risk' in printed_output.lower() or 'report' in printed_output.lower()

    @patch('university_system.modules.domain.academics.grading.predictive_analytics.assess_comprehensive_student_risk')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.generate_system_recommendations')
    def test_collect_comprehensive_risk_data(self, mock_recommendations, mock_assess, sample_data):
        """Test collecting comprehensive risk data"""
        mock_assess.return_value = {
            'student_id': 'ST001',
            'name': 'John Doe',
            'course': 'CS',
            'risk_score': 75.0,
            'risk_level': 'High',
            'risk_factors': {'low_gpa': True}
        }
        mock_recommendations.return_value = ['Increase support services']

        conn = sample_data()
        cursor = conn.cursor()

        risk_data = collect_comprehensive_risk_data(cursor)

        assert risk_data is not None
        assert 'students' in risk_data
        assert 'summary_stats' in risk_data
        assert 'recommendations' in risk_data

        conn.close()

    @patch('builtins.print')
    def test_generate_comprehensive_risk_report(self, mock_print, tmp_path):
        """Test generating comprehensive risk report PDF"""
        risk_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'students': [
                {
                    'student_id': 'ST001',
                    'name': 'John Doe',
                    'course': 'CS',
                    'email': 'john@test.com',
                    'risk_score': 75.0,
                    'risk_level': 'High',
                    'gpa': 1.5,
                    'risk_factors': {'low_gpa': True, 'failed_assessments': True}
                }
            ],
            'summary_stats': {
                'total_students': 1,
                'avg_risk_score': 75.0,
                'median_risk_score': 75.0,
                'max_risk_score': 75.0,
                'min_risk_score': 75.0,
                'risk_distribution': {'High': 1, 'Medium': 0, 'Low': 0}
            },
            'recommendations': ['Increase support']
        }

        # Mock file operations
        with patch('os.path.exists', return_value=True):
            with patch('os.makedirs'):
                with patch('builtins.open', create=True):
                    generate_comprehensive_risk_report(risk_data)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'report' in printed_output.lower() or 'saved' in printed_output.lower()

class TestExportFunctions:
    """Tests for export functions"""

    @patch('builtins.print')
    def test_export_at_risk_students(self, mock_print, tmp_path):
        """Test exporting at-risk students list"""
        at_risk_students = [
            {
                'id': 'ST001',
                'name': 'John Doe',
                'course': 'CS',
                'email': 'john@test.com',
                'gpa': 1.5,
                'risk_factors': {'total_score': 75.0, 'primary_factors': ['low_gpa']},
                'problematic_modules': [('CS101', 'Intro to CS', 'F')]
            }
        ]

        with patch('os.path.exists', return_value=True):
            with patch('os.makedirs'):
                export_at_risk_students(at_risk_students, 2.0)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'exported' in printed_output

    @patch('builtins.print')
    def test_export_early_warning_alerts(self, mock_print, tmp_path):
        """Test exporting early warning alerts"""
        alerts = [
            {
                'student_id': 'ST001',
                'name': 'John Doe',
                'course': 'CS',
                'email': 'john@test.com',
                'risk_score': 75.0,
                'risk_level': 'High',
                'recommended_actions': ['Contact immediately']
            }
        ]

        with patch('os.path.exists', return_value=True):
            with patch('os.makedirs'):
                export_early_warning_alerts(alerts)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'exported' in printed_output

    @patch('builtins.print')
    def test_export_dropout_risk_list(self, mock_print, tmp_path):
        """Test exporting dropout risk list"""
        high_risk_students = [
            {
                'student_id': 'ST001',
                'name': 'John Doe',
                'course': 'CS',
                'email': 'john@test.com',
                'risk_score': 85.0
            }
        ]

        with patch('os.path.exists', return_value=True):
            with patch('os.makedirs'):
                export_dropout_risk_list(high_risk_students)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'exported' in printed_output

class TestPredictionModels:
    """Tests for prediction model building"""

    @patch('builtins.print')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.extract_comprehensive_student_features')
    @patch('university_system.modules.domain.academics.grading.predictive_analytics.calculate_student_gpa')
    def test_build_at_risk_prediction_model_insufficient_data(self, mock_gpa, mock_features, mock_print, test_db):
        """Test building at-risk prediction model with insufficient data"""
        mock_features.return_value = None
        mock_gpa.return_value = (2.5, 6, [])

        conn = test_db()
        cursor = conn.cursor()

        build_at_risk_prediction_model(cursor)

        printed_output = ' '.join(str(call) for call in mock_print.call_args_list)
        assert 'Insufficient data' in printed_output or 'model' in printed_output.lower()

        conn.close()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
