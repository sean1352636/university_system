"""
Test suite for grade tracking formatters module
Tests all formatting utilities for grade tracking
"""

import pytest
from university_system.modules.domain.academics.gui.grade_tracking.utils.formatters import (
    format_percentage,
    format_gpa,
    format_letter_grade
)


class TestFormatPercentage:
    """Test cases for format_percentage function"""

    def test_format_percentage_valid_int(self):
        """Test formatting valid integer percentage"""
        assert format_percentage(85) == "85.00%"

    def test_format_percentage_valid_float(self):
        """Test formatting valid float percentage"""
        assert format_percentage(85.5) == "85.50%"

    def test_format_percentage_custom_decimals(self):
        """Test formatting with custom decimal places"""
        assert format_percentage(85.12345, decimals=3) == "85.123%"

    def test_format_percentage_zero_decimals(self):
        """Test formatting with zero decimal places"""
        assert format_percentage(85.6, decimals=0) == "86%"

    def test_format_percentage_zero_value(self):
        """Test formatting zero percentage"""
        assert format_percentage(0) == "0.00%"

    def test_format_percentage_hundred(self):
        """Test formatting 100 percentage"""
        assert format_percentage(100) == "100.00%"

    def test_format_percentage_invalid_string(self):
        """Test formatting invalid string value"""
        assert format_percentage("invalid") == "N/A"

    def test_format_percentage_none(self):
        """Test formatting None value"""
        assert format_percentage(None) == "N/A"

    def test_format_percentage_empty_string(self):
        """Test formatting empty string"""
        assert format_percentage("") == "N/A"


class TestFormatGPA:
    """Test cases for format_gpa function"""

    def test_format_gpa_valid_int(self):
        """Test formatting valid integer GPA"""
        assert format_gpa(3) == "3.00"

    def test_format_gpa_valid_float(self):
        """Test formatting valid float GPA"""
        assert format_gpa(3.75) == "3.75"

    def test_format_gpa_custom_decimals(self):
        """Test formatting with custom decimal places"""
        assert format_gpa(3.12345, decimals=3) == "3.123"

    def test_format_gpa_zero_decimals(self):
        """Test formatting with zero decimal places"""
        assert format_gpa(3.6, decimals=0) == "4"

    def test_format_gpa_zero_value(self):
        """Test formatting zero GPA"""
        assert format_gpa(0) == "0.00"

    def test_format_gpa_max_value(self):
        """Test formatting maximum GPA (4.0)"""
        assert format_gpa(4.0) == "4.00"

    def test_format_gpa_invalid_string(self):
        """Test formatting invalid string value"""
        assert format_gpa("invalid") == "N/A"

    def test_format_gpa_none(self):
        """Test formatting None value"""
        assert format_gpa(None) == "N/A"

    def test_format_gpa_empty_string(self):
        """Test formatting empty string"""
        assert format_gpa("") == "N/A"


class TestFormatLetterGrade:
    """Test cases for format_letter_grade function"""

    def test_format_letter_grade_a_plus(self):
        """Test formatting A+ grade (90-100)"""
        assert format_letter_grade(95) == "A+"
        assert format_letter_grade(90) == "A+"
        assert format_letter_grade(100) == "A+"

    def test_format_letter_grade_a(self):
        """Test formatting A grade (85-89)"""
        assert format_letter_grade(87) == "A"
        assert format_letter_grade(85) == "A"
        assert format_letter_grade(89.99) == "A"

    def test_format_letter_grade_a_minus(self):
        """Test formatting A- grade (80-84)"""
        assert format_letter_grade(82) == "A-"
        assert format_letter_grade(80) == "A-"
        assert format_letter_grade(84.99) == "A-"

    def test_format_letter_grade_b_plus(self):
        """Test formatting B+ grade (77-79)"""
        assert format_letter_grade(78) == "B+"
        assert format_letter_grade(77) == "B+"
        assert format_letter_grade(79.99) == "B+"

    def test_format_letter_grade_b(self):
        """Test formatting B grade (73-76)"""
        assert format_letter_grade(75) == "B"
        assert format_letter_grade(73) == "B"
        assert format_letter_grade(76.99) == "B"

    def test_format_letter_grade_b_minus(self):
        """Test formatting B- grade (70-72)"""
        assert format_letter_grade(71) == "B-"
        assert format_letter_grade(70) == "B-"
        assert format_letter_grade(72.99) == "B-"

    def test_format_letter_grade_c_plus(self):
        """Test formatting C+ grade (67-69)"""
        assert format_letter_grade(68) == "C+"
        assert format_letter_grade(67) == "C+"
        assert format_letter_grade(69.99) == "C+"

    def test_format_letter_grade_c(self):
        """Test formatting C grade (63-66)"""
        assert format_letter_grade(65) == "C"
        assert format_letter_grade(63) == "C"
        assert format_letter_grade(66.99) == "C"

    def test_format_letter_grade_c_minus(self):
        """Test formatting C- grade (60-62)"""
        assert format_letter_grade(61) == "C-"
        assert format_letter_grade(60) == "C-"
        assert format_letter_grade(62.99) == "C-"

    def test_format_letter_grade_d_plus(self):
        """Test formatting D+ grade (57-59)"""
        assert format_letter_grade(58) == "D+"
        assert format_letter_grade(57) == "D+"
        assert format_letter_grade(59.99) == "D+"

    def test_format_letter_grade_d(self):
        """Test formatting D grade (53-56)"""
        assert format_letter_grade(55) == "D"
        assert format_letter_grade(53) == "D"
        assert format_letter_grade(56.99) == "D"

    def test_format_letter_grade_d_minus(self):
        """Test formatting D- grade (50-52)"""
        assert format_letter_grade(51) == "D-"
        assert format_letter_grade(50) == "D-"
        assert format_letter_grade(52.99) == "D-"

    def test_format_letter_grade_f(self):
        """Test formatting F grade (below 50)"""
        assert format_letter_grade(49) == "F"
        assert format_letter_grade(0) == "F"
        assert format_letter_grade(25) == "F"

    def test_format_letter_grade_invalid_string(self):
        """Test formatting invalid string value"""
        assert format_letter_grade("invalid") == "N/A"

    def test_format_letter_grade_none(self):
        """Test formatting None value"""
        assert format_letter_grade(None) == "N/A"

    def test_format_letter_grade_empty_string(self):
        """Test formatting empty string"""
        assert format_letter_grade("") == "N/A"

    def test_format_letter_grade_boundary_values(self):
        """Test formatting at exact boundary values"""
        assert format_letter_grade(90.0) == "A+"
        assert format_letter_grade(89.99) == "A"
        assert format_letter_grade(85.0) == "A"
        assert format_letter_grade(84.99) == "A-"
        assert format_letter_grade(50.0) == "D-"
        assert format_letter_grade(49.99) == "F"
