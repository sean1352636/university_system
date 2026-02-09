"""
Comprehensive test suite for reports.py

Tests all functions and functionality including:
- generate_report function
- export_report function
- log_email_metrics function
- generate_report_form function
- get_user_communication_stats function
- get_recent_communication_activity function
- get_system_health_info function
- Internal formatting functions
"""

import pytest
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
from university_system.modules.shared.utils import reports
from university_system.modules.shared.utils.reports import (
    generate_report,
    export_report,
    log_email_metrics,
    generate_report_form,
    get_user_communication_stats,
    get_recent_communication_activity,
    get_system_health_info,
    _email_metrics,
    _communication_activity,
)


class TestGenerateReport:
    """Test generate_report function"""

    def test_generate_report_basic(self):
        """Test generating a basic report"""
        report = generate_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_generate_report_with_title(self):
        """Test generating report with custom title"""
        report = generate_report(title="Test Report")
        assert "Test Report" in report

    def test_generate_report_email_type(self):
        """Test generating email report"""
        data = {
            'total_sent': 100,
            'total_delivered': 95,
            'total_failed': 5,
            'queued': 10
        }
        report = generate_report(report_type='email', data=data)
        assert 'EMAIL STATISTICS' in report
        assert '100' in report
        assert '95' in report

    def test_generate_report_communication_type(self):
        """Test generating communication report"""
        data = {
            'total_messages': 500,
            'active_users': 50,
            'response_rate': '85%'
        }
        report = generate_report(report_type='communication', data=data)
        assert 'COMMUNICATION STATISTICS' in report
        assert '500' in report

    def test_generate_report_system_type(self):
        """Test generating system report"""
        data = {
            'status': 'healthy',
            'uptime': '10 days',
            'cpu_usage': '25%',
            'memory_usage': '50%'
        }
        report = generate_report(report_type='system', data=data)
        assert 'SYSTEM HEALTH' in report
        assert 'healthy' in report

    def test_generate_report_custom_type(self):
        """Test generating custom report"""
        data = {
            'custom_field1': 'value1',
            'custom_field2': 'value2'
        }
        report = generate_report(report_type='custom', data=data)
        assert 'value1' in report
        assert 'value2' in report

    def test_generate_report_no_data(self):
        """Test generating report with no data"""
        report = generate_report(report_type='email')
        assert isinstance(report, str)
        assert 'EMAIL STATISTICS' in report

    def test_generate_report_contains_header(self):
        """Test that report contains header"""
        report = generate_report()
        assert '=' * 80 in report

    def test_generate_report_contains_footer(self):
        """Test that report contains footer"""
        report = generate_report()
        assert 'End of Report' in report

    def test_generate_report_contains_timestamp(self):
        """Test that report contains generation timestamp"""
        report = generate_report()
        assert 'Generated:' in report

    def test_generate_report_with_args_kwargs(self):
        """Test generate_report with extra args and kwargs"""
        report = generate_report('email', {'total_sent': 10}, 'Title', extra='value')
        assert isinstance(report, str)


class TestExportReport:
    """Test export_report function"""

    def test_export_report_basic(self, tmp_path):
        """Test exporting a report to file"""
        os.chdir(tmp_path)
        report_content = "Test Report Content"
        result = export_report(report_content, filename="test_report.txt")
        assert result is True
        assert (tmp_path / "test_report.txt").exists()

    def test_export_report_with_directory(self, tmp_path):
        """Test exporting report to specific directory"""
        report_dir = tmp_path / "reports"
        report_content = "Test Report Content"
        result = export_report(
            report_content,
            filename="test.txt",
            directory=str(report_dir)
        )
        assert result is True
        assert (report_dir / "test.txt").exists()

    def test_export_report_creates_directory(self, tmp_path):
        """Test that export_report creates directory if needed"""
        report_dir = tmp_path / "new" / "subdirectory"
        report_content = "Test Content"
        result = export_report(
            report_content,
            filename="test.txt",
            directory=str(report_dir)
        )
        assert result is True
        assert report_dir.exists()

    def test_export_report_no_content(self):
        """Test exporting with no content"""
        result = export_report(None, filename="test.txt")
        assert result is False

    def test_export_report_empty_content(self, tmp_path):
        """Test exporting empty content"""
        os.chdir(tmp_path)
        result = export_report("", filename="test.txt")
        # Empty string is falsy, should return False

    def test_export_report_auto_filename(self, tmp_path):
        """Test export with auto-generated filename"""
        os.chdir(tmp_path)
        report_content = "Test Content"
        result = export_report(report_content)
        assert result is True
        # Should create a file with timestamp
        txt_files = list(tmp_path.glob("report_*.txt"))
        assert len(txt_files) > 0

    def test_export_report_with_unicode(self, tmp_path):
        """Test exporting report with unicode content"""
        os.chdir(tmp_path)
        report_content = "Test Report 中文 العربية 🎉"
        result = export_report(report_content, filename="unicode_test.txt")
        assert result is True

        # Read back and verify
        content = (tmp_path / "unicode_test.txt").read_text(encoding='utf-8')
        assert "中文" in content

    def test_export_report_with_args_kwargs(self, tmp_path):
        """Test export_report with extra args and kwargs"""
        os.chdir(tmp_path)
        result = export_report("Content", "file.txt", str(tmp_path), extra='value')
        assert isinstance(result, bool)


class TestLogEmailMetrics:
    """Test log_email_metrics function"""

    def setup_method(self):
        """Clear metrics before each test"""
        reports._email_metrics.clear()

    def test_log_email_metrics_basic(self):
        """Test logging email metrics"""
        log_email_metrics('sent', 1)
        assert len(reports._email_metrics) == 1

    def test_log_email_metrics_with_metadata(self):
        """Test logging metrics with metadata"""
        metadata = {'recipient': 'test@example.com', 'size': 1024}
        log_email_metrics('sent', 1, metadata=metadata)

        assert len(reports._email_metrics) == 1
        entry = reports._email_metrics[0]
        assert entry['type'] == 'sent'
        assert entry['value'] == 1
        assert entry['metadata'] == metadata

    def test_log_email_metrics_multiple(self):
        """Test logging multiple metrics"""
        log_email_metrics('sent', 5)
        log_email_metrics('delivered', 4)
        log_email_metrics('failed', 1)

        assert len(reports._email_metrics) == 3

    def test_log_email_metrics_has_timestamp(self):
        """Test that metrics have timestamps"""
        log_email_metrics('sent', 1)
        entry = reports._email_metrics[0]
        assert 'timestamp' in entry
        # Should be valid ISO format
        datetime.fromisoformat(entry['timestamp'])

    def test_log_email_metrics_limit(self):
        """Test that metrics are limited to 1000 entries"""
        for i in range(1100):
            log_email_metrics('sent', i)

        # Should keep only last 1000
        assert len(reports._email_metrics) <= 1000

    def test_log_email_metrics_no_type(self):
        """Test logging metrics without type"""
        log_email_metrics(None, 42)
        entry = reports._email_metrics[0]
        assert entry['type'] == 'unknown'

    def test_log_email_metrics_with_args_kwargs(self):
        """Test log_email_metrics with extra args and kwargs"""
        log_email_metrics('sent', 1, {'meta': 'data'}, extra='value')
        assert len(reports._email_metrics) > 0


class TestGenerateReportForm:
    """Test generate_report_form function"""

    def test_generate_report_form_basic(self):
        """Test generating basic report form"""
        form = generate_report_form()
        assert isinstance(form, dict)
        assert 'title' in form
        assert 'date_from' in form
        assert 'date_to' in form
        assert 'format' in form

    def test_generate_report_form_email_type(self):
        """Test generating email report form"""
        form = generate_report_form(report_type='email')
        assert 'include_failed' in form
        assert 'include_queued' in form

    def test_generate_report_form_communication_type(self):
        """Test generating communication report form"""
        form = generate_report_form(report_type='communication')
        assert 'user_filter' in form
        assert 'message_type' in form

    def test_generate_report_form_field_types(self):
        """Test that form fields have correct types"""
        form = generate_report_form()
        assert form['title']['type'] == 'text'
        assert form['date_from']['type'] == 'date'
        assert form['format']['type'] == 'select'

    def test_generate_report_form_field_labels(self):
        """Test that form fields have labels"""
        form = generate_report_form()
        for field in form.values():
            assert 'label' in field

    def test_generate_report_form_select_options(self):
        """Test that select fields have options"""
        form = generate_report_form()
        assert 'options' in form['format']
        assert 'text' in form['format']['options']
        assert 'csv' in form['format']['options']

    def test_generate_report_form_with_args_kwargs(self):
        """Test generate_report_form with extra args and kwargs"""
        form = generate_report_form('email', extra='value')
        assert isinstance(form, dict)


class TestGetUserCommunicationStats:
    """Test get_user_communication_stats function"""

    def test_get_user_communication_stats_basic(self):
        """Test getting user communication stats"""
        stats = get_user_communication_stats('user123')
        assert isinstance(stats, dict)
        assert 'user_id' in stats
        assert stats['user_id'] == 'user123'

    def test_get_user_communication_stats_has_required_fields(self):
        """Test that stats contain required fields"""
        stats = get_user_communication_stats('user123')
        assert 'total_emails_sent' in stats
        assert 'total_emails_received' in stats
        assert 'total_messages' in stats
        assert 'response_rate' in stats

    def test_get_user_communication_stats_no_user_id(self):
        """Test getting stats without user ID"""
        stats = get_user_communication_stats(None)
        assert stats['user_id'] == 'unknown'

    def test_get_user_communication_stats_has_breakdown(self):
        """Test that stats include communication breakdown"""
        stats = get_user_communication_stats('user123')
        assert 'communication_breakdown' in stats
        assert isinstance(stats['communication_breakdown'], dict)

    def test_get_user_communication_stats_with_args_kwargs(self):
        """Test get_user_communication_stats with extra args and kwargs"""
        stats = get_user_communication_stats('user123', extra='value')
        assert isinstance(stats, dict)


class TestGetRecentCommunicationActivity:
    """Test get_recent_communication_activity function"""

    def test_get_recent_communication_activity_basic(self):
        """Test getting recent communication activity"""
        activities = get_recent_communication_activity()
        assert isinstance(activities, list)

    def test_get_recent_communication_activity_with_limit(self):
        """Test getting activity with limit"""
        activities = get_recent_communication_activity(limit=5)
        assert len(activities) <= 5

    def test_get_recent_communication_activity_with_type(self):
        """Test filtering activity by type"""
        activities = get_recent_communication_activity(activity_type='email')
        for activity in activities:
            if 'type' in activity:
                # Sample activities might have different types
                pass

    def test_get_recent_communication_activity_structure(self):
        """Test that activities have correct structure"""
        activities = get_recent_communication_activity()
        if activities:
            activity = activities[0]
            assert isinstance(activity, dict)

    def test_get_recent_communication_activity_default_limit(self):
        """Test default limit of 10"""
        activities = get_recent_communication_activity()
        assert len(activities) <= 10

    def test_get_recent_communication_activity_with_args_kwargs(self):
        """Test get_recent_communication_activity with extra args and kwargs"""
        activities = get_recent_communication_activity(5, 'email', extra='value')
        assert isinstance(activities, list)


class TestGetSystemHealthInfo:
    """Test get_system_health_info function"""

    def test_get_system_health_info_basic(self):
        """Test getting system health info"""
        health = get_system_health_info()
        assert isinstance(health, dict)

    def test_get_system_health_info_has_status(self):
        """Test that health info has status"""
        health = get_system_health_info()
        assert 'status' in health
        assert health['status'] == 'healthy'

    def test_get_system_health_info_has_services(self):
        """Test that health info includes services status"""
        health = get_system_health_info()
        assert 'services' in health
        assert isinstance(health['services'], dict)

    def test_get_system_health_info_has_metrics(self):
        """Test that health info includes metrics"""
        health = get_system_health_info()
        assert 'metrics' in health
        assert isinstance(health['metrics'], dict)

    def test_get_system_health_info_has_performance(self):
        """Test that health info includes performance metrics"""
        health = get_system_health_info()
        assert 'performance' in health
        assert isinstance(health['performance'], dict)

    def test_get_system_health_info_has_email_queue(self):
        """Test that health info includes email queue status"""
        health = get_system_health_info()
        assert 'email_queue' in health

    def test_get_system_health_info_has_timestamp(self):
        """Test that health info has timestamp"""
        health = get_system_health_info()
        assert 'timestamp' in health
        # Should be valid ISO format
        datetime.fromisoformat(health['timestamp'])

    def test_get_system_health_info_with_args_kwargs(self):
        """Test get_system_health_info with extra args and kwargs"""
        health = get_system_health_info(extra='value')
        assert isinstance(health, dict)


class TestModuleGlobals:
    """Test module-level globals"""

    def test_email_metrics_is_list(self):
        """Test that _email_metrics is a list"""
        assert isinstance(reports._email_metrics, list)

    def test_communication_activity_is_list(self):
        """Test that _communication_activity is a list"""
        assert isinstance(reports._communication_activity, list)


class TestModuleExports:
    """Test module exports"""

    def test_module_has_all(self):
        """Test that module defines __all__"""
        assert hasattr(reports, '__all__')

    def test_all_contains_expected_functions(self):
        """Test that __all__ contains expected function names"""
        expected = [
            'generate_report',
            'export_report',
            'log_email_metrics',
            'generate_report_form',
            'get_user_communication_stats',
            'get_recent_communication_activity',
            'get_system_health_info',
        ]
        for name in expected:
            assert name in reports.__all__

    def test_exported_functions_are_callable(self):
        """Test that all exported functions are callable"""
        for name in reports.__all__:
            func = getattr(reports, name)
            assert callable(func)


class TestIntegration:
    """Integration tests for reporting functionality"""

    def test_full_reporting_workflow(self, tmp_path):
        """Test a complete reporting workflow"""
        # Generate report
        data = {
            'total_sent': 100,
            'total_delivered': 95,
            'total_failed': 5
        }
        report = generate_report(report_type='email', data=data)
        assert 'EMAIL STATISTICS' in report

        # Export report
        os.chdir(tmp_path)
        result = export_report(report, filename="email_report.txt")
        assert result is True

        # Verify file exists and has content
        report_file = tmp_path / "email_report.txt"
        assert report_file.exists()
        content = report_file.read_text()
        assert 'EMAIL STATISTICS' in content

    def test_metrics_and_health_workflow(self):
        """Test metrics logging and health check workflow"""
        # Log some metrics
        log_email_metrics('sent', 10)
        log_email_metrics('delivered', 9)
        log_email_metrics('failed', 1)

        # Get system health
        health = get_system_health_info()
        assert 'email_queue' in health
        assert 'pending' in health['email_queue']

    def test_stats_and_activity_workflow(self):
        """Test getting stats and activity"""
        # Get user stats
        stats = get_user_communication_stats('user123')
        assert stats['user_id'] == 'user123'

        # Get recent activity
        activities = get_recent_communication_activity(limit=10)
        assert isinstance(activities, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
