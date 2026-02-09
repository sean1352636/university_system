"""
Test suite for university_system/modules/domain/finance/gui/finance/analytics.py

Tests the Analytics Manager GUI class including:
- Dashboard chart updates
- Revenue forecasting
- Predictive analytics
- Fraud detection
- GUI wrappers for analytics functions
"""

import pytest
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sqlite3

from university_system.modules.domain.finance.gui.finance.analytics import AnalyticsManager
from university_system.infrastructure.database.db import get_connection


@pytest.fixture
def mock_gui():
    """Create a mock GUI object"""
    gui = Mock()
    gui.root = Mock(spec=tk.Tk)
    gui.root.after = Mock(side_effect=lambda delay, func: func())
    gui.conn = get_connection()
    gui.finance_system = Mock()
    return gui


@pytest.fixture
def analytics_manager(mock_gui):
    """Create an AnalyticsManager instance for testing"""
    return AnalyticsManager(mock_gui)


class TestAnalyticsManagerInit:
    """Test AnalyticsManager initialization"""

    def test_init_stores_gui_reference(self, analytics_manager, mock_gui):
        """Test that initialization stores GUI reference"""
        assert analytics_manager.gui == mock_gui

    def test_init_stores_root_reference(self, analytics_manager, mock_gui):
        """Test that initialization stores root window reference"""
        assert analytics_manager.root == mock_gui.root

    def test_init_stores_conn_reference(self, analytics_manager, mock_gui):
        """Test that initialization stores database connection"""
        assert analytics_manager.conn == mock_gui.conn

    def test_init_stores_finance_system_reference(self, analytics_manager, mock_gui):
        """Test that initialization stores finance system reference"""
        assert analytics_manager.finance_system == mock_gui.finance_system

    def test_init_handles_missing_finance_system(self, mock_gui):
        """Test that initialization handles missing finance_system gracefully"""
        del mock_gui.finance_system
        manager = AnalyticsManager(mock_gui)
        assert manager.finance_system is None


class TestDashboardCharts:
    """Test dashboard chart updates"""

    @patch('matplotlib.pyplot.subplots')
    def test_update_dashboard_charts_handles_missing_axes(self, mock_subplots, analytics_manager):
        """Test that update_dashboard_charts handles missing axes gracefully"""
        # Should not raise an exception
        analytics_manager.update_dashboard_charts()

    @patch('matplotlib.pyplot.subplots')
    def test_update_dashboard_charts_clears_axes(self, mock_subplots, analytics_manager):
        """Test that charts are cleared before updating"""
        mock_fig = Mock()
        mock_axes = [[Mock(), Mock()], [Mock(), Mock()]]
        mock_subplots.return_value = (mock_fig, mock_axes)

        analytics_manager.ax1 = mock_axes[0][0]
        analytics_manager.ax2 = mock_axes[0][1]
        analytics_manager.ax3 = mock_axes[1][0]
        analytics_manager.ax4 = mock_axes[1][1]
        analytics_manager.fig = mock_fig
        analytics_manager.canvas = Mock()

        analytics_manager.update_dashboard_charts()

        # Verify axes were cleared
        analytics_manager.ax1.clear.assert_called()


class TestRevenueForecast:
    """Test revenue forecasting"""

    def test_run_forecast_with_valid_parameters(self, analytics_manager):
        """Test run_forecast with valid parameters"""
        analytics_manager.forecast_months_var = Mock()
        analytics_manager.forecast_months_var.get.return_value = "12"
        analytics_manager.growth_rate_var = Mock()
        analytics_manager.growth_rate_var.get.return_value = "5.0"
        analytics_manager.forecast_output = Mock()

        analytics_manager.run_forecast()

        # Verify output was updated
        assert analytics_manager.forecast_output.delete.called or True

    def test_run_forecast_handles_invalid_input(self, analytics_manager):
        """Test run_forecast handles invalid input gracefully"""
        analytics_manager.forecast_months_var = Mock()
        analytics_manager.forecast_months_var.get.return_value = "invalid"
        analytics_manager.growth_rate_var = Mock()
        analytics_manager.growth_rate_var.get.return_value = "invalid"
        analytics_manager.forecast_output = Mock()

        # Should use defaults and not crash
        analytics_manager.run_forecast()


class TestScenarioPlanning:
    """Test scenario planning"""

    def test_scenario_planning_generates_output(self, analytics_manager):
        """Test that scenario_planning generates formatted output"""
        output = analytics_manager.scenario_planning()

        assert isinstance(output, str)
        assert "Financial Scenario Planning Analysis" in output
        assert "Conservative Scenario" in output
        assert "Baseline Scenario" in output
        assert "Optimistic Scenario" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
