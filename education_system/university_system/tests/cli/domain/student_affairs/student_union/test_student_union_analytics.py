"""
Tests for student union analytics module.
Tests advanced analytics and reporting functionality.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from unittest.mock import Mock, patch

from education_system.university_system.modules.domain.student_affairs.student_union.services import analytics

@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = Mock()
    cursor.fetchall = Mock(return_value=[])
    cursor.fetchone = Mock(return_value=None)
    cursor.execute = Mock()
    return cursor

@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    conn = Mock()
    conn.cursor = Mock()
    conn.close = Mock()
    return conn

class TestActivityCorrelationAnalysis:
    """Tests for activity_correlation_analysis function."""

    @patch('builtins.print')
    def test_correlation_with_sufficient_data(self, mock_print, mock_cursor):
        """Test correlation analysis with sufficient data."""
        # Sample data: clubs_joined, events_attended, student_id
        activity_data = [(i % 5 + 1, i % 3 + 1, f'S{i}') for i in range(20)]
        leadership_data = [(f'S{i}', i % 2, i % 3, i % 5) for i in range(20)]
        
        mock_cursor.fetchall.side_effect = [activity_data, leadership_data, []]
        
        analytics.activity_correlation_analysis(mock_cursor)
        
        # Verify correlation output
        assert any('Correlation' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.print')
    def test_correlation_insufficient_data(self, mock_print, mock_cursor):
        """Test with insufficient data for correlation."""
        mock_cursor.fetchall.side_effect = [
            [(1, 2, 'S1'), (2, 3, 'S2')],  # Only 2 data points
            [],
            []
        ]
        
        analytics.activity_correlation_analysis(mock_cursor)
        
        # Should handle gracefully
        mock_cursor.execute.assert_called()

class TestGenerateAdvancedAnalytics:
    """Tests for generate_advanced_analytics function."""

    @patch('builtins.input', side_effect=['7'])
    @patch('builtins.print')
    @patch('education_system.university_system.modules.core.services.student_union_misc.analytics.get_connection')
    @patch('education_system.university_system.modules.core.services.student_union_misc.context')
    def test_analytics_menu_exit(self, mock_ctx, mock_get_conn, mock_print, mock_input):
        """Test analytics menu displays and exits."""
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=True)
        
        mock_conn = Mock()
        mock_conn.cursor.return_value = Mock()
        mock_get_conn.return_value = mock_conn
        
        analytics.generate_advanced_analytics()
        
        # Verify menu was displayed
        assert any('Advanced Analytics' in str(call) for call in mock_print.call_args_list)
        mock_conn.close.assert_called_once()

    @patch('builtins.print')
    @patch('education_system.university_system.modules.core.services.student_union_misc.context')
    def test_analytics_no_auth(self, mock_ctx, mock_print):
        """Test analytics without authentication."""
        mock_ctx.auth = None
        
        analytics.generate_advanced_analytics()
        
        # Verify access denied
        assert any('must be logged in' in str(call).lower() for call in mock_print.call_args_list)

    @patch('builtins.print')
    @patch('education_system.university_system.modules.core.services.student_union_misc.context')
    def test_analytics_no_permission(self, mock_ctx, mock_print):
        """Test analytics without permission."""
        mock_ctx.auth = Mock()
        mock_ctx.auth.current_user = {'id': 1}
        mock_ctx.auth.check_permission = Mock(return_value=False)
        
        analytics.generate_advanced_analytics()
        
        # Verify permission denied
        assert any("don't have permission" in str(call).lower() for call in mock_print.call_args_list)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
