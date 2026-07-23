"""
Tests for student union events module.
Tests event management and virtual event functionality.
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from unittest.mock import Mock, patch

from education_system.post_18.university_system.modules.domain.student_affairs.student_union.services import events

@pytest.fixture
def mock_cursor():
    """Create a mock database cursor."""
    cursor = Mock()
    cursor.fetchall = Mock(return_value=[])
    cursor.fetchone = Mock(return_value=None)
    cursor.execute = Mock()
    return cursor

class TestManageLiveStreaming:
    """Tests for manage_live_streaming function."""

    @patch('builtins.input', side_effect=['1', '1', 'y', 'y', 'y', 'n'])
    @patch('builtins.print')
    def test_live_streaming_setup(self, mock_print, mock_input, mock_cursor):
        """Test live streaming setup process."""
        events.manage_live_streaming(mock_cursor)

        # Verify setup messages displayed
        assert any('Live Streaming' in str(call) for call in mock_print.call_args_list)
        assert any('YouTube Live' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['5', 'rtmp://server', 'key123', '4', 'n', 'n', 'n'])
    @patch('builtins.print')
    def test_custom_rtmp_stream(self, mock_print, mock_input, mock_cursor):
        """Test custom RTMP stream configuration."""
        events.manage_live_streaming(mock_cursor)

        # Verify RTMP configuration
        assert any('RTMP' in str(call) for call in mock_print.call_args_list)
        assert any('Custom stream configured' in str(call) for call in mock_print.call_args_list)

class TestInteractiveVirtualFeatures:
    """Tests for interactive_virtual_features function."""

    @patch('builtins.print')
    def test_virtual_features_display(self, mock_print, mock_cursor):
        """Test virtual features display."""
        events.interactive_virtual_features(mock_cursor)

        # Verify interactive features shown
        assert any('Interactive' in str(call) for call in mock_print.call_args_list)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
