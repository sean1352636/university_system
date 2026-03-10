"""
Tests for Business Intelligence Reports Core Module

Tests all functionality in university_system/modules/shared/services/business_intelligence/bi_reports_core.py
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from education_system.university_system.modules.shared.services.business_intelligence.bi_reports_core import (
    ReportDefinitionManager,
    ReportExportManager,
    ReportScheduleManager,
    VisualizationManager,
    CustomMetricManager,
    display_business_intelligence_menu,
    launch_business_intelligence_gui
)


class TestReportDefinitionManager:
    """Test ReportDefinitionManager class"""

    def test_create_report_success(self):
        """Test creating a report definition successfully"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 123
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            report_id = ReportDefinitionManager.create_report(
                report_name="Test Report",
                report_category="Academic",
                description="Test Description",
                sql_query="SELECT * FROM students",
                data_source="students_table",
                created_by="test_user"
            )

            assert report_id == 123
            mock_conn.execute.assert_called_once()

    def test_create_report_with_minimal_params(self):
        """Test creating report with minimal parameters"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 456
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            report_id = ReportDefinitionManager.create_report(
                report_name="Minimal Report",
                report_category="Financial"
            )

            assert report_id == 456

    def test_create_report_database_error(self):
        """Test handling database error when creating report"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Database error")
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            with pytest.raises(Exception) as exc_info:
                ReportDefinitionManager.create_report(
                    report_name="Error Report",
                    report_category="Test"
                )

            assert "Error creating report" in str(exc_info.value)

    def test_create_report_sql_query_validation(self):
        """Test creating report with SQL query"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 789
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            report_id = ReportDefinitionManager.create_report(
                report_name="SQL Report",
                report_category="Custom",
                sql_query="SELECT student_id, name FROM students WHERE age > 21"
            )

            assert report_id == 789
            # Verify SQL query was passed correctly
            call_args = mock_conn.execute.call_args
            assert "SELECT student_id, name FROM students WHERE age > 21" in str(call_args)


class TestReportExportManager:
    """Test ReportExportManager class"""

    def test_export_report_success(self):
        """Test exporting a report successfully"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 101
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            export_id = ReportExportManager.export_report(
                report_id=1,
                export_format="CSV",
                file_path="/tmp/report.csv",
                generated_by="test_user",
                row_count=150
            )

            assert export_id == 101

    def test_export_report_different_formats(self):
        """Test exporting reports in different formats"""
        formats = ["CSV", "JSON", "Excel", "PDF"]

        for fmt in formats:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.lastrowid = 200
            mock_conn.execute.return_value = mock_cursor
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=False)

            with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
                export_id = ReportExportManager.export_report(
                    report_id=1,
                    export_format=fmt,
                    file_path=f"/tmp/report.{fmt.lower()}",
                    generated_by="test_user"
                )

                assert export_id == 200

    def test_export_report_database_error(self):
        """Test handling database error during export"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Export failed")
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            with pytest.raises(Exception) as exc_info:
                ReportExportManager.export_report(
                    report_id=1,
                    export_format="CSV",
                    file_path="/tmp/test.csv",
                    generated_by="test_user"
                )

            assert "Error exporting report" in str(exc_info.value)


class TestReportScheduleManager:
    """Test ReportScheduleManager class"""

    def test_create_schedule_success(self):
        """Test creating a report schedule successfully"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 301
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            schedule_id = ReportScheduleManager.create_schedule(
                report_id=1,
                schedule_name="Weekly Report",
                frequency="weekly",
                delivery_method="email",
                recipients="user@example.com",
                export_format="PDF"
            )

            assert schedule_id == 301

    def test_create_schedule_daily(self):
        """Test creating daily schedule"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 302
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            schedule_id = ReportScheduleManager.create_schedule(
                report_id=2,
                schedule_name="Daily Summary",
                frequency="daily",
                delivery_method="email",
                recipients="admin@example.com",
                export_format="CSV"
            )

            assert schedule_id == 302

    def test_create_schedule_monthly(self):
        """Test creating monthly schedule"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 303
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            schedule_id = ReportScheduleManager.create_schedule(
                report_id=3,
                schedule_name="Monthly Analytics",
                frequency="monthly",
                delivery_method="download",
                recipients="",
                export_format="Excel"
            )

            assert schedule_id == 303

    def test_create_schedule_database_error(self):
        """Test handling database error when creating schedule"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Schedule creation failed")
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            with pytest.raises(Exception) as exc_info:
                ReportScheduleManager.create_schedule(
                    report_id=1,
                    schedule_name="Error Schedule",
                    frequency="weekly",
                    delivery_method="email",
                    recipients="test@test.com",
                    export_format="PDF"
                )

            assert "Error creating schedule" in str(exc_info.value)


class TestVisualizationManager:
    """Test VisualizationManager class"""

    def test_create_visualization_success(self):
        """Test creating a visualization successfully"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 401
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            viz_id = VisualizationManager.create_visualization(
                visualization_name="Enrollment Trend",
                chart_type="line",
                data_source="enrollment_data",
                x_axis="date",
                y_axis="count",
                created_by="test_user"
            )

            assert viz_id == 401

    def test_create_visualization_bar_chart(self):
        """Test creating bar chart visualization"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 402
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            viz_id = VisualizationManager.create_visualization(
                visualization_name="Course Distribution",
                chart_type="bar",
                data_source="course_data"
            )

            assert viz_id == 402

    def test_create_visualization_pie_chart(self):
        """Test creating pie chart visualization"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 403
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            viz_id = VisualizationManager.create_visualization(
                visualization_name="Gender Breakdown",
                chart_type="pie",
                data_source="student_demographics",
                created_by="admin"
            )

            assert viz_id == 403

    def test_create_visualization_database_error(self):
        """Test handling database error when creating visualization"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Visualization creation failed")
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            with pytest.raises(Exception) as exc_info:
                VisualizationManager.create_visualization(
                    visualization_name="Error Viz",
                    chart_type="scatter",
                    data_source="test_data"
                )

            assert "Error creating visualization" in str(exc_info.value)


class TestCustomMetricManager:
    """Test CustomMetricManager class"""

    def test_define_metric_success(self):
        """Test defining a custom metric successfully"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 501
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            metric_id = CustomMetricManager.define_metric(
                metric_name="Student Success Rate",
                metric_category="Academic",
                calculation_formula="(passed_students / total_students) * 100",
                description="Percentage of students who pass their courses",
                target_value=85.0,
                created_by="test_user"
            )

            assert metric_id == 501

    def test_define_metric_financial_category(self):
        """Test defining financial metric"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 502
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            metric_id = CustomMetricManager.define_metric(
                metric_name="Revenue per Student",
                metric_category="Financial",
                calculation_formula="total_revenue / total_students",
                target_value=10000.0
            )

            assert metric_id == 502

    def test_define_metric_with_complex_formula(self):
        """Test defining metric with complex formula"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 503
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            metric_id = CustomMetricManager.define_metric(
                metric_name="Weighted GPA Average",
                metric_category="Academic",
                calculation_formula="SUM(gpa * credits) / SUM(credits)",
                description="Credit-weighted average GPA",
                target_value=3.5
            )

            assert metric_id == 503

    def test_define_metric_no_target(self):
        """Test defining metric without target value"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 504
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            metric_id = CustomMetricManager.define_metric(
                metric_name="Enrollment Trend",
                metric_category="Enrollment",
                calculation_formula="COUNT(students)"
            )

            assert metric_id == 504

    def test_define_metric_database_error(self):
        """Test handling database error when defining metric"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Metric definition failed")
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            with pytest.raises(Exception) as exc_info:
                CustomMetricManager.define_metric(
                    metric_name="Error Metric",
                    metric_category="Test",
                    calculation_formula="invalid_formula"
                )

            assert "Error defining metric" in str(exc_info.value)


class TestBusinessIntelligenceMenu:
    """Test Business Intelligence menu function"""

    def test_display_menu_exit(self):
        """Test exiting the menu"""
        with patch('builtins.input', return_value='8'):
            with patch('builtins.print'):
                display_business_intelligence_menu(None)

    def test_display_menu_create_report(self):
        """Test selecting create report option"""
        with patch('builtins.input', side_effect=['1', '8']):
            with patch('builtins.print') as mock_print:
                display_business_intelligence_menu(None)
                # Should display feature message

    def test_display_menu_export_reports(self):
        """Test selecting export reports option"""
        with patch('builtins.input', side_effect=['2', '8']):
            with patch('builtins.print'):
                display_business_intelligence_menu(None)

    def test_display_menu_schedule_reports(self):
        """Test selecting schedule reports option"""
        with patch('builtins.input', side_effect=['3', '8']):
            with patch('builtins.print'):
                display_business_intelligence_menu(None)

    def test_display_menu_visualizations(self):
        """Test selecting visualizations option"""
        with patch('builtins.input', side_effect=['4', '8']):
            with patch('builtins.print'):
                display_business_intelligence_menu(None)

    def test_display_menu_custom_metrics(self):
        """Test selecting custom metrics option"""
        with patch('builtins.input', side_effect=['5', '8']):
            with patch('builtins.print'):
                display_business_intelligence_menu(None)

    def test_display_menu_invalid_choice(self):
        """Test invalid menu choice"""
        with patch('builtins.input', side_effect=['99', '8']):
            with patch('builtins.print') as mock_print:
                display_business_intelligence_menu(None)

    def test_display_menu_keyboard_interrupt(self):
        """Test handling keyboard interrupt"""
        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            with patch('builtins.print'):
                display_business_intelligence_menu(None)

    def test_display_menu_exception_handling(self):
        """Test handling exceptions in menu"""
        with patch('builtins.input', side_effect=['1', Exception('Test error'), '8']):
            with patch('builtins.print'):
                display_business_intelligence_menu(None)


class TestLaunchBusinessIntelligenceGUI:
    """Test GUI launcher function"""

    def test_launch_gui_function_exists(self):
        """Test that launcher function exists"""
        assert callable(launch_business_intelligence_gui)

    def test_launch_gui_function_call(self):
        """Test calling the launcher function"""
        mock_root = Mock()
        mock_auth = Mock()

        with patch('builtins.print'):
            # The function uses create_gui_launcher which shows a message
            result = launch_business_intelligence_gui(mock_root, mock_auth)


class TestIntegration:
    """Integration tests for BI Reports Core"""

    def test_complete_report_workflow(self):
        """Test complete workflow: create report, export, schedule"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Simulate creating a report
        mock_cursor.lastrowid = 1
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            # Create report
            report_id = ReportDefinitionManager.create_report(
                report_name="Integration Test Report",
                report_category="Test"
            )

            # Export report
            mock_cursor.lastrowid = 1
            export_id = ReportExportManager.export_report(
                report_id=report_id,
                export_format="PDF",
                file_path="/tmp/test.pdf",
                generated_by="test_user"
            )

            # Schedule report
            mock_cursor.lastrowid = 1
            schedule_id = ReportScheduleManager.create_schedule(
                report_id=report_id,
                schedule_name="Test Schedule",
                frequency="daily",
                delivery_method="email",
                recipients="test@test.com",
                export_format="PDF"
            )

            assert report_id > 0
            assert export_id > 0
            assert schedule_id > 0

    def test_visualization_and_metric_workflow(self):
        """Test creating visualization with custom metric"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.lastrowid = 1
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        with patch('university_system.modules.shared.services.business_intelligence.bi_reports_core.transaction', return_value=mock_conn):
            # Define custom metric
            metric_id = CustomMetricManager.define_metric(
                metric_name="Test Metric",
                metric_category="Test",
                calculation_formula="SUM(value)"
            )

            # Create visualization for the metric
            mock_cursor.lastrowid = 1
            viz_id = VisualizationManager.create_visualization(
                visualization_name="Metric Visualization",
                chart_type="line",
                data_source="custom_metrics"
            )

            assert metric_id > 0
            assert viz_id > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
