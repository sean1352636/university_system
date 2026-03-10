"""
Tests for university_system.modules.domain.academics.grade_misc.comparisons module.

This module tests all comparison functions including:
- Course comparisons
- Gender comparisons
- Module type comparisons
- Assessment type comparisons
- Time period comparisons
- Custom group comparisons
"""

from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta
from unittest import mock

import numpy as np
import pytest

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.domain.academics.grading.comparisons import (
    compare_by_assessment_type,
    compare_by_course,
    compare_by_enrollment_date,
    compare_by_gender,
    compare_by_module_codes,
    compare_by_module_type,
    compare_by_specific_courses,
    compare_by_time_period,
    custom_group_comparison,
    display_course_comparison,
    perform_statistical_test,
)


@pytest.fixture
def setup_test_data():
    """Set up test data for comparison tests"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create test students with different genders and courses
        cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, email, gender, course, enrollment_date)
            VALUES
            ('CMP001', 'Alice', 'Smith', 'alice@test.com', 'female', 'CS', '2023-01-15'),
            ('CMP002', 'Bob', 'Jones', 'bob@test.com', 'male', 'CS', '2023-01-20'),
            ('CMP003', 'Carol', 'White', 'carol@test.com', 'female', 'ENG', '2023-02-10'),
            ('CMP004', 'Dave', 'Brown', 'dave@test.com', 'male', 'ENG', '2023-02-15'),
            ('CMP005', 'Eve', 'Davis', 'eve@test.com', 'female', 'MATH', '2023-03-01')
        """)

        # Create modules with different types
        cursor.execute("""
            INSERT INTO modules (module_code, module_name, credits, module_type)
            VALUES
            ('CS101', 'Intro to CS', 10, 'Core'),
            ('CS102', 'Data Structures', 10, 'Core'),
            ('ENG101', 'English Lit', 10, 'Elective'),
            ('MATH101', 'Calculus', 10, 'Required')
        """)

        # Enroll students in modules
        enrollments = [
            ('CMP001', 'CS101'), ('CMP001', 'CS102'),
            ('CMP002', 'CS101'), ('CMP002', 'CS102'),
            ('CMP003', 'ENG101'),
            ('CMP004', 'ENG101'),
            ('CMP005', 'MATH101')
        ]
        for student_id, module_code in enrollments:
            cursor.execute("""
                INSERT INTO student_modules (student_id, module_code, enrollment_date)
                VALUES (?, ?, ?)
            """, (student_id, module_code, '2023-09-01'))

        # Create module grades
        cursor.execute("""
            INSERT INTO module_grades (student_id, module_code, final_score, final_grade)
            VALUES
            ('CMP001', 'CS101', 85.0, 'A'),
            ('CMP001', 'CS102', 90.0, 'A+'),
            ('CMP002', 'CS101', 78.0, 'B'),
            ('CMP002', 'CS102', 82.0, 'A-'),
            ('CMP003', 'ENG101', 88.0, 'A'),
            ('CMP004', 'ENG101', 75.0, 'B'),
            ('CMP005', 'MATH101', 65.0, 'C')
        """)

        # Create assessments with different types
        today = datetime.now().strftime('%Y-%m-%d')
        assessments = [
            ('CS101', 'Quiz 1', 'Quiz', 10, '2023-09-15'),
            ('CS101', 'Midterm', 'Exam', 40, '2023-10-15'),
            ('CS102', 'Assignment 1', 'Assignment', 20, '2023-10-01'),
            ('ENG101', 'Essay 1', 'Essay', 30, '2023-09-20')
        ]

        assessment_ids = []
        for module_code, name, assess_type, max_points, due_date in assessments:
            cursor.execute("""
                INSERT INTO assessments (module_code, assessment_name, assessment_type, max_points, due_date)
                VALUES (?, ?, ?, ?, ?)
            """, (module_code, name, assess_type, max_points, due_date))
            assessment_ids.append(cursor.lastrowid)

        # Create grades for assessments
        submission_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
            VALUES
            ('CMP001', ?, 9.0, 'A', ?),
            ('CMP001', ?, 36.0, 'A', ?),
            ('CMP002', ?, 7.5, 'B', ?)
        """, (assessment_ids[0], submission_date, assessment_ids[1], submission_date,
              assessment_ids[0], submission_date))

    yield

    # Cleanup
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM grades WHERE student_id LIKE 'CMP%'")
        cursor.execute("DELETE FROM assessments WHERE module_code LIKE 'CS%' OR module_code LIKE 'ENG%' OR module_code LIKE 'MATH%'")
        cursor.execute("DELETE FROM module_grades WHERE student_id LIKE 'CMP%'")
        cursor.execute("DELETE FROM student_modules WHERE student_id LIKE 'CMP%'")
        cursor.execute("DELETE FROM modules WHERE module_code IN ('CS101', 'CS102', 'ENG101', 'MATH101')")
        cursor.execute("DELETE FROM students WHERE student_id LIKE 'CMP%'")


class TestCompareByCourse:
    """Test course comparison functions"""

    def test_compare_by_course_with_data(self, setup_test_data, capsys):
        """Test compare_by_course with valid data"""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Mock user input to skip visualization and export
            with mock.patch('builtins.input', side_effect=['n', 'n']):
                compare_by_course(cursor)

            captured = capsys.readouterr()
            assert "Course Performance Comparison" in captured.out
            assert "CS" in captured.out
            assert "ENG" in captured.out

    def test_compare_by_course_no_data(self, capsys):
        """Test compare_by_course with no data"""
        with get_connection() as conn:
            cursor = conn.cursor()
            # Create a temporary empty scenario
            cursor.execute("DELETE FROM module_grades")

            try:
                with mock.patch('builtins.input', side_effect=['n', 'n']):
                    compare_by_course(cursor)

                captured = capsys.readouterr()
                assert "No course data found" in captured.out
            finally:
                conn.rollback()

    def test_display_course_comparison(self, capsys):
        """Test display_course_comparison function"""
        comparison_data = [
            {
                'course': 'CS',
                'student_count': 2,
                'avg_gpa': 3.5,
                'avg_score': 83.75,
                'passing_rate': 100.0,
                'excellence_rate': 75.0,
                'std_dev': 5.2
            },
            {
                'course': 'ENG',
                'student_count': 2,
                'avg_gpa': 3.0,
                'avg_score': 81.5,
                'passing_rate': 100.0,
                'excellence_rate': 50.0,
                'std_dev': 6.5
            }
        ]

        display_course_comparison(comparison_data)

        captured = capsys.readouterr()
        assert "COURSE PERFORMANCE COMPARISON" in captured.out
        assert "Best Performing Course" in captured.out
        assert "Worst Performing Course" in captured.out


class TestCompareByGender:
    """Test gender comparison functions"""

    def test_compare_by_gender_with_data(self, setup_test_data, capsys):
        """Test compare_by_gender with valid data"""
        with get_connection() as conn:
            cursor = conn.cursor()
            compare_by_gender(cursor)

            captured = capsys.readouterr()
            assert "Gender Performance Comparison" in captured.out
            assert "Female" in captured.out or "Male" in captured.out

    def test_compare_by_gender_no_data(self, capsys):
        """Test compare_by_gender with no gender data"""
        with transaction() as conn:
            cursor = conn.cursor()
            # Clear gender data temporarily
            cursor.execute("UPDATE students SET gender = NULL")

            try:
                compare_by_gender(cursor)
                captured = capsys.readouterr()
                assert "No gender data available" in captured.out
            finally:
                conn.rollback()

    @pytest.mark.skipif(True, reason="Requires scipy for t-test")
    def test_perform_statistical_test(self, setup_test_data, capsys):
        """Test statistical significance testing"""
        with get_connection() as conn:
            cursor = conn.cursor()

            gender_stats = [
                {
                    'gender': 'Female',
                    'student_count': 3,
                    'avg_score': 82.0,
                    'passing_rate': 100.0,
                    'excellence_rate': 66.7,
                    'total_grades': 3
                },
                {
                    'gender': 'Male',
                    'student_count': 2,
                    'avg_score': 80.0,
                    'passing_rate': 100.0,
                    'excellence_rate': 50.0,
                    'total_grades': 2
                }
            ]

            perform_statistical_test(cursor, gender_stats)

            captured = capsys.readouterr()
            assert "Statistical" in captured.out


class TestCompareByModuleType:
    """Test module type comparison functions"""

    def test_compare_by_module_type_with_data(self, setup_test_data, capsys):
        """Test compare_by_module_type with valid data"""
        with get_connection() as conn:
            cursor = conn.cursor()
            compare_by_module_type(cursor)

            captured = capsys.readouterr()
            assert "Module Type Performance Comparison" in captured.out
            assert "Core" in captured.out or "Elective" in captured.out

    def test_compare_by_module_type_no_data(self, capsys):
        """Test compare_by_module_type with no data"""
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM module_grades")

            try:
                compare_by_module_type(cursor)
                captured = capsys.readouterr()
                assert "No module type data available" in captured.out
            finally:
                conn.rollback()


class TestCompareByAssessmentType:
    """Test assessment type comparison functions"""

    def test_compare_by_assessment_type_with_data(self, setup_test_data, capsys):
        """Test compare_by_assessment_type with valid data"""
        with get_connection() as conn:
            cursor = conn.cursor()

            with mock.patch('builtins.input', return_value='n'):
                compare_by_assessment_type(cursor)

            captured = capsys.readouterr()
            assert "Assessment Type Performance Comparison" in captured.out

    def test_compare_by_assessment_type_export(self, setup_test_data, capsys, tmp_path, monkeypatch):
        """Test compare_by_assessment_type with export"""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        with get_connection() as conn:
            cursor = conn.cursor()

            with mock.patch('builtins.input', return_value='y'):
                compare_by_assessment_type(cursor)

            captured = capsys.readouterr()
            assert "Export" in captured.out


class TestCompareByTimePeriod:
    """Test time period comparison functions"""

    def test_compare_by_time_period_with_data(self, setup_test_data, capsys):
        """Test compare_by_time_period with valid data"""
        with get_connection() as conn:
            cursor = conn.cursor()
            compare_by_time_period(cursor)

            captured = capsys.readouterr()
            assert "Time Period Performance Comparison" in captured.out

    def test_compare_by_time_period_insufficient_data(self, capsys):
        """Test compare_by_time_period with insufficient data"""
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM grades")

            try:
                compare_by_time_period(cursor)
                captured = capsys.readouterr()
                assert "Insufficient time-based data" in captured.out
            finally:
                conn.rollback()


class TestCustomGroupComparison:
    """Test custom group comparison functions"""

    def test_compare_by_module_codes(self, setup_test_data, capsys):
        """Test compare_by_module_codes"""
        with get_connection() as conn:
            cursor = conn.cursor()

            with mock.patch('builtins.input', return_value='CS101, CS102'):
                compare_by_module_codes(cursor)

            captured = capsys.readouterr()
            assert "Module Code Comparison" in captured.out

    def test_compare_by_module_codes_no_modules(self, capsys):
        """Test compare_by_module_codes with no modules"""
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM modules")

            try:
                compare_by_module_codes(cursor)
                captured = capsys.readouterr()
                assert "No modules found" in captured.out
            finally:
                conn.rollback()

    def test_compare_by_enrollment_date(self, setup_test_data):
        """Test compare_by_enrollment_date"""
        with get_connection() as conn:
            cursor = conn.cursor()

            with mock.patch('builtins.input', side_effect=['2023-01-31', '2023-02-01']):
                compare_by_enrollment_date(cursor)

    def test_compare_by_specific_courses(self, setup_test_data, capsys):
        """Test compare_by_specific_courses"""
        with get_connection() as conn:
            cursor = conn.cursor()

            with mock.patch('builtins.input', return_value='CS, ENG'):
                compare_by_specific_courses(cursor)

            captured = capsys.readouterr()
            assert "Specific Course Comparison" in captured.out

    def test_custom_group_comparison_menu(self, setup_test_data):
        """Test custom_group_comparison menu navigation"""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Test each menu option
            with mock.patch('builtins.input', side_effect=['1', 'CS101, CS102']):
                custom_group_comparison(cursor)

            with mock.patch('builtins.input', side_effect=['4', 'CS, ENG']):
                custom_group_comparison(cursor)

            with mock.patch('builtins.input', return_value='5'):
                custom_group_comparison(cursor)


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_comparison_data(self, capsys):
        """Test with empty comparison data"""
        display_course_comparison([])
        captured = capsys.readouterr()
        # Should handle empty data gracefully

    def test_single_course_comparison(self, setup_test_data, capsys):
        """Test comparison with single course"""
        with transaction() as conn:
            cursor = conn.cursor()
            # Keep only one course
            cursor.execute("DELETE FROM students WHERE course != 'CS'")

            try:
                with mock.patch('builtins.input', side_effect=['n', 'n']):
                    compare_by_course(cursor)

                captured = capsys.readouterr()
                assert "Course Performance Comparison" in captured.out
            finally:
                conn.rollback()

    def test_comparison_with_null_scores(self, setup_test_data):
        """Test comparisons with NULL scores"""
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE module_grades SET final_score = NULL WHERE student_id = 'CMP005'")

            try:
                with mock.patch('builtins.input', side_effect=['n', 'n']):
                    compare_by_course(cursor)
            finally:
                conn.rollback()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
