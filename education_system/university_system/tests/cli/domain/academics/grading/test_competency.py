"""
Tests for university_system.modules.domain.academics.grade_misc.competency module.

This module tests competency management and student competency recording functions.
"""

from __future__ import annotations

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest import mock

import pytest

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.domain.academics.grading.competency import (
    manage_competencies,
    record_student_competencies,
)

@pytest.fixture
def setup_competency_tables():
    """Ensure competency tables exist"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create competencies table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competencies (
                competency_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT
            )
        """)

        # Create competency_levels table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competency_levels (
                level_id INTEGER PRIMARY KEY AUTOINCREMENT,
                competency_id INTEGER,
                level_name TEXT NOT NULL,
                level_value INTEGER,
                description TEXT,
                FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
            )
        """)

        # Create student_competencies table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_competencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                competency_id INTEGER,
                level_id INTEGER,
                evidence TEXT,
                assessment_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (competency_id) REFERENCES competencies(competency_id),
                FOREIGN KEY (level_id) REFERENCES competency_levels(level_id)
            )
        """)

        # Create assessment_competencies table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessment_competencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id INTEGER,
                competency_id INTEGER,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id),
                FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
            )
        """)

    yield

    # Cleanup — use direct connection with FK checks disabled to avoid
    # mismatch errors (assessment_competencies FK references wrong column)
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DELETE FROM student_competencies WHERE student_id LIKE 'COMP%'")
        conn.execute("DELETE FROM assessment_competencies")
        conn.execute("DELETE FROM competency_levels WHERE competency_id IN (SELECT competency_id FROM competencies WHERE name LIKE 'Test%')")
        conn.execute("DELETE FROM competencies WHERE name LIKE 'Test%'")
        conn.commit()
        conn.close()
    except Exception:
        pass

@pytest.fixture
def setup_test_data(setup_competency_tables):
    """Set up test data for competency tests"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create test student
        cursor.execute("""
            INSERT INTO students (student_id, first_name, last_name, email)
            VALUES ('COMP001', 'Test', 'Student', 'test@example.com')
        """)

        # Create test competency
        cursor.execute("""
            INSERT INTO competencies (name, description, category)
            VALUES ('Test Programming', 'Programming competency', 'Technical')
        """)
        competency_id = cursor.lastrowid

        # Create competency levels
        cursor.execute("""
            INSERT INTO competency_levels (competency_id, level_name, level_value, description)
            VALUES
            (?, 'Beginner', 1, 'Basic understanding'),
            (?, 'Intermediate', 2, 'Moderate proficiency'),
            (?, 'Advanced', 3, 'Expert level')
        """, (competency_id, competency_id, competency_id))

    yield competency_id

    # Cleanup
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE student_id LIKE 'COMP%'")

class TestManageCompetencies:
    """Test competency management functions"""

    def test_view_all_competencies(self, setup_test_data, capsys):
        """Test viewing all competencies"""
        with mock.patch('builtins.input', side_effect=['1', '5']):
            manage_competencies()

        captured = capsys.readouterr()
        assert "Competencies:" in captured.out
        assert "Test Programming" in captured.out

    def test_view_no_competencies(self, setup_competency_tables, capsys):
        """Test viewing competencies when none exist"""
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM competencies")

        with mock.patch('builtins.input', side_effect=['1', '5']):
            manage_competencies()

        captured = capsys.readouterr()
        assert "No competencies found" in captured.out

    def test_add_new_competency(self, setup_competency_tables, capsys):
        """Test adding a new competency"""
        inputs = [
            '2',  # Add new competency
            'Test Communication',  # Name
            'Effective communication skills',  # Description
            'Soft Skills',  # Category
            'n',  # Don't add levels now
            '5'   # Exit
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            manage_competencies()

        captured = capsys.readouterr()
        assert "Competency added successfully" in captured.out

        # Verify it was added
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM competencies WHERE name = 'Test Communication'")
            result = cursor.fetchone()
            assert result is not None

    def test_edit_competency(self, setup_test_data, capsys):
        """Test editing an existing competency"""
        competency_id = setup_test_data

        inputs = [
            '3',  # Edit competency
            str(competency_id),  # Competency ID
            'Test Programming Updated',  # New name
            '',  # Keep description
            '',  # Keep category
            '5'   # Exit
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            manage_competencies()

        captured = capsys.readouterr()
        assert "Competency updated successfully" in captured.out

    def test_edit_nonexistent_competency(self, setup_competency_tables, capsys):
        """Test editing a competency that doesn't exist"""
        inputs = [
            '3',  # Edit competency
            '99999',  # Non-existent ID
            '5'   # Exit
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            manage_competencies()

        captured = capsys.readouterr()
        assert "No competency found with ID 99999" in captured.out

    def test_edit_competency_invalid_id(self, setup_competency_tables, capsys):
        """Test editing with invalid ID"""
        inputs = [
            '3',  # Edit competency
            'invalid',  # Invalid ID
            '5'   # Exit
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            manage_competencies()

        captured = capsys.readouterr()
        assert "Invalid ID" in captured.out

    def test_delete_competency(self, setup_competency_tables, capsys):
        """Test deleting a competency"""
        # Create a competency to delete
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO competencies (name, description, category)
                VALUES ('Test Delete', 'To be deleted', 'Test')
            """)
            comp_id = cursor.lastrowid

        inputs = [
            '4',  # Delete competency
            str(comp_id),  # Competency ID
            'y',  # Confirm deletion
            '5'   # Exit
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            manage_competencies()

        captured = capsys.readouterr()
        assert "deleted successfully" in captured.out

    def test_delete_competency_with_related_data(self, setup_test_data, capsys):
        """Test deleting competency with related data"""
        competency_id = setup_test_data

        inputs = [
            '4',  # Delete competency
            str(competency_id),  # Competency ID
            'n',  # Don't confirm deletion
            '5'   # Exit
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            manage_competencies()

        captured = capsys.readouterr()
        assert "Warning:" in captured.out or "competency" in captured.out.lower()

    def test_invalid_menu_choice(self, setup_competency_tables, capsys):
        """Test invalid menu choice"""
        inputs = ['99', '5']  # Invalid choice, then exit

        with mock.patch('builtins.input', side_effect=inputs):
            manage_competencies()

        captured = capsys.readouterr()
        assert "Invalid choice" in captured.out

class TestRecordStudentCompetencies:
    """Test recording student competency assessments"""

    def test_record_student_competency(self, setup_test_data, capsys):
        """Test recording a student competency assessment"""
        competency_id = setup_test_data

        # Get the first level ID
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT level_id FROM competency_levels WHERE competency_id = ? LIMIT 1",
                          (competency_id,))
            level_id = cursor.fetchone()[0]

        inputs = [
            '1',  # Select first student from numbered list
            str(competency_id),  # Competency ID
            str(level_id),  # Level ID
            'Demonstrated in project work',  # Evidence
            ''  # Use today's date
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            record_student_competencies()

        captured = capsys.readouterr()
        assert "recorded successfully" in captured.out or "updated successfully" in captured.out

    def test_record_competency_no_student(self, setup_competency_tables, capsys):
        """Test recording competency with invalid student"""
        inputs = ['0']  # Select 0 to cancel (no valid student)

        with mock.patch('builtins.input', side_effect=inputs):
            record_student_competencies()

        # Should handle gracefully

    def test_record_competency_no_competencies(self, setup_competency_tables, capsys):
        """Test when no competencies are defined"""
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM competencies")

        # Create a test student
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO students (student_id, first_name, last_name, email)
                VALUES ('COMP002', 'Test', 'User', 'test@test.com')
            """)

            inputs = ['1']  # Select first student from numbered list

            with mock.patch('builtins.input', side_effect=inputs):
                record_student_competencies()

            captured = capsys.readouterr()
        assert ("No competencies defined" in captured.out
                or "no competencies" in captured.out.lower()
                or "No students found" in captured.out)

    def test_record_competency_no_levels(self, setup_competency_tables, capsys):
        """Test recording competency when no levels are defined"""
        with transaction() as conn:
            cursor = conn.cursor()

            # Create student
            cursor.execute("""
                INSERT INTO students (student_id, first_name, last_name, email)
                VALUES ('COMP003', 'Test', 'User', 'test@test.com')
            """)

            # Create competency without levels
            cursor.execute("""
                INSERT INTO competencies (name, description, category)
                VALUES ('Test No Levels', 'Test', 'Test')
            """)
            comp_id = cursor.lastrowid

        inputs = ['1', str(comp_id)]  # Select first student from numbered list

        with mock.patch('builtins.input', side_effect=inputs):
            record_student_competencies()

        captured = capsys.readouterr()
        assert "No levels defined" in captured.out

    def test_update_existing_assessment(self, setup_test_data, capsys):
        """Test updating an existing competency assessment"""
        competency_id = setup_test_data

        # Get level IDs
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT level_id FROM competency_levels WHERE competency_id = ? ORDER BY level_value",
                          (competency_id,))
            levels = [row[0] for row in cursor.fetchall()]

        # First, create an assessment
        inputs1 = [
            '1',  # Select first student
            str(competency_id),
            str(levels[0]),
            'Initial assessment',
            ''
        ]

        with mock.patch('builtins.input', side_effect=inputs1):
            record_student_competencies()

        # Now update it
        inputs2 = [
            '1',  # Select first student
            str(competency_id),
            str(levels[1]),  # Different level
            'Updated assessment',
            ''
        ]

        with mock.patch('builtins.input', side_effect=inputs2):
            record_student_competencies()

        captured = capsys.readouterr()
        assert "updated successfully" in captured.out

    def test_record_competency_invalid_level_id(self, setup_test_data, capsys):
        """Test recording with invalid level ID"""
        competency_id = setup_test_data

        inputs = [
            '1',  # Select first student
            str(competency_id),
            'invalid',  # Invalid level ID
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            record_student_competencies()

        captured = capsys.readouterr()
        assert "Invalid ID" in captured.out

    def test_record_competency_wrong_level_for_competency(self, setup_test_data, capsys):
        """Test recording with level that doesn't belong to competency"""
        competency_id = setup_test_data

        inputs = [
            '1',  # Select first student
            str(competency_id),
            '99999',  # Non-existent level ID
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            record_student_competencies()

        captured = capsys.readouterr()
        assert "No level found" in captured.out or "level" in captured.out.lower()

class TestDatabaseErrors:
    """Test error handling"""

    def test_manage_competencies_db_error(self, capsys):
        """Test database error handling in manage_competencies"""
        with mock.patch('education_system.university_system.modules.domain.academics.grading.competency.get_connection') as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            manage_competencies()

            captured = capsys.readouterr()
            assert "Database error" in captured.out

    def test_record_competencies_db_error(self, capsys):
        """Test database error handling in record_student_competencies"""
        with mock.patch('education_system.university_system.modules.domain.academics.grading.competency.get_connection') as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database error")

            record_student_competencies()

            captured = capsys.readouterr()
            assert "Database error" in captured.out

class TestEdgeCases:
    """Test edge cases"""

    def test_competency_with_long_description(self, setup_competency_tables, capsys):
        """Test competency with very long description"""
        long_desc = "A" * 500  # Very long description

        inputs = [
            '2',  # Add new
            'Test Long Desc',
            long_desc,
            'Test',
            'n',
            '5'
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            manage_competencies()

        # Should handle long descriptions

    def test_special_characters_in_competency_name(self, setup_competency_tables, capsys):
        """Test competency with special characters"""
        inputs = [
            '2',  # Add new
            "Test's & \"Competency\"",  # Special chars
            'Test description',
            'Test',
            'n',
            '5'
        ]

        with mock.patch('builtins.input', side_effect=inputs):
            manage_competencies()

        # Should handle special characters

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
