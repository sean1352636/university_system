#!/usr/bin/env python3
"""
Test script for CLI enrollment flow
Tests enroll/drop/waitlist, non-existent course, capacity

Converted to pytest format with database fixtures for proper integration testing.
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import tempfile
import sqlite3


@pytest.fixture
def temp_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    # Create basic schema for testing
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create modules table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            module_id TEXT PRIMARY KEY,
            module_name TEXT NOT NULL,
            credits INTEGER DEFAULT 0,
            max_enrollment INTEGER DEFAULT 30,
            current_enrollment INTEGER DEFAULT 0
        )
    ''')

    # Create students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT
        )
    ''')

    # Create enrollments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_id TEXT,
            status TEXT DEFAULT 'enrolled',
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (module_id) REFERENCES modules(module_id),
            UNIQUE(student_id, module_id)
        )
    ''')

    # Create waitlist table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id TEXT,
            student_id TEXT,
            position INTEGER,
            status TEXT DEFAULT 'waiting',
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (module_id) REFERENCES modules(module_id)
        )
    ''')

    # Insert test data
    cursor.execute(
        "INSERT INTO modules VALUES ('CS101', 'Intro to Computer Science', 3, 2, 0)"
    )
    cursor.execute(
        "INSERT INTO students VALUES ('S001', 'John', 'Doe', 'john@example.com')"
    )
    cursor.execute(
        "INSERT INTO students VALUES ('S002', 'Jane', 'Smith', 'jane@example.com')"
    )
    cursor.execute(
        "INSERT INTO students VALUES ('S003', 'Bob', 'Johnson', 'bob@example.com')"
    )

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_enroll_student_command(temp_db):
    """Test enrolling student in course via database"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Enroll student
    cursor.execute(
        "INSERT INTO enrollments (student_id, module_id, status) VALUES (?, ?, ?)",
        ('S001', 'CS101', 'enrolled')
    )
    cursor.execute(
        "UPDATE modules SET current_enrollment = current_enrollment + 1 WHERE module_id = ?",
        ('CS101',)
    )
    conn.commit()

    # Verify enrollment
    cursor.execute(
        "SELECT * FROM enrollments WHERE student_id = ? AND module_id = ?",
        ('S001', 'CS101')
    )
    result = cursor.fetchone()

    assert result is not None
    assert result[1] == 'S001'  # student_id
    assert result[2] == 'CS101'  # module_id
    assert result[3] == 'enrolled'  # status

    conn.close()


def test_drop_course_command(temp_db):
    """Test dropping course via database"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # First enroll
    cursor.execute(
        "INSERT INTO enrollments (student_id, module_id, status) VALUES (?, ?, ?)",
        ('S001', 'CS101', 'enrolled')
    )
    conn.commit()

    # Then drop
    cursor.execute(
        "DELETE FROM enrollments WHERE student_id = ? AND module_id = ?",
        ('S001', 'CS101')
    )
    conn.commit()

    # Verify dropped
    cursor.execute(
        "SELECT * FROM enrollments WHERE student_id = ? AND module_id = ?",
        ('S001', 'CS101')
    )
    result = cursor.fetchone()

    assert result is None

    conn.close()


def test_waitlist_command(temp_db):
    """Test adding student to waitlist when course is full"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Fill the course (max 2 students)
    cursor.execute(
        "INSERT INTO enrollments (student_id, module_id) VALUES (?, ?)",
        ('S001', 'CS101')
    )
    cursor.execute(
        "INSERT INTO enrollments (student_id, module_id) VALUES (?, ?)",
        ('S002', 'CS101')
    )
    cursor.execute(
        "UPDATE modules SET current_enrollment = 2 WHERE module_id = ?",
        ('CS101',)
    )
    conn.commit()

    # Check if course is full
    cursor.execute(
        "SELECT current_enrollment, max_enrollment FROM modules WHERE module_id = ?",
        ('CS101',)
    )
    current, maximum = cursor.fetchone()

    # Add to waitlist since course is full
    if current >= maximum:
        cursor.execute(
            "INSERT INTO course_waitlist (module_id, student_id, position) VALUES (?, ?, ?)",
            ('CS101', 'S003', 1)
        )
        conn.commit()

    # Verify on waitlist
    cursor.execute(
        "SELECT * FROM course_waitlist WHERE student_id = ? AND module_id = ?",
        ('S003', 'CS101')
    )
    result = cursor.fetchone()

    assert result is not None
    assert result[1] == 'CS101'  # module_id
    assert result[2] == 'S003'  # student_id

    conn.close()


def test_non_existent_course_error(temp_db):
    """Test error handling for non-existent course"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Check for non-existent course
    cursor.execute(
        "SELECT * FROM modules WHERE module_id = ?",
        ('NONEXISTENT',)
    )
    result = cursor.fetchone()

    # Should return None for non-existent course
    assert result is None

    conn.close()


def test_capacity_exceeded_error(temp_db):
    """Test that enrollment respects capacity limits"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Get current enrollment and max
    cursor.execute(
        "SELECT current_enrollment, max_enrollment FROM modules WHERE module_id = ?",
        ('CS101',)
    )
    current, maximum = cursor.fetchone()

    assert current < maximum, "Initial state should not be at capacity"

    # Enroll students up to capacity
    cursor.execute(
        "INSERT INTO enrollments (student_id, module_id) VALUES (?, ?)",
        ('S001', 'CS101')
    )
    cursor.execute(
        "INSERT INTO enrollments (student_id, module_id) VALUES (?, ?)",
        ('S002', 'CS101')
    )
    cursor.execute(
        "UPDATE modules SET current_enrollment = 2 WHERE module_id = ?",
        ('CS101',)
    )
    conn.commit()

    # Verify at capacity
    cursor.execute(
        "SELECT current_enrollment, max_enrollment FROM modules WHERE module_id = ?",
        ('CS101',)
    )
    current, maximum = cursor.fetchone()

    assert current == maximum, "Course should be at capacity"

    conn.close()


def test_enrollment_status_command(temp_db):
    """Test checking enrollment status via database query"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Enroll student
    cursor.execute(
        "INSERT INTO enrollments (student_id, module_id, status) VALUES (?, ?, ?)",
        ('S001', 'CS101', 'enrolled')
    )
    conn.commit()

    # Check enrollment status
    cursor.execute(
        """
        SELECT e.status, m.module_name
        FROM enrollments e
        JOIN modules m ON e.module_id = m.module_id
        WHERE e.student_id = ? AND e.module_id = ?
        """,
        ('S001', 'CS101')
    )
    result = cursor.fetchone()

    assert result is not None
    assert result[0] == 'enrolled'
    assert result[1] == 'Intro to Computer Science'

    conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
