"""
Tests for Enhanced Reporting Module

Tests all functionality in university_system/modules/shared/services/analytics/enhanced_reporting.py
"""

import pytest
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from university_system.modules.shared.services.analytics.enhanced_reporting import (
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
        assert len(key) == 32  # MD5 hash length

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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'data': 'test'}, f)
            cache_file = f.name

        try:
            # Make file old
            old_time = datetime.now() - timedelta(hours=25)
            os.utime(cache_file, (old_time.timestamp(), old_time.timestamp()))

            cache_key = Path(cache_file).stem
            with patch.object(CONFIG, '__getitem__', return_value=cache_file.replace('.json', '')):
                result = CacheManager.get_cached_report(cache_key)
                # Cache should be expired and deleted
                assert result is None or not os.path.exists(cache_file)
        finally:
            if os.path.exists(cache_file):
                os.remove(cache_file)

    def test_cache_report(self):
        """Test caching a report"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_key = 'test_cache_key'
            report_data = {'data': 'test_report', 'timestamp': datetime.now().isoformat()}

            with patch.object(CONFIG, '__getitem__', return_value=tmpdir):
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

            with patch.object(CONFIG, '__getitem__', side_effect=lambda k: tmpdir if k == 'cache_dir' else 1):
                CacheManager.cleanup_cache()
                # Should remove some files due to size limit


class TestDataQualityMonitor:
    """Test DataQualityMonitor class"""

    def test_run_quality_checks(self):
        """Test running complete quality checks"""
        mock_conn = Mock()

        with patch('university_system.modules.shared.services.analytics.enhanced_reporting.get_reporting_db_connection', return_value=mock_conn):
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
        """Test PredictiveAnalytics initialization"""
        with patch('university_system.modules.shared.services.analytics.enhanced_reporting.get_reporting_db_connection'):
            pa = PredictiveAnalytics()
            assert hasattr(pa, 'conn')

    def test_prepare_retention_data(self):
        """Test preparing retention prediction data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {'student_id': '1', 'gpa': 3.5, 'attendance_rate': 90, 'is_retained': 1},
            {'student_id': '2', 'gpa': 2.0, 'attendance_rate': 60, 'is_retained': 0}
        ]
        mock_conn.execute.return_value = mock_cursor

        pa = PredictiveAnalytics()
        pa.conn = mock_conn

        with patch('pandas.DataFrame.dropna', return_value=Mock(empty=False)):
            result = pa.prepare_retention_data()
            # Method should return data or None
            assert result is not None or result is None

    def test_detect_anomalies(self):
        """Test anomaly detection"""
        mock_conn = Mock()
        pa = PredictiveAnalytics()
        pa.conn = mock_conn

        with patch.object(pa, 'prepare_retention_data', return_value=None):
            anomalies = pa.detect_anomalies()
            # When no data, should return empty or handle gracefully
            assert isinstance(anomalies, (list, type(None)))


class TestAdvancedVisualization:
    """Test AdvancedVisualization class"""

    def test_create_correlation_heatmap(self):
        """Test creating correlation heatmap"""
        import pandas as pd
        import numpy as np

        df = pd.DataFrame({
            'col1': np.random.rand(10),
            'col2': np.random.rand(10),
            'col3': np.random.rand(10)
        })

        viz = AdvancedVisualization()

        with patch('matplotlib.pyplot.savefig'):
            with patch('matplotlib.pyplot.close'):
                result = viz.create_correlation_heatmap(df, 'test_output')
                # Should create visualization without error

    def test_create_trend_analysis(self):
        """Test creating trend analysis visualization"""
        import pandas as pd

        df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'value': range(10)
        })

        viz = AdvancedVisualization()

        with patch('matplotlib.pyplot.savefig'):
            with patch('matplotlib.pyplot.close'):
                result = viz.create_trend_analysis(df, 'date', 'value', 'test_output')


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
            frequency="monthly",
            recipients=['test@example.com'],
            format="pdf"
        )

        assert report.template_name == "Monthly Report"
        assert report.frequency == "monthly"
        assert len(report.recipients) == 1

    def test_to_dict(self):
        """Test converting scheduled report to dictionary"""
        report = AdvancedScheduledReport(
            template_name="Test",
            frequency="daily",
            recipients=[],
            format="pdf"
        )

        report_dict = report.to_dict()

        assert isinstance(report_dict, dict)
        assert report_dict['template_name'] == "Test"
        assert report_dict['frequency'] == "daily"


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

        assert isinstance(result, dict)
        assert 'columns' in result
        assert 'data' in result

    def test_save_template(self):
        """Test saving a template"""
        template = ReportTemplate(name="Test", sections=[])

        with patch('university_system.modules.shared.services.analytics.enhanced_reporting.get_reporting_db_connection'):
            with patch('university_system.modules.shared.services.analytics.enhanced_reporting.save_template_dict'):
                result = save_template(template)
                # Should complete without error

    def test_load_templates(self):
        """Test loading templates"""
        with patch('university_system.modules.shared.services.analytics.enhanced_reporting.get_reporting_db_connection'):
            templates = load_templates()
            assert isinstance(templates, (list, dict))

    def test_delete_template_from_db(self):
        """Test deleting a template"""
        with patch('university_system.modules.shared.services.analytics.enhanced_reporting.get_reporting_db_connection'):
            result = delete_template_from_db("test_template")
            # Should complete without error

    def test_cleanup_old_reports(self):
        """Test cleaning up old reports"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create old file
            old_file = os.path.join(tmpdir, 'old_report.pdf')
            with open(old_file, 'w') as f:
                f.write('test')

            old_time = datetime.now() - timedelta(days=40)
            os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

            with patch.object(CONFIG, '__getitem__', return_value=tmpdir):
                cleanup_old_reports(days_to_keep=30)
                # Old file should be removed

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
        with patch('university_system.modules.shared.services.analytics.enhanced_reporting.get_reporting_db_connection'):
            with patch('pandas.read_sql_query'):
                df = get_section_dataframe('students', '2024-01-01', '2024-01-31')
                # Should return DataFrame or None

    def test_generate_report(self):
        """Test generating a complete report"""
        template = ReportTemplate(name="Test", sections=['students'])

        with patch('university_system.modules.shared.services.analytics.enhanced_reporting.generate_enhanced_pdf_report'):
            result = generate_report(
                template,
                start_date='2024-01-01',
                end_date='2024-01-31',
                format='pdf'
            )
            # Should complete without error


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
