"""Shared database constants used by all education subsystems."""

# Connection settings
CONNECTION_TIMEOUT = 30
BUSY_TIMEOUT = 5000  # milliseconds

# Connection pool
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 5

# SQLite PRAGMAs for performance and safety
PRAGMAS = {
    "journal_mode": "WAL",
    "foreign_keys": "ON",
    "busy_timeout": str(BUSY_TIMEOUT),
    "cache_size": "-8000",  # 8MB
    "synchronous": "NORMAL",
}

# Common attendance statuses (basic set shared across systems)
COMMON_ATTENDANCE_STATUSES = ("present", "absent", "late", "excused")

# Terms (UK academic calendar)
TERMS = ("Autumn", "Spring", "Summer")
