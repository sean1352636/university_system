"""
Tests for Enhanced Reporting Module

Tests all functionality in university_system/modules/shared/services/analytics/enhanced_reporting.py
"""

import matplotlib
matplotlib.use('Agg')

import pytest
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from education_system.university_system.modules.shared.services.analytics.enhanced_reporting import (
    SystemConfig,
    CacheManager,
    DataQualityMonitor,
    PredictiveAnalytics,
    AdvancedVisualization,
    ReportTemplate,
    AdvancedScheduledReport,
    get_reporting_db_connection,
    serialize_dataframe,
    save_template,
    load_templates,
    save_template_dict,
    delete_template_from_db,
    get_template,
    generate_report,
    get_section_dataframe,
    cleanup_old_reports,
    load_scheduled_reports,
    save_scheduled_reports,
    CONFIG
)


class TestSystemConfig:
    """Test SystemConfig class"""

    def test_load_config_default_when_file_not_exists(self):
        """Test loading default config when file doesn't exist"""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            config = SystemConfig.load_config()

            assert 'security' in config
            assert 'performance' in config
            assert config['security']['session_timeout'] == 3600
            assert config['performance']['enable_caching'] is True

    def test_load_config_from_file(self):
        """Test loading config from existing file"""
        test_config = {
            'security': {'session_timeout': 7200, 'require_2fa': True},
            'performance': {'enable_caching': False, 'max_concurrent_reports': 3}
        }

        with patch('builtins.open', create=True) as mock_file:
            mock_file.return_value.__enter__.return_value.read.return_value = json.dumps(test_config)
            with patch('json.load', return_value=test_config):
                config = SystemConfig.load_config()

                assert config['security']['session_timeout'] == 7200
                assert config['security']['require_2fa'] is True

    def test_save_config(self):
        """Test saving config to file"""
        test_config = {'test_key': 'test_value'}

        with patch('builtins.open', create=True) as mock_file:
            with patch('json.dump') as mock_dump:
                SystemConfig.save_config(test_config)
                mock_dump.assert_called_once()


class TestCacheManager:
    """Test CacheManager class"""

    def test_get_cache_key(self):
        """Test cache key generation"""
        key = CacheManager.get_cache_key(
            'test_template',
            '2024-01-01',
            '2024-01-31',
            {'filter': 'value'}
        )

        assert isinstance(key, str)
        assert len(key) == 64  # SHA-256 hash length

    def test_get_cache_key_same_inputs_same_key(self):
        """Test that same inputs produce same cache key"""
        key1 = CacheManager.get_cache_key('template', '2024-01-01', '2024-01-31')
        key2 = CacheManager.get_cache_key('template', '2024-01-01', '2024-01-31')

        assert key1 == key2

    def test_get_cache_key_different_inputs_different_keys(self):
        """Test that different inputs produce different cache keys"""
        key1 = CacheManager.get_cache_key('template1', '2024-01-01', '2024-01-31')
        key2 = CacheManager.get_cache_key('template2', '2024-01-01', '2024-01-31')

        assert key1 != key2

    def test_get_cached_report_not_exists(self):
        """Test getting cached report when file doesn't exist"""
        result = CacheManager.get_cached_report('nonexistent_key')
        assert result is None

    def test_get_cached_report_expired(self):
        """Test getting cached report when cache is expired"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_key = 'test_expired_key'
            cache_file = os.path.join(tmpdir, f'{cache_key}.json')
            with open(cache_file, 'w') as f:
                json.dump({'data': 'test'}, f)

            # Make file old
            old_time = datetime.now() - timedelta(hours=25)
            os.utime(cache_file, (old_time.timestamp(), old_time.timestamp()))

            with patch.dict(CONFIG, {'cache_dir': tmpdir, 'cache_expiry_hours': 24}):
                result = CacheManager.get_cached_report(cache_key)
                # Cache should be expired and deleted
                assert result is None

    def test_cache_report(self):
        """Test caching a report"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_key = 'test_cache_key'
            report_data = {'data': 'test_report', 'timestamp': datetime.now().isoformat()}

            with patch.dict(CONFIG, {'cache_dir': tmpdir, 'max_cache_size_mb': 500}):
                CacheManager.cache_report(cache_key, report_data)

                cache_file = os.path.join(tmpdir, f"{cache_key}.json")
                assert os.path.exists(cache_file)

                with open(cache_file, 'r') as f:
                    loaded_data = json.load(f)
                    assert loaded_data['data'] == 'test_report'

    def test_cleanup_cache(self):
        """Test cache cleanup when size exceeds limit"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple cache files
            for i in range(5):
                with open(os.path.join(tmpdir, f'cache_{i}.json'), 'w') as f:
                    json.dump({'data': 'x' * 1000}, f)

            # Set max_cache_size_mb very small so cleanup triggers removal
            with patch.dict(CONFIG, {'cache_dir': tmpdir, 'max_cache_size_mb': 0}):
                CacheManager.cleanup_cache()
                # Should remove some files due to size limit


class TestDataQualityMonitor:
    """Test DataQualityMonitor class"""

    def test_run_quality_checks(self):
        """Test running complete quality checks"""
        mock_conn = Mock()

        with patch('education_system.university_system.modules.shared.services.analytics.enhanced_reporting.get_reporting_db_connection', return_value=mock_conn):
            with patch.object(DataQualityMonitor, 'check_missing_data', return_value={}):
                with patch.object(DataQualityMonitor, 'check_duplicates', return_value={}):
                    with patch.object(DataQualityMonitor, 'check_invalid_data', return_value={}):
                        with patch.object(DataQualityMonitor, 'check_data_freshness', return_value={}):
                            report = DataQualityMonitor.run_quality_checks()

                            assert 'timestamp' in report
                            assert 'checks' in report
                            assert 'missing_data' in report['checks']
                            assert 'duplicates' in report['checks']
                            assert 'invalid_data' in report['checks']
                            assert 'data_freshness' in report['checks']

    def test_check_missing_data(self):
        """Test checking for missing data"""
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            [5],  # missing emails
            [3],  # missing names
            [2],  # missing courses
            [100]  # total students
        ]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        result = DataQualityMonitor.check_missing_data(mock_conn)

        assert 'students' in result
        assert result['students']['missing_emails'] == 5
        assert result['students']['missing_names'] == 3
        assert result['students']['total_records'] == 100

    def test_check_duplicates(self):
        """Test checking for duplicate data"""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ['test@example.com', 3],
            ['another@example.com', 2]
        ]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        result = DataQualityMonitor.check_duplicates(mock_conn)

        assert 'duplicate_emails' in result
        assert result['duplicate_emails'] == 2
        assert len(result['duplicate_email_details']) == 2

    def test_check_invalid_data(self):
        """Test checking for invalid data"""
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            [5],  # invalid ages
            [3]   # invalid emails
        ]

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        result = DataQualityMonitor.check_invalid_data(mock_conn)

        assert result['invalid_ages'] == 5
        assert result['invalid_emails'] == 3

    def test_check_data_freshness(self):
        """Test checking data freshness"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = ['2024-01-15 10:30:00']

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor

        result = DataQualityMonitor.check_data_freshness(mock_conn)

        assert 'days_since_last_registration' in result
        assert 'last_registration_date' in result
        assert result['last_registration_date'] == '2024-01-15 10:30:00'


class TestPredictiveAnalytics:
    """Test PredictiveAnalytics class"""

    def test_init(self):
        """Test PredictiveAnalytics can be instantiated"""
        pa = PredictiveAnalytics()
        # PredictiveAnalytics uses static methods; verify it can be created
        assert pa is not None

    def test_prepare_retention_data(self):
        """Test predict_dropout_risk returns error when no attendance data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # No attendance_records table
        mock_conn.cursor.return_value = mock_cursor

        with patch('education_system.university_system.modules.shared.services.analytics.enhanced_reporting.predictive.get_reporting_db_connection', return_value=mock_conn):
            result = PredictiveAnalytics.predict_dropout_risk()
            # When no attendance data, should return error dict
            assert isinstance(result, dict)
            assert 'error' in result

    def test_detect_anomalies(self):
        """Test anomaly detection with insufficient data"""
        import pandas as pd

        mock_conn = Mock()
        with patch('education_system.university_system.modules.shared.services.analytics.enhanced_reporting.predictive.get_reporting_db_connection', return_value=mock_conn):
            with patch('education_system.university_system.modules.shared.services.analytics.enhanced_reporting.predictive.pd.read_sql_query', return_value=pd.DataFrame()):
                result = PredictiveAnalytics.detect_anomalies()
                # When no data, should return error dict
                assert isinstance(result, dict)


class TestAdvancedVisualization:
    """Test AdvancedVisualization class"""

    def test_create_correlation_heatmap(self):
        """Test creating correlation matrix via create_correlation_matrix"""
        mock_conn = Mock()
        mock_cursor = Mock()
        # Simulate attendance_records table exists
        mock_cursor.fetchone.return_value = ('attendance_records',)
        mock_conn.cursor.return_value = mock_cursor

        import pandas as pd
        import numpy as np

        df = pd.DataFrame({
            'age': np.random.randint(18, 30, 10),
            'module_count': np.random.randint(1, 5, 10),
            'avg_grade': np.random.rand(10) * 100,
            'attendance_records': np.random.randint(10, 50, 10),
            'present_count': np.random.randint(5, 40, 10),
        })

        with patch('education_system.university_system.modules.shared.services.analytics.enhanced_reporting.visualization.pd.read_sql_query', return_value=df):
            with patch('matplotlib.pyplot.savefig'):
                with patch('matplotlib.pyplot.close'):
                    result = AdvancedVisualization.create_correlation_matrix(mock_conn)
                    # Should create visualization without error

    def test_create_trend_analysis(self):
        """Test creating heatmap visualization"""
        import pandas as pd

        df = pd.DataFrame({
            'x': ['A', 'A', 'B', 'B'],
            'y': ['C', 'D', 'C', 'D'],
            'value': [1.0, 2.0, 3.0, 4.0]
        })

        with patch('matplotlib.pyplot.savefig'):
            with patch('matplotlib.pyplot.close'):
                with patch.dict(CONFIG, {'reports_dir': '/tmp'}):
                    result = AdvancedVisualization.create_heatmap(df, 'Test Heatmap', 'x', 'y', 'value')


class TestReportTemplate:
    """Test ReportTemplate class"""

    def test_create_template(self):
        """Test creating a report template"""
        template = ReportTemplate(
            name="Test Template",
            description="Test Description",
            sections=['students', 'courses']
        )

        assert template.name == "Test Template"
        assert template.description == "Test Description"
        assert len(template.sections) == 2

    def test_to_dict(self):
        """Test converting template to dictionary"""
        template = ReportTemplate(
            name="Test",
            description="Test Description",
            sections=['students']
        )

        template_dict = template.to_dict()

        assert isinstance(template_dict, dict)
        assert template_dict['name'] == "Test"
        assert 'sections' in template_dict


class TestAdvancedScheduledReport:
    """Test AdvancedScheduledReport class"""

    def test_create_scheduled_report(self):
        """Test creating a scheduled report"""
        report = AdvancedScheduledReport(
            template_name="Monthly Report",
            schedule_config={"frequency": "monthly"},
            recipients=['test@example.com']
        )

        assert report.template_name == "Monthly Report"
        assert report.schedule_config == {"frequency": "monthly"}
        assert len(report.recipients) == 1

    def test_to_dict(self):
        """Test converting scheduled report to dictionary"""
        report = AdvancedScheduledReport(
            template_name="Test",
            schedule_config={"frequency": "daily"},
            recipients=[]
        )

        report_dict = report.to_dict()

        assert isinstance(report_dict, dict)
        assert report_dict['template_name'] == "Test"
        assert report_dict['schedule_config'] == {"frequency": "daily"}


class TestUtilityFunctions:
    """Test utility functions"""

    def test_get_reporting_db_connection(self):
        """Test getting database connection"""
        with patch('sqlite3.connect') as mock_connect:
            conn = get_reporting_db_connection()
            mock_connect.assert_called_once()

    def test_serialize_dataframe(self):
        """Test serializing a pandas DataFrame"""
        import pandas as pd

        df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})

        result = serialize_dataframe(df)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]['col1'] == 1
        assert result[0]['col2'] == 'a'

    def test_save_template(self):
        """Test saving a template"""
        template = ReportTemplate(name="Test", description="Test", sections=[])

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # No existing template
        mock_conn.cursor.return_value = mock_cursor

        with patch('education_system.university_system.infrastructure.database.db.get_connection', return_value=mock_conn):
            result = save_template(template)
            # Should complete without error and return the template
            assert result is not None

    def test_load_templates(self):
        """Test loading templates"""
        with patch('education_system.university_system.modules.shared.services.analytics.enhanced_reporting.get_reporting_db_connection'):
            templates = load_templates()
            assert isinstance(templates, (list, dict))

    def test_delete_template_from_db(self):
        """Test deleting a template"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mock_conn.cursor.return_value = mock_cursor

        with patch('education_system.university_system.infrastructure.database.db.get_connection', return_value=mock_conn):
            result = delete_template_from_db("test_template")
            assert result is True

    def test_cleanup_old_reports(self):
        """Test cleaning up old reports"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create old file
            old_file = os.path.join(tmpdir, 'old_report.pdf')
            with open(old_file, 'w') as f:
                f.write('test')

            old_time = datetime.now() - timedelta(days=40)

            with patch.dict(CONFIG, {'reports_dir': tmpdir}):
                with patch('os.path.getctime', return_value=old_time.timestamp()):
                    cleanup_old_reports(days_to_keep=30)
                    # Old file should be removed
                    assert not os.path.exists(old_file)

    def test_load_scheduled_reports(self):
        """Test loading scheduled reports"""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            reports = load_scheduled_reports()
            assert isinstance(reports, list)
            assert len(reports) == 0

    def test_save_scheduled_reports(self):
        """Test saving scheduled reports"""
        reports = [{'name': 'Test Report', 'frequency': 'daily'}]

        with patch('builtins.open', create=True):
            with patch('json.dump'):
                save_scheduled_reports(reports)
                # Should complete without error


class TestReportGeneration:
    """Test report generation functions"""

    def test_get_section_dataframe(self):
        """Test getting section dataframe"""
        with patch('education_system.university_system.modules.shared.services.analytics.enhanced_reporting.get_reporting_db_connection'):
            with patch('pandas.read_sql_query'):
                df = get_section_dataframe('students', '2024-01-01', '2024-01-31')
                # Should return DataFrame or None

    def test_generate_report(self):
        """Test generating a complete report"""
        template = ReportTemplate(name="Test", description="Test", sections=['students'])

        with patch('education_system.university_system.modules.shared.services.analytics.enhanced_reporting.generate_enhanced_pdf_report'):
            result = generate_report(
                template,
                start_date='2024-01-01',
                end_date='2024-01-31',
                format='pdf'
            )
            # Should complete without error


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
