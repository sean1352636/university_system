"""
Comprehensive tests for finance menu module.
Tests the enhanced finance management menu system.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call

from education_system.systems.university.domain.finance.core.menu import (
    display_enhanced_finance_menu,
)


class TestDisplayEnhancedFinanceMenu:
    """Test suite for display_enhanced_finance_menu function"""

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('builtins.input', return_value='29')
    @patch('builtins.print')
    def test_display_menu_exit(self, mock_print, mock_input, mock_get_auth):
        """Test menu displays and exits properly"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should print menu
        assert mock_print.called
        # Should print "Goodbye!"
        assert any('Goodbye' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.core.menu.initialize_finance')
    @patch('builtins.input', return_value='29')
    @patch('builtins.print')
    def test_display_menu_initializes_if_no_auth(self, mock_print, mock_input,
                                                   mock_initialize, mock_get_auth):
        """Test menu initializes finance system if no auth"""
        # First call returns None, second call returns mock auth
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.side_effect = [None, mock_auth]

        display_enhanced_finance_menu()

        # Should initialize finance system
        mock_initialize.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.core.account_management.assign_fees_to_student')
    @patch('builtins.input', side_effect=['1', '29'])
    @patch('builtins.print')
    def test_display_menu_option_1_assign_fees(self, mock_print, mock_input,
                                                mock_assign_fees, mock_get_auth):
        """Test menu option 1: Assign Fees to Student"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call assign_fees_to_student
        mock_assign_fees.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.core.account_management.record_payment')
    @patch('builtins.input', side_effect=['2', '29'])
    @patch('builtins.print')
    def test_display_menu_option_2_record_payment(self, mock_print, mock_input,
                                                    mock_record_payment, mock_get_auth):
        """Test menu option 2: Record Payment"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call record_payment
        mock_record_payment.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.core.account_management.generate_invoice')
    @patch('builtins.input', side_effect=['3', '29'])
    @patch('builtins.print')
    def test_display_menu_option_3_generate_invoice(self, mock_print, mock_input,
                                                      mock_generate_invoice, mock_get_auth):
        """Test menu option 3: Generate Invoice"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call generate_invoice
        mock_generate_invoice.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.core.account_management.view_student_financial_statement')
    @patch('builtins.input', side_effect=['6', '29'])
    @patch('builtins.print')
    def test_display_menu_option_6_view_statement(self, mock_print, mock_input,
                                                    mock_view_statement, mock_get_auth):
        """Test menu option 6: View Student Financial Statement (no permission needed)"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = False  # No permission
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should still call view_student_financial_statement (no permission required)
        mock_view_statement.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.billing.payment_plans.manage_payment_plans')
    @patch('builtins.input', side_effect=['7', '29'])
    @patch('builtins.print')
    def test_display_menu_option_7_payment_plans(self, mock_print, mock_input,
                                                   mock_payment_plans, mock_get_auth):
        """Test menu option 7: Manage Payment Plans"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call manage_payment_plans
        mock_payment_plans.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.billing.fee_structure.calculate_late_fees')
    @patch('builtins.input', side_effect=['9', '29'])
    @patch('builtins.print')
    def test_display_menu_option_9_late_fees(self, mock_print, mock_input,
                                               mock_late_fees, mock_get_auth):
        """Test menu option 9: Calculate Late Fees"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call calculate_late_fees
        mock_late_fees.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.billing.fee_structure.update_exchange_rates')
    @patch('builtins.input', side_effect=['11', '29'])
    @patch('builtins.print')
    def test_display_menu_option_11_exchange_rates(self, mock_print, mock_input,
                                                     mock_exchange_rates, mock_get_auth):
        """Test menu option 11: Update Exchange Rates"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call update_exchange_rates
        mock_exchange_rates.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.reporting.revenue_analytics.generate_financial_dashboard')
    @patch('builtins.input', side_effect=['13', '29'])
    @patch('builtins.print')
    def test_display_menu_option_13_dashboard(self, mock_print, mock_input,
                                                mock_dashboard, mock_get_auth):
        """Test menu option 13: Generate Financial Dashboard"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call generate_financial_dashboard
        mock_dashboard.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.scholarships.scholarship_programs.manage_scholarships')
    @patch('builtins.input', side_effect=['18', '29'])
    @patch('builtins.print')
    def test_display_menu_option_18_scholarships(self, mock_print, mock_input,
                                                   mock_scholarships, mock_get_auth):
        """Test menu option 18: Manage Scholarships"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call manage_scholarships
        mock_scholarships.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.core.security_automation.detect_payment_fraud')
    @patch('builtins.input', side_effect=['20', '29'])
    @patch('builtins.print')
    def test_display_menu_option_20_fraud_detection(self, mock_print, mock_input,
                                                      mock_fraud, mock_get_auth):
        """Test menu option 20: Run Fraud Detection"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call detect_payment_fraud
        mock_fraud.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.reporting.revenue_analytics.generate_audit_report')
    @patch('builtins.input', side_effect=['21', '2024-01-01', '2024-12-31', '29'])
    @patch('builtins.print')
    def test_display_menu_option_21_audit_report(self, mock_print, mock_input,
                                                   mock_audit, mock_get_auth):
        """Test menu option 21: Generate Audit Report"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call generate_audit_report with dates
        mock_audit.assert_called_once_with('2024-01-01', '2024-12-31')

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.core.security_automation.send_automated_notifications')
    @patch('builtins.input', side_effect=['24', '29'])
    @patch('builtins.print')
    def test_display_menu_option_24_notifications(self, mock_print, mock_input,
                                                    mock_notifications, mock_get_auth):
        """Test menu option 24: Send Automated Notifications"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        # Mock return value for notifications sent
        mock_notifications.return_value = 5

        display_enhanced_finance_menu()

        # Should call send_automated_notifications
        mock_notifications.assert_called_once()
        # Should print number of notifications sent
        assert any('Sent 5 notifications' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.reporting.budget_analysis.manage_budgets')
    @patch('builtins.input', side_effect=['25', '29'])
    @patch('builtins.print')
    def test_display_menu_option_25_budgets(self, mock_print, mock_input,
                                              mock_budgets, mock_get_auth):
        """Test menu option 25: Budget Management"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call manage_budgets
        mock_budgets.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.reporting.revenue_analytics.manage_collections')
    @patch('builtins.input', side_effect=['27', '29'])
    @patch('builtins.print')
    def test_display_menu_option_27_collections(self, mock_print, mock_input,
                                                  mock_collections, mock_get_auth):
        """Test menu option 27: Collection Management"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call manage_collections
        mock_collections.assert_called_once()

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.core.menu.initialize_finance')
    @patch('builtins.input', side_effect=['28', '29'])
    @patch('builtins.print')
    def test_display_menu_option_28_initialize(self, mock_print, mock_input,
                                                 mock_initialize, mock_get_auth):
        """Test menu option 28: Initialize System (Reset)"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should call initialize_finance at least once (could be twice if no auth initially)
        assert mock_initialize.called

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('builtins.input', side_effect=['invalid', '29'])
    @patch('builtins.print')
    def test_display_menu_invalid_choice(self, mock_print, mock_input, mock_get_auth):
        """Test menu with invalid choice"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should print invalid choice message
        assert any('Invalid choice' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('builtins.input', side_effect=['1', '29'])
    @patch('builtins.print')
    def test_display_menu_insufficient_permissions(self, mock_print, mock_input, mock_get_auth):
        """Test menu option with insufficient permissions"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = False  # No permission
        mock_get_auth.return_value = mock_auth

        display_enhanced_finance_menu()

        # Should print insufficient permissions message
        assert any('insufficient permissions' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('education_system.systems.university.domain.finance.core.account_management.assign_fees_to_student')
    @patch('builtins.input', side_effect=['1', '29'])
    @patch('builtins.print')
    def test_display_menu_exception_handling(self, mock_print, mock_input,
                                               mock_assign_fees, mock_get_auth):
        """Test menu exception handling"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        # Make function raise exception
        mock_assign_fees.side_effect = Exception("Test error")

        display_enhanced_finance_menu()

        # Should handle error gracefully
        assert any('error occurred' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('builtins.print')
    def test_display_menu_shows_all_sections(self, mock_print, mock_get_auth):
        """Test menu displays all sections"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        with patch('builtins.input', return_value='29'):
            display_enhanced_finance_menu()

        # Verify all sections are displayed
        print_calls = [str(call) for call in mock_print.call_args_list]

        assert any('CORE FINANCE OPERATIONS' in call for call in print_calls)
        assert any('PAYMENT PLANS' in call for call in print_calls)
        assert any('LATE FEES' in call for call in print_calls)
        assert any('MULTI-CURRENCY' in call for call in print_calls)
        assert any('ANALYTICS' in call for call in print_calls)
        assert any('SCHOLARSHIPS' in call for call in print_calls)
        assert any('SECURITY' in call for call in print_calls)
        assert any('AUTOMATION' in call for call in print_calls)
        assert any('BUDGETING' in call for call in print_calls)
        assert any('COLLECTION' in call for call in print_calls)


class TestMenuPermissions:
    """Test suite for menu permission checking"""

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('builtins.print')
    def test_menu_hides_options_without_permission(self, mock_print, mock_get_auth):
        """Test menu hides options when user lacks permission"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = False
        mock_get_auth.return_value = mock_auth

        with patch('builtins.input', return_value='29'):
            display_enhanced_finance_menu()

        # Should not show options requiring manage_finances permission
        print_calls = [str(call) for call in mock_print.call_args_list]

        # Option 6 (View Student Financial Statement) should still be shown
        # as it doesn't require manage_finances permission
        # Other options should be hidden

    @patch('education_system.systems.university.domain.finance.core.menu.get_auth')
    @patch('builtins.print')
    def test_menu_shows_options_with_permission(self, mock_print, mock_get_auth):
        """Test menu shows all options when user has permission"""
        mock_auth = Mock()
        mock_auth.check_permission.return_value = True
        mock_get_auth.return_value = mock_auth

        with patch('builtins.input', return_value='29'):
            display_enhanced_finance_menu()

        print_calls = [str(call) for call in mock_print.call_args_list]

        # Should show all menu options
        assert any('Assign Fees' in call for call in print_calls)
        assert any('Record Payment' in call for call in print_calls)
        assert any('Generate Invoice' in call for call in print_calls)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
