"""
Tests for Financial Aid Common Imports Module

This module contains unit tests for common utility functions and imports used across
the financial aid GUI components.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
from decimal import Decimal

from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports import (
    configure_styles,
    create_scrollable_frame,
    create_data_table,
    create_search_filter_bar,
    format_currency,
    format_date,
    validate_decimal,
    validate_date,
    show_error,
    show_success,
    show_warning,
    confirm_action,
    create_stat_card,
    export_to_csv,
    get_current_user,
    check_permission,
    get_student_id,
    clear_frame,
    get_current_academic_year,
    get_academic_year_list,
    get_status_color,
    COLORS,
    STATUS_COLORS
)


class TestConstants:
    """Test module constants"""

    def test_colors_dict(self):
        """Test COLORS dictionary contains required keys"""
        required_colors = ['primary', 'secondary', 'success', 'warning',
                          'danger', 'info', 'light', 'dark', 'white']

        for color in required_colors:
            assert color in COLORS
            assert isinstance(COLORS[color], str)
            assert COLORS[color].startswith('#') or color == 'white'

    def test_status_colors_dict(self):
        """Test STATUS_COLORS dictionary contains status mappings"""
        required_statuses = ['pending', 'approved', 'denied', 'awarded',
                            'disbursed', 'active', 'inactive']

        for status in required_statuses:
            assert status in STATUS_COLORS
            assert isinstance(STATUS_COLORS[status], str)


class TestStyleConfiguration:
    """Test style configuration functions"""

    def test_configure_styles(self):
        """Test configure_styles creates ttk styles"""
        root = tk.Tk()

        configure_styles()

        style = ttk.Style()
        # Verify some styles were configured
        # Note: We can't easily verify all styles, but we can check the function runs without error

        root.destroy()


class TestWidgetCreation:
    """Test widget creation functions"""

    def test_create_scrollable_frame(self):
        """Test create_scrollable_frame returns proper widgets"""
        root = tk.Tk()
        parent = ttk.Frame(root)

        scrollable_frame, canvas, scrollbar = create_scrollable_frame(parent)

        assert isinstance(scrollable_frame, ttk.Frame)
        assert isinstance(canvas, tk.Canvas)
        assert isinstance(scrollbar, ttk.Scrollbar)

        root.destroy()

    def test_create_data_table(self):
        """Test create_data_table creates Treeview widget"""
        root = tk.Tk()
        parent = ttk.Frame(root)

        columns = ['Col1', 'Col2', 'Col3']
        tree = create_data_table(parent, columns)

        assert isinstance(tree, ttk.Treeview)
        assert isinstance(tree, ttk.Treeview)

        root.destroy()

    def test_create_data_table_with_widths(self):
        """Test create_data_table with custom column widths"""
        root = tk.Tk()
        parent = ttk.Frame(root)

        columns = ['Col1', 'Col2']
        widths = {'Col1': 150, 'Col2': 200}
        tree = create_data_table(parent, columns, widths)

        assert isinstance(tree, ttk.Treeview)

        root.destroy()

    def test_create_search_filter_bar(self):
        """Test create_search_filter_bar creates search widgets"""
        root = tk.Tk()
        parent = ttk.Frame(root)

        callback = Mock()
        search_entry, filter_combo = create_search_filter_bar(
            parent, callback, ['Option1', 'Option2']
        )

        assert isinstance(search_entry, ttk.Entry)
        assert isinstance(filter_combo, ttk.Combobox)

        root.destroy()

    def test_create_search_filter_bar_no_filters(self):
        """Test create_search_filter_bar without filter options"""
        root = tk.Tk()
        parent = ttk.Frame(root)

        callback = Mock()
        search_entry, filter_combo = create_search_filter_bar(parent, callback)

        assert isinstance(search_entry, ttk.Entry)
        assert filter_combo is None

        root.destroy()

    def test_create_stat_card(self):
        """Test create_stat_card creates frame with statistics"""
        root = tk.Tk()
        parent = ttk.Frame(root)

        card = create_stat_card(parent, "Test Stat", "42", "success")

        assert isinstance(card, ttk.Frame)

        root.destroy()


class TestFormatting:
    """Test formatting functions"""

    def test_format_currency(self):
        """Test format_currency formats numbers correctly"""
        assert format_currency(1000) == "£1,000.00"
        assert format_currency(1000.50) == "£1,000.50"
        assert format_currency(0) == "£0.00"
        assert format_currency(-500) == "£-500.00"

    def test_format_date_datetime_object(self):
        """Test format_date with datetime object"""
        test_date = datetime(2023, 9, 15, 10, 30)
        result = format_date(test_date)
        assert result == "2023-09-15"

    def test_format_date_date_object(self):
        """Test format_date with date object"""
        test_date = date(2023, 9, 15)
        result = format_date(test_date)
        assert result == "2023-09-15"

    def test_format_date_string(self):
        """Test format_date with string input"""
        result = format_date("2023-09-15")
        assert result == "2023-09-15"

    def test_format_date_invalid_string(self):
        """Test format_date with invalid string"""
        result = format_date("invalid")
        assert result == "invalid"


class TestValidation:
    """Test validation functions"""

    def test_validate_decimal_valid(self):
        """Test validate_decimal with valid inputs"""
        assert validate_decimal("123.45") is True
        assert validate_decimal("0") is True
        assert validate_decimal("-50.25") is True

    def test_validate_decimal_invalid(self):
        """Test validate_decimal with invalid inputs"""
        assert validate_decimal("abc") is False
        assert validate_decimal("12.34.56") is False
        assert validate_decimal("") is False

    def test_validate_date_valid_formats(self):
        """Test validate_date with valid date formats"""
        assert validate_date("2023-09-15") is True
        assert validate_date("09/15/2023") is True

    def test_validate_date_invalid(self):
        """Test validate_date with invalid dates"""
        assert validate_date("invalid") is False
        assert validate_date("2023-13-45") is False
        assert validate_date("") is False


class TestDialogs:
    """Test dialog functions"""

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.messagebox.showerror')
    def test_show_error(self, mock_error):
        """Test show_error displays error dialog"""
        show_error("Test Title", "Test Message")
        mock_error.assert_called_once_with("Test Title", "Test Message")

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.messagebox.showinfo')
    def test_show_success(self, mock_info):
        """Test show_success displays success dialog"""
        show_success("Test Title", "Test Message")
        mock_info.assert_called_once_with("Test Title", "Test Message")

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.messagebox.showwarning')
    def test_show_warning(self, mock_warning):
        """Test show_warning displays warning dialog"""
        show_warning("Test Title", "Test Message")
        mock_warning.assert_called_once_with("Test Title", "Test Message")

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.messagebox.askyesno')
    def test_confirm_action_yes(self, mock_confirm):
        """Test confirm_action returns True when confirmed"""
        mock_confirm.return_value = True
        result = confirm_action("Confirm this action?")
        assert result is True

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.messagebox.askyesno')
    def test_confirm_action_no(self, mock_confirm):
        """Test confirm_action returns False when cancelled"""
        mock_confirm.return_value = False
        result = confirm_action("Confirm this action?")
        assert result is False


class TestUserContext:
    """Test user context functions"""

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.get_auth')
    def test_get_current_user(self, mock_get_auth):
        """Test get_current_user returns current user"""
        mock_auth = Mock()
        mock_user = Mock(username='testuser')
        mock_auth.current_user = mock_user
        mock_get_auth.return_value = mock_auth

        result = get_current_user()
        assert result == mock_user

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.get_auth')
    def test_get_current_user_not_logged_in(self, mock_get_auth):
        """Test get_current_user returns None when not logged in"""
        mock_auth = Mock()
        mock_auth.current_user = None
        mock_get_auth.return_value = mock_auth

        result = get_current_user()
        assert result is None

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.get_auth')
    def test_check_permission_has_permission(self, mock_get_auth):
        """Test check_permission returns True when user has permission"""
        mock_auth = Mock()
        mock_auth.current_user = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        result = check_permission('test_permission')
        assert result is True

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.get_auth')
    def test_check_permission_no_permission(self, mock_get_auth):
        """Test check_permission returns False when user lacks permission"""
        mock_auth = Mock()
        mock_auth.current_user = Mock()
        mock_auth.check_permission.return_value = False
        mock_get_auth.return_value = mock_auth

        result = check_permission('test_permission')
        assert result is False

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.get_current_user')
    def test_get_student_id_with_dict(self, mock_get_user):
        """Test get_student_id with dict user"""
        mock_user = {'student_id': 'S12345'}
        mock_get_user.return_value = mock_user

        result = get_student_id()
        assert result == 'S12345'

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.get_current_user')
    def test_get_student_id_with_object(self, mock_get_user):
        """Test get_student_id with object user"""
        mock_user = Mock()
        mock_user.student_id = 'S12345'
        mock_user.to_dict.return_value = {'student_id': 'S12345'}
        mock_get_user.return_value = mock_user

        result = get_student_id()
        assert result == 'S12345'

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.get_current_user')
    def test_get_student_id_no_user(self, mock_get_user):
        """Test get_student_id returns None when no user"""
        mock_get_user.return_value = None

        result = get_student_id()
        assert result is None


class TestUtilities:
    """Test utility functions"""

    def test_clear_frame(self):
        """Test clear_frame removes all widgets from a frame"""
        # Use a Mock frame to test the function logic directly
        mock_frame = Mock()
        mock_frame.winfo_exists.return_value = True
        widget1 = Mock()
        widget2 = Mock()
        mock_frame.winfo_children.return_value = [widget1, widget2]

        clear_frame(mock_frame)

        widget1.destroy.assert_called_once()
        widget2.destroy.assert_called_once()

    def test_clear_frame_invalid_frame(self):
        """Test clear_frame handles invalid frame gracefully"""
        # Should not raise an exception
        clear_frame(None)

    def test_get_current_academic_year_fall(self):
        """Test get_current_academic_year in fall semester"""
        with patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.date') as mock_date:
            mock_date.today.return_value = date(2023, 9, 15)
            result = get_current_academic_year()
            assert result == "2023-2024"

    def test_get_current_academic_year_spring(self):
        """Test get_current_academic_year in spring semester"""
        with patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.date') as mock_date:
            mock_date.today.return_value = date(2024, 3, 15)
            result = get_current_academic_year()
            assert result == "2023-2024"

    def test_get_academic_year_list(self):
        """Test get_academic_year_list returns list of years"""
        with patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.get_current_academic_year') as mock_current:
            mock_current.return_value = "2023-2024"
            result = get_academic_year_list(3)

            assert isinstance(result, list)
            assert len(result) == 5  # -2 to +3
            assert "2023-2024" in result

    def test_get_status_color(self):
        """Test get_status_color returns correct colors"""
        assert get_status_color('pending') == STATUS_COLORS['pending']
        assert get_status_color('approved') == STATUS_COLORS['approved']
        assert get_status_color('denied') == STATUS_COLORS['denied']

        # Test unknown status
        result = get_status_color('unknown_status')
        assert result == COLORS['dark']


class TestExport:
    """Test export functions"""

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.filedialog.asksaveasfilename')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.show_success')
    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.log_activity')
    @patch('builtins.open', create=True)
    def test_export_to_csv_success(self, mock_open, mock_log, mock_success, mock_filedialog):
        """Test export_to_csv exports data successfully"""
        mock_filedialog.return_value = '/tmp/test.csv'

        data = [
            {'name': 'John', 'age': 25},
            {'name': 'Jane', 'age': 30}
        ]

        export_to_csv(data, 'test.csv')

        mock_filedialog.assert_called_once()
        mock_success.assert_called_once()
        mock_log.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports.show_warning')
    def test_export_to_csv_no_data(self, mock_warning):
        """Test export_to_csv handles empty data"""
        export_to_csv([], 'test.csv')
        mock_warning.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
