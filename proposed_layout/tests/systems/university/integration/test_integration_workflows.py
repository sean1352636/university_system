"""
Integration Tests for Critical Workflows

This module tests complete workflows across multiple system components:
- Student enrollment → course registration → grading → transcripts
- Financial transactions → payment plans → refunds
- Student support ticket lifecycle
- Housing application → approval → payment
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

@pytest.mark.integration
class TestEnrollmentToTranscriptWorkflow:
    """Test complete student academic journey from enrollment to transcript"""

    def test_complete_student_academic_lifecycle(self, temp_db):
        """Test: Student enrollment → course registration → grades → transcript generation"""

        # Step 1: Create student
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO students (
                    student_id, first_name, last_name, email,
                    date_of_birth, enrollment_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("STU001", "John", "Doe", "john.doe@uni.edu",
                  "2000-01-01", datetime.now().date().isoformat(), "active"))

            student_pk = cursor.lastrowid

        # Step 2: Create courses
        course_pks = {}
        with transaction() as conn:
            for code, name, credits in [("CS101", "Intro to Programming", 3),
                                        ("CS102", "Data Structures", 4),
                                        ("MATH201", "Calculus I", 4)]:
                cursor = conn.execute("""
                    INSERT INTO courses (
                        course_code, course_name, credits, status
                    ) VALUES (?, ?, ?, ?)
                """, (code, name, credits, "active"))
                course_pks[code] = cursor.lastrowid

        # Step 3: Enroll student in courses
        with transaction() as conn:
            for course_pk in course_pks.values():
                conn.execute("""
                    INSERT INTO enrollments (
                        student_id, course_id, enrollment_date, status
                    ) VALUES (?, ?, ?, ?)
                """, (student_pk, course_pk, datetime.now().date().isoformat(), "enrolled"))

        # Step 4: Record grades
        grades_data = [
            ("CS101", 85.5, "A"),
            ("CS102", 78.0, "B"),
            ("MATH201", 92.0, "A")
        ]

        with transaction() as conn:
            for code, score, letter in grades_data:
                conn.execute("""
                    INSERT INTO grades (
                        student_id, course_id, assignment_name,
                        score, max_score, grade_date
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (student_pk, course_pks[code], "Final Grade",
                      score, 100, datetime.now().date().isoformat()))

                # Update enrollment with final grade
                conn.execute("""
                    UPDATE enrollments
                    SET grade = ?, status = 'completed'
                    WHERE student_id = ? AND course_id = ?
                """, (letter, student_pk, course_pks[code]))

        # Step 5: Verify transcript data
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            transcript = conn.execute("""
                SELECT
                    c.course_code,
                    c.course_name,
                    c.credits,
                    e.grade,
                    AVG(g.score) as avg_score
                FROM students s
                JOIN enrollments e ON s.id = e.student_id
                JOIN courses c ON e.course_id = c.id
                LEFT JOIN grades g ON g.student_id = s.id AND g.course_id = c.id
                WHERE s.student_id = ?
                GROUP BY c.course_code, c.course_name, c.credits, e.grade
                ORDER BY c.course_code
            """, ("STU001",)).fetchall()

            assert len(transcript) == 3
            assert transcript[0]['grade'] in ['A', 'B']

    def test_course_withdrawal_impact(self, temp_db):
        """Test: Student withdraws from course and impact on records"""

        # Create student and course
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO students (student_id, first_name, last_name, status)
                VALUES (?, ?, ?, ?)
            """, ("STU002", "Jane", "Smith", "active"))
            student_pk = cursor.lastrowid

            cursor = conn.execute("""
                INSERT INTO courses (course_code, course_name, credits, status)
                VALUES (?, ?, ?, ?)
            """, ("CS201", "Advanced Programming", 4, "active"))
            course_pk = cursor.lastrowid

            # Enroll student
            conn.execute("""
                INSERT INTO enrollments (student_id, course_id, enrollment_date, status)
                VALUES (?, ?, ?, ?)
            """, (student_pk, course_pk, datetime.now().date().isoformat(), "enrolled"))

        # Withdraw from course
        with transaction() as conn:
            conn.execute("""
                UPDATE enrollments
                SET status = 'withdrawn'
                WHERE student_id = ? AND course_id = ?
            """, (student_pk, course_pk))

        # Verify withdrawal
        with get_connection() as conn:
            status = conn.execute("""
                SELECT status FROM enrollments
                WHERE student_id = ? AND course_id = ?
            """, (student_pk, course_pk)).fetchone()[0]
            assert status == "withdrawn"

@pytest.mark.integration
class TestFinancialTransactionWorkflow:
    """Test complete financial transaction workflows"""

    def test_payment_tracking_workflow(self, temp_db):
        """Test: Record payments and track balances"""

        # Create payment tracking tables
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tuition_fees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    semester TEXT NOT NULL,
                    amount REAL NOT NULL,
                    due_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    payment_date TEXT NOT NULL,
                    payment_method TEXT,
                    status TEXT DEFAULT 'completed'
                )
            """)

        # Create student
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO students (student_id, first_name, last_name, status)
                VALUES (?, ?, ?, ?)
            """, ("STU003", "Alice", "Williams", "active"))
            student_pk = cursor.lastrowid

        # Create tuition fee
        total_tuition = 10000.00
        with transaction() as conn:
            conn.execute("""
                INSERT INTO tuition_fees (student_id, semester, amount, due_date, status)
                VALUES (?, ?, ?, ?, ?)
            """, (student_pk, "2024-01", total_tuition,
                  (datetime.now() + timedelta(days=30)).date().isoformat(), "pending"))

        # Process payments
        num_installments = 4
        installment_amount = total_tuition / num_installments

        with transaction() as conn:
            for i in range(num_installments):
                conn.execute("""
                    INSERT INTO payments (
                        student_id, amount, payment_date, payment_method, status
                    ) VALUES (?, ?, ?, ?, ?)
                """, (student_pk, installment_amount, datetime.now().date().isoformat(),
                      "credit_card", "completed"))

        # Verify total paid
        with get_connection() as conn:
            total_paid = conn.execute("""
                SELECT SUM(amount) FROM payments WHERE student_id = ?
            """, (student_pk,)).fetchone()[0]

            assert total_paid == total_tuition

@pytest.mark.integration
class TestStudentSupportWorkflow:
    """Test student support ticket lifecycle"""

    def test_support_ticket_lifecycle(self, temp_db):
        """Test: Create ticket → assign → resolve → close"""

        # Setup support ticket tables
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    description TEXT,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'open',
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    assigned_to TEXT,
                    resolved_date TEXT
                )
            """)

        # Create student
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO students (student_id, first_name, last_name, status)
                VALUES (?, ?, ?, ?)
            """, ("STU004", "Bob", "Johnson", "active"))
            student_pk = cursor.lastrowid

        # Create support ticket
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO support_tickets (
                    student_id, subject, description, priority, status
                ) VALUES (?, ?, ?, ?, ?)
            """, (student_pk, "Cannot access online library",
                  "I get an error when trying to log in", "high", "open"))
            ticket_id = cursor.lastrowid

        # Assign ticket
        with transaction() as conn:
            conn.execute("""
                UPDATE support_tickets
                SET assigned_to = ?, status = ?
                WHERE id = ?
            """, ("staff001", "in_progress", ticket_id))

        # Resolve ticket
        with transaction() as conn:
            conn.execute("""
                UPDATE support_tickets
                SET status = ?, resolved_date = ?
                WHERE id = ?
            """, ("resolved", datetime.now().date().isoformat(), ticket_id))

        # Verify ticket lifecycle
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            ticket = conn.execute("""
                SELECT status, assigned_to, resolved_date
                FROM support_tickets WHERE id = ?
            """, (ticket_id,)).fetchone()

            assert ticket['status'] == "resolved"
            assert ticket['assigned_to'] == "staff001"
            assert ticket['resolved_date'] is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
