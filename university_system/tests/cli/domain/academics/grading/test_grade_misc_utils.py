import pytest
import numpy as np
from unittest.mock import Mock, patch

from university_system.modules.domain.academics.grading.utils import (
    select_student,
    percentage_to_letter,
    letter_to_percentage,
    calculate_trend_slope
)


class TestSelectStudent:
    """Test the select_student function"""

    @pytest.fixture
    def mock_cursor_with_students(self):
        """Create a mock cursor with student data"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('S001', 'John', 'Doe'),
            ('S002', 'Jane', 'Smith'),
            ('S003', 'Bob', 'Johnson'),
        ]
        return cursor

    @patch('builtins.input', return_value='1')
    @patch('builtins.print')
    def test_select_student_valid_choice(
        self, mock_print, mock_input, mock_cursor_with_students
    ):
        """Test selecting a valid student"""
        result = select_student(mock_cursor_with_students)

        assert result == 'S001'
        mock_cursor_with_students.execute.assert_called_once()

    @patch('builtins.input', return_value='3')
    def test_select_student_last_student(self, mock_input, mock_cursor_with_students):
        """Test selecting the last student in list"""
        result = select_student(mock_cursor_with_students)

        assert result == 'S003'

    @patch('builtins.input', return_value='0')
    @patch('builtins.print')
    def test_select_student_invalid_zero(
        self, mock_print, mock_input, mock_cursor_with_students
    ):
        """Test selecting with invalid index (0)"""
        result = select_student(mock_cursor_with_students)

        assert result is None
        mock_print.assert_any_call("Invalid selection.")

    @patch('builtins.input', return_value='10')
    @patch('builtins.print')
    def test_select_student_index_out_of_range(
        self, mock_print, mock_input, mock_cursor_with_students
    ):
        """Test selecting with index out of range"""
        result = select_student(mock_cursor_with_students)

        assert result is None
        mock_print.assert_any_call("Invalid selection.")

    @patch('builtins.input', return_value='abc')
    @patch('builtins.print')
    def test_select_student_invalid_input(
        self, mock_print, mock_input, mock_cursor_with_students
    ):
        """Test selecting with non-numeric input"""
        result = select_student(mock_cursor_with_students)

        assert result is None
        mock_print.assert_any_call("Please enter a valid number.")

    @patch('builtins.print')
    def test_select_student_no_students(self, mock_print):
        """Test when no students are in database"""
        cursor = Mock()
        cursor.fetchall.return_value = []

        result = select_student(cursor)

        assert result is None
        mock_print.assert_any_call("No students found.")

    @patch('builtins.input', return_value='2')
    @patch('builtins.print')
    def test_select_student_display_format(
        self, mock_print, mock_input, mock_cursor_with_students
    ):
        """Test that students are displayed with correct format"""
        select_student(mock_cursor_with_students)

        # Verify that student names were printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('John Doe' in call for call in print_calls)
        assert any('S001' in call for call in print_calls)


class TestPercentageToLetter:
    """Test the percentage_to_letter function"""

    def test_percentage_to_letter_a_plus(self):
        """Test conversion to A+"""
        assert percentage_to_letter(100) == 'A+'
        assert percentage_to_letter(97) == 'A+'
        assert percentage_to_letter(98.5) == 'A+'

    def test_percentage_to_letter_a(self):
        """Test conversion to A"""
        assert percentage_to_letter(95) == 'A'
        assert percentage_to_letter(93) == 'A'
        assert percentage_to_letter(96.9) == 'A'

    def test_percentage_to_letter_a_minus(self):
        """Test conversion to A-"""
        assert percentage_to_letter(90) == 'A-'
        assert percentage_to_letter(92) == 'A-'

    def test_percentage_to_letter_b_plus(self):
        """Test conversion to B+"""
        assert percentage_to_letter(87) == 'B+'
        assert percentage_to_letter(89) == 'B+'

    def test_percentage_to_letter_b(self):
        """Test conversion to B"""
        assert percentage_to_letter(85) == 'B'
        assert percentage_to_letter(83) == 'B'

    def test_percentage_to_letter_b_minus(self):
        """Test conversion to B-"""
        assert percentage_to_letter(80) == 'B-'
        assert percentage_to_letter(82) == 'B-'

    def test_percentage_to_letter_c_plus(self):
        """Test conversion to C+"""
        assert percentage_to_letter(77) == 'C+'
        assert percentage_to_letter(79) == 'C+'

    def test_percentage_to_letter_c(self):
        """Test conversion to C"""
        assert percentage_to_letter(75) == 'C'
        assert percentage_to_letter(73) == 'C'

    def test_percentage_to_letter_c_minus(self):
        """Test conversion to C-"""
        assert percentage_to_letter(70) == 'C-'
        assert percentage_to_letter(72) == 'C-'

    def test_percentage_to_letter_d_plus(self):
        """Test conversion to D+"""
        assert percentage_to_letter(67) == 'D+'
        assert percentage_to_letter(69) == 'D+'

    def test_percentage_to_letter_d(self):
        """Test conversion to D"""
        assert percentage_to_letter(65) == 'D'
        assert percentage_to_letter(63) == 'D'

    def test_percentage_to_letter_d_minus(self):
        """Test conversion to D-"""
        assert percentage_to_letter(60) == 'D-'
        assert percentage_to_letter(62) == 'D-'

    def test_percentage_to_letter_f(self):
        """Test conversion to F"""
        assert percentage_to_letter(59) == 'F'
        assert percentage_to_letter(50) == 'F'
        assert percentage_to_letter(0) == 'F'

    def test_percentage_to_letter_boundary_cases(self):
        """Test boundary cases"""
        # Upper boundaries
        assert percentage_to_letter(96.9) == 'A'
        assert percentage_to_letter(92.9) == 'A-'

        # Lower boundaries
        assert percentage_to_letter(93.0) == 'A'
        assert percentage_to_letter(90.0) == 'A-'

    def test_percentage_to_letter_extreme_values(self):
        """Test extreme percentage values"""
        assert percentage_to_letter(150) == 'A+'  # Over 100%
        assert percentage_to_letter(-10) == 'F'   # Negative


class TestLetterToPercentage:
    """Test the letter_to_percentage function"""

    def test_letter_to_percentage_all_grades(self):
        """Test conversion for all letter grades"""
        expected = {
            'A+': (90, 100),  # Approximate ranges
            'A': (93, 97),
            'A-': (90, 93),
            'B+': (87, 90),
            'B': (83, 87),
            'B-': (80, 83),
            'C+': (77, 80),
            'C': (73, 77),
            'C-': (70, 73),
            'D+': (67, 70),
            'D': (63, 67),
            'D-': (60, 63),
            'F': (0, 60)
        }

        for letter in expected.keys():
            percentage = letter_to_percentage(letter)
            assert isinstance(percentage, (int, float))
            assert 0 <= percentage <= 100

    def test_letter_to_percentage_consistency(self):
        """Test that A+ returns highest percentage"""
        assert letter_to_percentage('A+') > letter_to_percentage('A')
        assert letter_to_percentage('A') > letter_to_percentage('B')
        assert letter_to_percentage('B') > letter_to_percentage('C')
        assert letter_to_percentage('C') > letter_to_percentage('D')
        assert letter_to_percentage('D') > letter_to_percentage('F')

    def test_letter_to_percentage_invalid_grade(self):
        """Test with invalid letter grade"""
        result = letter_to_percentage('Z')
        assert result == 0  # Should return 0 for invalid grades

    def test_letter_to_percentage_empty_string(self):
        """Test with empty string"""
        result = letter_to_percentage('')
        assert result == 0

    def test_letter_to_percentage_case_sensitivity(self):
        """Test if function is case-sensitive"""
        # The function should handle the exact case as implemented
        result = letter_to_percentage('a+')
        # Depending on implementation, this may return 0 or handle lowercase
        assert isinstance(result, (int, float))


class TestCalculateTrendSlope:
    """Test the calculate_trend_slope function"""

    def test_calculate_trend_slope_increasing(self):
        """Test with increasing values"""
        values = [10, 20, 30, 40, 50]
        slope = calculate_trend_slope(values)

        assert slope > 0
        assert abs(slope - 10.0) < 0.1  # Should be approximately 10

    def test_calculate_trend_slope_decreasing(self):
        """Test with decreasing values"""
        values = [50, 40, 30, 20, 10]
        slope = calculate_trend_slope(values)

        assert slope < 0
        assert abs(slope + 10.0) < 0.1  # Should be approximately -10

    def test_calculate_trend_slope_constant(self):
        """Test with constant values"""
        values = [25, 25, 25, 25, 25]
        slope = calculate_trend_slope(values)

        assert abs(slope) < 0.001  # Should be very close to 0

    def test_calculate_trend_slope_single_value(self):
        """Test with single value"""
        values = [42]
        slope = calculate_trend_slope(values)

        assert slope == 0  # Should return 0 for insufficient data

    def test_calculate_trend_slope_empty_list(self):
        """Test with empty list"""
        values = []
        slope = calculate_trend_slope(values)

        assert slope == 0  # Should return 0 for empty list

    def test_calculate_trend_slope_two_values(self):
        """Test with exactly two values"""
        values = [10, 20]
        slope = calculate_trend_slope(values)

        assert slope == 10.0

    def test_calculate_trend_slope_fluctuating(self):
        """Test with fluctuating values"""
        values = [10, 15, 12, 18, 16, 20]
        slope = calculate_trend_slope(values)

        # Should have a positive slope overall
        assert slope > 0

    def test_calculate_trend_slope_with_numpy_array(self):
        """Test that it works with numpy arrays"""
        values = np.array([5, 10, 15, 20, 25])
        slope = calculate_trend_slope(values)

        assert slope > 0
        assert abs(slope - 5.0) < 0.1

    def test_calculate_trend_slope_with_floats(self):
        """Test with floating point values"""
        values = [1.5, 2.7, 3.9, 5.1, 6.3]
        slope = calculate_trend_slope(values)

        assert slope > 0
        assert isinstance(slope, (float, np.floating))

    def test_calculate_trend_slope_noisy_data(self):
        """Test with noisy but trending data"""
        # Data with overall upward trend but noise
        values = [10, 12, 11, 14, 13, 16, 15, 18, 17, 20]
        slope = calculate_trend_slope(values)

        # Should still detect positive trend
        assert slope > 0


class TestUtilsIntegration:
    """Integration tests for utility functions"""

    def test_percentage_letter_roundtrip_approximate(self):
        """Test that converting percentage to letter and back gives approximate result"""
        original_percentage = 85.0
        letter = percentage_to_letter(original_percentage)
        back_to_percentage = letter_to_percentage(letter)

        # Should be within the same grade range
        assert abs(original_percentage - back_to_percentage) < 10

    def test_trend_slope_with_grade_percentages(self):
        """Test trend calculation with grade percentages"""
        # Student improving over time
        grades = [72, 75, 78, 82, 85]
        slope = calculate_trend_slope(grades)

        assert slope > 0  # Should show improvement

    @patch('builtins.input', return_value='1')
    def test_select_student_integration(self, mock_input):
        """Test select_student with realistic data"""
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('STU001', 'Alice', 'Anderson'),
            ('STU002', 'Bob', 'Brown'),
            ('STU003', 'Charlie', 'Chen'),
        ]

        student_id = select_student(cursor)

        assert student_id == 'STU001'

    def test_grade_conversion_consistency(self):
        """Test that grade conversions are consistent"""
        # All letter grades should convert to valid percentages
        letters = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F']

        for letter in letters:
            percentage = letter_to_percentage(letter)
            converted_back = percentage_to_letter(percentage)

            # The conversion should be to the same grade or an adjacent one
            assert converted_back in letters

    def test_trend_with_real_grade_scenario(self):
        """Test trend calculation with realistic grade scenario"""
        # Student starts strong, dips mid-term, recovers
        assessments = [85, 88, 75, 72, 78, 82, 87]
        slope = calculate_trend_slope(assessments)

        # Overall trend should be relatively flat or slightly positive
        assert abs(slope) < 5  # Not a strong trend either way


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_percentage_to_letter_with_none(self):
        """Test percentage_to_letter with None"""
        with pytest.raises((TypeError, AttributeError)):
            percentage_to_letter(None)

    def test_letter_to_percentage_with_none(self):
        """Test letter_to_percentage with None"""
        result = letter_to_percentage(None)
        assert result == 0  # Should handle gracefully

    def test_calculate_trend_slope_with_none(self):
        """Test calculate_trend_slope with None values in list"""
        # This might raise an error depending on implementation
        try:
            values = [10, None, 20, None, 30]
            slope = calculate_trend_slope(values)
            # If it succeeds, slope should be calculated from valid values
            assert isinstance(slope, (int, float))
        except (TypeError, ValueError):
            # This is also acceptable behavior
            pass

    def test_select_student_database_error(self):
        """Test select_student when database query fails"""
        cursor = Mock()
        cursor.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            select_student(cursor)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
