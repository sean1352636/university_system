"""
Tests for Budget Analysis Module

This module contains unit tests for budget management and analysis functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from education_system.systems.university.domain.finance.reporting.budget_analysis import (
    manage_budgets,
    create_budget_plan,
    view_budget_plans,
    update_budget_plan,
    budget_vs_actual_analysis,
    manage_budget_categories,
    create_budget_category
)


class TestBudgetCreation:
    """Test budget creation functions"""

    @patch('education_system.systems.university.domain.finance.reporting.budget_analysis.get_connection')
    @patch('builtins.input')
    def test_create_budget_plan(self, mock_input, mock_get_conn):
        """Test create_budget_plan function"""
        # Mock inputs - budget name, year, currency, then 'done' to skip line items
        mock_input.side_effect = ['Test Budget', '2023-2024', 'GBP', 'DONE']

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 123
        # Mock fetchall to return empty list of categories
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Mock auth
        with patch('education_system.systems.university.domain.finance.reporting.budget_analysis.auth') as mock_auth:
            mock_auth.current_user = {'username': 'admin'}

            create_budget_plan()

            mock_cursor.execute.assert_called()

    @patch('education_system.systems.university.domain.finance.reporting.budget_analysis.get_connection')
    def test_view_budget_plans(self, mock_get_conn):
        """Test view_budget_plans function"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_budget = ('B123', 'Test Budget', '2023-2024', 'GBP', 'active',
                      100000.0, 80000.0, 'admin', '2023-09-01')

        mock_cursor.fetchall.return_value = [mock_budget]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        with patch('builtins.input', return_value=''):
            view_budget_plans()

            mock_cursor.execute.assert_called()


class TestBudgetCategories:
    """Test budget category functions"""

    @patch('education_system.systems.university.domain.finance.reporting.budget_analysis.get_connection')
    @patch('builtins.input')
    def test_create_budget_category(self, mock_input, mock_get_conn):
        """Test create_budget_category function"""
        mock_input.side_effect = ['Test Category', '1', '0', '']

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 456
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        create_budget_category()

        mock_cursor.execute.assert_called()


class TestBudgetAnalysis:
    """Test budget analysis functions"""

    @patch('education_system.systems.university.domain.finance.reporting.budget_analysis.get_connection')
    @patch('builtins.input')
    def test_budget_vs_actual_analysis(self, mock_input, mock_get_conn):
        """Test budget_vs_actual_analysis function"""
        mock_input.return_value = 'B123'

        mock_conn = Mock()
        mock_cursor = Mock()

        mock_budget = ('Test Budget', '2023-2024', 100000.0, 80000.0)
        mock_cursor.fetchone.return_value = mock_budget
        mock_cursor.fetchall.return_value = []

        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        budget_vs_actual_analysis()

        assert mock_cursor.execute.call_count >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
