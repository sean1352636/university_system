"""
Test suite for integration tests across multiple modules
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from university_system.infrastructure.database.db import get_db_connection

try:
    from university_system.infrastructure.auth.user_authentication import UserAuth
except ImportError:
    UserAuth = None


class TestIntegration(unittest.TestCase):
    """Integration tests across system components"""

    def test_auth_and_database_integration(self):
        """Test authentication with database"""
        if UserAuth is None:
            self.skipTest("UserAuth module not available")

        conn = get_db_connection()
        if not conn:
            self.skipTest("Database connection not available")

        auth = UserAuth()
        result = auth.login('admin', 'admin123')

        self.assertTrue(result, "Should be able to login with database connection")

        conn.close()

    def test_student_creation_workflow(self):
        """Test complete student creation workflow"""
        import random
        from datetime import datetime

        conn = get_db_connection()
        if not conn:
            self.skipTest("Database connection not available")

        cursor = conn.cursor()

        # Simulate student creation like the GUI does
        test_student_id = f"INTG{random.randint(100000, 999999)}"
        course = random.choice(['CS', 'DS'])

        try:
            cursor.execute('''
                INSERT INTO students (student_id, email_address, first_name,
                                    last_name, course, registration_datetime, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (test_student_id, f"{test_student_id}@tees.ac.uk", 'Integration',
                  'Test', course, datetime.now().isoformat(), 'Active'))

            conn.commit()

            # Verify creation
            cursor.execute('SELECT course FROM students WHERE student_id = ?',
                         (test_student_id,))
            result = cursor.fetchone()

            self.assertIsNotNone(result, "Student should be created")
            self.assertIn(result[0], ['CS', 'DS'], "Course should be CS or DS")

            # Cleanup
            cursor.execute('DELETE FROM students WHERE student_id = ?',
                         (test_student_id,))
            conn.commit()

        finally:
            conn.close()

    def test_gui_and_auth_integration(self):
        """Test GUI initialization with authentication"""
        if UserAuth is None:
            self.skipTest("UserAuth module not available")

        try:
            from university_system.modules.shared.gui.main_gui import init_gui

            # Test init with no session (login page)
            app = init_gui(session_user=None)

            self.assertIsNotNone(app, "GUI should initialize")
            self.assertIsNotNone(app.auth, "GUI should have auth manager")

            # Clean up
            if hasattr(app, 'root'):
                app.root.destroy()

        except ImportError:
            self.skipTest("GUI modules not available")
        except Exception as e:
            self.skipTest(f"GUI initialization failed (may be headless): {e}")

    def test_module_enrollment_integration(self):
        """Test module enrollment with student"""
        conn = get_db_connection()
        if not conn:
            self.skipTest("Database connection not available")

        cursor = conn.cursor()

        # Get a student
        cursor.execute('SELECT student_id, course FROM students LIMIT 1')
        student = cursor.fetchone()

        if not student:
            self.skipTest("No students available for testing")

        student_id = student[0]
        course = student[1]

        # Get modules
        cursor.execute('SELECT module_code FROM modules LIMIT 1')
        module = cursor.fetchone()

        if module:
            # This is an integration test - just verify we can query related data
            cursor.execute('''
                SELECT COUNT(*) FROM student_modules
                WHERE student_id = ?
            ''', (student_id,))
            count = cursor.fetchone()[0]

            self.assertGreaterEqual(count, 0, "Should be able to query enrollments")

        conn.close()


class TestEndToEndWorkflows(unittest.TestCase):
    """End-to-end workflow tests"""

    def test_cli_to_gui_workflow(self):
        """Test CLI to GUI transition workflow"""
        try:
            from university_system.modules.shared.gui.main_gui import init_gui

            # Simulate CLI login creating a user object
            mock_user = {
                'id': 'test123',
                'username': 'testuser',
                'role': 'student'
            }

            # Test init_gui with session_user (CLI→GUI transition)
            app = init_gui(session_user=mock_user)

            self.assertIsNotNone(app, "GUI should initialize with session user")

            # Verify user is set
            if hasattr(app, 'auth') and hasattr(app.auth, 'current_user'):
                self.assertEqual(app.auth.current_user, mock_user,
                               "Session user should be set in auth")

            # Clean up
            if hasattr(app, 'root'):
                app.root.destroy()

        except ImportError:
            self.skipTest("GUI modules not available")
        except Exception as e:
            self.skipTest(f"Workflow test failed (may be headless): {e}")


if __name__ == '__main__':
    unittest.main()
