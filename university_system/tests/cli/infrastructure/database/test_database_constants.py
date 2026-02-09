"""
Tests for database configuration constants.

This module tests all constants defined in the database.constants module
to ensure they have valid values and proper types.
"""

import pytest
from university_system.infrastructure.database import constants


class TestConnectionSettings:
    """Test connection-related constants."""

    def test_default_db_timeout(self):
        """Test default database timeout is positive number."""
        assert constants.DEFAULT_DB_TIMEOUT > 0
        assert isinstance(constants.DEFAULT_DB_TIMEOUT, (int, float))

    def test_sqlite_busy_timeout(self):
        """Test SQLite busy timeout is positive."""
        assert constants.SQLITE_BUSY_TIMEOUT > 0
        assert isinstance(constants.SQLITE_BUSY_TIMEOUT, int)

    def test_max_retry_attempts(self):
        """Test max retry attempts is positive integer."""
        assert constants.MAX_RETRY_ATTEMPTS > 0
        assert isinstance(constants.MAX_RETRY_ATTEMPTS, int)

    def test_retry_delay(self):
        """Test retry delay is positive number."""
        assert constants.RETRY_DELAY > 0
        assert isinstance(constants.RETRY_DELAY, (int, float))


class TestPragmaSettings:
    """Test PRAGMA-related constants."""

    def test_pragma_foreign_keys(self):
        """Test foreign keys pragma is valid."""
        assert constants.PRAGMA_FOREIGN_KEYS in ["ON", "OFF"]
        assert isinstance(constants.PRAGMA_FOREIGN_KEYS, str)

    def test_pragma_journal_mode(self):
        """Test journal mode pragma is valid."""
        valid_modes = ["DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"]
        assert constants.PRAGMA_JOURNAL_MODE in valid_modes
        assert isinstance(constants.PRAGMA_JOURNAL_MODE, str)

    def test_pragma_synchronous(self):
        """Test synchronous pragma is valid."""
        valid_modes = ["OFF", "NORMAL", "FULL", "EXTRA"]
        assert constants.PRAGMA_SYNCHRONOUS in valid_modes
        assert isinstance(constants.PRAGMA_SYNCHRONOUS, str)


class TestConnectionPoolSettings:
    """Test connection pool-related constants."""

    def test_max_pool_connections(self):
        """Test max pool connections is positive."""
        assert constants.MAX_POOL_CONNECTIONS > 0
        assert isinstance(constants.MAX_POOL_CONNECTIONS, int)

    def test_min_pool_connections(self):
        """Test min pool connections is valid."""
        assert constants.MIN_POOL_CONNECTIONS > 0
        assert constants.MIN_POOL_CONNECTIONS <= constants.MAX_POOL_CONNECTIONS
        assert isinstance(constants.MIN_POOL_CONNECTIONS, int)

    def test_pool_timeout(self):
        """Test pool timeout is positive."""
        assert constants.POOL_TIMEOUT > 0
        assert isinstance(constants.POOL_TIMEOUT, (int, float))

    def test_max_connection_age(self):
        """Test max connection age is positive."""
        assert constants.MAX_CONNECTION_AGE > 0
        assert isinstance(constants.MAX_CONNECTION_AGE, int)

    def test_pool_cleanup_interval(self):
        """Test pool cleanup interval is positive."""
        assert constants.POOL_CLEANUP_INTERVAL > 0
        assert isinstance(constants.POOL_CLEANUP_INTERVAL, int)


class TestQueryPerformance:
    """Test query performance-related constants."""

    def test_default_page_size(self):
        """Test default page size is positive."""
        assert constants.DEFAULT_PAGE_SIZE > 0
        assert isinstance(constants.DEFAULT_PAGE_SIZE, int)

    def test_max_page_size(self):
        """Test max page size is greater than default."""
        assert constants.MAX_PAGE_SIZE > 0
        assert constants.MAX_PAGE_SIZE >= constants.DEFAULT_PAGE_SIZE
        assert isinstance(constants.MAX_PAGE_SIZE, int)

    def test_query_timeout(self):
        """Test query timeout is positive."""
        assert constants.QUERY_TIMEOUT > 0
        assert isinstance(constants.QUERY_TIMEOUT, (int, float))


class TestBackupSettings:
    """Test backup-related constants."""

    def test_max_backups(self):
        """Test max backups is positive."""
        assert constants.MAX_BACKUPS > 0
        assert isinstance(constants.MAX_BACKUPS, int)

    def test_default_backup_interval(self):
        """Test default backup interval is positive."""
        assert constants.DEFAULT_BACKUP_INTERVAL > 0
        assert isinstance(constants.DEFAULT_BACKUP_INTERVAL, int)

    def test_backup_compression_level(self):
        """Test backup compression level is valid."""
        assert 1 <= constants.BACKUP_COMPRESSION_LEVEL <= 9
        assert isinstance(constants.BACKUP_COMPRESSION_LEVEL, int)


class TestEmailConfiguration:
    """Test email-related constants."""

    def test_min_email_send_delay(self):
        """Test min email send delay is non-negative."""
        assert constants.MIN_EMAIL_SEND_DELAY >= 0
        assert isinstance(constants.MIN_EMAIL_SEND_DELAY, (int, float))

    def test_default_email_send_delay(self):
        """Test default email send delay is valid."""
        assert constants.DEFAULT_EMAIL_SEND_DELAY >= constants.MIN_EMAIL_SEND_DELAY
        assert isinstance(constants.DEFAULT_EMAIL_SEND_DELAY, (int, float))

    def test_max_email_threads(self):
        """Test max email threads is positive."""
        assert constants.MAX_EMAIL_THREADS > 0
        assert isinstance(constants.MAX_EMAIL_THREADS, int)

    def test_email_queue_size(self):
        """Test email queue size is positive."""
        assert constants.EMAIL_QUEUE_SIZE > 0
        assert isinstance(constants.EMAIL_QUEUE_SIZE, int)

    def test_email_max_retries(self):
        """Test email max retries is non-negative."""
        assert constants.EMAIL_MAX_RETRIES >= 0
        assert isinstance(constants.EMAIL_MAX_RETRIES, int)


class TestCacheSettings:
    """Test cache-related constants."""

    def test_cache_ttl(self):
        """Test cache TTL is positive."""
        assert constants.CACHE_TTL > 0
        assert isinstance(constants.CACHE_TTL, int)

    def test_max_cache_size(self):
        """Test max cache size is positive."""
        assert constants.MAX_CACHE_SIZE > 0
        assert isinstance(constants.MAX_CACHE_SIZE, int)


class TestValidationLimits:
    """Test validation limit constants."""

    def test_max_student_id_length(self):
        """Test max student ID length is positive."""
        assert constants.MAX_STUDENT_ID_LENGTH > 0
        assert isinstance(constants.MAX_STUDENT_ID_LENGTH, int)

    def test_max_email_length(self):
        """Test max email length is reasonable."""
        assert constants.MAX_EMAIL_LENGTH >= 50  # Minimum reasonable email length
        assert isinstance(constants.MAX_EMAIL_LENGTH, int)

    def test_max_name_length(self):
        """Test max name length is positive."""
        assert constants.MAX_NAME_LENGTH > 0
        assert isinstance(constants.MAX_NAME_LENGTH, int)

    def test_max_text_length(self):
        """Test max text length is positive."""
        assert constants.MAX_TEXT_LENGTH > 0
        assert isinstance(constants.MAX_TEXT_LENGTH, int)

    def test_max_file_size(self):
        """Test max file size is positive."""
        assert constants.MAX_FILE_SIZE > 0
        assert isinstance(constants.MAX_FILE_SIZE, int)


class TestGradeSystem:
    """Test grade system constants."""

    def test_min_grade(self):
        """Test min grade is valid."""
        assert constants.MIN_GRADE >= 0
        assert isinstance(constants.MIN_GRADE, (int, float))

    def test_max_grade(self):
        """Test max grade is greater than min."""
        assert constants.MAX_GRADE > constants.MIN_GRADE
        assert isinstance(constants.MAX_GRADE, (int, float))

    def test_passing_grade(self):
        """Test passing grade is within valid range."""
        assert constants.MIN_GRADE <= constants.PASSING_GRADE <= constants.MAX_GRADE
        assert isinstance(constants.PASSING_GRADE, (int, float))

    def test_min_gpa(self):
        """Test min GPA is valid."""
        assert constants.MIN_GPA >= 0
        assert isinstance(constants.MIN_GPA, (int, float))

    def test_max_gpa(self):
        """Test max GPA is greater than min."""
        assert constants.MAX_GPA > constants.MIN_GPA
        assert isinstance(constants.MAX_GPA, (int, float))


class TestPagination:
    """Test pagination constants."""

    def test_default_items_per_page(self):
        """Test default items per page is positive."""
        assert constants.DEFAULT_ITEMS_PER_PAGE > 0
        assert isinstance(constants.DEFAULT_ITEMS_PER_PAGE, int)

    def test_max_items_per_page(self):
        """Test max items per page is greater than default."""
        assert constants.MAX_ITEMS_PER_PAGE >= constants.DEFAULT_ITEMS_PER_PAGE
        assert isinstance(constants.MAX_ITEMS_PER_PAGE, int)


class TestSessionManagement:
    """Test session management constants."""

    def test_session_timeout(self):
        """Test session timeout is positive."""
        assert constants.SESSION_TIMEOUT > 0
        assert isinstance(constants.SESSION_TIMEOUT, int)

    def test_remember_me_duration(self):
        """Test remember me duration is greater than session timeout."""
        assert constants.REMEMBER_ME_DURATION > constants.SESSION_TIMEOUT
        assert isinstance(constants.REMEMBER_ME_DURATION, int)

    def test_max_sessions_per_user(self):
        """Test max sessions per user is positive."""
        assert constants.MAX_SESSIONS_PER_USER > 0
        assert isinstance(constants.MAX_SESSIONS_PER_USER, int)


class TestRateLimiting:
    """Test rate limiting constants."""

    def test_max_login_attempts(self):
        """Test max login attempts is positive."""
        assert constants.MAX_LOGIN_ATTEMPTS > 0
        assert isinstance(constants.MAX_LOGIN_ATTEMPTS, int)

    def test_lockout_duration(self):
        """Test lockout duration is positive."""
        assert constants.LOCKOUT_DURATION > 0
        assert isinstance(constants.LOCKOUT_DURATION, int)

    def test_api_rate_limit(self):
        """Test API rate limit is positive."""
        assert constants.API_RATE_LIMIT > 0
        assert isinstance(constants.API_RATE_LIMIT, int)


class TestCryptography:
    """Test cryptography-related constants."""

    def test_password_hash_iterations(self):
        """Test password hash iterations meets OWASP recommendation."""
        # OWASP recommends at least 600,000 iterations for PBKDF2
        assert constants.PASSWORD_HASH_ITERATIONS >= 600_000
        assert isinstance(constants.PASSWORD_HASH_ITERATIONS, int)

    def test_salt_length(self):
        """Test salt length is adequate."""
        # Minimum 16 bytes recommended, 32 is better
        assert constants.SALT_LENGTH >= 16
        assert isinstance(constants.SALT_LENGTH, int)

    def test_key_derivation_length(self):
        """Test key derivation length is adequate."""
        assert constants.KEY_DERIVATION_LENGTH >= 32
        assert isinstance(constants.KEY_DERIVATION_LENGTH, int)

    def test_password_reset_token_expiry(self):
        """Test password reset token expiry is reasonable."""
        assert constants.PASSWORD_RESET_TOKEN_EXPIRY > 0
        assert isinstance(constants.PASSWORD_RESET_TOKEN_EXPIRY, int)


class TestStorageLimits:
    """Test storage limit constants."""

    def test_user_storage_quota(self):
        """Test user storage quota is positive."""
        assert constants.USER_STORAGE_QUOTA > 0
        assert isinstance(constants.USER_STORAGE_QUOTA, int)

    def test_max_database_size(self):
        """Test max database size is greater than user quota."""
        assert constants.MAX_DATABASE_SIZE > constants.USER_STORAGE_QUOTA
        assert isinstance(constants.MAX_DATABASE_SIZE, int)


class TestMonitoringAndLogging:
    """Test monitoring and logging constants."""

    def test_stats_log_interval(self):
        """Test stats log interval is positive."""
        assert constants.STATS_LOG_INTERVAL > 0
        assert isinstance(constants.STATS_LOG_INTERVAL, int)

    def test_max_log_file_size(self):
        """Test max log file size is positive."""
        assert constants.MAX_LOG_FILE_SIZE > 0
        assert isinstance(constants.MAX_LOG_FILE_SIZE, int)

    def test_log_file_backup_count(self):
        """Test log file backup count is positive."""
        assert constants.LOG_FILE_BACKUP_COUNT > 0
        assert isinstance(constants.LOG_FILE_BACKUP_COUNT, int)

    def test_log_rotation_interval(self):
        """Test log rotation interval is positive."""
        assert constants.LOG_ROTATION_INTERVAL > 0
        assert isinstance(constants.LOG_ROTATION_INTERVAL, int)


class TestHealthCheck:
    """Test health check constants."""

    def test_health_check_interval(self):
        """Test health check interval is positive."""
        assert constants.HEALTH_CHECK_INTERVAL > 0
        assert isinstance(constants.HEALTH_CHECK_INTERVAL, int)

    def test_health_check_query_timeout(self):
        """Test health check query timeout is positive and reasonable."""
        assert constants.HEALTH_CHECK_QUERY_TIMEOUT > 0
        assert constants.HEALTH_CHECK_QUERY_TIMEOUT < constants.QUERY_TIMEOUT
        assert isinstance(constants.HEALTH_CHECK_QUERY_TIMEOUT, (int, float))


class TestConstantsExport:
    """Test that all constants are properly exported."""

    def test_all_exports_defined(self):
        """Test that __all__ contains valid constant names."""
        for name in constants.__all__:
            assert hasattr(constants, name), f"Constant {name} in __all__ but not defined"

    def test_all_constants_exported(self):
        """Test that commonly used constants are in __all__."""
        essential_constants = [
            'DEFAULT_DB_TIMEOUT',
            'PRAGMA_FOREIGN_KEYS',
            'MAX_POOL_CONNECTIONS',
            'PASSWORD_HASH_ITERATIONS',
        ]
        for name in essential_constants:
            assert name in constants.__all__, f"Essential constant {name} not in __all__"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
