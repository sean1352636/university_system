"""
Test suite for student CRUD operations
"""
import unittest
import sys
import os
import random
import sqlite3
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from university_system.infrastructure.database.db import get_db_connection


class TestStudentCRUD(unittest.TestCase):
    """Test cases for student Create, Read, Update, Delete operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.conn = get_db_connection()
        if not self.conn:
            self.skipTest("Database connection not available")
        self.test_student_id = None

    def tearDown(self):
        """Clean up test data"""
        if self.test_student_id and self.conn:
            try:
                cursor = self.conn.cursor()
                cursor.execute('DELETE FROM students WHERE student_id = ?', (self.test_student_id,))
                self.conn.commit()
            except:
                pass
        if self.conn:
            self.conn.close()

    def test_create_student(self):
        """Test creating a new student record"""
        cursor = self.conn.cursor()

        # Generate test data
        self.test_student_id = f"TEST{random.randint(100000, 999999)}"
        test_email = f"test{self.test_student_id}@tees.ac.uk"
        course = random.choice(['CS', 'DS'])

        # Insert student
        cursor.execute('''
            INSERT INTO students (student_id, email_address, title, first_name,
                                middle_name, last_name, gender, dob, age, course,
                                registration_datetime, status, enrollment_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self.test_student_id, test_email, 'Mr', 'Test', 'Middle', 'Student',
              'male', '2000-01-01', 24, course, datetime.now().isoformat(),
              'Active', datetime.now().isoformat()))

        self.conn.commit()

        # Verify insertion
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (self.test_student_id,))
        result = cursor.fetchone()

        self.assertIsNotNone(result, "Student should be created in database")
        self.assertEqual(result[0], self.test_student_id, "Student ID should match")

    def test_read_student(self):
        """Test reading student records"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM students LIMIT 1')
        result = cursor.fetchone()

        if result:
            self.assertIsNotNone(result[0], "Student ID should not be None")
            self.assertIsNotNone(result[1], "Email should not be None")
        else:
            self.skipTest("No students in database to test read operation")

    def test_update_student(self):
        """Test updating student information"""
        # First create a test student
        self.test_create_student()

        cursor = self.conn.cursor()
        new_first_name = "UpdatedTest"

        # Update student
        cursor.execute('''
            UPDATE students SET first_name = ? WHERE student_id = ?
        ''', (new_first_name, self.test_student_id))

        self.conn.commit()

        # Verify update
        cursor.execute('SELECT first_name FROM students WHERE student_id = ?',
                      (self.test_student_id,))
        result = cursor.fetchone()

        self.assertEqual(result[0], new_first_name, "First name should be updated")

    def test_delete_student(self):
        """Test deleting a student record"""
        # First create a test student
        self.test_create_student()

        cursor = self.conn.cursor()

        # Delete student
        cursor.execute('DELETE FROM students WHERE student_id = ?',
                      (self.test_student_id,))
        self.conn.commit()

        # Verify deletion
        cursor.execute('SELECT * FROM students WHERE student_id = ?',
                      (self.test_student_id,))
        result = cursor.fetchone()

        self.assertIsNone(result, "Student should be deleted from database")
        self.test_student_id = None  # Mark as cleaned up

    def test_student_course_assignment(self):
        """Test that student course is correctly assigned to CS or DS"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT course FROM students LIMIT 10')
        results = cursor.fetchall()

        for result in results:
            course = result[0]
            if course:  # Some records might not have course set
                self.assertIn(course, ['CS', 'DS', 'Computer Science', 'Data Science'],
                            f"Course should be CS, DS, Computer Science, or Data Science, got: {course}")

    def test_student_email_format(self):
        """Test that student emails follow the correct format"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT email_address, student_id FROM students LIMIT 5')
        results = cursor.fetchall()

        valid_domains = ['.ac.uk', '.edu', '.com', '.org']
        for result in results:
            email = result[0]
            if email:
                self.assertIn('@', email, "Email should contain @ symbol")
                self.assertTrue(any(email.endswith(domain) for domain in valid_domains),
                              f"Email should end with one of {valid_domains}")

    def test_student_age_calculation(self):
        """Test that student age is reasonable"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT age, dob FROM students WHERE age IS NOT NULL LIMIT 5')
        results = cursor.fetchall()

        for result in results:
            age = result[0]
            if age:
                self.assertGreater(age, 0, "Age should be positive")
                self.assertLess(age, 100, "Age should be less than 100")

    def test_count_students_by_course(self):
        """Test counting students by course"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT course, COUNT(*) FROM students GROUP BY course')
        results = cursor.fetchall()

        total = sum(row[1] for row in results)
        self.assertGreater(total, 0, "Should have at least one student")


class TestStudentValidation(unittest.TestCase):
    """Test validation rules for student data"""

    def setUp(self):
        """Set up test fixtures"""
        self.conn = get_db_connection()
        if not self.conn:
            self.skipTest("Database connection not available")

    def tearDown(self):
        """Clean up"""
        if self.conn:
            self.conn.close()

    def test_duplicate_student_id(self):
        """Test that duplicate student IDs are prevented"""
        cursor = self.conn.cursor()

        # Get an existing student ID
        cursor.execute('SELECT student_id FROM students LIMIT 1')
        result = cursor.fetchone()

        if not result:
            self.skipTest("No students in database to test duplicate prevention")

        existing_id = result[0]

        # Try to insert duplicate
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute('''
                INSERT INTO students (student_id, email_address, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (existing_id, 'duplicate@test.com', 'Dup', 'Test'))
            self.conn.commit()


if __name__ == '__main__':
    unittest.main()
