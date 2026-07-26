"""
End-to-End Test Suites for Complete User Journeys

Tests complete user journeys through the system:
- New student onboarding
- Instructor course management
- Student course completion
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

@pytest.mark.integration
@pytest.mark.slow
class TestStudentJourneys:
    """Test complete student journeys"""

    def test_new_student_onboarding_journey(self, temp_db):
        """
        Test new student journey:
        1. Create student record
        2. Register for courses
        3. Verify enrollment
        """

        # Step 1: Create student
        with transaction(db_path=temp_db) as conn:
            cursor = conn.execute("""
                INSERT INTO students (
                    student_id, first_name, last_name, email, status
                ) VALUES (?, ?, ?, ?, ?)
            """, ("STU1001", "Sarah", "Johnson", "sarah@uni.edu", "active"))
            student_pk = cursor.lastrowid

        # Step 2: Create courses
        courses = [
            ("CS101", "Intro to CS"),
            ("MATH101", "Algebra"),
            ("ENG101", "Composition")
        ]

        course_pks = []
        with transaction(db_path=temp_db) as conn:
            for code, name in courses:
                cursor = conn.execute("""
                    INSERT INTO courses (course_code, course_name, credits, status)
                    VALUES (?, ?, ?, ?)
                """, (code, name, 3, "active"))
                course_pks.append(cursor.lastrowid)

        # Step 3: Register for courses
        with transaction(db_path=temp_db) as conn:
            for course_pk in course_pks:
                conn.execute("""
                    INSERT INTO enrollments (
                        student_id, course_id, enrollment_date, status
                    ) VALUES (?, ?, ?, ?)
                """, (student_pk, course_pk, datetime.now().date().isoformat(), "enrolled"))

        # Verify journey
        with get_connection(db_path=temp_db) as conn:
            enrollment_count = conn.execute("""
                SELECT COUNT(*) FROM enrollments WHERE student_id = ?
            """, (student_pk,)).fetchone()[0]
            assert enrollment_count == 3

    def test_student_course_completion_journey(self, temp_db):
        """
        Test student completing a course:
        1. Enroll in course
        2. Submit assignments
        3. Receive grade
        """

        # Setup student and course
        with transaction(db_path=temp_db) as conn:
            cursor = conn.execute("""
                INSERT INTO students (student_id, first_name, last_name, status)
                VALUES (?, ?, ?, ?)
            """, ("STU1002", "Michael", "Chang", "active"))
            student_pk = cursor.lastrowid

            cursor = conn.execute("""
                INSERT INTO courses (course_code, course_name, credits, status)
                VALUES (?, ?, ?, ?)
            """, ("BIO101", "Biology", 4, "active"))
            course_pk = cursor.lastrowid

            # Enroll
            conn.execute("""
                INSERT INTO enrollments (
                    student_id, course_id, enrollment_date, status
                ) VALUES (?, ?, ?, ?)
            """, (student_pk, course_pk, datetime.now().date().isoformat(), "enrolled"))

        # Submit assignments
        with transaction(db_path=temp_db) as conn:
            for i in range(3):
                conn.execute("""
                    INSERT INTO grades (
                        student_id, course_id, assignment_name,
                        score, max_score, grade_date
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (student_pk, course_pk, f"Assignment {i+1}",
                      85 + i, 100, datetime.now().date().isoformat()))

        # Record final grade
        with transaction(db_path=temp_db) as conn:
            conn.execute("""
                UPDATE enrollments
                SET grade = 'A', status = 'completed'
                WHERE student_id = ? AND course_id = ?
            """, (student_pk, course_pk))

        # Verify completion — query enrollment and assignment count separately
        # to avoid GROUP BY ambiguity with fetchone()
        with get_connection(db_path=temp_db) as conn:
            conn.row_factory = sqlite3.Row
            enrollment = conn.execute("""
                SELECT grade, status FROM enrollments
                WHERE student_id = ? AND course_id = ?
            """, (student_pk, course_pk)).fetchone()

            assignment_count = conn.execute("""
                SELECT COUNT(*) as cnt FROM grades
                WHERE student_id = ? AND course_id = ?
            """, (student_pk, course_pk)).fetchone()['cnt']

            assert enrollment['grade'] == 'A'
            assert enrollment['status'] == 'completed'
            assert assignment_count == 3

@pytest.mark.integration
@pytest.mark.slow
class TestInstructorJourneys:
    """Test instructor workflows"""

    def test_instructor_course_management(self, temp_db):
        """
        Test instructor managing a course:
        1. Create course with students
        2. Record grades
        3. Finalize grades
        """

        # Create instructor and course
        with transaction(db_path=temp_db) as conn:
            cursor = conn.execute("""
                INSERT INTO courses (course_code, course_name, credits, status)
                VALUES (?, ?, ?, ?)
            """, ("CS201", "Data Structures", 4, "active"))
            course_pk = cursor.lastrowid

        # Enroll students
        student_pks = []
        with transaction(db_path=temp_db) as conn:
            for i in range(3):
                cursor = conn.execute("""
                    INSERT INTO students (
                        student_id, first_name, last_name, status
                    ) VALUES (?, ?, ?, ?)
                """, (f"STU20{i}", f"Student{i}", "Test", "active"))
                student_pk = cursor.lastrowid
                student_pks.append(student_pk)

                conn.execute("""
                    INSERT INTO enrollments (
                        student_id, course_id, enrollment_date, status
                    ) VALUES (?, ?, ?, ?)
                """, (student_pk, course_pk, datetime.now().date().isoformat(), "enrolled"))

        # Record grades for all students
        grades = ['A', 'B', 'A']
        with transaction(db_path=temp_db) as conn:
            for i, student_pk in enumerate(student_pks):
                conn.execute("""
                    INSERT INTO grades (
                        student_id, course_id, assignment_name,
                        score, max_score, grade_date
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (student_pk, course_pk, "Final Grade",
                      90 - i*5, 100, datetime.now().date().isoformat()))

                conn.execute("""
                    UPDATE enrollments
                    SET grade = ?, status = 'completed'
                    WHERE student_id = ? AND course_id = ?
                """, (grades[i], student_pk, course_pk))

        # Verify all grades submitted
        with get_connection(db_path=temp_db) as conn:
            completed_count = conn.execute("""
                SELECT COUNT(*) FROM enrollments
                WHERE course_id = ? AND status = 'completed'
            """, (course_pk,)).fetchone()[0]
            assert completed_count == 3

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
