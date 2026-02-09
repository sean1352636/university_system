"""
Tests for Analytics Manager

This module tests the AnalyticsManager class which provides analytics
and reporting functionality for the grade tracking system.
"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, MagicMock, patch, call
import sqlite3
from datetime import datetime

from university_system.modules.domain.academics.gui.grade_tracking.analytics_manager import (
    AnalyticsManager
)


@pytest.fixture
def root_window():
    """Create a root Tkinter window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def mock_app(root_window):
    """Create a mock app instance"""
    app = Mock()
    app.root = root_window
    app.auth = Mock()
    app.conn = Mock(spec=sqlite3.Connection)

    # Create a mock layout with content_frame
    app.layout = Mock()
    app.layout.content_frame = ttk.Frame(root_window)

    return app


class TestAnalyticsManager:
    """Test suite for AnalyticsManager"""

    def test_initialization(self, mock_app):
        """Test analytics manager initialization"""
        manager = AnalyticsManager(mock_app)

        assert manager.app == mock_app
        assert manager.root == mock_app.root
        assert manager.auth == mock_app.auth
        assert manager.conn == mock_app.conn

    def test_content_frame_property(self, mock_app):
        """Test content_frame property returns correct frame"""
        manager = AnalyticsManager(mock_app)

        frame = manager.content_frame

        assert frame == mock_app.layout.content_frame

    def test_content_frame_property_no_layout(self, mock_app):
        """Test content_frame property when layout doesn't exist"""
        del mock_app.layout
        manager = AnalyticsManager(mock_app)

        frame = manager.content_frame

        assert frame is None

    def test_create_analytics_content(self, mock_app):
        """Test creating analytics content"""
        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        assert hasattr(manager, 'notebook')
        assert hasattr(manager, 'analytics_results')
        assert hasattr(manager, 'chart_frame')

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_identify_at_risk_students(self, mock_get_conn, mock_app):
        """Test identifying at-risk students"""
        # Mock database connection
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('student001', 'John Doe', 55.0, 2.1, 'CS101'),
            ('student002', 'Jane Smith', 50.0, 1.8, 'CS102')
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        # Call the method
        manager.identify_at_risk_students()

        # Verify database was queried
        cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_show_grade_distribution(self, mock_get_conn, mock_app):
        """Test showing grade distribution"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('A+', 5),
            ('A', 10),
            ('B+', 15),
            ('B', 20),
            ('C', 10)
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        manager.show_grade_distribution()

        cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_analyze_module_performance(self, mock_get_conn, mock_app):
        """Test analyzing module performance"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('CS101', 'Introduction to Programming', 75.5, 30),
            ('MATH201', 'Calculus I', 68.2, 25),
            ('ENG102', 'English Composition', 82.0, 35)
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        manager.analyze_module_performance()

        cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_student_risk_assessment(self, mock_get_conn, mock_app):
        """Test student risk assessment"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = (65.0, 2.5, 5, 2, 15.0)
        cursor.fetchall.return_value = [
            ('CS101', 55.0, 'D+'),
            ('MATH201', 50.0, 'D')
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        with patch('tkinter.simpledialog.askstring', return_value='student001'):
            manager.student_risk_assessment()

        cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_early_warning_system(self, mock_get_conn, mock_app):
        """Test early warning system"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('student001', 'John Doe', 55.0, 2.0, 3, 'CS101'),
            ('student002', 'Jane Smith', 50.0, 1.8, 5, 'MATH201')
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        manager.early_warning_system()

        cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_dropout_risk_analysis(self, mock_get_conn, mock_app):
        """Test dropout risk analysis"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('student001', 'John Doe', 45.0, 1.5, 8),
            ('student002', 'Jane Smith', 40.0, 1.2, 10)
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        manager.dropout_risk_analysis()

        cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.plt')
    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_generate_performance_dashboard(self, mock_get_conn, mock_plt, mock_app):
        """Test generating performance dashboard with charts"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('A+', 5),
            ('A', 10),
            ('B', 20)
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        # Only test if matplotlib is available
        if mock_plt is not None:
            manager.generate_performance_dashboard()
            cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_compare_course_performance(self, mock_get_conn, mock_app):
        """Test comparing course performance"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('CS101', 75.5, 3.0, 30),
            ('CS102', 70.2, 2.8, 28),
            ('CS201', 78.0, 3.2, 25)
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        manager.compare_course_performance()

        cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_analyze_performance_trends(self, mock_get_conn, mock_app):
        """Test analyzing performance trends over time"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('2024-01', 75.0),
            ('2024-02', 77.0),
            ('2024-03', 73.0),
            ('2024-04', 80.0)
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        manager.analyze_performance_trends()

        cursor.execute.assert_called()

    def test_create_reports_content(self, mock_app):
        """Test creating reports content"""
        manager = AnalyticsManager(mock_app)
        manager.create_reports_content()

        assert hasattr(manager, 'notebook')

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_intervention_recommendations(self, mock_get_conn, mock_app):
        """Test generating intervention recommendations"""
        conn = Mock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            ('student001', 'John Doe', 45.0, 1.5, 'CS101', 'Low grades'),
            ('student002', 'Jane Smith', 50.0, 1.8, 'MATH201', 'Missing assignments')
        ]
        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        manager.intervention_recommendations()

        cursor.execute.assert_called()

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_database_error_handling(self, mock_get_conn, mock_app):
        """Test handling database errors gracefully"""
        mock_get_conn.side_effect = sqlite3.Error("Database connection failed")

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        # Should not raise exception
        with patch('tkinter.messagebox.showerror'):
            manager.identify_at_risk_students()


class TestAnalyticsIntegration:
    """Integration tests for analytics features"""

    @patch('university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.get_connection')
    def test_full_analytics_workflow(self, mock_get_conn, mock_app):
        """Test complete analytics workflow"""
        conn = Mock()
        cursor = Mock()

        # Set up various return values for different queries
        cursor.fetchall.side_effect = [
            # At-risk students
            [('student001', 'John Doe', 55.0, 2.1, 'CS101')],
            # Grade distribution
            [('A', 10), ('B', 20), ('C', 15)],
            # Module performance
            [('CS101', 'Intro to CS', 75.0, 30)]
        ]

        conn.cursor.return_value = cursor
        mock_get_conn.return_value.__enter__.return_value = conn

        manager = AnalyticsManager(mock_app)
        manager.create_analytics_content()

        # Run multiple analytics functions
        manager.identify_at_risk_students()
        manager.show_grade_distribution()
        manager.analyze_module_performance()

        # Verify multiple database calls were made
        assert cursor.execute.call_count >= 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
