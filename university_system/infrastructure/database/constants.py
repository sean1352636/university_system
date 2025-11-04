"""
Database configuration constants.

This module defines all magic numbers and configuration values used
throughout the database layer, making them explicit and easy to modify.
"""

# ============================================================================
# Connection Settings
# ============================================================================

# Default timeout for database operations (seconds)
DEFAULT_DB_TIMEOUT = 30.0

# SQLite busy timeout - how long to wait for locks (milliseconds)
SQLITE_BUSY_TIMEOUT = 5000

# Maximum number of retry attempts for failed operations
MAX_RETRY_ATTEMPTS = 3

# Delay between retry attempts (seconds)
RETRY_DELAY = 0.5

# ============================================================================
# PRAGMA Settings
# ============================================================================

# Enable foreign key constraints
PRAGMA_FOREIGN_KEYS = "ON"

# Use Write-Ahead Logging for better concurrency
PRAGMA_JOURNAL_MODE = "WAL"

# Synchronous mode (NORMAL is good balance of safety/performance)
# Options: OFF, NORMAL, FULL, EXTRA
PRAGMA_SYNCHRONOUS = "NORMAL"

# ============================================================================
# Connection Pool Settings
# ============================================================================

# Maximum number of connections in the pool
MAX_POOL_CONNECTIONS = 10

# Minimum number of connections to keep alive
MIN_POOL_CONNECTIONS = 2

# Connection pool timeout (seconds)
POOL_TIMEOUT = 30.0

# Maximum time to keep an idle connection (seconds)
MAX_CONNECTION_AGE = 3600  # 1 hour

# How often to check for expired connections (seconds)
POOL_CLEANUP_INTERVAL = 300  # 5 minutes

# ============================================================================
# Query Performance
# ============================================================================

# Default page size for pagination
DEFAULT_PAGE_SIZE = 50

# Maximum page size to prevent memory issues
MAX_PAGE_SIZE = 1000

# Query timeout for long-running queries (seconds)
QUERY_TIMEOUT = 60.0

# ============================================================================
# Backup Settings
# ============================================================================

# Maximum number of backups to keep
MAX_BACKUPS = 10

# Default backup interval (seconds)
DEFAULT_BACKUP_INTERVAL = 86400  # 24 hours

# Backup compression level (1-9, where 9 is maximum compression)
BACKUP_COMPRESSION_LEVEL = 6

# ============================================================================
# Email Configuration
# ============================================================================

# Minimum delay between emails to avoid spam detection (seconds)
MIN_EMAIL_SEND_DELAY = 2.0

# Default email send delay (seconds)
DEFAULT_EMAIL_SEND_DELAY = 2.0

# Maximum number of email worker threads
MAX_EMAIL_THREADS = 1  # Single thread to maintain send order

# Email queue size
EMAIL_QUEUE_SIZE = 1000

# Email retry attempts
EMAIL_MAX_RETRIES = 3

# ============================================================================
# Cache Settings
# ============================================================================

# Cache entry time-to-live (seconds)
CACHE_TTL = 300  # 5 minutes

# Maximum cache size (entries)
MAX_CACHE_SIZE = 1000

# ============================================================================
# Validation Limits
# ============================================================================

# Maximum length for student ID
MAX_STUDENT_ID_LENGTH = 20

# Maximum length for email addresses
MAX_EMAIL_LENGTH = 255

# Maximum length for names
MAX_NAME_LENGTH = 100

# Maximum length for text fields
MAX_TEXT_LENGTH = 5000

# Maximum file upload size (bytes)
MAX_FILE_SIZE = 10485760  # 10 MB

# ============================================================================
# Grade System
# ============================================================================

# Valid grade range
MIN_GRADE = 0.0
MAX_GRADE = 100.0

# Passing grade threshold
PASSING_GRADE = 50.0

# GPA scale
MIN_GPA = 0.0
MAX_GPA = 4.0

# ============================================================================
# Pagination
# ============================================================================

# Default items per page
DEFAULT_ITEMS_PER_PAGE = 20

# Maximum items per page
MAX_ITEMS_PER_PAGE = 100

# ============================================================================
# Session Management
# ============================================================================

# Session timeout (seconds)
SESSION_TIMEOUT = 3600  # 1 hour

# Remember me cookie duration (seconds)
REMEMBER_ME_DURATION = 2592000  # 30 days

# Maximum concurrent sessions per user
MAX_SESSIONS_PER_USER = 5

# ============================================================================
# Rate Limiting
# ============================================================================

# Maximum login attempts before lockout
MAX_LOGIN_ATTEMPTS = 5

# Account lockout duration (seconds)
LOCKOUT_DURATION = 900  # 15 minutes

# API rate limit (requests per minute)
API_RATE_LIMIT = 60

# ============================================================================
# Cryptography
# ============================================================================

# Password hashing iterations (PBKDF2)
PASSWORD_HASH_ITERATIONS = 1_000_000  # 1 million (OWASP recommendation)

# Salt length for password hashing (bytes)
SALT_LENGTH = 32

# Key derivation length (bytes)
KEY_DERIVATION_LENGTH = 64

# Token expiry for password reset (seconds)
PASSWORD_RESET_TOKEN_EXPIRY = 3600  # 1 hour

# ============================================================================
# Storage Limits
# ============================================================================

# Storage quota per user (bytes)
USER_STORAGE_QUOTA = 1073741824  # 1 GB

# Maximum database size (bytes)
MAX_DATABASE_SIZE = 10737418240  # 10 GB

# ============================================================================
# Monitoring & Logging
# ============================================================================

# How often to log statistics (seconds)
STATS_LOG_INTERVAL = 3600  # 1 hour

# Maximum log file size (bytes)
MAX_LOG_FILE_SIZE = 10485760  # 10 MB

# Number of log files to keep
LOG_FILE_BACKUP_COUNT = 5

# Log rotation interval (seconds)
LOG_ROTATION_INTERVAL = 86400  # 24 hours

# ============================================================================
# Health Check
# ============================================================================

# Database health check interval (seconds)
HEALTH_CHECK_INTERVAL = 60

# Maximum acceptable query time for health check (seconds)
HEALTH_CHECK_QUERY_TIMEOUT = 1.0

# ============================================================================
# Export all constants
# ============================================================================

__all__ = [
    # Connection
    'DEFAULT_DB_TIMEOUT',
    'SQLITE_BUSY_TIMEOUT',
    'MAX_RETRY_ATTEMPTS',
    'RETRY_DELAY',
    # PRAGMA
    'PRAGMA_FOREIGN_KEYS',
    'PRAGMA_JOURNAL_MODE',
    'PRAGMA_SYNCHRONOUS',
    # Connection Pool
    'MAX_POOL_CONNECTIONS',
    'MIN_POOL_CONNECTIONS',
    'POOL_TIMEOUT',
    'MAX_CONNECTION_AGE',
    'POOL_CLEANUP_INTERVAL',
    # Query Performance
    'DEFAULT_PAGE_SIZE',
    'MAX_PAGE_SIZE',
    'QUERY_TIMEOUT',
    # Backup
    'MAX_BACKUPS',
    'DEFAULT_BACKUP_INTERVAL',
    'BACKUP_COMPRESSION_LEVEL',
    # Email
    'MIN_EMAIL_SEND_DELAY',
    'DEFAULT_EMAIL_SEND_DELAY',
    'MAX_EMAIL_THREADS',
    'EMAIL_QUEUE_SIZE',
    'EMAIL_MAX_RETRIES',
    # Cache
    'CACHE_TTL',
    'MAX_CACHE_SIZE',
    # Validation
    'MAX_STUDENT_ID_LENGTH',
    'MAX_EMAIL_LENGTH',
    'MAX_NAME_LENGTH',
    'MAX_TEXT_LENGTH',
    'MAX_FILE_SIZE',
    # Grades
    'MIN_GRADE',
    'MAX_GRADE',
    'PASSING_GRADE',
    'MIN_GPA',
    'MAX_GPA',
    # Pagination
    'DEFAULT_ITEMS_PER_PAGE',
    'MAX_ITEMS_PER_PAGE',
    # Session
    'SESSION_TIMEOUT',
    'REMEMBER_ME_DURATION',
    'MAX_SESSIONS_PER_USER',
    # Rate Limiting
    'MAX_LOGIN_ATTEMPTS',
    'LOCKOUT_DURATION',
    'API_RATE_LIMIT',
    # Cryptography
    'PASSWORD_HASH_ITERATIONS',
    'SALT_LENGTH',
    'KEY_DERIVATION_LENGTH',
    'PASSWORD_RESET_TOKEN_EXPIRY',
    # Storage
    'USER_STORAGE_QUOTA',
    'MAX_DATABASE_SIZE',
    # Monitoring
    'STATS_LOG_INTERVAL',
    'MAX_LOG_FILE_SIZE',
    'LOG_FILE_BACKUP_COUNT',
    'LOG_ROTATION_INTERVAL',
    # Health Check
    'HEALTH_CHECK_INTERVAL',
    'HEALTH_CHECK_QUERY_TIMEOUT',
]
