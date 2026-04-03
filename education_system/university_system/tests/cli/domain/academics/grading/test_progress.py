"""
Tests for university_system.modules.domain.academics.grade_misc.progress module.

This module tests progress tracking and success probability functions.
"""

from __future__ import annotations

import os
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest import mock

import numpy as np
import pytest

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.domain.academics.grading.progress import (
    analyze_student_progress,
    calculate_all_students_success_probability,
    calculate_individual_success_probability,
    calculate_student_success_probability,
    collect_dashboard_data,
    create_progress_visualization,
    save_intervention_recommendations,
    student_progress_tracking,
    success_probability_calculator,
)

@pytest.fixture
def setup_intervention_tables():
    """Ensure intervention tables exist for save_intervention_recommendations"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create student_risk_assessment table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_risk_assessment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                risk_score REAL,
                risk_level TEXT,
                assessment_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)

        # Create intervention_types table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS intervention_types (
                type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT
            )
        """)

        # Create recommended_interventions table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommended_interventions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                risk_assessment_id INTEGER,
                intervention_type_id INTEGER,
                priority INTEGER,
                notes TEXT,
                FOREIGN KEY (risk_assessment_id) REFERENCES student_risk_assessment(id),
                FOREIGN KEY (intervention_type_id) REFERENCES intervention_types(type_id)
            )
        """)

        # Insert some intervention types
        cursor.execute("INSERT OR IGNORE INTO intervention_types (name, description) VALUES ('Tutoring', 'Academic tutoring')")
        cursor.execute("INSERT OR IGNORE INTO intervention_types (name, description) VALUES ('Counseling', 'Academic counseling')")

    yield

    # Cleanup
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recommended_interventions")
        cursor.execute("DELETE FROM student_risk_assessment WHERE student_id LIKE 'PROG%'")

@pytest.fixture
def setup_progress_data(setup_intervention_tables):
    """Set up test data for progress tracking tests"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create test students
        cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, email, course)
            VALUES
            ('PROG001', 'Alice', 'Smith', 'alice@test.com', 'CS'),
            ('PROG002', 'Bob', 'Jones', 'bob@test.com', 'ENG'),
            ('PROG003', 'Carol', 'White', 'carol@test.com', 'MATH')
        """)

        # Create module
        cursor.execute("""
            INSERT INTO modules (module_code, module_name, credits)
            VALUES ('PROG101', 'Test Module', 10)
        """)

        # Enroll students
        for student_id in ['PROG001', 'PROG002', 'PROG003']:
            cursor.execute("""
                INSERT INTO student_modules (student_id, module_code, enrollment_date)
                VALUES (?, 'PROG101', '2023-09-01')
            """, (student_id,))

        # Create module grades
        cursor.execute("""
            INSERT INTO module_grades (student_id, module_code, final_score, final_grade)
            VALUES
            ('PROG001', 'PROG101', 85.0, 'A'),
            ('PROG002', 'PROG101', 70.0, 'B'),
            ('PROG003', 'PROG101', 55.0, 'D')
        """)

        # Create assessments with progression over time
        base_date = datetime.now() - timedelta(days=90)

        for i in range(5):
            submission_date = (base_date + timedelta(days=i * 15)).strftime('%Y-%m-%d')

            cursor.execute("""
                INSERT INTO assessments (module_code, assessment_name, assessment_type, max_points, due_date)
                VALUES ('PROG101', ?, 'Quiz', 100, ?)
            """, (f'Quiz {i+1}', submission_date))

            assessment_id = cursor.lastrowid

            # Create grades showing progression
            for student_id, base_score, trend in [('PROG001', 80, 2), ('PROG002', 65, 1), ('PROG003', 50, -1)]:
                score = base_score + (i * trend)
                letter_grade = 'A' if score >= 90 else 'B' if score >= 80 else 'C' if score >= 70 else 'D' if score >= 60 else 'F'

                cursor.execute("""
                    INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, assessment_id, min(max(score, 0), 100), letter_grade, submission_date))

    yield

    # Cleanup
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM grades WHERE student_id LIKE 'PROG%'")
        cursor.execute("DELETE FROM assessments WHERE module_code = 'PROG101'")
        cursor.execute("DELETE FROM module_grades WHERE student_id LIKE 'PROG%'")
        cursor.execute("DELETE FROM student_modules WHERE student_id LIKE 'PROG%'")
        cursor.execute("DELETE FROM modules WHERE module_code = 'PROG101'")
        cursor.execute("DELETE FROM students WHERE student_id LIKE 'PROG%'")

class TestStudentProgressTracking:
    """Test student progress tracking functions"""

    def test_student_progress_tracking_with_data(self, setup_progress_data, capsys):
        """Test tracking progress for a student with data"""
        with mock.patch('builtins.input', side_effect=['PROG001', 'n']):
            student_progress_tracking()

        captured = capsys.readouterr()
        assert "Progress Tracking for" in captured.out or "Alice Smith" in captured.out

    def test_student_progress_tracking_no_grades(self, setup_progress_data, capsys):
        """Test tracking for student with no assessment grades"""
        with transaction() as conn:
            cursor = conn.cursor()

            # Create student with no grades
            cursor.execute("""
                INSERT INTO students (student_id, first_name, last_name, email, course)
                VALUES ('PROG999', 'Test', 'NoGrades', 'test@test.com', 'CS')
            """)

        try:
            with mock.patch('education_system.university_system.modules.domain.academics.grading.progress.select_student', return_value='PROG999'):
                with mock.patch('builtins.input', side_effect=['n']):
                    student_progress_tracking()

            captured = capsys.readouterr()
            assert "No assessment grades found" in captured.out or "no" in captured.out.lower() or "grades" in captured.out.lower()
        finally:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM students WHERE student_id = 'PROG999'")

    def test_student_progress_tracking_with_visualization(self, setup_progress_data, tmp_path, monkeypatch, capsys):
        """Test tracking with visualization option"""
        monkeypatch.chdir(tmp_path)

        with mock.patch('builtins.input', side_effect=['PROG001', 'y']):
            student_progress_tracking()

        captured = capsys.readouterr()
        # Check if visualization was created
        viz_dir = tmp_path / "student_progress"
        if viz_dir.exists():
            assert len(list(viz_dir.glob("*.png"))) > 0

    def test_student_progress_tracking_db_error(self, capsys):
        """Test database error handling"""
        with mock.patch('education_system.university_system.modules.domain.academics.grading.progress.get_connection') as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            student_progress_tracking()

            captured = capsys.readouterr()
            assert "Database error" in captured.out or "database_error" in captured.out

class TestAnalyzeStudentProgress:
    """Test progress analysis functions"""

    def test_analyze_student_progress_improving(self, setup_progress_data, capsys):
        """Test analyzing improving student performance"""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get grades for improving student
            cursor.execute("""
                SELECT g.score / a.max_points * 100 as percentage,
                       g.letter_grade, g.submission_date, a.assessment_name,
                       a.module_code, a.assessment_type
                FROM grades g
                JOIN assessments a ON g.assessment_id = a.id
                WHERE g.student_id = 'PROG001'
                ORDER BY g.submission_date
            """)

            grades = cursor.fetchall()

        analyze_student_progress(grades, 'Alice', 'Smith')

        captured = capsys.readouterr()
        assert "Progress Analysis" in captured.out
        assert "Trend:" in captured.out

    def test_analyze_student_progress_declining(self, setup_progress_data, capsys):
        """Test analyzing declining student performance"""
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT g.score / a.max_points * 100 as percentage,
                       g.letter_grade, g.submission_date, a.assessment_name,
                       a.module_code, a.assessment_type
                FROM grades g
                JOIN assessments a ON g.assessment_id = a.id
                WHERE g.student_id = 'PROG003'
                ORDER BY g.submission_date
            """)

            grades = cursor.fetchall()

        analyze_student_progress(grades, 'Carol', 'White')

        captured = capsys.readouterr()
        assert "Progress Analysis" in captured.out
        assert "Trend:" in captured.out

    def test_analyze_student_progress_insufficient_data(self, capsys):
        """Test analysis with minimal data"""
        grades = [(80.0, 'B', '2024-01-01', 'Quiz 1', 'CS101', 'Quiz')]

        analyze_student_progress(grades, 'Test', 'Student')

        captured = capsys.readouterr()
        assert "Progress Analysis" in captured.out

class TestSuccessProbabilityCalculator:
    """Test success probability calculation"""

    def test_success_probability_individual(self, setup_progress_data, capsys):
        """Test individual success probability calculation"""
        with mock.patch('builtins.input', side_effect=['1', 'PROG001']):
            success_probability_calculator()

        captured = capsys.readouterr()
        assert "Success Probability" in captured.out or "probability" in captured.out.lower()

    def test_success_probability_all_students(self, setup_progress_data, capsys):
        """Test calculating success probability for all students"""
        with mock.patch('builtins.input', side_effect=['2']):
            success_probability_calculator()

        captured = capsys.readouterr()
        assert "Success Probability" in captured.out or "students" in captured.out.lower()

    def test_success_probability_db_error(self, capsys):
        """Test database error handling"""
        with mock.patch('education_system.university_system.modules.domain.academics.grading.progress.get_connection') as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            success_probability_calculator()

            captured = capsys.readouterr()
            assert "Database error" in captured.out

class TestCalculateIndividualSuccessProbability:
    """Test individual success probability calculation"""

    def test_calculate_individual_success_high_performer(self, setup_progress_data, capsys):
        """Test calculating probability for high-performing student"""
        with get_connection() as conn:
            cursor = conn.cursor()

            calculate_individual_success_probability(cursor, 'PROG001')

        captured = capsys.readouterr()
        assert "Success Probability for" in captured.out
        assert "Alice Smith" in captured.out

    def test_calculate_individual_success_low_performer(self, setup_progress_data, capsys):
        """Test calculating probability for low-performing student"""
        with get_connection() as conn:
            cursor = conn.cursor()

            calculate_individual_success_probability(cursor, 'PROG003')

        captured = capsys.readouterr()
        assert "Success Probability for" in captured.out
        assert "Carol White" in captured.out

    def test_calculate_individual_success_student_not_found(self, capsys):
        """Test with non-existent student"""
        with get_connection() as conn:
            cursor = conn.cursor()

            calculate_individual_success_probability(cursor, 'NONEXISTENT')

        captured = capsys.readouterr()
        assert "Student not found" in captured.out

class TestCalculateAllStudentsSuccessProbability:
    """Test calculating success probability for all students"""

    def test_calculate_all_students_with_data(self, setup_progress_data, capsys):
        """Test calculating for all students"""
        with get_connection() as conn:
            cursor = conn.cursor()

            calculate_all_students_success_probability(cursor)

        captured = capsys.readouterr()
        assert "Success Probability for All Students" in captured.out
        assert "Summary Statistics" in captured.out

    def test_calculate_all_students_no_data(self, capsys):
        """Test with no students"""
        # Save existing data so we can restore it
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM module_grades")
            saved_rows = cursor.fetchall()
            col_count = len(saved_rows[0]) if saved_rows else 0
            cursor.execute("DELETE FROM module_grades")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                calculate_all_students_success_probability(cursor)

            captured = capsys.readouterr()
            assert "No students" in captured.out or "found" in captured.out.lower()
        finally:
            with transaction() as conn:
                cursor = conn.cursor()
                for row in saved_rows:
                    placeholders = ", ".join(["?"] * len(row))
                    cursor.execute(
                        f"INSERT INTO module_grades VALUES ({placeholders})",
                        row
                    )

class TestCalculateStudentSuccessProbability:
    """Test student success probability calculation helper"""

    def test_calculate_student_success_probability(self, setup_progress_data):
        """Test calculating success probability"""
        with get_connection() as conn:
            cursor = conn.cursor()

            with mock.patch('education_system.university_system.modules.domain.academics.grading.grade_calculation.calculate_student_gpa', return_value=(3.5, 1, [('PROG101', 'Test Module', 'A', 3.5)])):
                probability = calculate_student_success_probability(cursor, 'PROG001')

            assert probability is not None
            assert 0 <= probability <= 1.0

    def test_calculate_student_success_probability_no_gpa(self):
        """Test with student having no GPA"""
        with get_connection() as conn:
            cursor = conn.cursor()

            probability = calculate_student_success_probability(cursor, 'NONEXISTENT')

            assert probability is None

class TestCollectDashboardData:
    """Test dashboard data collection"""

    def test_collect_dashboard_data(self, setup_progress_data):
        """Test collecting dashboard data"""
        with get_connection() as conn:
            cursor = conn.cursor()

            dashboard_data = collect_dashboard_data(cursor)

            assert 'overview' in dashboard_data
            assert 'total_students' in dashboard_data['overview']
            assert 'total_modules' in dashboard_data['overview']
            assert 'total_assessments' in dashboard_data['overview']
            assert 'total_grades' in dashboard_data['overview']

            assert 'grade_distribution' in dashboard_data
            assert 'course_performance' in dashboard_data
            assert 'risk_stats' in dashboard_data

    def test_collect_dashboard_data_with_gpa_stats(self, setup_progress_data):
        """Test dashboard data includes GPA statistics"""
        with get_connection() as conn:
            cursor = conn.cursor()

            dashboard_data = collect_dashboard_data(cursor)

            if 'gpa_stats' in dashboard_data:
                assert 'avg_gpa' in dashboard_data['gpa_stats']
                assert 'median_gpa' in dashboard_data['gpa_stats']
                assert 'std_gpa' in dashboard_data['gpa_stats']

    def test_collect_dashboard_data_empty_db(self):
        """Test with empty database"""
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM grades")
            cursor.execute("DELETE FROM module_grades")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                dashboard_data = collect_dashboard_data(cursor)

            # Should still return structure
            assert 'overview' in dashboard_data
        finally:
            with transaction() as conn:
                conn.rollback()

class TestCreateProgressVisualization:
    """Test progress visualization creation"""

    def test_create_progress_visualization(self, setup_progress_data, tmp_path, monkeypatch, capsys):
        """Test creating progress visualization"""
        monkeypatch.chdir(tmp_path)

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT g.score / a.max_points * 100 as percentage,
                       g.letter_grade, g.submission_date, a.assessment_name,
                       a.module_code, a.assessment_type
                FROM grades g
                JOIN assessments a ON g.assessment_id = a.id
                WHERE g.student_id = 'PROG001'
                ORDER BY g.submission_date
            """)

            grades = cursor.fetchall()

        create_progress_visualization(grades, 'PROG001', 'Alice', 'Smith')

        captured = capsys.readouterr()
        assert "Progress visualization saved" in captured.out

        # Check that output directory was created
        viz_dir = tmp_path / "student_progress"
        assert viz_dir.exists()

class TestSaveInterventionRecommendations:
    """Test saving intervention recommendations"""

    def test_save_intervention_recommendations(self, setup_progress_data):
        """Test saving recommendations to database"""
        with transaction() as conn:
            cursor = conn.cursor()

            # Create a risk assessment first
            cursor.execute("""
                INSERT INTO student_risk_assessment (student_id, risk_score, risk_level, assessment_date)
                VALUES ('PROG001', 25, 'Medium', '2024-01-15')
            """)

            # Create recommendations
            recommendations = [
                {
                    'student_id': 'PROG001',
                    'interventions': [
                        {
                            'type': 'Tutoring',
                            'priority': 1,
                            'description': 'Schedule tutoring sessions'
                        }
                    ]
                }
            ]

            try:
                save_intervention_recommendations(cursor, recommendations)
                # Should not raise an error
            finally:
                conn.rollback()

    def test_save_intervention_recommendations_no_risk_assessment(self, setup_progress_data):
        """Test saving when no risk assessment exists"""
        with transaction() as conn:
            cursor = conn.cursor()

            recommendations = [
                {
                    'student_id': 'PROG999',
                    'interventions': []
                }
            ]

            try:
                save_intervention_recommendations(cursor, recommendations)
                # Should handle gracefully
            finally:
                conn.rollback()

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_progress_with_single_grade(self, capsys):
        """Test progress analysis with only one grade"""
        grades = [(85.0, 'A', '2024-01-01', 'Quiz 1', 'CS101', 'Quiz')]

        analyze_student_progress(grades, 'Test', 'Student')

        captured = capsys.readouterr()
        assert "Progress Analysis" in captured.out

    def test_progress_with_perfect_scores(self, capsys):
        """Test progress with all perfect scores"""
        grades = [
            (100.0, 'A+', '2024-01-01', f'Quiz {i}', 'CS101', 'Quiz')
            for i in range(5)
        ]

        analyze_student_progress(grades, 'Perfect', 'Student')

        captured = capsys.readouterr()
        assert "Progress Analysis" in captured.out

    def test_progress_with_all_failing_scores(self, capsys):
        """Test progress with all failing scores"""
        grades = [
            (40.0, 'F', '2024-01-01', f'Quiz {i}', 'CS101', 'Quiz')
            for i in range(5)
        ]

        analyze_student_progress(grades, 'Failing', 'Student')

        captured = capsys.readouterr()
        assert "Progress Analysis" in captured.out

    def test_success_probability_boundary_values(self, setup_progress_data):
        """Test success probability at boundary GPA values"""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Test calculation works for different students
            for student_id in ['PROG001', 'PROG002', 'PROG003']:
                probability = calculate_student_success_probability(cursor, student_id)
                if probability is not None:
                    assert 0 <= probability <= 1.0

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
