"""
Comprehensive test suite for simple_activity_logger.py

Tests all classes, functions, and functionality including:
- LogLevel, OutputFormat, SecurityLevel enums
- LogEntry dataclass
- PIIDetector class
- SecurityMonitor class
- LogRotationManager class
- DatabaseManager and DatabaseLogger classes
- CloudIntegration class
- AnalyticsEngine class
- EnhancedActivityLogger class
- All plugin classes
- All helper functions
"""

import pytest
import os
import json
import tempfile
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.utils.activity_logger import (
    LogLevel,
    OutputFormat,
    SecurityLevel,
    LogEntry,
    PIIDetector,
    SecurityMonitor,
    LogRotationManager,
    DatabaseManager,
    DatabaseLogger,
    CloudIntegration,
    AnalyticsEngine,
    EnhancedActivityLogger,
    LoggerPlugin,
    PluginManager,
    SlackNotificationPlugin,
    MetricsCollectionPlugin,
    EmailNotificationPlugin,
    AuditTrailPlugin,
    enhanced_log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_admin_action,
    log_menu_navigation,
    log_activity,
    log_login,
    log_logout,
    log_dynamic_activity,
    load_logger_config,
    get_logger_instance,
    register_plugin,
    unregister_plugin,
    get_plugin_status,
    create_default_config,
)

class TestEnums:
    """Test all enum classes"""

    def test_log_level_enum(self):
        """Test LogLevel enum values"""
        assert LogLevel.DEBUG.value == 10
        assert LogLevel.INFO.value == 20
        assert LogLevel.WARNING.value == 30
        assert LogLevel.ERROR.value == 40
        assert LogLevel.CRITICAL.value == 50

    def test_output_format_enum(self):
        """Test OutputFormat enum values"""
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.CSV.value == "csv"
        assert OutputFormat.DATABASE.value == "database"
        assert OutputFormat.SYSLOG.value == "syslog"
        assert OutputFormat.CLOUD.value == "cloud"

    def test_security_level_enum(self):
        """Test SecurityLevel enum values"""
        assert SecurityLevel.LOW.value == 1
        assert SecurityLevel.MEDIUM.value == 2
        assert SecurityLevel.HIGH.value == 3
        assert SecurityLevel.CRITICAL.value == 4

class TestLogEntry:
    """Test LogEntry dataclass"""

    def test_log_entry_creation(self):
        """Test creating a LogEntry"""
        entry = LogEntry(
            timestamp="2025-01-01T12:00:00",
            user_id="user123",
            username="testuser",
            role="admin",
            action="login",
            module="auth",
            details="User logged in",
            status="success",
            log_level="INFO",
            session_id="session123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            request_size=1024,
            response_size=2048,
            processing_time=0.5,
            geolocation={"country": "US", "city": "New York"},
            security_level="LOW",
            trace_id="trace123"
        )

        assert entry.user_id == "user123"
        assert entry.username == "testuser"
        assert entry.action == "login"
        assert entry.status == "success"

    def test_log_entry_to_dict(self):
        """Test converting LogEntry to dictionary"""
        entry = LogEntry(
            timestamp="2025-01-01T12:00:00",
            user_id="user123",
            username="testuser",
            role="admin",
            action="login",
            module="auth",
            details="User logged in",
            status="success",
            log_level="INFO",
            session_id="session123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            request_size=1024,
            response_size=2048,
            processing_time=0.5,
            geolocation={"country": "US"},
            security_level="LOW",
            trace_id="trace123"
        )

        entry_dict = entry.to_dict()
        assert isinstance(entry_dict, dict)
        assert entry_dict['user_id'] == "user123"
        assert entry_dict['action'] == "login"

    def test_log_entry_to_json(self):
        """Test converting LogEntry to JSON"""
        entry = LogEntry(
            timestamp="2025-01-01T12:00:00",
            user_id="user123",
            username="testuser",
            role="admin",
            action="login",
            module="auth",
            details="User logged in",
            status="success",
            log_level="INFO",
            session_id="session123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            request_size=1024,
            response_size=2048,
            processing_time=0.5,
            geolocation={},
            security_level="LOW",
            trace_id="trace123"
        )

        json_str = entry.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed['user_id'] == "user123"

class TestPIIDetector:
    """Test PIIDetector class"""

    def test_pii_detector_initialization(self):
        """Test PIIDetector initialization"""
        detector = PIIDetector()
        assert detector is not None
        assert hasattr(detector, 'patterns')

    def test_email_pattern_detection(self):
        """Test email pattern detection"""
        detector = PIIDetector()
        test_text = "Contact me at john.doe@example.com"
        matches = detector.patterns['email'].findall(test_text)
        assert len(matches) > 0
        assert "john.doe@example.com" in matches

    def test_phone_pattern_detection(self):
        """Test phone number pattern detection"""
        detector = PIIDetector()
        test_text = "Call me at 555-123-4567"
        matches = detector.patterns['phone'].findall(test_text)
        assert len(matches) > 0

    def test_ssn_pattern_detection(self):
        """Test SSN pattern detection"""
        detector = PIIDetector()
        test_text = "SSN: 123-45-6789"
        matches = detector.patterns['ssn'].findall(test_text)
        assert len(matches) > 0

    def test_credit_card_pattern_detection(self):
        """Test credit card pattern detection"""
        detector = PIIDetector()
        test_text = "Card: 1234 5678 9012 3456"
        matches = detector.patterns['credit_card'].findall(test_text)
        assert len(matches) > 0

    def test_ip_address_pattern_detection(self):
        """Test IP address pattern detection"""
        detector = PIIDetector()
        test_text = "IP address: 192.168.1.1"
        matches = detector.patterns['ip_address'].findall(test_text)
        assert len(matches) > 0

class TestSecurityMonitor:
    """Test SecurityMonitor class"""

    def test_security_monitor_initialization(self):
        """Test SecurityMonitor initialization"""
        config = {
            'max_failed_attempts': 5,
            'lockout_window': 15,
            'max_requests_per_minute': 100
        }
        monitor = SecurityMonitor(config)
        assert monitor is not None

    def test_security_monitor_with_default_config(self):
        """Test SecurityMonitor with default configuration"""
        monitor = SecurityMonitor({})
        assert monitor is not None

class TestLogRotationManager:
    """Test LogRotationManager class"""

    def test_log_rotation_manager_initialization(self):
        """Test LogRotationManager initialization"""
        config = {
            'max_file_size': 100 * 1024 * 1024,
            'retention_days': 30,
            'compress_old_logs': True
        }
        manager = LogRotationManager(config)
        assert manager is not None

    def test_log_rotation_manager_with_default_config(self):
        """Test LogRotationManager with default configuration"""
        manager = LogRotationManager({})
        assert manager is not None

class TestDatabaseManager:
    """Test DatabaseManager class"""

    def test_database_manager_initialization(self):
        """Test DatabaseManager initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'test.db')
            manager = DatabaseManager(db_path)
            assert manager is not None
            assert manager.db_path == db_path

class TestDatabaseLogger:
    """Test DatabaseLogger class"""

    def test_database_logger_initialization(self):
        """Test DatabaseLogger initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'test_logs.db')
            logger = DatabaseLogger(db_path)
            assert logger is not None
            assert os.path.exists(db_path)

class TestCloudIntegration:
    """Test CloudIntegration class"""

    def test_cloud_integration_initialization(self):
        """Test CloudIntegration initialization"""
        config = {
            'enabled_services': [],
            'webhook_url': None
        }
        integration = CloudIntegration(config)
        assert integration is not None

    def test_cloud_integration_with_webhook(self):
        """Test CloudIntegration with webhook URL"""
        config = {
            'enabled_services': ['webhook'],
            'webhook_url': 'https://example.com/webhook'
        }
        integration = CloudIntegration(config)
        assert integration is not None

class TestAnalyticsEngine:
    """Test AnalyticsEngine class"""

    def test_analytics_engine_initialization(self):
        """Test AnalyticsEngine initialization with DatabaseLogger"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'test_logs.db')
            db_logger = DatabaseLogger(db_path)
            analytics = AnalyticsEngine(db_logger)
            assert analytics is not None

    def test_analytics_engine_with_none(self):
        """Test AnalyticsEngine initialization with None"""
        analytics = AnalyticsEngine(None)
        assert analytics is not None

class TestEnhancedActivityLogger:
    """Test EnhancedActivityLogger class"""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for logs"""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def logger_config(self, temp_log_dir):
        """Create a test logger configuration"""
        return {
            'log_dir': temp_log_dir,
            'min_log_level': 'INFO',
            'output_formats': ['json'],
            'queue_size': 100,
            'batch_size': 10,
            'flush_interval': 1,
            'encrypt_logs': False,
            'enable_pii_detection': True
        }

    def test_logger_initialization_with_config(self, logger_config, temp_log_dir):
        """Test logger initialization with configuration"""
        config_path = os.path.join(temp_log_dir, 'config.json')
        with open(config_path, 'w') as f:
            json.dump(logger_config, f)

        with patch('education_system.systems.university.infrastructure.paths.LOG_DIR', temp_log_dir):
            logger = EnhancedActivityLogger(config_path)
            assert logger is not None
            # Give time for background thread to start
            time.sleep(0.1)
            logger.shutdown_event.set()
            if logger.processing_thread and logger.processing_thread.is_alive():
                logger.processing_thread.join(timeout=2)

    def test_logger_initialization_without_config(self, temp_log_dir):
        """Test logger initialization without configuration"""
        with patch('education_system.systems.university.infrastructure.paths.LOG_DIR', temp_log_dir):
            logger = EnhancedActivityLogger(None)
            assert logger is not None
            # Give time for background thread to start
            time.sleep(0.1)
            logger.shutdown_event.set()
            if logger.processing_thread and logger.processing_thread.is_alive():
                logger.processing_thread.join(timeout=2)

class TestLoggerPlugin:
    """Test LoggerPlugin base class"""

    def test_logger_plugin_initialization(self):
        """Test LoggerPlugin initialization"""
        config = {'enabled': True}
        plugin = LoggerPlugin(config)
        assert plugin.enabled is True

    def test_logger_plugin_process_log(self):
        """Test LoggerPlugin before_log and after_log methods"""
        config = {'enabled': True}
        plugin = LoggerPlugin(config)
        log_entry = LogEntry(
            timestamp='2025-01-01T12:00:00',
            user_id='user123',
            username='testuser',
            role='admin',
            action='test',
            module='test_module',
            details='Test',
            status='success',
            log_level='INFO',
            session_id='session123',
            ip_address='192.168.1.1',
            user_agent='test',
            request_size=0,
            response_size=0,
            processing_time=0.0,
            geolocation={},
            security_level='LOW',
            trace_id='trace123'
        )
        # Base class methods should not raise
        result = plugin.before_log(log_entry)
        assert result is not None
        plugin.after_log(log_entry, True)

class TestPluginManager:
    """Test PluginManager class"""

    def test_plugin_manager_initialization(self):
        """Test PluginManager initialization"""
        manager = PluginManager()
        assert manager is not None
        assert hasattr(manager, 'plugins')

class TestSlackNotificationPlugin:
    """Test SlackNotificationPlugin class"""

    def test_slack_plugin_initialization(self):
        """Test SlackNotificationPlugin initialization"""
        config = {'slack_webhook_url': 'https://hooks.slack.com/test'}
        plugin = SlackNotificationPlugin(config)
        assert plugin.__class__.__name__ == "SlackNotificationPlugin"
        assert plugin.enabled is True
        assert plugin.webhook_url == 'https://hooks.slack.com/test'

class TestMetricsCollectionPlugin:
    """Test MetricsCollectionPlugin class"""

    def test_metrics_plugin_initialization(self):
        """Test MetricsCollectionPlugin initialization"""
        config = {}
        plugin = MetricsCollectionPlugin(config)
        assert plugin.__class__.__name__ == "MetricsCollectionPlugin"
        assert plugin.enabled is True

class TestEmailNotificationPlugin:
    """Test EmailNotificationPlugin class"""

    def test_email_plugin_initialization(self):
        """Test EmailNotificationPlugin initialization"""
        config = {
            'smtp_host': 'smtp.example.com',
            'smtp_port': 587,
            'from_email': 'noreply@example.com'
        }
        plugin = EmailNotificationPlugin(config)
        assert plugin.__class__.__name__ == "EmailNotificationPlugin"
        assert plugin.enabled is True

class TestAuditTrailPlugin:
    """Test AuditTrailPlugin class"""

    def test_audit_trail_plugin_initialization(self):
        """Test AuditTrailPlugin initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {'audit_log_path': os.path.join(tmpdir, 'audit.log')}
            plugin = AuditTrailPlugin(config)
            assert plugin.__class__.__name__ == "AuditTrailPlugin"
            assert plugin.enabled is True

class TestHelperFunctions:
    """Test helper functions"""

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.get_logger_instance')
    def test_enhanced_log_activity(self, mock_get_logger):
        """Test enhanced_log_activity function"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        enhanced_log_activity(
            action='test_action',
            module='test_module',
            description='Test description'
        )
        # Function should call the logger

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.enhanced_log_activity')
    def test_log_create(self, mock_log):
        """Test log_create function"""
        log_create('test_module', description='Created something')
        mock_log.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.enhanced_log_activity')
    def test_log_read(self, mock_log):
        """Test log_read function"""
        log_read('test_module', description='Read something')
        mock_log.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.enhanced_log_activity')
    def test_log_update(self, mock_log):
        """Test log_update function"""
        log_update('test_module', description='Updated something')
        mock_log.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.enhanced_log_activity')
    def test_log_delete(self, mock_log):
        """Test log_delete function"""
        log_delete('test_module', description='Deleted something')
        mock_log.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.enhanced_log_activity')
    def test_log_search(self, mock_log):
        """Test log_search function"""
        log_search('test_module', description='Searched something')
        mock_log.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.enhanced_log_activity')
    def test_log_export(self, mock_log):
        """Test log_export function"""
        log_export('test_module', description='Exported something')
        mock_log.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.enhanced_log_activity')
    def test_log_admin_action(self, mock_log):
        """Test log_admin_action function"""
        log_admin_action('test_module', description='Admin action')
        mock_log.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.enhanced_log_activity')
    def test_log_menu_navigation(self, mock_log):
        """Test log_menu_navigation function"""
        log_menu_navigation(description='Navigated to menu')
        mock_log.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.get_logger_instance')
    def test_log_activity(self, mock_get_logger):
        """Test log_activity function"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        log_activity(
            user_id='user123',
            username='testuser',
            role='admin',
            action='login',
            module='auth',
            details='User logged in'
        )

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.logger')
    def test_log_login(self, mock_logger):
        """Test log_login function"""
        mock_logger.log_activity = Mock()
        log_login('user123', 'testuser', 'admin')
        mock_logger.log_activity.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.logger')
    def test_log_logout(self, mock_logger):
        """Test log_logout function"""
        mock_logger.log_activity = Mock()
        log_logout('user123', 'testuser', 'admin')
        mock_logger.log_activity.assert_called_once()

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.get_logger_instance')
    def test_log_dynamic_activity(self, mock_get_logger):
        """Test log_dynamic_activity function"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        log_dynamic_activity(
            action='test_action',
            module='test_module',
            details='Test details'
        )

    def test_load_logger_config(self):
        """Test load_logger_config function"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'config.json')
            config_data = {
                'log_dir': tmpdir,
                'min_log_level': 'DEBUG',
                'output_formats': ['json']
            }
            with open(config_path, 'w') as f:
                json.dump(config_data, f)

            with patch('education_system.systems.university.infrastructure.paths.LOG_DIR', tmpdir):
                # load_logger_config doesn't return anything, it updates global logger
                load_logger_config(config_path)
                # Get the global logger instance
                logger = get_logger_instance()
                assert logger is not None
                # Cleanup
                if logger:
                    logger.shutdown_event.set()
                    if logger.processing_thread and logger.processing_thread.is_alive():
                        logger.processing_thread.join(timeout=2)

    def test_get_logger_instance(self):
        """Test get_logger_instance function"""
        logger = get_logger_instance()
        assert logger is not None
        # Clean up
        if logger:
            logger.shutdown_event.set()
            if logger.processing_thread and logger.processing_thread.is_alive():
                logger.processing_thread.join(timeout=2)

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.get_logger_instance')
    def test_register_plugin(self, mock_get_logger):
        """Test register_plugin function"""
        mock_logger = Mock()
        mock_logger.plugin_manager = Mock()
        mock_get_logger.return_value = mock_logger

        plugin = LoggerPlugin({'enabled': True})
        register_plugin(plugin)

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.get_logger_instance')
    def test_unregister_plugin(self, mock_get_logger):
        """Test unregister_plugin function"""
        mock_logger = Mock()
        mock_logger.plugin_manager = Mock()
        mock_get_logger.return_value = mock_logger

        unregister_plugin("TestPlugin")

    @patch('education_system.systems.university.infrastructure.utils.activity_logger.get_logger_instance')
    def test_get_plugin_status(self, mock_get_logger):
        """Test get_plugin_status function"""
        mock_logger = Mock()
        mock_logger.plugin_manager = Mock()
        mock_logger.plugin_manager.get_status.return_value = []
        mock_get_logger.return_value = mock_logger

        status = get_plugin_status()
        assert isinstance(status, list)

    def test_create_default_config(self):
        """Test create_default_config function"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'logger_config.json')
            create_default_config(config_path)
            assert os.path.exists(config_path)

            # Verify config is valid JSON
            with open(config_path, 'r') as f:
                config = json.load(f)
            assert isinstance(config, dict)

class TestIntegration:
    """Integration tests for complex workflows"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory"""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_full_logging_workflow(self, temp_dir):
        """Test a complete logging workflow"""
        config = {
            'log_dir': temp_dir,
            'min_log_level': 'DEBUG',
            'output_formats': ['json'],
            'queue_size': 100
        }

        config_path = os.path.join(temp_dir, 'config.json')
        with open(config_path, 'w') as f:
            json.dump(config, f)

        with patch('education_system.systems.university.infrastructure.paths.LOG_DIR', temp_dir):
            logger = EnhancedActivityLogger(config_path)

            # Give background thread time to start
            time.sleep(0.1)

            # Cleanup
            logger.shutdown_event.set()
            if logger.processing_thread and logger.processing_thread.is_alive():
                logger.processing_thread.join(timeout=2)

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
