"""
Comprehensive tests for database configuration constants.

Tests all constants defined in infrastructure.database.constants,
including environment variable overrides, default values, types,
and the __all__ export list.
"""

import os
import pytest
from unittest.mock import patch


class TestConnectionSettingsDefaults:
    """Test default values for connection settings constants."""

    def test_default_db_timeout_value(self):
        """Test DEFAULT_DB_TIMEOUT has expected default of 30.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import DEFAULT_DB_TIMEOUT
        # Without env override, should be 30.0
        assert DEFAULT_DB_TIMEOUT == 30.0

    def test_sqlite_busy_timeout_value(self):
        """Test SQLITE_BUSY_TIMEOUT has expected default of 30000."""
        from education_system.post_18.university_system.infrastructure.database.constants import SQLITE_BUSY_TIMEOUT
        assert SQLITE_BUSY_TIMEOUT == 30000

    def test_max_retry_attempts_value(self):
        """Test MAX_RETRY_ATTEMPTS has expected default of 3."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_RETRY_ATTEMPTS
        assert MAX_RETRY_ATTEMPTS == 3

    def test_retry_delay_value(self):
        """Test RETRY_DELAY has expected default of 0.5."""
        from education_system.post_18.university_system.infrastructure.database.constants import RETRY_DELAY
        assert RETRY_DELAY == 0.5


class TestConnectionSettingsEnvOverrides:
    """Test environment variable overrides for connection settings."""

    def test_db_timeout_env_override(self):
        """Test DEFAULT_DB_TIMEOUT can be overridden via DB_TIMEOUT env var."""
        with patch.dict(os.environ, {'DB_TIMEOUT': '60.0'}):
            # Need to reimport since constants are evaluated at module load time
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.DEFAULT_DB_TIMEOUT == 60.0
            # Restore
            del os.environ['DB_TIMEOUT']
            importlib.reload(mod)

    def test_sqlite_busy_timeout_env_override(self):
        """Test SQLITE_BUSY_TIMEOUT can be overridden via DB_BUSY_TIMEOUT env var."""
        with patch.dict(os.environ, {'DB_BUSY_TIMEOUT': '50000'}):
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.SQLITE_BUSY_TIMEOUT == 50000
            del os.environ['DB_BUSY_TIMEOUT']
            importlib.reload(mod)

    def test_max_retries_env_override(self):
        """Test MAX_RETRY_ATTEMPTS can be overridden via DB_MAX_RETRIES env var."""
        with patch.dict(os.environ, {'DB_MAX_RETRIES': '5'}):
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.MAX_RETRY_ATTEMPTS == 5
            del os.environ['DB_MAX_RETRIES']
            importlib.reload(mod)

    def test_retry_delay_env_override(self):
        """Test RETRY_DELAY can be overridden via DB_RETRY_DELAY env var."""
        with patch.dict(os.environ, {'DB_RETRY_DELAY': '1.0'}):
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.RETRY_DELAY == 1.0
            del os.environ['DB_RETRY_DELAY']
            importlib.reload(mod)


class TestPragmaSettingsDefaults:
    """Test default values and env overrides for PRAGMA settings."""

    def test_pragma_foreign_keys_default(self):
        """Test PRAGMA_FOREIGN_KEYS defaults to ON."""
        from education_system.post_18.university_system.infrastructure.database.constants import PRAGMA_FOREIGN_KEYS
        assert PRAGMA_FOREIGN_KEYS == 'ON'

    def test_pragma_journal_mode_default(self):
        """Test PRAGMA_JOURNAL_MODE defaults to WAL."""
        from education_system.post_18.university_system.infrastructure.database.constants import PRAGMA_JOURNAL_MODE
        assert PRAGMA_JOURNAL_MODE == 'WAL'

    def test_pragma_synchronous_default(self):
        """Test PRAGMA_SYNCHRONOUS defaults to NORMAL."""
        from education_system.post_18.university_system.infrastructure.database.constants import PRAGMA_SYNCHRONOUS
        assert PRAGMA_SYNCHRONOUS == 'NORMAL'

    def test_pragma_foreign_keys_env_override(self):
        """Test PRAGMA_FOREIGN_KEYS can be overridden."""
        with patch.dict(os.environ, {'DB_PRAGMA_FOREIGN_KEYS': 'OFF'}):
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.PRAGMA_FOREIGN_KEYS == 'OFF'
            del os.environ['DB_PRAGMA_FOREIGN_KEYS']
            importlib.reload(mod)

    def test_pragma_journal_mode_env_override(self):
        """Test PRAGMA_JOURNAL_MODE can be overridden."""
        with patch.dict(os.environ, {'DB_PRAGMA_JOURNAL_MODE': 'DELETE'}):
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.PRAGMA_JOURNAL_MODE == 'DELETE'
            del os.environ['DB_PRAGMA_JOURNAL_MODE']
            importlib.reload(mod)

    def test_pragma_synchronous_env_override(self):
        """Test PRAGMA_SYNCHRONOUS can be overridden."""
        with patch.dict(os.environ, {'DB_PRAGMA_SYNCHRONOUS': 'FULL'}):
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.PRAGMA_SYNCHRONOUS == 'FULL'
            del os.environ['DB_PRAGMA_SYNCHRONOUS']
            importlib.reload(mod)


class TestConnectionPoolDefaults:
    """Test connection pool default values and env overrides."""

    def test_max_pool_connections_default(self):
        """Test MAX_POOL_CONNECTIONS defaults to 10."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_POOL_CONNECTIONS
        assert MAX_POOL_CONNECTIONS == 10

    def test_min_pool_connections_default(self):
        """Test MIN_POOL_CONNECTIONS defaults to 2."""
        from education_system.post_18.university_system.infrastructure.database.constants import MIN_POOL_CONNECTIONS
        assert MIN_POOL_CONNECTIONS == 2

    def test_pool_timeout_default(self):
        """Test POOL_TIMEOUT defaults to 30.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import POOL_TIMEOUT
        assert POOL_TIMEOUT == 30.0

    def test_max_connection_age_default(self):
        """Test MAX_CONNECTION_AGE defaults to 3600 (1 hour)."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_CONNECTION_AGE
        assert MAX_CONNECTION_AGE == 3600

    def test_pool_cleanup_interval_default(self):
        """Test POOL_CLEANUP_INTERVAL defaults to 300 (5 minutes)."""
        from education_system.post_18.university_system.infrastructure.database.constants import POOL_CLEANUP_INTERVAL
        assert POOL_CLEANUP_INTERVAL == 300

    def test_min_lte_max_pool_connections(self):
        """Test MIN_POOL_CONNECTIONS is always <= MAX_POOL_CONNECTIONS."""
        from education_system.post_18.university_system.infrastructure.database.constants import (
            MIN_POOL_CONNECTIONS, MAX_POOL_CONNECTIONS
        )
        assert MIN_POOL_CONNECTIONS <= MAX_POOL_CONNECTIONS

    def test_max_pool_connections_env_override(self):
        """Test MAX_POOL_CONNECTIONS can be overridden."""
        with patch.dict(os.environ, {'DB_MAX_CONNECTIONS': '50'}):
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.MAX_POOL_CONNECTIONS == 50
            del os.environ['DB_MAX_CONNECTIONS']
            importlib.reload(mod)

    def test_min_pool_connections_env_override(self):
        """Test MIN_POOL_CONNECTIONS can be overridden."""
        with patch.dict(os.environ, {'DB_MIN_CONNECTIONS': '5'}):
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.MIN_POOL_CONNECTIONS == 5
            del os.environ['DB_MIN_CONNECTIONS']
            importlib.reload(mod)

    def test_pool_timeout_env_override(self):
        """Test POOL_TIMEOUT can be overridden."""
        with patch.dict(os.environ, {'DB_POOL_TIMEOUT': '60.0'}):
            import importlib
            import education_system.post_18.university_system.infrastructure.database.constants as mod
            importlib.reload(mod)
            assert mod.POOL_TIMEOUT == 60.0
            del os.environ['DB_POOL_TIMEOUT']
            importlib.reload(mod)


class TestQueryPerformanceDefaults:
    """Test query performance constants."""

    def test_default_page_size(self):
        """Test DEFAULT_PAGE_SIZE is 50."""
        from education_system.post_18.university_system.infrastructure.database.constants import DEFAULT_PAGE_SIZE
        assert DEFAULT_PAGE_SIZE == 50

    def test_max_page_size(self):
        """Test MAX_PAGE_SIZE is 1000."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_PAGE_SIZE
        assert MAX_PAGE_SIZE == 1000

    def test_query_timeout(self):
        """Test QUERY_TIMEOUT is 60.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import QUERY_TIMEOUT
        assert QUERY_TIMEOUT == 60.0

    def test_max_page_size_gte_default(self):
        """Test MAX_PAGE_SIZE >= DEFAULT_PAGE_SIZE."""
        from education_system.post_18.university_system.infrastructure.database.constants import (
            DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
        )
        assert MAX_PAGE_SIZE >= DEFAULT_PAGE_SIZE


class TestBackupSettingsDefaults:
    """Test backup configuration constants."""

    def test_max_backups(self):
        """Test MAX_BACKUPS is 10."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_BACKUPS
        assert MAX_BACKUPS == 10

    def test_default_backup_interval(self):
        """Test DEFAULT_BACKUP_INTERVAL is 86400 (24 hours)."""
        from education_system.post_18.university_system.infrastructure.database.constants import DEFAULT_BACKUP_INTERVAL
        assert DEFAULT_BACKUP_INTERVAL == 86400

    def test_backup_compression_level(self):
        """Test BACKUP_COMPRESSION_LEVEL is 6 and in valid range 1-9."""
        from education_system.post_18.university_system.infrastructure.database.constants import BACKUP_COMPRESSION_LEVEL
        assert BACKUP_COMPRESSION_LEVEL == 6
        assert 1 <= BACKUP_COMPRESSION_LEVEL <= 9


class TestEmailConstants:
    """Test email configuration constants."""

    def test_min_email_send_delay(self):
        """Test MIN_EMAIL_SEND_DELAY is 2.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import MIN_EMAIL_SEND_DELAY
        assert MIN_EMAIL_SEND_DELAY == 2.0

    def test_default_email_send_delay(self):
        """Test DEFAULT_EMAIL_SEND_DELAY is 2.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import DEFAULT_EMAIL_SEND_DELAY
        assert DEFAULT_EMAIL_SEND_DELAY == 2.0

    def test_max_email_threads(self):
        """Test MAX_EMAIL_THREADS is 1."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_EMAIL_THREADS
        assert MAX_EMAIL_THREADS == 1

    def test_email_queue_size(self):
        """Test EMAIL_QUEUE_SIZE is 1000."""
        from education_system.post_18.university_system.infrastructure.database.constants import EMAIL_QUEUE_SIZE
        assert EMAIL_QUEUE_SIZE == 1000

    def test_email_max_retries(self):
        """Test EMAIL_MAX_RETRIES is 3."""
        from education_system.post_18.university_system.infrastructure.database.constants import EMAIL_MAX_RETRIES
        assert EMAIL_MAX_RETRIES == 3


class TestCacheConstants:
    """Test cache configuration constants."""

    def test_cache_ttl(self):
        """Test CACHE_TTL is 300 (5 minutes)."""
        from education_system.post_18.university_system.infrastructure.database.constants import CACHE_TTL
        assert CACHE_TTL == 300

    def test_max_cache_size(self):
        """Test MAX_CACHE_SIZE is 1000."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_CACHE_SIZE
        assert MAX_CACHE_SIZE == 1000


class TestValidationLimitsDefaults:
    """Test validation limit constants."""

    def test_max_student_id_length(self):
        """Test MAX_STUDENT_ID_LENGTH is 20."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_STUDENT_ID_LENGTH
        assert MAX_STUDENT_ID_LENGTH == 20

    def test_max_email_length(self):
        """Test MAX_EMAIL_LENGTH is 255."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_EMAIL_LENGTH
        assert MAX_EMAIL_LENGTH == 255

    def test_max_name_length(self):
        """Test MAX_NAME_LENGTH is 100."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_NAME_LENGTH
        assert MAX_NAME_LENGTH == 100

    def test_max_text_length(self):
        """Test MAX_TEXT_LENGTH is 5000."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_TEXT_LENGTH
        assert MAX_TEXT_LENGTH == 5000

    def test_max_file_size(self):
        """Test MAX_FILE_SIZE is 10485760 (10 MB)."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_FILE_SIZE
        assert MAX_FILE_SIZE == 10485760


class TestGradeSystemDefaults:
    """Test grade system constants."""

    def test_min_grade(self):
        """Test MIN_GRADE is 0.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import MIN_GRADE
        assert MIN_GRADE == 0.0

    def test_max_grade(self):
        """Test MAX_GRADE is 100.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_GRADE
        assert MAX_GRADE == 100.0

    def test_passing_grade(self):
        """Test PASSING_GRADE is 50.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import PASSING_GRADE
        assert PASSING_GRADE == 50.0

    def test_gpa_range(self):
        """Test GPA range is 0.0 to 4.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import MIN_GPA, MAX_GPA
        assert MIN_GPA == 0.0
        assert MAX_GPA == 4.0


class TestSessionAndSecurityConstants:
    """Test session management and security constants."""

    def test_session_timeout(self):
        """Test SESSION_TIMEOUT is 3600 (1 hour)."""
        from education_system.post_18.university_system.infrastructure.database.constants import SESSION_TIMEOUT
        assert SESSION_TIMEOUT == 3600

    def test_remember_me_duration(self):
        """Test REMEMBER_ME_DURATION is 2592000 (30 days)."""
        from education_system.post_18.university_system.infrastructure.database.constants import REMEMBER_ME_DURATION
        assert REMEMBER_ME_DURATION == 2592000

    def test_max_sessions_per_user(self):
        """Test MAX_SESSIONS_PER_USER is 5."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_SESSIONS_PER_USER
        assert MAX_SESSIONS_PER_USER == 5

    def test_max_login_attempts(self):
        """Test MAX_LOGIN_ATTEMPTS is 5."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_LOGIN_ATTEMPTS
        assert MAX_LOGIN_ATTEMPTS == 5

    def test_lockout_duration(self):
        """Test LOCKOUT_DURATION is 900 (15 minutes)."""
        from education_system.post_18.university_system.infrastructure.database.constants import LOCKOUT_DURATION
        assert LOCKOUT_DURATION == 900

    def test_api_rate_limit(self):
        """Test API_RATE_LIMIT is 60."""
        from education_system.post_18.university_system.infrastructure.database.constants import API_RATE_LIMIT
        assert API_RATE_LIMIT == 60

    def test_password_hash_iterations(self):
        """Test PASSWORD_HASH_ITERATIONS is 1000000."""
        from education_system.post_18.university_system.infrastructure.database.constants import PASSWORD_HASH_ITERATIONS
        assert PASSWORD_HASH_ITERATIONS == 1_000_000

    def test_salt_length(self):
        """Test SALT_LENGTH is 32."""
        from education_system.post_18.university_system.infrastructure.database.constants import SALT_LENGTH
        assert SALT_LENGTH == 32

    def test_key_derivation_length(self):
        """Test KEY_DERIVATION_LENGTH is 64."""
        from education_system.post_18.university_system.infrastructure.database.constants import KEY_DERIVATION_LENGTH
        assert KEY_DERIVATION_LENGTH == 64

    def test_password_reset_token_expiry(self):
        """Test PASSWORD_RESET_TOKEN_EXPIRY is 3600."""
        from education_system.post_18.university_system.infrastructure.database.constants import PASSWORD_RESET_TOKEN_EXPIRY
        assert PASSWORD_RESET_TOKEN_EXPIRY == 3600


class TestStorageAndMonitoringConstants:
    """Test storage limits and monitoring constants."""

    def test_user_storage_quota(self):
        """Test USER_STORAGE_QUOTA is 1 GB."""
        from education_system.post_18.university_system.infrastructure.database.constants import USER_STORAGE_QUOTA
        assert USER_STORAGE_QUOTA == 1073741824

    def test_max_database_size(self):
        """Test MAX_DATABASE_SIZE is 10 GB."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_DATABASE_SIZE
        assert MAX_DATABASE_SIZE == 10737418240

    def test_stats_log_interval(self):
        """Test STATS_LOG_INTERVAL is 3600."""
        from education_system.post_18.university_system.infrastructure.database.constants import STATS_LOG_INTERVAL
        assert STATS_LOG_INTERVAL == 3600

    def test_max_log_file_size(self):
        """Test MAX_LOG_FILE_SIZE is 10 MB."""
        from education_system.post_18.university_system.infrastructure.database.constants import MAX_LOG_FILE_SIZE
        assert MAX_LOG_FILE_SIZE == 10485760

    def test_log_file_backup_count(self):
        """Test LOG_FILE_BACKUP_COUNT is 5."""
        from education_system.post_18.university_system.infrastructure.database.constants import LOG_FILE_BACKUP_COUNT
        assert LOG_FILE_BACKUP_COUNT == 5

    def test_health_check_interval(self):
        """Test HEALTH_CHECK_INTERVAL is 60."""
        from education_system.post_18.university_system.infrastructure.database.constants import HEALTH_CHECK_INTERVAL
        assert HEALTH_CHECK_INTERVAL == 60

    def test_health_check_query_timeout(self):
        """Test HEALTH_CHECK_QUERY_TIMEOUT is 1.0."""
        from education_system.post_18.university_system.infrastructure.database.constants import HEALTH_CHECK_QUERY_TIMEOUT
        assert HEALTH_CHECK_QUERY_TIMEOUT == 1.0


class TestAllExports:
    """Test __all__ export list completeness and validity."""

    def test_all_is_list(self):
        """Test __all__ is a list."""
        from education_system.post_18.university_system.infrastructure.database import constants
        assert isinstance(constants.__all__, list)

    def test_all_names_exist_as_attributes(self):
        """Test every name in __all__ is a real module attribute."""
        from education_system.post_18.university_system.infrastructure.database import constants
        for name in constants.__all__:
            assert hasattr(constants, name), f"{name} in __all__ but not defined"

    def test_all_contains_connection_constants(self):
        """Test __all__ contains connection constants."""
        from education_system.post_18.university_system.infrastructure.database.constants import __all__
        for name in ['DEFAULT_DB_TIMEOUT', 'SQLITE_BUSY_TIMEOUT',
                     'MAX_RETRY_ATTEMPTS', 'RETRY_DELAY']:
            assert name in __all__

    def test_all_contains_pragma_constants(self):
        """Test __all__ contains PRAGMA constants."""
        from education_system.post_18.university_system.infrastructure.database.constants import __all__
        for name in ['PRAGMA_FOREIGN_KEYS', 'PRAGMA_JOURNAL_MODE', 'PRAGMA_SYNCHRONOUS']:
            assert name in __all__

    def test_all_contains_pool_constants(self):
        """Test __all__ contains pool constants."""
        from education_system.post_18.university_system.infrastructure.database.constants import __all__
        for name in ['MAX_POOL_CONNECTIONS', 'MIN_POOL_CONNECTIONS',
                     'POOL_TIMEOUT', 'MAX_CONNECTION_AGE', 'POOL_CLEANUP_INTERVAL']:
            assert name in __all__

    def test_all_has_expected_length(self):
        """Test __all__ has the expected number of exports."""
        from education_system.post_18.university_system.infrastructure.database.constants import __all__
        # There are many constants; ensure at least the documented ones are present
        assert len(__all__) >= 40


class TestConstantTypes:
    """Test that all constants have correct types."""

    def test_float_constants_are_float(self):
        """Test that timeout and delay constants are float."""
        from education_system.post_18.university_system.infrastructure.database import constants
        float_consts = [
            'DEFAULT_DB_TIMEOUT', 'RETRY_DELAY', 'POOL_TIMEOUT',
            'QUERY_TIMEOUT', 'MIN_EMAIL_SEND_DELAY', 'DEFAULT_EMAIL_SEND_DELAY',
            'MIN_GRADE', 'MAX_GRADE', 'PASSING_GRADE', 'MIN_GPA', 'MAX_GPA',
            'HEALTH_CHECK_QUERY_TIMEOUT',
        ]
        for name in float_consts:
            val = getattr(constants, name)
            assert isinstance(val, (int, float)), f"{name} should be numeric, got {type(val)}"

    def test_int_constants_are_int(self):
        """Test that count and size constants are int."""
        from education_system.post_18.university_system.infrastructure.database import constants
        int_consts = [
            'SQLITE_BUSY_TIMEOUT', 'MAX_RETRY_ATTEMPTS',
            'MAX_POOL_CONNECTIONS', 'MIN_POOL_CONNECTIONS',
            'MAX_CONNECTION_AGE', 'POOL_CLEANUP_INTERVAL',
            'DEFAULT_PAGE_SIZE', 'MAX_PAGE_SIZE',
            'MAX_BACKUPS', 'DEFAULT_BACKUP_INTERVAL', 'BACKUP_COMPRESSION_LEVEL',
            'MAX_EMAIL_THREADS', 'EMAIL_QUEUE_SIZE', 'EMAIL_MAX_RETRIES',
            'CACHE_TTL', 'MAX_CACHE_SIZE',
            'MAX_STUDENT_ID_LENGTH', 'MAX_EMAIL_LENGTH', 'MAX_NAME_LENGTH',
            'MAX_TEXT_LENGTH', 'MAX_FILE_SIZE',
            'DEFAULT_ITEMS_PER_PAGE', 'MAX_ITEMS_PER_PAGE',
            'SESSION_TIMEOUT', 'REMEMBER_ME_DURATION', 'MAX_SESSIONS_PER_USER',
            'MAX_LOGIN_ATTEMPTS', 'LOCKOUT_DURATION', 'API_RATE_LIMIT',
            'PASSWORD_HASH_ITERATIONS', 'SALT_LENGTH', 'KEY_DERIVATION_LENGTH',
            'PASSWORD_RESET_TOKEN_EXPIRY',
            'USER_STORAGE_QUOTA', 'MAX_DATABASE_SIZE',
            'STATS_LOG_INTERVAL', 'MAX_LOG_FILE_SIZE', 'LOG_FILE_BACKUP_COUNT',
            'LOG_ROTATION_INTERVAL', 'HEALTH_CHECK_INTERVAL',
        ]
        for name in int_consts:
            val = getattr(constants, name)
            assert isinstance(val, int), f"{name} should be int, got {type(val)}"

    def test_string_constants_are_string(self):
        """Test that PRAGMA constants are strings."""
        from education_system.post_18.university_system.infrastructure.database import constants
        str_consts = ['PRAGMA_FOREIGN_KEYS', 'PRAGMA_JOURNAL_MODE', 'PRAGMA_SYNCHRONOUS']
        for name in str_consts:
            val = getattr(constants, name)
            assert isinstance(val, str), f"{name} should be str, got {type(val)}"

    def test_all_constants_positive(self):
        """Test that all numeric constants are positive (or zero for min values)."""
        from education_system.post_18.university_system.infrastructure.database import constants
        for name in constants.__all__:
            val = getattr(constants, name)
            if isinstance(val, (int, float)):
                assert val >= 0, f"{name} should be >= 0, got {val}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
