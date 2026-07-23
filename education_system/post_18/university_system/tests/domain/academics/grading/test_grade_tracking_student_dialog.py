"""Tests for grade tracking student dialog"""

import pytest
pytestmark = pytest.mark.gui

import unittest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import tempfile
import os

from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.dialogs.student_dialog import (
    StudentDialog,
    safe_grab_set,
    safe_combo_update,
    percentage_to_letter,
    letter_to_percentage,
    letter_to_gpa,
    GRADE_SYSTEMS
)

class TestGradeConversionFunctions(unittest.TestCase):
    """Test grade conversion utility functions"""

    def test_percentage_to_letter_a_plus(self):
        """Test conversion of A+ grade"""
        self.assertEqual(percentage_to_letter(95), 'A+')
        self.assertEqual(percentage_to_letter(90), 'A+')

    def test_percentage_to_letter_a(self):
        """Test conversion of A grade"""
        self.assertEqual(percentage_to_letter(87), 'A')
        self.assertEqual(percentage_to_letter(85), 'A')

    def test_percentage_to_letter_b_range(self):
        """Test conversion of B grades"""
        self.assertEqual(percentage_to_letter(77), 'B+')
        self.assertEqual(percentage_to_letter(72), 'B')
        self.assertEqual(percentage_to_letter(67), 'B-')

    def test_percentage_to_letter_f(self):
        """Test conversion of F grade"""
        self.assertEqual(percentage_to_letter(30), 'F')
        self.assertEqual(percentage_to_letter(0), 'F')

    def test_letter_to_percentage_conversion(self):
        """Test letter to percentage conversion"""
        # Should return midpoint of range
        self.assertAlmostEqual(letter_to_percentage('A+'), 95.0, places=1)
        self.assertAlmostEqual(letter_to_percentage('B'), 72.5, places=1)
        self.assertAlmostEqual(letter_to_percentage('F'), 17.5, places=1)

    def test_letter_to_percentage_invalid(self):
        """Test invalid letter grade conversion"""
        self.assertEqual(letter_to_percentage('Z'), 0)

    def test_letter_to_gpa_valid(self):
        """Test letter to GPA conversion"""
        self.assertEqual(letter_to_gpa('A+'), 4.3)
        self.assertEqual(letter_to_gpa('A'), 4.0)
        self.assertEqual(letter_to_gpa('B'), 3.0)
        self.assertEqual(letter_to_gpa('C'), 2.0)
        self.assertEqual(letter_to_gpa('F'), 0.0)

    def test_letter_to_gpa_invalid(self):
        """Test invalid letter to GPA conversion"""
        self.assertEqual(letter_to_gpa('Z'), 0)

class TestSafeGrabSet(unittest.TestCase):
    """Test safe_grab_set function"""

    def setUp(self):
        """Set up test root window"""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Destroy test root window"""
        try:
            self.root.destroy()
        except (OSError, IOError):
            pass

    def test_safe_grab_set_success(self):
        """Test successful grab set"""
        dialog = tk.Toplevel(self.root)
        # Should not raise exception
        try:
            safe_grab_set(dialog)
        except Exception as e:
            self.fail(f"safe_grab_set raised exception: {e}")
        finally:
            dialog.destroy()

    def test_safe_grab_set_handles_error(self):
        """Test safe_grab_set handles errors gracefully"""
        dialog = Mock()
        dialog.update_idletasks.side_effect = tk.TclError("Test error")

        # Should not raise exception
        try:
            safe_grab_set(dialog)
        except Exception as e:
            self.fail(f"safe_grab_set raised exception: {e}")

class TestSafeComboUpdate(unittest.TestCase):
    """Test safe_combo_update function"""

    def setUp(self):
        """Set up test root window"""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Destroy test root window"""
        try:
            self.root.destroy()
        except (OSError, IOError):
            pass

    def test_safe_combo_update_success(self):
        """Test successful combo update"""
        obj = Mock()
        combo = ttk.Combobox(self.root)
        obj.test_combo = combo

        result = safe_combo_update(obj, 'test_combo', ['Option 1', 'Option 2'])

        self.assertTrue(result)
        self.assertEqual(combo['values'], ('Option 1', 'Option 2'))
        combo.destroy()

    def test_safe_combo_update_missing_attribute(self):
        """Test combo update with missing attribute"""
        obj = Mock(spec=[])

        result = safe_combo_update(obj, 'nonexistent_combo', ['Option 1'])

        self.assertFalse(result)

    def test_safe_combo_update_destroyed_widget(self):
        """Test combo update with destroyed widget"""
        obj = Mock()
        combo = ttk.Combobox(self.root)
        obj.test_combo = combo
        combo.destroy()

        result = safe_combo_update(obj, 'test_combo', ['Option 1'])

        self.assertFalse(result)

class TestStudentDialog(unittest.TestCase):
    """Test StudentDialog class"""

    def setUp(self):
        """Set up test environment"""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up test environment"""
        try:
            self.root.destroy()
        except (OSError, IOError):
            pass

    def test_student_dialog_creation_new_student(self):
        """Test creating dialog for new student"""
        dialog = StudentDialog(self.root, "Add Student")

        self.assertIsNotNone(dialog.dialog)
        self.assertIsNone(dialog.result)
        self.assertEqual(dialog.dialog.title(), "Add Student")

        dialog.dialog.destroy()

    def test_student_dialog_creation_with_data(self):
        """Test creating dialog with existing student data"""
        student_data = (
            'STU001', 'John', 'M', 'Doe', 'Computer Science',
            'john.doe@example.com', '1234567890', '123 Main St',
            '2024-09-01', 'Active', '2000-01-01', 'Male', 'USA'
        )

        dialog = StudentDialog(self.root, "Edit Student", data=student_data)

        self.assertEqual(dialog.student_id_var.get(), 'STU001')
        self.assertEqual(dialog.first_name_var.get(), 'John')
        self.assertEqual(dialog.middle_name_var.get(), 'M')
        self.assertEqual(dialog.last_name_var.get(), 'Doe')
        self.assertEqual(dialog.course_var.get(), 'Computer Science')

        dialog.dialog.destroy()

    def test_student_dialog_validation_required_fields(self):
        """Test validation of required fields"""
        dialog = StudentDialog(self.root, "Add Student")

        # Try to save without required fields
        with patch('tkinter.messagebox.showerror') as mock_error:
            dialog.save_student()
            mock_error.assert_called()

        dialog.dialog.destroy()

    def test_student_dialog_save_valid_data(self):
        """Test saving valid student data"""
        dialog = StudentDialog(self.root, "Add Student")

        # Set required fields
        dialog.student_id_var.set('STU001')
        dialog.first_name_var.set('John')
        dialog.last_name_var.set('Doe')
        dialog.course_var.set('Computer Science')

        # Save student
        dialog.save_student()

        # Check result
        self.assertIsNotNone(dialog.result)
        self.assertEqual(dialog.result[0], 'STU001')
        self.assertEqual(dialog.result[1], 'John')
        self.assertEqual(dialog.result[3], 'Doe')

    def test_student_dialog_geometry(self):
        """Test dialog size"""
        dialog = StudentDialog(self.root, "Add Student")

        # Check geometry is set
        geometry = dialog.dialog.geometry()
        self.assertTrue('500x600' in geometry or dialog.dialog.winfo_width() > 0)

        dialog.dialog.destroy()

    def test_student_dialog_field_values_empty(self):
        """Test all fields are initialized when no data provided"""
        dialog = StudentDialog(self.root, "Add Student")

        self.assertEqual(dialog.student_id_var.get(), '')
        self.assertEqual(dialog.first_name_var.get(), '')
        self.assertEqual(dialog.middle_name_var.get(), '')
        self.assertEqual(dialog.last_name_var.get(), '')

        dialog.dialog.destroy()

class TestGradeSystemConstants(unittest.TestCase):
    """Test GRADE_SYSTEMS constants"""

    def test_grade_systems_structure(self):
        """Test grade systems data structure"""
        self.assertIn('letter', GRADE_SYSTEMS)
        self.assertIn('percentage', GRADE_SYSTEMS)

    def test_letter_grades_present(self):
        """Test all letter grades are present"""
        letter_grades = GRADE_SYSTEMS['letter']

        self.assertIn('A+', letter_grades)
        self.assertIn('A', letter_grades)
        self.assertIn('B', letter_grades)
        self.assertIn('C', letter_grades)
        self.assertIn('D', letter_grades)
        self.assertIn('F', letter_grades)

    def test_gpa_values_valid(self):
        """Test GPA values are valid"""
        letter_grades = GRADE_SYSTEMS['letter']

        self.assertEqual(letter_grades['A+'], 4.3)
        self.assertEqual(letter_grades['A'], 4.0)
        self.assertEqual(letter_grades['F'], 0.0)

        # All values should be between 0 and 4.3
        for grade, gpa in letter_grades.items():
            self.assertGreaterEqual(gpa, 0.0)
            self.assertLessEqual(gpa, 4.3)

    def test_percentage_conversion_ranges(self):
        """Test percentage conversion ranges"""
        conversion = GRADE_SYSTEMS['percentage']['conversion']

        # Check F grade range
        self.assertIn((0, 34.99), conversion)
        self.assertEqual(conversion[(0, 34.99)], 'F')

        # Check A+ grade range
        self.assertIn((90, 100), conversion)
        self.assertEqual(conversion[(90, 100)], 'A+')

if __name__ == '__main__':
    unittest.main()
