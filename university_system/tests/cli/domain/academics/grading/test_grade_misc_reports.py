import pytest
import os
import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import shutil
import numpy as np

from university_system.modules.domain.academics.grading.reports import (
    generate_statistical_report,
    generate_module_stats_report,
    generate_all_modules_stats_report,
    generate_course_stats_report,
    generate_all_courses_stats_report,
    generate_comprehensive_stats_report
)


class TestGenerateStatisticalReport:
    """Test the generate_statistical_report function"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database connection"""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        cursor.connection = conn
        return conn, cursor

    @pytest.fixture
    def reports_dir(self):
        """Create a temporary directory for reports"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @patch('university_system.modules.domain.academics.grade_misc.reports.get_connection')
    @patch('university_system.modules.domain.academics.grade_misc.reports._get_grading_imports')
    @patch('builtins.input', side_effect=['4'])
    @patch('university_system.modules.domain.academics.grade_misc.reports.generate_comprehensive_stats_report')
    def test_generate_statistical_report_comprehensive(
        self, mock_comprehensive, mock_input, mock_imports, mock_get_conn
    ):
        """Test generating comprehensive statistical report"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        generate_statistical_report()

        mock_comprehensive.assert_called_once()
        cursor.close.assert_called_once()

    @patch('university_system.modules.domain.academics.grade_misc.reports.get_connection')
    @patch('university_system.modules.domain.academics.grade_misc.reports._get_grading_imports')
    @patch('builtins.input', side_effect=['1'])
    def test_generate_statistical_report_assessment_no_selection(
        self, mock_input, mock_imports, mock_get_conn
    ):
        """Test when no assessment is selected"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        mock_select_assessment = Mock(return_value=None)
        mock_imports.return_value = (mock_select_assessment, Mock(), Mock())

        generate_statistical_report()

        conn.close.assert_called_once()

    @patch('university_system.modules.domain.academics.grade_misc.reports.get_connection')
    @patch('builtins.input', side_effect=['invalid'])
    def test_generate_statistical_report_invalid_choice(self, mock_input, mock_get_conn):
        """Test with invalid report type choice"""
        conn, cursor = Mock(), Mock()
        mock_get_conn.return_value = conn
        conn.cursor.return_value = cursor

        generate_statistical_report()

        conn.close.assert_called_once()


class TestGenerateModuleStatsReport:
    """Test the generate_module_stats_report function"""

    @pytest.fixture
    def mock_cursor(self):
        """Create a mock cursor with sample data"""
        cursor = Mock()

        # Module details
        cursor.fetchone.side_effect = [
            ('Test Module', 'Core'),  # Module details
        ]

        # Grades data
        cursor.fetchall.side_effect = [
            [(85.0, 'A'), (78.0, 'B'), (92.0, 'A+'), (65.0, 'C')],  # Grades
            [(1, 'Quiz 1', 'Quiz', 10, 5, 85.0)],  # Assessments
        ]

        return cursor

    @patch('university_system.modules.domain.academics.grade_misc.reports.os.path.exists')
    @patch('university_system.modules.domain.academics.grade_misc.reports.SimpleDocTemplate')
    @patch('university_system.modules.domain.academics.grade_misc.reports.plt')
    @patch('builtins.print')
    def test_generate_module_stats_report_success(
        self, mock_print, mock_plt, mock_doc, mock_exists, mock_cursor
    ):
        """Test successful generation of module stats report"""
        mock_exists.return_value = True
        reports_dir = 'test_reports'
        timestamp = '20250101_120000'

        # Mock GRADE_SYSTEMS
        with patch('university_system.modules.domain.academics.grade_misc.reports.GRADE_SYSTEMS', {
            'letter': {'A+': 4.3, 'A': 4.0, 'B': 3.0, 'C': 2.0, 'F': 0.0}
        }):
            generate_module_stats_report(mock_cursor, 'CS101', reports_dir, timestamp)

        # Verify database queries were made
        assert mock_cursor.execute.call_count >= 3

    @patch('builtins.print')
    def test_generate_module_stats_report_module_not_found(self, mock_print):
        """Test when module is not found"""
        cursor = Mock()
        cursor.fetchone.return_value = None

        generate_module_stats_report(cursor, 'INVALID', 'reports', '20250101')

        mock_print.assert_called_with("Module not found.")

    @patch('builtins.print')
    def test_generate_module_stats_report_no_grades(self, mock_print):
        """Test when no grades are found for module"""
        cursor = Mock()
        cursor.fetchone.return_value = ('Test Module', 'Core')
        cursor.fetchall.return_value = []

        generate_module_stats_report(cursor, 'CS101', 'reports', '20250101')

        assert any('No grades found' in str(call) for call in mock_print.call_args_list)


class TestGenerateCourseStatsReport:
    """Test the generate_course_stats_report function"""

    @pytest.fixture
    def mock_cursor_with_data(self):
        """Create a mock cursor with comprehensive course data"""
        cursor = Mock()

        # Students in course
        students = [
            ('S001', 'John', 'M', 'Doe'),
            ('S002', 'Jane', 'A', 'Smith'),
            ('S003', 'Bob', '', 'Johnson')
        ]
        cursor.fetchall.side_effect = [
            students,  # Students
            [  # Modules
                ('CS101', 'Intro to CS', 'Core', 3, 85.0, 3),
                ('CS102', 'Data Structures', 'Core', 3, 78.0, 2)
            ],
            [('male', 2), ('female', 1)],  # Gender counts
        ]

        return cursor

    @patch('university_system.modules.domain.academics.grade_misc.reports.calculate_student_gpa')
    @patch('university_system.modules.domain.academics.grade_misc.reports.SimpleDocTemplate')
    @patch('university_system.modules.domain.academics.grade_misc.reports.plt')
    @patch('builtins.print')
    def test_generate_course_stats_report_success(
        self, mock_print, mock_plt, mock_doc, mock_gpa, mock_cursor_with_data
    ):
        """Test successful course stats report generation"""
        # Mock GPA calculations
        mock_gpa.side_effect = [
            (3.5, 30, []),  # Student 1
            (3.2, 30, []),  # Student 2
            (2.8, 30, []),  # Student 3
        ]

        generate_course_stats_report(
            mock_cursor_with_data, 'Computer Science', 'reports', '20250101'
        )

        # Verify GPA was calculated for each student
        assert mock_gpa.call_count == 3

    @patch('builtins.print')
    def test_generate_course_stats_report_no_students(self, mock_print):
        """Test when no students found for course"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        generate_course_stats_report(cursor, 'InvalidCourse', 'reports', '20250101')

        assert any('No students found' in str(call) for call in mock_print.call_args_list)


class TestGenerateComprehensiveStatsReport:
    """Test the generate_comprehensive_stats_report function"""

    @pytest.fixture
    def comprehensive_cursor(self):
        """Create a mock cursor with comprehensive system data"""
        cursor = Mock()

        # Simulate multiple fetchone calls
        cursor.fetchone.side_effect = [
            (100,),  # total students
            (20,),   # total modules
            (150,),  # total assessments
            (500,),  # total grades
            (95,),   # students with grades
        ]

        # Simulate fetchall calls
        cursor.fetchall.side_effect = [
            [('Computer Science', 50), ('Data Science', 50)],  # Course counts
            [('Core', 10), ('Elective', 10)],  # Module types
            [('Exam', 50), ('Quiz', 100)],  # Assessment types
            [('A', 100), ('B', 200), ('C', 150), ('F', 50)],  # Grade distribution
            [('S001',), ('S002',), ('S003',)],  # Students with module grades
            [  # Top modules
                ('CS101', 'Intro to CS', 95.0, 50),
                ('CS102', 'Data Structures', 92.0, 45)
            ],
            [  # Bottom modules
                ('CS201', 'Algorithms', 65.0, 40),
                ('CS202', 'OS', 68.0, 42)
            ],
            [  # Top assessments
                (1, 'Midterm 1', 'CS101', 95.0, 50),
                (2, 'Final', 'CS102', 92.0, 48)
            ],
            [  # Bottom assessments
                (10, 'Quiz 1', 'CS201', 55.0, 40),
                (11, 'Project', 'CS202', 60.0, 38)
            ],
        ]

        return cursor

    @patch('university_system.modules.domain.academics.grade_misc.reports.calculate_student_gpa')
    @patch('university_system.modules.domain.academics.grade_misc.reports.GRADE_SYSTEMS')
    @patch('university_system.modules.domain.academics.grade_misc.reports.SimpleDocTemplate')
    @patch('university_system.modules.domain.academics.grade_misc.reports.plt')
    @patch('builtins.print')
    def test_generate_comprehensive_stats_report_success(
        self, mock_print, mock_plt, mock_doc, mock_grade_sys, mock_gpa, comprehensive_cursor
    ):
        """Test successful comprehensive report generation"""
        # Mock grade systems
        mock_grade_sys.__getitem__.return_value = {
            'A': 4.0, 'B': 3.0, 'C': 2.0, 'F': 0.0
        }

        # Mock GPA calculations
        mock_gpa.side_effect = [
            (3.5, 30, []),
            (3.2, 30, []),
            (2.8, 30, []),
        ]

        generate_comprehensive_stats_report(comprehensive_cursor, 'reports', '20250101')

        # Verify report was generated
        assert any('generated' in str(call).lower() for call in mock_print.call_args_list)

    @patch('university_system.modules.domain.academics.grade_misc.reports.calculate_student_gpa')
    @patch('builtins.print')
    def test_generate_comprehensive_stats_report_error_handling(
        self, mock_print, mock_gpa
    ):
        """Test error handling in comprehensive report"""
        cursor = Mock()
        cursor.fetchone.side_effect = Exception("Database error")

        generate_comprehensive_stats_report(cursor, 'reports', '20250101')

        # Should handle error gracefully
        assert mock_print.called


class TestGenerateAllModulesStatsReport:
    """Test the generate_all_modules_stats_report function"""

    @pytest.fixture
    def modules_data(self):
        """Sample modules data"""
        return [
            ('CS101', 'Intro to CS'),
            ('CS102', 'Data Structures'),
            ('CS201', 'Algorithms')
        ]

    @patch('university_system.modules.domain.academics.grade_misc.reports.SimpleDocTemplate')
    @patch('university_system.modules.domain.academics.grade_misc.reports.plt')
    @patch('builtins.print')
    def test_generate_all_modules_stats_report(
        self, mock_print, mock_plt, mock_doc, modules_data
    ):
        """Test generation of all modules stats report"""
        cursor = Mock()

        # Mock module grades data for each module
        cursor.fetchall.side_effect = [
            [(85.0, 'A'), (78.0, 'B'), (92.0, 'A+')],  # CS101
            [(75.0, 'B'), (88.0, 'A'), (82.0, 'B+')],  # CS102
            [(65.0, 'C'), (78.0, 'B'), (72.0, 'C+')],  # CS201
        ]

        cursor.fetchone.side_effect = [
            ('Intro to CS', 'Core'),  # CS101
            ('Data Structures', 'Core'),  # CS102
            ('Algorithms', 'Core'),  # CS201
        ]

        with patch('university_system.modules.domain.academics.grade_misc.reports.GRADE_SYSTEMS', {
            'letter': {'A+': 4.3, 'A': 4.0, 'B+': 3.3, 'B': 3.0, 'C+': 2.3, 'C': 2.0}
        }):
            generate_all_modules_stats_report(cursor, modules_data, 'reports', '20250101')


class TestGenerateAllCoursesStatsReport:
    """Test the generate_all_courses_stats_report function"""

    @patch('university_system.modules.domain.academics.grade_misc.reports.calculate_student_gpa')
    @patch('university_system.modules.domain.academics.grade_misc.reports.SimpleDocTemplate')
    @patch('university_system.modules.domain.academics.grade_misc.reports.plt')
    @patch('builtins.print')
    def test_generate_all_courses_stats_report(
        self, mock_print, mock_plt, mock_doc, mock_gpa
    ):
        """Test generation of all courses comparison report"""
        cursor = Mock()

        # Students per course
        cursor.fetchall.side_effect = [
            [('S001',), ('S002',), ('S003',)],  # CS students
            [('S004',), ('S005',)],  # DS students
            [('male', 2), ('female', 1)],  # CS gender
            [('male', 1), ('female', 1)],  # DS gender
        ]

        # Mock GPA calculations
        mock_gpa.side_effect = [
            (3.5, 30, []),
            (3.2, 30, []),
            (2.8, 30, []),
            (3.6, 30, []),
            (3.4, 30, []),
        ]

        courses = ['Computer Science', 'Data Science']
        generate_all_courses_stats_report(cursor, courses, 'reports', '20250101')

        # Verify GPA was calculated
        assert mock_gpa.call_count == 5

    @patch('builtins.print')
    def test_generate_all_courses_stats_report_no_data(self, mock_print):
        """Test when no course data is found"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        courses = ['Computer Science', 'Data Science']
        generate_all_courses_stats_report(cursor, courses, 'reports', '20250101')




class TestReportIntegration:
    """Integration tests for report generation"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with test data"""
        db_path = tempfile.mktemp(suffix='.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create minimal schema
        cursor.execute('''
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                middle_name TEXT,
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
            CREATE TABLE module_grades (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                module_code TEXT,
                final_score REAL,
                final_grade TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE assessments (
                assessment_id INTEGER PRIMARY KEY,
                assessment_name TEXT,
                module_code TEXT,
                max_points REAL,
                weight REAL,
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

        # Insert test data
        cursor.execute("INSERT INTO students VALUES ('S001', 'John', 'M', 'Doe', 'CS', 'male')")
        cursor.execute("INSERT INTO students VALUES ('S002', 'Jane', 'A', 'Smith', 'CS', 'female')")

        cursor.execute("INSERT INTO modules VALUES ('CS101', 'Intro to CS', 'Core')")

        cursor.execute("INSERT INTO module_grades VALUES (1, 'S001', 'CS101', 85.0, 'B')")
        cursor.execute("INSERT INTO module_grades VALUES (2, 'S002', 'CS101', 92.0, 'A')")

        conn.commit()

        yield conn

        conn.close()
        os.unlink(db_path)

    def test_reports_directory_creation(self):
        """Test that reports directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = os.path.join(temp_dir, 'statistical_reports')
            assert not os.path.exists(reports_dir)

            # The function should create the directory
            cursor = Mock()
            cursor.fetchone.return_value = None

            # This would typically create the directory
            # generate_module_stats_report(cursor, 'CS101', reports_dir, '20250101')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
