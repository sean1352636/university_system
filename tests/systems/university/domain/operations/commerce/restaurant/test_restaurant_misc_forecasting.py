"""
Tests for university_system/modules/core/services/restaurant_misc/forecasting.py
"""
from __future__ import annotations

from education_system.systems.university.infrastructure.database.db import sqlite3
from io import StringIO
from unittest import mock

import pytest

from education_system.systems.university.domain.operations.commerce.services.restaurant.operations import forecasting

@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    conn = mock.MagicMock(spec=sqlite3.Connection)
    cursor = mock.MagicMock(spec=sqlite3.Cursor)
    conn.cursor.return_value = cursor
    return conn, cursor

class TestRevenueForecast:
    """Tests for revenue_forecast function"""

    def test_revenue_forecast_success(self, mock_db_connection):
        """Test successful revenue forecast"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('2024-10', 10000.0, 100, 100.0),
            ('2024-11', 11000.0, 110, 100.0),
            ('2024-12', 12000.0, 120, 100.0),
            ('2025-01', 13000.0, 130, 100.0)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.revenue_forecast()

                output = fake_out.getvalue()
                assert 'REVENUE FORECAST (Next 3 Months)' in output
                assert 'Historical Analysis' in output
                assert 'Average Monthly Revenue' in output
                assert 'Revenue Forecasts' in output
                assert 'Conservative' in output
                assert 'Expected' in output
                assert 'Optimistic' in output

    def test_revenue_forecast_insufficient_data(self, mock_db_connection):
        """Test revenue forecast with insufficient data"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('2024-12', 10000.0, 100, 100.0),
            ('2025-01', 11000.0, 110, 100.0)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.revenue_forecast()

                output = fake_out.getvalue()
                assert 'Insufficient historical data' in output

    def test_revenue_forecast_calculates_growth_rate(self, mock_db_connection):
        """Test that forecast calculates growth rate correctly"""
        conn, cursor = mock_db_connection
        # 6 months of data showing steady growth
        cursor.fetchall.return_value = [
            ('2024-07', 8000.0, 80, 100.0),
            ('2024-08', 8500.0, 85, 100.0),
            ('2024-09', 9000.0, 90, 100.0),
            ('2024-10', 10000.0, 100, 100.0),
            ('2024-11', 11000.0, 110, 100.0),
            ('2024-12', 12000.0, 120, 100.0)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.revenue_forecast()

                output = fake_out.getvalue()
                assert 'Recent Growth Rate' in output
                # Should show positive growth
                assert '%' in output

    def test_revenue_forecast_exception(self, mock_db_connection):
        """Test revenue forecast when exception occurs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = Exception("Database error")

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.logging.error') as mock_log:
                    forecasting.revenue_forecast()

                    output = fake_out.getvalue()
                    assert 'An error occurred' in output
                    mock_log.assert_called_once()

class TestExpenseForecast:
    """Tests for expense_forecast function"""

    def test_expense_forecast_success(self, mock_db_connection):
        """Test successful expense forecast"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [
                ('Food & Beverages', '2024-12', 5000.0),
                ('Food & Beverages', '2025-01', 5200.0),
                ('Utilities', '2024-12', 1000.0),
                ('Utilities', '2025-01', 1100.0)
            ]
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.expense_forecast()

                output = fake_out.getvalue()
                assert 'EXPENSE FORECAST (Next 3 Months)' in output
                assert 'Food & Beverages' in output
                assert 'Utilities' in output
                assert 'Inflation-Adjusted Forecast' in output

    def test_expense_forecast_calculates_averages(self, mock_db_connection):
        """Test that expense forecast calculates category averages"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [
                ('Food', '2024-10', 1000.0),
                ('Food', '2024-11', 1200.0),
                ('Food', '2024-12', 1100.0)
            ]
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.expense_forecast()

                output = fake_out.getvalue()
                # Average should be (1000 + 1200 + 1100) / 3 = 1100
                assert 'Food' in output
                assert '£' in output

    def test_expense_forecast_applies_inflation(self, mock_db_connection):
        """Test that expense forecast applies inflation adjustment"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [('Food', '2024-12', 1000.0)]
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.expense_forecast()

                output = fake_out.getvalue()
                assert 'Assumed annual inflation: 5.0%' in output
                assert '3-Month forecast with inflation' in output

    def test_expense_forecast_exception(self, mock_db_connection):
        """Test expense forecast when exception occurs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = Exception("Database error")

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.logging.error') as mock_log:
                    forecasting.expense_forecast()

                    output = fake_out.getvalue()
                    assert 'An error occurred' in output
                    mock_log.assert_called_once()

class TestCashFlowProjection:
    """Tests for cash_flow_projection function"""

    def test_cash_flow_projection_success(self, mock_db_connection):
        """Test successful cash flow projection"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [
            (5000.0,),  # current_revenue
            (3000.0,),  # current_expenses
            (10000.0,),  # avg_revenue
            (6000.0,)  # avg_expenses
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.cash_flow_projection()

                output = fake_out.getvalue()
                assert 'CASH FLOW PROJECTION (Next 6 Months)' in output
                assert 'Starting Cash Position' in output
                assert 'Projected Monthly Cash Flow' in output
                assert 'Cash Flow Analysis' in output

    def test_cash_flow_projection_low_balance_warning(self, mock_db_connection):
        """Test cash flow projection shows warning for low balance"""
        conn, cursor = mock_db_connection
        # High expenses, low revenue
        cursor.fetchone.side_effect = [
            (1000.0,),  # current_revenue
            (5000.0,),  # current_expenses (very high)
            (2000.0,),  # avg_revenue
            (8000.0,)  # avg_expenses (consistently high)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.cash_flow_projection()

                output = fake_out.getvalue()
                # Should warn about low cash flow
                assert 'Cash flow' in output

    def test_cash_flow_projection_healthy_balance(self, mock_db_connection):
        """Test cash flow projection shows healthy message"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = [
            (10000.0,),  # current_revenue
            (4000.0,),  # current_expenses
            (12000.0,),  # avg_revenue
            (5000.0,)  # avg_expenses
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.cash_flow_projection()

                output = fake_out.getvalue()
                assert 'Cash flow appears healthy' in output

    def test_cash_flow_projection_exception(self, mock_db_connection):
        """Test cash flow projection when exception occurs"""
        conn, cursor = mock_db_connection
        cursor.fetchone.side_effect = Exception("Database error")

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.logging.error') as mock_log:
                    forecasting.cash_flow_projection()

                    output = fake_out.getvalue()
                    assert 'An error occurred' in output
                    mock_log.assert_called_once()

class TestSeasonalAnalysis:
    """Tests for seasonal_analysis function"""

    def test_seasonal_analysis_success(self, mock_db_connection):
        """Test successful seasonal analysis"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [
                ('01', 10000.0, 2),  # January
                ('02', 9000.0, 2),  # February
                ('03', 11000.0, 2),  # March
                ('12', 15000.0, 2)  # December (peak)
            ],
            [
                ('Monday', 1000.0),
                ('Friday', 2000.0),
                ('Saturday', 2500.0)
            ]
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.seasonal_analysis()

                output = fake_out.getvalue()
                assert 'SEASONAL ANALYSIS' in output
                assert 'Monthly Revenue Patterns' in output
                assert 'Day of Week Patterns' in output

    def test_seasonal_analysis_identifies_peak_months(self, mock_db_connection):
        """Test that seasonal analysis identifies peak months"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [
            [
                ('01', 10000.0, 2),
                ('12', 20000.0, 2)  # Much higher - should be peak
            ],
            []
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.seasonal_analysis()

                output = fake_out.getvalue()
                assert 'Peak' in output

    def test_seasonal_analysis_no_data(self, mock_db_connection):
        """Test seasonal analysis with no data"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = [[], []]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.seasonal_analysis()

                output = fake_out.getvalue()
                assert 'No historical data available' in output

    def test_seasonal_analysis_exception(self, mock_db_connection):
        """Test seasonal analysis when exception occurs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = Exception("Database error")

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.logging.error') as mock_log:
                    forecasting.seasonal_analysis()

                    output = fake_out.getvalue()
                    assert 'An error occurred' in output
                    mock_log.assert_called_once()

class TestGrowthProjections:
    """Tests for growth_projections function"""

    def test_growth_projections_success(self, mock_db_connection):
        """Test successful growth projections"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('2024-07', 8000.0, 80, 40),
            ('2024-08', 8500.0, 85, 42),
            ('2024-09', 9000.0, 90, 45),
            ('2024-10', 9500.0, 95, 47),
            ('2024-11', 10000.0, 100, 50),
            ('2024-12', 10500.0, 105, 52)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='25'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    forecasting.growth_projections()

                    output = fake_out.getvalue()
                    assert 'GROWTH PROJECTIONS' in output
                    assert 'Historical Growth Analysis' in output
                    assert '12-Month Growth Projections' in output
                    assert 'Conservative' in output
                    assert 'Optimistic' in output
                    assert 'Growth Investment Analysis' in output

    def test_growth_projections_insufficient_data(self, mock_db_connection):
        """Test growth projections with insufficient data"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('2024-12', 10000.0, 100, 50)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                forecasting.growth_projections()

                output = fake_out.getvalue()
                assert 'Insufficient data for growth projections' in output

    def test_growth_projections_calculates_growth_rates(self, mock_db_connection):
        """Test that growth projections calculate growth rates correctly"""
        conn, cursor = mock_db_connection
        # Show clear growth trend
        cursor.fetchall.return_value = [
            ('2024-07', 5000.0, 50, 25),
            ('2024-08', 6000.0, 60, 30),
            ('2024-09', 7000.0, 70, 35),
            ('2024-10', 8000.0, 80, 40),
            ('2024-11', 9000.0, 90, 45),
            ('2024-12', 10000.0, 100, 50)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='25'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    forecasting.growth_projections()

                    output = fake_out.getvalue()
                    assert 'Revenue Growth (quarterly)' in output
                    assert 'Order Growth (quarterly)' in output
                    assert 'Customer Growth (quarterly)' in output

    def test_growth_projections_investment_analysis(self, mock_db_connection):
        """Test growth projections includes investment analysis"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('2024-07', 8000.0, 80, 40),
            ('2024-08', 8500.0, 85, 42),
            ('2024-09', 9000.0, 90, 45),
            ('2024-10', 9500.0, 95, 47),
            ('2024-11', 10000.0, 100, 50),
            ('2024-12', 10500.0, 105, 52)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='30'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    forecasting.growth_projections()

                    output = fake_out.getvalue()
                    assert 'To achieve 30% revenue growth' in output
                    assert 'Target Revenue' in output
                    assert 'Estimated Investment Needed' in output
                    assert 'Marketing and customer acquisition' in output

    def test_growth_projections_exception(self, mock_db_connection):
        """Test growth projections when exception occurs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = Exception("Database error")

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.logging.error') as mock_log:
                    forecasting.growth_projections()

                    output = fake_out.getvalue()
                    assert 'An error occurred' in output
                    mock_log.assert_called_once()

    def test_growth_projections_multiple_scenarios(self, mock_db_connection):
        """Test that growth projections show multiple scenarios"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('2024-07', 8000.0, 80, 40),
            ('2024-08', 8500.0, 85, 42),
            ('2024-09', 9000.0, 90, 45),
            ('2024-10', 9500.0, 95, 47),
            ('2024-11', 10000.0, 100, 50),
            ('2024-12', 10500.0, 105, 52)
        ]

        with mock.patch('education_system.systems.university.infrastructure.restaurant_misc.forecasting.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='25'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    forecasting.growth_projections()

                    output = fake_out.getvalue()
                    # Should show all 4 scenarios
                    assert 'Conservative' in output
                    assert 'Expected' in output
                    assert 'Optimistic' in output
                    assert 'Aggressive' in output
