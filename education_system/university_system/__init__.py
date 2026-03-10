"""
University Management System

A comprehensive enterprise-grade university management platform built with Python.
Integrates academic, financial, student affairs, health services, and administrative
operations into a unified system.

Version: 5.0.0
Python: 3.8+
Database: SQLite (default), PostgreSQL/MySQL supported
Architecture: 4-layer domain-driven design

Main Components:
- Core: Fundamental primitives (paths, exceptions, types)
- Infrastructure: Auth, database, email, security, real-time, ML
- Modules: Domain logic and service implementations
- API: REST API and WebSocket endpoints
- Tests: Comprehensive test suite

Usage:
    # CLI Mode
    python run.py --cli

    # GUI Mode
    python run.py --gui

    # API Server
    uvicorn university_system.api.app:app --reload

    # Tests
    python -m pytest university_system/tests/
"""

__version__ = '5.0.0'
__author__ = 'University IT Team'
__license__ = 'MIT'

# Core primitives (no dependencies)
from education_system.university_system.core import (
    # Exceptions
    UniversitySystemError,
    DatabaseError,
    AuthenticationError,
    ValidationError,
    StudentError,
    CourseError,
    EnrollmentError,
    GradeError,
    FinanceError,
    EmailError,
    FileError,
    ConfigurationError,
    # Paths
    BASE_DIR,
    UNIVERSITY_SYSTEM_DIR,
    DATA_DIR,
    DB_DIR,
    DEFAULT_DB_PATH,
    LOG_DIR,
    REPORTS_DIR,
    UPLOADS_DIR,
    TEMP_DIR,
    TEMPLATES_DIR,
)

# Infrastructure services - use lazy imports to avoid circular dependencies
# These will be imported on first use rather than at module load time
_infrastructure_loaded = False

def _load_infrastructure():
    """Lazy load infrastructure to prevent circular imports."""
    global _infrastructure_loaded
    if not _infrastructure_loaded:
        from university_system import infrastructure
        _infrastructure_loaded = True
        return infrastructure
    return None

# Provide module-level access via __getattr__ for backward compatibility
def __getattr__(name):
    """Lazy load infrastructure exports on first access."""
    infrastructure_exports = {
        'get_connection', 'transaction', 'DatabaseManager',
        'UserAuth', 'require_permission', 'require_role',
        'get_auth', 'set_auth',
        'SECURITY_AVAILABLE', 'VALIDATION_AVAILABLE', 'CACHE_AVAILABLE',
        'ASYNC_UTILS_AVAILABLE', 'ML_AVAILABLE',
    }

    ml_exports = {'get_course_recommender', 'get_essay_grader', 'get_plagiarism_detector'}

    if name in infrastructure_exports:
        from university_system import infrastructure
        return getattr(infrastructure, name)

    if name in ml_exports:
        ml_funcs = _get_ml_exports()
        if name in ml_funcs:
            return ml_funcs[name]
        raise AttributeError(f"ML feature '{name}' not available")

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# Conditional imports moved to lazy loading to prevent circular dependencies
# These will be available via __getattr__ when accessed

def _get_ml_exports():
    """Lazy load ML exports."""
    from education_system.university_system.infrastructure import ML_AVAILABLE
    if ML_AVAILABLE:
        from education_system.university_system.infrastructure.ml import (
            get_course_recommender,
            get_essay_grader,
            get_plagiarism_detector,
        )
        return {
            'get_course_recommender': get_course_recommender,
            'get_essay_grader': get_essay_grader,
            'get_plagiarism_detector': get_plagiarism_detector,
        }
    return {}

__all__ = [
    # Version info
    '__version__',
    '__author__',
    '__license__',

    # Core exceptions
    'UniversitySystemError',
    'DatabaseError',
    'AuthenticationError',
    'ValidationError',
    'StudentError',
    'CourseError',
    'EnrollmentError',
    'GradeError',
    'FinanceError',
    'EmailError',
    'FileError',
    'ConfigurationError',

    # Core paths
    'BASE_DIR',
    'UNIVERSITY_SYSTEM_DIR',
    'DATA_DIR',
    'DB_DIR',
    'DEFAULT_DB_PATH',
    'LOG_DIR',
    'REPORTS_DIR',
    'UPLOADS_DIR',
    'TEMP_DIR',
    'TEMPLATES_DIR',

    # Infrastructure - Database
    'get_connection',
    'transaction',
    'DatabaseManager',

    # Infrastructure - Auth
    'UserAuth',
    'require_permission',
    'require_role',
    'get_auth',
    'set_auth',

    # Availability flags
    'SECURITY_AVAILABLE',
    'VALIDATION_AVAILABLE',
    'CACHE_AVAILABLE',
    'ASYNC_UTILS_AVAILABLE',
    'ML_AVAILABLE',
]

# Conditional exports added to __all__ (available via lazy loading)
__all__.extend([
    # ML exports (if available)
    'get_course_recommender',
    'get_essay_grader',
    'get_plagiarism_detector',
])
