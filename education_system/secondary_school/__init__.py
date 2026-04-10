"""
Secondary School Management System

A management platform for secondary schools (Years 7–11, ages 11–16)
covering KS3/KS4 academics, GCSEs, behaviour, pastoral care, SEND,
safeguarding, attendance, and the wider secondary-school lifecycle.

Python: 3.11+
Database: SQLite (default)
Architecture: 4-layer domain-driven design — interface → service → infrastructure → data

Part of the Education System monorepo (university, college, secondary, primary).
"""

# Version is authoritative in pyproject.toml; this must stay in sync.
__version__ = "8.70.0"
__author__ = "Education System Team"
__license__ = "MIT"

__all__ = [
    "__version__",
    "__author__",
    "__license__",
]
