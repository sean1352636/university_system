"""
Test suite for module enrollment functionality
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from university_system.infrastructure.database.db import get_db_connection


class TestModuleEnrollment(unittest.TestCase):
    """Test cases for student module enrollment"""

    def setUp(self):
        """Set up test fixtures"""
        self.conn = get_db_connection()
        if not self.conn:
            self.skipTest("Database connection not available")

    def tearDown(self):
        """Clean up"""
        if self.conn:
            self.conn.close()

    def test_student_modules_table_exists(self):
        """Test that student_modules table exists"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='student_modules'
        ''')
        result = cursor.fetchone()

        self.assertIsNotNone(result, "student_modules table should exist")

    def test_query_student_modules(self):
        """Test querying student module enrollments"""
        cursor = self.conn.cursor()

        # Get a student ID
        cursor.execute("SELECT student_id FROM students LIMIT 1")
        student = cursor.fetchone()

        if not student:
            self.skipTest("No students available for testing")

        student_id = student[0]

        # Query their modules
        cursor.execute('''
            SELECT module_code FROM student_modules
            WHERE student_id = ?
        ''', (student_id,))
        modules = cursor.fetchall()

        self.assertIsInstance(modules, list,
                            "Should return list of enrolled modules")

    def test_module_enrollment_count(self):
        """Test that students have appropriate number of modules"""
        cursor = self.conn.cursor()

        # Get students with their module count
        cursor.execute('''
            SELECT s.student_id, COUNT(sm.module_code) as module_count
            FROM students s
            LEFT JOIN student_modules sm ON s.student_id = sm.student_id
            GROUP BY s.student_id
            LIMIT 10
        ''')
        results = cursor.fetchall()

        for result in results:
            module_count = result[1]
            # Students typically have 3-6 modules
            if module_count > 0:
                self.assertLessEqual(module_count, 10,
                                   "Student should not have more than 10 modules")


if __name__ == '__main__':
    unittest.main()
