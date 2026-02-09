"""
Database package initialisation.

This package centralises all database‑related utilities for the
application.  Modules should import ``sqlite3``, ``DatabaseManager``
and other helpers from :mod:`refactored.database.db` instead of
directly using the built‑in :mod:`sqlite3` module.  Doing so ensures
that all database connections are created consistently and that the
database file resides in a single, well‑defined location on disk.

Additional features:
- Query performance monitoring
- Connection pool metrics
- Schema validation
"""

# All imports are lazy to avoid circular dependency issues
_LAZY_MODULES = {
    # Core database from db.py
    'sqlite3': 'db',
    'DatabaseManager': 'db',
    'get_connection': 'db',
    'DEFAULT_DB_PATH': 'db',
    'DB_DIR': 'db',
    'EXPORTS_DIR': 'db',
    'transaction': 'db',
    'atomic_operation': 'db',
    'ConnectionPool': 'db',
    'get_connection_pool': 'db',
    # Query monitoring
    'QueryTimer': 'query_monitor',
    'QueryMonitor': 'query_monitor',
    'QueryMetrics': 'query_monitor',
    'QueryStats': 'query_monitor',
    'get_query_monitor': 'query_monitor',
    'time_query': 'query_monitor',
    # Pool metrics
    'PoolMetrics': 'pool_metrics',
    'PoolMetricsCollector': 'pool_metrics',
    'ConnectionEvent': 'pool_metrics',
    'get_pool_metrics': 'pool_metrics',
    # Schema validation
    'SchemaValidator': 'schema_validator',
    'SchemaValidationError': 'schema_validator',
    'TableSchema': 'schema_validator',
    'SchemaDifference': 'schema_validator',
    'validate_schema_at_startup': 'schema_validator',
}

def __getattr__(name):
    """Lazily import database components to avoid circular imports."""
    if name in _LAZY_MODULES:
        module_name = _LAZY_MODULES[name]
        import importlib
        module = importlib.import_module(f'.{module_name}', __name__)
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = list(_LAZY_MODULES.keys())
