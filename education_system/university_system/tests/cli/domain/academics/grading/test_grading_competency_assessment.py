import pytest
import os
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import numpy as np

from education_system.university_system.modules.domain.academics.grading.competency_assessment import (
    add_competency_levels,
    manage_competency_levels,
    view_student_competency_profile,
    generate_competency_report,
    generate_student_competency_report,
    generate_course_competency_report,
    assess_student_risk,
    assess_comprehensive_student_risk
)

class TestAddCompetencyLevels:
    """Test the add_competency_levels function"""

    @patch('builtins.input', side_effect=['3', 'Beginner', 'Basic understanding',
                                          'Intermediate', 'Good understanding',
                                          'Advanced', 'Expert level'])
    @patch('builtins.print')
    def test_add_competency_levels_success(self, mock_print, mock_input):
        """Test successfully adding competency levels"""
        cursor = Mock()
        cursor.connection = Mock()

        add_competency_levels(cursor, 1, 'Problem Solving')

        # Verify 3 levels were inserted
        assert cursor.execute.call_count == 3
        cursor.connection.commit.assert_called_once()

    @patch('builtins.input', side_effect=['0', '2', 'Level 1', 'Desc 1', 'Level 2', 'Desc 2'])
    @patch('builtins.print')
    def test_add_competency_levels_invalid_then_valid(self, mock_print, mock_input):
        """Test invalid number followed by valid input"""
        cursor = Mock()
        cursor.connection = Mock()

        add_competency_levels(cursor, 1, 'Test Competency')

        # Should eventually succeed with 2 levels
        assert cursor.execute.call_count == 2

    @patch('builtins.input', side_effect=['abc', '1', 'Level 1', 'Description'])
    @patch('builtins.print')
    def test_add_competency_levels_non_numeric_input(self, mock_print, mock_input):
        """Test non-numeric input for number of levels"""
        cursor = Mock()
        cursor.connection = Mock()

        add_competency_levels(cursor, 1, 'Test Competency')

        # Should handle error and retry
        assert cursor.execute.call_count >= 1

class TestManageCompetencyLevels:
    """Test the manage_competency_levels function"""

    @patch('university_system.modules.domain.academics.grading.competency_assessment.get_connection')
    @patch('builtins.input', side_effect=['1', '4'])  # Select competency 1, then exit
    @patch('builtins.print')
    def test_manage_competency_levels_no_competencies(
        self, mock_print, mock_input, mock_get_conn
    ):
        """Test when no competencies exist"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []

        manage_competency_levels()

        mock_print.assert_any_call("No competencies found in the database. Please add competencies first.")

    @patch('university_system.modules.domain.academics.grading.competency_assessment.get_connection')
    @patch('builtins.input', side_effect=['1', '4'])
    def test_manage_competency_levels_invalid_id(self, mock_input, mock_get_conn):
        """Test with invalid competency ID"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        # First fetchall returns competencies, second fetchone returns None
        cursor.fetchall.return_value = [(1, 'Test', 'Category')]
        cursor.fetchone.return_value = None

        with patch('builtins.print') as mock_print:
            manage_competency_levels()

        assert any('not found' in str(call).lower() for call in mock_print.call_args_list)

class TestViewStudentCompetencyProfile:
    """Test the view_student_competency_profile function"""

    @pytest.fixture
    def mock_cursor_with_competencies(self):
        """Create mock cursor with competency data"""
        cursor = Mock()

        # Student data
        cursor.fetchone.return_value = ('John', 'Doe')

        # Competency assessments
        cursor.fetchall.return_value = [
            (1, 'Problem Solving', 'Technical', 'Solving complex problems',
             1, 'Advanced', 4, 'Expert level', '2025-01-15', 'Completed project'),
            (2, 'Communication', 'Soft Skills', 'Effective communication',
             2, 'Intermediate', 3, 'Good understanding', '2025-01-20', 'Presentation'),
        ]

        return cursor

    @patch('university_system.modules.domain.academics.grading.competency_assessment.get_connection')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.select_student')
    @patch('builtins.input', side_effect=['n', 'n'])  # Don't view evidence, don't visualize
    @patch('builtins.print')
    def test_view_student_competency_profile_success(
        self, mock_print, mock_input, mock_select, mock_get_conn, mock_cursor_with_competencies
    ):
        """Test successfully viewing student competency profile"""
        mock_select.return_value = 'S001'
        conn = Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = mock_cursor_with_competencies

        view_student_competency_profile()

        # Verify statistics were calculated and printed
        assert any('Total Assessed Competencies' in str(call) for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.academics.grading.competency_assessment.get_connection')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.select_student')
    @patch('builtins.print')
    def test_view_student_competency_profile_no_assessments(
        self, mock_print, mock_select, mock_get_conn
    ):
        """Test when student has no competency assessments"""
        mock_select.return_value = 'S001'
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = ('John', 'Doe')
        cursor.fetchall.return_value = []

        view_student_competency_profile()

        mock_print.assert_any_call("No competency assessments recorded for this student.")

    @patch('university_system.modules.domain.academics.grading.competency_assessment.get_connection')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.select_student')
    @patch('builtins.input', return_value='y')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.plt')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.os.makedirs')
    def test_view_student_competency_profile_with_visualization(
        self, mock_makedirs, mock_plt, mock_input, mock_select, mock_get_conn,
        mock_cursor_with_competencies
    ):
        """Test viewing profile with visualization"""
        mock_select.return_value = 'S001'
        conn = Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = mock_cursor_with_competencies

        view_student_competency_profile()

        # Verify plots were created
        assert mock_plt.savefig.call_count >= 1

class TestGenerateCompetencyReport:
    """Test the generate_competency_report function"""

    @patch('university_system.modules.domain.academics.grading.competency_assessment.get_connection')
    @patch('builtins.input', side_effect=['3'])  # Return to menu
    def test_generate_competency_report_exit(self, mock_input, mock_get_conn):
        """Test exiting the report menu"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        generate_competency_report()

        # Should exit without generating report
        conn.close.assert_called_once()

    @patch('university_system.modules.domain.academics.grading.competency_assessment.get_connection')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.select_student')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.generate_student_competency_report')
    @patch('builtins.input', side_effect=['1'])  # Individual student report
    def test_generate_competency_report_student(
        self, mock_input, mock_gen_report, mock_select, mock_get_conn
    ):
        """Test generating individual student competency report"""
        mock_select.return_value = 'S001'
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        generate_competency_report()

        mock_gen_report.assert_called_once()

class TestGenerateStudentCompetencyReport:
    """Test the generate_student_competency_report function"""

    @pytest.fixture
    def comprehensive_cursor(self):
        """Create comprehensive mock cursor with all required data"""
        cursor = Mock()

        # Multiple fetchone and fetchall calls
        cursor.fetchone.return_value = ('John', 'Doe', 'Computer Science')

        cursor.fetchall.return_value = [
            (1, 'Problem Solving', 'Technical', 'Solving problems',
             1, 'Advanced', 4, 'Expert level', '2025-01-15', 'Project completed'),
            (2, 'Communication', 'Soft Skills', 'Communication',
             2, 'Beginner', 1, 'Basic level', '2025-01-20', 'Needs improvement'),
        ]

        return cursor

    @patch('university_system.modules.domain.academics.grading.competency_assessment.SimpleDocTemplate')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.plt')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.os.makedirs')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.os.path.exists')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.os.remove')
    @patch('builtins.print')
    def test_generate_student_competency_report_success(
        self, mock_print, mock_remove, mock_exists, mock_makedirs,
        mock_plt, mock_doc, comprehensive_cursor
    ):
        """Test successfully generating student competency report"""
        mock_exists.return_value = False  # Directory doesn't exist

        generate_student_competency_report(comprehensive_cursor, 'S001')

        # Verify report was generated
        assert any('generated' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_generate_student_competency_report_student_not_found(self, mock_print):
        """Test when student is not found"""
        cursor = Mock()
        cursor.fetchone.return_value = None

        generate_student_competency_report(cursor, 'S999')

        mock_print.assert_any_call("Student not found.")

    @patch('builtins.print')
    def test_generate_student_competency_report_no_assessments(self, mock_print):
        """Test when student has no assessments"""
        cursor = Mock()
        cursor.fetchone.return_value = ('John', 'Doe', 'CS')
        cursor.fetchall.return_value = []

        generate_student_competency_report(cursor, 'S001')

        mock_print.assert_any_call("No competency assessments recorded for this student.")

class TestGenerateCourseCompetencyReport:
    """Test the generate_course_competency_report function"""

    @pytest.fixture
    def course_cursor(self):
        """Create mock cursor with course competency data"""
        cursor = Mock()

        # Students in course
        cursor.fetchall.side_effect = [
            [('S001', 'John', 'Doe'), ('S002', 'Jane', 'Smith')],  # Students
            [(1, 'Problem Solving', 'Technical')],  # Competencies
            [('S001', 4), ('S002', 3)],  # Level values for competency
            [('male', 1), ('female', 1)],  # Gender distribution
        ]

        return cursor

    @patch('university_system.modules.domain.academics.grading.competency_assessment.SimpleDocTemplate')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.plt')
    @patch('university_system.modules.domain.academics.grading.competency_assessment.os.makedirs')
    @patch('builtins.print')
    def test_generate_course_competency_report_success(
        self, mock_print, mock_makedirs, mock_plt, mock_doc, course_cursor
    ):
        """Test successful course competency report generation"""
        generate_course_competency_report(course_cursor, 'Computer Science')

        # Verify report generation
        assert any('generated' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_generate_course_competency_report_no_students(self, mock_print):
        """Test when no students in course"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        generate_course_competency_report(cursor, 'InvalidCourse')

        assert any('No students found' in str(call) for call in mock_print.call_args_list)

class TestAssessStudentRisk:
    """Test the assess_student_risk function"""

    @pytest.fixture
    def risk_cursor(self):
        """Create mock cursor for risk assessment"""
        cursor = Mock()

        # Multiple fetchone calls for different risk factors
        cursor.fetchone.side_effect = [
            (2,),  # Failed assessments count
            (10, 8),  # Total and submitted assessments
        ]

        # Grade trend data
        cursor.fetchall.return_value = [
            (90.0, '2025-01-01'),
            (85.0, '2025-01-08'),
            (80.0, '2025-01-15'),
            (75.0, '2025-01-22'),
        ]

        return cursor

    @patch('university_system.modules.domain.academics.grading.competency_assessment.calculate_student_gpa')
    def test_assess_student_risk_high_risk(self, mock_gpa, risk_cursor):
        """Test assessment of high-risk student"""
        mock_gpa.return_value = (1.8, 30, [])  # Low GPA

        result = assess_student_risk(risk_cursor, 'S001', 'John', 'Doe', 'CS')

        assert result['risk_level'] == 'High'
        assert result['student_id'] == 'S001'
        assert len(result['risk_factors']) > 0

    @patch('university_system.modules.domain.academics.grading.competency_assessment.calculate_student_gpa')
    def test_assess_student_risk_low_risk(self, mock_gpa):
        """Test assessment of low-risk student"""
        cursor = Mock()
        cursor.fetchone.side_effect = [
            (0,),  # No failed assessments
            (10, 10),  # All assessments submitted
        ]
        cursor.fetchall.return_value = [
            (85.0, '2025-01-01'),
            (87.0, '2025-01-08'),
            (89.0, '2025-01-15'),
        ]

        mock_gpa.return_value = (3.5, 30, [])  # Good GPA

        result = assess_student_risk(cursor, 'S001', 'John', 'Doe', 'CS')

        assert result['risk_level'] == 'Minimal'
        assert result['risk_score'] < 10

    @patch('university_system.modules.domain.academics.grading.competency_assessment.calculate_student_gpa')
    def test_assess_student_risk_medium_risk(self, mock_gpa):
        """Test assessment of medium-risk student"""
        cursor = Mock()
        cursor.fetchone.side_effect = [
            (1,),  # One failed assessment
            (10, 8),  # Some missing submissions
        ]
        cursor.fetchall.return_value = [
            (78.0, '2025-01-01'),
            (75.0, '2025-01-08'),
        ]

        mock_gpa.return_value = (2.6, 30, [])  # Below average GPA

        result = assess_student_risk(cursor, 'S001', 'John', 'Doe', 'CS')

        assert result['risk_level'] in ['Medium', 'Low']
        assert 10 <= result['risk_score'] < 50

class TestAssessComprehensiveStudentRisk:
    """Test the assess_comprehensive_student_risk function"""

    @patch('university_system.modules.domain.academics.grading.competency_assessment.calculate_student_gpa')
    def test_assess_comprehensive_student_risk_multiple_factors(self, mock_gpa):
        """Test comprehensive risk assessment with multiple factors"""
        cursor = Mock()

        # Set up mock returns for various risk factor queries
        cursor.fetchone.side_effect = [
            (10, 7),  # Submission rate
            (3,),  # Failed assessments
        ]

        cursor.fetchall.return_value = [
            (90.0, '2025-01-01'),
            (85.0, '2025-01-08'),
            (75.0, '2025-01-15'),  # Declining trend
        ]

        mock_gpa.return_value = (2.3, 30, [])  # Low GPA

        result = assess_comprehensive_student_risk(
            cursor, 'S001', 'John', 'Doe', 'CS', 'john@example.com'
        )

        assert result['risk_level'] == 'High'
        assert 'Academic Performance' in result['risk_factors']
        assert result['risk_score'] >= 50

    @patch('university_system.modules.domain.academics.grading.competency_assessment.calculate_student_gpa')
    def test_assess_comprehensive_student_risk_minimal(self, mock_gpa):
        """Test comprehensive assessment of minimal-risk student"""
        cursor = Mock()

        cursor.fetchone.side_effect = [
            (10, 10),  # Perfect submission rate
            (0,),  # No failures
        ]

        cursor.fetchall.return_value = [
            (85.0, '2025-01-01'),
            (87.0, '2025-01-08'),
            (89.0, '2025-01-15'),  # Improving trend
        ]

        mock_gpa.return_value = (3.7, 30, [])  # High GPA

        result = assess_comprehensive_student_risk(
            cursor, 'S001', 'John', 'Doe', 'CS', 'john@example.com'
        )

        assert result['risk_level'] == 'Minimal'
        assert result['risk_score'] < 10

class TestCompetencyIntegration:
    """Integration tests for competency assessment"""

    @pytest.fixture
    def temp_db_with_competencies(self):
        """Create temporary database with competency data"""
        db_path = tempfile.mktemp(suffix='.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create schema
        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                course TEXT,
                email TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE competencies (
                competency_id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                category TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE competency_levels (
                level_id INTEGER PRIMARY KEY,
                competency_id INTEGER,
                level_name TEXT,
                level_value INTEGER,
                description TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE student_competencies (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                competency_id INTEGER,
                level_id INTEGER,
                evidence TEXT,
                assessment_date TEXT
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
            CREATE TABLE assessments (
                assessment_id INTEGER PRIMARY KEY,
                module_code TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE student_modules (
                student_id TEXT,
                module_code TEXT
            )
        ''')

        # Insert test data
        cursor.execute("INSERT INTO students VALUES ('S001', 'John', 'Doe', 'CS', 'john@test.com')")
        cursor.execute("INSERT INTO competencies VALUES (1, 'Problem Solving', 'Solving', 'Technical')")
        cursor.execute("INSERT INTO competency_levels VALUES (1, 1, 'Advanced', 4, 'Expert')")
        cursor.execute("INSERT INTO student_competencies VALUES (1, 'S001', 1, 1, 'Evidence', '2025-01-15')")

        conn.commit()

        yield conn

        conn.close()
        os.unlink(db_path)

    def test_competency_data_retrieval(self, temp_db_with_competencies):
        """Test retrieving competency data from database"""
        cursor = temp_db_with_competencies.cursor()

        cursor.execute('''
            SELECT c.name, cl.level_name, cl.level_value
            FROM student_competencies sc
            JOIN competencies c ON sc.competency_id = c.competency_id
            JOIN competency_levels cl ON sc.level_id = cl.level_id
            WHERE sc.student_id = 'S001'
        ''')

        result = cursor.fetchall()

        assert len(result) == 1
        assert result[0][0] == 'Problem Solving'
        assert result[0][1] == 'Advanced'
        assert result[0][2] == 4

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
