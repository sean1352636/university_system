"""
Test suite for grade tracking validators module
Tests all validation utilities for grade tracking
"""

import pytest
from education_system.university_system.modules.domain.academics.gui.grade_tracking.utils.validators import (
    validate_grade,
    validate_gpa,
    validate_percentage
)


class TestValidateGrade:
    """Test cases for validate_grade function"""

    def test_validate_grade_valid_int(self):
        """Test validating valid integer grade"""
        assert validate_grade(85) is True
        assert validate_grade(0) is True
        assert validate_grade(100) is True

    def test_validate_grade_valid_float(self):
        """Test validating valid float grade"""
        assert validate_grade(85.5) is True
        assert validate_grade(0.0) is True
        assert validate_grade(100.0) is True

    def test_validate_grade_valid_string_number(self):
        """Test validating valid string representation of number"""
        assert validate_grade("85") is True
        assert validate_grade("85.5") is True
        assert validate_grade("0") is True
        assert validate_grade("100") is True

    def test_validate_grade_boundary_values(self):
        """Test validating boundary values"""
        assert validate_grade(0) is True
        assert validate_grade(100) is True
        assert validate_grade(0.0) is True
        assert validate_grade(100.0) is True

    def test_validate_grade_out_of_range_negative(self):
        """Test validating negative grade"""
        assert validate_grade(-1) is False
        assert validate_grade(-10) is False
        assert validate_grade(-0.1) is False

    def test_validate_grade_out_of_range_too_high(self):
        """Test validating grade above max"""
        assert validate_grade(101) is False
        assert validate_grade(100.1) is False
        assert validate_grade(150) is False

    def test_validate_grade_invalid_string(self):
        """Test validating invalid string"""
        assert validate_grade("invalid") is False
        assert validate_grade("abc") is False
        assert validate_grade("") is False

    def test_validate_grade_none(self):
        """Test validating None value"""
        assert validate_grade(None) is False

    def test_validate_grade_custom_max(self):
        """Test validating with custom max grade"""
        assert validate_grade(50, max_grade=50) is True
        assert validate_grade(51, max_grade=50) is False
        assert validate_grade(25, max_grade=50) is True

    def test_validate_grade_decimal_values(self):
        """Test validating decimal values"""
        assert validate_grade(85.75) is True
        assert validate_grade(99.99) is True
        assert validate_grade(0.01) is True


class TestValidateGPA:
    """Test cases for validate_gpa function"""

    def test_validate_gpa_valid_int(self):
        """Test validating valid integer GPA"""
        assert validate_gpa(3) is True
        assert validate_gpa(0) is True
        assert validate_gpa(4) is True

    def test_validate_gpa_valid_float(self):
        """Test validating valid float GPA"""
        assert validate_gpa(3.5) is True
        assert validate_gpa(0.0) is True
        assert validate_gpa(4.0) is True

    def test_validate_gpa_valid_string_number(self):
        """Test validating valid string representation of GPA"""
        assert validate_gpa("3.5") is True
        assert validate_gpa("0") is True
        assert validate_gpa("4.0") is True

    def test_validate_gpa_boundary_values(self):
        """Test validating boundary values"""
        assert validate_gpa(0.0) is True
        assert validate_gpa(4.0) is True

    def test_validate_gpa_out_of_range_negative(self):
        """Test validating negative GPA"""
        assert validate_gpa(-1) is False
        assert validate_gpa(-0.1) is False

    def test_validate_gpa_out_of_range_too_high(self):
        """Test validating GPA above 4.0"""
        assert validate_gpa(4.1) is False
        assert validate_gpa(5.0) is False

    def test_validate_gpa_invalid_string(self):
        """Test validating invalid string"""
        assert validate_gpa("invalid") is False
        assert validate_gpa("abc") is False
        assert validate_gpa("") is False

    def test_validate_gpa_none(self):
        """Test validating None value"""
        assert validate_gpa(None) is False

    def test_validate_gpa_custom_max(self):
        """Test validating with custom max GPA"""
        assert validate_gpa(5.0, max_gpa=5.0) is True
        assert validate_gpa(5.1, max_gpa=5.0) is False
        assert validate_gpa(3.5, max_gpa=5.0) is True

    def test_validate_gpa_decimal_values(self):
        """Test validating decimal GPA values"""
        assert validate_gpa(3.75) is True
        assert validate_gpa(3.99) is True
        assert validate_gpa(0.01) is True


class TestValidatePercentage:
    """Test cases for validate_percentage function"""

    def test_validate_percentage_valid_int(self):
        """Test validating valid integer percentage"""
        assert validate_percentage(85) is True
        assert validate_percentage(0) is True
        assert validate_percentage(100) is True

    def test_validate_percentage_valid_float(self):
        """Test validating valid float percentage"""
        assert validate_percentage(85.5) is True
        assert validate_percentage(0.0) is True
        assert validate_percentage(100.0) is True

    def test_validate_percentage_valid_string_number(self):
        """Test validating valid string representation of percentage"""
        assert validate_percentage("85") is True
        assert validate_percentage("85.5") is True
        assert validate_percentage("0") is True
        assert validate_percentage("100") is True

    def test_validate_percentage_boundary_values(self):
        """Test validating boundary values"""
        assert validate_percentage(0) is True
        assert validate_percentage(100) is True
        assert validate_percentage(0.0) is True
        assert validate_percentage(100.0) is True

    def test_validate_percentage_out_of_range_negative(self):
        """Test validating negative percentage"""
        assert validate_percentage(-1) is False
        assert validate_percentage(-10) is False
        assert validate_percentage(-0.1) is False

    def test_validate_percentage_out_of_range_too_high(self):
        """Test validating percentage above 100"""
        assert validate_percentage(101) is False
        assert validate_percentage(100.1) is False
        assert validate_percentage(150) is False

    def test_validate_percentage_invalid_string(self):
        """Test validating invalid string"""
        assert validate_percentage("invalid") is False
        assert validate_percentage("abc") is False
        assert validate_percentage("") is False

    def test_validate_percentage_none(self):
        """Test validating None value"""
        assert validate_percentage(None) is False

    def test_validate_percentage_decimal_values(self):
        """Test validating decimal percentage values"""
        assert validate_percentage(85.75) is True
        assert validate_percentage(99.99) is True
        assert validate_percentage(0.01) is True

    def test_validate_percentage_edge_cases(self):
        """Test validating edge case values"""
        assert validate_percentage(50.0) is True
        assert validate_percentage(50) is True
        assert validate_percentage(0.001) is True
        assert validate_percentage(99.999) is True


class TestIntegration:
    """Integration tests for validators"""

    def test_validator_consistency(self):
        """Test that validators are consistent with each other"""
        # Grade validation should accept the same range as percentage validation
        assert validate_grade(85) == validate_percentage(85)
        assert validate_grade(0) == validate_percentage(0)
        assert validate_grade(100) == validate_percentage(100)

    def test_validator_error_handling(self):
        """Test error handling across validators"""
        # All validators should handle None gracefully
        assert validate_grade(None) is False
        assert validate_gpa(None) is False
        assert validate_percentage(None) is False

        # All validators should handle invalid strings gracefully
        assert validate_grade("invalid") is False
        assert validate_gpa("invalid") is False
        assert validate_percentage("invalid") is False
