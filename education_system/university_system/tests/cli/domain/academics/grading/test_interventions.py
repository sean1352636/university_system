"""
Tests for university_system.modules.domain.academics.grade_misc.interventions module.

This module tests intervention recommendation functions.
"""

from __future__ import annotations

from education_system.university_system.infrastructure.database.db import sqlite3
from unittest import mock

import pytest

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.domain.academics.grading.interventions import (
    display_intervention_recommendations,
    generate_intervention_plan,
    generate_system_recommendations,
    intervention_recommendations,
)

@pytest.fixture
def setup_intervention_tables():
    """Ensure intervention tables exist"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create parent tables required by foreign keys
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                middle_name TEXT,
                last_name TEXT NOT NULL,
                course TEXT NOT NULL,
                email_address TEXT,
                gender TEXT,
                dob TEXT,
                age INTEGER,
                enrollment_date TEXT DEFAULT (date('now')),
                status TEXT DEFAULT 'Active',
                grade_level TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT NOT NULL,
                module_type TEXT,
                credits INTEGER DEFAULT 1,
                description TEXT,
                course TEXT,
                semester TEXT,
                year INTEGER
            )
        """)

        cursor.execute("""
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
        """)

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
                description TEXT,
                category TEXT
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
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (risk_assessment_id) REFERENCES student_risk_assessment(id),
                FOREIGN KEY (intervention_type_id) REFERENCES intervention_types(type_id)
            )
        """)

        # Insert intervention types
        intervention_types = [
            ('Academic Advising', 'Meeting with academic advisor', 'Academic'),
            ('Tutoring', 'One-on-one or group tutoring', 'Academic'),
            ('Study Skills Workshop', 'Workshop on study techniques', 'Skills'),
            ('Mentoring', 'Peer or faculty mentoring', 'Support'),
            ('Counseling', 'Academic or personal counseling', 'Support'),
            ('Modified Schedule', 'Course load adjustment', 'Administrative')
        ]

        for name, desc, category in intervention_types:
            cursor.execute("""
                INSERT OR IGNORE INTO intervention_types (name, description, category)
                VALUES (?, ?, ?)
            """, (name, desc, category))

    yield

    # Cleanup
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recommended_interventions")
        cursor.execute("DELETE FROM student_risk_assessment WHERE student_id LIKE 'INTV%'")

@pytest.fixture
def setup_test_data(setup_intervention_tables):
    """Set up test data for intervention tests"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create test students
        cursor.execute("""
            INSERT OR IGNORE INTO students (student_id, first_name, last_name, email_address, course)
            VALUES
            ('INTV001', 'Alice', 'Smith', 'alice@test.com', 'CS'),
            ('INTV002', 'Bob', 'Jones', 'bob@test.com', 'ENG'),
            ('INTV003', 'Carol', 'White', 'carol@test.com', 'MATH')
        """)

        # Create module for grading
        cursor.execute("""
            INSERT OR IGNORE INTO modules (module_code, module_name, credits)
            VALUES ('INTV101', 'Test Module', 10)
        """)

        # Create module grades
        cursor.execute("""
            INSERT OR IGNORE INTO module_grades (student_id, module_code, final_score, final_grade)
            VALUES
            ('INTV001', 'INTV101', 85.0, 'A'),
            ('INTV002', 'INTV101', 65.0, 'C'),
            ('INTV003', 'INTV101', 45.0, 'F')
        """)

        # Create risk assessments
        cursor.execute("""
            INSERT INTO student_risk_assessment (student_id, risk_score, risk_level, assessment_date)
            VALUES
            ('INTV001', 10, 'Low', '2024-01-15'),
            ('INTV002', 30, 'Medium', '2024-01-15'),
            ('INTV003', 50, 'High', '2024-01-15')
        """)

    yield

    # Cleanup
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM module_grades WHERE student_id LIKE 'INTV%'")
        cursor.execute("DELETE FROM modules WHERE module_code = 'INTV101'")
        cursor.execute("DELETE FROM students WHERE student_id LIKE 'INTV%'")

class TestInterventionRecommendations:
    """Test intervention recommendation generation"""

    def test_intervention_recommendations_with_data(self, setup_test_data, capsys):
        """Test generating intervention recommendations"""
        intervention_recommendations()

        captured = capsys.readouterr()
        assert "Intervention Recommendations" in captured.out or "INTERVENTION RECOMMENDATIONS" in captured.out

    def test_intervention_recommendations_no_data(self, setup_intervention_tables, capsys):
        """Test with no risk assessments"""
        # Save existing data so we can restore it
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM student_risk_assessment")
            saved_rows = cursor.fetchall()
            cursor.execute("DELETE FROM student_risk_assessment")

        try:
            intervention_recommendations()

            captured = capsys.readouterr()
            assert "No risk assessments found" in captured.out or "Run Student Risk Assessment" in captured.out
        finally:
            with transaction() as conn:
                cursor = conn.cursor()
                for row in saved_rows:
                    cursor.execute(
                        "INSERT INTO student_risk_assessment VALUES (?, ?, ?, ?, ?)",
                        row
                    )

    def test_intervention_recommendations_database_error(self, capsys):
        """Test database error handling"""
        with mock.patch('education_system.university_system.modules.domain.academics.grade_misc.interventions.get_connection') as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            intervention_recommendations()

            captured = capsys.readouterr()
            assert "Database error" in captured.out

class TestGenerateInterventionPlan:
    """Test individual intervention plan generation"""

    def test_generate_intervention_plan_high_risk(self, setup_test_data):
        """Test generating plan for high-risk student"""
        with get_connection() as conn:
            cursor = conn.cursor()

            plan = generate_intervention_plan(
                cursor,
                'INTV003',
                'Carol',
                'White',
                'MATH',
                50,
                'High'
            )

            assert plan is not None
            assert plan['student_id'] == 'INTV003'
            assert plan['name'] == 'Carol White'
            assert plan['risk_level'] == 'High'
            assert plan['risk_score'] == 50
            assert 'interventions' in plan
            assert len(plan['interventions']) > 0

            # High risk should include multiple interventions
            intervention_types = [i['type'] for i in plan['interventions']]
            assert 'Academic Advising' in intervention_types

    def test_generate_intervention_plan_medium_risk(self, setup_test_data):
        """Test generating plan for medium-risk student"""
        with get_connection() as conn:
            cursor = conn.cursor()

            plan = generate_intervention_plan(
                cursor,
                'INTV002',
                'Bob',
                'Jones',
                'ENG',
                30,
                'Medium'
            )

            assert plan is not None
            assert plan['risk_level'] == 'Medium'
            assert len(plan['interventions']) > 0

    def test_generate_intervention_plan_low_risk(self, setup_test_data):
        """Test generating plan for low-risk student"""
        with get_connection() as conn:
            cursor = conn.cursor()

            plan = generate_intervention_plan(
                cursor,
                'INTV001',
                'Alice',
                'Smith',
                'CS',
                10,
                'Low'
            )

            assert plan is not None
            assert plan['risk_level'] == 'Low'
            # Low risk may have fewer or no interventions

    def test_intervention_plan_includes_tutoring(self, setup_test_data):
        """Test that tutoring is recommended for low GPA"""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Student with failing grade should get tutoring recommendation
            plan = generate_intervention_plan(
                cursor,
                'INTV003',
                'Carol',
                'White',
                'MATH',
                50,
                'High'
            )

            intervention_types = [i['type'] for i in plan['interventions']]
            assert 'Tutoring' in intervention_types

    def test_intervention_plan_priorities(self, setup_test_data):
        """Test that interventions are prioritized correctly"""
        with get_connection() as conn:
            cursor = conn.cursor()

            plan = generate_intervention_plan(
                cursor,
                'INTV003',
                'Carol',
                'White',
                'MATH',
                50,
                'High'
            )

            # Should be sorted by priority
            priorities = [i['priority'] for i in plan['interventions']]
            assert priorities == sorted(priorities)

class TestDisplayInterventionRecommendations:
    """Test displaying intervention recommendations"""

    def test_display_intervention_recommendations(self, setup_test_data, capsys):
        """Test displaying recommendations"""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Generate some recommendations
            recommendations = []
            for student_id, first_name, last_name, course, risk_score, risk_level in [
                ('INTV001', 'Alice', 'Smith', 'CS', 10, 'Low'),
                ('INTV002', 'Bob', 'Jones', 'ENG', 30, 'Medium'),
                ('INTV003', 'Carol', 'White', 'MATH', 50, 'High')
            ]:
                plan = generate_intervention_plan(
                    cursor, student_id, first_name, last_name, course, risk_score, risk_level
                )
                recommendations.append(plan)

        display_intervention_recommendations(recommendations)

        captured = capsys.readouterr()
        assert "INTERVENTION RECOMMENDATIONS" in captured.out
        assert "Alice Smith" in captured.out
        assert "Bob Jones" in captured.out
        assert "Carol White" in captured.out

    def test_display_empty_recommendations(self, capsys):
        """Test displaying empty recommendations"""
        display_intervention_recommendations([])

        captured = capsys.readouterr()
        assert "INTERVENTION RECOMMENDATIONS" in captured.out

class TestGenerateSystemRecommendations:
    """Test system-wide recommendation generation"""

    def test_generate_system_recommendations_high_risk(self):
        """Test recommendations when many students are high risk"""
        risk_data = {
            'students': ['S1', 'S2', 'S3'],
            'summary_stats': {
                'total_students': 100,
                'avg_risk_score': 35,
                'risk_distribution': {
                    'High': 20,
                    'Medium': 30,
                    'Low': 50
                }
            }
        }

        recommendations = generate_system_recommendations(risk_data)

        assert len(recommendations) > 0
        assert isinstance(recommendations, list)

        # Should include emergency intervention for high percentage
        rec_text = ' '.join(recommendations)
        assert 'emergency' in rec_text.lower() or 'intervention' in rec_text.lower()

    def test_generate_system_recommendations_medium_risk(self):
        """Test recommendations for moderate risk scenario"""
        risk_data = {
            'students': ['S1', 'S2'],
            'summary_stats': {
                'total_students': 100,
                'avg_risk_score': 22,
                'risk_distribution': {
                    'High': 5,
                    'Medium': 30,
                    'Low': 65
                }
            }
        }

        recommendations = generate_system_recommendations(risk_data)

        assert len(recommendations) > 0
        rec_text = ' '.join(recommendations)
        assert 'tutoring' in rec_text.lower() or 'support' in rec_text.lower()

    def test_generate_system_recommendations_low_risk(self):
        """Test recommendations when risk is low"""
        risk_data = {
            'students': ['S1'],
            'summary_stats': {
                'total_students': 100,
                'avg_risk_score': 15,
                'risk_distribution': {
                    'High': 2,
                    'Medium': 10,
                    'Low': 88
                }
            }
        }

        recommendations = generate_system_recommendations(risk_data)

        assert len(recommendations) > 0
        # Should still have general recommendations
        assert 'risk assessment' in ' '.join(recommendations).lower() or 'monitoring' in ' '.join(recommendations).lower()

    def test_generate_system_recommendations_no_students(self):
        """Test with no students"""
        risk_data = {
            'students': [],
            'summary_stats': {
                'total_students': 0,
                'avg_risk_score': 0,
                'risk_distribution': {
                    'High': 0,
                    'Medium': 0,
                    'Low': 0
                }
            }
        }

        recommendations = generate_system_recommendations(risk_data)

        assert isinstance(recommendations, list)
        assert len(recommendations) == 0

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_intervention_plan_with_null_gpa(self, setup_test_data):
        """Test generating plan when GPA cannot be calculated"""
        with transaction() as conn:
            cursor = conn.cursor()

            # Create student with no grades
            cursor.execute("""
                INSERT OR IGNORE INTO students (student_id, first_name, last_name, email_address, course)
                VALUES ('INTV999', 'Test', 'NoGrades', 'test@test.com', 'CS')
            """)

            try:
                plan = generate_intervention_plan(
                    cursor,
                    'INTV999',
                    'Test',
                    'NoGrades',
                    'CS',
                    25,
                    'Medium'
                )

                assert plan is not None
                # Should still generate interventions even without GPA
            finally:
                cursor.execute("DELETE FROM students WHERE student_id = 'INTV999'")
                conn.rollback()

    def test_intervention_plan_boundary_risk_scores(self, setup_test_data):
        """Test with boundary risk scores"""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Test with risk score exactly at thresholds
            for risk_score in [20, 40, 60]:
                plan = generate_intervention_plan(
                    cursor,
                    'INTV001',
                    'Alice',
                    'Smith',
                    'CS',
                    risk_score,
                    'Medium'
                )

                assert plan is not None
                assert plan['risk_score'] == risk_score

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
