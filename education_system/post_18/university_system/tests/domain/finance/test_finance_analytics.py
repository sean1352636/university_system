"""
Comprehensive tests for finance analytics module.
Tests all analytics functions including growth rate calculations, seasonal factors,
fee structure impact, overdue accounts, and various financial projections.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from education_system.post_18.university_system.modules.domain.finance.core.analytics import (
    calculate_growth_rate,
    calculate_seasonal_factors,
    analyze_fee_structure_impact,
    view_overdue_accounts,
    assign_case_to_agency,
    generate_enrollment_projections,
    generate_cash_flow_analysis,
    generate_risk_analysis,
    generate_scenario_planning,
    recovery_rate_analysis,
    update_actual_amounts,
)


class TestCalculateGrowthRate:
    """Test suite for calculate_growth_rate function"""

    def test_calculate_growth_rate_empty_list(self):
        """Test growth rate calculation with empty list"""
        result = calculate_growth_rate([])
        assert result == 0

    def test_calculate_growth_rate_single_value(self):
        """Test growth rate calculation with single value"""
        result = calculate_growth_rate([100])
        assert result == 0

    def test_calculate_growth_rate_positive_growth(self):
        """Test growth rate calculation with positive growth"""
        revenues = [100, 110, 121]  # 10% growth each month
        result = calculate_growth_rate(revenues)
        assert abs(result - 10.0) < 0.1

    def test_calculate_growth_rate_negative_growth(self):
        """Test growth rate calculation with negative growth"""
        revenues = [100, 90, 81]  # 10% decline each month
        result = calculate_growth_rate(revenues)
        assert result < 0

    def test_calculate_growth_rate_mixed_growth(self):
        """Test growth rate calculation with mixed growth"""
        revenues = [100, 110, 105, 115]
        result = calculate_growth_rate(revenues)
        assert isinstance(result, (int, float, np.number))

    def test_calculate_growth_rate_with_zero(self):
        """Test growth rate calculation when previous value is zero"""
        revenues = [0, 100, 110]
        result = calculate_growth_rate(revenues)
        # Should skip zero values and calculate from valid pairs
        assert isinstance(result, (int, float, np.number))

    def test_calculate_growth_rate_all_zeros(self):
        """Test growth rate calculation when all values are zero"""
        revenues = [0, 0, 0]
        result = calculate_growth_rate(revenues)
        assert result == 0


class TestCalculateSeasonalFactors:
    """Test suite for calculate_seasonal_factors function"""

    def test_calculate_seasonal_factors_basic(self):
        """Test basic seasonal factor calculation"""
        historical_data = [
            ('2024-01', 1000),
            ('2024-02', 1200),
            ('2024-03', 1100),
        ]
        result = calculate_seasonal_factors(historical_data)

        assert isinstance(result, dict)
        assert len(result) == 12  # Should have all 12 months
        assert 1 in result
        assert 2 in result
        assert 3 in result

    def test_calculate_seasonal_factors_multiple_years(self):
        """Test seasonal factors with multiple years of data"""
        historical_data = [
            ('2023-01', 1000),
            ('2023-02', 1200),
            ('2024-01', 1100),
            ('2024-02', 1300),
        ]
        result = calculate_seasonal_factors(historical_data)

        assert isinstance(result, dict)
        assert len(result) == 12
        # January and February should have factors
        assert result[1] != 1.0
        assert result[2] != 1.0

    def test_calculate_seasonal_factors_empty_data(self):
        """Test seasonal factors with empty data"""
        # This should handle empty list gracefully
        result = calculate_seasonal_factors([])
        assert isinstance(result, dict)

    def test_calculate_seasonal_factors_missing_months(self):
        """Test seasonal factors when some months are missing"""
        historical_data = [
            ('2024-01', 1000),
            ('2024-03', 1100),
            ('2024-06', 1200),
        ]
        result = calculate_seasonal_factors(historical_data)

        # Missing months should have factor of 1.0
        assert result[2] == 1.0  # February missing
        assert result[4] == 1.0  # April missing
        assert result[5] == 1.0  # May missing


class TestAnalyzeFeeStructureImpact:
    """Test suite for analyze_fee_structure_impact function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    def test_analyze_fee_structure_impact_success(self, mock_get_connection):
        """Test successful fee structure impact analysis"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock database response
        mock_cursor.fetchall.return_value = [
            ('Computer Science', 100, 9000.0),
            ('Business Administration', 80, 8500.0),
        ]

        result = analyze_fee_structure_impact()

        assert result is not None
        assert isinstance(result, dict)
        assert 'Computer Science' in result
        assert 'Business Administration' in result
        # 10% increase on 100 students at 9000 = 90000
        assert result['Computer Science'] == 90000.0

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    def test_analyze_fee_structure_impact_database_error(self, mock_get_connection):
        """Test fee structure impact analysis with database error"""
        mock_get_connection.side_effect = Exception("Database connection error")

        result = analyze_fee_structure_impact()

        assert result is None

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    def test_analyze_fee_structure_impact_no_data(self, mock_get_connection):
        """Test fee structure impact analysis with no data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = analyze_fee_structure_impact()

        assert result is not None
        assert isinstance(result, dict)
        assert len(result) == 0


class TestViewOverdueAccounts:
    """Test suite for view_overdue_accounts function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.input', return_value='')
    @patch('builtins.print')
    def test_view_overdue_accounts_with_data(self, mock_print, mock_input, mock_get_connection):
        """Test viewing overdue accounts with data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock overdue accounts data
        mock_cursor.fetchall.side_effect = [
            [  # First query - overdue accounts
                ('STU001', 'John', 'Doe', 'john@test.com', '1234567890', 500.0, '2024-01-01', 2, 30),
                ('STU002', 'Jane', 'Smith', 'jane@test.com', '0987654321', 750.0, '2024-02-01', 1, 15),
            ],
            [  # Second query - period analysis
                ('1-30 days', 2, 1250.0),
            ]
        ]

        view_overdue_accounts()

        # Verify the function printed output
        assert mock_print.called
        mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_view_overdue_accounts_no_data(self, mock_print, mock_get_connection):
        """Test viewing overdue accounts with no data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        view_overdue_accounts()

        # Should print "No overdue accounts found."
        assert any('No overdue accounts' in str(call) for call in mock_print.call_args_list)
        mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_view_overdue_accounts_database_error(self, mock_print, mock_get_connection):
        """Test viewing overdue accounts with database error"""
        import sqlite3
        mock_get_connection.side_effect = sqlite3.Error("Database error")

        view_overdue_accounts()

        # Should handle error gracefully
        assert mock_print.called


class TestAssignCaseToAgency:
    """Test suite for assign_case_to_agency function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.input', return_value='1')
    @patch('builtins.print')
    def test_assign_case_to_agency_success(self, mock_print, mock_input, mock_get_connection):
        """Test successful case assignment to agency"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock agencies data
        mock_cursor.fetchall.return_value = [
            (1, 'Collection Agency A', 10.0, 100.0),
            (2, 'Collection Agency B', 15.0, 200.0),
        ]

        assign_case_to_agency(case_id=1)

        # Verify assignment was made
        assert mock_cursor.execute.call_count >= 2
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_assign_case_to_agency_no_agencies(self, mock_print, mock_get_connection):
        """Test case assignment when no agencies available"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        assign_case_to_agency(case_id=1)

        # Should print "No active collection agencies available."
        assert any('No active collection agencies' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.input', return_value='invalid')
    @patch('builtins.print')
    def test_assign_case_to_agency_invalid_input(self, mock_print, mock_input, mock_get_connection):
        """Test case assignment with invalid input"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            (1, 'Collection Agency A', 10.0, 100.0),
        ]

        assign_case_to_agency(case_id=1)

        # Should print "Invalid input."
        assert any('Invalid' in str(call) for call in mock_print.call_args_list)


class TestGenerateEnrollmentProjections:
    """Test suite for generate_enrollment_projections function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_generate_enrollment_projections_success(self, mock_print, mock_get_connection):
        """Test successful enrollment projections generation"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock enrollment data
        mock_cursor.fetchall.return_value = [
            ('Computer Science', 100, 9000.0),
            ('Business Administration', 80, 8500.0),
        ]

        generate_enrollment_projections()

        # Verify output was printed
        assert mock_print.called
        mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_generate_enrollment_projections_no_data(self, mock_print, mock_get_connection):
        """Test enrollment projections with no data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        generate_enrollment_projections()

        # Should print "No enrollment data found."
        assert any('No enrollment data' in str(call) for call in mock_print.call_args_list)


class TestGenerateCashFlowAnalysis:
    """Test suite for generate_cash_flow_analysis function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_generate_cash_flow_analysis_success(self, mock_print, mock_get_connection):
        """Test successful cash flow analysis generation"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock cash flow data
        mock_cursor.fetchall.return_value = [
            ('2024-01', 10000.0),
            ('2024-02', 12000.0),
            ('2024-03', 11000.0),
        ]

        generate_cash_flow_analysis()

        # Verify output was printed
        assert mock_print.called
        mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_generate_cash_flow_analysis_error(self, mock_print, mock_get_connection):
        """Test cash flow analysis with error"""
        mock_get_connection.side_effect = Exception("Database error")

        generate_cash_flow_analysis()

        # Should handle error gracefully
        assert any('Error' in str(call) for call in mock_print.call_args_list)


class TestGenerateRiskAnalysis:
    """Test suite for generate_risk_analysis function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_generate_risk_analysis_success(self, mock_print, mock_get_connection):
        """Test successful risk analysis generation"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock multiple fetchone and fetchall results
        mock_cursor.fetchone.side_effect = [
            (5000.0, 10),  # total_outstanding, students_with_debt
            (2000.0, 5),   # overdue_amount, overdue_students
        ]

        mock_cursor.fetchall.side_effect = [
            [  # collection_risk
                ('Low Risk (0-30 days)', 1000.0, 3),
                ('Medium Risk (31-90 days)', 500.0, 1),
                ('High Risk (90+ days)', 500.0, 1),
            ],
            [  # course_revenue
                ('Computer Science', 20000.0, 50),
                ('Business', 15000.0, 40),
            ]
        ]

        generate_risk_analysis()

        # Verify output was printed
        assert mock_print.called
        mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_generate_risk_analysis_no_debt(self, mock_print, mock_get_connection):
        """Test risk analysis with no debt"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock no debt
        mock_cursor.fetchone.side_effect = [
            (0.0, 0),  # total_outstanding, students_with_debt
            (0.0, 0),  # overdue_amount, overdue_students
        ]
        mock_cursor.fetchall.side_effect = [[], []]

        generate_risk_analysis()

        # Should still complete successfully
        assert mock_print.called


class TestGenerateScenarioPlanning:
    """Test suite for generate_scenario_planning function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_generate_scenario_planning_success(self, mock_print, mock_get_connection):
        """Test successful scenario planning generation"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock baseline data
        mock_cursor.fetchone.side_effect = [
            (100000.0,),  # current_revenue
            (500,),       # current_students
        ]

        generate_scenario_planning()

        # Verify output was printed
        assert mock_print.called
        mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_generate_scenario_planning_zero_students(self, mock_print, mock_get_connection):
        """Test scenario planning with zero students"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            (0.0,),  # current_revenue
            (0,),    # current_students
        ]

        generate_scenario_planning()

        # Should handle zero students gracefully
        assert mock_print.called


class TestRecoveryRateAnalysis:
    """Test suite for recovery_rate_analysis function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_recovery_rate_analysis_success(self, mock_print, mock_get_connection):
        """Test successful recovery rate analysis"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock recovery data for different debt ranges
        mock_cursor.fetchone.side_effect = [
            (5, 2000.0, 1500.0),  # £0-£500
            (3, 2500.0, 2000.0),  # £500-£1000
            (2, 3000.0, 2400.0),  # £1000-£2000
            (1, 4000.0, 3200.0),  # £2000-£5000
            (1, 6000.0, 4800.0),  # £5000+
        ]

        # Mock age analysis data
        mock_cursor.fetchall.return_value = [
            ('0-30 days', 3, 1500.0, 1200.0),
            ('31-60 days', 2, 2000.0, 1500.0),
            ('61-90 days', 1, 1000.0, 600.0),
            ('90+ days', 1, 500.0, 200.0),
        ]

        recovery_rate_analysis()

        # Verify output was printed
        assert mock_print.called
        mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_recovery_rate_analysis_no_cases(self, mock_print, mock_get_connection):
        """Test recovery rate analysis with no cases"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock no data
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        recovery_rate_analysis()

        # Should handle no data gracefully
        assert mock_print.called


class TestUpdateActualAmounts:
    """Test suite for update_actual_amounts function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_update_actual_amounts_success(self, mock_print, mock_get_connection):
        """Test successful actual amounts update"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        update_actual_amounts(budget_id=1)

        # Verify update was executed
        assert mock_cursor.execute.called
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

        # Should print success message
        assert any('updated' in str(call).lower() for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.get_connection')
    @patch('builtins.print')
    def test_update_actual_amounts_error(self, mock_print, mock_get_connection):
        """Test actual amounts update with error"""
        mock_get_connection.side_effect = Exception("Database error")

        update_actual_amounts(budget_id=1)

        # Should handle error gracefully
        assert any('Error' in str(call) for call in mock_print.call_args_list)


class TestBackgroundScheduler:
    """Test suite for background scheduler"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.analytics.threading.Thread')
    @patch('builtins.print')
    def test_start_background_scheduler(self, mock_print, mock_thread):
        """Test background scheduler startup"""
        from education_system.post_18.university_system.modules.domain.finance.core.analytics import start_background_scheduler

        start_background_scheduler()

        # Verify thread was created with daemon=True and started
        mock_thread.assert_called_once()
        assert mock_thread.call_args[1].get('daemon') is True
        mock_thread.return_value.start.assert_called_once()

        # Should print success message
        assert any('scheduler started' in str(call).lower() for call in mock_print.call_args_list)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
